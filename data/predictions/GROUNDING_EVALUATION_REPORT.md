# Grounding Evaluation Report

## Summary By Condition

| input_condition | grounding_model | asr_model | n_total | n_success_parse | n_failed_parse | parse_failure_rate | point_in_image_rate | click_accuracy_including_failures | click_accuracy_success_only | element_accuracy_including_failures |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| asr_typhoon_asr_api | G1 | typhoon_asr_api | 471 | 471 | 0 | 0.000000 | 1.000000 | 0.764331 | 0.764331 | 0.764331 |
| asr_typhoon_asr_api | G2 | typhoon_asr_api | 471 | 442 | 29 | 0.061571 | 0.906582 | 0.403397 | 0.429864 | 0.403397 |
| asr_whisper_large_v3_local | G1 | whisper_large_v3_local | 471 | 471 | 0 | 0.000000 | 1.000000 | 0.757962 | 0.757962 | 0.757962 |
| asr_whisper_large_v3_local | G2 | whisper_large_v3_local | 471 | 437 | 34 | 0.072187 | 0.919321 | 0.390658 | 0.421053 | 0.390658 |
| corrected_A_no_screen_cleanup_typhoon | G1 | typhoon_asr_api | 471 | 471 | 0 | 0.000000 | 1.000000 | 0.751592 | 0.751592 | 0.751592 |
| corrected_A_no_screen_cleanup_typhoon | G2 | typhoon_asr_api | 471 | 439 | 32 | 0.067941 | 0.912951 | 0.341826 | 0.366743 | 0.341826 |
| corrected_A_no_screen_cleanup_whisper | G1 | whisper_large_v3_local | 471 | 471 | 0 | 0.000000 | 1.000000 | 0.751592 | 0.751592 | 0.751592 |
| corrected_A_no_screen_cleanup_whisper | G2 | whisper_large_v3_local | 471 | 451 | 20 | 0.042463 | 0.940552 | 0.392781 | 0.410200 | 0.392781 |
| corrected_B_screen_string_match_typhoon | G1 | typhoon_asr_api | 471 | 471 | 0 | 0.000000 | 1.000000 | 0.755839 | 0.755839 | 0.755839 |
| corrected_B_screen_string_match_typhoon | G2 | typhoon_asr_api | 471 | 447 | 24 | 0.050955 | 0.934183 | 0.401274 | 0.422819 | 0.401274 |
| corrected_B_screen_string_match_whisper | G1 | whisper_large_v3_local | 471 | 471 | 0 | 0.000000 | 1.000000 | 0.753715 | 0.753715 | 0.753715 |
| corrected_B_screen_string_match_whisper | G2 | whisper_large_v3_local | 471 | 440 | 31 | 0.065817 | 0.902335 | 0.373673 | 0.400000 | 0.373673 |
| corrected_C_full_screen_aware_alias_typhoon | G1 | typhoon_asr_api | 471 | 471 | 0 | 0.000000 | 1.000000 | 0.751592 | 0.751592 | 0.751592 |
| corrected_C_full_screen_aware_alias_typhoon | G2 | typhoon_asr_api | 471 | 427 | 44 | 0.093418 | 0.885350 | 0.388535 | 0.428571 | 0.388535 |
| corrected_C_full_screen_aware_alias_whisper | G1 | whisper_large_v3_local | 471 | 471 | 0 | 0.000000 | 1.000000 | 0.738854 | 0.738854 | 0.738854 |
| corrected_C_full_screen_aware_alias_whisper | G2 | whisper_large_v3_local | 471 | 436 | 35 | 0.074310 | 0.906582 | 0.350318 | 0.378440 | 0.350318 |
| gold | G1 |  | 128 | 128 | 0 | 0.000000 | 1.000000 | 0.765625 | 0.765625 | 0.765625 |
| gold | G2 |  | 128 | 119 | 9 | 0.070312 | 0.914062 | 0.445312 | 0.478992 | 0.445312 |

## Failed Or Skipped Predictions

- G2__gold__map_send_money_001_t2_paraphrase_01: JSON response did not contain pred_x/pred_y or click coordinate
- G2__gold__map_view_monthly_statement_001_t2_paraphrase_01: JSON response did not contain pred_x/pred_y or click coordinate
- G2__gold__map_open_wallet_balance_001_t3_intent_01: JSON response did not contain pred_x/pred_y or click coordinate
- G2__gold__map_open_cart_001_t4_visual_positional_01: JSON response did not contain pred_x/pred_y or click coordinate
- G2__gold__map_change_language_001_t1_verbatim_01: JSON response did not contain pred_x/pred_y or click coordinate
- G2__gold__map_turn_off_notifications_001_t1_verbatim_01: JSON response did not contain pred_x/pred_y or click coordinate
- G2__gold__map_open_privacy_settings_001_t2_paraphrase_01: JSON response did not contain pred_x/pred_y or click coordinate
- G2__gold__map_manage_payment_methods_mock_001_t1_verbatim_01: JSON response did not contain pred_x/pred_y or click coordinate
- G2__gold__map_compose_new_message_001_t1_verbatim_01: JSON response did not contain pred_x/pred_y or click coordinate
- G2__asr_whisper_large_v3_local__azure__voice_01__dev__map_buy_now_001_t4_visual_positional_01: pred_x must be numeric
- G2__asr_whisper_large_v3_local__openai__voice_01__dev__map_change_password_mock_001_t2_paraphrase_01: pred_x must be numeric
- G2__asr_whisper_large_v3_local__azure__voice_01__dev__map_compose_new_message_001_t2_paraphrase_01: JSON response did not contain pred_x/pred_y or click coordinate
- G2__asr_whisper_large_v3_local__openai__voice_02__dev__map_top_up_mobile_001_t1_verbatim_01: could not convert string to float: '546,1203'
- G2__asr_whisper_large_v3_local__azure__voice_01__dev__map_top_up_mobile_001_t1_verbatim_01: JSON response did not contain pred_x/pred_y or click coordinate
- G2__asr_whisper_large_v3_local__openai__voice_01__dev__map_top_up_mobile_001_t3_intent_01: JSON response did not contain pred_x/pred_y or click coordinate
- G2__asr_whisper_large_v3_local__azure__voice_01__dev__map_view_promotion_001_t2_paraphrase_01: JSON response did not contain pred_x/pred_y or click coordinate
- G2__asr_whisper_large_v3_local__openai__voice_02__test__map_apply_filter_001_t2_paraphrase_01: could not convert string to float: '301,518'
- G2__asr_whisper_large_v3_local__azure__voice_01__test__map_apply_filter_001_t2_paraphrase_01: JSON response did not contain pred_x/pred_y or click coordinate
- G2__asr_whisper_large_v3_local__openai__voice_02__test__map_apply_filter_001_t4_visual_positional_01: JSON response did not contain pred_x/pred_y or click coordinate
- G2__asr_whisper_large_v3_local__openai__voice_01__test__map_change_language_001_t1_verbatim_01: JSON response did not contain pred_x/pred_y or click coordinate
