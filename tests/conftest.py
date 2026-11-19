"""시험 공통: 실행 스크립트를 따로 된 프로세스로 돌리고 결과를 test-output/ 에 남긴다.

test-output/ 은 GitHub Actions 산출물(artifact)로 올라가 확인 그림을 내려받을 수 있다.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
EXAMPLES = ROOT / "examples"
OUT = Path(os.environ.get("TJ_TEST_OUT", ROOT / "test-output"))


def run(script, *args, env=None, timeout=900):
    e = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", MPLBACKEND="Agg")
    e.update(env or {})
    p = subprocess.run([sys.executable, str(SRC / script), *map(str, args)], env=e,
                       capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    assert p.returncode == 0, f"{script} 실패\n--- stdout ---\n{p.stdout[-3000:]}\n--- stderr ---\n{p.stderr[-5000:]}"
    return p


@pytest.fixture(scope="session")
def out():
    OUT.mkdir(parents=True, exist_ok=True)
    return OUT
