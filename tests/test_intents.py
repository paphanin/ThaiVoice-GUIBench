from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INTENT_SCHEMA = ROOT / "schemas" / "intent.schema.json"
MAPPING_SCHEMA = ROOT / "schemas" / "intent_screen_target.schema.json"


BASE_INTENT = {
    "intent_id": "shopping_find_products",
    "domain": "shopping",
    "canonical_en": "Find products",
    "canonical_th": "หาสินค้า",
    "description": "Abstract shopping intent for locating products.",
    "allowed_tiers": ["T1_verbatim", "T2_paraphrase", "T3_intent", "T4_visual_positional"],
    "semantic_keywords_th": ["หา", "สินค้า", "ค้น"],
    "semantic_keywords_en": ["find", "product", "search"],
    "notes": "Test fixture intent.",
}

BASE_MAPPING = {
    "mapping_id": "map_shopping_find_products_001",
    "intent_id": "shopping_find_products",
    "screen_id": "shopping_fixture_001",
    "target_element_id": "search_button",
    "distractor_element_ids": ["sort_button", "filter_button"],
    "difficulty": "easy",
    "notes": "Test fixture mapping.",
}

BASE_SCREEN = {
    "screen_id": "shopping_fixture_001",
    "domain": "shopping",
    "elements": [
        {"element_id": "search_button"},
        {"element_id": "sort_button"},
        {"element_id": "filter_button"},
    ],
}


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_validator(tmp_path: Path, intents: list[dict], mappings: list[dict], screens: list[dict] | None = None) -> subprocess.CompletedProcess[str]:
    intents_path = tmp_path / "intents.jsonl"
    mappings_path = tmp_path / "intent_screen_targets.jsonl"
    screens_path = tmp_path / "screens.jsonl"
    write_jsonl(intents_path, intents)
    write_jsonl(mappings_path, mappings)
    if screens is not None:
        write_jsonl(screens_path, screens)

    return subprocess.run(
        [
            sys.executable,
            "scripts/validate_intents.py",
            "--intents",
            str(intents_path),
            "--mappings",
            str(mappings_path),
            "--screens",
            str(screens_path),
            "--intent-schema",
            str(INTENT_SCHEMA),
            "--mapping-schema",
            str(MAPPING_SCHEMA),
        ],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )


def test_valid_intent_records_and_tiny_screen_lookup(tmp_path: Path) -> None:
    result = run_validator(tmp_path, [BASE_INTENT], [BASE_MAPPING], [BASE_SCREEN])

    assert result.returncode == 0, result.stderr + result.stdout
    assert "Intent validation passed" in result.stdout


def test_duplicate_intent_ids_fail(tmp_path: Path) -> None:
    duplicate = copy.deepcopy(BASE_INTENT)
    duplicate["canonical_en"] = "Find items"

    result = run_validator(tmp_path, [BASE_INTENT, duplicate], [BASE_MAPPING], [BASE_SCREEN])

    assert result.returncode != 0
    assert "duplicate intent_id" in result.stdout


def test_mapping_references_missing_intent_fails(tmp_path: Path) -> None:
    mapping = copy.deepcopy(BASE_MAPPING)
    mapping["intent_id"] = "shopping_missing_intent"

    result = run_validator(tmp_path, [BASE_INTENT], [mapping], [BASE_SCREEN])

    assert result.returncode != 0
    assert "references missing intent_id" in result.stdout


def test_target_cannot_also_be_distractor(tmp_path: Path) -> None:
    mapping = copy.deepcopy(BASE_MAPPING)
    mapping["distractor_element_ids"] = ["search_button", "sort_button"]

    result = run_validator(tmp_path, [BASE_INTENT], [mapping], [BASE_SCREEN])

    assert result.returncode != 0
    assert "target_element_id must not also appear" in result.stdout


def test_missing_target_and_distractor_elements_fail_with_tiny_screen(tmp_path: Path) -> None:
    mapping = copy.deepcopy(BASE_MAPPING)
    mapping["target_element_id"] = "missing_target"
    mapping["distractor_element_ids"] = ["sort_button", "missing_distractor"]

    result = run_validator(tmp_path, [BASE_INTENT], [mapping], [BASE_SCREEN])

    assert result.returncode != 0
    assert "target_element_id `missing_target` does not exist" in result.stdout
    assert "distractor_element_id `missing_distractor` does not exist" in result.stdout


def test_unmapped_screen_fails(tmp_path: Path) -> None:
    unmapped_screen = copy.deepcopy(BASE_SCREEN)
    unmapped_screen["screen_id"] = "shopping_fixture_002"

    result = run_validator(tmp_path, [BASE_INTENT], [BASE_MAPPING], [BASE_SCREEN, unmapped_screen])

    assert result.returncode != 0
    assert "screen shopping_fixture_002: must have at least one intent-target mapping" in result.stdout
