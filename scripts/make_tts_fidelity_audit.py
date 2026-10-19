"""Create a TTS fidelity audit CSV for code-switched audio items."""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any


AUDIT_COLUMNS = [
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
    "issue_tags",
    "auditor_notes",
]

HUMAN_SCORE_COLUMNS = [
    "thai_intelligibility",
    "english_loanword_fidelity",
    "code_switch_fidelity",
    "overall_naturalness",
    "exclude_voice_candidate",
    "issue_tags",
    "auditor_notes",
]

CODE_SWITCHED_CLASSES = {"code_switched", "mostly_english"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("data/audio/audio_manifest.jsonl"))
    parser.add_argument("--utterances", type=Path, default=Path("data/utterances/utterances_audited.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/audio/audit/tts_fidelity_audit_v1.csv"))
    parser.add_argument("--summary", type=Path, default=Path("data/audio/audit/tts_fidelity_audit_summary.md"))
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
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


def has_code_switch_signal(utterance: dict[str, Any]) -> bool:
    language_class = utterance.get("language_class")
    loanword_spans = utterance.get("loanword_spans")
    return language_class in CODE_SWITCHED_CLASSES or (
        isinstance(loanword_spans, list) and len(loanword_spans) > 0
    )


def candidate_rows(
    manifest: list[dict[str, Any]],
    utterances_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen_audio_ids: set[str] = set()
    for index, audio in enumerate(manifest, start=1):
        audio_id = audio.get("audio_id")
        if not isinstance(audio_id, str) or not audio_id:
            raise ValueError(f"audio manifest:{index}: missing or invalid audio_id")
        if audio_id in seen_audio_ids:
            raise ValueError(f"duplicate audio_id `{audio_id}` in audio manifest")
        seen_audio_ids.add(audio_id)

        utterance_id = audio.get("utterance_id")
        utterance = utterances_by_id.get(utterance_id)
        if utterance is None:
            raise ValueError(f"audio `{audio_id}` references missing utterance `{utterance_id}`")
        if audio.get("text") != utterance.get("text_gold"):
            raise ValueError(f"audio `{audio_id}` text does not match utterance text_gold")
        if has_code_switch_signal(utterance):
            candidates.append({"audio": audio, "utterance": utterance})
    return candidates


def balanced_sample(
    candidates: list[dict[str, Any]],
    sample_size: int,
    seed: int,
) -> list[dict[str, Any]]:
    if sample_size <= 0:
        raise ValueError("--sample-size must be positive")
    if len(candidates) <= sample_size:
        return candidates

    grouped: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        audio = candidate["audio"]
        key = f"{audio['engine_id']}/{audio['voice_id']}"
        grouped.setdefault(key, []).append(candidate)

    rng = random.Random(seed)
    for group in grouped.values():
        group.sort(key=lambda item: item["audio"]["audio_id"])
        rng.shuffle(group)

    selected: list[dict[str, Any]] = []
    keys = sorted(grouped)
    while len(selected) < sample_size and any(grouped.values()):
        for key in keys:
            if grouped[key]:
                selected.append(grouped[key].pop(0))
                if len(selected) == sample_size:
                    break
    return selected


def make_audit_rows(candidates: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for candidate in candidates:
        audio = candidate["audio"]
        utterance = candidate["utterance"]
        row = {
            "audio_id": str(audio["audio_id"]),
            "utterance_id": str(audio["utterance_id"]),
            "engine_id": str(audio["engine_id"]),
            "voice_id": str(audio["voice_id"]),
            "provider_voice": str(audio["provider_voice"]),
            "split": str(audio["split"]),
            "tier": str(utterance.get("tier", "")),
            "text_gold": str(utterance["text_gold"]),
            "loanword_spans": json.dumps(utterance.get("loanword_spans", []), ensure_ascii=False),
            "audio_path": str(audio["audio_path"]),
        }
        row.update({column: "" for column in HUMAN_SCORE_COLUMNS})
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


def write_summary(
    path: Path,
    *,
    candidate_count: int,
    selected_count: int,
    sample_size: int,
    seed: int,
    rows: list[dict[str, str]],
    overwrite: bool,
) -> None:
    if path.exists() and path.stat().st_size > 0 and not overwrite:
        raise ValueError(f"{path} already exists; pass --overwrite to replace it")
    voice_counts = Counter(f"{row['engine_id']}/{row['voice_id']}" for row in rows)
    split_counts = Counter(row["split"] for row in rows)
    lines = [
        "# TTS Fidelity Audit",
        "",
        "This audit screens synthesized audio quality for code-switched Thai commands before final experiments.",
        "",
        "## Sample",
        "",
        f"- requested_sample_size: {sample_size}",
        f"- candidate_code_switched_audio_items: {candidate_count}",
        f"- selected_audio_items: {selected_count}",
        f"- seed: {seed}",
        f"- sampling_policy: {'audit_all_available' if candidate_count <= sample_size else 'balanced_by_voice'}",
        "",
        "## Counts By Voice",
        "",
    ]
    for voice, count in sorted(voice_counts.items()):
        lines.append(f"- {voice}: {count}")
    lines.extend(["", "## Counts By Split", ""])
    for split, count in sorted(split_counts.items()):
        lines.append(f"- {split}: {count}")
    lines.extend(
        [
            "",
            "## Scoring Rubric",
            "",
            "Use 1-5 scores for `thai_intelligibility`, `english_loanword_fidelity`, `code_switch_fidelity`, and `overall_naturalness`.",
            "",
            "- 5: excellent; clean enough for final benchmark use.",
            "- 4: good; minor issue but acceptable.",
            "- 3: usable but should be reviewed.",
            "- 2: poor; likely exclude or regenerate.",
            "- 1: unusable.",
            "",
            "Mark `exclude_voice_candidate=true` if a voice repeatedly scores low, especially when average overall naturalness is below 3 or loanword/code-switch fidelity is below 3.",
            "",
            "## Audit Dimensions",
            "",
            "- `thai_intelligibility`: Thai words are understandable without reading the transcript.",
            "- `english_loanword_fidelity`: English label or loanword sounds recognizable, such as `Transfer`, `Search`, or `Cart`.",
            "- `code_switch_fidelity`: transition between Thai and English sounds natural and not garbled.",
            "- `overall_naturalness`: voice sounds acceptable for benchmark use.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def create_audit(
    manifest_path: Path,
    utterances_path: Path,
    output_path: Path,
    summary_path: Path,
    sample_size: int,
    seed: int,
    overwrite: bool,
) -> tuple[int, int]:
    manifest = load_jsonl(manifest_path, "audio manifest")
    utterances = load_jsonl(utterances_path, "utterances")
    utterances_by_id = index_by_id(utterances, "utterance_id", "utterances")
    candidates = candidate_rows(manifest, utterances_by_id)
    selected = balanced_sample(candidates, sample_size, seed)
    rows = make_audit_rows(selected)
    write_csv(rows, output_path, overwrite)
    write_summary(
        summary_path,
        candidate_count=len(candidates),
        selected_count=len(selected),
        sample_size=sample_size,
        seed=seed,
        rows=rows,
        overwrite=overwrite,
    )
    return len(candidates), len(selected)


def main() -> int:
    args = parse_args()
    try:
        candidate_count, selected_count = create_audit(
            manifest_path=args.manifest,
            utterances_path=args.utterances,
            output_path=args.output,
            summary_path=args.summary,
            sample_size=args.sample_size,
            seed=args.seed,
            overwrite=args.overwrite,
        )
    except (OSError, ValueError) as exc:
        print(f"TTS fidelity audit creation failed: {exc}")
        return 1
    print(f"Wrote {selected_count} TTS fidelity audit rows to {args.output}")
    if selected_count < args.sample_size:
        print(f"Only {candidate_count} code-switched audio items are available; auditing all available items.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
