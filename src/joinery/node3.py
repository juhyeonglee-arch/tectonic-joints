"""세 부재 모서리 노드: 다리(1) + 장선 X(2) + 장선 Y(3).

다리는 세로(z), 장선 X는 +x 쪽으로, 장선 Y는 +y 쪽으로 뻗는다.
노드 높이(장선 높이)를 층으로 나누고, 층마다 두 장선이 다리 속으로 무엇을
들이미는지(장부·주먹장·턱·없음)와, 두 장선이 다리 속에서 겹칠 때 누가 이기는지
(우선순위)를 정한다. 층마다 우선순위를 바꾸면 장선끼리 반턱처럼 엇물린다.

전역 변수(표현과 관련)
  over   : 다리가 장선 윗면보다 얼마나 솟는가 (mm) — 사진 02의 솟은 매듭
  flush  : 장선을 다리 가운데에 둘지(0) 바깥면에 맞출지(1)

표현 목표
  reveal : 윗면·바깥 옆면에 맞물림 경계가 많이 보일수록 좋음 (드러냄)
  hide   : 경계가 적게 보일수록 좋음 (숨김) — 겉으로는 단순한 맞댐처럼
"""
import copy
import random

import numpy as np
import shapely
from shapely.geometry import box as sbox, Polygon
from shapely.ops import unary_union

from . import assembly as AS, check, geom

NAMES = {1: "다리", 2: "장선 X", 3: "장선 Y"}


class Spec3:
    def __init__(self, leg=120, aw=60, ah=120, ext=150, below=120, cell=5.0):
        self.leg, self.aw, self.ah, self.ext, self.below, self.cell = leg, aw, ah, ext, below, cell

    def label(self):
        return f"다리 {self.leg}×{self.leg} · 장선 {self.aw}×{self.ah}"


# ------------------------------------------------------------------ 형상
def _elem(kind, p, L, w, d_to_xy):
    if kind == "none":
        return Polygon()
    depth = p["depth"] * L
    if kind == "tenon":
        v0 = p["off"] * w / 2 - p["w"] * w / 2
        v1 = p["off"] * w / 2 + p["w"] * w / 2
        pts = [(-1, v0), (-1, v1), (depth, v1), (depth, v0)]
    elif kind == "dove":
        n, h = p["neck"] * w / 2, p["head"] * w / 2
        pts = [(-1, -n), (-1, n), (depth, h), (depth, -h)]
    else:
        pts = [(-1, -w / 2), (-1, w / 2), (depth, w / 2), (depth, -w / 2)]
    return Polygon([d_to_xy(d, v) for d, v in pts]).buffer(0)


def build(spec, genome):
    """→ dict(slabs=[(z0,z1,{1:geom,2:geom,3:geom})], size=(gx,gy,gz), ...) mm."""
    L, w, h = spec.leg, spec.aw, spec.ah
    over = genome["over"]
    flush = genome["flush"]
    gx = gy = L + spec.ext
    zb = spec.below
    gz = zb + h + over
    # 장선 중심선: 가운데 또는 바깥면(x=0, y=0 쪽)에 맞춤
    yc = (w / 2) if flush else L / 2          # 장선 X의 y 중심
    xc = (w / 2) if flush else L / 2          # 장선 Y의 x 중심
    sq = sbox(0, 0, L, L)
    bodyX = sbox(L, yc - w / 2, gx, yc + w / 2)
    bodyY = sbox(xc - w / 2, L, xc + w / 2, gy)

    def toX(d, v):
        return (L - d, yc + v)

    def toY(d, v):
        return (xc + v, L - d)

    slabs = []
    if zb > 0:
        slabs.append((0.0, zb, {1: sq, 2: Polygon(), 3: Polygon()}))
    tot = sum(b["frac"] for b in genome["bands"])
    cur = zb + h
    for k, b in enumerate(genome["bands"]):
        hh = h * b["frac"] / tot
        lo = zb if k == len(genome["bands"]) - 1 else max(zb, cur - hh)
        lo = round(lo / spec.cell) * spec.cell
        eX = _elem(b["x"][0], b["x"][1], L, w, toX).intersection(sq)
        eY = _elem(b["y"][0], b["y"][1], L, w, toY).intersection(sq)
        if b["pri"] == "x":
            eY = eY.difference(eX)
        else:
            eX = eX.difference(eY)
        leg = sq.difference(unary_union([eX, eY]))
        slabs.append((lo, cur, {1: leg, 2: unary_union([bodyX, eX]).buffer(0),
                                3: unary_union([bodyY, eY]).buffer(0)}))
        cur = lo
    if over > 0:
        slabs.append((zb + h, zb + h + over, {1: sq, 2: Polygon(), 3: Polygon()}))
    return {"slabs": slabs, "size": (gx, gy, gz), "spec": spec, "genome": genome}


def voxelize(node):
    sp = node["spec"]
    c = sp.cell
    gx, gy, gz = node["size"]
    nx, ny, nz = int(round(gx / c)), int(round(gy / c)), int(round(gz / c))
    X, Y = np.meshgrid((np.arange(nx) + 0.5) * c, (np.arange(ny) + 0.5) * c, indexing="ij")
    g = np.zeros((nx, ny, nz), np.uint8)
    for z0, z1, parts in node["slabs"]:
        k0, k1 = int(round(z0 / c)), int(round(z1 / c))
        for lab, poly in parts.items():
            if poly.is_empty:
                continue
            m = shapely.contains_xy(poly, X, Y)
            g[m, k0:k1] = lab
    return g


# ------------------------------------------------------------------ 평가
def visible_boundary(g, sp):
    """노드 둘레에서 보이는 '부재 경계' 길이(mm): 윗면 + 다리 바깥 두 옆면 + 장선 쪽 두 면."""
    c = sp.cell
    nL = int(round(sp.leg / c))
    nz = g.shape[2]

    def first_hit(arr):                     # arr: (..., depth) 앞에서부터 첫 0 아닌 값
        idx = np.argmax(arr > 0, axis=-1)
        val = np.take_along_axis(arr, idx[..., None], axis=-1)[..., 0]
        return val

    def blen(img):
        n = 0
        n += int(((img[1:] != img[:-1]) & (img[1:] > 0) & (img[:-1] > 0)).sum())
        n += int(((img[:, 1:] != img[:, :-1]) & (img[:, 1:] > 0) & (img[:, :-1] > 0)).sum())
        return n * c

    top = first_hit(g[:nL + 2, :nL + 2, ::-1])                    # 위에서 내려다봄
    zlo = int(round(sp.below / c)) - 1
    side_x0 = first_hit(np.transpose(g[:, :nL + 2, zlo:], (1, 2, 0)))   # x=0 면에서 +x로
    side_y0 = first_hit(np.transpose(g[:nL + 2, :, zlo:], (0, 2, 1)))   # y=0 면에서 +y로
    # 다리의 +x, +y 면 중 장선 옆으로 보이는 부분
    side_x1 = first_hit(np.transpose(g[::-1, :nL + 2, zlo:], (1, 2, 0)))
    side_y1 = first_hit(np.transpose(g[:nL + 2, ::-1, zlo:], (0, 2, 1)))
    parts = {"윗면": blen(top), "옆면x0": blen(side_x0), "옆면y0": blen(side_y0),
             "옆면x1": blen(side_x1), "옆면y1": blen(side_y1)}
    # 기본 맞댐(장선이 다리 면에 그냥 닿는 경우)에도 생기는 경계 = 기준선
    return parts, top


def evaluate(node, target="reveal"):
    sp = node["spec"]
    g = voxelize(node)
    c = sp.cell
    res = AS.disassemble(g, base=1)
    full = res["full_free"]
    # 구조 점수
    s = 0.0
    if res["ok"]:
        s += 30
        if len(res["keys"]) == 1:
            s += 20
            if full[res["keys"][0]] == ["위로"]:
                s += 10                     # 열쇠가 위로만 빠짐 = 중력이 잠근다
    else:
        s -= 30
    # 다 조립된 상태에서 장선이 자기 축으로 뽑히지 않아야 (당김 저항)
    pull = {2: "+x", 3: "+y"}
    for p in (2, 3):
        if pull[p] not in full[p]:
            s += 6
    if "아래로" in full[2] or "아래로" in full[3]:
        s -= 20
    comps = [check.components(g == p) for p in (1, 2, 3)]
    s += 10 if comps == [1, 1, 1] else -40
    mc = max(1, int(round(20.0 / c)))
    mg = max(1, int(round(35.0 / c)))
    zc = max(1, int(round(20.0 / c)))
    thin = 0.0
    short = 0.0
    for p, ax in ((1, "z"), (2, "x"), (3, "y")):
        t, sg = check.thin_and_grain(g, p, ax, mc, mg, zc)
        thin += t
        short += sg
    s += 12 * (1 - min(1, thin * 3)) + 12 * (1 - min(1, short * 3))
    # 다리 단면이 노드에서 얼마나 남는가
    nL = int(round(sp.leg / c))
    per_z = (g[:nL, :nL, :] == 1).sum(axis=(0, 1))
    zb, zt = int(round(sp.below / c)), int(round((sp.below + sp.ah) / c))
    left = float(per_z[zb:zt].min() / (nL * nL))
    s += 10 * min(1.0, left / 0.35)
    # 너무 얇은 층
    thin_band = sum(1 for z0, z1, _ in node["slabs"] if 0 < z1 - z0 < 25)
    s -= 8 * thin_band
    structure = s
    # 표현 점수
    vb, top = visible_boundary(g, sp)
    expo = sum(vb.values()) / sp.leg              # 다리 한 변 길이로 나눈 '보이는 경계'
    # 기준: 맞댐만 한 모서리 ≈ 10. 드러냄은 그보다 많을수록, 숨김은 적을수록.
    if target == "reveal":
        expr = 6 * float(np.clip(expo - 9, 0, 7))
    else:
        expr = 6 * float(np.clip(16 - expo, 0, 7))
    return {"score": round(structure + expr, 1), "structure": round(structure, 1),
            "expression": round(expr, 1), "exposure": round(expo, 2), "vis": vb,
            "assembly": res, "leg_left": left, "grid": g, "top": top}


# ------------------------------------------------------------------ 문법·진화
def _rand_elem(rng):
    k = rng.choice(["none", "tenon", "tenon", "dove", "dove", "lap"])
    if k == "tenon":
        return [k, dict(w=rng.uniform(0.3, 0.6), off=rng.uniform(-0.3, 0.3), depth=rng.uniform(0.3, 1.0))]
    if k == "dove":
        n = rng.uniform(0.3, 0.55)
        return [k, dict(neck=n, head=min(1.0, n + rng.uniform(0.2, 0.45)), depth=rng.uniform(0.3, 0.8))]
    if k == "lap":
        return [k, dict(depth=rng.uniform(0.2, 1.0))]
    return [k, {}]


def _rand_band(rng):
    return {"frac": rng.uniform(0.6, 1.6), "x": _rand_elem(rng), "y": _rand_elem(rng),
            "pri": rng.choice(["x", "y"])}


def random_genome(rng):
    return {"over": rng.choice([0, 0, 30, 60]), "flush": rng.choice([0, 0, 1]),
            "bands": [_rand_band(rng) for _ in range(rng.choice([2, 2, 3, 3, 4]))]}


TRADITIONAL = {
    # 서양 가구의 장부 모서리(두 장선이 다리에 장부로, 장부끼리 엇갈림)
    "장부 모서리": {"over": 0, "flush": 0, "bands": [
        {"frac": 1, "x": ["tenon", dict(w=0.4, off=0, depth=0.8)], "y": ["none", {}], "pri": "x"},
        {"frac": 1, "x": ["none", {}], "y": ["tenon", dict(w=0.4, off=0, depth=0.8)], "pri": "y"}]},
    # 한옥 사개맞춤에 가까운 꼴: 다리머리를 따고 장선끼리 반턱
    "사개(반턱) 모서리": {"over": 0, "flush": 0, "bands": [
        {"frac": 1, "x": ["lap", dict(depth=1.0)], "y": ["lap", dict(depth=1.0)], "pri": "y"},
        {"frac": 1, "x": ["lap", dict(depth=1.0)], "y": ["lap", dict(depth=1.0)], "pri": "x"}]},
    # 사진 02 꼴: 다리가 솟고 장선이 다리머리를 감쌈
    "솟은 매듭": {"over": 60, "flush": 0, "bands": [
        {"frac": 1, "x": ["lap", dict(depth=0.35)], "y": ["lap", dict(depth=0.35)], "pri": "x"},
        {"frac": 1, "x": ["tenon", dict(w=0.4, off=0, depth=0.7)], "y": ["none", {}], "pri": "x"}]},
}


def mutate(gen, rng):
    gen = copy.deepcopy(gen)
    r = rng.random()
    bands = gen["bands"]
    i = rng.randrange(len(bands))
    if r < 0.4:
        b = bands[i]
        b["frac"] = max(0.3, b["frac"] + rng.gauss(0, 0.25))
        for side in ("x", "y"):
            for key in b[side][1]:
                lo = -0.4 if key == "off" else 0.15
                b[side][1][key] = float(np.clip(b[side][1][key] + rng.gauss(0, 0.08), lo, 1.0))
            if b[side][0] == "dove" and b[side][1]["head"] <= b[side][1]["neck"] + 0.1:
                b[side][1]["head"] = min(1.0, b[side][1]["neck"] + 0.15)
    elif r < 0.62:
        bands[i][rng.choice(["x", "y"])] = _rand_elem(rng)
    elif r < 0.72:
        bands[i]["pri"] = "y" if bands[i]["pri"] == "x" else "x"
    elif r < 0.8:
        gen["over"] = rng.choice([0, 30, 60])
    elif r < 0.85:
        gen["flush"] = 1 - gen["flush"]
    elif r < 0.93 and len(bands) < 4:
        bands.insert(i, _rand_band(rng))
    elif len(bands) > 2:
        del bands[i]
    return gen


def signature(gen):
    return (gen["over"] > 0, gen["flush"]) + tuple(
        (b["x"][0], b["y"][0], b["pri"]) for b in gen["bands"])


def describe(gen):
    ko = {"none": "없음", "tenon": "장부", "dove": "주먹장", "lap": "턱"}
    tot = sum(b["frac"] for b in gen["bands"])
    lines = []
    for b in gen["bands"]:
        lap_name = lambda e: ("걸침" if e[1].get("depth", 0) > 0.6 else "턱") if e[0] == "lap" else ko[e[0]]
        lines.append(f"{int(round(100 * b['frac'] / tot))}%: X {lap_name(b['x'])} · Y {lap_name(b['y'])}"
                     f" ({'X' if b['pri'] == 'x' else 'Y'} 우선)")
    head = []
    if gen["over"]:
        head.append(f"다리 {gen['over']}mm 솟음")
    head.append("장선 바깥면 맞춤" if gen["flush"] else "장선 가운데")
    return " · ".join(head) + "\n위→아래  " + " / ".join(lines)


def search(spec, target, pop=40, gens=22, seed=3, log=None):
    rng = random.Random(seed)
    cache = {}

    def fit(gen):
        k = repr(gen)
        if k not in cache:
            r = evaluate(build(spec, gen), target)
            r.pop("grid")
            r.pop("top")
            cache[k] = (r["score"], r, gen)
        return cache[k][0]

    popl = [copy.deepcopy(t) for t in TRADITIONAL.values()]
    while len(popl) < pop:
        popl.append(random_genome(rng))
    for gi in range(gens):
        sc = sorted(popl, key=fit, reverse=True)
        if log:
            log(gi, fit(sc[0]))
        nxt = [copy.deepcopy(e) for e in sc[: pop // 6]]
        while len(nxt) < pop:
            a = max(rng.sample(sc, 3), key=fit)
            child = mutate(a, rng)
            if rng.random() < 0.5:
                child = mutate(child, rng)
            nxt.append(child)
        popl = nxt
    return sorted(cache.values(), key=lambda t: t[0], reverse=True)


def coarse(gen):
    """고를 때 쓰는 느슨한 꼴: 솟음·맞춤 + 층별 요소 종류 집합 (우선순위·비율 무시)."""
    kinds = []
    for b in gen["bands"]:
        k = (b["x"][0], b["y"][0])
        if not kinds or kinds[-1] != k:
            kinds.append(k)
    return (gen["over"] > 0, gen["flush"], tuple(kinds))


def pick(results, n=3):
    seen, out = set(), []
    trad = {coarse(t) for t in TRADITIONAL.values()}
    for s, r, gen in results:
        sig = coarse(gen)
        if sig in seen or sig in trad:
            continue
        seen.add(sig)
        out.append((gen, r))
        if len(out) >= n:
            break
    return out


# ------------------------------------------------------------------ 그림용
def quads(node, colors, explode=None):
    """explode: {부재: (dx,dy,dz)} mm."""
    out = []
    for p in (1, 2, 3):
        sl = [(z0, z1, parts[p], parts[p]) for z0, z1, parts in node["slabs"] if not parts[p].is_empty]
        off = explode.get(p, (0, 0, 0)) if explode else (0, 0, 0)
        out += geom.slab_quads(sl, p, colors[p], off)
    return out
