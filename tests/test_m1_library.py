"""M1 전통 결구 라이브러리: 실행, 검사 결과, 그림, 3dm."""
import json

import pytest
import rhino3dm

from conftest import run


@pytest.fixture(scope="module")
def m1(out):
    d = out / "m1_전통결구"
    run("run_m1.py", d)
    return d


def test_검사결과(m1):
    rows = json.loads((m1 / "검사결과.json").read_text(encoding="utf-8"))
    assert len(rows) == 9
    for r in rows:
        assert 0 <= r["점수"] <= 100
        assert r["판정"]
    # 한 방향으로만 빠지는(끼우는) 결구가 하나 이상 있어야 한다
    assert any(len(r["빠지는방향"]) == 1 for r in rows)


def test_그림(m1):
    assert (m1 / "전통결구_라이브러리_검사.png").stat().st_size > 50_000
    pngs = list((m1 / "결구별").glob("*.png"))
    assert len(pngs) == 9
    assert all(p.stat().st_size > 20_000 for p in pngs)


@pytest.mark.parametrize("name", ["전통결구_라이브러리_조립.3dm", "전통결구_라이브러리_분해.3dm"])
def test_3dm(m1, name):
    f = rhino3dm.File3dm.Read(str(m1 / name))
    assert f is not None
    assert len(f.Objects) > 0
    assert len(f.Layers) > 0
