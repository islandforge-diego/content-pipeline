"""native_dialog.py — open the OS-native file/folder picker, cross-platform.

Runs tkinter in a SEPARATE subprocess. This avoids two problems:
  1. On macOS, tkinter must own the main thread — it can't run inside a Flask
     worker thread. A subprocess sidesteps that entirely.
  2. The dialog appears as its own window (Finder on macOS, Explorer on Windows,
     GTK on Linux) and the subprocess exits cleanly when the user is done.

Returns the selected path(s), or None / [] if cancelled.
"""
import subprocess
import sys

# Code executed in the child process. Prints the chosen path to stdout.
_FILE_SNIPPET = """
import tkinter as tk
from tkinter import filedialog
r = tk.Tk(); r.withdraw(); r.attributes('-topmost', True)
p = filedialog.askopenfilename(title='Select a photo or video')
print(p or '', end='')
"""

_FOLDER_SNIPPET = """
import tkinter as tk
from tkinter import filedialog
r = tk.Tk(); r.withdraw(); r.attributes('-topmost', True)
p = filedialog.askdirectory(title='Select a folder')
print(p or '', end='')
"""


def _run(snippet: str) -> str:
    try:
        out = subprocess.run(
            [sys.executable, "-c", snippet],
            capture_output=True, text=True, timeout=300,
        )
        return out.stdout.strip()
    except Exception:
        return ""


def pick_file() -> str:
    """Open a native file picker. Returns the chosen path or '' if cancelled."""
    return _run(_FILE_SNIPPET)


def pick_folder() -> str:
    """Open a native folder picker. Returns the chosen path or '' if cancelled."""
    return _run(_FOLDER_SNIPPET)
