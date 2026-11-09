"""Build the Industrial SPC Analyzer into a standalone Windows executable.

Produces a self-contained, portable runtime that runs on another PC without
installing Python or any dependencies.

Usage (from the project root):
    python build.py [--onefile] [--onedir] [--name NAME] [--console] [--no-venv]

Modes:
    --onefile  (default)  Build a single .exe  -> dist\\<NAME>.exe
    --onedir              Build a folder with the exe + support files
                          (faster startup)     -> dist\\<NAME>\\<NAME>.exe

By default the build runs inside an isolated build virtual environment
(.build-venv) that contains only the runtime dependencies, so the executable
stays small and the build is fast and deterministic. Pass --no-venv to build
using the current Python environment instead.

The generated program stores its local config database and logs next to the
executable, so it is fully portable (no installation required).
"""

import argparse
import os
import shutil
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_NAME = "IndustrialSPCAnalyzer"


def find_pyinstaller():
    """Return the PyInstaller module path or None if unavailable."""
    try:
        import PyInstaller  # noqa: F401
        return True
    except ImportError:
        return False


def ensure_dependencies():
    print("==> Checking build dependencies...")
    if not find_pyinstaller():
        print("PyInstaller is not installed. Installing it now...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pyinstaller"])
    else:
        print("    PyInstaller found.")


def _data_args(onefile):
    """Bundle assets (icon/logo) and optional samples into the build."""
    args = ["--add-data", f"assets{os.pathsep}assets"]
    if os.path.isdir(os.path.join(PROJECT_ROOT, "samples")):
        args.append("--add-data")
        args.append(f"samples{os.pathsep}samples")
    if onefile:
        # a copy of logo is useful at runtime for reports
        args.append("--add-data")
        args.append(f"assets{os.pathsep}.")
    return args


# Modules that are never used by the app but can bloat / slow the build if
# present in the build environment. Excluding them keeps the exe lean.
DEFAULT_EXCLUDES = [
    "tkinter",
    "torch",
    "torchvision",
    "tensorflow",
    "keras",
    "transformers",
    "sklearn",
    "nltk",
    "onnxruntime",
    "spacy",
    "cv2",
    "pydub",
    "IPython",
    "jupyter",
    "notebook",
    "boto3",
    "botocore",
    "google",
    "opentelemetry",
    "kivy",
    "kivymd",
    "playwright",
    "gradio",
    "dash",
    "flask",
    "django",
    "fastapi",
    "uvicorn",
    "altair",
    "plotly",
    "dask",
    "ray",
    "celery",
    "mysql",
    "psycopg2",
    "psycopg",
    "pymysql",
]


def build(onefile, name, console, excludes=None):
    dist_root = os.path.join(PROJECT_ROOT, "dist")
    build_root = os.path.join(PROJECT_ROOT, "build", "pyinstaller")

    # clean previous output
    if os.path.isdir(dist_root):
        shutil.rmtree(dist_root, ignore_errors=True)
    if os.path.isdir(build_root):
        shutil.rmtree(build_root, ignore_errors=True)

    icon = os.path.join(PROJECT_ROOT, "assets", "app.ico")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath", dist_root,
        "--workpath", build_root,
        "--name", name,
        "--windowed" if not console else "--console",
    ]
    if os.path.isfile(icon):
        cmd += ["--icon", icon]

    cmd += _data_args(onefile)

    if onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")

    cmd += ["--hidden-import", "pyodbc"]
    cmd += ["--hidden-import", "openpyxl"]
    cmd += ["--hidden-import", "reportlab"]
    cmd += ["--hidden-import", "matplotlib.backends.backend_agg"]
    cmd += ["--hidden-import", "scipy.stats"]
    cmd += ["--hidden-import", "pandas"]

    exclude_set = set(DEFAULT_EXCLUDES)
    if excludes:
        exclude_set.update(excludes)
    for mod in sorted(exclude_set):
        cmd += ["--exclude-module", mod]

    cmd.append(os.path.join(PROJECT_ROOT, "app.py"))

    print("\n==> Running PyInstaller...")
    print("    " + " ".join(cmd) + "\n")
    subprocess.check_call(cmd, cwd=PROJECT_ROOT)

    if onefile:
        exe_path = os.path.join(dist_root, f"{name}.exe")
    else:
        exe_path = os.path.join(dist_root, name, f"{name}.exe")

    if not os.path.isfile(exe_path):
        raise SystemExit(f"Build failed: executable not found at {exe_path}")

    size_mb = os.path.getsize(exe_path) / (1024 * 1024)
    print("\n==========================================================")
    print("  BUILD COMPLETE")
    print("  Executable : " + exe_path)
    print(f"  Size       : {size_mb:.1f} MB")
    print("  Type       : {} (portable, no installation needed)".format(
        "single .exe" if onefile else "folder-based"))
    print("==========================================================")
    return exe_path


def ensure_venv():
    """Create (or reuse) an isolated build venv with only the runtime deps.

    Building inside a clean venv avoids PyInstaller picking up unrelated heavy
    packages (torch, tensorflow, ...) that would otherwise slow the build and
    bloat the executable. Returns the path to the venv python.
    """
    venv_dir = os.path.join(PROJECT_ROOT, ".build-venv")
    py_exe = os.path.join(venv_dir, "Scripts", "python.exe")

    if not os.path.isfile(py_exe):
        print("==> Creating isolated build virtual environment...")
        subprocess.check_call(
            [sys.executable, "-m", "venv", venv_dir])

    # refresh build tools
    print("==> Installing build/runtime dependencies into build venv...")
    subprocess.check_call([py_exe, "-m", "pip", "install", "--upgrade", "pip"])
    subprocess.check_call([py_exe, "-m", "pip", "install", "-r",
                           os.path.join(PROJECT_ROOT, "requirements.txt")])
    subprocess.check_call([py_exe, "-m", "pip", "install", "pyinstaller"])
    return py_exe


def run_inside_venv(venv_py, argv, onefile, name, console, excludes):
    """Re-run build.py using the isolated venv interpreter."""
    cmd = [venv_py, os.path.join(PROJECT_ROOT, __file__), "--onedir" if not onefile else "--onefile",
           "--name", name,
           "--venv-python", venv_py]
    if console:
        cmd.append("--console")
    for mod in excludes:
        cmd += ["--exclude", mod]
    print("\n==> Running build inside isolated environment...")
    subprocess.check_call(cmd, cwd=PROJECT_ROOT, env=dict(os.environ,
                          **{"PYTHONPATH": PROJECT_ROOT}))
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Build Industrial SPC Analyzer into a portable Windows exe.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--onefile", action="store_true",
                       help="Build a single .exe (default)")
    group.add_argument("--onedir", action="store_true",
                       help="Build a folder-based deployment")
    parser.add_argument("--name", default=DEFAULT_NAME,
                        help=f"Executable name (default: {DEFAULT_NAME})")
    parser.add_argument("--console", action="store_true",
                        help="Show a console window (for debugging)")
    parser.add_argument("--skip-install", action="store_true",
                        help="Do not auto-install PyInstaller if missing")
    parser.add_argument("--exclude", action="append", default=[],
                        metavar="MODULE",
                        help="Additional module to exclude from the build "
                             "(can be used multiple times)")

    # Hidden flag: used when re-invoking from inside the build venv.
    parser.add_argument("--venv-python", default=None, metavar="PATH",
                        help=argparse.SUPPRESS)
    parser.add_argument("--no-venv", action="store_true",
                        help="Do NOT build inside an isolated venv (use the "
                             "current Python environment directly)")
    args = parser.parse_args()

    onefile = not args.onedir

    # If not yet running inside the clean venv, bootstrap it once and re-run.
    if not args.no_venv and args.venv_python is None:
        venv_py = ensure_venv()
        if os.path.abspath(sys.executable) != os.path.abspath(venv_py):
            return run_inside_venv(
                venv_py, [], onefile, args.name, args.console, args.exclude)

    if not find_pyinstaller() and not args.skip_install:
        ensure_dependencies()
    elif not find_pyinstaller():
        raise SystemExit(
            "PyInstaller is not installed. Run: pip install pyinstaller")

    build(onefile, args.name, args.console, excludes=args.exclude)


if __name__ == "__main__":
    main()
