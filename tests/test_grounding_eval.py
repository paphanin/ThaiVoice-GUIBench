from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import evaluate_grounding  # noqa: E402


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def screen() -> dict:
    return {
        "screen_id": "screen_001",
        "domain": "settings",
        "width": 100,
        "height": 100,
        "elements": [
            {"element_id": "outer", "label": "Outer", "bbox": [0, 0, 100, 100]},
            {"element_id": "inner", "label": "Inner", "bbox": [10, 10, 20, 20]},
            {"element_id": "other", "label": "Other", "bbox": [40, 40, 60, 60]},
        ],
    }


def utterance() -> dict:
    return {
        "utterance_id": "utt_001",
        "screen_id": "screen_001",
        "target_element_id": "inner",
        "tier": "T1_verbatim",
        "language_class": "pure_thai",
        "text_gold": "กด inner",
    }


def manifest() -> dict:
    return {
        "audio_id": "audio_001",
        "utterance_id": "utt_001",
        "engine_id": "openai",
        "voice_id": "voice_01",
        "include_in_experiments": True,
    }


def prediction(**updates) -> dict:
    record = {
        "prediction_id": "G1__gold__utt_001",
        "utterance_id": "utt_001",
        "audio_id": None,
        "screen_id": "screen_001",
        "target_element_id": "inner",
        "grounding_model": "G1",
        "input_condition": "gold",
        "asr_model": None,
        "pred_x": 15,
        "pred_y": 15,
        "pred_label": "Inner",
        "status": "success",
        "failure_type": None,
        "error_message": "",
    }
    record.update(updates)
    return record


def test_point_inside_bbox_returns_true() -> None:
    assert evaluate_grounding.point_in_bbox(15, 15, [10, 10, 20, 20]) is True


def test_point_outside_bbox_returns_false() -> None:
    assert evaluate_grounding.point_in_bbox(25, 15, [10, 10, 20, 20]) is False


def test_derived_element_id_works() -> None:
    assert evaluate_grounding.derive_pred_element_id(screen(), 50, 50) == "other"


def test_overlapping_bboxes_choose_smallest_area() -> None:
    assert evaluate_grounding.derive_pred_element_id(screen(), 15, 15) == "inner"


def test_no_containing_bbox_returns_null() -> None:
    local_screen = {
        "screen_id": "screen_002",
        "elements": [{"element_id": "button", "label": "Button", "bbox": [10, 10, 20, 20]}],
    }
    assert evaluate_grounding.derive_pred_element_id(local_screen, 90, 90) is None


def test_click_accuracy_is_computed_correctly() -> None:
    rows = [
        {
            "status": "success",
            "point_in_image": True,
            "click_in_target_bbox": True,
            "element_match": True,
            "input_condition": "gold",
        },
        {
            "status": "success",
            "point_in_image": False,
            "click_in_target_bbox": False,
            "element_match": False,
            "input_condition": "gold",
        },
        {
            "status": "failed",
            "point_in_image": False,
            "click_in_target_bbox": False,
            "element_match": False,
            "input_condition": "gold",
        },
    ]
    summary = evaluate_grounding.summarize(rows, ("input_condition",))[0]
    assert summary["n"] == 2
    assert summary["click_accuracy"] == 0.5
    assert summary["n_total"] == 3
    assert summary["n_success_parse"] == 2
    assert summary["n_failed_parse"] == 1
    assert summary["parse_failure_rate"] == 1 / 3
    assert summary["point_in_image_rate"] == 1 / 3
    assert summary["n_success"] == 2
    assert summary["n_failed"] == 1
    assert summary["failure_rate"] == 1 / 3
    assert summary["click_accuracy_including_failures"] == 1 / 3
    assert summary["click_accuracy_success_only"] == 0.5
    assert summary["element_accuracy"] == 0.5
    assert summary["failure_count"] == 1


def test_failed_prediction_is_counted_as_incorrect() -> None:
    record = evaluate_grounding.evaluation_record(
        prediction(
            status="failed",
            pred_x=None,
            pred_y=None,
            pred_label="",
            failure_type="unparseable_model_output",
            error_message="JSON response did not contain pred_x/pred_y or click coordinate",
        ),
        {"screen_001": screen()},
        {"utt_001": utterance()},
        {"audio_001": manifest()},
    )
    assert record["click_in_target_bbox"] is False
    assert record["element_match"] is False
    assert record["point_in_image"] is False
    assert record["pred_element_id"] is None
    assert record["failure_type"] == "unparseable_model_output"


def test_legacy_unparseable_failure_type_is_inferred() -> None:
    normalized = evaluate_grounding.normalize_prediction_record(
        prediction(
            status="failed",
            pred_x=None,
            pred_y=None,
            pred_label="",
            error_message="JSON response did not contain pred_x/pred_y or click coordinate",
        )
    )
    record = evaluate_grounding.evaluation_record(
        normalized,
        {"screen_001": screen()},
        {"utt_001": utterance()},
        {"audio_001": manifest()},
    )
    assert record["failure_type"] == "unparseable_model_output"
    assert record["click_in_target_bbox"] is False
    assert record["element_match"] is False
    assert record["point_in_image"] is False


def test_missing_failed_failure_type_is_normalized() -> None:
    normalized = evaluate_grounding.normalize_prediction_record(
        prediction(
            status="failed",
            pred_x=None,
            pred_y=None,
            pred_label="",
            failure_type=None,
            error_message="some older failure",
        )
    )
    assert normalized["failure_type"] == "unparseable_model_output"


def test_out_of_bounds_success_is_incorrect() -> None:
    record = evaluate_grounding.evaluation_record(
        prediction(pred_x=-324, pred_y=-309),
        {"screen_001": screen()},
        {"utt_001": utterance()},
        {"audio_001": manifest()},
    )
    assert record["status"] == "success"
    assert record["point_in_image"] is False
    assert record["click_in_target_bbox"] is False
    assert record["element_match"] is False
    assert record["pred_element_id"] is None


def test_asr_records_get_voice_metadata_from_manifest() -> None:
    record = evaluate_grounding.evaluation_record(
        prediction(
            prediction_id="G1__asr_whisper_large_v3_local__audio_001",
            input_condition="asr_whisper_large_v3_local",
            audio_id="audio_001",
            asr_model="whisper_large_v3_local",
        ),
        {"screen_001": screen()},
        {"utt_001": utterance()},
        {"audio_001": manifest()},
    )
    assert record["tts_engine"] == "openai"
    assert record["voice_id"] == "voice_01"


def test_gold_records_have_null_voice_metadata() -> None:
    record = evaluate_grounding.evaluation_record(
        prediction(),
        {"screen_001": screen()},
        {"utt_001": utterance()},
        {"audio_001": manifest()},
    )
    assert record["tts_engine"] is None
    assert record["voice_id"] is None
