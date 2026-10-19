from __future__ import annotations

import io
import json
import subprocess
import sys
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def write_config(tmp_path: Path) -> Path:
    config = json.loads((ROOT / "configs/tts.yaml").read_text(encoding="utf-8"))
    config["outputs"] = {
        "audio_root": str(tmp_path / "audio"),
        "wav_root": str(tmp_path / "audio/wav"),
        "manifest": str(tmp_path / "audio/audio_manifest.jsonl"),
        "report": str(tmp_path / "audio/AUDIO_GENERATION_REPORT.md"),
        "logs_dir": str(tmp_path / "audio/logs"),
        "cache_dir": str(tmp_path / "audio/cache"),
    }
    path = tmp_path / "tts.yaml"
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def run_synthesize(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "scripts/synthesize_tts.py",
            "--config",
            str(tmp_path / "tts.yaml"),
            "--dry-run",
            "--overwrite",
        ],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )


def run_validate(tmp_path: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "scripts/validate_audio_manifest.py",
            "--manifest",
            str(tmp_path / "audio/audio_manifest.jsonl"),
            "--config",
            str(tmp_path / "tts.yaml"),
            "--manifest-only",
            *extra,
        ],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def wav_bytes(duration_frames: int = 40) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(8000)
        wav_file.writeframes(b"\x00\x00" * duration_frames)
    return buffer.getvalue()


def test_dry_run_synthesis_creates_expected_manifest_and_report(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = run_synthesize(tmp_path)

    assert result.returncode == 0, result.stderr + result.stdout
    rows = read_jsonl(tmp_path / "audio/audio_manifest.jsonl")
    assert len(rows) == 480
    assert (tmp_path / "audio/AUDIO_GENERATION_REPORT.md").exists()
    assert (tmp_path / "audio/logs/tts_generation_log.jsonl").exists()
    assert (tmp_path / "audio/cache/tts_cache_index.jsonl").exists()


def test_manifest_only_validation_passes_and_respects_test_only_voice(tmp_path: Path) -> None:
    write_config(tmp_path)
    result = run_synthesize(tmp_path)
    assert result.returncode == 0, result.stderr + result.stdout

    validation = run_validate(tmp_path)

    assert validation.returncode == 0, validation.stderr + validation.stdout
    rows = read_jsonl(tmp_path / "audio/audio_manifest.jsonl")
    dev_voice_keys = {(row["engine_id"], row["voice_id"]) for row in rows if row["split"] == "dev"}
    test_voice_keys = {(row["engine_id"], row["voice_id"]) for row in rows if row["split"] == "test"}
    assert ("azure", "voice_02") not in dev_voice_keys
    assert ("azure", "voice_02") in test_voice_keys
    assert sum(1 for row in rows if row["split"] == "dev") == 96
    assert sum(1 for row in rows if row["split"] == "test") == 384


def test_manifest_references_existing_utterances_and_matching_splits(tmp_path: Path) -> None:
    write_config(tmp_path)
    result = run_synthesize(tmp_path)
    assert result.returncode == 0, result.stderr + result.stdout
    rows = read_jsonl(tmp_path / "audio/audio_manifest.jsonl")
    utterances = {
        json.loads(line)["utterance_id"]: json.loads(line)
        for line in (ROOT / "data/utterances/utterances_audited.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    dev = set(json.loads((ROOT / "data/splits/dev.json").read_text(encoding="utf-8"))["utterance_ids"])
    test = set(json.loads((ROOT / "data/splits/test.json").read_text(encoding="utf-8"))["utterance_ids"])

    assert all(row["utterance_id"] in utterances for row in rows)
    assert all(row["text"] == utterances[row["utterance_id"]]["text_gold"] for row in rows)
    assert all((row["utterance_id"] in dev) == (row["split"] == "dev") for row in rows)
    assert all((row["utterance_id"] in test) == (row["split"] == "test") for row in rows)


def test_duplicate_audio_id_fails_validation(tmp_path: Path) -> None:
    write_config(tmp_path)
    result = run_synthesize(tmp_path)
    assert result.returncode == 0, result.stderr + result.stdout
    manifest_path = tmp_path / "audio/audio_manifest.jsonl"
    rows = read_jsonl(manifest_path)
    rows[1]["audio_id"] = rows[0]["audio_id"]
    manifest_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )

    validation = run_validate(tmp_path)

    assert validation.returncode != 0
    assert "duplicate audio_id" in validation.stdout


def test_missing_wav_fails_unless_manifest_only(tmp_path: Path) -> None:
    write_config(tmp_path)
    result = run_synthesize(tmp_path)
    assert result.returncode == 0, result.stderr + result.stdout

    manifest_only = run_validate(tmp_path)
    full_check = subprocess.run(
        [
            sys.executable,
            "scripts/validate_audio_manifest.py",
            "--manifest",
            str(tmp_path / "audio/audio_manifest.jsonl"),
            "--config",
            str(tmp_path / "tts.yaml"),
        ],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert manifest_only.returncode == 0, manifest_only.stderr + manifest_only.stdout
    assert full_check.returncode != 0
    assert "audio_path does not exist" in full_check.stdout


def test_skip_existing_resynthesizes_when_cached_text_hash_changes(tmp_path: Path, monkeypatch) -> None:
    import synthesize_tts

    wav_path = tmp_path / "audio/wav/openai/voice_01/test__utt_demo.wav"
    wav_path.parent.mkdir(parents=True)
    wav_path.write_bytes(wav_bytes(duration_frames=10))
    row = {
        "audio_id": "openai__voice_01__test__utt_demo",
        "audio_path": str(wav_path),
        "engine_id": "openai",
        "voice_id": "voice_01",
        "text_sha256": "new_hash",
    }
    voices = [
        (
            "openai",
            "voice_01",
            {"provider": "openai", "model": "demo"},
            {"provider_voice": "marin", "split_policy": "dev_test"},
        )
    ]
    calls = {"count": 0}

    def fake_synthesize_openai(record, engine_config, voice_config):
        calls["count"] += 1
        return wav_bytes(duration_frames=80)

    monkeypatch.setattr(synthesize_tts, "synthesize_openai", fake_synthesize_openai)

    logs = synthesize_tts.synthesize_real_audio(
        [row],
        voices,
        skip_existing=True,
        previous_cache={"openai__voice_01__test__utt_demo": {"text_sha256": "old_hash"}},
    )

    assert calls["count"] == 1
    assert logs == [
        {
            "audio_id": "openai__voice_01__test__utt_demo",
            "status": "synthesized",
            "audio_path": str(wav_path),
        }
    ]
    assert row["duration_ms"] == 10
