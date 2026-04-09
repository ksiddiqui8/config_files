import os
import tkinter as tk
from pathlib import Path

NOTEBOOK_FILE = Path.home() / ".local/share/qtile_dashboard/shared_notebook.md"
NOTEBOOK_FILE.parent.mkdir(parents=True, exist_ok=True)


class NotebookApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Shared Notebook")
        self.root.geometry("1000x700")

        self.text = tk.Text(root, wrap="word", font=("JetBrains Mono", 12))
        self.text.pack(expand=True, fill="both")

        self.status = tk.Label(root, text="", anchor="w")
        self.status.pack(fill="x")

        self.load_file()

        self.root.bind("<Control-s>", self.save_file)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def load_file(self):
        if NOTEBOOK_FILE.exists():
            content = NOTEBOOK_FILE.read_text(encoding="utf-8")
            self.text.insert("1.0", content)
            self.status.config(text=f"Loaded: {NOTEBOOK_FILE}")
        else:
            self.status.config(text=f"New notebook: {NOTEBOOK_FILE}")

    def save_file(self, event=None):
        content = self.text.get("1.0", "end-1c")
        NOTEBOOK_FILE.write_text(content, encoding="utf-8")
        self.status.config(text=f"Saved: {NOTEBOOK_FILE}")
        return "break"

    def on_close(self):
        self.save_file()
        self.root.destroy()


root = tk.Tk()
app = NotebookApp(root)
root.mainloop()
