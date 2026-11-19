"""생성 결구의 정확한 형상: 높이 층(band)마다 A·B의 평면 다각형 (mm).

검사는 복셀로 하지만, 그림·라이노·레이저 재단은 이 다각형으로 만든다.
그래서 빗각 면이 계단 없이 곧게 나온다.
"""
import math

import numpy as np
from shapely.geometry import Polygon, box as sbox
from shapely.geometry.polygon import orient
from shapely.ops import unary_union
try:
    import mapbox_earcut as earcut
except ImportError:            # 브라우저(Pyodide)에는 mapbox_earcut이 없다 → shapely로 대신
    earcut = None


def slabs(j):
    """[(z0, z1, geomA, geomB)] mm. j = generator.build() 결과."""
    sp = j.meta["spec"]
    c = sp.cell
    co, s, _ = j.meta["bout"]
    nx, ny, nz = j.grid.shape
    wA, wB = sp.wA, sp.wB
    gx, gy = nx * c, ny * c
    P = np.array([j.meta["xc"] * c, wA])
    ax = np.array([co, s])
    pp = np.array([-s, co])
    frame = sbox(0, 0, gx, gy)
    rectA = sbox(0, 0, gx, wA)

    def dv(d, v):  # (A 속 깊이, 옆) → xy
        t = -d - v * co / s
        q = P + v * pp + t * ax
        return (q[0], q[1])

    big = 4 * max(gx, gy)
    strip = Polygon([tuple(P + v * pp + t * ax) for v, t in
                     ((-wB / 2, -big), (wB / 2, -big), (wB / 2, big), (-wB / 2, big))])
    body = strip.intersection(sbox(0, wA, gx, gy)).intersection(frame)

    Dmax = wA / s
    out = []
    zb0 = j.meta["zb0"] * c
    if zb0 > 0:
        out.append((0.0, zb0, rectA, Polygon()))
    for lo, hi, kind, p in j.meta["bands"]:
        z0, z1 = lo * c, hi * c
        el = Polygon()
        if kind != "none":
            depth = p["depth"] * Dmax
            if kind == "tenon":
                v0 = p["off"] * wB / 2 - p["w"] * wB / 2
                v1 = p["off"] * wB / 2 + p["w"] * wB / 2
                el = Polygon([dv(-1, v0), dv(-1, v1), dv(depth, v1), dv(depth, v0)])
            elif kind == "dove":
                n, h = p["neck"] * wB / 2, p["head"] * wB / 2
                el = Polygon([dv(-1, -n), dv(-1, n), dv(depth, h), dv(depth, -h)])
            else:
                el = Polygon([dv(-1, -wB / 2), dv(-1, wB / 2), dv(depth, wB / 2), dv(depth, -wB / 2)])
            el = el.buffer(0).intersection(rectA)
        gA = rectA.difference(el)
        gB = unary_union([body, el]).buffer(0)
        out.append((z0, z1, gA, gB))
    return out


def _polys(g):
    if g.is_empty:
        return []
    if g.geom_type == "Polygon":
        return [g]
    return [x for x in getattr(g, "geoms", []) if x.geom_type == "Polygon" and not x.is_empty]


def slab_quads(slab_list, label, color, offset=(0, 0, 0)):
    """층 다각형들을 수직으로 뽑아 렌더러용 면 목록으로."""
    off = np.asarray(offset, float)
    quads = []
    for z0, z1, gA, gB in slab_list:
        g = gA if label == 1 else gB
        for poly in _polys(g):
            poly = orient(poly, 1.0)                  # 바깥 반시계, 구멍 시계
            rings = [poly.exterior] + list(poly.interiors)
            for ring in rings:
                pts = np.asarray(ring.coords)[:-1]
                for i in range(len(pts)):
                    a, b = pts[i], pts[(i + 1) % len(pts)]
                    e = b - a
                    L = math.hypot(*e)
                    if L < 1e-6:
                        continue
                    n = np.array([e[1] / L, -e[0] / L, 0.0])   # 반시계 → 바깥쪽 = 오른쪽
                    cs = np.array([[a[0], a[1], z0], [b[0], b[1], z0],
                                   [b[0], b[1], z1], [a[0], a[1], z1]]) + off
                    key = (label, "side", round(float(np.degrees(np.arctan2(n[1], n[0]))), 1),
                           round(float(n[:2] @ a), 1))
                    quads.append((cs, n, color, key))
            # 위·아래 뚜껑
            verts = np.concatenate([np.asarray(r.coords)[:-1] for r in rings])
            ends = np.cumsum([len(r.coords) - 1 for r in rings]).astype(np.uint32)
            tri = _triangulate(verts, ends)
            for z, sgn in ((z1, 1), (z0, -1)):
                n = np.array([0, 0, sgn], float)
                for t in tri:
                    p3 = [[*verts[k], z] for k in (t if sgn > 0 else t[::-1])]
                    p3.append(p3[-1])
                    quads.append((np.array(p3) + off, n, color, (label, "cap", sgn, round(z, 1))))
    return quads


def _triangulate(verts, ends):
    """구멍 있는 다각형 → 삼각형 꼭짓점 번호 (n, 3), 모두 반시계."""
    if earcut is not None:
        return earcut.triangulate_float64(verts, ends).reshape(-1, 3)
    import shapely
    starts = np.concatenate([[0], ends[:-1]]).astype(int)
    rings = [verts[a:b] for a, b in zip(starts, ends)]
    poly = Polygon(rings[0], rings[1:])
    index = {(round(float(x), 6), round(float(y), 6)): k for k, (x, y) in enumerate(verts)}
    out = []
    for t in shapely.get_parts(shapely.constrained_delaunay_triangles(poly)):
        c = np.asarray(t.exterior.coords)[:3]
        try:
            ids = [index[(round(float(x), 6), round(float(y), 6))] for x, y in c]
        except KeyError:
            continue
        a, b, d = verts[ids[0]], verts[ids[1]], verts[ids[2]]
        if (b[0] - a[0]) * (d[1] - a[1]) - (b[1] - a[1]) * (d[0] - a[0]) < 0:
            ids = [ids[0], ids[2], ids[1]]
        out.append(ids)
    return np.asarray(out, dtype=np.int64).reshape(-1, 3)
