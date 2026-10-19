from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TIERS = {"T1_verbatim", "T2_paraphrase", "T3_intent", "T4_visual_positional"}


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(args, cwd=ROOT, check=False, text=True, capture_output=True, env=env, encoding="utf-8")


def load_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def screen_target_labels() -> dict[tuple[str, str], str]:
    screens = load_jsonl(ROOT / "data/screens/screens.jsonl")
    labels: dict[tuple[str, str], str] = {}
    for screen in screens:
        for element in screen["elements"]:
            labels[(screen["screen_id"], element["element_id"])] = element["label"]
    return labels


def generate_fixture(tmp_path: Path) -> Path:
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
    return output


def test_generator_creates_all_four_tiers_for_every_mapping(tmp_path: Path) -> None:
    output = generate_fixture(tmp_path)
    records = load_jsonl(output)
    mappings = load_jsonl(ROOT / "data/intents/intent_screen_targets.jsonl")
    tiers_by_mapping: dict[str, set[str]] = defaultdict(set)
    for record in records:
        tiers_by_mapping[record["mapping_id"]].add(record["tier"])

    assert len(records) == len(mappings) * 4
    assert all(tiers_by_mapping[mapping["mapping_id"]] == TIERS for mapping in mappings)


def test_t1_can_include_target_label(tmp_path: Path) -> None:
    output = generate_fixture(tmp_path)
    labels = screen_target_labels()
    t1_records = [record for record in load_jsonl(output) if record["tier"] == "T1_verbatim"]

    assert t1_records
    assert all(labels[(record["screen_id"], record["target_element_id"])] in record["text_gold"] for record in t1_records)


def test_t2_t3_t4_do_not_include_target_label(tmp_path: Path) -> None:
    output = generate_fixture(tmp_path)
    labels = screen_target_labels()
    for record in load_jsonl(output):
        if record["tier"] == "T1_verbatim":
            continue
        label = labels[(record["screen_id"], record["target_element_id"])]
        assert label.lower() not in record["text_gold"].lower()


def test_generated_utterances_do_not_use_gendered_polite_particles(tmp_path: Path) -> None:
    output = generate_fixture(tmp_path)
    gendered_particles = ("ครับ", "ค่ะ", "คะ")

    for record in load_jsonl(output):
        assert not any(particle in record["text_gold"] for particle in gendered_particles)


def test_generated_fixture_validates(tmp_path: Path) -> None:
    output = generate_fixture(tmp_path)
    result = run_command(
        [
            sys.executable,
            "scripts/validate_utterances.py",
            "--utterances",
            str(output),
            "--mappings",
            "data/intents/intent_screen_targets.jsonl",
            "--screens",
            "data/screens/screens.jsonl",
            "--schema",
            "schemas/utterance.schema.json",
        ]
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "Utterance validation passed" in result.stdout
