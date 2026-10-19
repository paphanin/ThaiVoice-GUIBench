from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TIERS = ("T1_verbatim", "T2_paraphrase", "T3_intent", "T4_visual_positional")


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fixture_records(screen_count: int = 20) -> tuple[list[dict], list[dict], list[dict]]:
    domains = ("mock_finance", "shopping", "settings", "messaging")
    screens: list[dict] = []
    mappings: list[dict] = []
    utterances: list[dict] = []
    for index in range(screen_count):
        screen_id = f"screen_{index + 1:03d}"
        intent_id = f"intent_{index + 1:03d}"
        mapping_id = f"mapping_{index + 1:03d}"
        screens.append(
            {
                "screen_id": screen_id,
                "domain": domains[index % len(domains)],
                "elements": [],
            }
        )
        mappings.append(
            {
                "mapping_id": mapping_id,
                "intent_id": intent_id,
                "screen_id": screen_id,
                "target_element_id": "button",
                "distractor_element_ids": [],
                "difficulty": "easy",
                "notes": "",
            }
        )
        for tier in TIERS:
            utterances.append(
                {
                    "utterance_id": f"{mapping_id}_{tier.lower()}_01",
                    "mapping_id": mapping_id,
                    "intent_id": intent_id,
                    "screen_id": screen_id,
                    "target_element_id": "button",
                    "tier": tier,
                    "text_gold": f"ข้อความ {mapping_id} {tier}",
                    "language_class": "pure_thai",
                    "loanword_spans": [],
                    "generation_notes": "",
                }
            )
    return screens, mappings, utterances


def write_fixture(tmp_path: Path, *, screen_count: int = 20, audio_rows: list[dict] | None = None) -> None:
    screens, mappings, utterances = fixture_records(screen_count)
    write_jsonl(tmp_path / "screens.jsonl", screens)
    write_jsonl(tmp_path / "mappings.jsonl", mappings)
    write_jsonl(tmp_path / "utterances.jsonl", utterances)
    write_jsonl(tmp_path / "audio_manifest.jsonl", audio_rows or [])


def run_make(tmp_path: Path, profile: str = "provisional20") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "scripts/make_splits.py",
            "--screens",
            str(tmp_path / "screens.jsonl"),
            "--mappings",
            str(tmp_path / "mappings.jsonl"),
            "--utterances",
            str(tmp_path / "utterances.jsonl"),
            "--audio-manifest",
            str(tmp_path / "audio_manifest.jsonl"),
            "--output-dir",
            str(tmp_path / "splits"),
            "--profile",
            profile,
            "--overwrite",
        ],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )


def run_validate(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "scripts/validate_splits.py",
            "--dev",
            str(tmp_path / "splits/dev.json"),
            "--test",
            str(tmp_path / "splits/test.json"),
            "--screens",
            str(tmp_path / "screens.jsonl"),
            "--mappings",
            str(tmp_path / "mappings.jsonl"),
            "--utterances",
            str(tmp_path / "utterances.jsonl"),
            "--audio-manifest",
            str(tmp_path / "audio_manifest.jsonl"),
        ],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )


def test_provisional_20_screen_split_succeeds_and_validates(tmp_path: Path) -> None:
    write_fixture(tmp_path)

    result = run_make(tmp_path)
    assert result.returncode == 0, result.stderr + result.stdout
    validation = run_validate(tmp_path)
    assert validation.returncode == 0, validation.stderr + validation.stdout

    dev = read_json(tmp_path / "splits/dev.json")
    test = read_json(tmp_path / "splits/test.json")
    assert dev["profile"] == "provisional20"
    assert dev["provisional"] is True
    assert len(dev["screen_ids"]) == 5
    assert len(test["screen_ids"]) == 15
    assert set(dev["screen_ids"]).isdisjoint(test["screen_ids"])
    assert set(dev["intent_ids"]).isdisjoint(test["intent_ids"])


def test_final_profile_fails_until_enough_screens_exist(tmp_path: Path) -> None:
    write_fixture(tmp_path)

    result = run_make(tmp_path, profile="final")

    assert result.returncode != 0
    assert "final profile requires 65-80 screens" in result.stdout


def test_split_records_threshold_policy_and_counts(tmp_path: Path) -> None:
    write_fixture(tmp_path)
    result = run_make(tmp_path)
    assert result.returncode == 0, result.stderr + result.stdout

    dev = read_json(tmp_path / "splits/dev.json")
    test = read_json(tmp_path / "splits/test.json")
    assert dev["correction_threshold_source"] == "dev_only"
    assert test["correction_threshold_source"] == "dev_only"
    assert dev["counts"]["screens"] == 5
    assert test["counts"]["screens"] == 15
    assert dev["counts"]["utterances"] == len(dev["mapping_ids"]) * 4
    assert test["counts"]["utterances"] == len(test["mapping_ids"]) * 4


def test_split_keeps_screens_with_shared_intent_together(tmp_path: Path) -> None:
    screens, mappings, utterances = fixture_records()
    mappings.append(
        {
            "mapping_id": "mapping_shared_intent",
            "intent_id": "intent_001",
            "screen_id": "screen_002",
            "target_element_id": "button",
            "distractor_element_ids": ["other_button"],
            "difficulty": "medium",
            "notes": "Second screen for the same intent.",
        }
    )
    write_jsonl(tmp_path / "screens.jsonl", screens)
    write_jsonl(tmp_path / "mappings.jsonl", mappings)
    write_jsonl(tmp_path / "utterances.jsonl", utterances)
    write_jsonl(tmp_path / "audio_manifest.jsonl", [])

    result = run_make(tmp_path)
    assert result.returncode == 0, result.stderr + result.stdout
    validation = run_validate(tmp_path)
    assert validation.returncode == 0, validation.stderr + validation.stdout

    dev = read_json(tmp_path / "splits/dev.json")
    test = read_json(tmp_path / "splits/test.json")
    assert ({"screen_001", "screen_002"} <= set(dev["screen_ids"])) or (
        {"screen_001", "screen_002"} <= set(test["screen_ids"])
    )
    assert set(dev["intent_ids"]).isdisjoint(test["intent_ids"])


def test_voice_rule_activates_when_voice_metadata_exists(tmp_path: Path) -> None:
    write_fixture(tmp_path)
    result = run_make(tmp_path)
    assert result.returncode == 0, result.stderr + result.stdout
    dev = read_json(tmp_path / "splits/dev.json")
    test = read_json(tmp_path / "splits/test.json")
    dev_utterance = dev["utterance_ids"][0]
    test_utterance = test["utterance_ids"][0]

    write_fixture(
        tmp_path,
        audio_rows=[
            {"utterance_id": dev_utterance, "voice_id": "shared_voice"},
            {"utterance_id": test_utterance, "voice_id": "test_only_voice"},
        ],
    )
    result = run_make(tmp_path)
    assert result.returncode == 0, result.stderr + result.stdout
    validation = run_validate(tmp_path)
    assert validation.returncode == 0, validation.stderr + validation.stdout
    dev = read_json(tmp_path / "splits/dev.json")
    assert dev["voice_policy"]["status"] == "satisfied"
    assert dev["voice_policy"]["test_only_voice_ids"] == ["test_only_voice"]

    write_fixture(
        tmp_path,
        audio_rows=[
            {"utterance_id": dev_utterance, "voice_id": "shared_voice"},
            {"utterance_id": test_utterance, "voice_id": "shared_voice"},
        ],
    )
    result = run_make(tmp_path)
    assert result.returncode != 0
    assert "no voice is test-only" in result.stdout
