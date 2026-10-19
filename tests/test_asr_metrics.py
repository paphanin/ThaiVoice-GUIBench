from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import evaluate_asr  # noqa: E402


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def whitespace_tokenizer(text: str) -> list[str]:
    return [token for token in text.split() if token]


def utterance(utterance_id: str = "utt_001", loanword_spans: list[dict] | None = None) -> dict:
    return {
        "utterance_id": utterance_id,
        "mapping_id": "map_001",
        "intent_id": "search_product",
        "screen_id": "shopping_001",
        "target_element_id": "search_button",
        "tier": "T1_verbatim",
        "text_gold": "กด Search ให้หน่อย",
        "language_class": "code_switched",
        "loanword_spans": loanword_spans if loanword_spans is not None else [{"text": "Search", "start": 3, "end": 9}],
        "generation_notes": "T1 may include the visible target label.",
    }


def manifest_row(audio_id: str = "openai__voice_01__test__utt_001_t1_verbatim_01") -> dict:
    return {
        "audio_id": audio_id,
        "utterance_id": "utt_001",
        "audio_path": "data/audio/wav/openai/voice_01/test__utt_001.wav",
        "duration_ms": 1000,
        "engine_id": "openai",
        "voice_id": "voice_01",
        "split": "test",
        "include_in_experiments": True,
    }


def asr_record(
    model: str,
    audio_id: str = "openai__voice_01__test__utt_001_t1_verbatim_01",
    status: str = "success",
    transcript: str = "กด Search ให้หน่อย",
    error_message: str = "",
) -> dict:
    return {
        "asr_id": f"{audio_id}__{model}",
        "audio_id": audio_id,
        "utterance_id": "utt_001",
        "asr_model": model,
        "backend": "faster_whisper" if model == "whisper_large_v3_local" else "typhoon_api",
        "transcript": transcript,
        "status": status,
        "error_message": error_message,
        "audio_path": "data/audio/wav/openai/voice_01/test__utt_001.wav",
        "audio_duration_ms": 1000,
        "latency_ms": 100,
        "rtf": 0.1,
        "created_at": "2026-07-09T00:00:00Z",
        "params": {},
    }


def test_cer_exact_match_is_zero() -> None:
    assert evaluate_asr.character_error_rate("abc", "abc") == 0


def test_cer_substitution_is_greater_than_zero() -> None:
    assert evaluate_asr.character_error_rate("abc", "axc") > 0


def test_thai_wer_runs_through_tokenizer_path() -> None:
    assert evaluate_asr.word_error_rate("กด Search", "กด Search", tokenizer=whitespace_tokenizer) == 0


def test_loanword_exact_match() -> None:
    loanwords = evaluate_asr.loanwords_for_utterance(utterance())
    count, errors, rate = evaluate_asr.loanword_error_counts(loanwords, "กด Search ให้หน่อย")

    assert count == 1
    assert errors == 0
    assert rate == 0


def test_failed_asr_outputs_counted_but_excluded_from_means(tmp_path: Path) -> None:
    audio_id = "openai__voice_01__test__utt_001_t1_verbatim_01"
    write_jsonl(tmp_path / "utterances.jsonl", [utterance()])
    write_jsonl(tmp_path / "audio_manifest.jsonl", [manifest_row(audio_id)])
    write_jsonl(
        tmp_path / "asr" / "whisper_large_v3_local.jsonl",
        [asr_record("whisper_large_v3_local", audio_id, transcript="กด Search ให้หน่อย")],
    )
    write_jsonl(
        tmp_path / "asr" / "typhoon_asr_api.jsonl",
        [asr_record("typhoon_asr_api", audio_id, status="failed", transcript="", error_message="api error")],
    )

    result = evaluate_asr.evaluate_asr(
        tmp_path / "utterances.jsonl",
        tmp_path / "audio_manifest.jsonl",
        tmp_path / "asr",
        tmp_path / "out",
        tokenizer=whitespace_tokenizer,
    )

    by_model = {row["asr_model"]: row for row in result["by_model"]}
    assert by_model["whisper_large_v3_local"]["mean_cer"] == 0
    assert by_model["typhoon_asr_api"]["failed_count"] == 1
    assert by_model["typhoon_asr_api"]["mean_cer"] is None


def test_missing_required_asr_file_fails_unless_allowed(tmp_path: Path) -> None:
    audio_id = "openai__voice_01__test__utt_001_t1_verbatim_01"
    write_jsonl(tmp_path / "utterances.jsonl", [utterance()])
    write_jsonl(tmp_path / "audio_manifest.jsonl", [manifest_row(audio_id)])
    write_jsonl(
        tmp_path / "asr" / "whisper_large_v3_local.jsonl",
        [asr_record("whisper_large_v3_local", audio_id)],
    )

    try:
        evaluate_asr.evaluate_asr(
            tmp_path / "utterances.jsonl",
            tmp_path / "audio_manifest.jsonl",
            tmp_path / "asr",
            tmp_path / "out",
            tokenizer=whitespace_tokenizer,
        )
    except ValueError as exc:
        assert "missing required ASR output files" in str(exc)
    else:
        raise AssertionError("expected missing required ASR file to fail")

    result = evaluate_asr.evaluate_asr(
        tmp_path / "utterances.jsonl",
        tmp_path / "audio_manifest.jsonl",
        tmp_path / "asr",
        tmp_path / "out",
        allow_missing_models=True,
        tokenizer=whitespace_tokenizer,
    )
    assert len(result["metrics"]) == 1
