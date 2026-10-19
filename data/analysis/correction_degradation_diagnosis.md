# Corrected-Grounding Degradation Diagnosis

## Scope

This report verifies why corrected-transcript grounding can have lower click accuracy than raw-ASR grounding even when model outputs parse successfully. It uses the frozen correction outputs and existing grounding predictions only. No correction setting, prompt, alias, model, or evaluation rule was changed, and no grounding model was rerun.

Derived data:

- `data/analysis/correction_transition_counts.csv`
- `data/analysis/correction_changed_unchanged_summary.csv`
- `data/analysis/grounding_rerun_variability.csv`

## Final Diagnosis

No dataset join, denominator, screenshot, transcript-provenance, duplicate, prompt-template, semantic model-setting, or evaluation mismatch was found.

The observed differences have two sources:

1. **Independent grounding rerun variability.** Typhoon methods A and B changed no transcripts, but independently rerun grounding produced different coordinates and different click outcomes. These full 471-record no-op conditions show that pooled raw-versus-corrected differences cannot be attributed entirely to correction.
2. **Correction-induced degradation concentrated in method C.** The clearest result is G1/Typhoon/C: its 53 changed transcripts fall from `0.905660` raw click accuracy to `0.792453` corrected click accuracy, with `WC=0` and `CW=6`. G1/Whisper/C also has a negative changed-subset delta.

Conversely, the changed subsets for G1/Whisper methods A and B show small apparent gains (`+0.027778` and `+0.013889`). Their pooled accuracy is lower because the separately rerun unchanged prompts lose more cases than they gain.

Parse success means that a model response contains usable coordinates. It does not mean that the coordinates identify the correct target.

## Integrity Checks

Pairs were joined using `(utterance_id, audio_id, screen_id, asr_model, grounding_model)`.

| Check | Result |
| --- | --- |
| Canonical prediction rows | `7792` |
| Unique prediction IDs | `7792`; duplicates `0` |
| Duplicate model/condition/utterance/audio combinations | `0` |
| Corrected records expected/present | `5652 / 5652` |
| Corrected groups | `12`, each with `471` records |
| Complete raw-to-corrected pairs | `5652`; missing `0` |
| Pairwise screen-ID mismatches | `0` |
| Active screenshot paths | `20 / 20` present |
| Correction rows / unique correction IDs | `2826 / 2826` |
| Empty, null, or non-string corrected transcripts | `0` |
| Metadata-like corrected transcripts | `0` |
| Multiline corrected transcripts | `0` |
| Raw prediction transcript vs ASR output mismatches | `0` |
| Corrected prediction transcript vs correction output mismatches | `0` |
| Stored `changed` flag vs actual transcript difference mismatches | `0` |

Every comparison therefore uses an identical 471-record denominator. Raw and corrected pairs reference the same logical screenshot ID and active image path. Historical request-time image hashes were not stored, so byte-level equality at the earlier inference timestamp cannot be independently reconstructed, but no screen/path mismatch exists in the data or runner flow.

## Prompt And Model Verification

- Raw and corrected G1 records both use `build_prompt` and the OpenAI Responses API.
- Raw and corrected G2 records both use `build_ui_tars_prompt` and the local OpenAI-compatible Chat Completions API.
- `input_condition` and `transcript_source` are record metadata and are not placed in either prompt.
- Neither prompt contains `target_element_id`, target bbox, candidate labels, distractors, or the gold answer.
- For unchanged transcripts, the text prompt is identical: transcript, screenshot dimensions, coordinate convention, and output instruction are the same.
- G1 uses the same semantic configuration: `api_vision`, `openai`, `gpt-5.5`.
- G2 uses the same semantic configuration: `local_openai_compatible_vision`, `ui_tars`, `ByteDance-Seed/UI-TARS-1.5-7B`, the same local base URL, and `coordinate_mode=absolute`.

Older G1 raw records omit optional null-valued `display_name`, `base_url`, and `coordinate_mode` fields that newer records serialize. After ignoring absent/null bookkeeping fields and response-specific `parse_notes`, semantic model-configuration mismatches are `0`. G2 settings match exactly after excluding response-specific parse notes.

Neither inference wrapper sets a deterministic seed or explicit temperature. G1 raw predictions were produced on 2026-07-09 and corrected predictions on 2026-07-19; G2 runs were likewise separate on 2026-07-11 and 2026-07-18.

## Group Classification

Classifications distinguish evidence on actually changed transcripts from movement caused by independently rerunning unchanged prompts.

| Grounding | ASR | Method | Classification | Basis |
| --- | --- | --- | --- | --- |
| G1 | Whisper | A | apparent correction benefit | Changed subset `+0.027778`; pooled loss comes from unchanged rerun cases |
| G1 | Whisper | B | apparent correction benefit | Changed subset `+0.013889`; pooled loss comes from unchanged rerun cases |
| G1 | Whisper | C | apparent correction degradation | Changed subset `-0.026549`, with `CW=4` and `WC=1` |
| G1 | Typhoon | A | dominated by independent rerun variability | No transcripts changed; full 471-record no-op control |
| G1 | Typhoon | B | dominated by independent rerun variability | No transcripts changed; full 471-record no-op control |
| G1 | Typhoon | C | apparent correction degradation | Changed subset `-0.113208`, with `CW=6` and `WC=0` |
| G2 | Whisper | A | mixed or inconclusive | Changed subset gains one net case, while unchanged outcomes have extensive flips |
| G2 | Whisper | B | mixed or inconclusive | Small negative changed and unchanged deltas amid extensive rerun variation |
| G2 | Whisper | C | dominated by independent rerun variability | Most pooled loss occurs on unchanged prompts |
| G2 | Typhoon | A | dominated by independent rerun variability | No transcripts changed; full 471-record no-op control |
| G2 | Typhoon | B | dominated by independent rerun variability | No transcripts changed; full 471-record no-op control |
| G2 | Typhoon | C | dominated by independent rerun variability | Changed subset has zero net delta; unchanged subset accounts for pooled loss |

These labels are descriptive, not causal estimates from controlled repeated trials.

## Pairwise Transitions: All Records

`CC`: raw correct to corrected correct. `WC`: raw wrong to corrected correct. `CW`: raw correct to corrected wrong. `WW`: wrong in both runs. Parse failures and out-of-bounds points count as incorrect.

| Grounding | ASR | Method | n | CC | WC | CW | WW | Raw acc. | Corrected acc. | Delta |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| G1 | Whisper | A | 471 | 350 | 4 | 7 | 110 | 0.757962 | 0.751592 | -0.006369 |
| G1 | Whisper | B | 471 | 349 | 6 | 8 | 108 | 0.757962 | 0.753715 | -0.004246 |
| G1 | Whisper | C | 471 | 345 | 3 | 12 | 111 | 0.757962 | 0.738854 | -0.019108 |
| G1 | Typhoon | A | 471 | 349 | 5 | 11 | 106 | 0.764331 | 0.751592 | -0.012739 |
| G1 | Typhoon | B | 471 | 348 | 8 | 12 | 103 | 0.764331 | 0.755839 | -0.008493 |
| G1 | Typhoon | C | 471 | 346 | 8 | 14 | 103 | 0.764331 | 0.751592 | -0.012739 |
| G2 | Whisper | A | 471 | 124 | 61 | 60 | 226 | 0.390658 | 0.392781 | +0.002123 |
| G2 | Whisper | B | 471 | 121 | 55 | 63 | 232 | 0.390658 | 0.373673 | -0.016985 |
| G2 | Whisper | C | 471 | 121 | 44 | 63 | 243 | 0.390658 | 0.350318 | -0.040340 |
| G2 | Typhoon | A | 471 | 112 | 49 | 78 | 232 | 0.403397 | 0.341826 | -0.061571 |
| G2 | Typhoon | B | 471 | 120 | 69 | 70 | 212 | 0.403397 | 0.401274 | -0.002123 |
| G2 | Typhoon | C | 471 | 125 | 58 | 65 | 223 | 0.403397 | 0.388535 | -0.014862 |

## Changed-Transcript Results

Typhoon A and B contain no changed transcripts and are omitted from the numeric rows below.

| Grounding | ASR | Method | n changed | CC | WC | CW | WW | Raw acc. | Corrected acc. | Delta |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| G1 | Whisper | A | 72 | 58 | 2 | 0 | 12 | 0.805556 | 0.833333 | +0.027778 |
| G1 | Whisper | B | 72 | 58 | 1 | 0 | 13 | 0.805556 | 0.819444 | +0.013889 |
| G1 | Whisper | C | 113 | 89 | 1 | 4 | 19 | 0.823009 | 0.796460 | -0.026549 |
| G1 | Typhoon | C | 53 | 42 | 0 | 6 | 5 | 0.905660 | 0.792453 | -0.113208 |
| G2 | Whisper | A | 72 | 23 | 14 | 13 | 22 | 0.500000 | 0.513889 | +0.013889 |
| G2 | Whisper | B | 72 | 26 | 9 | 10 | 27 | 0.500000 | 0.486111 | -0.013889 |
| G2 | Whisper | C | 113 | 41 | 13 | 15 | 44 | 0.495575 | 0.477876 | -0.017699 |
| G2 | Typhoon | C | 53 | 18 | 6 | 6 | 23 | 0.452830 | 0.452830 | 0.000000 |

The strongest correction-attributable negative result is G1/Typhoon/C. The changed-subset gains for G1/Whisper A and B are small but directionally positive. G2 changed-subset effects are small relative to its unchanged-prompt instability and are treated as mixed or inconclusive unless the unchanged subset clearly dominates.

## Unchanged-Transcript Rerun Variability

| Grounding | ASR | Method | n unchanged | Same coordinates | Different coordinates | CC | WC | CW | WW | Raw acc. | Corrected-run acc. | Delta |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| G1 | Whisper | A | 399 | 279 | 120 | 292 | 2 | 7 | 98 | 0.749373 | 0.736842 | -0.012531 |
| G1 | Whisper | B | 399 | 277 | 122 | 291 | 5 | 8 | 95 | 0.749373 | 0.741855 | -0.007519 |
| G1 | Whisper | C | 358 | 247 | 111 | 256 | 2 | 8 | 92 | 0.737430 | 0.720670 | -0.016760 |
| G1 | Typhoon | A | 471 | 333 | 138 | 349 | 5 | 11 | 106 | 0.764331 | 0.751592 | -0.012739 |
| G1 | Typhoon | B | 471 | 332 | 139 | 348 | 8 | 12 | 103 | 0.764331 | 0.755839 | -0.008493 |
| G1 | Typhoon | C | 418 | 278 | 140 | 304 | 8 | 8 | 98 | 0.746411 | 0.746411 | 0.000000 |
| G2 | Whisper | A | 399 | 5 | 394 | 101 | 47 | 47 | 204 | 0.370927 | 0.370927 | 0.000000 |
| G2 | Whisper | B | 399 | 3 | 396 | 95 | 46 | 53 | 205 | 0.370927 | 0.353383 | -0.017544 |
| G2 | Whisper | C | 358 | 1 | 357 | 80 | 31 | 48 | 199 | 0.357542 | 0.310056 | -0.047486 |
| G2 | Typhoon | A | 471 | 2 | 469 | 112 | 49 | 78 | 232 | 0.403397 | 0.341826 | -0.061571 |
| G2 | Typhoon | B | 471 | 5 | 466 | 120 | 69 | 70 | 212 | 0.403397 | 0.401274 | -0.002123 |
| G2 | Typhoon | C | 418 | 4 | 414 | 107 | 52 | 59 | 200 | 0.397129 | 0.380383 | -0.016746 |

Typhoon A and B are exact no-op transcript controls. G1 still changes coordinates on 138 and 139 records, producing negative aggregate deltas. UI-TARS is much less repeatable: identical prompts reproduce valid exact coordinates in only 1 to 5 cases per group, and parse status can also change between independent runs.

## Record Examples

### Raw Wrong To Corrected Correct

- Model/condition: G1, Whisper, method A
- `utterance_id`: `map_change_language_001_t3_intent_01`
- `audio_id`: `azure__voice_01__test__map_change_language_001_t3_intent_01`
- `screen_id`: `settings_002`; target label: `ภาษา`
- Raw transcript: `จะปรับคำบนแอปให้เข้าใจง่ายขึ้นตั้งแต่ตรงไหน`
- Corrected transcript: `จะปรับคําบนแอปให้เข้าใจง่ายขึ้นตั้งแต่ตรงไหน`
- Raw click: `(540, 1500)`, outside the target; derived element `null`
- Corrected click: `(300, 506)`, target element `ภาษา_button`

This is a changed-transcript recovery, but the textual change is only Unicode-form cleanup. Because inference was independently rerun, it should be described as an apparent downstream benefit rather than definitive causal evidence.

### Raw Correct To Corrected Wrong

- Model/condition: G1, Typhoon, method C
- `utterance_id`: `map_compose_new_message_001_t3_intent_01`
- `audio_id`: `azure__voice_01__dev__map_compose_new_message_001_t3_intent_01`
- `screen_id`: `messaging_001`; target label: `แชตใหม่`
- Raw transcript: `จะเขียนไปหาคนใหม่ตั้งแต่ตรงไหน`
- Corrected transcript: `จะเขียนไปค้นหาคนใหม่ตั้งแต่ตรงไหน`
- Raw click: `(540, 879)`, target element `แชตใหม่_list_item`
- Corrected click: `(782, 506)`, wrong element `ค้นหา_button`

This example is consistent with method-C degradation: the inserted search wording redirects grounding from composing a new message to the visible search control.

### Unchanged Transcript With Different Click Outcome

- Model/condition: G1, Typhoon, method A no-op control
- `utterance_id`: `map_view_promotion_001_t3_intent_01`
- `audio_id`: `azure__voice_01__dev__map_view_promotion_001_t3_intent_01`
- `screen_id`: `shopping_004`; target label: `โปรโมชัน`
- Raw and corrected transcript: `อยากรู้ว่ามีดีนอะไรตอนนี้ตั้งแต่ตรงไหน`
- Raw click: `(300, 506)`, target element `โปรโมชัน_button`
- Corrected-run click: `(419, 1798)`, wrong element `ดีล_tab`

The prompt transcript is identical, so this correctness flip is evidence of independent grounding rerun variability, not correction.

## Attribution Boundary

Reasonably attributable to correction:

- G1/Typhoon/C changed-subset degradation, especially its six `CW` cases and zero `WC` cases.
- G1/Whisper/C's smaller negative changed-subset result.
- Small apparent changed-subset gains for G1/Whisper A and B, stated cautiously because the model was independently rerun.

Confounded or dominated by independent grounding runs:

- Every unchanged-transcript comparison.
- All Typhoon A/B pooled differences because these methods changed zero transcripts.
- Much of G2's pooled movement, given its very low coordinate repeatability and parse-status variation.
- Any all-record click gain or degradation that combines changed and independently rerun unchanged prompts.

The final interpretation must retain both the negative method-C findings and the no-op variability evidence. No post-hoc threshold or correction change is recommended or performed here.
