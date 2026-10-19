from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_COLUMNS = [
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
HUMAN_SCORE_COLUMNS = EXPECTED_COLUMNS[10:]


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_audit(tmp_path: Path, *, sample_size: int = 100) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "scripts/make_tts_fidelity_audit.py",
            "--manifest",
            str(tmp_path / "audio_manifest.jsonl"),
            "--utterances",
            str(tmp_path / "utterances.jsonl"),
            "--output",
            str(tmp_path / "tts_fidelity_audit_v1.csv"),
            "--summary",
            str(tmp_path / "tts_fidelity_audit_summary.md"),
            "--sample-size",
            str(sample_size),
            "--overwrite",
        ],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def write_fixture(tmp_path: Path, utterance_count: int = 3) -> None:
    utterances = [
        {
            "utterance_id": "utt_code_001",
            "tier": "T1_verbatim",
            "text_gold": "กดปุ่ม Transfer ให้หน่อย",
            "language_class": "code_switched",
            "loanword_spans": [{"text": "Transfer", "start": 7, "end": 15}],
        },
        {
            "utterance_id": "utt_thai_001",
            "tier": "T2_paraphrase",
            "text_gold": "โอนเงินให้หน่อย",
            "language_class": "pure_thai",
            "loanword_spans": [],
        },
        {
            "utterance_id": "utt_code_002",
            "tier": "T1_verbatim",
            "text_gold": "เปิด Cart ให้หน่อย",
            "language_class": "code_switched",
            "loanword_spans": [{"text": "Cart", "start": 5, "end": 9}],
        },
    ][:utterance_count]
    manifest = [
        {
            "audio_id": f"openai__voice_01__test__{utterance['utterance_id']}",
            "utterance_id": utterance["utterance_id"],
            "engine_id": "openai",
            "voice_id": "voice_01",
            "provider_voice": "marin",
            "split": "test",
            "text": utterance["text_gold"],
            "audio_path": f"data/audio/wav/openai/voice_01/test__{utterance['utterance_id']}.wav",
        }
        for utterance in utterances
    ]
    write_jsonl(tmp_path / "utterances.jsonl", utterances)
    write_jsonl(tmp_path / "audio_manifest.jsonl", manifest)


def test_tts_fidelity_audit_filters_code_switched_rows_and_leaves_scores_blank(tmp_path: Path) -> None:
    write_fixture(tmp_path)

    result = run_audit(tmp_path)

    assert result.returncode == 0, result.stderr + result.stdout
    with (tmp_path / "tts_fidelity_audit_v1.csv").open("r", encoding="utf-8", newline="") as file:
        assert next(csv.reader(file)) == EXPECTED_COLUMNS
    rows = read_csv(tmp_path / "tts_fidelity_audit_v1.csv")
    assert [row["utterance_id"] for row in rows] == ["utt_code_001", "utt_code_002"]
    assert rows[0]["tier"] == "T1_verbatim"
    assert rows[0]["text_gold"] == "กดปุ่ม Transfer ให้หน่อย"
    assert "Transfer" in rows[0]["loanword_spans"]
    assert all(row[column] == "" for row in rows for column in HUMAN_SCORE_COLUMNS)


def test_tts_fidelity_audit_uses_all_available_when_less_than_sample_size(tmp_path: Path) -> None:
    write_fixture(tmp_path)

    result = run_audit(tmp_path, sample_size=100)

    assert result.returncode == 0, result.stderr + result.stdout
    rows = read_csv(tmp_path / "tts_fidelity_audit_v1.csv")
    summary = (tmp_path / "tts_fidelity_audit_summary.md").read_text(encoding="utf-8")
    assert len(rows) == 2
    assert "Only 2 code-switched audio items are available" in result.stdout
    assert "sampling_policy: audit_all_available" in summary
    assert "requested_sample_size: 100" in summary
    assert "selected_audio_items: 2" in summary


def test_tts_fidelity_audit_samples_deterministically_when_candidates_exceed_limit(tmp_path: Path) -> None:
    utterances = []
    manifest = []
    for index in range(8):
        utterance_id = f"utt_code_{index:03d}"
        utterances.append(
            {
                "utterance_id": utterance_id,
                "tier": "T1_verbatim",
                "text_gold": f"กด Search {index}",
                "language_class": "code_switched",
                "loanword_spans": [{"text": "Search", "start": 3, "end": 9}],
            }
        )
        voice_id = "voice_01" if index % 2 == 0 else "voice_02"
        manifest.append(
            {
                "audio_id": f"openai__{voice_id}__test__{utterance_id}",
                "utterance_id": utterance_id,
                "engine_id": "openai",
                "voice_id": voice_id,
                "provider_voice": "demo",
                "split": "test",
                "text": f"กด Search {index}",
                "audio_path": f"data/audio/wav/openai/{voice_id}/test__{utterance_id}.wav",
            }
        )
    write_jsonl(tmp_path / "utterances.jsonl", utterances)
    write_jsonl(tmp_path / "audio_manifest.jsonl", manifest)

    first = run_audit(tmp_path, sample_size=4)
    first_rows = read_csv(tmp_path / "tts_fidelity_audit_v1.csv")
    second = run_audit(tmp_path, sample_size=4)
    second_rows = read_csv(tmp_path / "tts_fidelity_audit_v1.csv")

    assert first.returncode == 0, first.stderr + first.stdout
    assert second.returncode == 0, second.stderr + second.stdout
    assert [row["audio_id"] for row in first_rows] == [row["audio_id"] for row in second_rows]
    assert len(first_rows) == 4
    assert {row["voice_id"] for row in first_rows} == {"voice_01", "voice_02"}


def test_tts_fidelity_audit_missing_utterance_fails(tmp_path: Path) -> None:
    write_jsonl(
        tmp_path / "utterances.jsonl",
        [
            {
                "utterance_id": "utt_code_001",
                "tier": "T1_verbatim",
                "text_gold": "กดปุ่ม Transfer ให้หน่อย",
                "language_class": "code_switched",
                "loanword_spans": [{"text": "Transfer", "start": 7, "end": 15}],
            }
        ],
    )
    write_jsonl(
        tmp_path / "audio_manifest.jsonl",
        [
            {
                "audio_id": "openai__voice_01__test__missing",
                "utterance_id": "missing",
                "engine_id": "openai",
                "voice_id": "voice_01",
                "provider_voice": "marin",
                "split": "test",
                "text": "กดปุ่ม Transfer ให้หน่อย",
                "audio_path": "data/audio/wav/openai/voice_01/test__missing.wav",
            }
        ],
    )

    result = run_audit(tmp_path)

    assert result.returncode != 0
    assert "references missing utterance" in result.stdout
