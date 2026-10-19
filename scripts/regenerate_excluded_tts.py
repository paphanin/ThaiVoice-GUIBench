"""Regenerate replacement candidates for TTS audio flagged by fidelity audit."""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path
from typing import Any

import synthesize_tts


TRUTHY = {"1", "true", "yes", "y"}

EXCLUSION_LOG_COLUMNS = [
    "audio_id",
    "utterance_id",
    "tts_engine",
    "voice_id",
    "text_gold",
    "thai_intelligibility",
    "loanword_fidelity",
    "code_switch_fidelity",
    "overall_naturalness",
    "decision",
    "exclusion_level",
    "reason",
    "replacement_audio_id",
    "notes",
]

ATTEMPT_LOG_COLUMNS = [
    "original_audio_id",
    "replacement_audio_id",
    "utterance_id",
    "tts_engine",
    "voice_id",
    "provider_voice",
    "text_gold",
    "original_audio_path",
    "replacement_audio_path",
    "attempt_number",
    "status",
    "error",
    "duration_ms",
    "created_at",
]

REGEN_AUDIT_COLUMNS = [
    "original_audio_id",
    "replacement_audio_id",
    "utterance_id",
    "engine_id",
    "voice_id",
    "provider_voice",
    "split",
    "tier",
    "text_gold",
    "loanword_spans",
    "replacement_audio_path",
    "thai_intelligibility",
    "english_loanword_fidelity",
    "code_switch_fidelity",
    "overall_naturalness",
    "replacement_decision",
    "issue_tags",
    "auditor_notes",
]

REGEN_AUDIT_BLANK_COLUMNS = [
    "thai_intelligibility",
    "english_loanword_fidelity",
    "code_switch_fidelity",
    "overall_naturalness",
    "replacement_decision",
    "issue_tags",
    "auditor_notes",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/tts.yaml"))
    parser.add_argument("--manifest", type=Path, default=Path("data/audio/audio_manifest.jsonl"))
    parser.add_argument("--audit", type=Path, default=Path("data/audio/audit/tts_fidelity_audit_v1.csv"))
    parser.add_argument("--replacement-root", type=Path, default=Path("data/audio/wav_regen"))
    parser.add_argument("--exclusion-log", type=Path, default=Path("data/audio/audit/tts_exclusion_log.csv"))
    parser.add_argument(
        "--attempt-log",
        type=Path,
        default=Path("data/audio/audit/tts_regeneration_attempts.csv"),
    )
    parser.add_argument(
        "--replacement-audit",
        type=Path,
        default=Path("data/audio/audit/tts_regeneration_audit_v1.csv"),
    )
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--max-retries", type=int, default=0)
    parser.add_argument("--retry-delay-seconds", type=float, default=5.0)
    parser.add_argument("--dry-run", action="store_true")
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


def read_csv(path: Path, label: str) -> list[dict[str, str]]:
    if not path.exists():
        raise ValueError(f"{label} does not exist: {path}")
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise ValueError(f"{label} is missing a header row: {path}")
        return list(reader)


def write_csv(rows: list[dict[str, str]], path: Path, columns: list[str], overwrite: bool) -> None:
    if path.exists() and path.stat().st_size > 0 and not overwrite:
        raise ValueError(f"{path} already exists; pass --overwrite to replace it")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def bool_field(value: str | None) -> bool:
    return str(value or "").strip().lower() in TRUTHY


def require_columns(rows: list[dict[str, str]], columns: list[str], label: str) -> None:
    if not rows:
        raise ValueError(f"{label} contains no rows")
    missing = [column for column in columns if column not in rows[0]]
    if missing:
        raise ValueError(f"{label} missing required columns: {missing}")


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


def selected_flagged_rows(audit_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    require_columns(
        audit_rows,
        [
            "audio_id",
            "utterance_id",
            "engine_id",
            "voice_id",
            "provider_voice",
            "split",
            "tier",
            "text_gold",
            "loanword_spans",
            "audio_path",
            "thai_intelligibility",
            "english_loanword_fidelity",
            "code_switch_fidelity",
            "overall_naturalness",
            "exclude_voice_candidate",
        ],
        "TTS fidelity audit",
    )
    flagged = [row for row in audit_rows if bool_field(row.get("exclude_voice_candidate"))]
    seen: set[str] = set()
    for row in flagged:
        audio_id = row["audio_id"]
        if audio_id in seen:
            raise ValueError(f"duplicate flagged audio_id `{audio_id}` in TTS fidelity audit")
        seen.add(audio_id)
    return flagged


def voice_lookup(config: dict[str, Any]) -> dict[tuple[str, str], tuple[dict[str, Any], dict[str, Any]]]:
    voices = synthesize_tts.selected_voice_configs(config, [], [])
    return {
        (engine_id, voice_id): (engine_config, voice_config)
        for engine_id, voice_id, engine_config, voice_config in voices
    }


def replacement_audio_id(original_audio_id: str, attempt_number: int) -> str:
    if attempt_number < 1:
        raise ValueError("--attempt-number must be at least 1")
    return f"{original_audio_id}__regen{attempt_number:02d}"


def replacement_path(root: Path, engine_id: str, voice_id: str, replacement_id: str) -> Path:
    return root / engine_id / voice_id / f"{replacement_id}.wav"


def reason_for_exclusion(row: dict[str, str]) -> str:
    loanword_score = row.get("english_loanword_fidelity", "").strip()
    naturalness_score = row.get("overall_naturalness", "").strip()
    reasons: list[str] = []
    if loanword_score in {"1", "2"}:
        reasons.append("English loanword fidelity below acceptable threshold")
    if naturalness_score in {"1", "2"}:
        reasons.append("overall naturalness below acceptable threshold")
    if not reasons:
        reasons.append("flagged during TTS fidelity audit")
    return "; ".join(reasons) + "."


def validate_flagged_rows(
    flagged_rows: list[dict[str, str]],
    manifest_by_id: dict[str, dict[str, Any]],
    voices: dict[tuple[str, str], tuple[dict[str, Any], dict[str, Any]]],
) -> None:
    errors: list[str] = []
    for row in flagged_rows:
        audio_id = row["audio_id"]
        manifest_row = manifest_by_id.get(audio_id)
        if manifest_row is None:
            errors.append(f"flagged audio `{audio_id}` is missing from audio manifest")
            continue
        for field in ["utterance_id", "engine_id", "voice_id", "provider_voice", "split"]:
            if str(manifest_row.get(field)) != row[field]:
                errors.append(f"flagged audio `{audio_id}` {field} does not match manifest")
        if str(manifest_row.get("text")) != row["text_gold"]:
            errors.append(f"flagged audio `{audio_id}` text_gold does not match manifest text")
        key = (str(manifest_row.get("engine_id")), str(manifest_row.get("voice_id")))
        if key not in voices:
            errors.append(f"flagged audio `{audio_id}` uses unknown engine/voice `{key[0]}/{key[1]}`")
    if errors:
        raise ValueError("\n".join(errors))


def synthesize_candidate(
    row: dict[str, Any],
    engine_config: dict[str, Any],
    voice_config: dict[str, Any],
) -> bytes:
    provider = engine_config.get("provider")
    if provider == "openai":
        return synthesize_tts.synthesize_openai(row, engine_config, voice_config)
    if provider == "azure":
        return synthesize_tts.synthesize_azure(row, engine_config, voice_config)
    raise ValueError(f"unsupported TTS provider `{provider}` for engine `{row['engine_id']}`")


def synthesize_with_retries(
    row: dict[str, Any],
    engine_config: dict[str, Any],
    voice_config: dict[str, Any],
    max_retries: int,
    retry_delay_seconds: float,
) -> bytes:
    last_error: Exception | None = None
    for attempt_index in range(max_retries + 1):
        try:
            return synthesize_candidate(row, engine_config, voice_config)
        except Exception as exc:  # noqa: BLE001 - preserve provider error for audit log.
            last_error = exc
            if attempt_index < max_retries:
                time.sleep(retry_delay_seconds)
    assert last_error is not None
    raise last_error


def make_candidate_row(
    manifest_row: dict[str, Any],
    replacement_id: str,
    replacement_wav_path: Path,
) -> dict[str, Any]:
    return {
        "audio_id": replacement_id,
        "utterance_id": manifest_row["utterance_id"],
        "split": manifest_row["split"],
        "engine_id": manifest_row["engine_id"],
        "voice_id": manifest_row["voice_id"],
        "provider_voice": manifest_row["provider_voice"],
        "provider_model": manifest_row["provider_model"],
        "text": manifest_row["text"],
        "text_sha256": manifest_row["text_sha256"],
        "audio_path": replacement_wav_path.as_posix(),
        "format": manifest_row["format"],
        "sample_rate_hz": manifest_row["sample_rate_hz"],
        "duration_ms": None,
        "synthesis_mode": manifest_row["synthesis_mode"],
        "created_at": synthesize_tts.utc_now(),
    }


def make_exclusion_row(
    audit_row: dict[str, str],
    replacement_id: str,
    attempt_status: str,
    error: str,
) -> dict[str, str]:
    notes = "Replacement candidate pending human audit." if attempt_status == "success" else error
    if attempt_status == "dry_run_planned":
        notes = "Dry run only; no replacement audio generated."
    return {
        "audio_id": audit_row["audio_id"],
        "utterance_id": audit_row["utterance_id"],
        "tts_engine": audit_row["engine_id"],
        "voice_id": audit_row["voice_id"],
        "text_gold": audit_row["text_gold"],
        "thai_intelligibility": audit_row["thai_intelligibility"],
        "loanword_fidelity": audit_row["english_loanword_fidelity"],
        "code_switch_fidelity": audit_row["code_switch_fidelity"],
        "overall_naturalness": audit_row["overall_naturalness"],
        "decision": "regenerate",
        "exclusion_level": "audio_file",
        "reason": reason_for_exclusion(audit_row),
        "replacement_audio_id": replacement_id if attempt_status == "success" else "",
        "notes": notes,
    }


def make_attempt_row(
    audit_row: dict[str, str],
    manifest_row: dict[str, Any],
    replacement_id: str,
    replacement_wav_path: Path,
    attempt_number: int,
    status: str,
    error: str,
    duration_ms: int | None,
    created_at: str,
) -> dict[str, str]:
    return {
        "original_audio_id": audit_row["audio_id"],
        "replacement_audio_id": replacement_id,
        "utterance_id": audit_row["utterance_id"],
        "tts_engine": audit_row["engine_id"],
        "voice_id": audit_row["voice_id"],
        "provider_voice": audit_row["provider_voice"],
        "text_gold": audit_row["text_gold"],
        "original_audio_path": str(manifest_row["audio_path"]),
        "replacement_audio_path": replacement_wav_path.as_posix(),
        "attempt_number": str(attempt_number),
        "status": status,
        "error": error,
        "duration_ms": "" if duration_ms is None else str(duration_ms),
        "created_at": created_at,
    }


def make_replacement_audit_row(
    audit_row: dict[str, str],
    replacement_id: str,
    replacement_wav_path: Path,
) -> dict[str, str]:
    row = {
        "original_audio_id": audit_row["audio_id"],
        "replacement_audio_id": replacement_id,
        "utterance_id": audit_row["utterance_id"],
        "engine_id": audit_row["engine_id"],
        "voice_id": audit_row["voice_id"],
        "provider_voice": audit_row["provider_voice"],
        "split": audit_row["split"],
        "tier": audit_row["tier"],
        "text_gold": audit_row["text_gold"],
        "loanword_spans": audit_row["loanword_spans"],
        "replacement_audio_path": replacement_wav_path.as_posix(),
    }
    row.update({column: "" for column in REGEN_AUDIT_BLANK_COLUMNS})
    return row


def regenerate_exclusions(
    *,
    config_path: Path,
    manifest_path: Path,
    audit_path: Path,
    replacement_root: Path,
    exclusion_log_path: Path,
    attempt_log_path: Path,
    replacement_audit_path: Path,
    attempt_number: int,
    max_retries: int,
    retry_delay_seconds: float,
    dry_run: bool,
    overwrite: bool,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    config = synthesize_tts.load_config(config_path)
    manifest = load_jsonl(manifest_path, "audio manifest")
    audit_rows = read_csv(audit_path, "TTS fidelity audit")
    flagged_rows = selected_flagged_rows(audit_rows)
    manifest_by_id = index_by_id(manifest, "audio_id", "audio manifest")
    voices = voice_lookup(config)
    validate_flagged_rows(flagged_rows, manifest_by_id, voices)

    if max_retries < 0:
        raise ValueError("--max-retries cannot be negative")
    if retry_delay_seconds < 0:
        raise ValueError("--retry-delay-seconds cannot be negative")

    exclusion_rows: list[dict[str, str]] = []
    attempt_rows: list[dict[str, str]] = []
    replacement_audit_rows: list[dict[str, str]] = []
    existing_replacement_ids: set[str] = set()

    for audit_row in flagged_rows:
        manifest_row = manifest_by_id[audit_row["audio_id"]]
        replacement_id = replacement_audio_id(audit_row["audio_id"], attempt_number)
        if replacement_id in existing_replacement_ids:
            raise ValueError(f"duplicate replacement_audio_id `{replacement_id}`")
        existing_replacement_ids.add(replacement_id)

        replacement_wav_path = replacement_path(
            replacement_root,
            audit_row["engine_id"],
            audit_row["voice_id"],
            replacement_id,
        )
        if replacement_wav_path.exists() and replacement_wav_path.stat().st_size > 0 and not overwrite:
            raise ValueError(f"{replacement_wav_path} already exists; pass --overwrite to replace it")

        candidate = make_candidate_row(manifest_row, replacement_id, replacement_wav_path)
        engine_config, voice_config = voices[(audit_row["engine_id"], audit_row["voice_id"])]
        created_at = synthesize_tts.utc_now()
        duration_ms: int | None = None
        error = ""

        if dry_run:
            status = "dry_run_planned"
        else:
            try:
                replacement_wav_path.parent.mkdir(parents=True, exist_ok=True)
                audio_bytes = synthesize_with_retries(
                    candidate,
                    engine_config,
                    voice_config,
                    max_retries=max_retries,
                    retry_delay_seconds=retry_delay_seconds,
                )
                replacement_wav_path.write_bytes(audio_bytes)
                duration_ms = synthesize_tts.wav_duration_ms(replacement_wav_path)
                status = "success"
            except Exception as exc:  # noqa: BLE001 - keep trying later rows and log provider errors.
                status = "failed_generation"
                error = str(exc)

        exclusion_rows.append(make_exclusion_row(audit_row, replacement_id, status, error))
        attempt_rows.append(
            make_attempt_row(
                audit_row,
                manifest_row,
                replacement_id,
                replacement_wav_path,
                attempt_number,
                status,
                error,
                duration_ms,
                created_at,
            )
        )
        if status == "success":
            replacement_audit_rows.append(
                make_replacement_audit_row(audit_row, replacement_id, replacement_wav_path)
            )

    write_csv(exclusion_rows, exclusion_log_path, EXCLUSION_LOG_COLUMNS, overwrite)
    write_csv(attempt_rows, attempt_log_path, ATTEMPT_LOG_COLUMNS, overwrite)
    write_csv(replacement_audit_rows, replacement_audit_path, REGEN_AUDIT_COLUMNS, overwrite)
    return exclusion_rows, attempt_rows, replacement_audit_rows


def main() -> int:
    args = parse_args()
    try:
        _, attempt_rows, replacement_audit_rows = regenerate_exclusions(
            config_path=args.config,
            manifest_path=args.manifest,
            audit_path=args.audit,
            replacement_root=args.replacement_root,
            exclusion_log_path=args.exclusion_log,
            attempt_log_path=args.attempt_log,
            replacement_audit_path=args.replacement_audit,
            attempt_number=args.attempt_number,
            max_retries=args.max_retries,
            retry_delay_seconds=args.retry_delay_seconds,
            dry_run=args.dry_run,
            overwrite=args.overwrite,
        )
    except (OSError, ValueError) as exc:
        print(f"TTS regeneration failed: {exc}")
        return 1

    status_counts: dict[str, int] = {}
    for row in attempt_rows:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
    print(f"Processed {len(attempt_rows)} flagged TTS audio rows")
    for status, count in sorted(status_counts.items()):
        print(f"- {status}: {count}")
    print(f"Wrote {len(replacement_audit_rows)} replacement audit rows")
    if any(row["status"] == "failed_generation" for row in attempt_rows):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
