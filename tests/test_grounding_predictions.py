from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import run_grounding  # noqa: E402

VALIDATOR = REPO_ROOT / "scripts" / "validate_grounding_predictions.py"
SCHEMA = REPO_ROOT / "schemas" / "grounding_prediction.schema.json"


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def base_files(tmp_path: Path) -> tuple[Path, Path, Path]:
    image_path = tmp_path / "screen.png"
    image_path.write_bytes(b"not a real png but exists")
    screens = [
        {
            "screen_id": "screen_001",
            "width": 100,
            "height": 200,
            "image_path": str(image_path),
            "elements": [
                {"element_id": "button_1", "bbox": [10, 20, 50, 80], "label": "OK", "role": "button"}
            ],
        }
    ]
    utterances = [
        {
            "utterance_id": "utt_001",
            "screen_id": "screen_001",
            "target_element_id": "button_1",
            "text_gold": "กด OK",
        }
    ]
    manifest = [
        {
            "audio_id": "audio_001",
            "utterance_id": "utt_001",
            "include_in_experiments": True,
        }
    ]
    screens_path = tmp_path / "screens.jsonl"
    utterances_path = tmp_path / "utterances.jsonl"
    manifest_path = tmp_path / "audio_manifest.jsonl"
    write_jsonl(screens_path, screens)
    write_jsonl(utterances_path, utterances)
    write_jsonl(manifest_path, manifest)
    return screens_path, utterances_path, manifest_path


def valid_record(**updates) -> dict:
    record = {
        "prediction_id": "G1__gold__utt_001",
        "utterance_id": "utt_001",
        "audio_id": None,
        "screen_id": "screen_001",
        "target_element_id": "button_1",
        "grounding_model": "G1",
        "input_condition": "gold",
        "asr_model": None,
        "transcript_source": "gold",
        "transcript": "กด OK",
        "pred_x": 30,
        "pred_y": 50,
        "pred_label": "OK",
        "confidence": 0.9,
        "status": "success",
        "failure_type": None,
        "error_message": "",
        "latency_ms": 10,
        "raw_response_path": "data/predictions/raw/G1__gold__utt_001.json",
        "created_at": "2026-07-09T00:00:00Z",
        "params": {"backend": "api_vision", "provider": "openai", "model_name": "gpt-5.5"},
    }
    record.update(updates)
    return record


def run_validator(tmp_path: Path, records: list[dict]) -> subprocess.CompletedProcess[str]:
    screens_path, utterances_path, manifest_path = base_files(tmp_path)
    predictions_path = tmp_path / "predictions.jsonl"
    write_jsonl(predictions_path, records)
    return subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--predictions",
            str(predictions_path),
            "--screens",
            str(screens_path),
            "--utterances",
            str(utterances_path),
            "--manifest",
            str(manifest_path),
            "--schema",
            str(SCHEMA),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_valid_prediction_passes(tmp_path: Path) -> None:
    result = run_validator(tmp_path, [valid_record()])
    assert result.returncode == 0, result.stdout + result.stderr


def test_duplicate_prediction_ids_fail(tmp_path: Path) -> None:
    result = run_validator(tmp_path, [valid_record(), valid_record()])
    assert result.returncode != 0
    assert "duplicate prediction_id" in result.stdout


def test_success_without_coordinates_fails(tmp_path: Path) -> None:
    result = run_validator(tmp_path, [valid_record(pred_x=None)])
    assert result.returncode != 0
    assert "numeric pred_x and pred_y" in result.stdout


def test_success_with_out_of_bounds_coordinates_passes_prediction_validation(tmp_path: Path) -> None:
    result = run_validator(tmp_path, [valid_record(pred_x=-324, pred_y=-309)])
    assert result.returncode == 0, result.stdout + result.stderr


def test_failed_without_error_message_fails(tmp_path: Path) -> None:
    result = run_validator(
        tmp_path,
        [valid_record(status="failed", pred_x=None, pred_y=None, confidence=None, error_message="")],
    )
    assert result.returncode != 0
    assert "failed record requires non-empty error_message" in result.stdout


def test_asr_condition_without_audio_id_fails(tmp_path: Path) -> None:
    result = run_validator(
        tmp_path,
        [
            valid_record(
                prediction_id="G1__asr_whisper_large_v3_local__audio_001",
                input_condition="asr_whisper_large_v3_local",
                asr_model="whisper_large_v3_local",
                transcript_source="whisper_large_v3_local",
            )
        ],
    )
    assert result.returncode != 0
    assert "ASR condition requires audio_id" in result.stdout


def test_corrected_condition_requires_audio_id(tmp_path: Path) -> None:
    result = run_validator(
        tmp_path,
        [
            valid_record(
                prediction_id="G1__corrected_A_no_screen_cleanup_whisper__audio_001",
                input_condition="corrected_A_no_screen_cleanup_whisper",
                asr_model="whisper_large_v3_local",
                transcript_source="corrected:A_no_screen_cleanup:whisper_large_v3_local",
            )
        ],
    )
    assert result.returncode != 0
    assert "ASR condition requires audio_id" in result.stdout


def test_corrected_condition_with_audio_id_passes(tmp_path: Path) -> None:
    result = run_validator(
        tmp_path,
        [
            valid_record(
                prediction_id="G1__corrected_A_no_screen_cleanup_whisper__audio_001",
                input_condition="corrected_A_no_screen_cleanup_whisper",
                audio_id="audio_001",
                asr_model="whisper_large_v3_local",
                transcript_source="corrected:A_no_screen_cleanup:whisper_large_v3_local",
            )
        ],
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_gold_condition_with_non_null_audio_id_fails(tmp_path: Path) -> None:
    result = run_validator(tmp_path, [valid_record(audio_id="audio_001")])
    assert result.returncode != 0
    assert "gold condition must have audio_id=null" in result.stdout


def test_invalid_input_condition_fails(tmp_path: Path) -> None:
    result = run_validator(tmp_path, [valid_record(input_condition="bad_condition")])
    assert result.returncode != 0
    assert "invalid input_condition" in result.stdout or "schema error" in result.stdout


def test_parse_ui_tars_direct_json_coordinates() -> None:
    parsed = run_grounding.parse_ui_tars_output(
        '{"pred_x": 123, "pred_y": 456, "pred_label": "OK", "confidence": 0.7}',
        width=1000,
        height=1000,
    )
    assert parsed["pred_x"] == 123
    assert parsed["pred_y"] == 456
    assert parsed["pred_label"] == "OK"
    assert parsed["confidence"] == 0.7
    assert parsed["parse_notes"]["parse_source"] == "json"
    assert parsed["parse_notes"]["coordinate_format"] == "scale_1000"


def test_parse_ui_tars_click_xy_output() -> None:
    parsed = run_grounding.parse_ui_tars_output("click(x=123, y=456)", width=1000, height=1000)
    assert parsed["pred_x"] == 123
    assert parsed["pred_y"] == 456
    assert parsed["parse_notes"]["parse_source"] == "click_xy"


def test_parse_ui_tars_start_box_output() -> None:
    parsed = run_grounding.parse_ui_tars_output(
        "Thought: click the button\nAction: click(start_box='<|box_start|>(500,250)<|box_end|>')",
        width=1080,
        height=1920,
    )
    assert parsed["pred_x"] == 540
    assert parsed["pred_y"] == 480
    assert parsed["parse_notes"]["parse_source"] == "start_box_text"
    assert parsed["parse_notes"]["coordinate_format"] == "scale_1000"


def test_parse_ui_tars_normalized_coordinates() -> None:
    parsed = run_grounding.parse_ui_tars_output(
        '{"pred_x": 0.5, "pred_y": 0.25, "confidence": 0.8}',
        width=1080,
        height=1920,
    )
    assert parsed["pred_x"] == 540
    assert parsed["pred_y"] == 480
    assert parsed["parse_notes"]["coordinate_format"] == "normalized_0_1"


def test_parse_ui_tars_1000_scale_coordinates() -> None:
    parsed = run_grounding.parse_ui_tars_output(
        '{"action": "click", "coordinate": [500, 250]}',
        width=1080,
        height=1920,
    )
    assert parsed["pred_x"] == 540
    assert parsed["pred_y"] == 480
    assert parsed["parse_notes"]["parse_source"] == "action_json"
    assert parsed["parse_notes"]["coordinate_format"] == "scale_1000"


def test_parse_ui_tars_malformed_pred_x_pair() -> None:
    parsed = run_grounding.parse_ui_tars_output(
        '{"pred_x": 300, 526, "pred_label": "hydrationBottle", "confidence": 0.8898964}',
        width=1080,
        height=1920,
    )
    assert parsed["pred_x"] == 324
    assert parsed["pred_y"] == pytest.approx(1009.92)
    assert parsed["parse_notes"]["parse_source"] == "malformed_pred_x_pair"
    assert parsed["parse_notes"]["coordinate_format"] == "scale_1000"


def test_parse_ui_tars_malformed_pred_x_pair_before_closing_brace() -> None:
    parsed = run_grounding.parse_ui_tars_output(
        '{"pred_x": 299, 527}',
        width=1080,
        height=1920,
        coordinate_mode="absolute",
    )
    assert parsed["pred_x"] == 299
    assert parsed["pred_y"] == 527
    assert parsed["parse_notes"]["parse_source"] == "malformed_pred_x_pair"
    assert parsed["parse_notes"]["coordinate_format"] == "absolute"


def test_parse_ui_tars_incomplete_pred_x_array() -> None:
    parsed = run_grounding.parse_ui_tars_output('{"pred_x": [822, 518]', width=1080, height=1920)
    assert parsed["pred_x"] == 887.76
    assert parsed["pred_y"] == pytest.approx(994.56)
    assert parsed["parse_notes"]["parse_source"] == "pred_x_array_text"
    assert parsed["parse_notes"]["coordinate_format"] == "scale_1000"


def test_parse_ui_tars_pred_x_string_pair_json() -> None:
    parsed = run_grounding.parse_ui_tars_output(
        '{"pred_x": "807,520", "pred_label": "button", "confidence": 0.98}',
        width=1080,
        height=1920,
        coordinate_mode="absolute",
    )
    assert parsed["pred_x"] == 807
    assert parsed["pred_y"] == 520
    assert parsed["parse_notes"]["parse_source"] == "pred_x_string_pair_json"
    assert parsed["parse_notes"]["coordinate_format"] == "absolute"


def test_parse_ui_tars_nonsense_pred_x_string_fails() -> None:
    with pytest.raises(ValueError, match="JSON response did not contain pred_x/pred_y or click coordinate"):
        run_grounding.parse_ui_tars_output(
            '{"pred_x": " Becker reason: Not Happens To David"}',
            width=1080,
            height=1920,
            coordinate_mode="absolute",
        )


def test_failed_ui_tars_parse_creates_failed_record(tmp_path: Path, monkeypatch) -> None:
    image_path = tmp_path / "screen.png"
    image_path.write_bytes(b"fake")
    example = run_grounding.GroundingExample(
        prediction_id="G2__gold__utt_001",
        utterance_id="utt_001",
        audio_id=None,
        screen_id="screen_001",
        target_element_id="button_1",
        input_condition="gold",
        asr_model=None,
        transcript_source="gold",
        transcript="กด OK",
        screen={"screen_id": "screen_001", "image_path": str(image_path), "width": 100, "height": 200},
    )

    def fail_parse(*args, **kwargs):
        raise ValueError("could not parse UI-TARS click coordinates")

    monkeypatch.setattr(run_grounding, "local_openai_compatible_vision_call", fail_parse)
    record = run_grounding.run_model(
        example,
        {
            "_model_key": "G2",
            "backend": "local_openai_compatible_vision",
            "provider": "ui_tars",
            "model_name": "ByteDance-Seed/UI-TARS-1.5-7B",
        },
        tmp_path / "raw",
        Path(),
    )
    assert record["status"] == "failed"
    assert record["failure_type"] == "unparseable_model_output"
    assert record["pred_x"] is None
    assert record["pred_y"] is None
    assert "could not parse UI-TARS click coordinates" in record["error_message"]


def test_failed_ui_tars_parse_saves_raw_response(tmp_path: Path, monkeypatch) -> None:
    image_path = tmp_path / "screen.png"
    image_path.write_bytes(b"fake")
    example = run_grounding.GroundingExample(
        prediction_id="G2__gold__utt_001",
        utterance_id="utt_001",
        audio_id=None,
        screen_id="screen_001",
        target_element_id="button_1",
        input_condition="gold",
        asr_model=None,
        transcript_source="gold",
        transcript="กด OK",
        screen={"screen_id": "screen_001", "image_path": str(image_path), "width": 100, "height": 200},
    )

    def fail_parse(*args, **kwargs):
        raise run_grounding.ModelOutputParseError(
            "could not parse UI-TARS click coordinates",
            raw_response='{"choices":[{"message":{"content":"unparseable"}}]}',
            output_text="unparseable",
        )

    monkeypatch.setattr(run_grounding, "local_openai_compatible_vision_call", fail_parse)
    record = run_grounding.run_model(
        example,
        {
            "_model_key": "G2",
            "backend": "local_openai_compatible_vision",
            "provider": "ui_tars",
            "model_name": "ByteDance-Seed/UI-TARS-1.5-7B",
        },
        tmp_path / "raw",
        Path(),
    )
    assert record["status"] == "failed"
    assert record["failure_type"] == "unparseable_model_output"
    assert record["raw_response_path"] is not None
    assert Path(record["raw_response_path"]).exists()


def test_g2_prediction_ids_do_not_collide_with_g1() -> None:
    g1_id = run_grounding.stable_prediction_id("G1", "gold", "utt_001", None)
    g2_id = run_grounding.stable_prediction_id("G2", "gold", "utt_001", None)
    assert g1_id == "G1__gold__utt_001"
    assert g2_id == "G2__gold__utt_001"
    assert g1_id != g2_id


def test_build_corrected_examples_uses_corrected_transcript(tmp_path: Path) -> None:
    corrections_path = tmp_path / "corrections.jsonl"
    write_jsonl(
        corrections_path,
        [
            {
                "status": "success",
                "asr_model": "whisper_large_v3_local",
                "method": "A_no_screen_cleanup",
                "audio_id": "audio_001",
                "utterance_id": "utt_001",
                "corrected_transcript": "corrected command",
            }
        ],
    )
    utterances = {
        "utt_001": {
            "utterance_id": "utt_001",
            "screen_id": "screen_001",
            "target_element_id": "button_1",
        }
    }
    screens = {"screen_001": {"screen_id": "screen_001"}}
    audio = {"audio_001": {"audio_id": "audio_001"}}
    examples = run_grounding.build_corrected_examples(
        "G1",
        "corrected_A_no_screen_cleanup_whisper",
        corrections_path,
        utterances,
        screens,
        audio,
    )
    assert len(examples) == 1
    assert examples[0].transcript == "corrected command"
    assert examples[0].input_condition == "corrected_A_no_screen_cleanup_whisper"
    assert examples[0].asr_model == "whisper_large_v3_local"
