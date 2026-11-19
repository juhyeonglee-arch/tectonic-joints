"""M2 결구 생성기: 층별 요소 조합(결구 문법) + 진화 탐색.

결구 문법
---------
전통 결구를 높이 방향 층(band)으로 쪼개 보면 각 층은 몇 가지 평면 요소 중 하나다.
  - 장부(tenon)   : 좁은 혀가 상대 부재 속으로 들어감
  - 주먹장(dove)  : 목이 좁고 머리가 넓은 사다리꼴 → 당김에 잠김
  - 턱/걸침(lap)  : 단면 전체가 상대 부재에 얕게(턱) 또는 깊게(걸침) 묻힘
  - 없음(none)    : 그 층은 상대 부재 면에서 멈춤
예) 주먹장맞춤 = [위 2/3: 주먹장, 아래 1/3: 없음]
    턱장부맞춤 = [위: 장부, 가운데: 장부, 아래: 턱]
    메뚜기장   = [위 절반: 주먹장(긴 목), 아래: 없음 + A 받침턱]
생성기는 이 요소들의 새 조합·비율을 찾되, 임의 각도(평면 사잇각)와 단면에서
'한 방향으로만 끼워지는가'와 제작·강도 기준을 검사기로 매긴다.

좌표: A는 x 방향(폭 wA, 높이 hA). B는 A의 +y 면으로 사잇각 θ로 들어오고,
윗면을 A와 맞춘다(top-flush). 요소 모양은 B 기준 좌표 (d = A 앞면에서 B축을
따라 들어간 깊이, v = B 중심선에서 옆으로 떨어진 거리)로 정의한다.
"""
import copy
import math
import random

import numpy as np
from scipy import ndimage

from .grid import Joint, A, B, EMPTY
from . import check

ELEM_KO = {"none": "없음", "tenon": "장부", "dove": "주먹장", "lap": "턱"}


# ----------------------------------------------------------------- 형상 만들기
class Spec:
    def __init__(self, wA=150, hA=180, wB=120, hB=150, angle=90.0, cell=5.0):
        self.wA, self.hA, self.wB, self.hB = wA, hA, wB, hB
        self.angle = angle
        self.cell = cell

    def label(self):
        return f"A {self.wA}×{self.hA} · B {self.wB}×{self.hB} · 사잇각 {self.angle:.0f}°"


def build(spec, genome):
    """genome = [(높이 비율, 요소, 파라미터 dict), ...] 위층부터."""
    c = spec.cell
    th = math.radians(spec.angle)
    s, co = math.sin(th), math.cos(th)
    wA, hA, wB, hB = (int(round(v / c)) for v in (spec.wA, spec.hA, spec.wB, spec.hB))
    Dmax = wA / s                         # A를 관통하는 B축 방향 길이(칸)
    ext = int(round(wB * 1.6))            # B가 A 밖으로 나온 길이
    half_foot = (wB / 2) / s + abs(co / s) * wA + 2
    reach_x = abs(co) * ext
    margin = int(math.ceil(half_foot + reach_x + wB * 0.6))
    nx = 2 * margin
    ny = wA + int(math.ceil(s * ext)) + 1
    nz = hA
    xc = nx / 2 - co * ext / 2            # 중심선이 A 앞면(y=wA)과 만나는 x
    g = np.zeros((nx, ny, nz), np.uint8)
    g[:, :wA, :] = A

    X, Y = np.meshgrid(np.arange(nx) + 0.5, np.arange(ny) + 0.5, indexing="ij")
    dx, dy = X - xc, Y - wA
    u = dx * co + dy * s                  # B축 (A 밖으로 +)
    v = -dx * s + dy * co                 # 옆
    inB = np.abs(v) <= wB / 2
    body = inB & (Y >= wA) & (u <= ext)
    zb0 = hA - hB
    g[body, zb0:] = B

    # A 속 깊이 d: A 앞면에서 B축(-) 방향으로 잰 거리
    d = (wA - Y) / s
    insideA = Y < wA
    z = zb0
    total = sum(b[0] for b in genome)
    tops = []
    cur = hA
    for frac, kind, p in genome:
        hh = max(1, int(round(hB * frac / total)))
        lo = max(zb0, cur - hh)
        tops.append((lo, cur, kind, p))
        cur = lo
    if tops:
        lo, hi, kind, p = tops[-1]
        tops[-1] = (zb0, hi, kind, p)
    for lo, hi, kind, p in tops:
        if kind == "none":
            continue
        depth = p["depth"] * Dmax
        if kind == "tenon":
            m = (np.abs(v - p["off"] * wB / 2) <= p["w"] * wB / 2) & (d <= depth)
        elif kind == "dove":
            w = p["neck"] + (p["head"] - p["neck"]) * np.clip(d / max(depth, 1e-6), 0, 1)
            m = (np.abs(v) <= w * wB / 2) & (d <= depth)
        else:  # lap
            m = inB & (d <= depth)
        m &= insideA
        g[m, lo:hi] = B
    j = Joint("gen", "생성 결구", "맞춤", g, "x",
              "y" if abs(co) < 0.71 else "x", cell_mm=c)
    j.meta.update(xc=xc, zb0=zb0, bout=(co, s, 0.0), bperp=(-s, co, 0.0), bands=tops, spec=spec, genome=genome)
    return j


# ----------------------------------------------------------------- 검사
def sweep_free(g, d, mover=B, fixed=A):
    """임의 방향 d로 mover를 끝까지 밀어 낼 수 있는가 (표면 칸만 추적)."""
    pm = g == mover
    surf = pm & ~ndimage.binary_erosion(pm, border_value=0)
    pts = np.argwhere(surf).astype(float) + 0.5
    d = np.asarray(d, float)
    d[np.abs(d) < 1e-9] = 0
    d = d / np.abs(d).max() * 0.7         # 한 걸음 < 1칸
    shp = np.array(g.shape)
    fx = g == fixed
    if np.count_nonzero(d) > 1:
        # 비스듬한 방향: 복셀 계단끼리 걸리는 가짜 충돌을 없애려고 고정 부재를 한 칸 깎는다
        # (실물에서는 레이저 판의 빗선이 곧게 잘리므로 이 계단이 없다)
        fx = ndimage.binary_erosion(fx, border_value=1)
    alive = np.ones(len(pts), bool)
    for k in range(1, int(shp.max() * 1.6 / 0.7) + 2):
        q = np.floor(pts[alive] + d * k).astype(int)
        inside = np.all((q >= 0) & (q < shp), axis=1)
        if not inside.any():
            return True
        qi = q[inside]
        if fx[qi[:, 0], qi[:, 1], qi[:, 2]].any():
            return False
        idx = np.flatnonzero(alive)
        alive[idx[~inside]] = False
    return True


def escapes(j):
    g = j.grid
    co, s, _ = j.meta["bout"]
    dirs = {"위로": (0, 0, 1), "아래로": (0, 0, -1),
            "B축 바깥으로": (co, s, 0), "B축 안으로": (-co, -s, 0),
            "옆(+)": (-s, co, 0), "옆(−)": (s, -co, 0)}
    # A축 방향도 (사잇각이 기울면 B가 A를 따라 미끄러질 수 있다)
    dirs["A축(+x)"] = (1, 0, 0)
    dirs["A축(−x)"] = (-1, 0, 0)
    out = {}
    for name, d in dirs.items():
        if sweep_free(g, d):
            out[name] = d
    return out


def a_section_left(j):
    """A의 가장 많이 따인 단면이 원래 단면의 몇 %가 남는가."""
    pa = j.grid == A
    per_x = pa.sum(axis=(1, 2))
    full = per_x.max()
    return float(per_x.min() / full)


def contact_faces(j):
    g = j.grid
    n = 0
    for ax in range(3):
        a = np.moveaxis(g, ax, 0)
        n += int(((a[1:] == A) & (a[:-1] == B)).sum() + ((a[1:] == B) & (a[:-1] == A)).sum())
    return n


def evaluate(j, min_mm=25.0, min_grain_mm=40.0):
    esc = escapes(j)
    names = list(esc)
    g = j.grid
    c = j.cell_mm
    comps = (check.components(g == A), check.components(g == B))
    mc = max(1, int(round(min_mm / c)))
    mg = max(1, int(round(min_grain_mm / c)))
    zc = max(1, int(round(20.0 / c)))
    tA, sA = check.thin_and_grain(g, A, j.axis_a, mc, mg, zc)
    tB, sB = check.thin_and_grain(g, B, j.axis_b, mc, mg, zc)
    left = a_section_left(j)
    contact = contact_faces(j) * c * c / 100.0        # cm²

    if len(names) == 1:
        lock = 50 + (6 if names[0] == "위로" else 0)
        verdict = f"좋음: {names[0]}만 빠짐"
    elif len(names) == 0:
        lock, verdict = 8, "끼울 수 없음"
    elif len(names) == 2 and set(names) in ({"위로", "아래로"}, {"B축 바깥으로", "B축 안으로"}):
        lock, verdict = 28, "보통: 한 축으로 미끄러짐"
    else:
        lock, verdict = 10, "약함: " + ", ".join(names)
    if "아래로" in names:                     # 보가 아래로 빠지면 하중을 못 받는다
        lock -= 10
    if names and "B축 바깥으로" not in names:   # 당겨도 안 빠짐 = 진짜 맞물림(주먹장류)
        lock += 12
    # 너무 얇은 층(30mm 미만)은 쪼개지고 판 수도 낭비 → 감점
    thin_band = sum(1 for lo, hi, k, _ in j.meta["bands"] if (hi - lo) * c < 30 and k != "none")
    whole = 10 if comps == (1, 1) else -30
    thin = 15 * (1 - min(1, (tA + tB) * 4))
    grain = 15 * (1 - min(1, (sA + sB) * 4))
    sect = 10 * min(1.0, left / 0.6)            # A 단면이 60% 이상 남아야 만점
    # 주먹장 벌어짐(목→머리, 한쪽 mm)이 너무 작으면 나무가 조금만 줄어도 풀린다
    flare = max([(p["head"] - p["neck"]) * j.meta["spec"].wB / 2
                 for lo, hi, k, p in j.meta["bands"] if k == "dove"] or [0.0])
    weak_flare = 0.0
    if names and "B축 바깥으로" not in names and flare < 10:
        weak_flare = (10 - flare) * 1.5
    score = lock + whole + thin + grain + sect - 8 * thin_band - weak_flare
    return {"escape": names, "escape_vec": esc, "lock": verdict, "score": round(score, 1),
            "thin": (tA, tB), "short_grain": (sA, sB), "A_left": left,
            "contact_cm2": contact, "components": comps, "flare_mm": flare}


# ----------------------------------------------------------------- 문법 / 진화
TRADITIONAL = {
    "주먹장맞춤": [(2, "dove", dict(neck=0.33, head=0.62, depth=0.66)), (1, "none", {})],
    "장부맞춤": [(1, "none", {}), (5, "tenon", dict(w=0.33, off=0.0, depth=1.0)), (1, "none", {})],
    "턱장부맞춤": [(2, "tenon", dict(w=0.33, off=0.0, depth=0.85)), (1, "lap", dict(depth=0.25))],
    "반턱주먹장": [(1, "dove", dict(neck=0.45, head=0.8, depth=0.9)), (1, "none", {})],
    "걸침턱": [(1, "lap", dict(depth=0.3)), (2, "none", {})],
}


def _rand_elem(rng):
    k = rng.choice(["none", "tenon", "dove", "dove", "lap"])
    if k == "tenon":
        return k, dict(w=rng.uniform(0.25, 0.5), off=rng.uniform(-0.3, 0.3), depth=rng.uniform(0.4, 1.0))
    if k == "dove":
        n = rng.uniform(0.25, 0.5)
        return k, dict(neck=n, head=min(0.95, n + rng.uniform(0.15, 0.4)), depth=rng.uniform(0.4, 0.95))
    if k == "lap":
        return k, dict(depth=rng.uniform(0.15, 0.6))
    return k, {}


def random_genome(rng):
    n = rng.choice([2, 2, 3, 3, 4])
    out = []
    for _ in range(n):
        k, p = _rand_elem(rng)
        out.append((rng.uniform(0.6, 2.0), k, p))
    return out


def mutate(gen, rng):
    gen = copy.deepcopy(gen)
    r = rng.random()
    i = rng.randrange(len(gen))
    if r < 0.45:                                   # 파라미터 조정
        f, k, p = gen[i]
        for key in p:
            p[key] = float(np.clip(p[key] + rng.gauss(0, 0.08), -0.35 if key == "off" else 0.1, 1.0))
        if k == "dove" and p["head"] <= p["neck"] + 0.08:
            p["head"] = min(1.0, p["neck"] + 0.12)
        gen[i] = (max(0.3, f + rng.gauss(0, 0.25)), k, p)
    elif r < 0.7:                                  # 요소 바꾸기
        k, p = _rand_elem(rng)
        gen[i] = (gen[i][0], k, p)
    elif r < 0.85 and len(gen) < 4:                # 층 나누기
        f, k, p = gen[i]
        k2, p2 = _rand_elem(rng)
        gen[i:i + 1] = [(f / 2, k, p), (f / 2, k2, p2)]
    elif len(gen) > 2:                             # 층 합치기
        del gen[i]
    return gen


def crossover(a, b, rng):
    i = rng.randrange(1, len(a) + 1)
    j = rng.randrange(0, len(b))
    child = copy.deepcopy(a[:i] + b[j:])
    return child[:4] if len(child) >= 2 else copy.deepcopy(a)


def signature(gen):
    """같은 '꼴'인지 가르는 열쇠: 층 요소 순서 (연속된 같은 요소는 하나로)."""
    sig = []
    for _, k, _ in gen:
        if not sig or sig[-1] != k:
            sig.append(k)
    return tuple(sig)


def lineage(gen):
    """각 층이 어느 전통 요소를 물려받았는지 사람이 읽는 말로."""
    tot = sum(f for f, _, _ in gen)
    parts = []
    for f, k, p in gen:
        pct = int(round(100 * f / tot))
        if k == "dove":
            parts.append(f"주먹장 {pct}% (목 {p['neck']:.2f}→머리 {p['head']:.2f}, 깊이 {p['depth']:.2f})")
        elif k == "tenon":
            parts.append(f"장부 {pct}% (두께 {p['w']:.2f}, 깊이 {p['depth']:.2f})")
        elif k == "lap":
            parts.append(f"{'턱' if p['depth'] < 0.35 else '걸침'} {pct}% (깊이 {p['depth']:.2f})")
        else:
            parts.append(f"없음 {pct}%")
    sig = signature(gen)
    near = [name for name, tg in TRADITIONAL.items() if signature(tg) == sig]
    return "위→아래: " + " / ".join(parts), (near[0] if near else None)


def search(spec, pop=48, gens=26, seed=1, log=None):
    rng = random.Random(seed)
    cache = {}

    def fit(gen):
        key = repr(gen)
        if key not in cache:
            j = build(spec, gen)
            r = evaluate(j)
            novelty = 0 if any(signature(gen) == signature(t) for t in TRADITIONAL.values()) else 6
            cache[key] = (r["score"] + novelty, r)
        return cache[key][0]

    population = [copy.deepcopy(t) for t in TRADITIONAL.values()]
    while len(population) < pop:
        population.append(random_genome(rng))
    for gi in range(gens):
        scored = sorted(population, key=fit, reverse=True)
        if log:
            log(gi, fit(scored[0]), signature(scored[0]))
        elite = scored[: pop // 6]
        nxt = [copy.deepcopy(e) for e in elite]
        while len(nxt) < pop:
            a = max(rng.sample(scored, 3), key=fit)
            if rng.random() < 0.35:
                b = max(rng.sample(scored, 3), key=fit)
                child = crossover(a, b, rng)
            else:
                child = copy.deepcopy(a)
            child = mutate(child, rng)
            if rng.random() < 0.4:
                child = mutate(child, rng)
            nxt.append(child)
        population = nxt
    # 모든 평가 결과에서 서로 다른 꼴로 상위 몇 개
    allg = sorted(cache.items(), key=lambda kv: kv[1][0], reverse=True)
    return [(eval(k), v[0], v[1]) for k, v in allg]


def pick_diverse(results, n=6, include_traditional=False):
    seen, out = set(), []
    for gen, f, r in results:
        sig = signature(gen)
        if sig in seen:
            continue
        if not include_traditional and any(sig == signature(t) for t in TRADITIONAL.values()):
            continue
        seen.add(sig)
        out.append((gen, f, r))
        if len(out) >= n:
            break
    return out
