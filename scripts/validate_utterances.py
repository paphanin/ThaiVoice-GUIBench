"""Validate ThaiVoice-GUIBench generated utterances."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


TIERS = ("T1_verbatim", "T2_paraphrase", "T3_intent", "T4_visual_positional")
LABEL_ALIASES = {
    "transfer": ("ทรานส์เฟอร์", "ทรานเฟอร์"),
    "top up": ("ท็อปอัป", "ท็อปอัพ"),
    "withdraw": ("วิดดรอว์",),
    "history": ("ฮิสทอรี",),
    "pay bill": ("เพย์บิล",),
    "scan": ("สแกน",),
    "accounts": ("แอคเคานต์",),
    "search": ("เสิร์ช",),
    "sort": ("ซอร์ต",),
    "filter": ("ฟิลเตอร์",),
    "promotion": ("โปรโมชั่น",),
    "cart": ("คาร์ต",),
    "add cart": ("แอดคาร์ต",),
    "buy now": ("บาย นาว", "บายนาว"),
    "notifications": ("โนติฟิเคชัน", "โนติฟิเคชั่น"),
    "settings": ("เซตติง", "เซ็ตติ้ง"),
    "privacy": ("ไพรเวซี",),
    "security": ("ซีเคียวริตี้",),
    "about": ("อะเบาต์",),
    "send": ("เซนด์",),
    "mute": ("มิวต์",),
    "profile": ("โพรไฟล์",),
    "โปรโมชัน": ("โปรโมชั่น",),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--utterances", type=Path, default=Path("data/utterances/utterances.jsonl"))
    parser.add_argument("--mappings", type=Path, default=Path("data/intents/intent_screen_targets.jsonl"))
    parser.add_argument("--screens", type=Path, default=Path("data/screens/screens.jsonl"))
    parser.add_argument("--schema", type=Path, default=Path("schemas/utterance.schema.json"))
    return parser.parse_args()


def load_json(path: Path, label: str) -> tuple[dict[str, Any] | None, list[str]]:
    if not path.exists():
        return None, [f"{label} does not exist: {path}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, [f"{label} is invalid JSON: {path}:{exc.lineno}:{exc.colno}: {exc.msg}"]
    if not isinstance(data, dict):
        return None, [f"{label} must be a JSON object: {path}"]
    return data, []


def load_jsonl(path: Path, label: str) -> tuple[list[dict[str, Any]], list[str]]:
    if not path.exists():
        return [], [f"{label} does not exist: {path}"]
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    with path.open("r", encoding="utf-8") as file:
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
                errors.append(f"{label}:{line_number}: expected a JSON object")
                continue
            records.append(record)
    if not records:
        errors.append(f"{label} contains no records: {path}")
    return records, errors


def format_error_path(error_path: Any) -> str:
    parts = [str(part) for part in error_path]
    return ".".join(parts) if parts else "<record>"


def schema_errors(records: list[dict[str, Any]], schema: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(schema)
    errors: list[str] = []
    for index, record in enumerate(records, start=1):
        record_id = record.get("utterance_id", f"line_{index}")
        for error in sorted(validator.iter_errors(record), key=lambda item: list(item.path)):
            errors.append(f"utterance {record_id}: {format_error_path(error.path)}: {error.message}")
    return errors


def screen_indexes(screens: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, dict[str, Any]]]]:
    by_screen = {screen["screen_id"]: screen for screen in screens}
    elements = {
        screen["screen_id"]: {element["element_id"]: element for element in screen.get("elements", [])}
        for screen in screens
    }
    return by_screen, elements


def leakage_terms(label: str) -> list[str]:
    terms = [label.strip()]
    lowered = label.strip().lower()
    terms.extend(LABEL_ALIASES.get(lowered, ()))
    terms.extend(LABEL_ALIASES.get(label.strip(), ()))
    return [term for term in dict.fromkeys(terms) if term]


def leakage_term(text: str, label: str) -> str | None:
    text_lower = text.lower()
    for term in leakage_terms(label):
        if term.lower() in text_lower:
            return term
    return None


def duplicate_errors(records: list[dict[str, Any]], field: str) -> list[str]:
    values = [record.get(field) for record in records if isinstance(record.get(field), str)]
    counts = Counter(values)
    return [f"duplicate {field} `{value}`" for value, count in sorted(counts.items()) if count > 1]


def validate_utterances(
    utterances_path: Path,
    mappings_path: Path,
    screens_path: Path,
    schema_path: Path,
) -> list[str]:
    errors: list[str] = []
    schema, schema_load_errors = load_json(schema_path, "utterance schema")
    errors.extend(schema_load_errors)
    utterances, load_errors = load_jsonl(utterances_path, "utterances")
    errors.extend(load_errors)
    mappings, load_errors = load_jsonl(mappings_path, "intent-screen mappings")
    errors.extend(load_errors)
    screens, load_errors = load_jsonl(screens_path, "screens")
    errors.extend(load_errors)
    if errors:
        return errors

    assert schema is not None
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        return [f"utterance schema is invalid: {exc}"]

    errors.extend(schema_errors(utterances, schema))
    errors.extend(duplicate_errors(utterances, "utterance_id"))
    errors.extend(duplicate_errors(utterances, "text_gold"))
    if errors:
        return errors

    mappings_by_id = {mapping["mapping_id"]: mapping for mapping in mappings}
    screens_by_id, elements_by_screen = screen_indexes(screens)
    tiers_by_mapping: defaultdict[str, set[str]] = defaultdict(set)

    for utterance in utterances:
        utterance_id = utterance["utterance_id"]
        mapping_id = utterance["mapping_id"]
        mapping = mappings_by_id.get(mapping_id)
        if mapping is None:
            errors.append(f"utterance {utterance_id}: mapping_id `{mapping_id}` does not exist")
            continue

        if utterance["intent_id"] != mapping["intent_id"]:
            errors.append(f"utterance {utterance_id}: intent_id does not match mapping `{mapping_id}`")
        if utterance["screen_id"] != mapping["screen_id"]:
            errors.append(f"utterance {utterance_id}: screen_id does not match mapping `{mapping_id}`")
        if utterance["target_element_id"] != mapping["target_element_id"]:
            errors.append(f"utterance {utterance_id}: target_element_id does not match mapping `{mapping_id}`")

        screen = screens_by_id.get(utterance["screen_id"])
        if screen is None:
            errors.append(f"utterance {utterance_id}: screen_id `{utterance['screen_id']}` does not exist")
            continue
        element = elements_by_screen[utterance["screen_id"]].get(utterance["target_element_id"])
        if element is None:
            errors.append(
                f"utterance {utterance_id}: target_element_id `{utterance['target_element_id']}` does not exist on screen `{utterance['screen_id']}`"
            )
            continue

        text = utterance["text_gold"].strip()
        if not text:
            errors.append(f"utterance {utterance_id}: text_gold must not be empty")
        tiers_by_mapping[mapping_id].add(utterance["tier"])

        if utterance["tier"] != "T1_verbatim":
            leaked = leakage_term(text, element["label"])
            if leaked:
                errors.append(
                    f"utterance {utterance_id}: {utterance['tier']} leaks target label or alias `{leaked}`"
                )

    for mapping_id in mappings_by_id:
        missing_tiers = sorted(set(TIERS) - tiers_by_mapping.get(mapping_id, set()))
        if missing_tiers:
            errors.append(f"mapping {mapping_id}: missing utterance tiers {missing_tiers}")

    return errors


def main() -> int:
    args = parse_args()
    errors = validate_utterances(
        utterances_path=args.utterances,
        mappings_path=args.mappings,
        screens_path=args.screens,
        schema_path=args.schema,
    )
    if errors:
        print("Utterance validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Utterance validation passed: {args.utterances}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
