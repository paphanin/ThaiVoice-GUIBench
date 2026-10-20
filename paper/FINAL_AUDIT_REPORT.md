# Required-revision audit

Updated: 2026-10-20; required-reporting revision: 2026-10-19. Supersedes the July audit and its stronger causal/significance wording.

## Scope and preservation

Reporting and IEEE formatting changes use existing results. Dataset labels, targets, schemas, predictions, correction settings, ASR outputs, and existing inference runs are unchanged. A baseline SHA-256 comparison checks 9,561 pre-existing data/config/schema/script/test/figure files: zero changed or missing. Old 40-screen archives and smoke runs are not distributed. New packaging code, tests, documentation, and standard missing TeX dependencies support reproducibility without new inference.

## Required revisions addressed

1. Abstract, contributions, results, captions, and conclusion describe exploratory cross-run differences. Exact unadjusted post-hoc p=0.03125 is contextualized as audio-level, dependent within commands, unadjusted across comparisons, and confounded by reruns. Six deteriorations derive from three commands; no general correction-harm or confirmatory significance claim remains.
2. Changed/unchanged and no-op controls expose confounding without isolating correction causality or proving serving-system drift. Independent collection dates and uncontrolled inference defaults are explicit.
3. Existing command-weighted gold-versus-ASR comparisons and clustered intervals are retained. No detectable difference is distinguished from equivalence/robustness and adequate sensitivity or power.
4. The baseline table reports all gold/raw-ASR tiers. GPT-5.5 gold T4 is 62.50 percent, not the raw-ASR T4 score. Missing independent human reference performance/agreement and unresolved model, command, screen, protocol, and annotation error sources are explicit.
5. Construction documents deterministic templates and anti-circularity, one Thai-speaking author reviewing all 128 commands, heuristic naturalness prefilling, and 20 recorded edits. Leakage validation does not substitute for naturalness or ambiguity checks.
6. The 140-case analysis identifies one unblinded reviewer, visible system/target/outcome information, automatic suggestions, guide/taxonomy, deterministic sampling and balancing, and evidence notes. No inter-reviewer agreement or between-reviewer dispute resolution applies. Sample counts are not prevalence estimates.
7. T1-only code-switching is stated in the abstract and conclusion, alongside 18 commands and nine selectively excluded Azure renditions. Language, tier, provider, and exclusion effects remain confounded.
8. Literal transcript metrics and the existing NFKC/whitespace diagnostic are distinguished. Non-cosmetic is not synonymous with semantic error; transliteration equivalence is an unverified possibility.
9. Reproduction documentation provides exact prompts, frozen aliases and thresholds, manifest provenance, available client/serving records, and unrecorded historical settings. The native probe includes all 34 failures plus 66 seeded remaining items, with parsed/correct counts 0/0 versus 23/14 and 66/30 versus 45/21. Its selected sample cannot establish protocol fairness.

## Numeric, build, and artifact checks

All six baseline aggregate rows and 24 tier scores match the frozen Table 3 CSV at printed precision. The consolidated correction table retains all literal metrics and net counts, with 12 model deltas checked against the frozen CSV. Changed/unchanged numeric rows are identical to the original. Ten validators pass; full pytest and release-integrity results are retained in the revision logs. The packager preserves literal LF-delimited JSONL: Unicode U+0085/U+2028 inside transcript strings do not split records.

IEEEtran conference/US Letter defaults replace generic margins and compressed references. Six pages include references; the requested copyright notice is on page 1 once. All pages are rendered and inspected, all fonts embedded, and no Type 3 font, overfull box, unresolved citation/reference, or font substitution remains. The class's normal reference trigger balances the last page. Remaining underfull warnings are visually acceptable.

## Deliverables and public-access verification

`paper/main.pdf` and matching source accompany the benchmark at https://github.com/paphanin/ThaiVoice-GUIBench/releases/tag/v1.0.2. Release checks cover every checksum, expected benchmark counts, and referenced screen/audio/raw-response files. The publication workflow checks anonymous public access and compares the downloaded asset's SHA-256 with the local ZIP. The download verification record is outside the archive to avoid self-referential checksums. No IEEE PDF eXpress or venue-submission action is claimed.

Historical data reports are frozen and may retain interpretations superseded by this audit. The revised manuscript and `docs/REPRODUCIBILITY.md` govern current claims.

## Coauthor update, 2026-10-20

Thepchai Supnithi and Nongnuch Ketui are added after Paphanin Amnuaikitwanit in the paper and PDF author metadata. Affiliations and additional review activities were not inferred. Version v1.0.2 preserves the prior releases and the frozen benchmark.
