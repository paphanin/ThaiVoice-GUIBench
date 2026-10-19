# ThaiVoice-GUIBench v1.0.1: reproducibility and reporting

## Access and revision scope

The public versioned release is https://github.com/paphanin/ThaiVoice-GUIBench/releases/tag/v1.0.1. Download the `ThaiVoice-GUIBench-v1.0.1.zip` asset; GitHub's generated source archive is a separate convenience copy. A local copy is at `output/release/ThaiVoice-GUIBench-v1.0.1.zip`.

This revision adds reporting and IEEE formatting only: no speech synthesis, ASR, correction, model inference, new human study, threshold tuning, or annotation changes were performed. The paper remains strictly 4--6 pages including references. Use the release tag and checksummed asset for reproducible access.

## Frozen benchmark and package contents

- 20 synthetic screens, five in each of four mock domains, with confusable distractors and annotated element boxes; 32 intent--screen mappings.
- 128 audited commands: 32 per tier; 110 pure Thai and 18 code-switched. Every code-switched command is T1.
- 480 WAV files and manifest rows; 471 included, nine excluded. Excluded files remain in the archive, flagged in the manifest and exclusion log.
- Original and audited command JSONL, intent mappings, screen images/metadata, splits, TTS/ASR manifests, both ASR output files, raw and corrected grounding predictions, raw responses, fixed corrections, aliases, threshold configurations, evaluation results, existing reruns, native-template probe, and review records.
- Formal schemas, generation/evaluation code, validators, tests, exact prompt templates, available serving configurations, manuscript source/PDF, and figure source data.
- `SHA256SUMS` covers every packaged file except itself. `RELEASE.json` records version and publication status. The ZIP has sorted members and fixed timestamps. Old 40-screen archives, caches, logs, smoke-test predictions, local environments, and credentials are excluded.

`data/` records and their historical reports are frozen. Some historical reports contain stronger interpretations superseded by the revised paper and this guide; they are retained for provenance, not as current claims. The current paper's status and audit files describe the revised conclusions. The author block and PDF author metadata identify Paphanin Amnuaikitwanit, as supplied on 2026-10-19. Version v1.0.1 records this author correction; the original release is preserved.

## Command construction and author-confirmed review provenance

`configs/utterance_generation.yaml` and `scripts/generate_utterances.py` define deterministic generation (seed 42, one command per tier/mapping). T1 can use the visible label. T2/T3 use intent-specific wording and T4 uses visual/spatial information; label copying and listed copied-label aliases are rejected in T2--T4. The source includes mappings for validation; this does not mean target labels are valid generation inputs for indirect wording.

The author confirmed during the revision that one Thai-speaking author created/reviewed the templates and checked all 128 commands for naturalness and ambiguity. The audit scaffold in `scripts/make_native_audit.py` initially labels text containing the mock-domain qualifier as slightly awkward and other text as natural. The 108 natural / 20 slightly-awkward counts therefore originate as heuristic prefills, not independent human ratings. The saved audit records document 20 style edits and zero removals. These confirmations supplement the CSV, which does not store reviewer identities or timestamps per judgment. AI assistance was not independently quantified; the paper does not claim unaided or independent multi-rater validation.

Lexical leakage checks, naturalness review, and independent agreement on a target are distinct. No independent human reference click performance by tier was collected. No human agreement with designated targets or inter-rater target-selection agreement is available. The author review does not establish a model ceiling or isolate ambiguity/annotation error from model errors.

## The 140-case review

The author confirmed one human reviewer followed `data/analysis/FAILURE_ANALYSIS_GUIDE.md` with system identities, gold targets/text, suggested categories, coordinates, and outcomes visible. Review was unblinded. No second independent coding pass, inter-reviewer agreement, or between-reviewer disagreement resolution applies.

The sampler (`scripts/make_failure_review_sample.py`) deterministically selects unique (grounder, ASR, correction method, audio ID) tuples. It prioritizes correction transitions, false corrections, no-op variability, UI-TARS parse/out-of-bounds failures, T3/T4 errors, loanwords, and confusable labels, then balances tiers and model/method groups. Each tier has 35 cases; ASR models have 70 each; grounders have 71/69; A/B/C have 47/46/47. Sampling has no random seed because ordering and selection are deterministic. Priority flags overlap.

The guide describes comparison of gold/raw/corrected text and clicks, one final taxonomy code per case, and concise evidence notes. Allowed categories cover lexical/segmentation, confusable labels, visual/positional failures, ambiguity, over-correction, TTS pronunciation, parse/out-of-bounds failures, correction/click associations, unchanged-prompt variability, and other. Some judgments require Thai proficiency or listening; automatic suggestions are not final labels. Outcome visibility and prefilled categories can bias interpretation. The sample is purposive, not a benchmark prevalence estimate. Frozen qualitative notes with words such as ?helped? describe associations and do not isolate causality.

## Audio schedule, exclusions, and denominators

`configs/tts.yaml` specifies OpenAI marin and cedar on all 128 commands: 256 files. Azure Premwadee covers all 128; Niwat is test-only on 96: 224 files. Hence 32 dev commands have three files each and 96 test commands have four. Of the 18 code-switched commands, two dev commands contribute six files and 16 test commands contribute 64, totaling 70. Nine excluded Azure T1 code-switched files leave 61 valid. Valid per-command rendition counts are: 39 commands with three, 88 with four, and one with two.

Primary ASR and audio-conditioned click aggregates weight included audio rows equally. Gold grounding has one row per command. The existing paired bootstrap averages raw-ASR click correctness within command, subtracts that command's gold score, and resamples commands equally (10,000 draws, seed 20260719). Aggregate gold and audio-level raw-ASR percentages have different weights and must not be subtracted as that command-weighted estimate. No new equal-weighted model evaluation was added. Per-command/tier/language/provider/voice/split coverage is recoverable directly by joining `audio_manifest.jsonl` to `utterances_audited.jsonl` on `utterance_id`.

## Models, prompts, and serving records

- Whisper large-v3: faster-whisper 1.2.1; hosted Typhoon model `typhoon-asr-realtime`, provider transcription API `/v1`.
- GPT-5.5: Responses API `/v1/responses`, OpenAI SDK 2.44.0; stored model snapshot `gpt-5.5-2026-04-23`.
- UI-TARS-1.5-7B: local OpenAI-compatible vLLM endpoint, bfloat16, absolute-pixel coordinates. Original and rerun client configurations are `configs/grounding.yaml` and `configs/grounding_phase2_rerun.yaml`.
- `docs/prompts/gpt55_grounding.txt`, `ui_tars_grounding.txt`, and `ui_tars_native.txt` were exported from the actual frozen prompt-builder expressions. Placeholders identify the command and dimensions. The two main grounders use model-specific wording with the same semantic inputs and JSON fields; prompts are not text-identical across models. No gold ID, target box, or candidate list is provided.
- The client wrappers did not set an inference seed or temperature. Saved hosted response metadata includes returned values (for example temperature 1.0); a returned default is not an experimental control. Full historical vLLM/CUDA versions, hardware, launch flags, and local decoding defaults were not recorded. Current local package versions cannot reconstruct that historical serving environment.
- Baseline predictions date July 9--11, 2026; corrected predictions date July 18--19. Existing UI-TARS identical-prompt reruns and the native-template probe date July 19. Separate inference and scheduling confound correction comparisons. Directional changes alone do not demonstrate system drift.

Frozen correction config and aliases live in `data/corrections/frozen_correction_config.yaml` and `frozen_aliases.yaml`; their original freeze hashes are in `CORRECTION_FREEZE_NOTE.md`. Method B uses string threshold 0.95 / minimum confidence 0.94; method C uses string 0.94, alias 0.92, phonetic 0.90, maximum edit distance 1, minimum confidence 0.93, and n-best size 5. Exact enforcement is in `scripts/run_correction.py`; declarations alone are not extra tunable settings. No parameters were changed in this revision.

## Metrics and exploratory interpretation

CER normalizes whitespace but does not apply Unicode normalization in the original evaluation. WER uses PyThaiNLP 5.3.4 (newmm). Literal LER uses lowercased/space-normalized Latin loanword containment, not semantic equivalence of Thai transliteration. The 61 audio-level instances derive from 18 commands. Script variation is a hypothesis, not an established explanation for Typhoon's 59/61 literal errors; no exhaustive loanword audit was added.

Original recovery means lower CER or fewer loanword errors; false correction means higher CER or any text change to an already exact-gold transcript. The existing post-hoc NFKC/whitespace diagnostic marks raw/corrected pairs identical after normalization as cosmetic, and recomputes normalized CER recovery/false correction separately. Non-cosmetic does not necessarily mean a semantic error. Full counts are in `data/analysis/false_correction_cosmetic_split.csv`.

Gold GPT-5.5 T1--T4 click accuracy is 100/71.875/71.875/62.5 percent; UI-TARS is 75/34.375/43.75/25 percent, each on 32 commands. Use the actual `input_condition=gold` tier rows in Table 3 source CSV, not its repeated aggregate `gold_click_accuracy` column. Failures remain in the denominator.

All sign tests are post-hoc audio-level descriptions, unadjusted for multiple comparisons and not corrected for within-command dependence. GPT-5.5/Typhoon/C has 53 changed items, WC=0, CW=6, delta -11.3208 points, exact p=0.03125. Its six deteriorations derive from three commands: `map_compose_new_message_001_t3_intent_01` (three renditions), `map_open_help_center_001_t4_visual_positional_01` (two), and `map_turn_off_notifications_001_t4_visual_positional_01` (one). This is one exploratory adverse difference, not confirmatory evidence of general correction harm. No new adjusted test or clustered correction analysis was performed. No-op comparisons reveal rerun variability without identifying a causal correction effect.

## Existing native-template probe

`run_native_format_ablation.py` selects all 34 G2/Whisper parse failures, then 66 from the remaining 437 items using Python Random seed 20260719. It uses the saved official GROUNDING-style template and an action parser, interpreting coordinates as absolute pixels, as documented in the runner. Its actual IDs and responses are in `data/predictions/phase2_native_ablation/native_predictions.jsonl`.

| Subset | n | JSON parsed | JSON correct | Native parsed | Native correct |
| --- | ---: | ---: | ---: | ---: | ---: |
| Frozen parse failures | 34 | 0 | 0 | 23 | 14 |
| Random remaining items | 66 | 66 | 30 | 45 | 21 |
| All selected | 100 | 66 | 30 | 68 | 35 |

This failure-enriched sample is not representative. Format, parser, run timing, and coordinate handling are not fully isolated. It does not establish full-benchmark native accuracy or protocol fairness.

## Offline verification and reproduction

Use Python 3.12 or newer; this revision was verified under Python 3.14.6. Install the small validation environment with `python -m pip install -r requirements-validation.txt`. Tests and validation do not require API credentials or a running model server.

```powershell
python -m pytest -q
python scripts/validate_screens.py
python scripts/validate_intents.py
python scripts/validate_utterances.py --utterances data/utterances/utterances_audited.jsonl
python scripts/validate_splits.py
python scripts/validate_audio_manifest.py
python scripts/validate_asr_outputs.py --model whisper_large_v3_local --outputs data/asr_outputs/whisper_large_v3_local.jsonl --utterances data/utterances/utterances_audited.jsonl
python scripts/validate_asr_outputs.py --model typhoon_asr_api --outputs data/asr_outputs/typhoon_asr_api.jsonl --utterances data/utterances/utterances_audited.jsonl
python scripts/validate_corrections.py
python scripts/validate_grounding_predictions.py --predictions data/predictions/grounding_predictions.jsonl
python scripts/validate_grounding_predictions.py --predictions data/predictions/phase2_rerun_g2/grounding_predictions_rerun.jsonl
python scripts/package_reproducibility.py --verify output/release/ThaiVoice-GUIBench-v1.0.1.zip
```

`pytest` includes tests for corruption/exclusion behavior in the release packager. The native-format probe has a distinct record format; use the frozen probe runner/analysis records rather than passing it to the main JSON-protocol prediction schema.

To recompute grounding scores from saved predictions without new inference, use an isolated output directory:

```powershell
python scripts/evaluate_grounding.py --output-dir tmp/recomputed_grounding
```

Recomputing ASR WER additionally requires historical `pythainlp==5.3.4`; it is not needed to validate frozen records. `python scripts/evaluate_asr.py --output-dir tmp/recomputed_asr` recomputes those scores without running ASR. Do not run generation, inference, or result-generation scripts with default output destinations over frozen artifacts. Some supplementary scripts have fixed output paths: run them only in a disposable extracted copy. The stored CSVs already contain the results needed for the revised manuscript.

From `paper/`, build with `pdflatex --disable-installer -interaction=nonstopmode -halt-on-error main.tex`, `bibtex main`, then pdfLaTeX twice. The unmodified class, bibliography style, citation support, and missing standard Times/Courier definitions/metrics are included; template provenance is in `paper/TEMPLATE_PROVENANCE.md`. The manuscript uses IEEE conference/US Letter defaults, includes the required first-page copyright notice, and must pass the 4--6-page gate after any availability-link edit. No online PDF eXpress certification is claimed.

Build a release from the source tree with `python scripts/package_reproducibility.py --build`. The command verifies archive checksums, benchmark counts, and all primary referenced screen/audio/raw-response files. Rebuild after changing the paper, documentation, or publication URL; do not ship a stale PDF or checksum list.
