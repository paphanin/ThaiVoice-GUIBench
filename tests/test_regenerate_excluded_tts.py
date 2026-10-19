from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import regenerate_excluded_tts  # noqa: E402


def wav_bytes(duration_frames: int = 40) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(8000)
        wav_file.writeframes(b"\x00\x00" * duration_frames)
    return buffer.getvalue()


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def write_config(tmp_path: Path) -> Path:
    config = {
        "engines": {
            "azure": {
                "provider": "azure",
                "output_format": "riff-24khz-16bit-mono-pcm",
                "voices": {
                    "voice_01": {
                        "provider_voice": "th-TH-PremwadeeNeural",
                        "split_policy": "dev_test",
                    },
                    "voice_02": {
                        "provider_voice": "th-TH-NiwatNeural",
                        "split_policy": "test_only",
                    },
                },
            }
        }
    }
    path = tmp_path / "tts.yaml"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def manifest_row(
    *,
    audio_id: str,
    utterance_id: str,
    voice_id: str = "voice_01",
    text: str = "กดปุ่ม Transfer ให้หน่อย",
    audio_path: str = "data/audio/wav/azure/voice_01/test__utt_001.wav",
) -> dict:
    return {
        "audio_id": audio_id,
        "utterance_id": utterance_id,
        "split": "test",
        "engine_id": "azure",
        "voice_id": voice_id,
        "provider_voice": "th-TH-PremwadeeNeural" if voice_id == "voice_01" else "th-TH-NiwatNeural",
        "provider_model": "riff-24khz-16bit-mono-pcm",
        "text": text,
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "audio_path": audio_path,
        "format": "wav",
        "sample_rate_hz": 24000,
        "duration_ms": 500,
        "synthesis_mode": "real",
        "created_at": "2026-07-09T00:00:00Z",
    }


def audit_row(
    *,
    audio_id: str,
    utterance_id: str,
    voice_id: str = "voice_01",
    flagged: str = "TRUE",
    text: str = "กดปุ่ม Transfer ให้หน่อย",
) -> dict[str, str]:
    return {
        "audio_id": audio_id,
        "utterance_id": utterance_id,
        "engine_id": "azure",
        "voice_id": voice_id,
        "provider_voice": "th-TH-PremwadeeNeural" if voice_id == "voice_01" else "th-TH-NiwatNeural",
        "split": "test",
        "tier": "T1_verbatim",
        "text_gold": text,
        "loanword_spans": '[{"text": "Transfer", "start": 7, "end": 15}]',
        "audio_path": f"data/audio/wav/azure/{voice_id}/test__{utterance_id}.wav",
        "thai_intelligibility": "5",
        "english_loanword_fidelity": "2",
        "code_switch_fidelity": "4",
        "overall_naturalness": "3",
        "exclude_voice_candidate": flagged,
        "issue_tags": "",
        "auditor_notes": "",
    }


def run_regeneration(tmp_path: Path, *, overwrite: bool = True):
    return regenerate_excluded_tts.regenerate_exclusions(
        config_path=tmp_path / "tts.yaml",
        manifest_path=tmp_path / "audio_manifest.jsonl",
        audit_path=tmp_path / "tts_fidelity_audit_v1.csv",
        replacement_root=tmp_path / "wav_regen",
        exclusion_log_path=tmp_path / "tts_exclusion_log.csv",
        attempt_log_path=tmp_path / "tts_regeneration_attempts.csv",
        replacement_audit_path=tmp_path / "tts_regeneration_audit_v1.csv",
        attempt_number=1,
        max_retries=0,
        retry_delay_seconds=0,
        dry_run=False,
        overwrite=overwrite,
    )


def test_regenerates_only_flagged_rows_and_preserves_original_wav(tmp_path: Path, monkeypatch) -> None:
    write_config(tmp_path)
    original_path = tmp_path / "audio/wav/azure/voice_01/test__utt_001.wav"
    original_path.parent.mkdir(parents=True)
    original_path.write_bytes(b"original audio")
    flagged_audio_id = "azure__voice_01__test__utt_001"
    skipped_audio_id = "azure__voice_01__test__utt_002"
    write_jsonl(
        tmp_path / "audio_manifest.jsonl",
        [
            manifest_row(audio_id=flagged_audio_id, utterance_id="utt_001", audio_path=original_path.as_posix()),
            manifest_row(audio_id=skipped_audio_id, utterance_id="utt_002"),
        ],
    )
    write_csv(
        tmp_path / "tts_fidelity_audit_v1.csv",
        regenerate_excluded_tts.REGEN_AUDIT_COLUMNS[:0]
        + [
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
        ],
        [
            audit_row(audio_id=flagged_audio_id, utterance_id="utt_001"),
            audit_row(audio_id=skipped_audio_id, utterance_id="utt_002", flagged=""),
        ],
    )
    calls: list[str] = []

    def fake_synthesize(row, engine_config, voice_config):
        calls.append(row["audio_id"])
        return wav_bytes(duration_frames=80)

    monkeypatch.setattr(regenerate_excluded_tts, "synthesize_candidate", fake_synthesize)

    exclusion_rows, attempt_rows, replacement_audit_rows = run_regeneration(tmp_path)

    replacement_id = f"{flagged_audio_id}__regen01"
    replacement_path = tmp_path / "wav_regen/azure/voice_01" / f"{replacement_id}.wav"
    assert calls == [replacement_id]
    assert original_path.read_bytes() == b"original audio"
    assert replacement_path.exists()
    assert [row["audio_id"] for row in exclusion_rows] == [flagged_audio_id]
    assert attempt_rows[0]["status"] == "success"
    assert attempt_rows[0]["replacement_audio_id"] == replacement_id
    assert replacement_audit_rows[0]["replacement_audio_id"] == replacement_id
    assert read_csv(tmp_path / "tts_exclusion_log.csv")[0]["decision"] == "regenerate"


def test_regeneration_attempt_log_is_deterministic_and_replacement_ids_are_unique(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_config(tmp_path)
    first_id = "azure__voice_01__test__utt_001"
    second_id = "azure__voice_02__test__utt_002"
    write_jsonl(
        tmp_path / "audio_manifest.jsonl",
        [
            manifest_row(audio_id=first_id, utterance_id="utt_001"),
            manifest_row(
                audio_id=second_id,
                utterance_id="utt_002",
                voice_id="voice_02",
                audio_path="data/audio/wav/azure/voice_02/test__utt_002.wav",
            ),
        ],
    )
    write_csv(
        tmp_path / "tts_fidelity_audit_v1.csv",
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
            "issue_tags",
            "auditor_notes",
        ],
        [
            audit_row(audio_id=first_id, utterance_id="utt_001"),
            audit_row(audio_id=second_id, utterance_id="utt_002", voice_id="voice_02"),
        ],
    )

    monkeypatch.setattr(
        regenerate_excluded_tts,
        "synthesize_candidate",
        lambda row, engine_config, voice_config: wav_bytes(duration_frames=80),
    )

    run_regeneration(tmp_path)
    attempts = read_csv(tmp_path / "tts_regeneration_attempts.csv")

    assert [row["original_audio_id"] for row in attempts] == [first_id, second_id]
    assert [row["replacement_audio_id"] for row in attempts] == [
        f"{first_id}__regen01",
        f"{second_id}__regen01",
    ]
    assert len({row["replacement_audio_id"] for row in attempts}) == 2


def test_missing_manifest_row_fails_clearly(tmp_path: Path) -> None:
    write_config(tmp_path)
    write_jsonl(
        tmp_path / "audio_manifest.jsonl",
        [manifest_row(audio_id="azure__voice_01__test__utt_other", utterance_id="utt_other")],
    )
    missing_id = "azure__voice_01__test__utt_missing"
    write_csv(
        tmp_path / "tts_fidelity_audit_v1.csv",
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
            "issue_tags",
            "auditor_notes",
        ],
        [audit_row(audio_id=missing_id, utterance_id="utt_missing")],
    )

    try:
        run_regeneration(tmp_path)
    except ValueError as exc:
        assert f"flagged audio `{missing_id}` is missing from audio manifest" in str(exc)
    else:
        raise AssertionError("expected missing manifest row to fail")


def test_duplicate_flagged_audio_id_fails(tmp_path: Path) -> None:
    write_config(tmp_path)
    audio_id = "azure__voice_01__test__utt_001"
    write_jsonl(tmp_path / "audio_manifest.jsonl", [manifest_row(audio_id=audio_id, utterance_id="utt_001")])
    write_csv(
        tmp_path / "tts_fidelity_audit_v1.csv",
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
            "issue_tags",
            "auditor_notes",
        ],
        [
            audit_row(audio_id=audio_id, utterance_id="utt_001"),
            audit_row(audio_id=audio_id, utterance_id="utt_001"),
        ],
    )

    try:
        run_regeneration(tmp_path)
    except ValueError as exc:
        assert "duplicate flagged audio_id" in str(exc)
    else:
        raise AssertionError("expected duplicate flagged audio_id to fail")
