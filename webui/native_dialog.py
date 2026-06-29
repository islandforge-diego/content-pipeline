"""native_dialog.py — open the OS-native file/folder picker, cross-platform.

Uses each platform's built-in dialog so there are no extra dependencies:
  - macOS   → AppleScript via `osascript` (always present; Homebrew Python has no Tk)
  - Windows → PowerShell + System.Windows.Forms
  - other   → tkinter in a subprocess (Linux with python3-tk)

Returns the selected path, or '' if cancelled.
"""
import subprocess
import sys


# ---------------------------------------------------------------- macOS

def _macos(kind: str) -> str:
    if kind == "folder":
        script = 'POSIX path of (choose folder with prompt "Select a folder")'
    else:
        script = 'POSIX path of (choose file with prompt "Select a photo or video")'
    out = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, encoding="utf-8", errors="replace")
    # Cancel → non-zero exit ("User canceled"); success → POSIX path on stdout
    return out.stdout.strip() if out.returncode == 0 else ""


# ---------------------------------------------------------------- Windows

_WIN_FILE = r"""
Add-Type -AssemblyName System.Windows.Forms
$d = New-Object System.Windows.Forms.OpenFileDialog
$d.Title = 'Select a photo or video'
if ($d.ShowDialog() -eq 'OK') { [Console]::Out.Write($d.FileName) }
"""

_WIN_FOLDER = r"""
Add-Type -AssemblyName System.Windows.Forms
$d = New-Object System.Windows.Forms.FolderBrowserDialog
$d.Description = 'Select a folder'
if ($d.ShowDialog() -eq 'OK') { [Console]::Out.Write($d.SelectedPath) }
"""


def _windows(kind: str) -> str:
    script = _WIN_FOLDER if kind == "folder" else _WIN_FILE
    out = subprocess.run(
        ["powershell", "-NoProfile", "-STA", "-Command", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return out.stdout.strip()


# ---------------------------------------------------------------- tkinter fallback

_TK_FILE = """
import tkinter as tk
from tkinter import filedialog
r = tk.Tk(); r.withdraw(); r.attributes('-topmost', True)
print(filedialog.askopenfilename(title='Select a photo or video') or '', end='')
"""

_TK_FOLDER = """
import tkinter as tk
from tkinter import filedialog
r = tk.Tk(); r.withdraw(); r.attributes('-topmost', True)
print(filedialog.askdirectory(title='Select a folder') or '', end='')
"""


def _tk(kind: str) -> str:
    snippet = _TK_FOLDER if kind == "folder" else _TK_FILE
    try:
        out = subprocess.run([sys.executable, "-c", snippet], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        return out.stdout.strip()
    except Exception:
        return ""


# ---------------------------------------------------------------- dispatch

def _pick(kind: str) -> str:
    try:
        if sys.platform == "darwin":
            return _macos(kind)
        if sys.platform.startswith("win"):
            return _windows(kind)
        return _tk(kind)
    except Exception:
        return ""


def pick_file() -> str:
    """Open a native file picker. Returns the chosen path or '' if cancelled."""
    return _pick("file")


def pick_folder() -> str:
    """Open a native folder picker. Returns the chosen path or '' if cancelled."""
    return _pick("folder")
