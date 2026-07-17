"""Shared, lightweight behavior for simulation Treeviews."""

import re
from tkinter import TclError


PAGE_SIZES = ("25", "50", "100", "250", "All")
NATURAL_PARTS = re.compile(r"(\d+)")


def natural_key(value):
    return tuple(
        int(part) if part.isdigit() else part.casefold()
        for part in NATURAL_PARTS.split(str(value))
    )


def filter_tags(tags, query):
    query = str(query or "").strip().casefold()
    if not query:
        return list(tags)
    return [
        tag for tag in tags
        if query in tag.name.casefold()
        or query in tag.address.casefold()
        or query in getattr(tag, "comment", "").casefold()
        or query in tag.data_type.casefold()
    ]


def sort_tags(tags, column, descending=False, settings=None, values=None):
    settings, values = settings or {}, values or {}
    def key(tag):
        if column == "address": return natural_key(tag.address)
        if column == "name": return natural_key(tag.name)
        if column == "type": return natural_key(tag.data_type)
        setting = settings.get(getattr(tag, "tag_id", ""), settings.get(tag.name, {}))
        if column == "mode": return natural_key(setting.get("mode", ""))
        if column in ("status", "value"): return (values.get(tag.name) is None, values.get(tag.name, 0))
        if column == "profile": return natural_key(setting.get("mode", "Manual"))
        if column == "difference": return bool(values.get(tag.name, False))
        return natural_key(tag.name)
    return sorted(tags, key=key, reverse=bool(descending))


def page_tags(tags, page, page_size):
    if str(page_size) == "All":
        return 0, 1, 0, list(tags)
    size = max(1, int(page_size))
    count = max(1, (len(tags) + size - 1) // size)
    page = min(max(0, int(page)), count - 1)
    start = page * size
    return page, count, start, list(tags[start:start + size])


def debounce(app, owner, delay_ms, callback):
    attribute = f"_{owner}_debounce_job"
    previous = getattr(app, attribute, None)
    if previous is not None:
        try: app.cancel_job(previous)
        except (TclError, ValueError): pass
    job = None
    def run():
        if getattr(app, attribute, None) == job:
            setattr(app, attribute, None)
        callback()
    job = app.schedule_job(delay_ms, run)
    setattr(app, attribute, job)


def clear_entry(entry):
    entry.delete(0, "end")


def copy_text(widget, text):
    widget.clipboard_clear()
    widget.clipboard_append(str(text))


def move_selection(table, key):
    children = table.get_children()
    if not children:
        return None
    selected = table.selection()
    index = table.index(selected[0]) if selected else 0
    page = max(1, int(table.cget("height") or 10)) if hasattr(table, "cget") else 10
    index = {
        "Up": index - 1, "Down": index + 1,
        "Prior": index - page, "Next": index + page,
        "Home": 0, "End": len(children) - 1,
    }.get(key, index)
    index = min(max(0, index), len(children) - 1)
    item = children[index]
    table.selection_set(item)
    table.focus(item)
    table.see(item)
    return item


class ToolTip:
    """Small dependency-free tooltip for Tk/CTk widgets."""
    def __init__(self, widget, text):
        self.widget, self.text, self.window = widget, text, None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")

    def show(self, _event=None):
        if self.window is not None: return
        text = self.text() if callable(self.text) else self.text
        if not text: return
        import tkinter as tk
        self.window = tk.Toplevel(self.widget)
        self.window.wm_overrideredirect(True)
        self.window.wm_geometry(f"+{self.widget.winfo_rootx() + 12}+{self.widget.winfo_rooty() + 28}")
        tk.Label(self.window, text=text, bg="#263238", fg="white", relief="solid", borderwidth=1, padx=6, pady=3, wraplength=420, justify="left").pack()

    def hide(self, _event=None):
        if self.window is not None:
            self.window.destroy()
            self.window = None


def tag_comment_tooltip(widget, tag_or_resolver):
    """Attach a tooltip that exposes a tag comment without changing its label."""
    def text():
        tag = tag_or_resolver() if callable(tag_or_resolver) else tag_or_resolver
        if tag is None or not getattr(tag, "comment", ""):
            return ""
        return f"Name: {tag.name}\nAddress: {tag.address}\nComment: {tag.comment}"
    return ToolTip(widget, text)


def treeview_tag_comment_tooltip(tree, resolver):
    """Show the comment for the Treeview row currently under the pointer."""
    state = {"row": ""}
    tree.bind(
        "<Enter>",
        lambda event: state.update(row=tree.identify_row(event.y)),
        add="+",
    )
    tree.bind(
        "<Motion>",
        lambda event: state.update(row=tree.identify_row(event.y)),
        add="+",
    )
    return tag_comment_tooltip(
        tree,
        lambda: resolver(state["row"]) if state["row"] else None,
    )
