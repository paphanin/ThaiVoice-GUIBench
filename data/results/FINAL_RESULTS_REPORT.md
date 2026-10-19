# Final Results Report

## Status

- Results use the frozen original 20-screen dataset and existing validated inference outputs.

- No model was rerun and no correction threshold, prompt, alias, model version, or evaluation rule was changed.

- Negative and mixed correction results are retained.

- Pooled corrected-versus-raw click deltas combine transcript-related effects with independent grounding rerun variability.

- Unchanged-transcript deltas are evidence of rerun variability and are not attributed to correction.

## Definitions

- Recovery count uses the frozen automatic transcript comparison: lower CER or fewer loanword errors than raw ASR.

- False-correction count uses the frozen automatic comparison: worse CER, or a changed transcript whose raw ASR already exactly matches gold. Unsupported-label risks are discussed through the finalized diagnosis and group classification.

- Net transcript benefit is recovery count minus false-correction count.

- Click metrics include parse failures as incorrect unless a success-only column is explicitly named.

## Table 1 - Dataset Statistics

| section | category | count | notes |
| --- | --- | --- | --- |
| dataset_totals | screens | 20 |  |
| dataset_totals | mappings | 32 |  |
| dataset_totals | commands | 128 |  |
| dataset_totals | audio_manifest_records | 480 |  |
| screens_by_domain | messaging | 5 |  |
| screens_by_domain | mock_finance | 5 |  |
| screens_by_domain | settings | 5 |  |
| screens_by_domain | shopping | 5 |  |
| mappings_by_domain | messaging | 7 |  |
| mappings_by_domain | mock_finance | 8 |  |
| mappings_by_domain | settings | 8 |  |
| mappings_by_domain | shopping | 9 |  |
| commands_by_tier | T1_verbatim | 32 |  |
| commands_by_tier | T2_paraphrase | 32 |  |
| commands_by_tier | T3_intent | 32 |  |
| commands_by_tier | T4_visual_positional | 32 |  |
| audio_files_by_tts_engine | azure | 224 |  |
| audio_files_by_tts_engine | openai | 256 |  |
| audio_files_by_voice | azure/voice_01 | 128 |  |
| audio_files_by_voice | azure/voice_02 | 96 |  |
| audio_files_by_voice | openai/voice_01 | 128 |  |
| audio_files_by_voice | openai/voice_02 | 128 |  |
| commands_by_language_class | code_switched | 18 |  |
| commands_by_language_class | pure_thai | 110 |  |
| loanwords | utterances_with_loanwords | 18 |  |
| loanwords | loanword_tokens | 18 |  |
| audio_validity | valid_audio | 471 |  |
| audio_validity | excluded_audio | 9 |  |

## Table 2 - ASR Performance

| slice | asr_model | tier | domain | tts_engine | voice_id | language_class | records | success_count | failed_count | asr_failure_rate | cer | thai_tokenized_wer | loanword_error_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| asr_model | typhoon_asr_api |  |  |  |  |  | 471 | 471 | 0 | 0.000000 | 0.069473 | 0.132748 | 0.967213 |
| asr_model | whisper_large_v3_local |  |  |  |  |  | 471 | 471 | 0 | 0.000000 | 0.055513 | 0.107190 | 0.459016 |
| asr_model+tier | typhoon_asr_api | T1_verbatim |  |  |  |  | 111 | 111 | 0 | 0.000000 | 0.154481 | 0.229285 | 0.967213 |
| asr_model+tier | typhoon_asr_api | T2_paraphrase |  |  |  |  | 120 | 120 | 0 | 0.000000 | 0.032317 | 0.107217 |  |
| asr_model+tier | typhoon_asr_api | T3_intent |  |  |  |  | 120 | 120 | 0 | 0.000000 | 0.057996 | 0.113587 |  |
| asr_model+tier | typhoon_asr_api | T4_visual_positional |  |  |  |  | 120 | 120 | 0 | 0.000000 | 0.039473 | 0.088144 |  |
| asr_model+tier | whisper_large_v3_local | T1_verbatim |  |  |  |  | 111 | 111 | 0 | 0.000000 | 0.087801 | 0.126352 | 0.459016 |
| asr_model+tier | whisper_large_v3_local | T2_paraphrase |  |  |  |  | 120 | 120 | 0 | 0.000000 | 0.040711 | 0.100192 |  |
| asr_model+tier | whisper_large_v3_local | T3_intent |  |  |  |  | 120 | 120 | 0 | 0.000000 | 0.062708 | 0.125000 |  |
| asr_model+tier | whisper_large_v3_local | T4_visual_positional |  |  |  |  | 120 | 120 | 0 | 0.000000 | 0.033253 | 0.078655 |  |
| asr_model+domain | typhoon_asr_api |  | messaging |  |  |  | 99 | 99 | 0 | 0.000000 | 0.069941 | 0.120717 | 1.000000 |
| asr_model+domain | typhoon_asr_api |  | mock_finance |  |  |  | 119 | 119 | 0 | 0.000000 | 0.086496 | 0.167339 | 0.947368 |
| asr_model+domain | typhoon_asr_api |  | settings |  |  |  | 123 | 123 | 0 | 0.000000 | 0.069089 | 0.154573 | 1.000000 |
| asr_model+domain | typhoon_asr_api |  | shopping |  |  |  | 130 | 130 | 0 | 0.000000 | 0.053897 | 0.089597 | 0.944444 |
| asr_model+domain | whisper_large_v3_local |  | messaging |  |  |  | 99 | 99 | 0 | 0.000000 | 0.061094 | 0.115565 | 0.600000 |
| asr_model+domain | whisper_large_v3_local |  | mock_finance |  |  |  | 119 | 119 | 0 | 0.000000 | 0.076671 | 0.137543 | 0.421053 |
| asr_model+domain | whisper_large_v3_local |  | settings |  |  |  | 123 | 123 | 0 | 0.000000 | 0.041693 | 0.081803 | 0.357143 |
| asr_model+domain | whisper_large_v3_local |  | shopping |  |  |  | 130 | 130 | 0 | 0.000000 | 0.044972 | 0.097049 | 0.500000 |
| asr_model+tts_engine | typhoon_asr_api |  |  | azure |  |  | 215 | 215 | 0 | 0.000000 | 0.075375 | 0.144880 | 1.000000 |
| asr_model+tts_engine | typhoon_asr_api |  |  | openai |  |  | 256 | 256 | 0 | 0.000000 | 0.064515 | 0.122559 | 0.944444 |
| asr_model+tts_engine | whisper_large_v3_local |  |  | azure |  |  | 215 | 215 | 0 | 0.000000 | 0.057281 | 0.108016 | 0.600000 |
| asr_model+tts_engine | whisper_large_v3_local |  |  | openai |  |  | 256 | 256 | 0 | 0.000000 | 0.054029 | 0.106497 | 0.361111 |
| asr_model+tts_engine+voice_id | typhoon_asr_api |  |  | azure | voice_01 |  | 125 | 125 | 0 | 0.000000 | 0.084741 | 0.159214 | 1.000000 |
| asr_model+tts_engine+voice_id | typhoon_asr_api |  |  | azure | voice_02 |  | 90 | 90 | 0 | 0.000000 | 0.062367 | 0.124972 | 1.000000 |
| asr_model+tts_engine+voice_id | typhoon_asr_api |  |  | openai | voice_01 |  | 128 | 128 | 0 | 0.000000 | 0.070499 | 0.121941 | 1.000000 |
| asr_model+tts_engine+voice_id | typhoon_asr_api |  |  | openai | voice_02 |  | 128 | 128 | 0 | 0.000000 | 0.058531 | 0.123178 | 0.888889 |
| asr_model+tts_engine+voice_id | whisper_large_v3_local |  |  | azure | voice_01 |  | 125 | 125 | 0 | 0.000000 | 0.058433 | 0.101629 | 0.600000 |
| asr_model+tts_engine+voice_id | whisper_large_v3_local |  |  | azure | voice_02 |  | 90 | 90 | 0 | 0.000000 | 0.055681 | 0.116886 | 0.600000 |
| asr_model+tts_engine+voice_id | whisper_large_v3_local |  |  | openai | voice_01 |  | 128 | 128 | 0 | 0.000000 | 0.059881 | 0.118245 | 0.277778 |
| asr_model+tts_engine+voice_id | whisper_large_v3_local |  |  | openai | voice_02 |  | 128 | 128 | 0 | 0.000000 | 0.048176 | 0.094749 | 0.444444 |
| asr_model+language_class | typhoon_asr_api |  |  |  |  | code_switched | 61 | 61 | 0 | 0.000000 | 0.220266 | 0.308307 | 0.967213 |
| asr_model+language_class | typhoon_asr_api |  |  |  |  | pure_thai | 410 | 410 | 0 | 0.000000 | 0.047037 | 0.106629 |  |
| asr_model+language_class | whisper_large_v3_local |  |  |  |  | code_switched | 61 | 61 | 0 | 0.000000 | 0.100230 | 0.153624 | 0.459016 |
| asr_model+language_class | whisper_large_v3_local |  |  |  |  | pure_thai | 410 | 410 | 0 | 0.000000 | 0.048860 | 0.100282 |  |

## Table 3 - Grounding Degradation From ASR

| slice | grounding_model | input_condition | asr_model | tier | domain | language_class | n_total | n_success_parse | n_failed_parse | parse_failure_rate | point_in_image_rate | click_accuracy_including_failures | click_accuracy_success_only | absolute_drop_from_gold |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| grounding_model+input_condition+asr_model | G1 | asr_typhoon_asr_api | typhoon_asr_api |  |  |  | 471 | 471 | 0 | 0.000000 | 1.000000 | 0.764331 | 0.764331 | 0.001294 |
| grounding_model+input_condition+asr_model | G1 | asr_whisper_large_v3_local | whisper_large_v3_local |  |  |  | 471 | 471 | 0 | 0.000000 | 1.000000 | 0.757962 | 0.757962 | 0.007663 |
| grounding_model+input_condition+asr_model | G1 | gold |  |  |  |  | 128 | 128 | 0 | 0.000000 | 1.000000 | 0.765625 | 0.765625 | 0.000000 |
| grounding_model+input_condition+asr_model | G2 | asr_typhoon_asr_api | typhoon_asr_api |  |  |  | 471 | 442 | 29 | 0.061571 | 0.906582 | 0.403397 | 0.429864 | 0.041915 |
| grounding_model+input_condition+asr_model | G2 | asr_whisper_large_v3_local | whisper_large_v3_local |  |  |  | 471 | 437 | 34 | 0.072187 | 0.919321 | 0.390658 | 0.421053 | 0.054654 |
| grounding_model+input_condition+asr_model | G2 | gold |  |  |  |  | 128 | 119 | 9 | 0.070312 | 0.914062 | 0.445312 | 0.478992 | 0.000000 |
| grounding_model+input_condition+asr_model+tier | G1 | asr_typhoon_asr_api | typhoon_asr_api | T1_verbatim |  |  | 111 | 111 | 0 | 0.000000 | 1.000000 | 1.000000 | 1.000000 | -0.234375 |
| grounding_model+input_condition+asr_model+tier | G1 | asr_typhoon_asr_api | typhoon_asr_api | T2_paraphrase |  |  | 120 | 120 | 0 | 0.000000 | 1.000000 | 0.758333 | 0.758333 | 0.007292 |
| grounding_model+input_condition+asr_model+tier | G1 | asr_typhoon_asr_api | typhoon_asr_api | T3_intent |  |  | 120 | 120 | 0 | 0.000000 | 1.000000 | 0.733333 | 0.733333 | 0.032292 |
| grounding_model+input_condition+asr_model+tier | G1 | asr_typhoon_asr_api | typhoon_asr_api | T4_visual_positional |  |  | 120 | 120 | 0 | 0.000000 | 1.000000 | 0.583333 | 0.583333 | 0.182292 |
| grounding_model+input_condition+asr_model+tier | G1 | asr_whisper_large_v3_local | whisper_large_v3_local | T1_verbatim |  |  | 111 | 111 | 0 | 0.000000 | 1.000000 | 1.000000 | 1.000000 | -0.234375 |
| grounding_model+input_condition+asr_model+tier | G1 | asr_whisper_large_v3_local | whisper_large_v3_local | T2_paraphrase |  |  | 120 | 120 | 0 | 0.000000 | 1.000000 | 0.733333 | 0.733333 | 0.032292 |
| grounding_model+input_condition+asr_model+tier | G1 | asr_whisper_large_v3_local | whisper_large_v3_local | T3_intent |  |  | 120 | 120 | 0 | 0.000000 | 1.000000 | 0.725000 | 0.725000 | 0.040625 |
| grounding_model+input_condition+asr_model+tier | G1 | asr_whisper_large_v3_local | whisper_large_v3_local | T4_visual_positional |  |  | 120 | 120 | 0 | 0.000000 | 1.000000 | 0.591667 | 0.591667 | 0.173958 |
| grounding_model+input_condition+asr_model+tier | G1 | gold |  | T1_verbatim |  |  | 32 | 32 | 0 | 0.000000 | 1.000000 | 1.000000 | 1.000000 | 0.000000 |
| grounding_model+input_condition+asr_model+tier | G1 | gold |  | T2_paraphrase |  |  | 32 | 32 | 0 | 0.000000 | 1.000000 | 0.718750 | 0.718750 | 0.000000 |
| grounding_model+input_condition+asr_model+tier | G1 | gold |  | T3_intent |  |  | 32 | 32 | 0 | 0.000000 | 1.000000 | 0.718750 | 0.718750 | 0.000000 |
| grounding_model+input_condition+asr_model+tier | G1 | gold |  | T4_visual_positional |  |  | 32 | 32 | 0 | 0.000000 | 1.000000 | 0.625000 | 0.625000 | 0.000000 |
| grounding_model+input_condition+asr_model+tier | G2 | asr_typhoon_asr_api | typhoon_asr_api | T1_verbatim |  |  | 111 | 102 | 9 | 0.081081 | 0.900901 | 0.567568 | 0.617647 | -0.122255 |
| grounding_model+input_condition+asr_model+tier | G2 | asr_typhoon_asr_api | typhoon_asr_api | T2_paraphrase |  |  | 120 | 113 | 7 | 0.058333 | 0.941667 | 0.416667 | 0.442478 | 0.028646 |
| grounding_model+input_condition+asr_model+tier | G2 | asr_typhoon_asr_api | typhoon_asr_api | T3_intent |  |  | 120 | 116 | 4 | 0.033333 | 0.941667 | 0.408333 | 0.422414 | 0.036979 |
| grounding_model+input_condition+asr_model+tier | G2 | asr_typhoon_asr_api | typhoon_asr_api | T4_visual_positional |  |  | 120 | 111 | 9 | 0.075000 | 0.841667 | 0.233333 | 0.252252 | 0.211979 |
| grounding_model+input_condition+asr_model+tier | G2 | asr_whisper_large_v3_local | whisper_large_v3_local | T1_verbatim |  |  | 111 | 103 | 8 | 0.072072 | 0.927928 | 0.702703 | 0.757282 | -0.257390 |
| grounding_model+input_condition+asr_model+tier | G2 | asr_whisper_large_v3_local | whisper_large_v3_local | T2_paraphrase |  |  | 120 | 112 | 8 | 0.066667 | 0.925000 | 0.291667 | 0.312500 | 0.153646 |
| grounding_model+input_condition+asr_model+tier | G2 | asr_whisper_large_v3_local | whisper_large_v3_local | T3_intent |  |  | 120 | 114 | 6 | 0.050000 | 0.941667 | 0.291667 | 0.307018 | 0.153646 |
| grounding_model+input_condition+asr_model+tier | G2 | asr_whisper_large_v3_local | whisper_large_v3_local | T4_visual_positional |  |  | 120 | 108 | 12 | 0.100000 | 0.883333 | 0.300000 | 0.333333 | 0.145313 |
| grounding_model+input_condition+asr_model+tier | G2 | gold |  | T1_verbatim |  |  | 32 | 28 | 4 | 0.125000 | 0.875000 | 0.750000 | 0.857143 | 0.000000 |
| grounding_model+input_condition+asr_model+tier | G2 | gold |  | T2_paraphrase |  |  | 32 | 29 | 3 | 0.093750 | 0.906250 | 0.343750 | 0.379310 | 0.000000 |
| grounding_model+input_condition+asr_model+tier | G2 | gold |  | T3_intent |  |  | 32 | 31 | 1 | 0.031250 | 0.968750 | 0.437500 | 0.451613 | 0.000000 |
| grounding_model+input_condition+asr_model+tier | G2 | gold |  | T4_visual_positional |  |  | 32 | 31 | 1 | 0.031250 | 0.906250 | 0.250000 | 0.258065 | 0.000000 |
| grounding_model+input_condition+asr_model+domain | G1 | asr_typhoon_asr_api | typhoon_asr_api |  | messaging |  | 99 | 99 | 0 | 0.000000 | 1.000000 | 0.848485 | 0.848485 | -0.082860 |
| grounding_model+input_condition+asr_model+domain | G1 | asr_typhoon_asr_api | typhoon_asr_api |  | mock_finance |  | 119 | 119 | 0 | 0.000000 | 1.000000 | 0.747899 | 0.747899 | 0.017726 |
| grounding_model+input_condition+asr_model+domain | G1 | asr_typhoon_asr_api | typhoon_asr_api |  | settings |  | 123 | 123 | 0 | 0.000000 | 1.000000 | 0.756098 | 0.756098 | 0.009527 |
| grounding_model+input_condition+asr_model+domain | G1 | asr_typhoon_asr_api | typhoon_asr_api |  | shopping |  | 130 | 130 | 0 | 0.000000 | 1.000000 | 0.723077 | 0.723077 | 0.042548 |
| grounding_model+input_condition+asr_model+domain | G1 | asr_whisper_large_v3_local | whisper_large_v3_local |  | messaging |  | 99 | 99 | 0 | 0.000000 | 1.000000 | 0.858586 | 0.858586 | -0.092961 |
| grounding_model+input_condition+asr_model+domain | G1 | asr_whisper_large_v3_local | whisper_large_v3_local |  | mock_finance |  | 119 | 119 | 0 | 0.000000 | 1.000000 | 0.764706 | 0.764706 | 0.000919 |
| grounding_model+input_condition+asr_model+domain | G1 | asr_whisper_large_v3_local | whisper_large_v3_local |  | settings |  | 123 | 123 | 0 | 0.000000 | 1.000000 | 0.723577 | 0.723577 | 0.042048 |
| grounding_model+input_condition+asr_model+domain | G1 | asr_whisper_large_v3_local | whisper_large_v3_local |  | shopping |  | 130 | 130 | 0 | 0.000000 | 1.000000 | 0.707692 | 0.707692 | 0.057933 |
| grounding_model+input_condition+asr_model+domain | G1 | gold |  |  | messaging |  | 28 | 28 | 0 | 0.000000 | 1.000000 | 0.821429 | 0.821429 | 0.000000 |
| grounding_model+input_condition+asr_model+domain | G1 | gold |  |  | mock_finance |  | 32 | 32 | 0 | 0.000000 | 1.000000 | 0.781250 | 0.781250 | 0.000000 |
| grounding_model+input_condition+asr_model+domain | G1 | gold |  |  | settings |  | 32 | 32 | 0 | 0.000000 | 1.000000 | 0.750000 | 0.750000 | 0.000000 |
| grounding_model+input_condition+asr_model+domain | G1 | gold |  |  | shopping |  | 36 | 36 | 0 | 0.000000 | 1.000000 | 0.722222 | 0.722222 | 0.000000 |
| grounding_model+input_condition+asr_model+domain | G2 | asr_typhoon_asr_api | typhoon_asr_api |  | messaging |  | 99 | 95 | 4 | 0.040404 | 0.939394 | 0.474747 | 0.494737 | -0.029435 |
| grounding_model+input_condition+asr_model+domain | G2 | asr_typhoon_asr_api | typhoon_asr_api |  | mock_finance |  | 119 | 112 | 7 | 0.058824 | 0.915966 | 0.428571 | 0.455357 | 0.016741 |
| grounding_model+input_condition+asr_model+domain | G2 | asr_typhoon_asr_api | typhoon_asr_api |  | settings |  | 123 | 116 | 7 | 0.056911 | 0.910569 | 0.292683 | 0.310345 | 0.152630 |
| grounding_model+input_condition+asr_model+domain | G2 | asr_typhoon_asr_api | typhoon_asr_api |  | shopping |  | 130 | 119 | 11 | 0.084615 | 0.869231 | 0.430769 | 0.470588 | 0.014543 |
| grounding_model+input_condition+asr_model+domain | G2 | asr_whisper_large_v3_local | whisper_large_v3_local |  | messaging |  | 99 | 96 | 3 | 0.030303 | 0.959596 | 0.484848 | 0.500000 | -0.039536 |
| grounding_model+input_condition+asr_model+domain | G2 | asr_whisper_large_v3_local | whisper_large_v3_local |  | mock_finance |  | 119 | 109 | 10 | 0.084034 | 0.907563 | 0.420168 | 0.458716 | 0.025144 |
| grounding_model+input_condition+asr_model+domain | G2 | asr_whisper_large_v3_local | whisper_large_v3_local |  | settings |  | 123 | 113 | 10 | 0.081301 | 0.910569 | 0.292683 | 0.318584 | 0.152630 |
| grounding_model+input_condition+asr_model+domain | G2 | asr_whisper_large_v3_local | whisper_large_v3_local |  | shopping |  | 130 | 119 | 11 | 0.084615 | 0.907692 | 0.384615 | 0.420168 | 0.060697 |
| grounding_model+input_condition+asr_model+domain | G2 | gold |  |  | messaging |  | 28 | 27 | 1 | 0.035714 | 0.964286 | 0.464286 | 0.481481 | 0.000000 |
| grounding_model+input_condition+asr_model+domain | G2 | gold |  |  | mock_finance |  | 32 | 29 | 3 | 0.093750 | 0.906250 | 0.375000 | 0.413793 | 0.000000 |
| grounding_model+input_condition+asr_model+domain | G2 | gold |  |  | settings |  | 32 | 28 | 4 | 0.125000 | 0.843750 | 0.375000 | 0.428571 | 0.000000 |
| grounding_model+input_condition+asr_model+domain | G2 | gold |  |  | shopping |  | 36 | 35 | 1 | 0.027778 | 0.944444 | 0.555556 | 0.571429 | 0.000000 |
| grounding_model+input_condition+asr_model+language_class | G1 | asr_typhoon_asr_api | typhoon_asr_api |  |  | code_switched | 61 | 61 | 0 | 0.000000 | 1.000000 | 1.000000 | 1.000000 | -0.234375 |
| grounding_model+input_condition+asr_model+language_class | G1 | asr_typhoon_asr_api | typhoon_asr_api |  |  | pure_thai | 410 | 410 | 0 | 0.000000 | 1.000000 | 0.729268 | 0.729268 | 0.036357 |
| grounding_model+input_condition+asr_model+language_class | G1 | asr_whisper_large_v3_local | whisper_large_v3_local |  |  | code_switched | 61 | 61 | 0 | 0.000000 | 1.000000 | 1.000000 | 1.000000 | -0.234375 |
| grounding_model+input_condition+asr_model+language_class | G1 | asr_whisper_large_v3_local | whisper_large_v3_local |  |  | pure_thai | 410 | 410 | 0 | 0.000000 | 1.000000 | 0.721951 | 0.721951 | 0.043674 |
| grounding_model+input_condition+asr_model+language_class | G1 | gold |  |  |  | code_switched | 18 | 18 | 0 | 0.000000 | 1.000000 | 1.000000 | 1.000000 | 0.000000 |
| grounding_model+input_condition+asr_model+language_class | G1 | gold |  |  |  | pure_thai | 110 | 110 | 0 | 0.000000 | 1.000000 | 0.727273 | 0.727273 | 0.000000 |
| grounding_model+input_condition+asr_model+language_class | G2 | asr_typhoon_asr_api | typhoon_asr_api |  |  | code_switched | 61 | 57 | 4 | 0.065574 | 0.918033 | 0.557377 | 0.596491 | -0.112065 |
| grounding_model+input_condition+asr_model+language_class | G2 | asr_typhoon_asr_api | typhoon_asr_api |  |  | pure_thai | 410 | 385 | 25 | 0.060976 | 0.904878 | 0.380488 | 0.405195 | 0.064825 |
| grounding_model+input_condition+asr_model+language_class | G2 | asr_whisper_large_v3_local | whisper_large_v3_local |  |  | code_switched | 61 | 60 | 1 | 0.016393 | 0.983607 | 0.803279 | 0.816667 | -0.357966 |
| grounding_model+input_condition+asr_model+language_class | G2 | asr_whisper_large_v3_local | whisper_large_v3_local |  |  | pure_thai | 410 | 377 | 33 | 0.080488 | 0.909756 | 0.329268 | 0.358090 | 0.116044 |
| grounding_model+input_condition+asr_model+language_class | G2 | gold |  |  |  | code_switched | 18 | 17 | 1 | 0.055556 | 0.944444 | 0.777778 | 0.823529 | 0.000000 |
| grounding_model+input_condition+asr_model+language_class | G2 | gold |  |  |  | pure_thai | 110 | 102 | 8 | 0.072727 | 0.909091 | 0.390909 | 0.421569 | 0.000000 |

## Table 4 - Correction Effects

| grounding_model | asr_model | correction_method | n_total | changed_count | changed_rate | recovery_count | recovery_rate | false_correction_count | false_correction_rate | net_transcript_benefit | raw_click_accuracy | corrected_run_click_accuracy | pooled_click_delta | CC | WC | CW | WW | classification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| G1 | typhoon_asr_api | A_no_screen_cleanup | 471 | 0 | 0.000000 | 0 | 0.000000 | 0 | 0.000000 | 0 | 0.764331 | 0.751592 | -0.012739 | 349 | 5 | 11 | 106 | dominated by independent rerun variability |
| G1 | typhoon_asr_api | B_screen_string_match | 471 | 0 | 0.000000 | 0 | 0.000000 | 0 | 0.000000 | 0 | 0.764331 | 0.755839 | -0.008493 | 348 | 8 | 12 | 103 | dominated by independent rerun variability |
| G1 | typhoon_asr_api | C_full_screen_aware_alias | 471 | 53 | 0.112527 | 15 | 0.031847 | 48 | 0.101911 | -33 | 0.764331 | 0.751592 | -0.012739 | 346 | 8 | 14 | 103 | apparent correction degradation |
| G1 | whisper_large_v3_local | A_no_screen_cleanup | 471 | 72 | 0.152866 | 0 | 0.000000 | 72 | 0.152866 | -72 | 0.757962 | 0.751592 | -0.006369 | 350 | 4 | 7 | 110 | apparent correction benefit |
| G1 | whisper_large_v3_local | B_screen_string_match | 471 | 72 | 0.152866 | 3 | 0.006369 | 72 | 0.152866 | -69 | 0.757962 | 0.753715 | -0.004246 | 349 | 6 | 8 | 108 | apparent correction benefit |
| G1 | whisper_large_v3_local | C_full_screen_aware_alias | 471 | 113 | 0.239915 | 8 | 0.016985 | 110 | 0.233546 | -102 | 0.757962 | 0.738854 | -0.019108 | 345 | 3 | 12 | 111 | apparent correction degradation |
| G2 | typhoon_asr_api | A_no_screen_cleanup | 471 | 0 | 0.000000 | 0 | 0.000000 | 0 | 0.000000 | 0 | 0.403397 | 0.341826 | -0.061571 | 112 | 49 | 78 | 232 | dominated by independent rerun variability |
| G2 | typhoon_asr_api | B_screen_string_match | 471 | 0 | 0.000000 | 0 | 0.000000 | 0 | 0.000000 | 0 | 0.403397 | 0.401274 | -0.002123 | 120 | 69 | 70 | 212 | dominated by independent rerun variability |
| G2 | typhoon_asr_api | C_full_screen_aware_alias | 471 | 53 | 0.112527 | 15 | 0.031847 | 48 | 0.101911 | -33 | 0.403397 | 0.388535 | -0.014862 | 125 | 58 | 65 | 223 | dominated by independent rerun variability |
| G2 | whisper_large_v3_local | A_no_screen_cleanup | 471 | 72 | 0.152866 | 0 | 0.000000 | 72 | 0.152866 | -72 | 0.390658 | 0.392781 | 0.002123 | 124 | 61 | 60 | 226 | mixed or inconclusive |
| G2 | whisper_large_v3_local | B_screen_string_match | 471 | 72 | 0.152866 | 3 | 0.006369 | 72 | 0.152866 | -69 | 0.390658 | 0.373673 | -0.016985 | 121 | 55 | 63 | 232 | mixed or inconclusive |
| G2 | whisper_large_v3_local | C_full_screen_aware_alias | 471 | 113 | 0.239915 | 8 | 0.016985 | 110 | 0.233546 | -102 | 0.390658 | 0.350318 | -0.040340 | 121 | 44 | 63 | 243 | dominated by independent rerun variability |

## Table 4b - Changed Versus Unchanged Effects

| grounding_model | asr_model | correction_method | subset | n | raw_click_accuracy | corrected_run_click_accuracy | click_delta | exact_same_coordinate_count | different_coordinate_count | WC | CW | classification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| G1 | typhoon_asr_api | A_no_screen_cleanup | changed | 0 |  |  |  | 0 | 0 | 0 | 0 | dominated by independent rerun variability |
| G1 | typhoon_asr_api | A_no_screen_cleanup | unchanged | 471 | 0.764331 | 0.751592 | -0.012739 | 333 | 138 | 5 | 11 | dominated by independent rerun variability |
| G1 | typhoon_asr_api | B_screen_string_match | changed | 0 |  |  |  | 0 | 0 | 0 | 0 | dominated by independent rerun variability |
| G1 | typhoon_asr_api | B_screen_string_match | unchanged | 471 | 0.764331 | 0.755839 | -0.008493 | 332 | 139 | 8 | 12 | dominated by independent rerun variability |
| G1 | typhoon_asr_api | C_full_screen_aware_alias | changed | 53 | 0.905660 | 0.792453 | -0.113208 | 37 | 16 | 0 | 6 | apparent correction degradation |
| G1 | typhoon_asr_api | C_full_screen_aware_alias | unchanged | 418 | 0.746411 | 0.746411 | 0.000000 | 278 | 140 | 8 | 8 | apparent correction degradation |
| G1 | whisper_large_v3_local | A_no_screen_cleanup | changed | 72 | 0.805556 | 0.833333 | 0.027778 | 47 | 25 | 2 | 0 | apparent correction benefit |
| G1 | whisper_large_v3_local | A_no_screen_cleanup | unchanged | 399 | 0.749373 | 0.736842 | -0.012531 | 279 | 120 | 2 | 7 | apparent correction benefit |
| G1 | whisper_large_v3_local | B_screen_string_match | changed | 72 | 0.805556 | 0.819444 | 0.013889 | 49 | 23 | 1 | 0 | apparent correction benefit |
| G1 | whisper_large_v3_local | B_screen_string_match | unchanged | 399 | 0.749373 | 0.741855 | -0.007519 | 277 | 122 | 5 | 8 | apparent correction benefit |
| G1 | whisper_large_v3_local | C_full_screen_aware_alias | changed | 113 | 0.823009 | 0.796460 | -0.026549 | 79 | 34 | 1 | 4 | apparent correction degradation |
| G1 | whisper_large_v3_local | C_full_screen_aware_alias | unchanged | 358 | 0.737430 | 0.720670 | -0.016760 | 247 | 111 | 2 | 8 | apparent correction degradation |
| G2 | typhoon_asr_api | A_no_screen_cleanup | changed | 0 |  |  |  | 0 | 0 | 0 | 0 | dominated by independent rerun variability |
| G2 | typhoon_asr_api | A_no_screen_cleanup | unchanged | 471 | 0.403397 | 0.341826 | -0.061571 | 2 | 469 | 49 | 78 | dominated by independent rerun variability |
| G2 | typhoon_asr_api | B_screen_string_match | changed | 0 |  |  |  | 0 | 0 | 0 | 0 | dominated by independent rerun variability |
| G2 | typhoon_asr_api | B_screen_string_match | unchanged | 471 | 0.403397 | 0.401274 | -0.002123 | 5 | 466 | 69 | 70 | dominated by independent rerun variability |
| G2 | typhoon_asr_api | C_full_screen_aware_alias | changed | 53 | 0.452830 | 0.452830 | 0.000000 | 0 | 53 | 6 | 6 | dominated by independent rerun variability |
| G2 | typhoon_asr_api | C_full_screen_aware_alias | unchanged | 418 | 0.397129 | 0.380383 | -0.016746 | 4 | 414 | 52 | 59 | dominated by independent rerun variability |
| G2 | whisper_large_v3_local | A_no_screen_cleanup | changed | 72 | 0.500000 | 0.513889 | 0.013889 | 0 | 72 | 14 | 13 | mixed or inconclusive |
| G2 | whisper_large_v3_local | A_no_screen_cleanup | unchanged | 399 | 0.370927 | 0.370927 | 0.000000 | 5 | 394 | 47 | 47 | mixed or inconclusive |
| G2 | whisper_large_v3_local | B_screen_string_match | changed | 72 | 0.500000 | 0.486111 | -0.013889 | 0 | 72 | 9 | 10 | mixed or inconclusive |
| G2 | whisper_large_v3_local | B_screen_string_match | unchanged | 399 | 0.370927 | 0.353383 | -0.017544 | 3 | 396 | 46 | 53 | mixed or inconclusive |
| G2 | whisper_large_v3_local | C_full_screen_aware_alias | changed | 113 | 0.495575 | 0.477876 | -0.017699 | 1 | 112 | 13 | 15 | dominated by independent rerun variability |
| G2 | whisper_large_v3_local | C_full_screen_aware_alias | unchanged | 358 | 0.357542 | 0.310056 | -0.047486 | 1 | 357 | 31 | 48 | dominated by independent rerun variability |

## Interpretation

- G1/Whisper A and B have positive changed-subset deltas, while their pooled deltas remain slightly negative because unchanged prompts were independently rerun.

- Method C shows supported degradation for G1, especially Typhoon/C on changed transcripts.

- Typhoon A and B are no-op transcript controls; their click differences measure independent rerun variability.

- G2/UI-TARS has substantial parse and repeatability limitations. Its pooled correction deltas must not be read as purely transcript-causal.

## Summary JSON

```json
{
  "screens": 20,
  "mappings": 32,
  "utterances": 128,
  "audio_manifest_rows": 480,
  "valid_audio": 471,
  "excluded_audio": 9,
  "asr_records": 942,
  "grounding_eval_records": 7792,
  "correction_records": 2826,
  "corrected_grounding_records": 5652,
  "corrected_grounding_available": true,
  "asr_metrics_source": "data\\asr_outputs\\asr_metrics_by_file.jsonl",
  "asr_performance_by_model": [
    {
      "slice": "asr_model",
      "asr_model": "typhoon_asr_api",
      "records": 471,
      "success_count": 471,
      "failed_count": 0,
      "asr_failure_rate": 0.0,
      "cer": 0.06947260901030043,
      "thai_tokenized_wer": 0.13274829086930998,
      "loanword_error_rate": 0.9672131147540983,
      "loanword_count": 61,
      "loanword_errors": 59
    },
    {
      "slice": "asr_model",
      "asr_model": "whisper_large_v3_local",
      "records": 471,
      "success_count": 471,
      "failed_count": 0,
      "asr_failure_rate": 0.0,
      "cer": 0.055513175229112595,
      "thai_tokenized_wer": 0.10719040336874731,
      "loanword_error_rate": 0.45901639344262296,
      "loanword_count": 61,
      "loanword_errors": 28
    }
  ],
  "grounding_baselines": [
    {
      "slice": "grounding_model+input_condition+asr_model",
      "grounding_model": "G1",
      "input_condition": "asr_typhoon_asr_api",
      "asr_model": "typhoon_asr_api",
      "n_total": 471,
      "n_success_parse": 471,
      "n_failed_parse": 0,
      "parse_failure_rate": 0.0,
      "point_in_image_rate": 1.0,
      "click_accuracy_including_failures": 0.7643312101910829,
      "click_accuracy_success_only": 0.7643312101910829,
      "gold_click_accuracy": 0.765625,
      "absolute_drop_from_gold": 0.0012937898089171451
    },
    {
      "slice": "grounding_model+input_condition+asr_model",
      "grounding_model": "G1",
      "input_condition": "asr_whisper_large_v3_local",
      "asr_model": "whisper_large_v3_local",
      "n_total": 471,
      "n_success_parse": 471,
      "n_failed_parse": 0,
      "parse_failure_rate": 0.0,
      "point_in_image_rate": 1.0,
      "click_accuracy_including_failures": 0.7579617834394905,
      "click_accuracy_success_only": 0.7579617834394905,
      "gold_click_accuracy": 0.765625,
      "absolute_drop_from_gold": 0.0076632165605095
    },
    {
      "slice": "grounding_model+input_condition+asr_model",
      "grounding_model": "G1",
      "input_condition": "gold",
      "asr_model": null,
      "n_total": 128,
      "n_success_parse": 128,
      "n_failed_parse": 0,
      "parse_failure_rate": 0.0,
      "point_in_image_rate": 1.0,
      "click_accuracy_including_failures": 0.765625,
      "click_accuracy_success_only": 0.765625,
      "gold_click_accuracy": 0.765625,
      "absolute_drop_from_gold": 0.0
    },
    {
      "slice": "grounding_model+input_condition+asr_model",
      "grounding_model": "G2",
      "input_condition": "asr_typhoon_asr_api",
      "asr_model": "typhoon_asr_api",
      "n_total": 471,
      "n_success_parse": 442,
      "n_failed_parse": 29,
      "parse_failure_rate": 0.06157112526539278,
      "point_in_image_rate": 0.9065817409766455,
      "click_accuracy_including_failures": 0.4033970276008493,
      "click_accuracy_success_only": 0.4298642533936652,
      "gold_click_accuracy": 0.4453125,
      "absolute_drop_from_gold": 0.04191547239915072
    },
    {
      "slice": "grounding_model+input_condition+asr_model",
      "grounding_model": "G2",
      "input_condition": "asr_whisper_large_v3_local",
      "asr_model": "whisper_large_v3_local",
      "n_total": 471,
      "n_success_parse": 437,
      "n_failed_parse": 34,
      "parse_failure_rate": 0.07218683651804671,
      "point_in_image_rate": 0.9193205944798302,
      "click_accuracy_including_failures": 0.39065817409766457,
      "click_accuracy_success_only": 0.42105263157894735,
      "gold_click_accuracy": 0.4453125,
      "absolute_drop_from_gold": 0.05465432590233543
    },
    {
      "slice": "grounding_model+input_condition+asr_model",
      "grounding_model": "G2",
      "input_condition": "gold",
      "asr_model": null,
      "n_total": 128,
      "n_success_parse": 119,
      "n_failed_parse": 9,
      "parse_failure_rate": 0.0703125,
      "point_in_image_rate": 0.9140625,
      "click_accuracy_including_failures": 0.4453125,
      "click_accuracy_success_only": 0.4789915966386555,
      "gold_click_accuracy": 0.4453125,
      "absolute_drop_from_gold": 0.0
    }
  ],
  "correction_effects": [
    {
      "grounding_model": "G1",
      "asr_model": "typhoon_asr_api",
      "correction_method": "A_no_screen_cleanup",
      "n_total": 471,
      "changed_count": 0,
      "changed_rate": 0.0,
      "recovery_count": 0,
      "recovery_rate": 0.0,
      "false_correction_count": 0,
      "false_correction_rate": 0.0,
      "net_transcript_benefit": 0,
      "raw_click_accuracy": 0.764331,
      "corrected_run_click_accuracy": 0.751592,
      "pooled_click_delta": -0.012739,
      "CC": 349,
      "WC": 5,
      "CW": 11,
      "WW": 106,
      "classification": "dominated by independent rerun variability"
    },
    {
      "grounding_model": "G1",
      "asr_model": "typhoon_asr_api",
      "correction_method": "B_screen_string_match",
      "n_total": 471,
      "changed_count": 0,
      "changed_rate": 0.0,
      "recovery_count": 0,
      "recovery_rate": 0.0,
      "false_correction_count": 0,
      "false_correction_rate": 0.0,
      "net_transcript_benefit": 0,
      "raw_click_accuracy": 0.764331,
      "corrected_run_click_accuracy": 0.755839,
      "pooled_click_delta": -0.008493,
      "CC": 348,
      "WC": 8,
      "CW": 12,
      "WW": 103,
      "classification": "dominated by independent rerun variability"
    },
    {
      "grounding_model": "G1",
      "asr_model": "typhoon_asr_api",
      "correction_method": "C_full_screen_aware_alias",
      "n_total": 471,
      "changed_count": 53,
      "changed_rate": 0.11252653927813164,
      "recovery_count": 15,
      "recovery_rate": 0.03184713375796178,
      "false_correction_count": 48,
      "false_correction_rate": 0.10191082802547771,
      "net_transcript_benefit": -33,
      "raw_click_accuracy": 0.764331,
      "corrected_run_click_accuracy": 0.751592,
      "pooled_click_delta": -0.012739,
      "CC": 346,
      "WC": 8,
      "CW": 14,
      "WW": 103,
      "classification": "apparent correction degradation"
    },
    {
      "grounding_model": "G1",
      "asr_model": "whisper_large_v3_local",
      "correction_method": "A_no_screen_cleanup",
      "n_total": 471,
      "changed_count": 72,
      "changed_rate": 0.15286624203821655,
      "recovery_count": 0,
      "recovery_rate": 0.0,
      "false_correction_count": 72,
      "false_correction_rate": 0.15286624203821655,
      "net_transcript_benefit": -72,
      "raw_click_accuracy": 0.757962,
      "corrected_run_click_accuracy": 0.751592,
      "pooled_click_delta": -0.006369,
      "CC": 350,
      "WC": 4,
      "CW": 7,
      "WW": 110,
      "classification": "apparent correction benefit"
    },
    {
      "grounding_model": "G1",
      "asr_model": "whisper_large_v3_local",
      "correction_method": "B_screen_string_match",
      "n_total": 471,
      "changed_count": 72,
      "changed_rate": 0.15286624203821655,
      "recovery_count": 3,
      "recovery_rate": 0.006369426751592357,
      "false_correction_count": 72,
      "false_correction_rate": 0.15286624203821655,
      "net_transcript_benefit": -69,
      "raw_click_accuracy": 0.757962,
      "corrected_run_click_accuracy": 0.753715,
      "pooled_click_delta": -0.004246,
      "CC": 349,
      "WC": 6,
      "CW": 8,
      "WW": 108,
      "classification": "apparent correction benefit"
    },
    {
      "grounding_model": "G1",
      "asr_model": "whisper_large_v3_local",
      "correction_method": "C_full_screen_aware_alias",
      "n_total": 471,
      "changed_count": 113,
      "changed_rate": 0.23991507430997877,
      "recovery_count": 8,
      "recovery_rate": 0.016985138004246284,
      "false_correction_count": 110,
      "false_correction_rate": 0.23354564755838642,
      "net_transcript_benefit": -102,
      "raw_click_accuracy": 0.757962,
      "corrected_run_click_accuracy": 0.738854,
      "pooled_click_delta": -0.019108,
      "CC": 345,
      "WC": 3,
      "CW": 12,
      "WW": 111,
      "classification": "apparent correction degradation"
    },
    {
      "grounding_model": "G2",
      "asr_model": "typhoon_asr_api",
      "correction_method": "A_no_screen_cleanup",
      "n_total": 471,
      "changed_count": 0,
      "changed_rate": 0.0,
      "recovery_count": 0,
      "recovery_rate": 0.0,
      "false_correction_count": 0,
      "false_correction_rate": 0.0,
      "net_transcript_benefit": 0,
      "raw_click_accuracy": 0.403397,
      "corrected_run_click_accuracy": 0.341826,
      "pooled_click_delta": -0.061571,
      "CC": 112,
      "WC": 49,
      "CW": 78,
      "WW": 232,
      "classification": "dominated by independent rerun variability"
    },
    {
      "grounding_model": "G2",
      "asr_model": "typhoon_asr_api",
      "correction_method": "B_screen_string_match",
      "n_total": 471,
      "changed_count": 0,
      "changed_rate": 0.0,
      "recovery_count": 0,
      "recovery_rate": 0.0,
      "false_correction_count": 0,
      "false_correction_rate": 0.0,
      "net_transcript_benefit": 0,
      "raw_click_accuracy": 0.403397,
      "corrected_run_click_accuracy": 0.401274,
      "pooled_click_delta": -0.002123,
      "CC": 120,
      "WC": 69,
      "CW": 70,
      "WW": 212,
      "classification": "dominated by independent rerun variability"
    },
    {
      "grounding_model": "G2",
      "asr_model": "typhoon_asr_api",
      "correction_method": "C_full_screen_aware_alias",
      "n_total": 471,
      "changed_count": 53,
      "changed_rate": 0.11252653927813164,
      "recovery_count": 15,
      "recovery_rate": 0.03184713375796178,
      "false_correction_count": 48,
      "false_correction_rate": 0.10191082802547771,
      "net_transcript_benefit": -33,
      "raw_click_accuracy": 0.403397,
      "corrected_run_click_accuracy": 0.388535,
      "pooled_click_delta": -0.014862,
      "CC": 125,
      "WC": 58,
      "CW": 65,
      "WW": 223,
      "classification": "dominated by independent rerun variability"
    },
    {
      "grounding_model": "G2",
      "asr_model": "whisper_large_v3_local",
      "correction_method": "A_no_screen_cleanup",
      "n_total": 471,
      "changed_count": 72,
      "changed_rate": 0.15286624203821655,
      "recovery_count": 0,
      "recovery_rate": 0.0,
      "false_correction_count": 72,
      "false_correction_rate": 0.15286624203821655,
      "net_transcript_benefit": -72,
      "raw_click_accuracy": 0.390658,
      "corrected_run_click_accuracy": 0.392781,
      "pooled_click_delta": 0.002123,
      "CC": 124,
      "WC": 61,
      "CW": 60,
      "WW": 226,
      "classification": "mixed or inconclusive"
    },
    {
      "grounding_model": "G2",
      "asr_model": "whisper_large_v3_local",
      "correction_method": "B_screen_string_match",
      "n_total": 471,
      "changed_count": 72,
      "changed_rate": 0.15286624203821655,
      "recovery_count": 3,
      "recovery_rate": 0.006369426751592357,
      "false_correction_count": 72,
      "false_correction_rate": 0.15286624203821655,
      "net_transcript_benefit": -69,
      "raw_click_accuracy": 0.390658,
      "corrected_run_click_accuracy": 0.373673,
      "pooled_click_delta": -0.016985,
      "CC": 121,
      "WC": 55,
      "CW": 63,
      "WW": 232,
      "classification": "mixed or inconclusive"
    },
    {
      "grounding_model": "G2",
      "asr_model": "whisper_large_v3_local",
      "correction_method": "C_full_screen_aware_alias",
      "n_total": 471,
      "changed_count": 113,
      "changed_rate": 0.23991507430997877,
      "recovery_count": 8,
      "recovery_rate": 0.016985138004246284,
      "false_correction_count": 110,
      "false_correction_rate": 0.23354564755838642,
      "net_transcript_benefit": -102,
      "raw_click_accuracy": 0.390658,
      "corrected_run_click_accuracy": 0.350318,
      "pooled_click_delta": -0.04034,
      "CC": 121,
      "WC": 44,
      "CW": 63,
      "WW": 243,
      "classification": "dominated by independent rerun variability"
    }
  ],
  "correction_interpretation": {
    "pooled_click_delta_is_causal_correction_effect": false,
    "pooled_delta_contains": [
      "correction-related transcript effects",
      "independent grounding rerun variability"
    ],
    "unchanged_subset_delta_interpretation": "independent grounding rerun variability",
    "method_c_degradation_supported": true,
    "whisper_a_b_changed_subset_gains_supported_for_g1": true,
    "g2_repeatability_limitation": true
  },
  "table_paths": {
    "table1": "data/results/table1_dataset_statistics.csv",
    "table2": "data/results/table2_asr_performance.csv",
    "table3": "data/results/table3_grounding_degradation.csv",
    "table4": "data/results/table4_correction_effects.csv",
    "table4b": "data/results/table4b_changed_unchanged_effects.csv"
  }
}
```
