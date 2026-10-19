"""Validate ThaiVoice-GUIBench correction output JSONL."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import jsonschema


METHODS = {
    "A_no_screen_cleanup",
    "B_screen_string_match",
    "C_full_screen_aware_alias",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
    return rows


def validate_records(
    records: list[dict[str, Any]],
    schema: dict[str, Any],
    utterances: dict[str, dict[str, Any]],
    manifest: dict[str, dict[str, Any]],
    screens: dict[str, dict[str, Any]],
    asr_ids: set[str],
) -> list[str]:
    validator = jsonschema.Draft202012Validator(schema)
    errors: list[str] = []
    seen_ids: set[str] = set()
    seen_keys: set[tuple[str, str]] = set()
    for index, record in enumerate(records, 1):
        for error in sorted(validator.iter_errors(record), key=lambda e: e.path):
            errors.append(f"record {index}: schema: {error.message}")
        cid = record.get("correction_id")
        if cid in seen_ids:
            errors.append(f"record {index}: duplicate correction_id {cid}")
        seen_ids.add(cid)
        key = (record.get("asr_id"), record.get("method"))
        if key in seen_keys:
            errors.append(f"record {index}: duplicate correction for asr_id/method {key}")
        seen_keys.add(key)
        if record.get("method") not in METHODS:
            errors.append(f"record {index}: unknown method {record.get('method')}")
        if record.get("asr_id") not in asr_ids:
            errors.append(f"record {index}: unknown asr_id {record.get('asr_id')}")
        if record.get("utterance_id") not in utterances:
            errors.append(f"record {index}: unknown utterance_id {record.get('utterance_id')}")
        if record.get("audio_id") not in manifest:
            errors.append(f"record {index}: unknown audio_id {record.get('audio_id')}")
        if record.get("screen_id") not in screens:
            errors.append(f"record {index}: unknown screen_id {record.get('screen_id')}")
        if record.get("status") == "success" and record.get("error_message"):
            errors.append(f"record {index}: success record has error_message")
        if record.get("status") != "success" and not record.get("error_message"):
            errors.append(f"record {index}: failed/skipped record has empty error_message")
        if record.get("changed") and record.get("input_transcript") == record.get("corrected_transcript"):
            errors.append(f"record {index}: changed=true but transcript is unchanged")
        if not record.get("changed") and record.get("input_transcript") != record.get("corrected_transcript"):
            errors.append(f"record {index}: changed=false but transcript changed")
        if record.get("changed") and not record.get("changes"):
            errors.append(f"record {index}: changed record has empty changes")
        if record.get("method") == "A_no_screen_cleanup" and record.get("matched_screen_label") is not None:
            errors.append(f"record {index}: method A must not have matched_screen_label")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corrections", type=Path, default=Path("data/corrections/corrected_transcripts.jsonl"))
    parser.add_argument("--schema", type=Path, default=Path("schemas/correction_output.schema.json"))
    parser.add_argument("--screens", type=Path, default=Path("data/screens/screens.jsonl"))
    parser.add_argument("--utterances", type=Path, default=Path("data/utterances/utterances_audited.jsonl"))
    parser.add_argument("--manifest", type=Path, default=Path("data/audio/audio_manifest.jsonl"))
    parser.add_argument("--asr-output", type=Path, action="append", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.asr_output is None:
        args.asr_output = [
            Path("data/asr_outputs/whisper_large_v3_local.jsonl"),
            Path("data/asr_outputs/typhoon_asr_api.jsonl"),
        ]
    if not args.corrections.exists():
        raise SystemExit(f"correction file does not exist: {args.corrections}")
    with args.schema.open("r", encoding="utf-8") as f:
        schema = json.load(f)
    records = load_jsonl(args.corrections)
    utterances = {row["utterance_id"]: row for row in load_jsonl(args.utterances)}
    manifest = {row["audio_id"]: row for row in load_jsonl(args.manifest)}
    screens = {row["screen_id"]: row for row in load_jsonl(args.screens)}
    asr_ids: set[str] = set()
    for path in args.asr_output:
        asr_ids.update(row["asr_id"] for row in load_jsonl(path) if row.get("asr_id"))
    errors = validate_records(records, schema, utterances, manifest, screens, asr_ids)
    if errors:
        for error in errors:
            print(error)
        raise SystemExit(1)
    print(f"Correction validation passed: {args.corrections} ({len(records)} records)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
