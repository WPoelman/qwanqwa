from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "demo"
EXPORT_SCRIPT = ROOT / "scripts" / "export_demo_data.py"
DEMO_FILES = ["index.html", "app.css", "app.js", "data"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the QQ demo and copy it into a target directory.")
    parser.add_argument(
        "output_dir",
        type=Path,
        help="Directory to publish the built demo into, for example ../site/static/qq",
    )
    parser.add_argument(
        "--skip-export",
        action="store_true",
        help="Reuse the current demo build instead of regenerating the data first.",
    )
    return parser.parse_args()


def run_export() -> None:
    subprocess.run([sys.executable, str(EXPORT_SCRIPT)], cwd=ROOT, check=True)


def reset_target(target_dir: Path) -> None:
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)


def copy_demo(target_dir: Path) -> None:
    for name in DEMO_FILES:
        source = DEMO_DIR / name
        target = target_dir / name
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.expanduser().resolve()

    if not args.skip_export:
        run_export()

    reset_target(output_dir)
    copy_demo(output_dir)
    print(f"Published demo to {output_dir}")


if __name__ == "__main__":
    main()
