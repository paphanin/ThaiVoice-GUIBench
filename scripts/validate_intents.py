"""Validate ThaiVoice-GUIBench intent records and screen-target mappings."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intents", type=Path, default=Path("data/intents/intents.jsonl"))
    parser.add_argument("--mappings", type=Path, default=Path("data/intents/intent_screen_targets.jsonl"))
    parser.add_argument("--screens", type=Path, default=Path("data/screens/screens.jsonl"))
    parser.add_argument("--intent-schema", type=Path, default=Path("schemas/intent.schema.json"))
    parser.add_argument("--mapping-schema", type=Path, default=Path("schemas/intent_screen_target.schema.json"))
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


def load_jsonl(path: Path, label: str, required: bool = True) -> tuple[list[dict[str, Any]], list[str]]:
    if not path.exists():
        if required:
            return [], [f"{label} does not exist: {path}"]
        return [], []

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

    if required and not records:
        errors.append(f"{label} contains no records: {path}")
    return records, errors


def format_error_path(error_path: Any) -> str:
    parts = [str(part) for part in error_path]
    return ".".join(parts) if parts else "<record>"


def validate_schema_records(
    records: list[dict[str, Any]],
    schema: dict[str, Any],
    label: str,
    id_field: str,
) -> list[str]:
    validator = Draft202012Validator(schema)
    errors: list[str] = []
    for index, record in enumerate(records, start=1):
        record_id = record.get(id_field, f"line_{index}")
        for error in sorted(validator.iter_errors(record), key=lambda item: list(item.path)):
            errors.append(f"{label} {record_id}: {format_error_path(error.path)}: {error.message}")
    return errors


def duplicate_errors(records: list[dict[str, Any]], field: str, label: str) -> list[str]:
    values = [record.get(field) for record in records if isinstance(record.get(field), str)]
    counts = Counter(values)
    return [f"duplicate {label} `{value}`" for value, count in sorted(counts.items()) if count > 1]


def load_screen_index(screens_path: Path) -> tuple[dict[str, set[str]], dict[str, str], list[str]]:
    screens, errors = load_jsonl(screens_path, "screens", required=False)
    screen_elements: dict[str, set[str]] = {}
    screen_domains: dict[str, str] = {}

    for index, screen in enumerate(screens, start=1):
        screen_id = screen.get("screen_id")
        domain = screen.get("domain")
        if not isinstance(screen_id, str) or not screen_id:
            errors.append(f"screens line {index}: missing or invalid screen_id")
            continue
        if not isinstance(domain, str) or not domain:
            errors.append(f"screen {screen_id}: missing or invalid domain")
            continue
        elements = screen.get("elements")
        if not isinstance(elements, list):
            errors.append(f"screen {screen_id}: elements must be a list")
            continue

        element_ids: set[str] = set()
        for element_index, element in enumerate(elements):
            if not isinstance(element, dict):
                errors.append(f"screen {screen_id} element {element_index}: element must be an object")
                continue
            element_id = element.get("element_id")
            if not isinstance(element_id, str) or not element_id:
                errors.append(f"screen {screen_id} element {element_index}: missing or invalid element_id")
                continue
            element_ids.add(element_id)

        screen_elements[screen_id] = element_ids
        screen_domains[screen_id] = domain

    return screen_elements, screen_domains, errors


def validate_references(
    intents: list[dict[str, Any]],
    mappings: list[dict[str, Any]],
    screens_path: Path,
) -> list[str]:
    errors: list[str] = []
    intent_ids = {intent["intent_id"] for intent in intents if isinstance(intent.get("intent_id"), str)}
    mappings_by_intent: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)

    for mapping in mappings:
        mapping_id = mapping.get("mapping_id", "<missing>")
        intent_id = mapping.get("intent_id")
        if intent_id not in intent_ids:
            errors.append(f"mapping {mapping_id}: references missing intent_id `{intent_id}`")
        elif isinstance(intent_id, str):
            mappings_by_intent[intent_id].append(mapping)

        target_element_id = mapping.get("target_element_id")
        distractor_element_ids = mapping.get("distractor_element_ids")
        if isinstance(distractor_element_ids, list) and target_element_id in distractor_element_ids:
            errors.append(f"mapping {mapping_id}: target_element_id must not also appear in distractor_element_ids")

    screen_elements: dict[str, set[str]] = {}
    screen_domains: dict[str, str] = {}
    if screens_path.exists():
        screen_elements, screen_domains, screen_errors = load_screen_index(screens_path)
        errors.extend(screen_errors)

    if screen_elements:
        mapped_screen_ids: set[str] = set()
        for mapping in mappings:
            mapping_id = mapping.get("mapping_id", "<missing>")
            screen_id = mapping.get("screen_id")
            target_element_id = mapping.get("target_element_id")
            distractor_element_ids = mapping.get("distractor_element_ids")

            if screen_id not in screen_elements:
                errors.append(f"mapping {mapping_id}: references missing screen_id `{screen_id}`")
                continue

            mapped_screen_ids.add(screen_id)

            element_ids = screen_elements[screen_id]
            if target_element_id not in element_ids:
                errors.append(
                    f"mapping {mapping_id}: target_element_id `{target_element_id}` does not exist on screen `{screen_id}`"
                )
            if isinstance(distractor_element_ids, list):
                for distractor_id in distractor_element_ids:
                    if distractor_id not in element_ids:
                        errors.append(
                            f"mapping {mapping_id}: distractor_element_id `{distractor_id}` does not exist on screen `{screen_id}`"
                        )

        for screen_id in sorted(set(screen_elements) - mapped_screen_ids):
            errors.append(f"screen {screen_id}: must have at least one intent-target mapping")

        domains_with_screens = set(screen_domains.values())
        for intent in intents:
            intent_id = intent.get("intent_id")
            domain = intent.get("domain")
            if domain in domains_with_screens and intent_id not in mappings_by_intent:
                errors.append(f"intent {intent_id}: must have at least one mapping for existing `{domain}` screens")

    return errors


def validate_intents(
    intents_path: Path,
    mappings_path: Path,
    screens_path: Path,
    intent_schema_path: Path,
    mapping_schema_path: Path,
) -> list[str]:
    errors: list[str] = []

    intent_schema, schema_errors = load_json(intent_schema_path, "intent schema")
    errors.extend(schema_errors)
    mapping_schema, schema_errors = load_json(mapping_schema_path, "mapping schema")
    errors.extend(schema_errors)
    intents, jsonl_errors = load_jsonl(intents_path, "intents")
    errors.extend(jsonl_errors)
    mappings, jsonl_errors = load_jsonl(mappings_path, "intent-screen mappings")
    errors.extend(jsonl_errors)

    if errors:
        return errors

    assert intent_schema is not None
    assert mapping_schema is not None

    try:
        Draft202012Validator.check_schema(intent_schema)
    except Exception as exc:  # jsonschema raises several schema-related exception types.
        errors.append(f"intent schema is invalid: {exc}")
    try:
        Draft202012Validator.check_schema(mapping_schema)
    except Exception as exc:
        errors.append(f"mapping schema is invalid: {exc}")
    if errors:
        return errors

    errors.extend(validate_schema_records(intents, intent_schema, "intent", "intent_id"))
    errors.extend(validate_schema_records(mappings, mapping_schema, "mapping", "mapping_id"))
    errors.extend(duplicate_errors(intents, "intent_id", "intent_id"))
    errors.extend(duplicate_errors(mappings, "mapping_id", "mapping_id"))

    # Cross-file checks only make sense for structurally valid records.
    if not errors:
        errors.extend(validate_references(intents, mappings, screens_path))
    return errors


def main() -> int:
    args = parse_args()
    errors = validate_intents(
        intents_path=args.intents,
        mappings_path=args.mappings,
        screens_path=args.screens,
        intent_schema_path=args.intent_schema,
        mapping_schema_path=args.mapping_schema,
    )

    if errors:
        print("Intent validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Intent validation passed: {args.intents} and {args.mappings}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
