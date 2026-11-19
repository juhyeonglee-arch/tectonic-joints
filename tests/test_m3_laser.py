"""M3 레이저 적층: 기본 가정값과 바뀐 값 두 번 돌려 DXF·판 수·작업대 크기를 확인."""
import csv
import json

import ezdxf
import pytest
import rhino3dm
from ezdxf import bbox

from conftest import EXAMPLES, run

LAYERS = {"ENGRAVE", "CUT_INNER", "CUT_OUTER"}
CASES = {
    # 이름: (환경변수, 기대 작업대 수 {노드: 판 수} 또는 None)
    "기본_3mm": ({}, {"1대1 드러냄": 11, "1대1 숨김": 15, "1대2 드러냄": 2, "1대2 숨김": 2}),
    "바꾼값_2.7mm_커프0.15": ({"M3_T": "2.7", "M3_KERF": "0.15", "M3_CLEAR": "0.1", "M3_PIN": "5",
                            "M3_BED": "500x300"}, None),
}


@pytest.fixture(scope="module", params=list(CASES))
def m3(request, out):
    name = request.param
    env, expect = CASES[name]
    d = out / f"m3_레이저적층_{name}"
    run("run_m3.py", d, EXAMPLES / "node3_후보목록.json", env=env)
    bed = tuple(float(v) for v in env.get("M3_BED", "600x400").split("x"))
    return d, bed, expect, env


def test_보고(m3):
    d, bed, expect, env = m3
    rep = json.loads((d / "출력보고.json").read_text(encoding="utf-8"))
    assert rep["가정"]["판두께"] == float(env.get("M3_T", 3.0))
    assert list(rep["가정"]["작업대"]) == list(bed)
    for key, node in rep["노드"].items():
        assert node["작업대 수"] >= 1
        if expect:
            assert node["작업대 수"] == expect[key], key


def test_dxf(m3):
    d, bed, _, _ = m3
    files = sorted(d.rglob("*.dxf"))
    assert len(files) >= 5
    for f in files:
        doc = ezdxf.readfile(f)
        msp = doc.modelspace()
        layers = {e.dxf.layer for e in msp}
        assert layers <= LAYERS, (f.name, layers)
        assert "CUT_OUTER" in layers, f.name
        ext = bbox.extents(msp)
        assert ext.extmin.x >= -1e-6 and ext.extmin.y >= -1e-6, f.name
        assert ext.extmax.x <= bed[0] + 1e-6 and ext.extmax.y <= bed[1] + 1e-6, (f.name, ext.extmax)


def test_판목록과_그림(m3):
    d, _, _, _ = m3
    for sub in d.glob("1대*/*_*"):
        rows = list(csv.DictReader((sub / "판목록.csv").open(encoding="utf-8-sig")))
        assert rows
        named = {r["작업대 파일"] for r in rows}
        assert named == {p.name for p in sub.glob("*.dxf")}, sub
        assert (sub / "조립순서도.png").stat().st_size > 50_000
        assert (sub / "배치_미리보기.png").stat().st_size > 10_000


def test_적층확인_3dm(m3):
    d, _, _, _ = m3
    f = rhino3dm.File3dm.Read(str(d / "적층확인.3dm"))
    assert f is not None and len(f.Objects) > 0


# 판 두께에 맞춰 층 경계를 옮겨도 빠지는 방향(= 잠김)이 바뀌면 안 된다.
# 알려진 문제: 숨김 노드는 판 두께 2.7·2.9·4mm에서 장선 X가 +x로 빠지게 된다 (저장소 이슈 참고).
LOCK_CASES = [("3.0", None), ("2.8", None), ("3.2", None),
              ("2.7", "숨김 노드 장선 X가 +x로 빠짐 (알려진 문제)")]


@pytest.mark.parametrize("t,known", LOCK_CASES, ids=[f"{t}mm" for t, _ in LOCK_CASES])
def test_판맞춤후_잠김_유지(t, known, out, request):
    if known:
        request.applymarker(pytest.mark.xfail(reason=known, strict=True))
    d = out / f"m3_잠김확인_{t}mm"
    run("run_m3.py", d, EXAMPLES / "node3_후보목록.json", env={"M3_T": t, "M3_SCALES": "1"})
    rep = json.loads((d / "출력보고.json").read_text(encoding="utf-8"))
    bad = {k: (n["빠짐 원래"], n["빠짐 판맞춤"]) for k, n in rep["노드"].items()
           if n["빠짐 판맞춤"] != n["빠짐 원래"]}
    assert not bad, bad
