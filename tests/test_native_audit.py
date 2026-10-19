from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_COLUMNS = [
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
REMAINING_HUMAN_COLUMNS = EXPECTED_COLUMNS[9:]


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_audit(tmp_path: Path, screens: list[dict] | None = None) -> subprocess.CompletedProcess[str]:
    utterances = [
        {
            "utterance_id": "utt_demo_001",
            "intent_id": "send_money",
            "screen_id": "screen_demo",
            "target_element_id": "transfer_button",
            "tier": "T2_paraphrase",
            "text_gold": "โอนเงินให้คนนี้หน่อย",
        },
        {
            "utterance_id": "utt_demo_002",
            "intent_id": "send_money",
            "screen_id": "screen_demo",
            "target_element_id": "transfer_button",
            "tier": "T3_intent",
            "text_gold": "เปิดหน้าจำลองให้หน่อย",
        }
    ]
    intents = [
        {
            "intent_id": "send_money",
            "domain": "mock_finance",
        }
    ]
    if screens is None:
        screens = [
            {
                "screen_id": "screen_demo",
                "elements": [
                    {"element_id": "transfer_button", "label": "Transfer"},
                    {"element_id": "topup_button", "label": "Top up"},
                ],
            }
        ]

    utterance_path = tmp_path / "utterances.jsonl"
    intent_path = tmp_path / "intents.jsonl"
    screen_path = tmp_path / "screens.jsonl"
    output_path = tmp_path / "native_audit_v1.csv"
    summary_path = tmp_path / "native_audit_summary.md"
    write_jsonl(utterance_path, utterances)
    write_jsonl(intent_path, intents)
    write_jsonl(screen_path, screens)

    return subprocess.run(
        [
            sys.executable,
            "scripts/make_native_audit.py",
            "--utterances",
            str(utterance_path),
            "--intents",
            str(intent_path),
            "--screens",
            str(screen_path),
            "--output",
            str(output_path),
            "--summary",
            str(summary_path),
            "--overwrite",
        ],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )


def run_audit_preserving_existing(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    utterances = [
        {
            "utterance_id": "utt_demo_001",
            "intent_id": "send_money",
            "screen_id": "screen_demo",
            "target_element_id": "transfer_button",
            "tier": "T2_paraphrase",
            "text_gold": "โอนเงินให้คนนี้หน่อย",
        }
    ]
    intents = [{"intent_id": "send_money", "domain": "mock_finance"}]
    screens = [
        {
            "screen_id": "screen_demo",
            "elements": [{"element_id": "transfer_button", "label": "Transfer"}],
        }
    ]
    utterance_path = tmp_path / "utterances.jsonl"
    intent_path = tmp_path / "intents.jsonl"
    screen_path = tmp_path / "screens.jsonl"
    output_path = tmp_path / "native_audit_v1.csv"
    summary_path = tmp_path / "native_audit_summary.md"
    write_jsonl(utterance_path, utterances)
    write_jsonl(intent_path, intents)
    write_jsonl(screen_path, screens)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=EXPECTED_COLUMNS)
        writer.writeheader()
        writer.writerow(
            {
                "utterance_id": "utt_demo_001",
                "domain": "mock_finance",
                "tier": "T2_paraphrase",
                "intent_id": "send_money",
                "screen_id": "screen_demo",
                "target_element_id": "transfer_button",
                "target_label": "Transfer",
                "original_text": "ช่วยโอนเงินให้คนนี้หน่อยครับ",
                "naturalness_score": "natural",
                "tier_validity": "T2_paraphrase",
                "label_leakage": "",
                "asr_tts_risk": "low",
                "edited_text": "ช่วยโอนเงินให้คนนี้หน่อยค่ะ",
                "edit_type": "particle_fix",
                "edit_reason": "neutralize ending",
                "auditor_notes": "keep edit",
            }
        )

    return subprocess.run(
        [
            sys.executable,
            "scripts/make_native_audit.py",
            "--utterances",
            str(utterance_path),
            "--intents",
            str(intent_path),
            "--screens",
            str(screen_path),
            "--output",
            str(output_path),
            "--summary",
            str(summary_path),
            "--preserve-existing",
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


def test_native_audit_csv_header_and_row_values(tmp_path: Path) -> None:
    result = run_audit(tmp_path)

    assert result.returncode == 0, result.stderr + result.stdout
    with (tmp_path / "native_audit_v1.csv").open("r", encoding="utf-8", newline="") as file:
        reader = csv.reader(file)
        assert next(reader) == EXPECTED_COLUMNS

    rows = read_csv(tmp_path / "native_audit_v1.csv")
    assert len(rows) == 2
    row = rows[0]
    assert row["utterance_id"] == "utt_demo_001"
    assert row["domain"] == "mock_finance"
    assert row["target_label"] == "Transfer"
    assert row["original_text"] == "โอนเงินให้คนนี้หน่อย"


def test_native_audit_prefills_naturalness_and_leaves_remaining_fields_blank(tmp_path: Path) -> None:
    result = run_audit(tmp_path)

    assert result.returncode == 0, result.stderr + result.stdout
    rows = read_csv(tmp_path / "native_audit_v1.csv")
    by_id = {row["utterance_id"]: row for row in rows}
    assert by_id["utt_demo_001"]["naturalness_score"] == "natural"
    assert by_id["utt_demo_002"]["naturalness_score"] == "slightly_awkward"
    assert all(row[column] == "" for row in rows for column in REMAINING_HUMAN_COLUMNS)


def test_native_audit_missing_target_element_fails(tmp_path: Path) -> None:
    screens = [
        {
            "screen_id": "screen_demo",
            "elements": [
                {"element_id": "topup_button", "label": "Top up"},
            ],
        }
    ]

    result = run_audit(tmp_path, screens=screens)

    assert result.returncode != 0
    assert "target_element_id `transfer_button` missing" in result.stdout


def test_native_audit_preserves_existing_fields_and_neutralizes_edited_text(tmp_path: Path) -> None:
    result = run_audit_preserving_existing(tmp_path)

    assert result.returncode == 0, result.stderr + result.stdout
    rows = read_csv(tmp_path / "native_audit_v1.csv")
    assert len(rows) == 1
    row = rows[0]
    assert row["original_text"] == "โอนเงินให้คนนี้หน่อย"
    assert row["tier_validity"] == "T2_paraphrase"
    assert row["asr_tts_risk"] == "low"
    assert row["edited_text"] == "ช่วยโอนเงินให้คนนี้หน่อย"
    assert row["edit_type"] == "particle_fix"
    assert row["auditor_notes"] == "keep edit"
