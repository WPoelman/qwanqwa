from __future__ import annotations

import shutil
from pathlib import Path

from qq.explorer.export import DEFAULT_DATA_DIR, REPO_ROOT, export_demo_data

DEMO_DIR = REPO_ROOT / "demo"
DEMO_FILES = ("index.html", "app.css", "app.js", "data")


def publish_demo(output_dir: Path, skip_export: bool = False, overwrite: bool = False) -> Path:
    target_dir = output_dir.expanduser().resolve()

    if not skip_export:
        export_demo_data(DEFAULT_DATA_DIR)

    if target_dir.exists():
        if not overwrite:
            raise FileExistsError(f"Refusing to replace existing directory: {target_dir}")
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    for name in DEMO_FILES:
        source = DEMO_DIR / name
        target = target_dir / name
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)

    return target_dir
