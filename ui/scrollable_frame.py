import customtkinter as ctk
import weakref
from tkinter import TclError


def widget_exists(widget):
    """Return False for widgets whose Tcl command has already been removed."""
    if widget is None:
        return False
    try:
        return bool(widget.winfo_exists())
    except TclError:
        return False
    except AttributeError:
        # Lightweight widgets used by unit tests do not expose winfo_exists.
        return True


def safe_scrollbar_set(scrollbar, first, last):
    if not widget_exists(scrollbar):
        return
    try:
        scrollbar.set(first, last)
    except TclError:
        return


def safe_canvas_yview(canvas, *args):
    if not widget_exists(canvas):
        return
    try:
        canvas.yview(*args)
    except TclError:
        return


def normalized_scroll_units(event):
    """Return a small, platform-independent vertical scroll amount."""
    number = getattr(event, "num", None)
    if number == 4:
        return -1
    if number == 5:
        return 1

    delta = getattr(event, "delta", 0) or 0
    if not delta:
        return 0
    direction = -1 if delta > 0 else 1
    magnitude = max(1, min(3, int(abs(delta)) // 120 or 1))
    return direction * magnitude


class SafeScrollableFrame(ctk.CTkScrollableFrame):
    """Scrollable frame with bounded wheel motion and safe event targeting."""

    _instances = weakref.WeakSet()
    _linux_dispatch_bound = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._instances.add(self)
        # Tk reports Linux wheel motion as buttons. Install one application
        # dispatcher, rather than one global callback per canvas.
        if not self.__class__._linux_dispatch_bound:
            self.bind_all("<Button-4>", self.__class__._dispatch_linux_wheel, add="+")
            self.bind_all("<Button-5>", self.__class__._dispatch_linux_wheel, add="+")
            self.__class__._linux_dispatch_bound = True

    @classmethod
    def _dispatch_linux_wheel(cls, event):
        for frame in tuple(cls._instances):
            if not widget_exists(frame):
                cls._instances.discard(frame)
                continue
            if frame.check_if_master_is_canvas(getattr(event, "widget", None)):
                frame._mouse_wheel_all(event)
                return

    def check_if_master_is_canvas(self, widget):
        if widget == self._parent_canvas:
            return True
        if not hasattr(widget, "master") or widget.master is None:
            return False
        return self.check_if_master_is_canvas(widget.master)

    def _mouse_wheel_all(self, event):
        # CustomTkinter dispatches wheel events globally.  The ancestry check is
        # what prevents Digital, Analog, and hidden tabs scrolling together.
        if not self.check_if_master_is_canvas(getattr(event, "widget", None)):
            return
        units = normalized_scroll_units(event)
        if not units:
            return
        shift = bool(getattr(event, "state", 0) & 0x0001) or getattr(
            self, "_shift_pressed", False
        )
        if shift and hasattr(self._parent_canvas, "xview_scroll"):
            self._parent_canvas.xview_scroll(units, "units")
        else:
            # yview("scroll", ...) also works with lightweight test canvases
            # and is the canonical Tk canvas API.
            self._parent_canvas.yview("scroll", units, "units")

    def scroll_units(self, units):
        safe_canvas_yview(self._parent_canvas, "scroll", int(units), "units")

    def disconnect_scroll_callbacks(self):
        """Break Tcl/Python scroll links before a containing UI is destroyed."""
        try:
            if widget_exists(self._parent_canvas):
                self._parent_canvas.configure(yscrollcommand="")
        except TclError:
            pass
        try:
            if widget_exists(self._scrollbar):
                self._scrollbar.configure(command=None)
        except TclError:
            pass

    def install_navigation(self):
        """Integrate compact arrows directly above/below the scrollbar."""
        # CTk creates a stock scrollbar as part of construction. Replacing it is
        # initialization, not refresh; sever its canvas callback first.
        self.disconnect_scroll_callbacks()
        if widget_exists(self._scrollbar):
            self._scrollbar.destroy()
        self._navigation_frame = ctk.CTkFrame(
            self._parent_frame, width=30, fg_color="transparent"
        )
        self._navigation_frame.grid(row=1, column=1, sticky="ns")
        self._navigation_frame.grid_rowconfigure(1, weight=1)
        self._up_button = ctk.CTkButton(
            self._navigation_frame, text="▲", width=28, height=26,
            command=lambda: self.scroll_units(-1),
        )
        self._up_button.grid(row=0, column=0, sticky="ew", pady=(0, 2))
        self._scrollbar = ctk.CTkScrollbar(
            self._navigation_frame, orientation="vertical",
            command=lambda *args: safe_canvas_yview(self._parent_canvas, *args),
        )
        self._scrollbar.grid(row=1, column=0, sticky="ns")
        self._down_button = ctk.CTkButton(
            self._navigation_frame, text="▼", width=28, height=26,
            command=lambda: self.scroll_units(1),
        )
        self._down_button.grid(row=2, column=0, sticky="ew", pady=(2, 0))
        scrollbar = self._scrollbar
        self._parent_canvas.configure(
            yscrollcommand=lambda first, last: safe_scrollbar_set(
                scrollbar, first, last
            )
        )
        return self._navigation_frame
