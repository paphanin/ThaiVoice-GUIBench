from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODEL = "whisper_large_v3_local"


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def manifest_row(audio_id: str, utterance_id: str, include: bool = True) -> dict:
    return {
        "audio_id": audio_id,
        "utterance_id": utterance_id,
        "audio_path": f"data/audio/wav/azure/voice_01/test__{utterance_id}.wav",
        "duration_ms": 1000,
        "include_in_experiments": include,
    }


def utterance_row(utterance_id: str) -> dict:
    return {
        "utterance_id": utterance_id,
        "text_gold": "demo",
    }


def asr_record(audio_id: str, utterance_id: str, **overrides: object) -> dict:
    record = {
        "asr_id": f"{audio_id}__{MODEL}",
        "audio_id": audio_id,
        "utterance_id": utterance_id,
        "asr_model": MODEL,
        "backend": "faster_whisper",
        "transcript": "ทดสอบ",
        "status": "success",
        "error_message": "",
        "audio_path": f"data/audio/wav/azure/voice_01/test__{utterance_id}.wav",
        "audio_duration_ms": 1000,
        "latency_ms": 250,
        "rtf": 0.25,
        "created_at": "2026-07-09T00:00:00Z",
        "params": {"model_name": "large-v3"},
    }
    record.update(overrides)
    return record


def write_fixture(tmp_path: Path, manifest: list[dict], utterances: list[dict], outputs: list[dict]) -> None:
    write_jsonl(tmp_path / "audio_manifest.jsonl", manifest)
    write_jsonl(tmp_path / "utterances.jsonl", utterances)
    write_jsonl(tmp_path / "asr_outputs.jsonl", outputs)


def run_validate(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "scripts/validate_asr_outputs.py",
            "--model",
            MODEL,
            "--outputs",
            str(tmp_path / "asr_outputs.jsonl"),
            "--manifest",
            str(tmp_path / "audio_manifest.jsonl"),
            "--utterances",
            str(tmp_path / "utterances.jsonl"),
            "--schema",
            "schemas/asr_output.schema.json",
        ],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )


def test_valid_asr_output_record_passes_validation(tmp_path: Path) -> None:
    audio_id = "azure__voice_01__test__utt_001_t1_verbatim_01"
    write_fixture(
        tmp_path,
        [manifest_row(audio_id, "utt_001_t1_verbatim_01")],
        [utterance_row("utt_001_t1_verbatim_01")],
        [asr_record(audio_id, "utt_001_t1_verbatim_01")],
    )

    result = run_validate(tmp_path)

    assert result.returncode == 0, result.stderr + result.stdout
    assert "ASR output validation passed" in result.stdout


def test_duplicate_asr_ids_fail(tmp_path: Path) -> None:
    audio_id = "azure__voice_01__test__utt_001_t1_verbatim_01"
    record = asr_record(audio_id, "utt_001_t1_verbatim_01")
    write_fixture(
        tmp_path,
        [manifest_row(audio_id, "utt_001_t1_verbatim_01")],
        [utterance_row("utt_001_t1_verbatim_01")],
        [record, dict(record)],
    )

    result = run_validate(tmp_path)

    assert result.returncode != 0
    assert "duplicate asr_id" in result.stdout


def test_missing_transcript_with_success_fails(tmp_path: Path) -> None:
    audio_id = "azure__voice_01__test__utt_001_t1_verbatim_01"
    write_fixture(
        tmp_path,
        [manifest_row(audio_id, "utt_001_t1_verbatim_01")],
        [utterance_row("utt_001_t1_verbatim_01")],
        [asr_record(audio_id, "utt_001_t1_verbatim_01", transcript="")],
    )

    result = run_validate(tmp_path)

    assert result.returncode != 0
    assert "successful records must have non-empty transcript" in result.stdout


def test_failed_record_without_error_message_fails(tmp_path: Path) -> None:
    audio_id = "azure__voice_01__test__utt_001_t1_verbatim_01"
    write_fixture(
        tmp_path,
        [manifest_row(audio_id, "utt_001_t1_verbatim_01")],
        [utterance_row("utt_001_t1_verbatim_01")],
        [asr_record(audio_id, "utt_001_t1_verbatim_01", status="failed", transcript="", error_message="")],
    )

    result = run_validate(tmp_path)

    assert result.returncode != 0
    assert "failed records must have non-empty error_message" in result.stdout


def test_excluded_audio_files_are_not_required(tmp_path: Path) -> None:
    included_id = "azure__voice_01__test__utt_001_t1_verbatim_01"
    excluded_id = "azure__voice_01__test__utt_002_t1_verbatim_01"
    write_fixture(
        tmp_path,
        [
            manifest_row(included_id, "utt_001_t1_verbatim_01", include=True),
            manifest_row(excluded_id, "utt_002_t1_verbatim_01", include=False),
        ],
        [utterance_row("utt_001_t1_verbatim_01"), utterance_row("utt_002_t1_verbatim_01")],
        [asr_record(included_id, "utt_001_t1_verbatim_01")],
    )

    result = run_validate(tmp_path)

    assert result.returncode == 0, result.stderr + result.stdout


def test_expected_valid_audio_missing_from_output_fails(tmp_path: Path) -> None:
    first_id = "azure__voice_01__test__utt_001_t1_verbatim_01"
    second_id = "azure__voice_01__test__utt_002_t1_verbatim_01"
    write_fixture(
        tmp_path,
        [
            manifest_row(first_id, "utt_001_t1_verbatim_01"),
            manifest_row(second_id, "utt_002_t1_verbatim_01"),
        ],
        [utterance_row("utt_001_t1_verbatim_01"), utterance_row("utt_002_t1_verbatim_01")],
        [asr_record(first_id, "utt_001_t1_verbatim_01")],
    )

    result = run_validate(tmp_path)

    assert result.returncode != 0
    assert "missing expected valid audio_ids" in result.stdout
