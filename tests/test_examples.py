# ruff: noqa: S603, S607
import subprocess
from shutil import which

import pytest


@pytest.mark.skipif(not which("mcptools"), reason="requires mcptools")
def test_mcptools():
    proc = subprocess.run(["examples/mcptools.sh"], capture_output=True, timeout=15, check=True)
    assert proc.returncode == 0
    assert b"Ready." in proc.stdout
