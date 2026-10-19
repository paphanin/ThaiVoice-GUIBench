"""Evaluate GUI grounding predictions against target element bboxes."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


BBox = list[float]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, default=Path("data/predictions/grounding_predictions.jsonl"))
    parser.add_argument("--screens", type=Path, default=Path("data/screens/screens.jsonl"))
    parser.add_argument("--utterances", type=Path, default=Path("data/utterances/utterances_audited.jsonl"))
    parser.add_argument("--manifest", type=Path, default=Path("data/audio/audio_manifest.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/predictions"))
    return parser.parse_args()


def load_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    if not path.exists():
        raise ValueError(f"{label} does not exist: {path}")
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{label}:{line_number}: invalid JSON: {exc.msg}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"{label}:{line_number}: expected JSON object")
            records.append(record)
    if not records:
        raise ValueError(f"{label} contains no records: {path}")
    return records


def write_jsonl(records: Iterable[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def normalize_prediction_record(record: dict[str, Any]) -> dict[str, Any]:
    copy = dict(record)
    copy.setdefault("failure_type", None)
    if copy.get("status") != "success" and copy.get("failure_type") in (None, ""):
        copy["failure_type"] = "unparseable_model_output"
    return copy


def index_by(records: list[dict[str, Any]], field: str, label: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(records, start=1):
        value = record.get(field)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{label}:{index}: missing or invalid {field}")
        if value in indexed:
            raise ValueError(f"{label}: duplicate {field} `{value}`")
        indexed[value] = record
    return indexed


def include_audio(record: dict[str, Any]) -> bool:
    if "include_in_experiments" in record:
        return record.get("include_in_experiments") is True
    if "audit_status" in record:
        return str(record.get("audit_status", "")).strip().lower() != "excluded"
    return record.get("generation_status") == "success"


def domain_from_screen(screen: dict[str, Any], screen_id: str) -> str:
    domain = screen.get("domain")
    if isinstance(domain, str):
        return domain
    return re.sub(r"_\d+$", "", screen_id)


def normalized_bbox(value: Any) -> BBox:
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError(f"invalid bbox: {value!r}")
    bbox: BBox = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"invalid bbox coordinate: {value!r}")
        bbox.append(float(item))
    return bbox


def point_in_bbox(x: float, y: float, bbox: list[float] | tuple[float, float, float, float]) -> bool:
    x1, y1, x2, y2 = bbox
    return x1 <= x <= x2 and y1 <= y <= y2


def screen_dimensions(screen: dict[str, Any]) -> tuple[float, float]:
    width = screen.get("width")
    height = screen.get("height")
    if not is_number(width) or not is_number(height):
        raise ValueError(f"screen `{screen.get('screen_id')}` is missing numeric width/height")
    return float(width), float(height)


def point_in_image(x: float, y: float, width: float, height: float) -> bool:
    return 0 <= x <= width and 0 <= y <= height


def bbox_area(bbox: list[float] | tuple[float, float, float, float]) -> float:
    x1, y1, x2, y2 = bbox
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def target_element(screen: dict[str, Any], target_element_id: str) -> dict[str, Any]:
    for element in screen.get("elements", []):
        if element.get("element_id") == target_element_id:
            return element
    raise ValueError(f"target element `{target_element_id}` not found on screen `{screen.get('screen_id')}`")


def derive_pred_element_id(screen: dict[str, Any], pred_x: float, pred_y: float) -> str | None:
    containing: list[tuple[float, str]] = []
    for element in screen.get("elements", []):
        element_id = element.get("element_id")
        if not isinstance(element_id, str):
            continue
        bbox = normalized_bbox(element.get("bbox"))
        if point_in_bbox(pred_x, pred_y, bbox):
            containing.append((bbox_area(bbox), element_id))
    if not containing:
        return None
    containing.sort(key=lambda item: (item[0], item[1]))
    return containing[0][1]


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def voice_metadata(prediction: dict[str, Any], manifest_by_id: dict[str, dict[str, Any]]) -> tuple[str | None, str | None]:
    if prediction.get("input_condition") == "gold":
        return None, None
    audio_id = prediction.get("audio_id")
    if not isinstance(audio_id, str) or audio_id not in manifest_by_id:
        raise ValueError(f"prediction `{prediction.get('prediction_id')}` references unknown audio_id `{audio_id}`")
    manifest_record = manifest_by_id[audio_id]
    if not include_audio(manifest_record):
        raise ValueError(f"prediction `{prediction.get('prediction_id')}` references excluded audio_id `{audio_id}`")
    return str(manifest_record.get("engine_id", "")), str(manifest_record.get("voice_id", ""))


def evaluation_record(
    prediction: dict[str, Any],
    screens_by_id: dict[str, dict[str, Any]],
    utterances_by_id: dict[str, dict[str, Any]],
    manifest_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    prediction_id = prediction.get("prediction_id")
    utterance_id = prediction.get("utterance_id")
    screen_id = prediction.get("screen_id")
    target_element_id = prediction.get("target_element_id")
    if not isinstance(utterance_id, str) or utterance_id not in utterances_by_id:
        raise ValueError(f"prediction `{prediction_id}` references unknown utterance_id `{utterance_id}`")
    if not isinstance(screen_id, str) or screen_id not in screens_by_id:
        raise ValueError(f"prediction `{prediction_id}` references unknown screen_id `{screen_id}`")
    if not isinstance(target_element_id, str):
        raise ValueError(f"prediction `{prediction_id}` has invalid target_element_id")

    utterance = utterances_by_id[utterance_id]
    screen = screens_by_id[screen_id]
    target = target_element(screen, target_element_id)
    target_bbox = normalized_bbox(target.get("bbox"))
    tts_engine, voice_id = voice_metadata(prediction, manifest_by_id)
    status = str(prediction.get("status", ""))
    pred_element_id: str | None = None
    point_in_image_value = False
    click_in_target_bbox = False
    element_match = False

    if status == "success":
        pred_x = prediction.get("pred_x")
        pred_y = prediction.get("pred_y")
        if not is_number(pred_x) or not is_number(pred_y):
            raise ValueError(f"successful prediction `{prediction_id}` is missing numeric pred_x/pred_y")
        pred_x_float = float(pred_x)
        pred_y_float = float(pred_y)
        width, height = screen_dimensions(screen)
        point_in_image_value = point_in_image(pred_x_float, pred_y_float, width, height)
        if point_in_image_value:
            click_in_target_bbox = point_in_bbox(pred_x_float, pred_y_float, target_bbox)
            pred_element_id = derive_pred_element_id(screen, pred_x_float, pred_y_float)
            element_match = pred_element_id == target_element_id

    return {
        "prediction_id": prediction_id,
        "utterance_id": utterance_id,
        "audio_id": prediction.get("audio_id"),
        "screen_id": screen_id,
        "domain": domain_from_screen(screen, screen_id),
        "tier": str(utterance.get("tier", "")),
        "language_class": str(utterance.get("language_class", "")),
        "target_element_id": target_element_id,
        "target_label": target.get("label") if isinstance(target.get("label"), str) else None,
        "target_bbox": target_bbox,
        "grounding_model": prediction.get("grounding_model"),
        "input_condition": prediction.get("input_condition"),
        "asr_model": prediction.get("asr_model"),
        "tts_engine": tts_engine,
        "voice_id": voice_id,
        "pred_x": prediction.get("pred_x"),
        "pred_y": prediction.get("pred_y"),
        "pred_label": str(prediction.get("pred_label", "")),
        "point_in_image": point_in_image_value,
        "pred_element_id": pred_element_id,
        "click_in_target_bbox": click_in_target_bbox,
        "element_match": element_match,
        "status": status,
        "failure_type": prediction.get("failure_type"),
        "error_message": str(prediction.get("error_message", "")),
    }


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def metric_value(value: float | None) -> str:
    return "" if value is None else f"{value:.6f}"


def metric_bool(value: bool) -> float:
    return 1.0 if value else 0.0


def summarize(records: list[dict[str, Any]], group_fields: tuple[str, ...]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[tuple(record.get(field) for field in group_fields)].append(record)

    rows: list[dict[str, Any]] = []
    for key, group in sorted(grouped.items(), key=lambda item: tuple("" if value is None else str(value) for value in item[0])):
        success_records = [record for record in group if record.get("status") == "success"]
        total_records = list(group)
        n_success_parse = len(success_records)
        n_failed_parse = len(total_records) - n_success_parse
        row = {field: value for field, value in zip(group_fields, key)}
        row.update(
            {
                "n_total": len(total_records),
                "n_success_parse": n_success_parse,
                "n_failed_parse": n_failed_parse,
                "parse_failure_rate": (n_failed_parse / len(total_records)) if total_records else None,
                "point_in_image_rate": mean([metric_bool(bool(record["point_in_image"])) for record in total_records]),
                "click_accuracy_including_failures": mean(
                    [metric_bool(bool(record["click_in_target_bbox"])) for record in total_records]
                ),
                "element_accuracy_including_failures": mean(
                    [metric_bool(bool(record["element_match"])) for record in total_records]
                ),
                "click_accuracy_success_only": mean(
                    [metric_bool(bool(record["click_in_target_bbox"])) for record in success_records]
                ),
                "element_accuracy_success_only": mean(
                    [metric_bool(bool(record["element_match"])) for record in success_records]
                ),
                "n_success": n_success_parse,
                "n_failed": n_failed_parse,
                "failure_rate": (n_failed_parse / len(total_records)) if total_records else None,
                "n": len(success_records),
                "click_accuracy": mean([metric_bool(bool(record["click_in_target_bbox"])) for record in success_records]),
                "element_accuracy": mean([metric_bool(bool(record["element_match"])) for record in success_records]),
                "failure_count": n_failed_parse,
                "records": len(group),
            }
        )
        rows.append(row)
    return rows


def write_summary_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for field in row:
            if field not in fieldnames:
                fieldnames.append(field)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            output = dict(row)
            for field in (
                "parse_failure_rate",
                "point_in_image_rate",
                "failure_rate",
                "click_accuracy_including_failures",
                "element_accuracy_including_failures",
                "click_accuracy_success_only",
                "element_accuracy_success_only",
                "click_accuracy",
                "element_accuracy",
            ):
                output[field] = metric_value(output.get(field))
            for field, value in list(output.items()):
                if value is None:
                    output[field] = ""
            writer.writerow(output)


def markdown_table(headers: tuple[str, ...], rows: list[tuple[Any, ...]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def build_report(summary_by_condition: list[dict[str, Any]], failed_records: list[dict[str, Any]]) -> str:
    condition_rows = [
        (
            row.get("input_condition", ""),
            row.get("grounding_model", ""),
            row.get("asr_model") or "",
            row.get("n_total", 0),
            row.get("n_success_parse", 0),
            row.get("n_failed_parse", 0),
            metric_value(row.get("parse_failure_rate")),
            metric_value(row.get("point_in_image_rate")),
            metric_value(row.get("click_accuracy_including_failures")),
            metric_value(row.get("click_accuracy_success_only")),
            metric_value(row.get("element_accuracy_including_failures")),
        )
        for row in summary_by_condition
    ]
    failed_text = "\n".join(
        f"- {record.get('prediction_id')}: {record.get('error_message', '')}" for record in failed_records[:20]
    )
    if not failed_text:
        failed_text = "- none"
    return "\n\n".join(
        [
            "# Grounding Evaluation Report",
            "## Summary By Condition\n\n"
            + markdown_table(
                (
                    "input_condition",
                    "grounding_model",
                    "asr_model",
                    "n_total",
                    "n_success_parse",
                    "n_failed_parse",
                    "parse_failure_rate",
                    "point_in_image_rate",
                    "click_accuracy_including_failures",
                    "click_accuracy_success_only",
                    "element_accuracy_including_failures",
                ),
                condition_rows,
            ),
            "## Failed Or Skipped Predictions\n\n" + failed_text,
        ]
    ) + "\n"


def evaluate_grounding(
    predictions_path: Path,
    screens_path: Path,
    utterances_path: Path,
    manifest_path: Path,
    output_dir: Path,
) -> dict[str, list[dict[str, Any]]]:
    predictions = [normalize_prediction_record(record) for record in load_jsonl(predictions_path, "grounding predictions")]
    screens = load_jsonl(screens_path, "screens")
    utterances = load_jsonl(utterances_path, "utterances")
    manifest = load_jsonl(manifest_path, "audio manifest")

    screens_by_id = index_by(screens, "screen_id", "screens")
    utterances_by_id = index_by(utterances, "utterance_id", "utterances")
    manifest_by_id = index_by(manifest, "audio_id", "audio manifest")

    eval_records = [
        evaluation_record(prediction, screens_by_id, utterances_by_id, manifest_by_id)
        for prediction in predictions
    ]
    summaries = {
        "by_condition": summarize(eval_records, ("input_condition", "grounding_model", "asr_model")),
        "by_tier": summarize(eval_records, ("input_condition", "grounding_model", "tier")),
        "by_model": summarize(eval_records, ("grounding_model",)),
        "by_asr_model": summarize(eval_records, ("asr_model",)),
        "by_voice": summarize(eval_records, ("input_condition", "grounding_model", "tts_engine", "voice_id")),
        "by_language_class": summarize(eval_records, ("input_condition", "grounding_model", "language_class")),
        "by_domain": summarize(eval_records, ("input_condition", "grounding_model", "domain")),
        "by_tts_engine": summarize(eval_records, ("input_condition", "grounding_model", "tts_engine")),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(eval_records, output_dir / "grounding_evaluation_by_file.jsonl")
    write_summary_csv(summaries["by_condition"], output_dir / "grounding_summary_by_condition.csv")
    write_summary_csv(summaries["by_tier"], output_dir / "grounding_summary_by_tier.csv")
    write_summary_csv(summaries["by_model"], output_dir / "grounding_summary_by_model.csv")
    write_summary_csv(summaries["by_asr_model"], output_dir / "grounding_summary_by_asr_model.csv")
    write_summary_csv(summaries["by_voice"], output_dir / "grounding_summary_by_voice.csv")
    write_summary_csv(summaries["by_language_class"], output_dir / "grounding_summary_by_language_class.csv")
    write_summary_csv(summaries["by_domain"], output_dir / "grounding_summary_by_domain.csv")
    write_summary_csv(summaries["by_tts_engine"], output_dir / "grounding_summary_by_tts_engine.csv")
    failed_records = [record for record in eval_records if record.get("status") != "success"]
    (output_dir / "GROUNDING_EVALUATION_REPORT.md").write_text(
        build_report(summaries["by_condition"], failed_records),
        encoding="utf-8",
    )
    return {"records": eval_records, **summaries}


def main() -> int:
    args = parse_args()
    try:
        result = evaluate_grounding(
            predictions_path=args.predictions,
            screens_path=args.screens,
            utterances_path=args.utterances,
            manifest_path=args.manifest,
            output_dir=args.output_dir,
        )
    except (OSError, ValueError) as exc:
        print(f"Grounding evaluation failed: {exc}")
        return 1
    print(f"Wrote grounding evaluation for {len(result['records'])} records to {args.output_dir}")
    for row in result["by_condition"]:
        print(
            f"{row['input_condition']}/{row['grounding_model']}/{row.get('asr_model') or 'gold'}: "
            f"parse_failure_rate={metric_value(row.get('parse_failure_rate'))} "
            f"point_in_image_rate={metric_value(row.get('point_in_image_rate'))} "
            f"click_accuracy_including_failures={metric_value(row.get('click_accuracy_including_failures'))} "
            f"click_accuracy_success_only={metric_value(row.get('click_accuracy_success_only'))} "
            f"n_failed_parse={row['n_failed_parse']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
