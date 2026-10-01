"""Browser tests (opt-in; see conftest.py). Each test runs one check in
runner.js against a live server with a FakeSummariser."""

import pytest

CHECKS = [
    "zoom_grows_words",
    "pin_drift_under_2px",
    "map_toggle_and_jump",
    "columns_drag_persists",
    "palette_and_highlight_persist",
    "poisoned_localstorage_is_harmless",
    "xss_payload_in_tree_text_is_escaped",
    "overview_card_renders",
    "phone_layout_no_overflow",
    "columns_switch_to_one_when_lines_get_short",
    "doit_tiles_start_due_size_and_relative_days",
    "meeting_actions_list_with_relative_days",
    "search_whole_document_and_navigate",
    "search_at_every_depth_never_errors_and_finds_summaries",
    "cjk_word_count_agrees_with_server",
    "failed_build_shows_message_and_retries",
]


@pytest.mark.parametrize("check", CHECKS)
def test_browser_check(run_check, check):
    run_check(check)


@pytest.mark.parametrize("seed", [7, 21])
def test_monkey_seed_has_no_errors_overflow_or_lost_header(run_check, seed):
    run_check("monkey_seed", str(seed), "60")
