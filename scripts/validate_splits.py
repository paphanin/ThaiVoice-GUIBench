"""Validate ThaiVoice-GUIBench dev/test split files."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


TIERS = ("T1_verbatim", "T2_paraphrase", "T3_intent", "T4_visual_positional")
PROFILE_COUNTS = {
    "provisional20": (5, 15, 15),
    "final": (15, 50, 65),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev", type=Path, default=Path("data/splits/dev.json"))
    parser.add_argument("--test", type=Path, default=Path("data/splits/test.json"))
    parser.add_argument("--screens", type=Path, default=Path("data/screens/screens.jsonl"))
    parser.add_argument("--mappings", type=Path, default=Path("data/intents/intent_screen_targets.jsonl"))
    parser.add_argument("--utterances", type=Path, default=Path("data/utterances/utterances_audited.jsonl"))
    parser.add_argument("--audio-manifest", type=Path, default=Path("data/audio/audio_manifest.jsonl"))
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


def load_jsonl(path: Path, label: str, *, allow_empty: bool = False) -> tuple[list[dict[str, Any]], list[str]]:
    if not path.exists():
        if allow_empty:
            return [], []
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
                errors.append(f"{label}:{line_number}: expected JSON object")
                continue
            records.append(record)
    if not records and not allow_empty:
        errors.append(f"{label} contains no records: {path}")
    return records, errors


def index_by_id(records: list[dict[str, Any]], field: str, label: str) -> tuple[dict[str, dict[str, Any]], list[str]]:
    indexed: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for index, record in enumerate(records, start=1):
        value = record.get(field)
        if not isinstance(value, str) or not value:
            errors.append(f"{label}:{index}: missing or invalid {field}")
            continue
        if value in indexed:
            errors.append(f"duplicate {field} `{value}` in {label}")
            continue
        indexed[value] = record
    return indexed, errors


def require_string_list(split: dict[str, Any], field: str, split_name: str) -> tuple[set[str], list[str]]:
    value = split.get(field)
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        return set(), [f"{split_name}: {field} must be a list of nonempty strings"]
    if len(value) != len(set(value)):
        return set(value), [f"{split_name}: {field} contains duplicates"]
    return set(value), []


def expected_counts(
    screen_ids: set[str],
    screens_by_id: dict[str, dict[str, Any]],
    mappings: list[dict[str, Any]],
    utterances: list[dict[str, Any]],
) -> dict[str, Any]:
    mapping_ids = {mapping["mapping_id"] for mapping in mappings if mapping["screen_id"] in screen_ids}
    split_utterances = [utterance for utterance in utterances if utterance["mapping_id"] in mapping_ids]
    domains = Counter(str(screens_by_id[screen_id].get("domain", "unknown")) for screen_id in screen_ids)
    tiers = Counter(str(utterance.get("tier", "unknown")) for utterance in split_utterances)
    return {
        "screens": len(screen_ids),
        "intents": len({mapping["intent_id"] for mapping in mappings if mapping["screen_id"] in screen_ids}),
        "mappings": len(mapping_ids),
        "utterances": len(split_utterances),
        "domains": dict(sorted(domains.items())),
        "tiers": {tier: tiers.get(tier, 0) for tier in TIERS},
    }


def validate_single_split(
    split: dict[str, Any],
    split_name: str,
    screens_by_id: dict[str, dict[str, Any]],
    mappings: list[dict[str, Any]],
    mappings_by_id: dict[str, dict[str, Any]],
    utterances: list[dict[str, Any]],
    utterances_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    if split.get("split_name") != split_name:
        errors.append(f"{split_name}: split_name must be `{split_name}`")
    if split.get("correction_threshold_source") != "dev_only":
        errors.append(f"{split_name}: correction_threshold_source must be `dev_only`")

    screen_ids, field_errors = require_string_list(split, "screen_ids", split_name)
    errors.extend(field_errors)
    mapping_ids, field_errors = require_string_list(split, "mapping_ids", split_name)
    errors.extend(field_errors)
    intent_ids, field_errors = require_string_list(split, "intent_ids", split_name)
    errors.extend(field_errors)
    utterance_ids, field_errors = require_string_list(split, "utterance_ids", split_name)
    errors.extend(field_errors)
    if errors:
        return errors

    missing_screens = sorted(screen_ids - set(screens_by_id))
    if missing_screens:
        errors.append(f"{split_name}: unknown screen_ids {missing_screens}")

    expected_mapping_ids = {mapping["mapping_id"] for mapping in mappings if mapping["screen_id"] in screen_ids}
    if mapping_ids != expected_mapping_ids:
        errors.append(f"{split_name}: mapping_ids do not match mappings for split screens")
    for mapping_id in mapping_ids:
        mapping = mappings_by_id.get(mapping_id)
        if mapping is None:
            errors.append(f"{split_name}: unknown mapping_id `{mapping_id}`")
        elif mapping["screen_id"] not in screen_ids:
            errors.append(f"{split_name}: mapping `{mapping_id}` belongs to screen `{mapping['screen_id']}` outside split")

    expected_intent_ids = {
        mapping["intent_id"] for mapping in mappings if mapping["mapping_id"] in expected_mapping_ids
    }
    if intent_ids != expected_intent_ids:
        errors.append(f"{split_name}: intent_ids do not match mappings for split screens")

    expected_utterance_ids = {
        utterance["utterance_id"] for utterance in utterances if utterance["mapping_id"] in expected_mapping_ids
    }
    if utterance_ids != expected_utterance_ids:
        errors.append(f"{split_name}: utterance_ids do not match utterances for split mappings")
    for utterance_id in utterance_ids:
        utterance = utterances_by_id.get(utterance_id)
        if utterance is None:
            errors.append(f"{split_name}: unknown utterance_id `{utterance_id}`")
        elif utterance["mapping_id"] not in mapping_ids:
            errors.append(
                f"{split_name}: utterance `{utterance_id}` belongs to mapping `{utterance['mapping_id']}` outside split"
            )

    counts = split.get("counts")
    expected = expected_counts(screen_ids, screens_by_id, mappings, utterances)
    if counts != expected:
        errors.append(f"{split_name}: counts do not match source data")

    return errors


def validate_profile_counts(dev_split: dict[str, Any], test_split: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    profile = dev_split.get("profile")
    if profile != test_split.get("profile"):
        errors.append("dev/test profiles must match")
        return errors
    if profile not in PROFILE_COUNTS:
        errors.append(f"unknown split profile `{profile}`")
        return errors
    dev_expected, test_min, test_max = PROFILE_COUNTS[profile]
    dev_count = len(dev_split.get("screen_ids", []))
    test_count = len(test_split.get("screen_ids", []))
    if dev_count != dev_expected:
        errors.append(f"{profile}: dev screen count must be {dev_expected}; found {dev_count}")
    if test_count < test_min or test_count > test_max:
        errors.append(f"{profile}: test screen count must be between {test_min} and {test_max}; found {test_count}")
    expected_provisional = profile == "provisional20"
    if dev_split.get("provisional") != expected_provisional or test_split.get("provisional") != expected_provisional:
        errors.append(f"{profile}: provisional flag is incorrect")
    return errors


def validate_voice_policy(
    dev_split: dict[str, Any],
    test_split: dict[str, Any],
    audio_rows: list[dict[str, Any]],
) -> list[str]:
    if not audio_rows:
        return []
    if not any(manifest_voice_key(row) for row in audio_rows):
        return []
    dev_utterance_ids = set(dev_split.get("utterance_ids", []))
    test_utterance_ids = set(test_split.get("utterance_ids", []))
    dev_voices = {
        manifest_voice_key(row)
        for row in audio_rows
        if manifest_voice_key(row) and row.get("utterance_id") in dev_utterance_ids
    }
    test_voices = {
        manifest_voice_key(row)
        for row in audio_rows
        if manifest_voice_key(row) and row.get("utterance_id") in test_utterance_ids
    }
    test_only = sorted(test_voices - dev_voices)
    if not test_only:
        return ["audio manifest has voice_id metadata, but no voice appears only in test"]
    for split_name, split in [("dev", dev_split), ("test", test_split)]:
        policy = split.get("voice_policy")
        if not isinstance(policy, dict):
            return [f"{split_name}: voice_policy must be an object"]
        if policy.get("status") != "satisfied":
            return [f"{split_name}: voice_policy.status must be `satisfied` when voice metadata exists"]
        if sorted(policy.get("test_only_voice_ids", [])) != test_only:
            return [f"{split_name}: voice_policy.test_only_voice_ids does not match audio manifest"]
    return []


def manifest_voice_key(row: dict[str, Any]) -> str | None:
    voice_id = row.get("voice_id")
    if not isinstance(voice_id, str) or not voice_id:
        return None
    engine_id = row.get("engine_id")
    if isinstance(engine_id, str) and engine_id:
        return f"{engine_id}/{voice_id}"
    return voice_id


def validate_splits(
    dev_path: Path,
    test_path: Path,
    screens_path: Path,
    mappings_path: Path,
    utterances_path: Path,
    audio_manifest_path: Path,
) -> list[str]:
    errors: list[str] = []
    dev_split, load_errors = load_json(dev_path, "dev split")
    errors.extend(load_errors)
    test_split, load_errors = load_json(test_path, "test split")
    errors.extend(load_errors)
    screens, load_errors = load_jsonl(screens_path, "screens")
    errors.extend(load_errors)
    mappings, load_errors = load_jsonl(mappings_path, "intent-screen mappings")
    errors.extend(load_errors)
    utterances, load_errors = load_jsonl(utterances_path, "utterances")
    errors.extend(load_errors)
    audio_rows, load_errors = load_jsonl(audio_manifest_path, "audio manifest", allow_empty=True)
    errors.extend(load_errors)
    if errors:
        return errors

    assert dev_split is not None
    assert test_split is not None
    screens_by_id, index_errors = index_by_id(screens, "screen_id", "screens")
    errors.extend(index_errors)
    mappings_by_id, index_errors = index_by_id(mappings, "mapping_id", "intent-screen mappings")
    errors.extend(index_errors)
    utterances_by_id, index_errors = index_by_id(utterances, "utterance_id", "utterances")
    errors.extend(index_errors)
    if errors:
        return errors

    errors.extend(validate_profile_counts(dev_split, test_split))
    errors.extend(
        validate_single_split(
            dev_split, "dev", screens_by_id, mappings, mappings_by_id, utterances, utterances_by_id
        )
    )
    errors.extend(
        validate_single_split(
            test_split, "test", screens_by_id, mappings, mappings_by_id, utterances, utterances_by_id
        )
    )

    dev_screens = set(dev_split.get("screen_ids", []))
    test_screens = set(test_split.get("screen_ids", []))
    screen_overlap = sorted(dev_screens & test_screens)
    if screen_overlap:
        errors.append(f"dev/test screen overlap is not allowed: {screen_overlap}")
    if dev_screens | test_screens != set(screens_by_id):
        errors.append("dev/test screen_ids must cover all source screens for the selected profile")

    dev_intents = set(dev_split.get("intent_ids", []))
    test_intents = set(test_split.get("intent_ids", []))
    intent_overlap = sorted(dev_intents & test_intents)
    if intent_overlap:
        errors.append(f"dev/test intent overlap is not allowed when avoidable: {intent_overlap}")

    errors.extend(validate_voice_policy(dev_split, test_split, audio_rows))
    return errors


def main() -> int:
    args = parse_args()
    errors = validate_splits(
        dev_path=args.dev,
        test_path=args.test,
        screens_path=args.screens,
        mappings_path=args.mappings,
        utterances_path=args.utterances,
        audio_manifest_path=args.audio_manifest,
    )
    if errors:
        print("Split validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Split validation passed: {args.dev} and {args.test}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
