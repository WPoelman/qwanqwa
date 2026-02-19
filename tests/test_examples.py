"""Smoke-test every example script: each must run to completion without errors."""

import subprocess
import sys
from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
EXAMPLE_SCRIPTS = sorted(EXAMPLES_DIR.glob("*.py"))


@pytest.mark.parametrize("script", EXAMPLE_SCRIPTS, ids=lambda p: p.name)
def test_example_runs(script: Path):
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"{script.name} exited with code {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
