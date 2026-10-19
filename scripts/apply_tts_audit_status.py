"""Apply TTS fidelity audit inclusion flags to the audio manifest."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


REQUIRED_EXCLUSION_COLUMNS = ["audio_id", "decision", "exclusion_level"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("data/audio/audio_manifest.jsonl"))
    parser.add_argument(
        "--exclusion-log",
        type=Path,
        default=Path("data/audio/audit/tts_exclusion_log.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output manifest path. Defaults to updating --manifest in place.",
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def clean(value: str | None) -> str:
    return (value or "").strip()


def load_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    if not path.exists():
        raise ValueError(f"{label} does not exist: {path}")
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as file:
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


def require_columns(fieldnames: list[str] | None, path: Path) -> None:
    if fieldnames is None:
        raise ValueError(f"exclusion CSV has no header: {path}")
    missing = [column for column in REQUIRED_EXCLUSION_COLUMNS if column not in fieldnames]
    if missing:
        raise ValueError(f"exclusion CSV missing required columns {missing}: {path}")


def load_excluded_audio_ids(path: Path) -> set[str]:
    if not path.exists():
        raise ValueError(f"exclusion CSV does not exist: {path}")
    excluded: set[str] = set()
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        require_columns(reader.fieldnames, path)
        for line_number, row in enumerate(reader, start=2):
            audio_id = clean(row.get("audio_id"))
            if not audio_id:
                raise ValueError(f"exclusion CSV:{line_number}: missing audio_id")
            if audio_id in excluded:
                raise ValueError(f"duplicate excluded audio_id `{audio_id}`")
            excluded.add(audio_id)
    return excluded


def validate_manifest_audio_ids(records: list[dict[str, Any]]) -> set[str]:
    audio_ids: set[str] = set()
    for index, record in enumerate(records, start=1):
        audio_id = record.get("audio_id")
        if not isinstance(audio_id, str) or not audio_id:
            raise ValueError(f"manifest:{index}: missing or invalid audio_id")
        if audio_id in audio_ids:
            raise ValueError(f"duplicate manifest audio_id `{audio_id}`")
        audio_ids.add(audio_id)
    return audio_ids


def apply_tts_audit_status(
    manifest_path: Path,
    exclusion_log_path: Path,
    output_path: Path,
    overwrite: bool,
) -> tuple[int, int, int]:
    manifest = load_jsonl(manifest_path, "audio manifest")
    manifest_audio_ids = validate_manifest_audio_ids(manifest)
    excluded_audio_ids = load_excluded_audio_ids(exclusion_log_path)
    unknown_exclusions = sorted(excluded_audio_ids - manifest_audio_ids)
    if unknown_exclusions:
        raise ValueError(f"exclusion CSV contains unknown audio_ids {unknown_exclusions[:5]}")

    included_count = 0
    excluded_count = 0
    updated: list[dict[str, Any]] = []
    for record in manifest:
        output_record = dict(record)
        include = record["audio_id"] not in excluded_audio_ids
        output_record["include_in_experiments"] = include
        if include:
            included_count += 1
        else:
            excluded_count += 1
        updated.append(output_record)

    if output_path != manifest_path and output_path.exists() and output_path.stat().st_size > 0 and not overwrite:
        raise ValueError(f"{output_path} already exists; pass --overwrite to replace it")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for record in updated:
            file.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return len(updated), included_count, excluded_count


def main() -> int:
    args = parse_args()
    output = args.output or args.manifest
    try:
        total, included, excluded = apply_tts_audit_status(
            manifest_path=args.manifest,
            exclusion_log_path=args.exclusion_log,
            output_path=output,
            overwrite=args.overwrite,
        )
    except ValueError as exc:
        print(f"TTS audit status application failed: {exc}")
        return 1
    print(f"Wrote {total} audio manifest rows to {output}")
    print(f"include_in_experiments=true: {included}")
    print(f"include_in_experiments=false: {excluded}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
