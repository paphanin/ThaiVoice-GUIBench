"""Validate ThaiVoice-GUIBench grounding prediction JSONL files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


VALID_CONDITIONS = {
    "gold",
    "asr_whisper_large_v3_local",
    "asr_typhoon_asr_api",
    "corrected_A_no_screen_cleanup_whisper",
    "corrected_B_screen_string_match_whisper",
    "corrected_C_full_screen_aware_alias_whisper",
    "corrected_A_no_screen_cleanup_typhoon",
    "corrected_B_screen_string_match_typhoon",
    "corrected_C_full_screen_aware_alias_typhoon",
}
ASR_CONDITIONS = VALID_CONDITIONS - {"gold"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--screens", type=Path, default=Path("data/screens/screens.jsonl"))
    parser.add_argument("--utterances", type=Path, default=Path("data/utterances/utterances_audited.jsonl"))
    parser.add_argument("--manifest", type=Path, default=Path("data/audio/audio_manifest.jsonl"))
    parser.add_argument("--schema", type=Path, default=Path("schemas/grounding_prediction.schema.json"))
    return parser.parse_args()


def load_json(path: Path, label: str) -> tuple[dict[str, Any] | None, list[str]]:
    if not path.exists():
        return None, [f"{label} does not exist: {path}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        return None, [f"{label} is invalid JSON: {path}:{exc.lineno}:{exc.colno}: {exc.msg}"]
    if not isinstance(data, dict):
        return None, [f"{label} must be a JSON object: {path}"]
    return data, []


def load_jsonl(path: Path, label: str, require_records: bool = True) -> tuple[list[dict[str, Any]], list[str]]:
    if not path.exists():
        return [], [f"{label} does not exist: {path}"]
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    with path.open("r", encoding="utf-8-sig") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                errors.append(f"{label}:{line_number}: invalid JSON: {exc.msg}")
                continue
            if not isinstance(record, dict):
                errors.append(f"{label}:{line_number}: expected JSON object")
                continue
            records.append(record)
    if require_records and not records:
        errors.append(f"{label} contains no records: {path}")
    return records, errors


def include_audio(record: dict[str, Any]) -> bool:
    if "include_in_experiments" in record:
        return record.get("include_in_experiments") is True
    if "audit_status" in record:
        return str(record.get("audit_status", "")).strip().lower() != "excluded"
    return record.get("generation_status") == "success"


def format_error_path(error_path: Any) -> str:
    parts = [str(part) for part in error_path]
    return ".".join(parts) if parts else "<record>"


def basic_schema_errors(records: list[dict[str, Any]], schema: dict[str, Any]) -> list[str]:
    required = schema.get("required", [])
    errors: list[str] = []
    for index, record in enumerate(records, start=1):
        record_id = record.get("prediction_id", f"line_{index}")
        for field in required:
            if field not in record:
                errors.append(f"{record_id}: missing required field {field}")
        condition = record.get("input_condition")
        if condition not in VALID_CONDITIONS:
            errors.append(f"{record_id}: invalid input_condition {condition!r}")
        status = record.get("status")
        if status not in {"success", "failed", "skipped"}:
            errors.append(f"{record_id}: invalid status {status!r}")
    return errors


def jsonschema_errors(records: list[dict[str, Any]], schema: dict[str, Any]) -> list[str]:
    try:
        from jsonschema import Draft202012Validator  # type: ignore[import-not-found]
    except Exception:
        return basic_schema_errors(records, schema)
    validator = Draft202012Validator(schema)
    errors: list[str] = []
    for index, record in enumerate(records, start=1):
        record_id = record.get("prediction_id", f"line_{index}")
        for error in sorted(validator.iter_errors(record), key=lambda item: list(item.path)):
            errors.append(f"{record_id}: schema error at {format_error_path(error.path)}: {error.message}")
    return errors


def index_by(records: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        value = record.get(key)
        if isinstance(value, str):
            indexed[value] = record
    return indexed


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def semantic_errors(
    predictions: list[dict[str, Any]],
    screens: list[dict[str, Any]],
    utterances: list[dict[str, Any]],
    manifest: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    seen_prediction_ids: set[str] = set()
    seen_combo_keys: set[tuple[Any, ...]] = set()
    screens_by_id = index_by(screens, "screen_id")
    utterances_by_id = index_by(utterances, "utterance_id")
    manifest_by_id = index_by(manifest, "audio_id")

    for record in predictions:
        prediction_id = record.get("prediction_id")
        label = prediction_id or "<missing prediction_id>"
        if prediction_id in seen_prediction_ids:
            errors.append(f"{label}: duplicate prediction_id")
        elif isinstance(prediction_id, str):
            seen_prediction_ids.add(prediction_id)

        combo_key = (
            record.get("grounding_model"),
            record.get("input_condition"),
            record.get("utterance_id"),
            record.get("audio_id"),
        )
        if combo_key in seen_combo_keys:
            errors.append(f"{label}: duplicate condition/model/utterance/audio prediction")
        else:
            seen_combo_keys.add(combo_key)

        utterance_id = record.get("utterance_id")
        utterance = utterances_by_id.get(utterance_id) if isinstance(utterance_id, str) else None
        if utterance is None:
            errors.append(f"{label}: unknown utterance_id {utterance_id!r}")

        screen_id = record.get("screen_id")
        screen = screens_by_id.get(screen_id) if isinstance(screen_id, str) else None
        if screen is None:
            errors.append(f"{label}: unknown screen_id {screen_id!r}")
        else:
            image_path = screen.get("image_path")
            if not isinstance(image_path, str) or not Path(image_path).exists():
                errors.append(f"{label}: screenshot path does not exist for screen {screen_id!r}: {image_path!r}")
            target_element_id = record.get("target_element_id")
            element_ids = {element.get("element_id") for element in screen.get("elements", [])}
            if target_element_id not in element_ids:
                errors.append(f"{label}: target_element_id {target_element_id!r} not found on screen {screen_id!r}")

        condition = record.get("input_condition")
        if condition not in VALID_CONDITIONS:
            errors.append(f"{label}: invalid input_condition {condition!r}")
        if condition == "gold":
            if record.get("audio_id") is not None:
                errors.append(f"{label}: gold condition must have audio_id=null")
            if record.get("asr_model") is not None:
                errors.append(f"{label}: gold condition must have asr_model=null")
        elif condition in ASR_CONDITIONS:
            audio_id = record.get("audio_id")
            asr_model = record.get("asr_model")
            if not audio_id:
                errors.append(f"{label}: ASR condition requires audio_id")
            elif audio_id not in manifest_by_id:
                errors.append(f"{label}: unknown audio_id {audio_id!r}")
            elif not include_audio(manifest_by_id[audio_id]):
                errors.append(f"{label}: audio_id is excluded from experiments {audio_id!r}")
            if not asr_model:
                errors.append(f"{label}: ASR condition requires asr_model")

        status = record.get("status")
        if status == "success":
            if not is_number(record.get("pred_x")) or not is_number(record.get("pred_y")):
                errors.append(f"{label}: success record requires numeric pred_x and pred_y")
        if status == "failed" and not str(record.get("error_message", "")).strip():
            errors.append(f"{label}: failed record requires non-empty error_message")
        if status == "success" and record.get("failure_type") not in (None, ""):
            errors.append(f"{label}: success record must not have failure_type")
    return errors


def normalize_prediction_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for record in records:
        copy = dict(record)
        copy.setdefault("failure_type", None)
        if copy.get("status") != "success" and copy.get("failure_type") in (None, ""):
            copy["failure_type"] = "unparseable_model_output"
        normalized.append(copy)
    return normalized


def validate_files(
    predictions_path: Path,
    screens_path: Path,
    utterances_path: Path,
    manifest_path: Path,
    schema_path: Path,
) -> tuple[bool, list[str]]:
    schema, schema_load_errors = load_json(schema_path, "schema")
    predictions, prediction_errors = load_jsonl(predictions_path, "predictions")
    screens, screen_errors = load_jsonl(screens_path, "screens")
    utterances, utterance_errors = load_jsonl(utterances_path, "utterances")
    manifest, manifest_errors = load_jsonl(manifest_path, "audio manifest")
    predictions = normalize_prediction_records(predictions)
    errors = schema_load_errors + prediction_errors + screen_errors + utterance_errors + manifest_errors
    if schema and predictions:
        errors.extend(jsonschema_errors(predictions, schema))
    if predictions and screens and utterances and manifest:
        errors.extend(semantic_errors(predictions, screens, utterances, manifest))
    return not errors, errors


def main() -> int:
    args = parse_args()
    ok, errors = validate_files(args.predictions, args.screens, args.utterances, args.manifest, args.schema)
    if errors:
        print("Grounding prediction validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Grounding prediction validation passed: {args.predictions}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
