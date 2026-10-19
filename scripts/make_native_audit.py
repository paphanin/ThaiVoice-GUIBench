"""Create a native-speaker audit CSV scaffold for generated utterances."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


AUDIT_COLUMNS = [
    "utterance_id",
    "domain",
    "tier",
    "intent_id",
    "screen_id",
    "target_element_id",
    "target_label",
    "original_text",
    "naturalness_score",
    "tier_validity",
    "label_leakage",
    "asr_tts_risk",
    "edited_text",
    "edit_type",
    "edit_reason",
    "auditor_notes",
]

HUMAN_AUDIT_COLUMNS = [
    "tier_validity",
    "label_leakage",
    "asr_tts_risk",
    "edited_text",
    "edit_type",
    "edit_reason",
    "auditor_notes",
]

SUMMARY_TEXT = """# Native Audit Rubric

This audit sheet is for human/native-speaker review of ThaiVoice-GUIBench utterances.
The CSV is a scaffold: metadata and original text are prefilled, while judgment fields are intentionally blank.

## Naturalness Score

Use exactly one of:

- `natural`: sounds like something a Thai speaker could naturally say to a phone, app, or assistant.
- `slightly_awkward`: understandable, but too formal, long, translated-sounding, or a bit unnatural.
- `bad`: unusable for the benchmark because it is unnatural, wrong meaning, wrong tier, leaked label, unsafe, too ambiguous, too long, or not speakable.

Project-specific prefill rule for this audit pass:

- Utterances containing `จำลอง` are prefilled as `slightly_awkward`.
- All other generated utterances are prefilled as `natural`.
- Human auditors may override these labels if they find another issue.

## Tier Validity

- `T1_verbatim`: may say the visible target label.
- `T2_paraphrase`: should use a synonym, translation, or paraphrase; must not copy the exact target label.
- `T3_intent`: should describe the user goal; must not name the UI element.
- `T4_visual_positional`: should use visual or positional cues; must not copy the target label.

## Label Leakage

For T2-T4, mark leakage if the command contains the exact target label, copied English label, case variant, or listed phonological alias.
Do not over-ban normal Thai semantic words. For example, if the target label is `Transfer`, `โอนเงิน` is allowed in T2, but `Transfer`, `ทรานส์เฟอร์`, or `ทรานเฟอร์` are not.

## ASR/TTS Risk

Flag high risk for text that TTS or ASR may mangle unnecessarily, such as odd abbreviations, symbols, emojis, repeated punctuation, or unnatural code-switching.
Prefer controlled natural speech over noisy text.

## Edit Types

Use one of:

- `none`
- `style_simplification`
- `spoken_register_fix`
- `tier_fix`
- `label_leakage_fix`
- `meaning_fix`
- `particle_fix`
- `length_reduction`
- `code_switch_fix`
- `safety_fix`
- `duplicate_fix`
- `remove_bad_item`

## Editing Rules

Make the smallest edit that fixes the problem. Preserve intent, tier, and diversity.
Do not rewrite natural commands just to match personal style.

## Safety

For mock finance/settings tasks, avoid wording that performs real private actions.
Use navigation phrasing such as `เปิดหน้า...` for sensitive mock flows.
Avoid real credentials, OTP, real payment execution, or private account data.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--utterances", type=Path, default=Path("data/utterances/utterances.jsonl"))
    parser.add_argument("--intents", type=Path, default=Path("data/intents/intents.jsonl"))
    parser.add_argument("--screens", type=Path, default=Path("data/screens/screens.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/utterances/audit/native_audit_v1.csv"))
    parser.add_argument("--summary", type=Path, default=Path("data/utterances/audit/native_audit_summary.md"))
    parser.add_argument("--preserve-existing", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def load_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    if not path.exists():
        raise ValueError(f"{label} does not exist: {path}")
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
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


def index_by_id(records: list[dict[str, Any]], field: str, label: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(records, start=1):
        value = record.get(field)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{label}:{index}: missing or invalid {field}")
        if value in indexed:
            raise ValueError(f"duplicate {field} `{value}` in {label}")
        indexed[value] = record
    return indexed


def screen_element_index(screens: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    indexed: dict[str, dict[str, dict[str, Any]]] = {}
    for screen in screens:
        screen_id = screen.get("screen_id")
        if not isinstance(screen_id, str) or not screen_id:
            raise ValueError("screen record missing screen_id")
        elements = screen.get("elements")
        if not isinstance(elements, list):
            raise ValueError(f"screen `{screen_id}` elements must be a list")
        indexed[screen_id] = {}
        for element in elements:
            element_id = element.get("element_id") if isinstance(element, dict) else None
            if not isinstance(element_id, str) or not element_id:
                raise ValueError(f"screen `{screen_id}` contains element without element_id")
            indexed[screen_id][element_id] = element
    return indexed


def naturalness_score_for_text(text: str) -> str:
    return "slightly_awkward" if "จำลอง" in text else "natural"


def neutralize_polite_particles(text: str) -> str:
    for particle in ("ครับ", "ค่ะ", "คะ"):
        text = text.replace(particle, "")
    return " ".join(text.split())


def load_existing_audit(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise ValueError(f"existing audit CSV has no header: {path}")
        missing = [column for column in AUDIT_COLUMNS if column not in reader.fieldnames]
        if missing:
            raise ValueError(f"existing audit CSV missing required columns {missing}: {path}")
        rows: dict[str, dict[str, str]] = {}
        for line_number, row in enumerate(reader, start=2):
            utterance_id = (row.get("utterance_id") or "").strip()
            if not utterance_id:
                raise ValueError(f"existing audit CSV:{line_number}: missing utterance_id")
            if utterance_id in rows:
                raise ValueError(f"duplicate existing audit utterance_id `{utterance_id}`")
            rows[utterance_id] = {column: (row.get(column) or "").strip() for column in AUDIT_COLUMNS}
    return rows


def make_rows(
    utterances: list[dict[str, Any]],
    intents_by_id: dict[str, dict[str, Any]],
    elements_by_screen: dict[str, dict[str, dict[str, Any]]],
    existing_rows_by_id: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    existing_rows_by_id = existing_rows_by_id or {}
    seen_utterance_ids: set[str] = set()
    rows: list[dict[str, str]] = []
    for index, utterance in enumerate(utterances, start=1):
        utterance_id = utterance.get("utterance_id")
        if not isinstance(utterance_id, str) or not utterance_id:
            raise ValueError(f"utterances:{index}: missing or invalid utterance_id")
        if utterance_id in seen_utterance_ids:
            raise ValueError(f"duplicate utterance_id `{utterance_id}`")
        seen_utterance_ids.add(utterance_id)

        intent_id = utterance.get("intent_id")
        if intent_id not in intents_by_id:
            raise ValueError(f"utterance `{utterance_id}` references missing intent `{intent_id}`")
        screen_id = utterance.get("screen_id")
        if screen_id not in elements_by_screen:
            raise ValueError(f"utterance `{utterance_id}` references missing screen `{screen_id}`")
        target_element_id = utterance.get("target_element_id")
        if target_element_id not in elements_by_screen[screen_id]:
            raise ValueError(
                f"utterance `{utterance_id}` target_element_id `{target_element_id}` missing from screen `{screen_id}`"
            )
        target = elements_by_screen[screen_id][target_element_id]

        original_text = str(utterance.get("text_gold", ""))
        row = {
            "utterance_id": utterance_id,
            "domain": str(intents_by_id[intent_id]["domain"]),
            "tier": str(utterance.get("tier", "")),
            "intent_id": str(intent_id),
            "screen_id": str(screen_id),
            "target_element_id": str(target_element_id),
            "target_label": str(target.get("label", "")),
            "original_text": original_text,
            "naturalness_score": naturalness_score_for_text(original_text),
        }
        row.update({column: "" for column in HUMAN_AUDIT_COLUMNS})
        existing = existing_rows_by_id.get(utterance_id)
        if existing:
            row["naturalness_score"] = existing.get("naturalness_score") or row["naturalness_score"]
            for column in HUMAN_AUDIT_COLUMNS:
                row[column] = existing.get(column, "")
            if row["edited_text"]:
                row["edited_text"] = neutralize_polite_particles(row["edited_text"])
        rows.append(row)
    return rows


def write_csv(rows: list[dict[str, str]], path: Path, overwrite: bool) -> None:
    if path.exists() and path.stat().st_size > 0 and not overwrite:
        raise ValueError(f"{path} already exists; pass --overwrite to replace it")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=AUDIT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(path: Path, overwrite: bool) -> None:
    if path.exists() and path.stat().st_size > 0 and not overwrite:
        raise ValueError(f"{path} already exists; pass --overwrite to replace it")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(SUMMARY_TEXT, encoding="utf-8")


def create_audit(
    utterances_path: Path,
    intents_path: Path,
    screens_path: Path,
    output_path: Path,
    summary_path: Path,
    overwrite: bool,
    preserve_existing: bool,
) -> list[dict[str, str]]:
    utterances = load_jsonl(utterances_path, "utterances")
    intents = load_jsonl(intents_path, "intents")
    screens = load_jsonl(screens_path, "screens")
    existing_rows_by_id = load_existing_audit(output_path) if preserve_existing else {}
    rows = make_rows(
        utterances=utterances,
        intents_by_id=index_by_id(intents, "intent_id", "intents"),
        elements_by_screen=screen_element_index(screens),
        existing_rows_by_id=existing_rows_by_id,
    )
    write_csv(rows, output_path, overwrite=overwrite)
    write_summary(summary_path, overwrite=overwrite)
    return rows


def main() -> int:
    args = parse_args()
    try:
        rows = create_audit(
            utterances_path=args.utterances,
            intents_path=args.intents,
            screens_path=args.screens,
            output_path=args.output,
            summary_path=args.summary,
            overwrite=args.overwrite,
            preserve_existing=args.preserve_existing,
        )
    except ValueError as exc:
        print(f"Native audit scaffold failed: {exc}")
        return 1
    print(f"Wrote {len(rows)} audit rows to {args.output}")
    print(f"Wrote audit rubric to {args.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
