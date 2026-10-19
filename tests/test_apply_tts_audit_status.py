from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXCLUSION_COLUMNS = [
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


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def write_exclusion_log(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=EXCLUSION_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def manifest_row(audio_id: str) -> dict:
    return {
        "audio_id": audio_id,
        "utterance_id": audio_id.rsplit("__", 1)[-1],
        "split": "test",
        "engine_id": "azure",
        "voice_id": "voice_01",
        "provider_voice": "th-TH-PremwadeeNeural",
        "provider_model": "riff-24khz-16bit-mono-pcm",
        "text": "demo",
        "text_sha256": "0" * 64,
        "audio_path": f"data/audio/wav/azure/voice_01/test__{audio_id}.wav",
        "format": "wav",
        "sample_rate_hz": 24000,
        "duration_ms": 1000,
        "synthesis_mode": "real",
        "created_at": "2026-07-08T10:12:56Z",
    }


def exclusion_row(audio_id: str) -> dict[str, str]:
    return {
        "audio_id": audio_id,
        "utterance_id": "utt_001",
        "tts_engine": "azure",
        "voice_id": "voice_01",
        "text_gold": "demo",
        "thai_intelligibility": "5",
        "loanword_fidelity": "2",
        "code_switch_fidelity": "5",
        "overall_naturalness": "3",
        "decision": "regenerate",
        "exclusion_level": "audio_file",
        "reason": "English loanword fidelity below acceptable threshold.",
        "replacement_audio_id": f"{audio_id}__regen01",
        "notes": "Replacement candidate pending human audit.",
    }


def run_apply(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "scripts/apply_tts_audit_status.py",
            "--manifest",
            str(tmp_path / "audio_manifest.jsonl"),
            "--exclusion-log",
            str(tmp_path / "tts_exclusion_log.csv"),
        ],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )


def test_apply_tts_audit_status_marks_excluded_and_passed_rows(tmp_path: Path) -> None:
    excluded_id = "azure__voice_01__test__utt_001_t1_verbatim_01"
    included_id = "azure__voice_01__test__utt_002_t2_paraphrase_01"
    write_jsonl(tmp_path / "audio_manifest.jsonl", [manifest_row(excluded_id), manifest_row(included_id)])
    write_exclusion_log(tmp_path / "tts_exclusion_log.csv", [exclusion_row(excluded_id)])

    result = run_apply(tmp_path)

    assert result.returncode == 0, result.stderr + result.stdout
    rows = read_jsonl(tmp_path / "audio_manifest.jsonl")
    by_id = {row["audio_id"]: row for row in rows}
    assert by_id[excluded_id]["include_in_experiments"] is False
    assert by_id[included_id]["include_in_experiments"] is True
    assert "include_in_experiments=true: 1" in result.stdout
    assert "include_in_experiments=false: 1" in result.stdout


def test_apply_tts_audit_status_fails_for_unknown_exclusion(tmp_path: Path) -> None:
    write_jsonl(
        tmp_path / "audio_manifest.jsonl",
        [manifest_row("azure__voice_01__test__utt_001_t1_verbatim_01")],
    )
    write_exclusion_log(
        tmp_path / "tts_exclusion_log.csv",
        [exclusion_row("azure__voice_01__test__unknown_t1_verbatim_01")],
    )

    result = run_apply(tmp_path)

    assert result.returncode != 0
    assert "exclusion CSV contains unknown audio_ids" in result.stdout


def test_apply_tts_audit_status_fails_for_duplicate_exclusion(tmp_path: Path) -> None:
    audio_id = "azure__voice_01__test__utt_001_t1_verbatim_01"
    write_jsonl(tmp_path / "audio_manifest.jsonl", [manifest_row(audio_id)])
    write_exclusion_log(tmp_path / "tts_exclusion_log.csv", [exclusion_row(audio_id), exclusion_row(audio_id)])

    result = run_apply(tmp_path)

    assert result.returncode != 0
    assert f"duplicate excluded audio_id `{audio_id}`" in result.stdout
