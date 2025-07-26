# ruff: noqa: S603, S607
import subprocess

import pytest


def test_mcptools():
    proc = subprocess.run(["examples/mcptools.sh"], capture_output=True, timeout=20, check=True)
    assert proc.returncode == 0
    if b"Skipped." in proc.stdout:
        raise pytest.skip("mcptools not installed")
    assert b"Ready." in proc.stdout
