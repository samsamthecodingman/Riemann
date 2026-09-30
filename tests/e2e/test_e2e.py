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
]


@pytest.mark.parametrize("check", CHECKS)
def test_browser_check(run_check, check):
    run_check(check)


@pytest.mark.parametrize("seed", [7, 21])
def test_monkey_seed_has_no_errors_overflow_or_lost_header(run_check, seed):
    run_check("monkey_seed", str(seed), "60")
