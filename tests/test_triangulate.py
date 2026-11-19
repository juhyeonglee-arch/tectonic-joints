"""브라우저용 삼각분할(shapely)이 mapbox_earcut과 같은 넓이를 덮는지."""
import numpy as np
import pytest

from conftest import SRC
import sys
sys.path.insert(0, str(SRC))
from joinery import geom  # noqa: E402


def _area(v, tri):
    a, b, c = v[tri[:, 0]], v[tri[:, 1]], v[tri[:, 2]]
    return 0.5 * ((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0]))


@pytest.mark.parametrize("use_earcut", [True, False])
def test_구멍있는_다각형(use_earcut, monkeypatch):
    if not use_earcut:
        monkeypatch.setattr(geom, "earcut", None)
    elif geom.earcut is None:
        pytest.skip("mapbox_earcut 없음")
    v = np.array([[0, 0], [10, 0], [10, 10], [0, 10], [2, 2], [2, 4], [4, 4], [4, 2]], float)
    ends = np.array([4, 8], np.uint32)
    tri = geom._triangulate(v, ends)
    ar = _area(v, tri)
    assert (ar > 0).all()
    assert ar.sum() == pytest.approx(100 - 4)
