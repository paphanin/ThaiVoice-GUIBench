"""Synthesize or plan TTS audio for ThaiVoice-GUIBench utterances."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import urllib.error
import urllib.request
import wave
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SPLITS = ("dev", "test")
DEV_TEST_POLICY = "dev_test"
TEST_ONLY_POLICY = "test_only"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/tts.yaml"))
    parser.add_argument("--utterances", type=Path, default=None)
    parser.add_argument("--dev", type=Path, default=None)
    parser.add_argument("--test", type=Path, default=None)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--audio-root", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--engine", action="append", default=[])
    parser.add_argument("--voice", action="append", default=[])
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"TTS config does not exist: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{path} must be JSON-compatible YAML for dependency-free parsing: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise ValueError(f"TTS config must be an object: {path}")
    return data


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"{label} does not exist: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is invalid JSON: {path}:{exc.lineno}:{exc.colno}: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return data


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


def write_jsonl(records: list[dict[str, Any]], path: Path, *, overwrite: bool) -> None:
    if path.exists() and path.stat().st_size > 0 and not overwrite:
        raise ValueError(f"{path} already exists; pass --overwrite to replace it")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def load_existing_cache(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    records = load_jsonl(path, "TTS cache")
    return {
        str(record["audio_id"]): record
        for record in records
        if isinstance(record.get("audio_id"), str)
    }


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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


def resolved_paths(config: dict[str, Any], args: argparse.Namespace) -> dict[str, Path]:
    inputs = config.get("inputs", {})
    outputs = config.get("outputs", {})
    if not isinstance(inputs, dict) or not isinstance(outputs, dict):
        raise ValueError("configs/tts.yaml must contain object-valued inputs and outputs")
    audio_root = args.audio_root or Path(outputs.get("audio_root", "data/audio"))
    return {
        "utterances": args.utterances or Path(inputs.get("utterances", "data/utterances/utterances_audited.jsonl")),
        "dev": args.dev or Path(inputs.get("dev_split", "data/splits/dev.json")),
        "test": args.test or Path(inputs.get("test_split", "data/splits/test.json")),
        "manifest": args.manifest or Path(outputs.get("manifest", audio_root / "audio_manifest.jsonl")),
        "audio_root": audio_root,
        "wav_root": Path(outputs.get("wav_root", audio_root / "wav")),
        "report": Path(outputs.get("report", audio_root / "AUDIO_GENERATION_REPORT.md")),
        "logs_dir": Path(outputs.get("logs_dir", audio_root / "logs")),
        "cache_dir": Path(outputs.get("cache_dir", audio_root / "cache")),
    }


def split_index(dev_split: dict[str, Any], test_split: dict[str, Any]) -> dict[str, str]:
    by_utterance: dict[str, str] = {}
    for split_name, split in [("dev", dev_split), ("test", test_split)]:
        utterance_ids = split.get("utterance_ids")
        if not isinstance(utterance_ids, list):
            raise ValueError(f"{split_name} split missing utterance_ids list")
        for utterance_id in utterance_ids:
            if not isinstance(utterance_id, str):
                raise ValueError(f"{split_name} split has non-string utterance_id")
            if utterance_id in by_utterance:
                raise ValueError(f"utterance_id `{utterance_id}` appears in multiple splits")
            by_utterance[utterance_id] = split_name
    return by_utterance


def selected_voice_configs(
    config: dict[str, Any], engine_filters: list[str], voice_filters: list[str]
) -> list[tuple[str, str, dict[str, Any], dict[str, Any]]]:
    engines = config.get("engines")
    if not isinstance(engines, dict) or not engines:
        raise ValueError("configs/tts.yaml must define at least one engine")
    engine_filter_set = set(engine_filters)
    voice_filter_set = set(voice_filters)
    selected: list[tuple[str, str, dict[str, Any], dict[str, Any]]] = []
    for engine_id, engine_config in engines.items():
        if engine_filter_set and engine_id not in engine_filter_set:
            continue
        if not isinstance(engine_config, dict):
            raise ValueError(f"engine `{engine_id}` config must be an object")
        voices = engine_config.get("voices")
        if not isinstance(voices, dict) or not voices:
            raise ValueError(f"engine `{engine_id}` must define voices")
        for voice_id, voice_config in voices.items():
            qualified_voice = f"{engine_id}/{voice_id}"
            if voice_filter_set and voice_id not in voice_filter_set and qualified_voice not in voice_filter_set:
                continue
            if not isinstance(voice_config, dict):
                raise ValueError(f"voice `{qualified_voice}` config must be an object")
            split_policy = voice_config.get("split_policy")
            if split_policy not in {DEV_TEST_POLICY, TEST_ONLY_POLICY}:
                raise ValueError(f"voice `{qualified_voice}` has invalid split_policy `{split_policy}`")
            selected.append((engine_id, voice_id, engine_config, voice_config))
    if not selected:
        raise ValueError("no voices selected by --engine/--voice filters")
    return selected


def provider_model(engine_config: dict[str, Any]) -> str:
    return str(engine_config.get("model") or engine_config.get("output_format") or "provider_default")


def audio_path(wav_root: Path, engine_id: str, voice_id: str, split: str, utterance_id: str) -> Path:
    return wav_root / engine_id / voice_id / f"{split}__{utterance_id}.wav"


def audio_id(engine_id: str, voice_id: str, split: str, utterance_id: str) -> str:
    return f"{engine_id}__{voice_id}__{split}__{utterance_id}"


def should_use_voice(split: str, voice_config: dict[str, Any]) -> bool:
    if split == "dev":
        return voice_config["split_policy"] == DEV_TEST_POLICY
    if split == "test":
        return voice_config["split_policy"] in {DEV_TEST_POLICY, TEST_ONLY_POLICY}
    raise ValueError(f"unsupported split: {split}")


def scheduled_manifest_rows(
    utterances: list[dict[str, Any]],
    split_by_utterance: dict[str, str],
    voices: list[tuple[str, str, dict[str, Any], dict[str, Any]]],
    wav_root: Path,
    defaults: dict[str, Any],
    *,
    created_at: str,
    dry_run: bool,
) -> list[dict[str, Any]]:
    utterances_by_id = index_by_id(utterances, "utterance_id", "utterances")
    rows: list[dict[str, Any]] = []
    for split in SPLITS:
        split_utterance_ids = [utterance_id for utterance_id, value in split_by_utterance.items() if value == split]
        for utterance_id in split_utterance_ids:
            utterance = utterances_by_id.get(utterance_id)
            if utterance is None:
                raise ValueError(f"split references missing utterance_id `{utterance_id}`")
            text = str(utterance["text_gold"])
            for engine_id, voice_id, engine_config, voice_config in voices:
                if not should_use_voice(split, voice_config):
                    continue
                path = audio_path(wav_root, engine_id, voice_id, split, utterance_id)
                rows.append(
                    {
                        "audio_id": audio_id(engine_id, voice_id, split, utterance_id),
                        "utterance_id": utterance_id,
                        "split": split,
                        "engine_id": engine_id,
                        "voice_id": voice_id,
                        "provider_voice": str(voice_config["provider_voice"]),
                        "provider_model": provider_model(engine_config),
                        "text": text,
                        "text_sha256": sha256_text(text),
                        "audio_path": path.as_posix(),
                        "format": str(defaults.get("format", "wav")),
                        "sample_rate_hz": int(defaults.get("sample_rate_hz", 24000)),
                        "duration_ms": None,
                        "synthesis_mode": "dry_run" if dry_run else "real",
                        "created_at": created_at,
                    }
                )
    return rows


def wav_duration_ms(path: Path) -> int:
    with wave.open(str(path), "rb") as wav_file:
        frames = wav_file.getnframes()
        rate = wav_file.getframerate()
    return round((frames / rate) * 1000)


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"missing required environment variable `{name}` for real TTS synthesis")
    return value


def validate_provider_environment(voices: list[tuple[str, str, dict[str, Any], dict[str, Any]]]) -> None:
    checked: set[tuple[str, str]] = set()
    for engine_id, _, engine_config, _ in voices:
        provider = engine_config.get("provider")
        key = (str(provider), engine_id)
        if key in checked:
            continue
        checked.add(key)
        if provider == "openai":
            require_env(str(engine_config.get("api_key_env", "OPENAI_API_KEY")))
        elif provider == "azure":
            require_env(str(engine_config.get("api_key_env", "AZURE_SPEECH_KEY")))
            endpoint_env = str(engine_config.get("endpoint_env", "AZURE_SPEECH_ENDPOINT"))
            region_env = str(engine_config.get("region_env", "AZURE_SPEECH_REGION"))
            if not os.environ.get(endpoint_env):
                require_env(region_env)


def http_post(url: str, headers: dict[str, str], body: bytes) -> bytes:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ValueError(f"TTS provider request failed with HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"TTS provider request failed: {exc}") from exc


def synthesize_openai(row: dict[str, Any], engine_config: dict[str, Any], voice_config: dict[str, Any]) -> bytes:
    api_key = require_env(str(engine_config.get("api_key_env", "OPENAI_API_KEY")))
    payload: dict[str, Any] = {
        "model": provider_model(engine_config),
        "voice": row["provider_voice"],
        "input": row["text"],
        "response_format": "wav",
    }
    instructions = voice_config.get("instructions")
    if instructions:
        payload["instructions"] = str(instructions)
    return http_post(
        str(engine_config.get("endpoint", "https://api.openai.com/v1/audio/speech")),
        {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json.dumps(payload).encode("utf-8"),
    )


def azure_endpoint(engine_config: dict[str, Any]) -> str:
    endpoint_env = str(engine_config.get("endpoint_env", "AZURE_SPEECH_ENDPOINT"))
    endpoint = os.environ.get(endpoint_env)
    if endpoint:
        return endpoint.rstrip("/") + "/cognitiveservices/v1" if not endpoint.endswith("/v1") else endpoint
    region = require_env(str(engine_config.get("region_env", "AZURE_SPEECH_REGION")))
    return f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"


def synthesize_azure(row: dict[str, Any], engine_config: dict[str, Any], voice_config: dict[str, Any]) -> bytes:
    api_key = require_env(str(engine_config.get("api_key_env", "AZURE_SPEECH_KEY")))
    language = str(engine_config.get("language", "th-TH"))
    voice = str(voice_config["provider_voice"])
    ssml = (
        f"<speak version='1.0' xml:lang='{language}'>"
        f"<voice xml:lang='{language}' name='{html.escape(voice)}'>"
        f"{html.escape(row['text'])}"
        "</voice></speak>"
    )
    return http_post(
        azure_endpoint(engine_config),
        {
            "Ocp-Apim-Subscription-Key": api_key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": str(engine_config.get("output_format", "riff-24khz-16bit-mono-pcm")),
            "User-Agent": "ThaiVoice-GUIBench",
        },
        ssml.encode("utf-8"),
    )


def synthesize_real_audio(
    rows: list[dict[str, Any]],
    voices: list[tuple[str, str, dict[str, Any], dict[str, Any]]],
    *,
    skip_existing: bool,
    previous_cache: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    previous_cache = previous_cache or {}
    voice_lookup = {
        (engine_id, voice_id): (engine_config, voice_config)
        for engine_id, voice_id, engine_config, voice_config in voices
    }
    log_rows: list[dict[str, Any]] = []
    for row in rows:
        path = Path(row["audio_path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        cached = previous_cache.get(row["audio_id"])
        cache_hash_matches = cached is not None and cached.get("text_sha256") == row["text_sha256"]
        if path.exists() and path.stat().st_size > 0 and skip_existing and cache_hash_matches:
            row["duration_ms"] = wav_duration_ms(path)
            log_rows.append({"audio_id": row["audio_id"], "status": "skipped_existing", "audio_path": row["audio_path"]})
            continue
        engine_config, voice_config = voice_lookup[(row["engine_id"], row["voice_id"])]
        provider = engine_config.get("provider")
        if provider == "openai":
            audio_bytes = synthesize_openai(row, engine_config, voice_config)
        elif provider == "azure":
            audio_bytes = synthesize_azure(row, engine_config, voice_config)
        else:
            raise ValueError(f"unsupported TTS provider `{provider}` for engine `{row['engine_id']}`")
        path.write_bytes(audio_bytes)
        row["duration_ms"] = wav_duration_ms(path)
        log_rows.append({"audio_id": row["audio_id"], "status": "synthesized", "audio_path": row["audio_path"]})
    return log_rows


def prepare_directories(paths: dict[str, Path], voices: list[tuple[str, str, dict[str, Any], dict[str, Any]]]) -> None:
    for key in ["wav_root", "logs_dir", "cache_dir"]:
        paths[key].mkdir(parents=True, exist_ok=True)
    for engine_id, voice_id, _, _ in voices:
        (paths["wav_root"] / engine_id / voice_id).mkdir(parents=True, exist_ok=True)


def write_cache(records: list[dict[str, Any]], path: Path, *, overwrite: bool) -> None:
    cache_rows = [
        {
            "audio_id": record["audio_id"],
            "text_sha256": record["text_sha256"],
            "audio_path": record["audio_path"],
            "synthesis_mode": record["synthesis_mode"],
        }
        for record in records
    ]
    write_jsonl(cache_rows, path, overwrite=overwrite)


def write_report(records: list[dict[str, Any]], paths: dict[str, Path], *, dry_run: bool, overwrite: bool) -> None:
    report_path = paths["report"]
    if report_path.exists() and report_path.stat().st_size > 0 and not overwrite:
        raise ValueError(f"{report_path} already exists; pass --overwrite to replace it")
    split_counts = Counter(record["split"] for record in records)
    engine_counts = Counter(record["engine_id"] for record in records)
    voice_counts = Counter(f"{record['engine_id']}/{record['voice_id']}" for record in records)
    test_only_voices = sorted(
        voice for voice in set(voice_counts) if not any(record["split"] == "dev" and f"{record['engine_id']}/{record['voice_id']}" == voice for record in records)
    )
    lines = [
        "# Audio Generation Report",
        "",
        f"- generated_at: {utc_now()}",
        f"- synthesis_mode: {'dry_run' if dry_run else 'real'}",
        f"- manifest_rows: {len(records)}",
        f"- manifest: `{paths['manifest']}`",
        "",
        "## Counts By Split",
        "",
    ]
    for split in SPLITS:
        lines.append(f"- {split}: {split_counts.get(split, 0)}")
    lines.extend(["", "## Counts By Engine", ""])
    for engine_id, count in sorted(engine_counts.items()):
        lines.append(f"- {engine_id}: {count}")
    lines.extend(["", "## Counts By Voice", ""])
    for voice, count in sorted(voice_counts.items()):
        lines.append(f"- {voice}: {count}")
    lines.extend(["", "## Test-Only Voices", ""])
    if test_only_voices:
        for voice in test_only_voices:
            lines.append(f"- {voice}")
    else:
        lines.append("- none")
    paths["report"].parent.mkdir(parents=True, exist_ok=True)
    paths["report"].write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_audio_manifest(
    config_path: Path,
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    config = load_config(config_path)
    paths = resolved_paths(config, args)
    defaults = config.get("defaults", {})
    if not isinstance(defaults, dict):
        raise ValueError("configs/tts.yaml defaults must be an object")
    utterances = load_jsonl(paths["utterances"], "utterances")
    dev_split = load_json(paths["dev"], "dev split")
    test_split = load_json(paths["test"], "test split")
    split_by_utterance = split_index(dev_split, test_split)
    voices = selected_voice_configs(config, args.engine, args.voice)
    prepare_directories(paths, voices)
    if not args.dry_run:
        validate_provider_environment(voices)
    created_at = utc_now()
    rows = scheduled_manifest_rows(
        utterances,
        split_by_utterance,
        voices,
        paths["wav_root"],
        defaults,
        created_at=created_at,
        dry_run=args.dry_run,
    )
    if args.dry_run:
        log_rows = [
            {"audio_id": record["audio_id"], "status": "dry_run_planned", "audio_path": record["audio_path"]}
            for record in rows
        ]
    else:
        cache_path = paths["cache_dir"] / "tts_cache_index.jsonl"
        previous_cache = load_existing_cache(cache_path)
        log_rows = synthesize_real_audio(
            rows,
            voices,
            skip_existing=args.skip_existing,
            previous_cache=previous_cache,
        )

    write_jsonl(rows, paths["manifest"], overwrite=args.overwrite)
    write_jsonl(log_rows, paths["logs_dir"] / "tts_generation_log.jsonl", overwrite=args.overwrite)
    write_cache(rows, paths["cache_dir"] / "tts_cache_index.jsonl", overwrite=args.overwrite)
    write_report(rows, paths, dry_run=args.dry_run, overwrite=args.overwrite)
    return rows


def main() -> int:
    args = parse_args()
    try:
        rows = generate_audio_manifest(args.config, args)
    except (OSError, ValueError) as exc:
        print(f"TTS synthesis failed: {exc}")
        return 1
    print(f"Wrote {len(rows)} audio manifest rows to {args.manifest or 'data/audio/audio_manifest.jsonl'}")
    mode = "dry-run" if args.dry_run else "real"
    print(f"TTS mode: {mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
