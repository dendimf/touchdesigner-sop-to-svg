# extensionHelperMOD (or similar) — put this in a Module or Extension DAT
import os
import sys
import platform
import subprocess
from pathlib import Path
from typing import Optional

# ────────────────────────────────────────────────
#   CONFIG
# ────────────────────────────────────────────────

PROJECT_FOLDER = Path(project.folder)           # type: ignore[name-defined]
DEP_ROOT       = PROJECT_FOLDER / "dep"
PYTHON_DEP_DIR = DEP_ROOT / "python"
SCRIPTS_SUBDIR = "scripts"                      # subfolder name for platform scripts + reqs.txt

# ────────────────────────────────────────────────
#   Helpers
# ────────────────────────────────────────────────

def ensure_directory(path: Path) -> None:
    """Create directory if it doesn't exist."""
    path.mkdir(parents=True, exist_ok=True)


def write_if_changed(path: Path, content: str) -> bool:
    """
    Write content to file only if different → avoids unnecessary file changes.
    Returns True if file was (re)written.
    """
    if path.is_file() and path.read_text(encoding="utf-8").strip() == content.strip():
        return False
    path.write_text(content, encoding="utf-8")
    return True


def add_project_dep_to_syspath() -> bool:
    """Prepend project-specific python deps path to sys.path if missing."""
    dep_str = str(PYTHON_DEP_DIR.resolve())
    if dep_str in sys.path:
        return False

    sys.path.insert(0, dep_str)
    return True


def get_requirements_path() -> Path:
    """Location of requirements.txt for current component."""
    # Assumes script is running in context of a component that has .par.Name
    comp_name = parent().par.Name.val                               # type: ignore
    return DEP_ROOT / SCRIPTS_SUBDIR / comp_name / "requirements.txt"


# ────────────────────────────────────────────────
#   Script templates (as multiline f-strings)
# ────────────────────────────────────────────────

def get_windows_install_script(reqs_dir: Path, target_dir: Path) -> str:
    return f"""@echo off
:: Auto-generated TouchDesigner dependency installer (Windows)
:: Do not edit manually

echo Updating pip...
python -m pip install --upgrade pip

echo Installing requirements to project folder...
pip install --no-warn-script-location ^
    -r "{reqs_dir}\\requirements.txt" ^
    --target "{target_dir}"

echo.
echo Done. You may close this window.
pause
"""


def get_macos_install_script(reqs_dir: Path, target_dir: Path) -> str:
    return f"""#!/usr/bin/env bash
# Auto-generated TouchDesigner dependency installer (macOS)
# Do not edit manually

set -euo pipefail

echo "Updating pip..."
python3 -m pip install --upgrade pip

echo "Installing requirements..."
python3 -m pip install --no-warn-script-location \\
    -r "{reqs_dir}/requirements.txt" \\
    --target "{target_dir}"

echo ""
echo "Done."
read -p "Press Enter to close..."
"""


# ────────────────────────────────────────────────
#   Public API (call these from onSetupParameters / onCook / button callback / etc.)
# ────────────────────────────────────────────────

def ensure_project_python_path(debug: bool = False) -> None:
    """
    Make sure dep/python is in sys.path (idempotent).
    Call this early (e.g. on project start or extension init).
    """
    added = add_project_dep_to_syspath()

    if debug or added:
        print(f"[dep] Project python path: {PYTHON_DEP_DIR}")
        if debug:
            print("[dep] Current sys.path:")
            for p in sys.path:
                print(f"  {p}")


def install_or_update_external_deps(debug: bool = False) -> None:
    """
    Idempotent setup:
      • Create folders
      • Write requirements.txt from 'reqs' DAT if needed
      • Generate platform install script if needed
      • Run install only if python/ folder is empty
    """
    ensure_directory(DEP_ROOT)
    ensure_directory(PYTHON_DEP_DIR)

    reqs_path = get_requirements_path()
    ensure_directory(reqs_path.parent)

    # Write requirements.txt from DAT if missing or empty
    reqs_dat = op("reqs")  # type: ignore[name-defined]
    if not reqs_path.is_file() or not reqs_path.read_text().strip():
        if reqs_dat and reqs_dat.text.strip():
            reqs_path.write_text(reqs_dat.text.strip() + "\n", encoding="utf-8")
            print(f"[dep] Wrote requirements.txt → {reqs_path}")
        else:
            print("[dep] Warning: no requirements content found in 'reqs' DAT")

    # Platform-specific logic
    system = platform.system()

    if system == "Windows":
        script_path = reqs_path.parent / "update-deps-windows.cmd"
        script_content = get_windows_install_script(reqs_path.parent, PYTHON_DEP_DIR)

        if write_if_changed(script_path, script_content):
            print(f"[dep] Updated Windows install script → {script_path}")

        if not any(PYTHON_DEP_DIR.iterdir()):  # empty → install needed
            print("[dep] Installing dependencies (Windows)...")
            subprocess.Popen([str(script_path)], creationflags=subprocess.CREATE_NEW_CONSOLE)

    elif system == "Darwin":
        script_path = reqs_path.parent / "update-deps-mac.sh"
        script_content = get_macos_install_script(reqs_path.parent, PYTHON_DEP_DIR)

        wrote = write_if_changed(script_path, script_content)

        if wrote:
            print(f"[dep] Updated macOS install script → {script_path}")
            os.chmod(script_path, 0o755)

        if not any(PYTHON_DEP_DIR.iterdir()):
            print("[dep] Installing dependencies (macOS)...")
            # Prefer opening in Terminal rather than background process
            subprocess.call(["open", "-a", "Terminal", str(script_path)])

    else:
        print(f"[dep] Unsupported platform: {system} — skipping auto-install")


# For debugging / manual trigger
if __name__ == "__main__" and debug := True:
    ensure_project_python_path(debug=debug)
    install_or_update_external_deps(debug=debug)
