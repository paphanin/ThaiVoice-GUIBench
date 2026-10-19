# Qualitative Examples for the Paper

These four manually reviewed cases come from synthetic GUI screens and TTS-generated commands. They contain no real user or private-account data. Raw and corrected grounding predictions were produced in independent inference runs, so unchanged-prompt click differences are treated as rerun variability.

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

