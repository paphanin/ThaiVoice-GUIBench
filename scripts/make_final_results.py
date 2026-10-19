"""Create final paper-ready result tables from validated ThaiVoice-GUIBench outputs."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from evaluate_asr import (
    character_error_rate,
    loanword_error_counts,
    loanwords_for_utterance,
    word_error_rate,
)


RAW_CONDITIONS = {
    "whisper_large_v3_local": "asr_whisper_large_v3_local",
    "typhoon_asr_api": "asr_typhoon_asr_api",
}

CORRECTION_METHODS = (
    "A_no_screen_cleanup",
    "B_screen_string_match",
    "C_full_screen_aware_alias",
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
    return rows


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: format_value(row.get(key)) for key in fieldnames})


def format_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6f}"
    return value


def mean(values: Iterable[float]) -> float | None:
    vals = list(values)
    return sum(vals) / len(vals) if vals else None


def rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def include_audio(record: dict[str, Any]) -> bool:
    if "include_in_experiments" in record:
        return record.get("include_in_experiments") is True
    if "audit_status" in record:
        return str(record.get("audit_status", "")).strip().lower() != "excluded"
    return record.get("generation_status") == "success"


def domain_from_screen_id(screen_id: str) -> str:
    return "_".join(screen_id.split("_")[:-1])


def screen_domain_map(screens: list[dict[str, Any]]) -> dict[str, str]:
    return {row["screen_id"]: row.get("domain") or domain_from_screen_id(row["screen_id"]) for row in screens}


def table1_dataset_statistics(
    screens: list[dict[str, Any]],
    mappings: list[dict[str, Any]],
    utterances: list[dict[str, Any]],
    manifest: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    domains = screen_domain_map(screens)

    def add(section: str, category: str, count: int, notes: str = "") -> None:
        rows.append({"section": section, "category": category, "count": count, "notes": notes})

    add("dataset_totals", "screens", len(screens))
    add("dataset_totals", "mappings", len(mappings))
    add("dataset_totals", "commands", len(utterances))
    add("dataset_totals", "audio_manifest_records", len(manifest))
    for domain, count in sorted(Counter(domains.values()).items()):
        add("screens_by_domain", domain, count)
    mapping_domains = Counter(domains.get(row["screen_id"], domain_from_screen_id(row["screen_id"])) for row in mappings)
    for domain, count in sorted(mapping_domains.items()):
        add("mappings_by_domain", domain, count)
    for tier, count in sorted(Counter(row.get("tier", "") for row in utterances).items()):
        add("commands_by_tier", tier, count)
    for engine, count in sorted(Counter(row.get("engine_id", "") for row in manifest).items()):
        add("audio_files_by_tts_engine", engine, count)
    for (engine, voice), count in sorted(Counter((row.get("engine_id", ""), row.get("voice_id", "")) for row in manifest).items()):
        add("audio_files_by_voice", f"{engine}/{voice}", count)
    for language_class, count in sorted(Counter(row.get("language_class", "") for row in utterances).items()):
        add("commands_by_language_class", language_class, count)
    loanword_utterances = sum(1 for row in utterances if loanwords_for_utterance(row))
    loanword_tokens = sum(len(loanwords_for_utterance(row)) for row in utterances)
    add("loanwords", "utterances_with_loanwords", loanword_utterances)
    add("loanwords", "loanword_tokens", loanword_tokens)
    valid = sum(1 for row in manifest if include_audio(row))
    excluded = len(manifest) - valid
    add("audio_validity", "valid_audio", valid)
    add("audio_validity", "excluded_audio", excluded)
    return rows


def asr_metric_records(
    utterances: list[dict[str, Any]],
    manifest: list[dict[str, Any]],
    asr_rows: list[dict[str, Any]],
    cached_metrics: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if cached_metrics:
        valid_audio = {row["audio_id"] for row in manifest if include_audio(row)}
        return [row for row in cached_metrics if row.get("audio_id") in valid_audio]

    utterances_by_id = {row["utterance_id"]: row for row in utterances}
    manifest_by_id = {row["audio_id"]: row for row in manifest}
    valid_audio = {row["audio_id"] for row in manifest if include_audio(row)}
    records: list[dict[str, Any]] = []
    for asr in asr_rows:
        audio_id = asr.get("audio_id")
        if audio_id not in valid_audio:
            continue
        utt = utterances_by_id[asr["utterance_id"]]
        audio = manifest_by_id[audio_id]
        status = asr.get("status")
        transcript = str(asr.get("transcript", ""))
        gold = str(utt.get("text_gold", ""))
        loanwords = loanwords_for_utterance(utt)
        loanword_count, loanword_errors, loanword_rate = loanword_error_counts(loanwords, transcript)
        if status == "success":
            cer = character_error_rate(gold, transcript)
            wer = word_error_rate(gold, transcript)
        else:
            cer = None
            wer = None
            loanword_errors = None
            loanword_rate = None
        records.append(
            {
                "asr_id": asr["asr_id"],
                "audio_id": audio_id,
                "utterance_id": asr["utterance_id"],
                "asr_model": asr["asr_model"],
                "status": status,
                "cer": cer,
                "wer": wer,
                "loanword_error_rate": loanword_rate,
                "loanword_count": loanword_count,
                "loanword_errors": loanword_errors,
                "tier": utt.get("tier", ""),
                "domain": domain_from_screen_id(utt.get("screen_id", "")),
                "language_class": utt.get("language_class", ""),
                "tts_engine": audio.get("engine_id", ""),
                "voice_id": audio.get("voice_id", ""),
            }
        )
    return records


def summarize_asr(records: list[dict[str, Any]], group_fields: tuple[str, ...]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        grouped[tuple(row.get(field, "") for field in group_fields)].append(row)
    rows: list[dict[str, Any]] = []
    for key, group in sorted(grouped.items(), key=lambda item: tuple(str(x) for x in item[0])):
        success = [row for row in group if row.get("status") == "success"]
        loanword_count = sum(int(row.get("loanword_count") or 0) for row in success)
        loanword_errors = sum(int(row.get("loanword_errors") or 0) for row in success)
        out = {"slice": "+".join(group_fields)}
        out.update({field: value for field, value in zip(group_fields, key)})
        out.update(
            {
                "records": len(group),
                "success_count": len(success),
                "failed_count": len(group) - len(success),
                "asr_failure_rate": rate(len(group) - len(success), len(group)),
                "cer": mean(float(row["cer"]) for row in success if row.get("cer") is not None),
                "thai_tokenized_wer": mean(
                    float(row["wer"]) for row in success if row.get("wer") is not None
                ),
                "loanword_error_rate": rate(loanword_errors, loanword_count),
                "loanword_count": loanword_count,
                "loanword_errors": loanword_errors,
            }
        )
        rows.append(out)
    return rows


def table2_asr_performance(asr_metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for fields in (
        ("asr_model",),
        ("asr_model", "tier"),
        ("asr_model", "domain"),
        ("asr_model", "tts_engine"),
        ("asr_model", "tts_engine", "voice_id"),
        ("asr_model", "language_class"),
    ):
        rows.extend(summarize_asr(asr_metrics, fields))
    return rows


def summarize_grounding(records: list[dict[str, Any]], group_fields: tuple[str, ...]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        grouped[tuple(row.get(field, "") for field in group_fields)].append(row)
    rows: list[dict[str, Any]] = []
    for key, group in sorted(grouped.items(), key=lambda item: tuple(str(x) for x in item[0])):
        success = [row for row in group if row.get("status") == "success"]
        failed = len(group) - len(success)
        out = {"slice": "+".join(group_fields)}
        out.update({field: value for field, value in zip(group_fields, key)})
        out.update(
            {
                "n_total": len(group),
                "n_success_parse": len(success),
                "n_failed_parse": failed,
                "parse_failure_rate": rate(failed, len(group)),
                "point_in_image_rate": mean(1.0 if row.get("point_in_image") else 0.0 for row in group),
                "click_accuracy_including_failures": mean(1.0 if row.get("click_in_target_bbox") else 0.0 for row in group),
                "click_accuracy_success_only": mean(1.0 if row.get("click_in_target_bbox") else 0.0 for row in success),
            }
        )
        rows.append(out)
    return rows


def table3_grounding_degradation(eval_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    baseline = [
        row
        for row in eval_records
        if row.get("input_condition") in {"gold", "asr_whisper_large_v3_local", "asr_typhoon_asr_api"}
    ]
    rows: list[dict[str, Any]] = []
    for fields in (
        ("grounding_model", "input_condition", "asr_model"),
        ("grounding_model", "input_condition", "asr_model", "tier"),
        ("grounding_model", "input_condition", "asr_model", "domain"),
        ("grounding_model", "input_condition", "asr_model", "language_class"),
    ):
        rows.extend(summarize_grounding(baseline, fields))

    gold_acc = {
        row["grounding_model"]: row["click_accuracy_including_failures"]
        for row in summarize_grounding(
            [r for r in baseline if r.get("input_condition") == "gold"],
            ("grounding_model",),
        )
    }
    for row in rows:
        gm = row.get("grounding_model")
        if row.get("input_condition") == "gold":
            row["gold_click_accuracy"] = row.get("click_accuracy_including_failures")
            row["absolute_drop_from_gold"] = 0.0
        else:
            row["gold_click_accuracy"] = gold_acc.get(gm)
            raw_acc = row.get("click_accuracy_including_failures")
            row["absolute_drop_from_gold"] = (
                gold_acc[gm] - raw_acc if gm in gold_acc and raw_acc is not None else None
            )
    return rows


def corrected_condition(asr_model: str, method: str) -> str:
    suffix = "whisper" if asr_model == "whisper_large_v3_local" else "typhoon"
    prefix = {
        "A_no_screen_cleanup": "corrected_A_no_screen_cleanup",
        "B_screen_string_match": "corrected_B_screen_string_match",
        "C_full_screen_aware_alias": "corrected_C_full_screen_aware_alias",
    }[method]
    return f"{prefix}_{suffix}"


def raw_click_accuracy_by_model(eval_records: list[dict[str, Any]]) -> dict[tuple[str, str], float]:
    rows = summarize_grounding(
        [
            row
            for row in eval_records
            if row.get("input_condition") in {"asr_whisper_large_v3_local", "asr_typhoon_asr_api"}
        ],
        ("grounding_model", "asr_model"),
    )
    return {
        (row["grounding_model"], row["asr_model"]): row["click_accuracy_including_failures"]
        for row in rows
    }


def corrected_click_accuracy_by_model(eval_records: list[dict[str, Any]]) -> dict[tuple[str, str, str], float]:
    rows = summarize_grounding(
        [row for row in eval_records if str(row.get("input_condition", "")).startswith("corrected_")],
        ("grounding_model", "asr_model", "input_condition"),
    )
    return {
        (row["grounding_model"], row["asr_model"], row["input_condition"]): row["click_accuracy_including_failures"]
        for row in rows
    }


def transcript_correction_metrics(
    corrections: list[dict[str, Any]],
    utterances: list[dict[str, Any]],
) -> dict[tuple[str, str], dict[str, Any]]:
    utterances_by_id = {row["utterance_id"]: row for row in utterances}
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in corrections:
        if row.get("status") == "success":
            grouped[(row["asr_model"], row["method"])].append(row)

    metrics: dict[tuple[str, str], dict[str, Any]] = {}
    for (asr_model, method), group in sorted(grouped.items()):
        changed = [row for row in group if row.get("changed")]
        recovery_count = 0
        false_count = 0
        for row in group:
            utt = utterances_by_id[row["utterance_id"]]
            gold = str(utt.get("text_gold", ""))
            raw = str(row.get("input_transcript", ""))
            corrected = str(row.get("corrected_transcript", ""))
            raw_cer = character_error_rate(gold, raw)
            corrected_cer = character_error_rate(gold, corrected)
            raw_loanwords = loanword_error_counts(loanwords_for_utterance(utt), raw)[1]
            corrected_loanwords = loanword_error_counts(loanwords_for_utterance(utt), corrected)[1]
            recovered = corrected_cer < raw_cer or corrected_loanwords < raw_loanwords
            false = corrected_cer > raw_cer or (row.get("changed") and raw_cer == 0)
            if recovered:
                recovery_count += 1
            if false:
                false_count += 1
        metrics[(asr_model, method)] = {
            "n_total": len(group),
            "changed_count": len(changed),
            "changed_rate": rate(len(changed), len(group)),
            "recovery_count": recovery_count,
            "recovery_rate": rate(recovery_count, len(group)),
            "false_correction_count": false_count,
            "false_correction_rate": rate(false_count, len(group)),
            "net_transcript_benefit": recovery_count - false_count,
        }
    return metrics


def csv_int(row: dict[str, str], key: str) -> int:
    value = row.get(key, "")
    return int(value) if value not in (None, "") else 0


def csv_float(row: dict[str, str], key: str) -> float | None:
    value = row.get(key, "")
    return float(value) if value not in (None, "") else None


def table4_correction_effects(
    corrections: list[dict[str, Any]],
    utterances: list[dict[str, Any]],
    transition_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    transcript_metrics = transcript_correction_metrics(corrections, utterances)
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for transition in transition_rows:
        grounding_model = transition["grounding_model"]
        asr_model = transition["asr_model"]
        method = transition["correction_method"]
        key = (grounding_model, asr_model, method)
        if key in seen:
            raise ValueError(f"duplicate correction transition row: {key}")
        seen.add(key)
        transcript = transcript_metrics[(asr_model, method)]
        n_total = csv_int(transition, "n_total")
        if n_total != transcript["n_total"]:
            raise ValueError(f"correction/transition denominator mismatch for {key}")
        cc = csv_int(transition, "CC")
        wc = csv_int(transition, "WC")
        cw = csv_int(transition, "CW")
        ww = csv_int(transition, "WW")
        if cc + wc + cw + ww != n_total:
            raise ValueError(f"invalid transition total for {key}")
        rows.append(
            {
                "grounding_model": grounding_model,
                "asr_model": asr_model,
                "correction_method": method,
                **transcript,
                "raw_click_accuracy": csv_float(transition, "raw_click_accuracy"),
                "corrected_run_click_accuracy": csv_float(transition, "corrected_click_accuracy"),
                "pooled_click_delta": csv_float(transition, "accuracy_delta"),
                "CC": cc,
                "WC": wc,
                "CW": cw,
                "WW": ww,
                "classification": transition.get("classification", ""),
            }
        )
    if len(rows) != 12:
        raise ValueError(f"expected 12 correction-effect rows, found {len(rows)}")
    return sorted(rows, key=lambda row: (row["grounding_model"], row["asr_model"], row["correction_method"]))


def coordinate_counts_by_subset(
    predictions: list[dict[str, Any]],
) -> dict[tuple[str, str, str, str], tuple[int, int]]:
    raw_conditions = set(RAW_CONDITIONS.values())
    raw_by_key = {
        (
            row.get("grounding_model"),
            row.get("asr_model"),
            row.get("utterance_id"),
            row.get("audio_id"),
            row.get("screen_id"),
        ): row
        for row in predictions
        if row.get("input_condition") in raw_conditions
    }
    details = {
        corrected_condition(asr_model, method): (asr_model, method)
        for asr_model in RAW_CONDITIONS
        for method in CORRECTION_METHODS
    }
    counts: dict[tuple[str, str, str, str], list[int]] = defaultdict(lambda: [0, 0])
    for corrected in predictions:
        condition = str(corrected.get("input_condition", ""))
        if condition not in details:
            continue
        asr_model, method = details[condition]
        raw_key = (
            corrected.get("grounding_model"),
            corrected.get("asr_model"),
            corrected.get("utterance_id"),
            corrected.get("audio_id"),
            corrected.get("screen_id"),
        )
        raw = raw_by_key.get(raw_key)
        if raw is None:
            raise ValueError(f"missing raw grounding pair for {corrected.get('prediction_id')}")
        subset = "changed" if raw.get("transcript") != corrected.get("transcript") else "unchanged"
        coordinates = (raw.get("pred_x"), raw.get("pred_y"), corrected.get("pred_x"), corrected.get("pred_y"))
        numeric = all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in coordinates)
        same = numeric and coordinates[0] == coordinates[2] and coordinates[1] == coordinates[3]
        count = counts[(str(corrected.get("grounding_model")), asr_model, method, subset)]
        count[0 if same else 1] += 1
    return {key: (value[0], value[1]) for key, value in counts.items()}


def table4b_changed_unchanged_effects(
    subset_rows: list[dict[str, str]],
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    coordinate_counts = coordinate_counts_by_subset(predictions)
    rows: list[dict[str, Any]] = []
    for subset_row in subset_rows:
        subset = subset_row.get("subset")
        if subset not in {"changed", "unchanged"}:
            continue
        key = (
            subset_row["grounding_model"],
            subset_row["asr_model"],
            subset_row["correction_method"],
            subset,
        )
        same_count, different_count = coordinate_counts.get(key, (0, 0))
        n = csv_int(subset_row, "n")
        if same_count + different_count != n:
            raise ValueError(f"coordinate-count denominator mismatch for {key}")
        rows.append(
            {
                "grounding_model": key[0],
                "asr_model": key[1],
                "correction_method": key[2],
                "subset": subset,
                "n": n,
                "raw_click_accuracy": csv_float(subset_row, "raw_click_accuracy"),
                "corrected_run_click_accuracy": csv_float(subset_row, "corrected_click_accuracy"),
                "click_delta": csv_float(subset_row, "accuracy_delta"),
                "exact_same_coordinate_count": same_count,
                "different_coordinate_count": different_count,
                "WC": csv_int(subset_row, "WC"),
                "CW": csv_int(subset_row, "CW"),
                "classification": subset_row.get("classification", ""),
            }
        )
    if len(rows) != 24:
        raise ValueError(f"expected 24 changed/unchanged rows, found {len(rows)}")
    return sorted(
        rows,
        key=lambda row: (
            row["grounding_model"],
            row["asr_model"],
            row["correction_method"],
            row["subset"],
        ),
    )


def markdown_table(rows: list[dict[str, Any]], columns: list[str], limit: int | None = None) -> str:
    shown = rows if limit is None else rows[:limit]
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in shown:
        lines.append("| " + " | ".join(str(format_value(row.get(col))) for col in columns) + " |")
    return "\n".join(lines)


def build_report(
    table1: list[dict[str, Any]],
    table2: list[dict[str, Any]],
    table3: list[dict[str, Any]],
    table4: list[dict[str, Any]],
    table4b: list[dict[str, Any]],
    summary: dict[str, Any],
) -> str:
    notes = [
        "# Final Results Report",
        "## Status",
        "- Results use the frozen original 20-screen dataset and existing validated inference outputs.",
        "- No model was rerun and no correction threshold, prompt, alias, model version, or evaluation rule was changed.",
        "- Negative and mixed correction results are retained.",
        "- Pooled corrected-versus-raw click deltas combine transcript-related effects with independent grounding rerun variability.",
        "- Unchanged-transcript deltas are evidence of rerun variability and are not attributed to correction.",
        "## Definitions",
        "- Recovery count uses the frozen automatic transcript comparison: lower CER or fewer loanword errors than raw ASR.",
        "- False-correction count uses the frozen automatic comparison: worse CER, or a changed transcript whose raw ASR already exactly matches gold. Unsupported-label risks are discussed through the finalized diagnosis and group classification.",
        "- Net transcript benefit is recovery count minus false-correction count.",
        "- Click metrics include parse failures as incorrect unless a success-only column is explicitly named.",
        "## Table 1 - Dataset Statistics",
        markdown_table(table1, ["section", "category", "count", "notes"]),
        "## Table 2 - ASR Performance",
        markdown_table(
            table2,
            [
                "slice",
                "asr_model",
                "tier",
                "domain",
                "tts_engine",
                "voice_id",
                "language_class",
                "records",
                "success_count",
                "failed_count",
                "asr_failure_rate",
                "cer",
                "thai_tokenized_wer",
                "loanword_error_rate",
            ],
        ),
        "## Table 3 - Grounding Degradation From ASR",
        markdown_table(
            table3,
            [
                "slice",
                "grounding_model",
                "input_condition",
                "asr_model",
                "tier",
                "domain",
                "language_class",
                "n_total",
                "n_success_parse",
                "n_failed_parse",
                "parse_failure_rate",
                "point_in_image_rate",
                "click_accuracy_including_failures",
                "click_accuracy_success_only",
                "absolute_drop_from_gold",
            ],
        ),
        "## Table 4 - Correction Effects",
        markdown_table(
            table4,
            [
                "grounding_model",
                "asr_model",
                "correction_method",
                "n_total",
                "changed_count",
                "changed_rate",
                "recovery_count",
                "recovery_rate",
                "false_correction_count",
                "false_correction_rate",
                "net_transcript_benefit",
                "raw_click_accuracy",
                "corrected_run_click_accuracy",
                "pooled_click_delta",
                "CC",
                "WC",
                "CW",
                "WW",
                "classification",
            ],
        ),
        "## Table 4b - Changed Versus Unchanged Effects",
        markdown_table(
            table4b,
            [
                "grounding_model",
                "asr_model",
                "correction_method",
                "subset",
                "n",
                "raw_click_accuracy",
                "corrected_run_click_accuracy",
                "click_delta",
                "exact_same_coordinate_count",
                "different_coordinate_count",
                "WC",
                "CW",
                "classification",
            ],
        ),
        "## Interpretation",
        "- G1/Whisper A and B have positive changed-subset deltas, while their pooled deltas remain slightly negative because unchanged prompts were independently rerun.",
        "- Method C shows supported degradation for G1, especially Typhoon/C on changed transcripts.",
        "- Typhoon A and B are no-op transcript controls; their click differences measure independent rerun variability.",
        "- G2/UI-TARS has substantial parse and repeatability limitations. Its pooled correction deltas must not be read as purely transcript-causal.",
        "## Summary JSON",
        "```json\n" + json.dumps(summary, ensure_ascii=False, indent=2) + "\n```",
    ]
    return "\n\n".join(notes) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screens", type=Path, default=Path("data/screens/screens.jsonl"))
    parser.add_argument("--mappings", type=Path, default=Path("data/intents/intent_screen_targets.jsonl"))
    parser.add_argument("--utterances", type=Path, default=Path("data/utterances/utterances_audited.jsonl"))
    parser.add_argument("--manifest", type=Path, default=Path("data/audio/audio_manifest.jsonl"))
    parser.add_argument("--whisper", type=Path, default=Path("data/asr_outputs/whisper_large_v3_local.jsonl"))
    parser.add_argument("--typhoon", type=Path, default=Path("data/asr_outputs/typhoon_asr_api.jsonl"))
    parser.add_argument("--asr-metrics-cache", type=Path, default=Path("data/asr_outputs/asr_metrics_by_file.jsonl"))
    parser.add_argument("--predictions", type=Path, default=Path("data/predictions/grounding_predictions.jsonl"))
    parser.add_argument("--grounding-eval", type=Path, default=Path("data/predictions/grounding_evaluation_by_file.jsonl"))
    parser.add_argument("--corrections", type=Path, default=Path("data/corrections/corrected_transcripts.jsonl"))
    parser.add_argument(
        "--correction-transitions",
        type=Path,
        default=Path("data/analysis/correction_transition_counts.csv"),
    )
    parser.add_argument(
        "--correction-subsets",
        type=Path,
        default=Path("data/analysis/correction_changed_unchanged_summary.csv"),
    )
    parser.add_argument(
        "--rerun-variability",
        type=Path,
        default=Path("data/analysis/grounding_rerun_variability.csv"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("data/results"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    screens = load_jsonl(args.screens)
    mappings = load_jsonl(args.mappings)
    utterances = load_jsonl(args.utterances)
    manifest = load_jsonl(args.manifest)
    asr_rows = load_jsonl(args.whisper) + load_jsonl(args.typhoon)
    predictions = load_jsonl(args.predictions)
    eval_records = load_jsonl(args.grounding_eval)
    corrections = load_jsonl(args.corrections)
    transition_rows = load_csv(args.correction_transitions)
    subset_rows = load_csv(args.correction_subsets)
    rerun_variability_rows = load_csv(args.rerun_variability)
    cached_asr_metrics = load_jsonl(args.asr_metrics_cache) if args.asr_metrics_cache.exists() else None

    args.output_dir.mkdir(parents=True, exist_ok=True)
    asr_metrics = asr_metric_records(utterances, manifest, asr_rows, cached_metrics=cached_asr_metrics)
    table1 = table1_dataset_statistics(screens, mappings, utterances, manifest)
    table2 = table2_asr_performance(asr_metrics)
    table3 = table3_grounding_degradation(eval_records)
    table4 = table4_correction_effects(corrections, utterances, transition_rows)
    table4b = table4b_changed_unchanged_effects(subset_rows, predictions)

    if len(rerun_variability_rows) != 12:
        raise ValueError(f"expected 12 rerun-variability rows, found {len(rerun_variability_rows)}")

    write_csv(args.output_dir / "table1_dataset_statistics.csv", table1)
    write_csv(args.output_dir / "table2_asr_performance.csv", table2)
    write_csv(args.output_dir / "table3_grounding_degradation.csv", table3)
    write_csv(args.output_dir / "table4_correction_effects.csv", table4)
    write_csv(args.output_dir / "table4b_changed_unchanged_effects.csv", table4b)

    asr_overall = [row for row in table2 if row["slice"] == "asr_model"]
    grounding_overall = [
        row for row in table3 if row["slice"] == "grounding_model+input_condition+asr_model"
    ]

    summary = {
        "screens": len(screens),
        "mappings": len(mappings),
        "utterances": len(utterances),
        "audio_manifest_rows": len(manifest),
        "valid_audio": sum(1 for row in manifest if include_audio(row)),
        "excluded_audio": sum(1 for row in manifest if not include_audio(row)),
        "asr_records": len(asr_metrics),
        "grounding_eval_records": len(eval_records),
        "correction_records": len(corrections),
        "corrected_grounding_records": sum(
            1 for row in eval_records if str(row.get("input_condition", "")).startswith("corrected_")
        ),
        "corrected_grounding_available": any(
            str(row.get("input_condition", "")).startswith("corrected_") for row in eval_records
        ),
        "asr_metrics_source": str(args.asr_metrics_cache) if cached_asr_metrics else "computed_from_asr_outputs",
        "asr_performance_by_model": asr_overall,
        "grounding_baselines": grounding_overall,
        "correction_effects": table4,
        "correction_interpretation": {
            "pooled_click_delta_is_causal_correction_effect": False,
            "pooled_delta_contains": [
                "correction-related transcript effects",
                "independent grounding rerun variability",
            ],
            "unchanged_subset_delta_interpretation": "independent grounding rerun variability",
            "method_c_degradation_supported": True,
            "whisper_a_b_changed_subset_gains_supported_for_g1": True,
            "g2_repeatability_limitation": True,
        },
        "table_paths": {
            "table1": "data/results/table1_dataset_statistics.csv",
            "table2": "data/results/table2_asr_performance.csv",
            "table3": "data/results/table3_grounding_degradation.csv",
            "table4": "data/results/table4_correction_effects.csv",
            "table4b": "data/results/table4b_changed_unchanged_effects.csv",
        },
    }
    (args.output_dir / "final_metrics_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "FINAL_RESULTS_REPORT.md").write_text(
        build_report(table1, table2, table3, table4, table4b, summary),
        encoding="utf-8",
    )
    print(f"Wrote final result tables to {args.output_dir}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
