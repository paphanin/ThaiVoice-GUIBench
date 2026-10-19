# Manual Failure and Rerun-Variability Analysis

## Scope

This report summarizes all **140** completed manual annotations in `failure_review_sample.csv`. No predictions, correction outputs, thresholds, prompts, aliases, model settings, or result tables were changed.

The sample was deliberately stratified around failures, correction effects, and rerun variability. Its category percentages describe this review sample and are **not prevalence estimates for the full benchmark**. The attribution boundary follows `data/analysis/correction_degradation_diagnosis.md`: raw and corrected grounding were independent inference runs, and unchanged/no-op prompt differences are not attributed to correction.

## Final Taxonomy Distribution

| Manual taxonomy | Cases | Percent |
| --- | ---: | ---: |
| `unchanged_prompt_rerun_variability` | 27 | 19.3% |
| `confusable_screen_label` | 16 | 11.4% |
| `positional_phrase_failure` | 16 | 11.4% |
| `parse_failure` | 15 | 10.7% |
| `ambiguous_instruction` | 14 | 10.0% |
| `correction_changed_without_downstream_gain` | 13 | 9.3% |
| `out_of_bounds_prediction` | 13 | 9.3% |
| `loanword_ASR_error` | 12 | 8.6% |
| `over_correction` | 7 | 5.0% |
| `correction_helped` | 4 | 2.9% |
| `correction_helped_transcript_but_hurt_grounding` | 2 | 1.4% |
| `Thai_word_segmentation_issue` | 1 | 0.7% |

## Taxonomy by Tier

| Tier | Cases | Manual taxonomy counts |
| --- | ---: | --- |
| `T1_verbatim` | 35 | correction_changed_without_downstream_gain: 4; correction_helped: 1; correction_helped_transcript_but_hurt_grounding: 2; loanword_ASR_error: 12; out_of_bounds_prediction: 3; parse_failure: 8; unchanged_prompt_rerun_variability: 5 |
| `T2_paraphrase` | 35 | Thai_word_segmentation_issue: 1; ambiguous_instruction: 1; confusable_screen_label: 8; correction_changed_without_downstream_gain: 5; correction_helped: 1; out_of_bounds_prediction: 3; over_correction: 1; parse_failure: 3; unchanged_prompt_rerun_variability: 12 |
| `T3_intent` | 35 | ambiguous_instruction: 11; confusable_screen_label: 8; correction_changed_without_downstream_gain: 2; out_of_bounds_prediction: 1; over_correction: 3; parse_failure: 3; unchanged_prompt_rerun_variability: 7 |
| `T4_visual_positional` | 35 | ambiguous_instruction: 2; correction_changed_without_downstream_gain: 2; correction_helped: 2; out_of_bounds_prediction: 6; over_correction: 3; parse_failure: 1; positional_phrase_failure: 16; unchanged_prompt_rerun_variability: 3 |

## Taxonomy by ASR Model

| ASR model | Cases | Manual taxonomy counts |
| --- | ---: | --- |
| `typhoon_asr_api` | 70 | Thai_word_segmentation_issue: 1; ambiguous_instruction: 7; confusable_screen_label: 11; correction_changed_without_downstream_gain: 4; correction_helped: 2; loanword_ASR_error: 9; out_of_bounds_prediction: 5; over_correction: 6; parse_failure: 7; positional_phrase_failure: 11; unchanged_prompt_rerun_variability: 7 |
| `whisper_large_v3_local` | 70 | ambiguous_instruction: 7; confusable_screen_label: 5; correction_changed_without_downstream_gain: 9; correction_helped: 2; correction_helped_transcript_but_hurt_grounding: 2; loanword_ASR_error: 3; out_of_bounds_prediction: 8; over_correction: 1; parse_failure: 8; positional_phrase_failure: 5; unchanged_prompt_rerun_variability: 20 |

## Taxonomy by Grounding Model

| Grounding model | Cases | Manual taxonomy counts |
| --- | ---: | --- |
| `G1` | 71 | ambiguous_instruction: 13; confusable_screen_label: 16; correction_changed_without_downstream_gain: 9; loanword_ASR_error: 6; over_correction: 6; positional_phrase_failure: 14; unchanged_prompt_rerun_variability: 7 |
| `G2` | 69 | Thai_word_segmentation_issue: 1; ambiguous_instruction: 1; correction_changed_without_downstream_gain: 4; correction_helped: 4; correction_helped_transcript_but_hurt_grounding: 2; loanword_ASR_error: 6; out_of_bounds_prediction: 13; over_correction: 1; parse_failure: 15; positional_phrase_failure: 2; unchanged_prompt_rerun_variability: 20 |

## Taxonomy by Correction Method

| Correction method | Cases | Manual taxonomy counts |
| --- | ---: | --- |
| `A_no_screen_cleanup` | 47 | ambiguous_instruction: 4; confusable_screen_label: 9; correction_changed_without_downstream_gain: 5; loanword_ASR_error: 2; out_of_bounds_prediction: 3; parse_failure: 4; positional_phrase_failure: 7; unchanged_prompt_rerun_variability: 13 |
| `B_screen_string_match` | 46 | ambiguous_instruction: 4; confusable_screen_label: 5; correction_changed_without_downstream_gain: 3; correction_helped: 1; correction_helped_transcript_but_hurt_grounding: 1; loanword_ASR_error: 5; out_of_bounds_prediction: 8; parse_failure: 4; positional_phrase_failure: 5; unchanged_prompt_rerun_variability: 10 |
| `C_full_screen_aware_alias` | 47 | Thai_word_segmentation_issue: 1; ambiguous_instruction: 6; confusable_screen_label: 2; correction_changed_without_downstream_gain: 5; correction_helped: 3; correction_helped_transcript_but_hurt_grounding: 1; loanword_ASR_error: 5; out_of_bounds_prediction: 2; over_correction: 7; parse_failure: 7; positional_phrase_failure: 4; unchanged_prompt_rerun_variability: 4 |

Full long-form counts and within-group percentages are in `failure_taxonomy_summary.csv`.

## Outcome Transitions

| Transition | Cases | Percent |
| --- | ---: | ---: |
| `CC` | 21 | 15.0% |
| `WC` | 22 | 15.7% |
| `CW` | 26 | 18.6% |
| `WW` | 71 | 50.7% |

`CC`, `WC`, `CW`, and `WW` denote raw/corrected click correctness. Parse failures and out-of-bounds points are incorrect clicks.

## Changed Transcripts and Rerun Variability

| Stored transcript change | Cases | CC | WC | CW | WW |
| --- | ---: | ---: | ---: | ---: | ---: |
| `true` | 48 | 8 | 16 | 18 | 6 |
| `false` | 92 | 13 | 6 | 8 | 65 |

- The stored correction flag marks **48** cases changed and **92** unchanged.
- Manual review assigned **27** cases to `unchanged_prompt_rerun_variability`: **12** had exactly unchanged transcript text, while **15** were stored as changed but were judged normalization-only/no-op changes.
- These rerun-variability cases include 12 `WC` and 8 `CW` flips. They are not evidence that correction helped or harmed grounding.

## Correction-Helping Patterns

Manual review labeled **4** sampled cases as `correction_helped`; all were `WC` transitions. They comprise B_screen_string_match: 1; C_full_screen_aware_alias: 3 and typhoon_asr_api: 2; whisper_large_v3_local: 2. The selected clear example repairs a Thai alias to the visible English label `Cart`. Because this is a stratified sample and inference runs were independent, these counts are qualitative evidence rather than an estimated recovery rate.

## Correction-Harming Patterns

Manual review identified **9** harming cases: 7 `over_correction` and 2 linguistically helpful corrections followed by worse grounding. All 9 are `CW` transitions; 8 use Method C. Examples include visible-label injection redirecting the click and a correct screen-string repair followed by a worse independent grounding result.

## Rerun-Variability Patterns

The **27** manually labeled variability cases are concentrated in G1: 7; G2: 20. This is consistent with the separate degradation diagnosis, which found substantially lower coordinate repeatability for UI-TARS and full no-op Typhoon A/B controls with changed click outcomes. Parse success remains distinct from click correctness.

## Selected Qualitative Examples

## 1. Correction helped (`case_093`)

- Screen: `shopping_002`
- Tier: `T2_paraphrase`
- ASR / grounding / correction: `typhoon_asr_api` / `G2` / `C_full_screen_aware_alias`
- Target label: `Cart`
- Gold text: เปิดตะกร้าสินค้าให้หน่อย
- Raw ASR transcript: เปิดตะกร้า สินค้าให้หน่อย
- Corrected transcript: เปิดCart สินค้าให้หน่อย
- Transcript changed: `true`
- Raw prediction: label="(empty)", coordinates=[142.0,1476.0], click_correct=false
- Corrected-run prediction: label="(empty)", coordinates=[418.0,1815.0], click_correct=true
- Transition: `WC`
- Interpretation: Real alias ตะกร้า->Cart; corrected click moved to the Cart tab [418,1815] - clear correction win.

## 2. False correction (`case_135`)

- Screen: `settings_004`
- Tier: `T2_paraphrase`
- ASR / grounding / correction: `whisper_large_v3_local` / `G2` / `C_full_screen_aware_alias`
- Target label: `Notifications`
- Gold text: ปิดการเตือนของแอปให้หน่อย
- Raw ASR transcript: ปิดการเตือนของแอปให้หน่อย
- Corrected transcript: ปิดการNotificationsของแอปให้หน่อย
- Transcript changed: `true`
- Raw prediction: label="(empty)", coordinates=[303.0,514.0], click_correct=true
- Corrected-run prediction: label="(empty)", coordinates=[546.0,511.0], click_correct=false
- Transition: `CW`
- Interpretation: Raw transcript already equalled gold; method C still rewrote การเตือน->การNotifications and the corrected run missed ([303,514]->[546,511]) - false correction on a perfect transcript.

## 3. Plausible correction, worse grounding (`case_118`)

- Screen: `mock_finance_001`
- Tier: `T1_verbatim`
- ASR / grounding / correction: `whisper_large_v3_local` / `G2` / `B_screen_string_match`
- Target label: `Pay bill`
- Gold text: ช่วยแตะ Pay bill สำหรับชำระบิลให้หน่อย
- Raw ASR transcript: ช่วยแต่ Paybill สำหรับชำระบิวให้หน่อย
- Corrected transcript: ช่วยแต่ Pay bill สําหรับชําระบิวให้หน่อย
- Transcript changed: `true`
- Raw prediction: label="(empty)", coordinates=[546.0,1035.0], click_correct=true
- Corrected-run prediction: label="(empty)", coordinates=[143.0,495.0], click_correct=false
- Transition: `CW`
- Interpretation: Method B genuinely fixed Paybill->'Pay bill' (exact screen string) yet the click moved off-target [546,1035]->[143,495] - transcript improved, grounding hurt.

## 4. Unchanged prompt, different click outcome (`case_003`)

- Screen: `mock_finance_003`
- Tier: `T2_paraphrase`
- ASR / grounding / correction: `typhoon_asr_api` / `G1` / `A_no_screen_cleanup`
- Target label: `Statements`
- Gold text: ขอดูรายการของเดือนนี้หน่อย
- Raw ASR transcript: ขอดูรายการของเดือนนี้หน่อย
- Corrected transcript: ขอดูรายการของเดือนนี้หน่อย
- Transcript changed: `false`
- Raw prediction: label="History", coordinates=[782.0,506.0], click_correct=false
- Corrected-run prediction: label="Statements", coordinates=[540.0,879.0], click_correct=true
- Transition: `WC`
- Interpretation: Transcript unchanged; raw picked History, corrected-run rerun picked Statements - W->C flip is independent rerun variance (History/Statements are also semantically close). Was visual_grounding_error.


## Limitations Revealed by the Analysis

- The 140 cases were purposefully sampled, so category shares cannot be generalized to the full dataset without weighting.
- Raw and corrected grounding are independent inference runs. The analysis can identify changed-text associations but cannot fully isolate correction causality from rerun stochasticity.
- Unicode normalization can set `transcript_changed=true` without a meaningful linguistic change; manual review separated these no-op cases.
- UI-TARS parse failures and out-of-bounds coordinates are distinct failure modes, and both remain incorrect in click evaluation.
- T3/T4 ambiguity and positional failures can persist even when ASR is usable, while confusable labels can redirect an otherwise plausible click.
- The benchmark uses 20 synthetic screens and TTS-generated speech, so it does not establish behavior for real user speech or production interfaces.
