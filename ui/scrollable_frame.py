import customtkinter as ctk


class SafeScrollableFrame(ctk.CTkScrollableFrame):
    """Scrollable frame tolerant of stale Tk mouse-wheel event targets."""

    def check_if_master_is_canvas(self, widget):
        if widget == self._parent_canvas:
            return True
        if not hasattr(widget, "master"):
            return False
        if widget.master is None:
            return False
        return self.check_if_master_is_canvas(widget.master)
