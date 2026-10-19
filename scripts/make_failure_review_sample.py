"""Create a deterministic manual review sample for correction and grounding failures."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

from evaluate_asr import character_error_rate, loanword_error_counts, loanwords_for_utterance


RAW_CONDITIONS = {
    "whisper_large_v3_local": "asr_whisper_large_v3_local",
    "typhoon_asr_api": "asr_typhoon_asr_api",
}

CORRECTED_CONDITIONS = {
    ("whisper_large_v3_local", "A_no_screen_cleanup"): "corrected_A_no_screen_cleanup_whisper",
    ("whisper_large_v3_local", "B_screen_string_match"): "corrected_B_screen_string_match_whisper",
    ("whisper_large_v3_local", "C_full_screen_aware_alias"): "corrected_C_full_screen_aware_alias_whisper",
    ("typhoon_asr_api", "A_no_screen_cleanup"): "corrected_A_no_screen_cleanup_typhoon",
    ("typhoon_asr_api", "B_screen_string_match"): "corrected_B_screen_string_match_typhoon",
    ("typhoon_asr_api", "C_full_screen_aware_alias"): "corrected_C_full_screen_aware_alias_typhoon",
}

TAXONOMY_VALUES = (
    "loanword_ASR_error",
    "Thai_word_segmentation_issue",
    "confusable_screen_label",
    "visual_grounding_error",
    "positional_phrase_failure",
    "over_correction",
    "ambiguous_instruction",
    "TTS_pronunciation_issue",
    "parse_failure",
    "out_of_bounds_prediction",
    "correction_helped",
    "correction_helped_transcript_but_hurt_grounding",
    "correction_changed_without_downstream_gain",
    "unchanged_prompt_rerun_variability",
    "other",
)

CSV_FIELDS = (
    "case_id",
    "utterance_id",
    "audio_id",
    "screen_id",
    "domain",
    "tier",
    "language_class",
    "tts_engine",
    "voice_id",
    "asr_model",
    "grounding_model",
    "gold_text",
    "raw_asr_transcript",
    "corrected_transcript",
    "correction_method",
    "transcript_changed",
    "target_label",
    "predicted_label_raw",
    "predicted_label_corrected",
    "raw_coordinates",
    "corrected_coordinates",
    "raw_click_correct",
    "corrected_click_correct",
    "coordinate_same",
    "transition_type",
    "candidate_failure_taxonomy",
    "manual_failure_taxonomy",
    "notes",
    "include_as_qualitative_example",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--utterances", type=Path, default=Path("data/utterances/utterances_audited.jsonl"))
    parser.add_argument("--manifest", type=Path, default=Path("data/audio/audio_manifest.jsonl"))
    parser.add_argument("--whisper", type=Path, default=Path("data/asr_outputs/whisper_large_v3_local.jsonl"))
    parser.add_argument("--typhoon", type=Path, default=Path("data/asr_outputs/typhoon_asr_api.jsonl"))
    parser.add_argument("--predictions", type=Path, default=Path("data/predictions/grounding_predictions.jsonl"))
    parser.add_argument("--corrections", type=Path, default=Path("data/corrections/corrected_transcripts.jsonl"))
    parser.add_argument("--screens", type=Path, default=Path("data/screens/screens.jsonl"))
    parser.add_argument("--table4", type=Path, default=Path("data/results/table4_correction_effects.csv"))
    parser.add_argument("--table4b", type=Path, default=Path("data/results/table4b_changed_unchanged_effects.csv"))
    parser.add_argument(
        "--transitions", type=Path, default=Path("data/analysis/correction_transition_counts.csv")
    )
    parser.add_argument("--output", type=Path, default=Path("data/analysis/failure_review_sample.csv"))
    parser.add_argument("--guide", type=Path, default=Path("data/analysis/FAILURE_ANALYSIS_GUIDE.md"))
    parser.add_argument("--sample-size", type=int, default=140)
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as file:
        for line_number, line in enumerate(file, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number}: expected a JSON object")
            rows.append(row)
    return rows


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def unique_index(rows: list[dict[str, Any]], key_fn: Callable[[dict[str, Any]], Any], label: str) -> dict[Any, dict[str, Any]]:
    result: dict[Any, dict[str, Any]] = {}
    for row in rows:
        key = key_fn(row)
        if key in result:
            raise ValueError(f"duplicate {label}: {key!r}")
        result[key] = row
    return result


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def point_in_bbox(x: float, y: float, bbox: list[float]) -> bool:
    x1, y1, x2, y2 = bbox
    return x1 <= x <= x2 and y1 <= y <= y2


def point_in_image(prediction: dict[str, Any], screen: dict[str, Any]) -> bool:
    x = prediction.get("pred_x")
    y = prediction.get("pred_y")
    return (
        prediction.get("status") == "success"
        and is_number(x)
        and is_number(y)
        and 0 <= float(x) <= float(screen["width"])
        and 0 <= float(y) <= float(screen["height"])
    )


def prediction_click_correct(prediction: dict[str, Any], screen: dict[str, Any]) -> bool:
    if not point_in_image(prediction, screen):
        return False
    target_id = prediction.get("target_element_id")
    target = next((item for item in screen["elements"] if item.get("element_id") == target_id), None)
    if target is None:
        raise ValueError(f"missing target {target_id!r} on {screen['screen_id']}")
    return point_in_bbox(float(prediction["pred_x"]), float(prediction["pred_y"]), target["bbox"])


def derive_element(prediction: dict[str, Any], screen: dict[str, Any]) -> dict[str, Any] | None:
    if not point_in_image(prediction, screen):
        return None
    x = float(prediction["pred_x"])
    y = float(prediction["pred_y"])
    containing = [
        element
        for element in screen["elements"]
        if point_in_bbox(x, y, element["bbox"])
    ]
    if not containing:
        return None
    return min(
        containing,
        key=lambda element: (
            (element["bbox"][2] - element["bbox"][0])
            * (element["bbox"][3] - element["bbox"][1]),
            element["element_id"],
        ),
    )


def coordinate_text(prediction: dict[str, Any]) -> str:
    if not is_number(prediction.get("pred_x")) or not is_number(prediction.get("pred_y")):
        return ""
    return json.dumps([prediction["pred_x"], prediction["pred_y"]], ensure_ascii=False, separators=(",", ":"))


def coordinates_same(raw: dict[str, Any], corrected: dict[str, Any]) -> bool:
    values = (raw.get("pred_x"), raw.get("pred_y"), corrected.get("pred_x"), corrected.get("pred_y"))
    return all(is_number(value) for value in values) and values[0] == values[2] and values[1] == values[3]


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def stable_order_key(candidate: dict[str, Any]) -> str:
    key = "|".join(
        str(candidate[field])
        for field in ("grounding_model", "asr_model", "correction_method", "audio_id")
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def candidate_taxonomy(candidate: dict[str, Any]) -> str:
    flags = candidate["priority_flags"]
    if flags["uitars_parse_failure"]:
        return "parse_failure"
    if flags["uitars_out_of_bounds"]:
        return "out_of_bounds_prediction"
    if flags["transcript_improved_hurt"]:
        return "correction_helped_transcript_but_hurt_grounding"
    if flags["raw_wrong_correction_helped"]:
        return "correction_helped"
    if flags["changed_no_downstream_gain"]:
        return "correction_changed_without_downstream_gain"
    if flags["transcript_false_correction"] or flags["raw_correct_correction_hurt"]:
        return "over_correction"
    if flags["g1_visual_grounding_error"]:
        return "visual_grounding_error"
    if flags["unchanged_rerun_variability"]:
        return "unchanged_prompt_rerun_variability"
    if candidate["tier"] == "T4_visual_positional" and (not candidate["raw_correct"] or not candidate["corrected_correct"]):
        return "positional_phrase_failure"
    if flags["loanword_asr_error"]:
        return "loanword_ASR_error"
    if flags["confusable_screen_label"]:
        return "confusable_screen_label"
    if candidate["tier"] == "T3_intent" and (not candidate["raw_correct"] or not candidate["corrected_correct"]):
        return "ambiguous_instruction"
    if not candidate["raw_correct"] or not candidate["corrected_correct"]:
        return "visual_grounding_error"
    return "other"


def build_candidates(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, int]]:
    utterances = load_jsonl(args.utterances)
    manifest = load_jsonl(args.manifest)
    screens = load_jsonl(args.screens)
    whisper = load_jsonl(args.whisper)
    typhoon = load_jsonl(args.typhoon)
    corrections = load_jsonl(args.corrections)
    predictions = load_jsonl(args.predictions)

    utterance_by_id = unique_index(utterances, lambda row: row["utterance_id"], "utterance_id")
    manifest_by_id = unique_index(manifest, lambda row: row["audio_id"], "audio_id")
    screen_by_id = unique_index(screens, lambda row: row["screen_id"], "screen_id")
    asr_by_key = unique_index(
        whisper + typhoon,
        lambda row: (row["asr_model"], row["audio_id"]),
        "ASR model/audio pair",
    )
    correction_by_key = unique_index(
        corrections,
        lambda row: (row["asr_model"], row["method"], row["audio_id"]),
        "correction model/method/audio tuple",
    )
    unique_index(predictions, lambda row: row["prediction_id"], "prediction_id")

    raw_by_key: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    corrected_by_key: dict[tuple[str, str, str, str, str, str], dict[str, Any]] = {}
    condition_details = {condition: key for key, condition in CORRECTED_CONDITIONS.items()}
    for prediction in predictions:
        condition = prediction.get("input_condition")
        if condition in RAW_CONDITIONS.values():
            key = (
                prediction["grounding_model"],
                prediction["asr_model"],
                prediction["utterance_id"],
                prediction["audio_id"],
                prediction["screen_id"],
            )
            if key in raw_by_key:
                raise ValueError(f"duplicate raw prediction pair: {key!r}")
            raw_by_key[key] = prediction
        elif condition in condition_details:
            asr_model, method = condition_details[condition]
            if prediction.get("asr_model") != asr_model:
                raise ValueError(f"corrected prediction ASR mismatch: {prediction['prediction_id']}")
            key = (
                prediction["grounding_model"],
                asr_model,
                method,
                prediction["utterance_id"],
                prediction["audio_id"],
                prediction["screen_id"],
            )
            if key in corrected_by_key:
                raise ValueError(f"duplicate corrected prediction pair: {key!r}")
            corrected_by_key[key] = prediction

    candidates: list[dict[str, Any]] = []
    transition_counter: Counter[tuple[str, str, str, str]] = Counter()
    subset_counter: Counter[tuple[str, str, str, str]] = Counter()
    coordinate_counter: Counter[tuple[str, str, str, str, str]] = Counter()

    for corrected_key, corrected_prediction in corrected_by_key.items():
        grounding_model, asr_model, method, utterance_id, audio_id, screen_id = corrected_key
        raw_key = (grounding_model, asr_model, utterance_id, audio_id, screen_id)
        raw_prediction = raw_by_key.get(raw_key)
        if raw_prediction is None:
            raise ValueError(f"missing raw prediction for {corrected_prediction['prediction_id']}")
        correction = correction_by_key.get((asr_model, method, audio_id))
        if correction is None:
            raise ValueError(f"missing correction for {corrected_prediction['prediction_id']}")
        asr = asr_by_key.get((asr_model, audio_id))
        if asr is None:
            raise ValueError(f"missing ASR record for {corrected_prediction['prediction_id']}")
        utterance = utterance_by_id[utterance_id]
        audio = manifest_by_id[audio_id]
        screen = screen_by_id[screen_id]

        raw_transcript = str(asr.get("transcript", ""))
        corrected_transcript = str(correction.get("corrected_transcript", ""))
        if raw_prediction.get("transcript") != raw_transcript or correction.get("input_transcript") != raw_transcript:
            raise ValueError(f"raw transcript provenance mismatch for {corrected_prediction['prediction_id']}")
        if corrected_prediction.get("transcript") != corrected_transcript:
            raise ValueError(f"corrected transcript provenance mismatch for {corrected_prediction['prediction_id']}")

        raw_correct = prediction_click_correct(raw_prediction, screen)
        corrected_correct = prediction_click_correct(corrected_prediction, screen)
        transition = ("C" if raw_correct else "W") + ("C" if corrected_correct else "W")
        changed = bool(correction.get("changed"))
        same_coordinate = coordinates_same(raw_prediction, corrected_prediction)
        subset = "changed" if changed else "unchanged"
        transition_counter[(grounding_model, asr_model, method, transition)] += 1
        subset_counter[(grounding_model, asr_model, method, subset)] += 1
        coordinate_counter[(grounding_model, asr_model, method, subset, "same" if same_coordinate else "different")] += 1

        gold_text = str(utterance.get("text_gold", ""))
        raw_cer = character_error_rate(gold_text, raw_transcript)
        corrected_cer = character_error_rate(gold_text, corrected_transcript)
        loanwords = loanwords_for_utterance(utterance)
        raw_loanword_errors = loanword_error_counts(loanwords, raw_transcript)[1]
        corrected_loanword_errors = loanword_error_counts(loanwords, corrected_transcript)[1]
        recovered = corrected_cer < raw_cer or corrected_loanword_errors < raw_loanword_errors
        false_correction = corrected_cer > raw_cer or (changed and raw_cer == 0)

        target = next(
            element for element in screen["elements"] if element["element_id"] == utterance["target_element_id"]
        )
        raw_element = derive_element(raw_prediction, screen)
        corrected_element = derive_element(corrected_prediction, screen)
        target_group = target.get("distractor_group")
        confusable = bool(
            target_group
            and any(
                element is not None
                and element.get("element_id") != target.get("element_id")
                and element.get("distractor_group") == target_group
                for element in (raw_element, corrected_element)
            )
        )
        raw_oob = raw_prediction.get("status") == "success" and not point_in_image(raw_prediction, screen)
        corrected_oob = corrected_prediction.get("status") == "success" and not point_in_image(corrected_prediction, screen)
        parse_failure = raw_prediction.get("status") != "success" or corrected_prediction.get("status") != "success"

        priority_flags = {
            "raw_wrong_correction_helped": changed and transition == "WC",
            "raw_correct_correction_hurt": changed and transition == "CW",
            "transcript_false_correction": changed and false_correction,
            "method_c_g1_degradation": grounding_model == "G1" and method == "C_full_screen_aware_alias" and changed and transition == "CW",
            "whisper_ab_g1_improvement": grounding_model == "G1" and asr_model == "whisper_large_v3_local" and method in {"A_no_screen_cleanup", "B_screen_string_match"} and changed and transition == "WC",
            "unchanged_rerun_variability": not changed and not same_coordinate,
            "uitars_parse_failure": grounding_model == "G2" and parse_failure,
            "uitars_out_of_bounds": grounding_model == "G2" and (raw_oob or corrected_oob),
            "t3_t4_failure": utterance["tier"] in {"T3_intent", "T4_visual_positional"} and (not raw_correct or not corrected_correct),
            "loanword_asr_error": raw_loanword_errors > 0,
            "confusable_screen_label": confusable,
            "transcript_improved_hurt": changed and recovered and transition == "CW",
            "changed_no_downstream_gain": changed and transition in {"CC", "WW"},
            "g1_visual_grounding_error": grounding_model == "G1"
            and (raw_cer == 0 or corrected_cer == 0)
            and (not raw_correct or not corrected_correct),
        }
        candidate = {
            "utterance_id": utterance_id,
            "audio_id": audio_id,
            "screen_id": screen_id,
            "domain": screen.get("domain", ""),
            "tier": utterance.get("tier", ""),
            "language_class": utterance.get("language_class", ""),
            "tts_engine": audio.get("engine_id", ""),
            "voice_id": audio.get("voice_id", ""),
            "asr_model": asr_model,
            "grounding_model": grounding_model,
            "gold_text": gold_text,
            "raw_asr_transcript": raw_transcript,
            "corrected_transcript": corrected_transcript,
            "correction_method": method,
            "transcript_changed": changed,
            "target_label": target.get("label", ""),
            "predicted_label_raw": str(raw_prediction.get("pred_label", "")),
            "predicted_label_corrected": str(corrected_prediction.get("pred_label", "")),
            "raw_coordinates": coordinate_text(raw_prediction),
            "corrected_coordinates": coordinate_text(corrected_prediction),
            "raw_correct": raw_correct,
            "corrected_correct": corrected_correct,
            "coordinate_same": same_coordinate,
            "transition_type": transition,
            "priority_flags": priority_flags,
        }
        candidate["candidate_failure_taxonomy"] = candidate_taxonomy(candidate)
        candidates.append(candidate)

    expected_corrected = len(corrections) * 2
    if len(candidates) != expected_corrected:
        raise ValueError(f"expected {expected_corrected} corrected grounding pairs, found {len(candidates)}")

    validate_aggregates(args, transition_counter, subset_counter, coordinate_counter)
    counts = {
        "utterances": len(utterances),
        "audio": len(manifest),
        "asr": len(whisper) + len(typhoon),
        "corrections": len(corrections),
        "prediction_pairs": len(candidates),
    }
    return candidates, counts


def csv_int(row: dict[str, str], field: str) -> int:
    value = row.get(field, "")
    return int(value) if value else 0


def validate_aggregates(
    args: argparse.Namespace,
    transitions: Counter[tuple[str, str, str, str]],
    subsets: Counter[tuple[str, str, str, str]],
    coordinates: Counter[tuple[str, str, str, str, str]],
) -> None:
    transition_rows = load_csv(args.transitions)
    table4_rows = load_csv(args.table4)
    table4b_rows = load_csv(args.table4b)
    table4_by_key = {
        (row["grounding_model"], row["asr_model"], row["correction_method"]): row for row in table4_rows
    }
    transition_by_key = {
        (row["grounding_model"], row["asr_model"], row["correction_method"]): row
        for row in transition_rows
    }
    if table4_by_key.keys() != transition_by_key.keys() or len(table4_by_key) != 12:
        raise ValueError("Table 4 and transition groups do not contain the same 12 groups")
    for key, transition_row in transition_by_key.items():
        derived = {name: transitions[(*key, name)] for name in ("CC", "WC", "CW", "WW")}
        for name, count in derived.items():
            if csv_int(transition_row, name) != count or csv_int(table4_by_key[key], name) != count:
                raise ValueError(f"transition mismatch for {key}/{name}")
        if csv_int(transition_row, "n_total") != sum(derived.values()):
            raise ValueError(f"transition denominator mismatch for {key}")

    if len(table4b_rows) != 24:
        raise ValueError(f"expected 24 Table 4b rows, found {len(table4b_rows)}")
    for row in table4b_rows:
        key = (row["grounding_model"], row["asr_model"], row["correction_method"], row["subset"])
        if csv_int(row, "n") != subsets[key]:
            raise ValueError(f"subset denominator mismatch for {key}")
        same = coordinates[(*key, "same")]
        different = coordinates[(*key, "different")]
        if csv_int(row, "exact_same_coordinate_count") != same or csv_int(row, "different_coordinate_count") != different:
            raise ValueError(f"coordinate-count mismatch for {key}")


def select_sample(candidates: list[dict[str, Any]], sample_size: int) -> tuple[list[dict[str, Any]], dict[str, tuple[int, int]]]:
    if not 100 <= sample_size <= 150:
        raise ValueError("sample size must be between 100 and 150")
    if sample_size > len(candidates):
        raise ValueError("sample size exceeds candidate count")

    targets = (
        ("raw_wrong_correction_helped", 8),
        ("raw_correct_correction_hurt", 8),
        ("transcript_false_correction", 10),
        ("method_c_g1_degradation", 6),
        ("whisper_ab_g1_improvement", 3),
        ("unchanged_rerun_variability", 15),
        ("uitars_parse_failure", 14),
        ("uitars_out_of_bounds", 8),
        ("t3_t4_failure", 16),
        ("loanword_asr_error", 10),
        ("confusable_screen_label", 8),
        ("transcript_improved_hurt", 3),
        ("changed_no_downstream_gain", 10),
        ("g1_visual_grounding_error", 8),
    )
    selected: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    balance: dict[str, Counter[str]] = {
        field: Counter()
        for field in (
            "tier",
            "asr_model",
            "grounding_model",
            "correction_method",
            "candidate_failure_taxonomy",
        )
    }

    def candidate_id(candidate: dict[str, Any]) -> tuple[str, str, str, str]:
        return (
            candidate["grounding_model"],
            candidate["asr_model"],
            candidate["correction_method"],
            candidate["audio_id"],
        )

    def add(candidate: dict[str, Any]) -> None:
        selected[candidate_id(candidate)] = candidate
        for field, counter in balance.items():
            counter[str(candidate[field])] += 1

    def choose(pool: list[dict[str, Any]]) -> dict[str, Any]:
        return min(
            pool,
            key=lambda item: (
                sum(balance[field][str(item[field])] for field in balance),
                stable_order_key(item),
            ),
        )

    coverage: dict[str, tuple[int, int]] = {}
    for flag, target in targets:
        pool = [candidate for candidate in candidates if candidate["priority_flags"][flag]]
        desired = min(target, len(pool))
        while sum(1 for candidate in selected.values() if candidate["priority_flags"][flag]) < desired:
            available = [candidate for candidate in pool if candidate_id(candidate) not in selected]
            if not available:
                break
            add(choose(available))
        coverage[flag] = (
            len(pool),
            sum(1 for candidate in selected.values() if candidate["priority_flags"][flag]),
        )

    priority_candidates = [candidate for candidate in candidates if any(candidate["priority_flags"].values())]
    for pool in (priority_candidates, candidates):
        while len(selected) < sample_size:
            available = [candidate for candidate in pool if candidate_id(candidate) not in selected]
            if not available:
                break
            add(choose(available))
    if len(selected) != sample_size:
        raise ValueError(f"could only select {len(selected)} of {sample_size} requested cases")

    sample = sorted(
        selected.values(),
        key=lambda row: (
            row["grounding_model"],
            row["asr_model"],
            row["correction_method"],
            row["tier"],
            row["audio_id"],
        ),
    )
    for flag, _ in targets:
        available, _ = coverage[flag]
        coverage[flag] = (
            available,
            sum(1 for candidate in sample if candidate["priority_flags"][flag]),
        )
    return sample, coverage


def output_row(candidate: dict[str, Any], index: int) -> dict[str, str]:
    return {
        "case_id": f"case_{index:03d}",
        "utterance_id": str(candidate["utterance_id"]),
        "audio_id": str(candidate["audio_id"]),
        "screen_id": str(candidate["screen_id"]),
        "domain": str(candidate["domain"]),
        "tier": str(candidate["tier"]),
        "language_class": str(candidate["language_class"]),
        "tts_engine": str(candidate["tts_engine"]),
        "voice_id": str(candidate["voice_id"]),
        "asr_model": str(candidate["asr_model"]),
        "grounding_model": str(candidate["grounding_model"]),
        "gold_text": str(candidate["gold_text"]),
        "raw_asr_transcript": str(candidate["raw_asr_transcript"]),
        "corrected_transcript": str(candidate["corrected_transcript"]),
        "correction_method": str(candidate["correction_method"]),
        "transcript_changed": bool_text(candidate["transcript_changed"]),
        "target_label": str(candidate["target_label"]),
        "predicted_label_raw": str(candidate["predicted_label_raw"]),
        "predicted_label_corrected": str(candidate["predicted_label_corrected"]),
        "raw_coordinates": str(candidate["raw_coordinates"]),
        "corrected_coordinates": str(candidate["corrected_coordinates"]),
        "raw_click_correct": bool_text(candidate["raw_correct"]),
        "corrected_click_correct": bool_text(candidate["corrected_correct"]),
        "coordinate_same": bool_text(candidate["coordinate_same"]),
        "transition_type": str(candidate["transition_type"]),
        "candidate_failure_taxonomy": str(candidate["candidate_failure_taxonomy"]),
        "manual_failure_taxonomy": "",
        "notes": "",
        "include_as_qualitative_example": "",
    }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(counter: Counter[str], header: str) -> str:
    lines = [f"| {header} | Cases |", "| --- | ---: |"]
    lines.extend(f"| {key} | {value} |" for key, value in sorted(counter.items()))
    return "\n".join(lines)


def write_guide(
    path: Path,
    rows: list[dict[str, str]],
    coverage: dict[str, tuple[int, int]],
    source_counts: dict[str, int],
) -> None:
    counters = {
        "Tier": Counter(row["tier"] for row in rows),
        "ASR model": Counter(row["asr_model"] for row in rows),
        "Grounding model": Counter(row["grounding_model"] for row in rows),
        "Correction method": Counter(row["correction_method"] for row in rows),
        "Transition": Counter(row["transition_type"] for row in rows),
        "Candidate taxonomy": Counter(row["candidate_failure_taxonomy"] for row in rows),
    }
    coverage_rows = "\n".join(
        f"| `{flag}` | {available} | {selected} |"
        for flag, (available, selected) in coverage.items()
    )
    distribution_sections = "\n\n".join(
        f"### By {name}\n\n{markdown_table(counter, name)}" for name, counter in counters.items()
    )
    taxonomy = "\n".join(f"- `{value}`" for value in TAXONOMY_VALUES)
    text = f"""# Manual Failure and Variability Review Guide

## Scope

`failure_review_sample.csv` contains **{len(rows)}** deterministically selected cases for human review. It is an analysis-preparation artifact only: no prediction, correction, or result-table records were modified.

The sampler validated {source_counts['prediction_pairs']} raw/corrected grounding pairs derived from {source_counts['corrections']} correction records, {source_counts['asr']} ASR records, {source_counts['audio']} audio-manifest rows, and {source_counts['utterances']} audited utterances. Pairwise CC/WC/CW/WW totals and changed/unchanged coordinate counts were checked against `correction_transition_counts.csv`, Table 4, and Table 4b before sampling.

## Transition Codes

- `CC`: raw click correct, corrected-run click correct.
- `WC`: raw click wrong, corrected-run click correct.
- `CW`: raw click correct, corrected-run click wrong.
- `WW`: both clicks wrong.

`coordinate_same=true` requires two successfully parsed, exactly equal coordinate pairs. A false value can mean a different coordinate, a parse failure, or a missing coordinate. Inspect the coordinate and prediction-label fields before assigning a manual category.

## Sampling

Cases were selected without replacement from unique `(grounding_model, asr_model, correction_method, audio_id)` tuples. Selection first covered the requested priority signals, then filled to {len(rows)} while balancing tier, ASR model, grounding model, and correction method. Priority signals overlap, so their selected counts do not sum to the sample size.

| Priority signal | Available pairs | Selected cases |
| --- | ---: | ---: |
{coverage_rows}

## Sample Distribution

{distribution_sections}

## Review Procedure

1. Compare `gold_text`, `raw_asr_transcript`, and `corrected_transcript` without using the gold text to reinterpret the model output.
2. Inspect raw and corrected labels, coordinates, click outcomes, and transition type.
3. Replace or confirm `candidate_failure_taxonomy` in `manual_failure_taxonomy` using one allowed value below.
4. Use `notes` for concise evidence. Mark `include_as_qualitative_example` as `yes` only for clear, representative cases.
5. Treat unchanged-transcript differences as independent grounding rerun variability, not correction effects.
6. Treat parse success and click correctness separately. Out-of-bounds parsed coordinates are click failures, while unparseable UI-TARS outputs are parse failures.

## Allowed Manual Taxonomy

{taxonomy}

The automatic taxonomy is a review aid, not a final annotation. In particular, `TTS_pronunciation_issue` and some segmentation errors require listening or native-speaker judgment and are not inferred automatically.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    args = parse_args()
    candidates, source_counts = build_candidates(args)
    sample, coverage = select_sample(candidates, args.sample_size)
    rows = [output_row(candidate, index) for index, candidate in enumerate(sample, 1)]
    write_csv(args.output, rows)
    write_guide(args.guide, rows, coverage, source_counts)
    print(f"candidate_pairs={len(candidates)}")
    print(f"sample_size={len(rows)}")
    print(f"output={args.output}")
    print(f"guide={args.guide}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
