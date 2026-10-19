# Manual Failure and Variability Review Guide

## Scope

`failure_review_sample.csv` contains **140** deterministically selected cases for human review. It is an analysis-preparation artifact only: no prediction, correction, or result-table records were modified.

The sampler validated 5652 raw/corrected grounding pairs derived from 2826 correction records, 942 ASR records, 480 audio-manifest rows, and 128 audited utterances. Pairwise CC/WC/CW/WW totals and changed/unchanged coordinate counts were checked against `correction_transition_counts.csv`, Table 4, and Table 4b before sampling.

## Transition Codes

- `CC`: raw click correct, corrected-run click correct.
- `WC`: raw click wrong, corrected-run click correct.
- `CW`: raw click correct, corrected-run click wrong.
- `WW`: both clicks wrong.

`coordinate_same=true` requires two successfully parsed, exactly equal coordinate pairs. A false value can mean a different coordinate, a parse failure, or a missing coordinate. Inspect the coordinate and prediction-label fields before assigning a manual category.

## Sampling

Cases were selected without replacement from unique `(grounding_model, asr_model, correction_method, audio_id)` tuples. Selection first covered the requested priority signals, then filled to 140 while balancing tier, ASR model, grounding model, and correction method. Priority signals overlap, so their selected counts do not sum to the sample size.

| Priority signal | Available pairs | Selected cases |
| --- | ---: | ---: |
| `raw_wrong_correction_helped` | 46 | 16 |
| `raw_correct_correction_hurt` | 54 | 18 |
| `transcript_false_correction` | 604 | 48 |
| `method_c_g1_degradation` | 10 | 6 |
| `whisper_ab_g1_improvement` | 3 | 3 |
| `unchanged_rerun_variability` | 3266 | 42 |
| `uitars_parse_failure` | 348 | 15 |
| `uitars_out_of_bounds` | 100 | 14 |
| `t3_t4_failure` | 1722 | 66 |
| `loanword_asr_error` | 522 | 22 |
| `confusable_screen_label` | 1125 | 41 |
| `transcript_improved_hurt` | 6 | 3 |
| `changed_no_downstream_gain` | 520 | 14 |
| `g1_visual_grounding_error` | 290 | 14 |

## Sample Distribution

### By Tier

| Tier | Cases |
| --- | ---: |
| T1_verbatim | 35 |
| T2_paraphrase | 35 |
| T3_intent | 35 |
| T4_visual_positional | 35 |

### By ASR model

| ASR model | Cases |
| --- | ---: |
| typhoon_asr_api | 70 |
| whisper_large_v3_local | 70 |

### By Grounding model

| Grounding model | Cases |
| --- | ---: |
| G1 | 71 |
| G2 | 69 |

### By Correction method

| Correction method | Cases |
| --- | ---: |
| A_no_screen_cleanup | 47 |
| B_screen_string_match | 46 |
| C_full_screen_aware_alias | 47 |

### By Transition

| Transition | Cases |
| --- | ---: |
| CC | 21 |
| CW | 26 |
| WC | 22 |
| WW | 71 |

### By Candidate taxonomy

| Candidate taxonomy | Cases |
| --- | ---: |
| ambiguous_instruction | 11 |
| confusable_screen_label | 12 |
| correction_changed_without_downstream_gain | 13 |
| correction_helped | 13 |
| correction_helped_transcript_but_hurt_grounding | 2 |
| loanword_ASR_error | 11 |
| out_of_bounds_prediction | 13 |
| over_correction | 13 |
| parse_failure | 15 |
| positional_phrase_failure | 12 |
| unchanged_prompt_rerun_variability | 13 |
| visual_grounding_error | 12 |

## Review Procedure

1. Compare `gold_text`, `raw_asr_transcript`, and `corrected_transcript` without using the gold text to reinterpret the model output.
2. Inspect raw and corrected labels, coordinates, click outcomes, and transition type.
3. Replace or confirm `candidate_failure_taxonomy` in `manual_failure_taxonomy` using one allowed value below.
4. Use `notes` for concise evidence. Mark `include_as_qualitative_example` as `yes` only for clear, representative cases.
5. Treat unchanged-transcript differences as independent grounding rerun variability, not correction effects.
6. Treat parse success and click correctness separately. Out-of-bounds parsed coordinates are click failures, while unparseable UI-TARS outputs are parse failures.

## Allowed Manual Taxonomy

- `loanword_ASR_error`
- `Thai_word_segmentation_issue`
- `confusable_screen_label`
- `visual_grounding_error`
- `positional_phrase_failure`
- `over_correction`
- `ambiguous_instruction`
- `TTS_pronunciation_issue`
- `parse_failure`
- `out_of_bounds_prediction`
- `correction_helped`
- `correction_helped_transcript_but_hurt_grounding`
- `correction_changed_without_downstream_gain`
- `unchanged_prompt_rerun_variability`
- `other`

The automatic taxonomy is a review aid, not a final annotation. In particular, `TTS_pronunciation_issue` and some segmentation errors require listening or native-speaker judgment and are not inferred automatically.
