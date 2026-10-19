from scripts.run_correction import (
    choose_unique_candidate,
    failed_record,
    fuzzy_candidates,
    run_method_b,
    run_method_c,
)


SCREEN_LABELS = ["Transfer", "Top up", "Withdraw"]


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
        "english_variants": ["transfer"],
        "thai_meaning_aliases": ["โอนเงิน"],
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


def test_below_threshold_preserves_original():
    result = run_method_b("tap totallydifferent please", SCREEN_LABELS, METHOD_B)
    assert not result.changed
    assert result.corrected_transcript == "tap totallydifferent please"


def test_ambiguous_similar_matches_preserve_original():
    candidates = []
    candidates.extend(fuzzy_candidates("tap tr please", "Transfer", [("tr", "test")], 0.9, 0, "screen"))
    candidates.extend(fuzzy_candidates("tap tr please", "Top up", [("tr", "test")], 0.9, 0, "screen"))
    assert choose_unique_candidate(candidates, 0.9) is None


def test_t3_t4_no_label_injection_without_surface_form():
    result = run_method_c("อยากทำรายการนี้ ต้องกดตรงไหน", SCREEN_LABELS, ALIASES, METHOD_C)
    assert result.matched_screen_label is None
    assert "Transfer" not in result.corrected_transcript
    assert "Top up" not in result.corrected_transcript


def test_t3_t4_allows_only_strong_existing_alias_surface_form():
    result = run_method_c("อยากโอนเงิน ต้องกดตรงไหน", SCREEN_LABELS, ALIASES, METHOD_C)
    assert result.changed
    assert result.corrected_transcript == "อยากTransfer ต้องกดตรงไหน"


def test_failed_record_does_not_invent_correction():
    asr = {
        "asr_id": "asr1",
        "utterance_id": "utt1",
        "audio_id": "audio1",
        "asr_model": "whisper_large_v3_local",
        "transcript": "raw transcript",
    }
    record = failed_record(asr, "A_no_screen_cleanup", "join failed")
    assert record["status"] == "failed"
    assert record["corrected_transcript"] == "raw transcript"
    assert record["changed"] is False
    assert record["error_message"] == "join failed"


def test_method_c_does_not_need_target_metadata():
    result = run_method_c("tap tranfser please", SCREEN_LABELS, ALIASES, METHOD_C)
    assert result.changed
    assert result.corrected_transcript == "tap Transfer please"
