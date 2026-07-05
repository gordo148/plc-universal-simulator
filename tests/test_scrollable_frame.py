from types import SimpleNamespace

from ui.scrollable_frame import SafeScrollableFrame


def build_frame(canvas):
    frame = object.__new__(SafeScrollableFrame)
    frame._parent_canvas = canvas
    return frame


def test_stale_string_widget_is_not_treated_as_scrollable_child():
    frame = build_frame(object())

    assert frame.check_if_master_is_canvas(".!destroyed_widget") is False


def test_mouse_wheel_ignores_stale_string_widget_without_exception():
    frame = build_frame(object())

    frame._mouse_wheel_all(SimpleNamespace(widget=".!destroyed_widget"))


def test_widget_ancestor_chain_reaches_scrollable_canvas():
    canvas = object()
    frame = build_frame(canvas)
    child = SimpleNamespace(master=SimpleNamespace(master=canvas))

    assert frame.check_if_master_is_canvas(child) is True


def test_mouse_wheel_still_scrolls_for_valid_widget():
    class Canvas:
        def __init__(self):
            self.scroll_calls = []

        def yview(self, *args):
            if args:
                self.scroll_calls.append(args)
            return (0.0, 0.5)

    canvas = Canvas()
    frame = build_frame(canvas)
    frame._shift_pressed = False
    child = SimpleNamespace(master=canvas)

    frame._mouse_wheel_all(SimpleNamespace(widget=child, delta=-1))

    assert canvas.scroll_calls == [("scroll", 1, "units")]
