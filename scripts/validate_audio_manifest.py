"""Validate ThaiVoice-GUIBench TTS audio manifests."""

from __future__ import annotations

import argparse
import json
import wave
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


DEV_TEST_POLICY = "dev_test"
TEST_ONLY_POLICY = "test_only"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("data/audio/audio_manifest.jsonl"))
    parser.add_argument("--schema", type=Path, default=Path("schemas/audio_manifest.schema.json"))
    parser.add_argument("--utterances", type=Path, default=Path("data/utterances/utterances_audited.jsonl"))
    parser.add_argument("--dev", type=Path, default=Path("data/splits/dev.json"))
    parser.add_argument("--test", type=Path, default=Path("data/splits/test.json"))
    parser.add_argument("--config", type=Path, default=Path("configs/tts.yaml"))
    parser.add_argument("--manifest-only", action="store_true")
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
                errors.append(f"{label}:{line_number}: expected JSON object")
                continue
            records.append(record)
    if not records:
        errors.append(f"{label} contains no records: {path}")
    return records, errors


def load_config(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    config, errors = load_json(path, "TTS config")
    if errors:
        return None, [
            error.replace("is invalid JSON", "must be JSON-compatible YAML and is invalid JSON")
            for error in errors
        ]
    return config, []


def split_index(dev_split: dict[str, Any], test_split: dict[str, Any]) -> tuple[dict[str, str], list[str]]:
    errors: list[str] = []
    by_utterance: dict[str, str] = {}
    for split_name, split in [("dev", dev_split), ("test", test_split)]:
        utterance_ids = split.get("utterance_ids")
        if not isinstance(utterance_ids, list):
            errors.append(f"{split_name} split missing utterance_ids list")
            continue
        for utterance_id in utterance_ids:
            if not isinstance(utterance_id, str):
                errors.append(f"{split_name} split has non-string utterance_id")
                continue
            if utterance_id in by_utterance:
                errors.append(f"utterance_id `{utterance_id}` appears in multiple splits")
            by_utterance[utterance_id] = split_name
    return by_utterance, errors


def voice_configs(config: dict[str, Any]) -> tuple[dict[tuple[str, str], dict[str, Any]], list[str]]:
    engines = config.get("engines")
    if not isinstance(engines, dict) or not engines:
        return {}, ["TTS config must define engines"]
    voices: dict[tuple[str, str], dict[str, Any]] = {}
    errors: list[str] = []
    for engine_id, engine_config in engines.items():
        if not isinstance(engine_config, dict):
            errors.append(f"engine `{engine_id}` config must be an object")
            continue
        engine_voices = engine_config.get("voices")
        if not isinstance(engine_voices, dict) or not engine_voices:
            errors.append(f"engine `{engine_id}` must define voices")
            continue
        for voice_id, voice_config in engine_voices.items():
            if not isinstance(voice_config, dict):
                errors.append(f"voice `{engine_id}/{voice_id}` config must be an object")
                continue
            split_policy = voice_config.get("split_policy")
            if split_policy not in {DEV_TEST_POLICY, TEST_ONLY_POLICY}:
                errors.append(f"voice `{engine_id}/{voice_id}` has invalid split_policy `{split_policy}`")
            merged = dict(voice_config)
            merged["provider_model"] = str(engine_config.get("model") or engine_config.get("output_format") or "provider_default")
            voices[(engine_id, voice_id)] = merged
    return voices, errors


def expected_audio_ids(split_by_utterance: dict[str, str], voices: dict[tuple[str, str], dict[str, Any]]) -> set[str]:
    expected: set[str] = set()
    for utterance_id, split in split_by_utterance.items():
        for (engine_id, voice_id), voice_config in voices.items():
            policy = voice_config["split_policy"]
            if split == "dev" and policy != DEV_TEST_POLICY:
                continue
            expected.add(f"{engine_id}__{voice_id}__{split}__{utterance_id}")
    return expected


def audio_slot_key(record: dict[str, Any]) -> tuple[str, str, str]:
    return (str(record["utterance_id"]), str(record["engine_id"]), str(record["voice_id"]))


def duplicate_slot_errors(records: list[dict[str, Any]]) -> list[str]:
    counts = Counter(audio_slot_key(record) for record in records)
    return [f"duplicate audio slot `{value}`" for value, count in sorted(counts.items()) if count > 1]


def duplicate_errors(records: list[dict[str, Any]], field: str) -> list[str]:
    counts = Counter(record.get(field) for record in records if isinstance(record.get(field), str))
    return [f"duplicate {field} `{value}`" for value, count in sorted(counts.items()) if count > 1]


def format_error_path(error_path: Any) -> str:
    parts = [str(part) for part in error_path]
    return ".".join(parts) if parts else "<record>"


def schema_errors(records: list[dict[str, Any]], schema: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(schema)
    errors: list[str] = []
    for index, record in enumerate(records, start=1):
        record_id = record.get("audio_id", f"line_{index}")
        for error in sorted(validator.iter_errors(record), key=lambda item: list(item.path)):
            errors.append(f"audio {record_id}: {format_error_path(error.path)}: {error.message}")
    return errors


def validate_files(records: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for record in records:
        if record.get("generation_status") == "failed_generation":
            continue
        path = Path(record["audio_path"])
        if not path.exists():
            errors.append(f"audio {record['audio_id']}: audio_path does not exist: {path}")
            continue
        if path.stat().st_size == 0:
            errors.append(f"audio {record['audio_id']}: audio_path is empty: {path}")
            continue
        try:
            with wave.open(str(path), "rb") as wav_file:
                duration_ms = round((wav_file.getnframes() / wav_file.getframerate()) * 1000)
        except wave.Error as exc:
            errors.append(f"audio {record['audio_id']}: invalid WAV file: {exc}")
            continue
        if record.get("duration_ms") != duration_ms:
            errors.append(f"audio {record['audio_id']}: duration_ms does not match WAV file")
    return errors


def validate_audio_manifest(
    manifest_path: Path,
    schema_path: Path,
    utterances_path: Path,
    dev_path: Path,
    test_path: Path,
    config_path: Path,
    manifest_only: bool,
) -> list[str]:
    errors: list[str] = []
    schema, load_errors = load_json(schema_path, "audio manifest schema")
    errors.extend(load_errors)
    manifest, load_errors = load_jsonl(manifest_path, "audio manifest")
    errors.extend(load_errors)
    utterances, load_errors = load_jsonl(utterances_path, "utterances")
    errors.extend(load_errors)
    dev_split, load_errors = load_json(dev_path, "dev split")
    errors.extend(load_errors)
    test_split, load_errors = load_json(test_path, "test split")
    errors.extend(load_errors)
    config, load_errors = load_config(config_path)
    errors.extend(load_errors)
    if errors:
        return errors

    assert schema is not None
    assert dev_split is not None
    assert test_split is not None
    assert config is not None
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        return [f"audio manifest schema is invalid: {exc}"]

    errors.extend(schema_errors(manifest, schema))
    errors.extend(duplicate_errors(manifest, "audio_id"))
    errors.extend(duplicate_errors(manifest, "audio_path"))
    errors.extend(duplicate_slot_errors(manifest))
    if errors:
        return errors

    utterances_by_id = {utterance["utterance_id"]: utterance for utterance in utterances}
    split_by_utterance, split_errors = split_index(dev_split, test_split)
    errors.extend(split_errors)
    voices, voice_errors = voice_configs(config)
    errors.extend(voice_errors)
    outputs = config.get("outputs", {})
    wav_root = Path(outputs.get("wav_root", "data/audio/wav")) if isinstance(outputs, dict) else Path("data/audio/wav")
    if errors:
        return errors

    manifest_audio_ids = {record["audio_id"] for record in manifest}
    expected_ids = expected_audio_ids(split_by_utterance, voices)
    if manifest_audio_ids != expected_ids:
        missing = sorted(expected_ids - manifest_audio_ids)
        extra = sorted(manifest_audio_ids - expected_ids)
        if missing:
            errors.append(f"audio manifest missing expected audio_ids {missing[:5]}")
        if extra:
            errors.append(f"audio manifest contains unexpected audio_ids {extra[:5]}")

    voice_splits: dict[tuple[str, str], set[str]] = {}
    for record in manifest:
        utterance = utterances_by_id.get(record["utterance_id"])
        if utterance is None:
            errors.append(f"audio {record['audio_id']}: unknown utterance_id `{record['utterance_id']}`")
            continue
        expected_split = split_by_utterance.get(record["utterance_id"])
        if record["split"] != expected_split:
            errors.append(f"audio {record['audio_id']}: split does not match split files")
        if record["text"] != utterance["text_gold"]:
            errors.append(f"audio {record['audio_id']}: text does not match audited utterance text_gold")
        if record["text_sha256"] != __import__("hashlib").sha256(record["text"].encode("utf-8")).hexdigest():
            errors.append(f"audio {record['audio_id']}: text_sha256 does not match text")
        key = (record["engine_id"], record["voice_id"])
        voice_config = voices.get(key)
        if voice_config is None:
            errors.append(f"audio {record['audio_id']}: unknown engine/voice `{record['engine_id']}/{record['voice_id']}`")
            continue
        if record["provider_voice"] != voice_config.get("provider_voice"):
            errors.append(f"audio {record['audio_id']}: provider_voice does not match config")
        if record["provider_model"] != voice_config.get("provider_model"):
            errors.append(f"audio {record['audio_id']}: provider_model does not match config")
        expected_path = wav_root / record["engine_id"] / record["voice_id"] / f"{record['split']}__{record['utterance_id']}.wav"
        if record["audio_path"] != expected_path.as_posix():
            errors.append(f"audio {record['audio_id']}: audio_path does not match repo convention")
        voice_splits.setdefault(key, set()).add(record["split"])

    test_only_voices = [key for key, voice_config in voices.items() if voice_config["split_policy"] == TEST_ONLY_POLICY]
    if not test_only_voices:
        errors.append("TTS config must define at least one test_only voice")
    for key in test_only_voices:
        splits = voice_splits.get(key, set())
        if "dev" in splits:
            errors.append(f"test_only voice `{key[0]}/{key[1]}` appears in dev")
        if "test" not in splits:
            errors.append(f"test_only voice `{key[0]}/{key[1]}` does not appear in test")

    if not manifest_only:
        errors.extend(validate_files(manifest))
    return errors


def main() -> int:
    args = parse_args()
    errors = validate_audio_manifest(
        manifest_path=args.manifest,
        schema_path=args.schema,
        utterances_path=args.utterances,
        dev_path=args.dev,
        test_path=args.test,
        config_path=args.config,
        manifest_only=args.manifest_only,
    )
    if errors:
        print("Audio manifest validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    mode = "manifest-only" if args.manifest_only else "with audio files"
    print(f"Audio manifest validation passed ({mode}): {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
