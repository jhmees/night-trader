"""Overlay note card: tiny always-on-top tkinter window, click to dismiss.

Ugly by design (see design doc: "No polish. Python, ugly window, works").
Tk must run on the main thread on macOS — main.py owns the mainloop and
feeds cards in via show(), which is thread-safe.
"""

from __future__ import annotations

import tkinter as tk


class Overlay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.overrideredirect(True)          # no title bar
        self.root.attributes("-topmost", True)
        try:
            self.root.attributes("-alpha", 0.92)
        except tk.TclError:
            pass
        self.label = tk.Label(
            self.root, text="", font=("Menlo", 13), fg="#e8e8e8", bg="#1e1e28",
            wraplength=380, justify="left", padx=14, pady=10,
        )
        self.label.pack()
        self.label.bind("<Button-1>", lambda e: self.hide())

    def show(self, text: str) -> None:
        """Thread-safe: schedule the update on the Tk main thread."""
        self.root.after(0, self._show, text)

    def _show(self, text: str) -> None:
        self.label.config(text=text)
        self.root.update_idletasks()
        # top-right corner, small margin
        w = self.label.winfo_reqwidth()
        x = self.root.winfo_screenwidth() - w - 24
        self.root.geometry(f"+{x}+40")
        self.root.deiconify()

    def hide(self) -> None:
        self.root.withdraw()

    def mainloop(self) -> None:
        self.root.mainloop()
