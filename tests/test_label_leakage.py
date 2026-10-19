from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(args, cwd=ROOT, check=False, text=True, capture_output=True, env=env, encoding="utf-8")


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def base_fixture(tmp_path: Path) -> tuple[Path, list[dict]]:
    output = tmp_path / "utterances.jsonl"
    result = run_command(
        [
            sys.executable,
            "scripts/generate_utterances.py",
            "--num-per-tier",
            "1",
            "--seed",
            "42",
            "--output",
            str(output),
            "--overwrite",
        ]
    )
    assert result.returncode == 0, result.stderr + result.stdout
    return output, load_jsonl(output)


def validate(path: Path) -> subprocess.CompletedProcess[str]:
    return run_command(
        [
            sys.executable,
            "scripts/validate_utterances.py",
            "--utterances",
            str(path),
            "--mappings",
            "data/intents/intent_screen_targets.jsonl",
            "--screens",
            "data/screens/screens.jsonl",
            "--schema",
            "schemas/utterance.schema.json",
        ]
    )


def test_duplicate_utterance_ids_fail_validation(tmp_path: Path) -> None:
    _, records = base_fixture(tmp_path)
    bad_records = copy.deepcopy(records)
    bad_records[1]["utterance_id"] = bad_records[0]["utterance_id"]
    bad_path = tmp_path / "duplicate_ids.jsonl"
    write_jsonl(bad_path, bad_records)

    result = validate(bad_path)

    assert result.returncode != 0
    assert "duplicate utterance_id" in result.stdout


def test_missing_tier_fails_validation(tmp_path: Path) -> None:
    _, records = base_fixture(tmp_path)
    mapping_id = records[0]["mapping_id"]
    bad_records = [
        record
        for record in records
        if not (record["mapping_id"] == mapping_id and record["tier"] == "T4_visual_positional")
    ]
    bad_path = tmp_path / "missing_tier.jsonl"
    write_jsonl(bad_path, bad_records)

    result = validate(bad_path)

    assert result.returncode != 0
    assert "missing utterance tiers" in result.stdout


def test_leaked_t2_target_label_fails_validation(tmp_path: Path) -> None:
    _, records = base_fixture(tmp_path)
    screens = load_jsonl(ROOT / "data/screens/screens.jsonl")
    labels = {
        (screen["screen_id"], element["element_id"]): element["label"]
        for screen in screens
        for element in screen["elements"]
    }
    bad_records = copy.deepcopy(records)
    leaked = next(record for record in bad_records if record["tier"] == "T2_paraphrase")
    label = labels[(leaked["screen_id"], leaked["target_element_id"])]
    leaked["text_gold"] = f"กด {label} ให้หน่อยครับ"
    bad_path = tmp_path / "leaked_t2.jsonl"
    write_jsonl(bad_path, bad_records)

    result = validate(bad_path)

    assert result.returncode != 0
    assert "leaks target label" in result.stdout


def test_transfer_phonological_alias_fails_validation(tmp_path: Path) -> None:
    _, records = base_fixture(tmp_path)
    bad_records = copy.deepcopy(records)
    leaked = next(
        record
        for record in bad_records
        if record["tier"] == "T2_paraphrase" and record["target_element_id"] == "transfer_button"
    )
    leaked["text_gold"] = "กดทรานเฟอร์ให้หน่อยครับ"
    bad_path = tmp_path / "leaked_transfer_alias.jsonl"
    write_jsonl(bad_path, bad_records)

    result = validate(bad_path)

    assert result.returncode != 0
    assert "ทรานเฟอร์" in result.stdout


def test_validator_passes_on_small_valid_fixture(tmp_path: Path) -> None:
    utterances = [
        {
            "utterance_id": "map_demo_t1_verbatim_01",
            "mapping_id": "map_demo",
            "intent_id": "demo_intent",
            "screen_id": "screen_demo",
            "target_element_id": "transfer_button",
            "tier": "T1_verbatim",
            "text_gold": "กดปุ่ม Transfer ให้หน่อยครับ",
            "language_class": "code_switched",
            "loanword_spans": [{"text": "Transfer", "start": 7, "end": 15}],
            "generation_notes": "fixture",
        },
        {
            "utterance_id": "map_demo_t2_paraphrase_01",
            "mapping_id": "map_demo",
            "intent_id": "demo_intent",
            "screen_id": "screen_demo",
            "target_element_id": "transfer_button",
            "tier": "T2_paraphrase",
            "text_gold": "ช่วยโอนเงินให้คนนี้หน่อยครับ",
            "language_class": "pure_thai",
            "loanword_spans": [],
            "generation_notes": "fixture",
        },
        {
            "utterance_id": "map_demo_t3_intent_01",
            "mapping_id": "map_demo",
            "intent_id": "demo_intent",
            "screen_id": "screen_demo",
            "target_element_id": "transfer_button",
            "tier": "T3_intent",
            "text_gold": "อยากส่งเงินให้คนนี้ ต้องกดตรงไหน",
            "language_class": "pure_thai",
            "loanword_spans": [],
            "generation_notes": "fixture",
        },
        {
            "utterance_id": "map_demo_t4_visual_positional_01",
            "mapping_id": "map_demo",
            "intent_id": "demo_intent",
            "screen_id": "screen_demo",
            "target_element_id": "transfer_button",
            "tier": "T4_visual_positional",
            "text_gold": "กดปุ่มมุมขวาบนให้หน่อยค่ะ",
            "language_class": "pure_thai",
            "loanword_spans": [],
            "generation_notes": "fixture",
        },
    ]
    mappings = [
        {
            "mapping_id": "map_demo",
            "intent_id": "demo_intent",
            "screen_id": "screen_demo",
            "target_element_id": "transfer_button",
            "distractor_element_ids": ["topup_button"],
            "difficulty": "easy",
            "notes": "fixture",
        }
    ]
    screens = [
        {
            "screen_id": "screen_demo",
            "domain": "mock_finance",
            "width": 1080,
            "height": 1920,
            "elements": [
                {"element_id": "transfer_button", "label": "Transfer", "bbox": [600, 430, 900, 560]},
                {"element_id": "topup_button", "label": "Top up", "bbox": [100, 430, 400, 560]},
            ],
        }
    ]

    utterance_path = tmp_path / "utterances.jsonl"
    mapping_path = tmp_path / "mappings.jsonl"
    screen_path = tmp_path / "screens.jsonl"
    write_jsonl(utterance_path, utterances)
    write_jsonl(mapping_path, mappings)
    write_jsonl(screen_path, screens)

    result = run_command(
        [
            sys.executable,
            "scripts/validate_utterances.py",
            "--utterances",
            str(utterance_path),
            "--mappings",
            str(mapping_path),
            "--screens",
            str(screen_path),
            "--schema",
            "schemas/utterance.schema.json",
        ]
    )

    assert result.returncode == 0, result.stderr + result.stdout
