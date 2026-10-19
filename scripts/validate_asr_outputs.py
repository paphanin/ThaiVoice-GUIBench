"""Validate ThaiVoice-GUIBench ASR output JSONL files."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--outputs", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=Path("data/audio/audio_manifest.jsonl"))
    parser.add_argument("--utterances", type=Path, default=Path("data/utterances/utterances.jsonl"))
    parser.add_argument("--schema", type=Path, default=Path("schemas/asr_output.schema.json"))
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


def load_jsonl(path: Path, label: str) -> tuple[list[dict[str, Any]], list[str]]:
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
    if not records:
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


def jsonschema_errors(records: list[dict[str, Any]], schema: dict[str, Any]) -> list[str]:
    try:
        from jsonschema import Draft202012Validator  # type: ignore[import-not-found]
    except Exception:
        return basic_schema_errors(records, schema)
    validator = Draft202012Validator(schema)
    errors: list[str] = []
    for index, record in enumerate(records, start=1):
        record_id = record.get("asr_id", f"line_{index}")
        for error in sorted(validator.iter_errors(record), key=lambda item: list(item.path)):
            errors.append(f"ASR {record_id}: {format_error_path(error.path)}: {error.message}")
    return errors


def basic_schema_errors(records: list[dict[str, Any]], schema: dict[str, Any]) -> list[str]:
    required = schema.get("required", [])
    properties = schema.get("properties", {})
    allowed = set(properties)
    errors: list[str] = []
    for index, record in enumerate(records, start=1):
        record_id = record.get("asr_id", f"line_{index}")
        missing = [field for field in required if field not in record]
        for field in missing:
            errors.append(f"ASR {record_id}: {field}: required property is missing")
        extra = sorted(set(record) - allowed)
        if schema.get("additionalProperties") is False and extra:
            errors.append(f"ASR {record_id}: <record>: unexpected properties {extra}")
        for field, spec in properties.items():
            if field not in record:
                continue
            value = record[field]
            expected_type = spec.get("type")
            if not type_matches(value, expected_type):
                errors.append(f"ASR {record_id}: {field}: invalid type")
            if "enum" in spec and value not in spec["enum"]:
                errors.append(f"ASR {record_id}: {field}: invalid value `{value}`")
            if isinstance(value, str) and value == "" and spec.get("minLength", 0) > 0:
                errors.append(f"ASR {record_id}: {field}: must be non-empty")
            if isinstance(value, (int, float)) and "minimum" in spec and value < spec["minimum"]:
                errors.append(f"ASR {record_id}: {field}: must be >= {spec['minimum']}")
    return errors


def type_matches(value: Any, expected_type: Any) -> bool:
    if expected_type is None:
        return True
    expected_types = expected_type if isinstance(expected_type, list) else [expected_type]
    for type_name in expected_types:
        if type_name == "null" and value is None:
            return True
        if type_name == "string" and isinstance(value, str):
            return True
        if type_name == "integer" and isinstance(value, int) and not isinstance(value, bool):
            return True
        if type_name == "number" and isinstance(value, (int, float)) and not isinstance(value, bool):
            return True
        if type_name == "boolean" and isinstance(value, bool):
            return True
        if type_name == "object" and isinstance(value, dict):
            return True
        if type_name == "array" and isinstance(value, list):
            return True
    return False


def duplicate_errors(records: list[dict[str, Any]], field: str) -> list[str]:
    counts = Counter(record.get(field) for record in records if isinstance(record.get(field), str))
    return [f"duplicate {field} `{value}`" for value, count in sorted(counts.items()) if count > 1]


def validate_asr_outputs(
    model: str,
    outputs_path: Path,
    manifest_path: Path,
    utterances_path: Path,
    schema_path: Path,
) -> list[str]:
    errors: list[str] = []
    schema, load_errors = load_json(schema_path, "ASR output schema")
    errors.extend(load_errors)
    records, load_errors = load_jsonl(outputs_path, "ASR outputs")
    errors.extend(load_errors)
    manifest, load_errors = load_jsonl(manifest_path, "audio manifest")
    errors.extend(load_errors)
    utterances, load_errors = load_jsonl(utterances_path, "utterances")
    errors.extend(load_errors)
    if errors:
        return errors
    assert schema is not None

    errors.extend(jsonschema_errors(records, schema))
    errors.extend(duplicate_errors(records, "asr_id"))

    manifest_by_audio_id = {row["audio_id"]: row for row in manifest if isinstance(row.get("audio_id"), str)}
    utterance_ids = {row["utterance_id"] for row in utterances if isinstance(row.get("utterance_id"), str)}
    expected_audio_ids = {row["audio_id"] for row in manifest if isinstance(row.get("audio_id"), str) and include_audio(row)}
    excluded_audio_ids = {row["audio_id"] for row in manifest if isinstance(row.get("audio_id"), str) and not include_audio(row)}

    record_audio_ids: set[str] = set()
    for record in records:
        asr_id = record.get("asr_id", "<missing>")
        audio_id = record.get("audio_id")
        utterance_id = record.get("utterance_id")
        if record.get("asr_model") != model:
            errors.append(f"ASR {asr_id}: asr_model does not match requested model `{model}`")
        if audio_id not in manifest_by_audio_id:
            errors.append(f"ASR {asr_id}: unknown audio_id `{audio_id}`")
        elif audio_id in excluded_audio_ids:
            errors.append(f"ASR {asr_id}: excluded audio_id `{audio_id}` must not be present")
        else:
            record_audio_ids.add(str(audio_id))
            manifest_row = manifest_by_audio_id[str(audio_id)]
            if utterance_id != manifest_row.get("utterance_id"):
                errors.append(f"ASR {asr_id}: utterance_id does not match audio manifest")
        if utterance_id not in utterance_ids:
            errors.append(f"ASR {asr_id}: unknown utterance_id `{utterance_id}`")
        status = record.get("status")
        transcript = str(record.get("transcript", "")).strip()
        error_message = str(record.get("error_message", "")).strip()
        if status == "success" and not transcript:
            errors.append(f"ASR {asr_id}: successful records must have non-empty transcript")
        if status == "failed" and not error_message:
            errors.append(f"ASR {asr_id}: failed records must have non-empty error_message")
        rtf = record.get("rtf")
        if rtf is not None and (not isinstance(rtf, (int, float)) or isinstance(rtf, bool) or rtf < 0):
            errors.append(f"ASR {asr_id}: rtf must be non-negative when available")

    missing = sorted(expected_audio_ids - record_audio_ids)
    if missing:
        errors.append(f"ASR outputs missing expected valid audio_ids {missing[:5]}")
    return errors


def main() -> int:
    args = parse_args()
    errors = validate_asr_outputs(
        model=args.model,
        outputs_path=args.outputs,
        manifest_path=args.manifest,
        utterances_path=args.utterances,
        schema_path=args.schema,
    )
    if errors:
        print("ASR output validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"ASR output validation passed: {args.outputs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
