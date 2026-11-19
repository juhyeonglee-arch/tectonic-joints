"""M2 생성기. 평소에는 저장된 후보로 그림만, M2_FULL=1 이면 진화 탐색까지(약 4분)."""
import json
import os

import pytest
import rhino3dm

from conftest import EXAMPLES, run


@pytest.mark.skipif(os.environ.get("M2_FULL") == "1", reason="전체 탐색 시험에서 다룸")
def test_m2_cached(out):
    d = out / "m2_생성후보"
    run("run_m2.py", d, env={"M2_CACHE": str(EXAMPLES / "m2_후보목록.json")})
    _check(d)


@pytest.mark.skipif(os.environ.get("M2_FULL") != "1", reason="M2_FULL=1 일 때만 (매일 1회)")
def test_m2_full_search(out):
    d = out / "m2_생성후보_전체탐색"
    run("run_m2.py", d, timeout=3600)
    _check(d)


def _check(d):
    pngs = sorted(d.glob("후보_*.png"))
    assert len(pngs) == 3
    for p in pngs:
        assert p.stat().st_size > 50_000
        f = rhino3dm.File3dm.Read(str(p.with_suffix(".3dm")))
        assert f is not None and len(f.Objects) > 0
    assert json.loads((d / "후보목록.json").read_text(encoding="utf-8"))
