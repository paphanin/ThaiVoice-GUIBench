from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT_COLUMNS = [
    "utterance_id",
    "domain",
    "tier",
    "intent_id",
    "screen_id",
    "target_element_id",
    "target_label",
    "original_text",
    "naturalness_score",
    "tier_validity",
    "label_leakage",
    "asr_tts_risk",
    "edited_text",
    "edit_type",
    "edit_reason",
    "auditor_notes",
]


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def write_audit_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=AUDIT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def fixture_utterances() -> list[dict]:
    return [
        {
            "utterance_id": "utt_001",
            "mapping_id": "map_001",
            "intent_id": "send_money",
            "screen_id": "screen_001",
            "target_element_id": "transfer_button",
            "tier": "T1_verbatim",
            "text_gold": "กดปุ่ม Transfer ในหน้าเงินจำลองเพื่อส่งเงินให้หน่อยครับ",
            "language_class": "code_switched",
            "loanword_spans": [{"text": "Transfer", "start": 7, "end": 15}],
            "generation_notes": "T1 may include the visible target label.",
        },
        {
            "utterance_id": "utt_002",
            "mapping_id": "map_001",
            "intent_id": "send_money",
            "screen_id": "screen_001",
            "target_element_id": "transfer_button",
            "tier": "T2_paraphrase",
            "text_gold": "ช่วยโอนเงินให้คนนี้หน่อยครับ",
            "language_class": "pure_thai",
            "loanword_spans": [],
            "generation_notes": "Generated from curated intent paraphrase.",
        },
    ]


def audit_row(utterance: dict, **overrides: str) -> dict[str, str]:
    row = {
        "utterance_id": utterance["utterance_id"],
        "domain": "mock_finance",
        "tier": utterance["tier"],
        "intent_id": utterance["intent_id"],
        "screen_id": utterance["screen_id"],
        "target_element_id": utterance["target_element_id"],
        "target_label": "Transfer",
        "original_text": utterance["text_gold"],
        "naturalness_score": "natural",
        "tier_validity": utterance["tier"],
        "label_leakage": "",
        "asr_tts_risk": "",
        "edited_text": "",
        "edit_type": "",
        "edit_reason": "",
        "auditor_notes": "",
    }
    row.update(overrides)
    return row


def run_apply(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "scripts/apply_native_audit.py",
            "--utterances",
            str(tmp_path / "utterances.jsonl"),
            "--audit",
            str(tmp_path / "native_audit_v1.csv"),
            "--output",
            str(tmp_path / "utterances_audited.jsonl"),
            "--summary",
            str(tmp_path / "native_audit_summary.md"),
            "--overwrite",
        ],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )


def write_fixture(tmp_path: Path, audit_rows: list[dict[str, str]]) -> None:
    write_jsonl(tmp_path / "utterances.jsonl", fixture_utterances())
    write_audit_csv(tmp_path / "native_audit_v1.csv", audit_rows)


def test_apply_audit_replaces_edited_text_and_preserves_metadata_order(tmp_path: Path) -> None:
    utterances = fixture_utterances()
    write_fixture(
        tmp_path,
        [
            audit_row(
                utterances[0],
                naturalness_score="slightly_awkward",
                edited_text="กดปุ่ม Transfer เพื่อส่งเงินให้หน่อยครับ",
                edit_type="style_simplification",
                edit_reason="to make it sound more natural",
            ),
            audit_row(utterances[1]),
        ],
    )

    result = run_apply(tmp_path)

    assert result.returncode == 0, result.stderr + result.stdout
    records = read_jsonl(tmp_path / "utterances_audited.jsonl")
    assert [record["utterance_id"] for record in records] == ["utt_001", "utt_002"]
    assert records[0]["text_gold"] == "กดปุ่ม Transfer เพื่อส่งเงินให้หน่อยครับ"
    assert records[1]["text_gold"] == "ช่วยโอนเงินให้คนนี้หน่อยครับ"
    assert records[0]["mapping_id"] == "map_001"
    assert records[0]["language_class"] == "code_switched"
    assert records[0]["loanword_spans"] == [{"text": "Transfer", "start": 7, "end": 15}]
    assert records[0]["generation_notes"] == "T1 may include the visible target label."


def test_apply_audit_duplicate_audit_ids_fail(tmp_path: Path) -> None:
    utterances = fixture_utterances()
    duplicate = audit_row(utterances[1], utterance_id="utt_001")
    write_fixture(tmp_path, [audit_row(utterances[0]), duplicate])

    result = run_apply(tmp_path)

    assert result.returncode != 0
    assert "duplicate audit utterance_id `utt_001`" in result.stdout


def test_apply_audit_missing_audit_row_fails(tmp_path: Path) -> None:
    utterances = fixture_utterances()
    write_fixture(tmp_path, [audit_row(utterances[0])])

    result = run_apply(tmp_path)

    assert result.returncode != 0
    assert "missing audit row for utterance_id `utt_002`" in result.stdout


def test_apply_audit_remove_bad_item_skips_row_and_counts_removed(tmp_path: Path) -> None:
    utterances = fixture_utterances()
    write_fixture(
        tmp_path,
        [
            audit_row(utterances[0]),
            audit_row(
                utterances[1],
                naturalness_score="bad",
                edit_type="remove_bad_item",
                edit_reason="meaning_fix",
            ),
        ],
    )

    result = run_apply(tmp_path)

    assert result.returncode == 0, result.stderr + result.stdout
    records = read_jsonl(tmp_path / "utterances_audited.jsonl")
    assert [record["utterance_id"] for record in records] == ["utt_001"]
    summary = (tmp_path / "native_audit_summary.md").read_text(encoding="utf-8")
    assert "| number generated | 2 |" in summary
    assert "| number bad | 1 |" in summary
    assert "| number removed | 1 |" in summary


def test_apply_audit_summary_statistics(tmp_path: Path) -> None:
    utterances = fixture_utterances()
    write_fixture(
        tmp_path,
        [
            audit_row(
                utterances[0],
                naturalness_score="slightly_awkward",
                label_leakage="leakage",
                edited_text="กดปุ่ม Transfer เพื่อส่งเงินให้หน่อยครับ",
                edit_type="style_simplification",
                edit_reason="to make it sound more natural",
            ),
            audit_row(
                utterances[1],
                tier_validity="wrong_tier",
            ),
        ],
    )

    result = run_apply(tmp_path)

    assert result.returncode == 0, result.stderr + result.stdout
    summary = (tmp_path / "native_audit_summary.md").read_text(encoding="utf-8")
    assert "| number natural | 1 |" in summary
    assert "| number slightly awkward | 1 |" in summary
    assert "| number edited | 1 |" in summary
    assert "| edit rate | 1/2 (50.0%) |" in summary
    assert "| to make it sound more natural | 1 |" in summary
    assert "| label leakage cases found | 1 |" in summary
    assert "| tier mismatch cases found | 1 |" in summary
