"""M3 레이저 적층 출력: 세 부재 노드를 판 두께로 썰어 재단용 판 목록을 만든다.

흐름
  1. 층(band) 경계를 판 두께의 배수로 맞춘다 (경계마다 가장 가까운 배수 → 누적 오차 없음)
  2. 부재·판마다 평면 다각형 → 떨어진 조각(섬)은 각각 한 장의 부품
  3. 맞춤 공차: 모든 부품을 공차/2 만큼 안으로 → 맞닿는 두 부재 사이 틈 = 공차
     커프 보정: 그 다음 커프/2 만큼 바깥으로 (구멍은 안으로) → 레이저가 지나간 뒤 설계 치수
  4. 정렬 핀: 부재마다 세로 핀 자리를 골라 모든 조각이 핀 2개(작으면 1개)에 꿰이게
     핀은 부재 맨 윗장을 뚫지 않는다 (겉에 안 보이게). 장선은 맨 아랫장도 막는다.
  5. 각인: 판 번호 (노드-부재 번호, 아래에서 1부터). 맨 윗장은 뒤집어 놓으므로 좌우를 뒤집어 자른다.
"""
import math

import numpy as np
import shapely
from shapely import affinity
from shapely.geometry import Point, Polygon, box as sbox
from shapely.ops import unary_union
from matplotlib.textpath import TextPath
from matplotlib.font_manager import FontProperties
import os

from . import geom

_FONT = os.path.join(os.path.dirname(__file__), "fonts", "PretendardVariable.ttf")
MEMBER_CODE = {1: "L", 2: "X", 3: "Y"}
MEMBER_KO = {1: "다리", 2: "장선 X", 3: "장선 Y"}


class Params:
    def __init__(self, t=3.0, kerf=0.2, clear=0.2, pin=4.0, pin_fit=0.1, wall=2.5,
                 bed=(600.0, 400.0), margin=5.0, gap=3.0, scale=1.0):
        self.t, self.kerf, self.clear = t, kerf, clear
        self.pin, self.pin_fit, self.wall = pin, pin_fit, wall
        self.bed, self.margin, self.gap, self.scale = bed, margin, gap, scale


# ------------------------------------------------------------------ 1. 판으로 썰기
def snap_slabs(node, P):
    """node['slabs'] (mm, 원래 축척) → 판 경계에 맞춘 slab 목록 [(n0, n1, parts)] (판 번호 범위)
    과 축척 적용한 다각형."""
    s = P.scale
    out = []
    report = []
    for z0, z1, parts in sorted(node["slabs"], key=lambda t: t[0]):
        n0, n1 = int(round(z0 * s / P.t)), int(round(z1 * s / P.t))
        report.append((z0 * s, z1 * s, n0 * P.t, n1 * P.t))
        if n1 <= n0:
            continue
        sp = {p: (affinity.scale(g, s, s, origin=(0, 0)) if not g.is_empty else g) for p, g in parts.items()}
        out.append((n0, n1, sp))
    return out, report


def snapped_node(node, P):
    """판 경계에 맞춘 노드 (검사용: 판 두께 = 격자 한 칸)."""
    from .node3 import Spec3
    sl, _ = snap_slabs(node, P)
    sp0 = node["spec"]
    sp = Spec3(leg=sp0.leg * P.scale, aw=sp0.aw * P.scale, ah=sp0.ah * P.scale,
               ext=sp0.ext * P.scale, below=sp0.below * P.scale,
               cell=P.t / math.ceil(P.t / (sp0.cell * P.scale) - 1e-9))
    gx, gy, gz = node["size"]
    return {"slabs": [(n0 * P.t, n1 * P.t, parts) for n0, n1, parts in sl],
            "size": (gx * P.scale, gy * P.scale, sl[-1][1] * P.t), "spec": sp, "genome": node["genome"]}


def member_sheets(node, P):
    """부재별 판 목록 {p: [dict(k, z0, z1, design=[섬...])]}  k = 부재 안에서 아래부터 1."""
    sl, _ = snap_slabs(node, P)
    out = {1: [], 2: [], 3: []}
    for n0, n1, parts in sl:
        for p in (1, 2, 3):
            g = parts[p]
            if g.is_empty:
                continue
            g = g.buffer(-P.clear / 2, join_style="mitre")
            isl = [x for x in geom._polys(g) if x.area > 1.0]
            for n in range(n0, n1):
                out[p].append({"z0": n * P.t, "z1": (n + 1) * P.t, "fit": isl})
    for p in out:
        for k, sh in enumerate(out[p], 1):
            sh["k"] = k
    return out


# ------------------------------------------------------------------ 4. 정렬 핀
def place_pins(sheets, P, member, max_pins=6, avoid=None):
    """세로 핀 자리 고르기 (탐욕적 덮기). 반환 [dict(x, y, k0, k1)] k0..k1 판 번호(포함)."""
    if not sheets:
        return [], []
    rh = (P.pin + P.pin_fit) / 2
    allu = unary_union([unary_union(s["fit"]) for s in sheets])
    x0, y0, x1, y1 = allu.bounds
    step = max(1.0, min(2.0, P.pin / 2))
    xs = np.arange(x0 + rh, x1 - rh + 1e-9, step)
    ys = np.arange(y0 + rh, y1 - rh + 1e-9, step)
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    X, Y = X.ravel(), Y.ravel()
    if avoid is not None:                  # 장선 핀은 다리 속(장부·턱)에 넣지 않는다
        keep = ~shapely.contains_xy(avoid.buffer(rh + P.wall), X, Y)
        X, Y = X[keep], Y[keep]
    S = len(sheets)
    idx = -np.ones((S, len(X)), np.int32)          # 판 s에서 점이 들어가는 섬 번호 (핀 놓을 수 있을 때)
    target = []
    cache = {}
    for s, sh in enumerate(sheets):
        key = id(sh["fit"])
        if key not in cache:
            row = -np.ones(len(X), np.int32)
            tg = []
            for i, isl in enumerate(sh["fit"]):
                er = isl.buffer(-(rh + P.wall))
                if not er.is_empty:
                    row[shapely.contains_xy(er, X, Y)] = i
                # 핀 두 개를 띄워 놓을 만한 섬이면 2개, 아니면 1개
                a, b, c, d = er.bounds if not er.is_empty else (0, 0, 0, 0)
                tg.append(0 if er.is_empty else (2 if max(c - a, d - b) >= 10 else 1))
            cache[key] = (row, tg)
        row, tg = cache[key]
        idx[s] = row
        target.append(tg)
    blocked = [S - 1]                     # 맨 윗장
    if member != 1:
        blocked.append(0)                 # 장선 맨 아랫장 (밑에서 보임)
    for b in blocked:
        idx[b] = -1
    cnt = [[0] * len(t) for t in target]
    pins = []
    min_len = 3

    def runs(col):
        r, start = [], None
        for s in range(S + 1):
            ok = s < S and col[s] >= 0
            if ok and start is None:
                start = s
            if not ok and start is not None:
                if s - start >= min_len:
                    r.append((start, s - 1))
                start = None
        return r

    allruns = [runs(idx[:, j]) for j in range(len(X))]
    while len(pins) < max_pins:
        best, bsc = None, 0.0
        for j in range(len(X)):
            if pins:
                dmin = min(math.hypot(X[j] - q["x"], Y[j] - q["y"]) for q in pins)
                if dmin < 2 * rh + 6:
                    continue
            else:
                dmin = 0.0
            for a, b in allruns[j]:
                g = 0
                for s in range(a, b + 1):
                    i = idx[s, j]
                    if cnt[s][i] < target[s][i]:
                        g += 1
                if g == 0:
                    continue
                sc = g + 0.02 * min(dmin, 200) + 0.001 * (b - a)
                if sc > bsc:
                    bsc, best = sc, (j, a, b)
        if best is None:
            break
        j, a, b = best
        for s in range(a, b + 1):
            cnt[s][idx[s, j]] += 1
        pins.append({"x": float(X[j]), "y": float(Y[j]), "k0": a + 1, "k1": b + 1})
    # 핀이 하나도 안 꿰인 섬
    loose = []
    for s, sh in enumerate(sheets):
        for i in range(len(sh["fit"])):
            if cnt[s][i] == 0:
                loose.append((sh["k"], i))
    for i, q in enumerate(pins, 1):
        q["name"] = f"P{i}"
        q["len"] = (q["k1"] - q["k0"] + 1) * P.t - 1.0
    return pins, loose


# ------------------------------------------------------------------ 5. 각인 글자
def text_polys(s, h):
    tp = TextPath((0, 0), s, size=h * 1.38, prop=FontProperties(fname=_FONT, weight=500))
    polys = [np.asarray(p) for p in tp.to_polygons() if len(p) >= 3]
    if not polys:
        return [], (0, 0, 0, 0)
    allp = np.concatenate(polys)
    return polys, (allp[:, 0].min(), allp[:, 1].min(), allp[:, 0].max(), allp[:, 1].max())


def place_label(isl, s, holes, sizes=(3.5, 2.5, 1.8)):
    """섬 안에 글자 상자를 놓을 자리. 반환 (글자 다각형들 [xy 배열], 크기) 또는 (None, 0)."""
    for h in sizes:
        polys, (a, b, c, d) = text_polys(s, h)
        w, hh = c - a, d - b
        room = isl.buffer(-1.2)
        for hp in holes:
            room = room.difference(hp.buffer(1.2))
        if room.is_empty:
            continue
        x0, y0, x1, y1 = room.bounds
        cx, cy = isl.centroid.x, isl.centroid.y
        cands = []
        for x in np.arange(x0, x1 - w + 1e-9, 1.0):
            for y in np.arange(y0, y1 - hh + 1e-9, 1.0):
                cands.append((abs(x + w / 2 - cx) + abs(y + hh / 2 - cy), x, y))
        cands.sort()
        for _, x, y in cands[:4000]:
            if room.contains(sbox(x, y, x + w, y + hh)):
                return [p + np.array([x - a, y - b]) for p in polys], h
    return None, 0


# ------------------------------------------------------------------ 부품 만들기
def build_parts(node, P, tag):
    """노드 → 부품 목록, 부재별 판 정보, 핀."""
    ms = member_sheets(node, P)
    rh_cut = (P.pin + P.pin_fit) / 2 - P.kerf / 2
    parts, info = [], {}
    for p in (1, 2, 3):
        sheets = ms[p]
        Ls = node["spec"].leg * P.scale
        pins, loose = place_pins(sheets, P, p, avoid=None if p == 1 else sbox(0, 0, Ls, Ls))
        info[p] = {"sheets": sheets, "pins": pins, "loose": loose}
        n = len(sheets)
        for sh in sheets:
            k = sh["k"]
            top = k == n
            for i, isl in enumerate(sh["fit"]):
                holes = [Point(q["x"], q["y"]).buffer(rh_cut, 48) for q in pins
                         if q["k0"] <= k <= q["k1"] and isl.contains(Point(q["x"], q["y"]))]
                cut = isl.buffer(P.kerf / 2, join_style="mitre")
                suf = "abcdefgh"[i] if len(sh["fit"]) > 1 else ""
                pid = f"{tag}-{MEMBER_CODE[p]}{k:02d}{suf}{'T' if top else ''}"
                lab, lh = place_label(isl, pid, holes)
                part = {"id": pid, "member": p, "k": k, "z0": sh["z0"], "z1": sh["z1"],
                        "cut": cut, "holes": holes, "label": lab or [], "label_h": lh,
                        "top": top, "design": isl}
                if top:                         # 뒤집어 놓을 판: 좌우 반전해서 자른다
                    part = mirror_part(part)
                parts.append(part)
    return parts, info


def mirror_part(part):
    cx = part["cut"].centroid.x
    m = lambda g: affinity.scale(g, -1, 1, origin=(cx, 0))
    part = dict(part)
    part["cut"] = m(part["cut"])
    part["holes"] = [m(h) for h in part["holes"]]
    # 글자는 읽히게 다시 놓는다 (뒤집으면 아랫면이 되어 안 보임)
    if part["label"]:
        lab = [np.column_stack([2 * cx - q[:, 0], q[:, 1]]) for q in part["label"]]
        allp = np.concatenate(lab)
        w = allp[:, 0].max() - allp[:, 0].min()
        lab = [np.column_stack([2 * allp[:, 0].min() + w - q[:, 0], q[:, 1]]) for q in lab]
        part["label"] = lab
    part["mirrored"] = True
    return part


def thin_warnings(parts, min_w=3.0):
    """너비 min_w 미만 살이 있는 부품 (MDF 3mm에서 잘 부러짐)."""
    out = []
    for q in parts:
        g = q["design"]
        op = g.buffer(-min_w / 2, join_style="mitre").buffer(min_w / 2, join_style="mitre")
        lost = g.difference(op).area
        if lost > 0.5:
            out.append((q["id"], round(lost, 1)))
    return out


# ------------------------------------------------------------------ 배치 (선반 방식)
def _transform(part, rot, dx, dy):
    def T(g):
        if rot:
            g = affinity.rotate(g, 90, origin=(0, 0))
        return affinity.translate(g, dx, dy)

    def Tp(a):
        a = np.asarray(a, float)
        if rot:
            a = np.column_stack([-a[:, 1], a[:, 0]])
        return a + np.array([dx, dy])
    q = dict(part)
    q["cut"] = T(part["cut"])
    q["holes"] = [T(h) for h in part["holes"]]
    q["label"] = [Tp(a) for a in part["label"]]
    return q


def nest(parts, P):
    W, H = P.bed
    m, gap = P.margin, P.gap
    items = []
    for q in parts:
        a, b, c, d = q["cut"].bounds
        w, h = c - a, d - b
        rot = h > w                                      # 긴 쪽을 가로로
        if rot:
            w, h = h, w
        if w > W - 2 * m or h > H - 2 * m:
            raise ValueError(f"{q['id']}가 작업대보다 큼 ({w:.0f}×{h:.0f})")
        items.append((h, w, rot, q))
    items.sort(key=lambda t: (-round(t[0], 0), -t[1], t[3]["id"]))
    beds = []
    cur, x, y, rowh = None, m, m, 0.0
    for h, w, rot, q in items:
        if cur is None:
            cur, x, y, rowh = [], m, m, 0.0
        if x + w > W - m:
            x, y, rowh = m, y + rowh + gap, 0.0
        if y + h > H - m:
            beds.append(cur)
            cur, x, y, rowh = [], m, m, 0.0
        g = q["cut"]
        if rot:
            g = affinity.rotate(g, 90, origin=(0, 0))
        a, b, _, _ = g.bounds
        cur.append(_transform(q, rot, x - a, y - b) | {"rot": rot})
        x += w + gap
        rowh = max(rowh, h)
    if cur:
        beds.append(cur)
    return beds


# ------------------------------------------------------------------ DXF
def write_dxf(bed, path, P):
    import ezdxf
    doc = ezdxf.new("R2010", setup=False)
    doc.units = ezdxf.units.MM
    doc.header["$INSUNITS"] = 4
    doc.header["$MEASUREMENT"] = 1
    doc.layers.add("ENGRAVE", color=5)       # 1. 각인 (판 번호) — 약한 출력
    doc.layers.add("CUT_INNER", color=6)     # 2. 안쪽 자르기 (핀 구멍, 속 구멍)
    doc.layers.add("CUT_OUTER", color=1)     # 3. 바깥 자르기
    msp = doc.modelspace()

    def ring(coords, layer):
        pts = [(round(float(x), 4), round(float(y), 4)) for x, y in np.asarray(coords)[:-1]]
        if len(pts) >= 3:
            msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": layer})

    for q in bed:
        for a in q["label"]:
            pts = [(round(float(x), 4), round(float(y), 4)) for x, y in a]
            if pts and pts[0] == pts[-1]:
                pts = pts[:-1]
            if len(pts) >= 3:
                msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "ENGRAVE"})
        for h in q["holes"]:
            c = h.centroid
            r = math.sqrt(h.area / math.pi)
            msp.add_circle((round(c.x, 4), round(c.y, 4)), round(r, 4), dxfattribs={"layer": "CUT_INNER"})
        for poly in geom._polys(q["cut"]):
            for it in poly.interiors:
                ring(it.coords, "CUT_INNER")
            ring(poly.exterior.coords, "CUT_OUTER")
    doc.saveas(path)


# ------------------------------------------------------------------ 공차 시험편
def coupon(P, clears=(0.0, 0.1, 0.2, 0.3, 0.4), pins=(-0.2, -0.1, 0.0, 0.1, 0.2)):
    """시험편 부품 목록 (작업대 좌표, 이미 놓인 상태).

    - 구멍판: 20mm 정사각 구멍 5개(설계 틈 0~0.4) + 핀 구멍 5개(핀 지름 -0.2~+0.2)
    - 끼움 조각: 20mm 정사각 5개 → 구멍판에 하나씩 끼워 보고 손으로 꽉 밀어 들어가는 틈을 고른다
    - 커프 빗: 보정 없이 10mm 조각 10개 → 붙여서 잰 너비 W면 커프 = (100 - W) / 10
    """
    k2 = P.kerf / 2
    parts = []
    s = 20.0
    plate = sbox(0, 0, 150, 62)
    holes, labels = [], []
    for i, c in enumerate(clears):
        x = 8 + i * 28
        hole = sbox(x, 30, x + s + c, 30 + s + c)
        holes.append(hole)
        pl, _ = text_polys(f"{c:.1f}", 3.0)
        labels += [a + np.array([x + 3, 24 - 3]) for a in pl]
    pinh = []
    for i, d in enumerate(pins):
        x = 18 + i * 28
        r = (P.pin + d) / 2 - k2
        pinh.append(Point(x, 10).buffer(r, 48))
        pl, _ = text_polys(f"{P.pin + d:.1f}", 2.5)
        labels += [a + np.array([x - 6, 15.5]) for a in pl]
    pl, _ = text_polys(f"T{P.t:g} K{P.kerf:g}", 2.5)
    labels += [a + np.array([120, 3]) for a in pl]
    cut = plate.buffer(k2, join_style="mitre")
    cut = cut.difference(unary_union([h.buffer(-k2, join_style="mitre") for h in holes]))
    parts.append({"id": "C-PLATE", "cut": cut, "holes": pinh, "label": labels})
    for i, c in enumerate(clears):
        x = 160 + i * 25
        sq = sbox(x, 30, x + s, 30 + s).buffer(k2, join_style="mitre")
        pl, _ = text_polys(f"{i + 1}", 3.0)
        parts.append({"id": f"C-T{i + 1}", "cut": sq, "holes": [],
                      "label": [a + np.array([x + 2, 32]) for a in pl]})
    for i in range(10):                    # 커프 빗: 보정 없음
        x = 160 + i * 10
        parts.append({"id": f"C-K{i + 1}", "cut": sbox(x, 5, x + 10, 25), "holes": [], "label": []})
    return [[_transform(q, False, 5, 5) for q in parts]]
