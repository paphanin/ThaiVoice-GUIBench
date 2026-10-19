# Corrected Grounding Run Report

## Scope

- Corrected transcript source: `data/corrections/corrected_transcripts.jsonl`
- Predictions output: `data/predictions/grounding_predictions.jsonl`
- Grounding models: `G1` / GPT-5.5 and `G2` / UI-TARS-1.5-7B
- Baseline gold and raw-ASR predictions were not rerun.
- Existing correction outputs and grounding prompts were not changed.

## Counts

| Model | Condition | Generated | Success | Failed |
| --- | --- | ---: | ---: | ---: |
| G1 | corrected_A_no_screen_cleanup_whisper | 471 | 471 | 0 |
| G1 | corrected_B_screen_string_match_whisper | 471 | 471 | 0 |
| G1 | corrected_C_full_screen_aware_alias_whisper | 471 | 471 | 0 |
| G1 | corrected_A_no_screen_cleanup_typhoon | 471 | 471 | 0 |
| G1 | corrected_B_screen_string_match_typhoon | 471 | 471 | 0 |
| G1 | corrected_C_full_screen_aware_alias_typhoon | 471 | 471 | 0 |
| G2 | corrected_A_no_screen_cleanup_whisper | 471 | 451 | 20 |
| G2 | corrected_B_screen_string_match_whisper | 471 | 440 | 31 |
| G2 | corrected_C_full_screen_aware_alias_whisper | 471 | 436 | 35 |
| G2 | corrected_A_no_screen_cleanup_typhoon | 471 | 439 | 32 |
| G2 | corrected_B_screen_string_match_typhoon | 471 | 447 | 24 |
| G2 | corrected_C_full_screen_aware_alias_typhoon | 471 | 427 | 44 |

- Expected corrected grounding records: `5652`
- Generated corrected grounding records: `5652`
- Success: `5466`
- Failed: `186`
- G1 coverage: `2826 / 2826`
- G2 coverage: `2826 / 2826`

## Accuracy

Accuracy and gain use click accuracy including parse failures. Gain is corrected accuracy minus the corresponding raw-ASR accuracy.

| Grounding model | ASR model | Correction method | Raw ASR click accuracy | Corrected click accuracy | Gain | Parse failure rate |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| G1 | whisper_large_v3_local | A_no_screen_cleanup | 0.757962 | 0.751592 | -0.006370 | 0.000000 |
| G1 | whisper_large_v3_local | B_screen_string_match | 0.757962 | 0.753715 | -0.004247 | 0.000000 |
| G1 | whisper_large_v3_local | C_full_screen_aware_alias | 0.757962 | 0.738854 | -0.019108 | 0.000000 |
| G1 | typhoon_asr_api | A_no_screen_cleanup | 0.764331 | 0.751592 | -0.012739 | 0.000000 |
| G1 | typhoon_asr_api | B_screen_string_match | 0.764331 | 0.755839 | -0.008492 | 0.000000 |
| G1 | typhoon_asr_api | C_full_screen_aware_alias | 0.764331 | 0.751592 | -0.012739 | 0.000000 |
| G2 | whisper_large_v3_local | A_no_screen_cleanup | 0.390658 | 0.392781 | 0.002123 | 0.042463 |
| G2 | whisper_large_v3_local | B_screen_string_match | 0.390658 | 0.373673 | -0.016985 | 0.065817 |
| G2 | whisper_large_v3_local | C_full_screen_aware_alias | 0.390658 | 0.350318 | -0.040340 | 0.074310 |
| G2 | typhoon_asr_api | A_no_screen_cleanup | 0.403397 | 0.341826 | -0.061571 | 0.067941 |
| G2 | typhoon_asr_api | B_screen_string_match | 0.403397 | 0.401274 | -0.002123 | 0.050955 |
| G2 | typhoon_asr_api | C_full_screen_aware_alias | 0.403397 | 0.388535 | -0.014862 | 0.093418 |

## Failure Summary

| Model | ASR model | Correction method | Failure count | Failure behavior |
| --- | --- | --- | ---: | --- |
| G1 | whisper_large_v3_local | A/B/C | 0 | No failed predictions |
| G1 | typhoon_asr_api | A/B/C | 0 | No failed predictions |
| G2 | whisper_large_v3_local | A_no_screen_cleanup | 20 | Unparseable model output |
| G2 | whisper_large_v3_local | B_screen_string_match | 31 | Unparseable model output |
| G2 | whisper_large_v3_local | C_full_screen_aware_alias | 35 | Unparseable model output |
| G2 | typhoon_asr_api | A_no_screen_cleanup | 32 | Unparseable model output |
| G2 | typhoon_asr_api | B_screen_string_match | 24 | Unparseable model output |
| G2 | typhoon_asr_api | C_full_screen_aware_alias | 44 | Unparseable model output |

Failed predictions remain in the evaluation denominator as incorrect. Parseable out-of-bounds coordinates also remain parse successes but count as incorrect clicks.

## Validation

- Prediction IDs: `7792 / 7792` unique
- Grounding prediction validation: passed
- Grounding evaluation: completed for `7792` records
- Corrected-condition coverage: `471` records for every model/ASR/method combination
