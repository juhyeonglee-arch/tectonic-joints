"""세 부재 모서리: 예제 후보(캐시)로 그림과 3dm 만들기."""
import json

import rhino3dm

from conftest import EXAMPLES, run


def test_node3(out):
    d = out / "node3_세부재모서리"
    run("run_node3.py", d, env={"N3_CACHE": str(EXAMPLES / "node3_후보목록.json")})
    for n in ["세부재모서리_드러냄.png", "세부재모서리_숨김.png", "세부재모서리_기존꼴.png"]:
        assert (d / n).stat().st_size > 50_000, n
    cand = json.loads((d / "후보목록.json").read_text(encoding="utf-8"))
    assert cand
    f = rhino3dm.File3dm.Read(str(d / "세부재모서리.3dm"))
    assert f is not None and len(f.Objects) > 0
