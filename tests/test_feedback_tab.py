"""Feedback tab lifecycle regression tests."""

from types import SimpleNamespace

from ui.feedback_tab import update_feedback_values


def test_feedback_update_before_tab_creation_is_safe():
    app = SimpleNamespace()

    assert update_feedback_values(app) is None
