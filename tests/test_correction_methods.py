import json
import shutil
import subprocess
import sys
from pathlib import Path

import jsonschema

from scripts.run_correction import (
    build_alias_variants_for_label,
    cleanup_transcript,
    run_method_a,
    run_method_b,
    run_method_c,
)


SCREEN = {
    "screen_id": "mock_finance_001",
    "domain": "mock_finance",
    "visible_lexicon": ["Transfer", "Top up", "Withdraw", "History"],
    "elements": [
        {"label": "Transfer"},
        {"label": "Top up"},
        {"label": "Withdraw"},
        {"label": "History"},
    ],
}


METHOD_B = {
    "string_similarity_threshold": 0.95,
    "max_edit_distance": 1,
    "min_confidence": 0.94,
}


METHOD_C = {
    "string_similarity_threshold": 0.94,
    "alias_similarity_threshold": 0.92,
    "phonetic_similarity_threshold": 0.90,
    "max_edit_distance": 1,
    "min_confidence": 0.93,
}


ALIASES = [
    {
        "canonical_label": "Transfer",
        "english_variants": ["transfer", "send money"],
        "thai_meaning_aliases": ["โอนเงิน", "ส่งเงิน"],
        "thai_phonetic_aliases": ["แทรนสเฟอร์"],
        "latin_normalized_variants": ["tranfser"],
    },
    {
        "canonical_label": "Top up",
        "english_variants": ["top up"],
        "thai_meaning_aliases": ["เติมเงิน"],
        "thai_phonetic_aliases": ["ท็อปอัป"],
        "latin_normalized_variants": ["topup"],
    },
]


def test_method_a_normalizes_unicode_whitespace_and_punctuation():
    result = run_method_a("  Transfer   now!!!  ")
    assert result.changed
    assert result.corrected_transcript == "Transfer now!"
    assert result.matched_screen_label is None


def test_method_b_corrects_exact_visible_label_case_only():
    result = run_method_b("tap transfer please", SCREEN["visible_lexicon"], METHOD_B)
    assert result.changed
    assert result.corrected_transcript == "tap Transfer please"
    assert result.matched_screen_label == "Transfer"
    assert result.match_score >= METHOD_B["min_confidence"]


def test_method_b_does_not_use_alias_table():
    result = run_method_b("ช่วยโอนเงินหน่อย", SCREEN["visible_lexicon"], METHOD_B)
    assert not result.changed
    assert result.corrected_transcript == "ช่วยโอนเงินหน่อย"


def test_method_c_uses_alias_for_visible_label():
    result = run_method_c("ช่วยโอนเงินหน่อย", SCREEN["visible_lexicon"], ALIASES, METHOD_C)
    assert result.changed
    assert result.corrected_transcript == "ช่วยTransferหน่อย"
    assert result.matched_screen_label == "Transfer"


def test_method_c_uses_latin_normalized_variant():
    result = run_method_c("tap tranfser please", SCREEN["visible_lexicon"], ALIASES, METHOD_C)
    assert result.changed
    assert result.corrected_transcript == "tap Transfer please"


def test_alias_variants_are_label_only():
    variants = build_alias_variants_for_label("Transfer", ALIASES)
    values = {value for value, _source in variants}
    assert "transfer" in values
    assert "โอนเงิน" in values
    assert all("button" not in value for value in values)


def test_schema_accepts_valid_correction_record():
    with open("schemas/correction_output.schema.json", encoding="utf-8") as f:
        schema = json.load(f)
    record = {
        "correction_id": "asr1__A_no_screen_cleanup",
        "asr_id": "asr1",
        "utterance_id": "utt1",
        "audio_id": "aud1",
        "screen_id": "screen1",
        "asr_model": "whisper_large_v3_local",
        "method": "A_no_screen_cleanup",
        "input_transcript": "hello",
        "corrected_transcript": "hello",
        "changed": False,
        "matched_screen_label": None,
        "match_score": None,
        "confidence": None,
        "correction_reason": "no_cleanup_needed",
        "tier": "T1_verbatim",
        "domain": "mock_finance",
        "language_class": "pure_thai",
        "tts_engine": "openai",
        "voice_id": "voice_01",
        "status": "success",
        "error_message": "",
        "changes": [],
        "created_at": "2026-07-19T00:00:00Z",
        "params": {},
    }
    jsonschema.Draft202012Validator(schema).validate(record)


def test_runner_dry_run_limit_does_not_write():
    tmp_dir = Path(".pytest_correction_tmp")
    shutil.rmtree(tmp_dir, ignore_errors=True)
    tmp_dir.mkdir()
    output = tmp_dir / "corrections.jsonl"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_correction.py",
            "--limit",
            "1",
            "--dry-run",
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert "records_built" in result.stdout
    assert not output.exists()
    shutil.rmtree(tmp_dir, ignore_errors=True)
