"""M2: 단면·각도 → 새 결구 후보 (층별 요소 조합 + 진화 탐색)."""
import json
import os
import sys
import textwrap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from joinery import generator as G, render, export3dm, geom  # noqa: E402
from joinery.raster import render as raster  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else "m2_out"
os.makedirs(OUT, exist_ok=True)

CASES = [
    ("직교_90도", G.Spec(wA=150, hA=180, wB=120, hB=150, angle=90)),
    ("빗각_60도", G.Spec(wA=150, hA=180, wB=120, hB=150, angle=60)),
    ("빗각_45도_가는부재", G.Spec(wA=180, hA=210, wB=90, hB=120, angle=45)),
]


def solid_quads(j, r, explode=True):
    sl = geom.slabs(j)
    off = np.zeros(3)
    if explode and r["escape"]:
        v = np.array(r["escape_vec"][r["escape"][0]], float)
        sp = j.meta["spec"]
        gap = sp.hA * 1.1 if abs(v[2]) > 0.5 else sp.wA * 1.3
        off = v / np.linalg.norm(v) * gap
    return (geom.slab_quads(sl, 1, render.COL[1]) +
            geom.slab_quads(sl, 2, render.COL[2], off))


def layer_quads(j, gap=70.0):
    """층 분해도: 각 층(A 회색 + B 파랑)을 위아래로 띄워 층마다의 맞물림 평면을 보인다."""
    sl = sorted(geom.slabs(j), key=lambda t: t[0])
    out = []
    for k, s in enumerate(sl):
        dz = k * gap
        out += geom.slab_quads([s], 1, render.COL[1], (0, 0, dz))
        out += geom.slab_quads([s], 2, render.COL[2], (0, 0, dz))
    return out


def layer_plans(ax, j):
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path
    sl = sorted(geom.slabs(j), key=lambda t: -t[1])
    sp = j.meta["spec"]
    c = sp.cell
    cx, cy = j.meta["xc"] * c, sp.wA
    R = max(sp.wA, sp.wB) * 1.05
    n = len(sl)
    cols = min(n, 3)
    rows = (n + cols - 1) // cols
    w = 1.0 / cols
    h = 1.0 / rows
    for k, (z0, z1, gA, gB) in enumerate(sl):
        r_, c_ = divmod(k, cols)
        sub = ax.inset_axes([c_ * w + 0.01, 1 - (r_ + 1) * h + 0.04, w - 0.02, h - 0.08])
        for g, col in ((gA, "#d9d9d9"), (gB, "#4d85e6")):
            for poly in geom._polys(g):
                verts = [np.asarray(poly.exterior.coords)] + [np.asarray(i.coords) for i in poly.interiors]
                codes = []
                for v in verts:
                    cd = [Path.LINETO] * len(v)
                    cd[0] = Path.MOVETO
                    codes += cd
                sub.add_patch(PathPatch(Path(np.concatenate(verts), codes), fc=col, ec="#111", lw=0.6))
        sub.set_xlim(cx - R, cx + R)
        sub.set_ylim(cy - sp.wA - 15, cy + R * 0.9)
        sub.set_aspect("equal")
        sub.set_xticks([]); sub.set_yticks([])
        for sp_ in sub.spines.values():
            sp_.set_color("#bbb")
        sub.set_title(f"{k + 1}층  z {z0:.0f}–{z1:.0f}", fontsize=8, color="#444", pad=2)


def view_for(name):
    return (-62, 30) if name in ("위로", "아래로") else (-40, 40)


def sheet(case, spec, picks, trad, path):
    items = [("전통 기준: " + trad[0], trad[1], trad[2])] + \
            [(f"후보 {i + 1}", g, r) for i, (g, f, r) in enumerate(picks)]
    cols = 2
    rows = (len(items) + cols - 1) // cols
    fig = plt.figure(figsize=(cols * 9.0, rows * 5.6), dpi=125, facecolor="white")
    gs = fig.add_gridspec(rows, cols * 2, width_ratios=[1.15, 1] * cols, hspace=0.42, wspace=0.02)
    for i, (title, gen, r) in enumerate(items):
        j = G.build(spec, gen)
        rr, cc = divmod(i, cols)
        ax = fig.add_subplot(gs[rr, cc * 2])
        esc = r["escape"]
        az, el = view_for(esc[0] if esc else "")
        ax.imshow(raster(solid_quads(j, r), azim=az, elev=el, size=700))
        ax.set_axis_off()
        ax2 = fig.add_subplot(gs[rr, cc * 2 + 1])
        ax2.set_axis_off()
        ax2.set_title("층별 평면 (위→아래, 레이저 판 모양)", fontsize=10, color="#1f4fb4")
        layer_plans(ax2, j)
        lin, near = G.lineage(gen)
        ax.set_title(f"{title}   점수 {r['score']:.0f}", fontsize=14, color="#111", loc="left", pad=22)
        ax.text(0.0, 1.03, f"{r['lock']}  ·  A 단면 {r['A_left'] * 100:.0f}% 남음  ·  주먹장 벌어짐 {r['flare_mm']:.0f}mm",
                transform=ax.transAxes, ha="left", fontsize=10, color="#1f4fb4")
        ax.text(0.0, -0.02, "\n".join(textwrap.wrap(lin, 70)), transform=ax.transAxes,
                ha="left", va="top", fontsize=9.5, color="#444")
    fig.suptitle(f"새 결구 후보 — {spec.label()}    회색 = A(고정)  파랑 = B(빠지는 방향으로 띄움)",
                 fontsize=16, color="#111", y=0.995)
    fig.savefig(path, facecolor="white", bbox_inches="tight")
    plt.close(fig)


summary = []
for case, spec in CASES:
    print("==", case, flush=True)
    cached = os.environ.get("M2_CACHE")
    if cached:
        prev = [x for x in json.load(open(cached, encoding="utf-8")) if x["조건"] == case]
        picks = []
        for x in prev:
            gen = [tuple(b) for b in x["유전자"]]
            r = G.evaluate(G.build(spec, gen))
            picks.append((gen, r["score"], r))
    else:
        res = G.search(spec, log=lambda gi, f, s: print(f"  세대 {gi:2d}  최고 {f:.1f}  {s}", flush=True)
                       if gi % 5 == 0 else None)
        picks = G.pick_diverse(res, 5)
    # 같은 조건의 전통 결구 중 가장 나은 것 (비교 기준)
    best_t = max(((n, t, G.evaluate(G.build(spec, t))) for n, t in G.TRADITIONAL.items()),
                 key=lambda x: x[2]["score"])
    sheet(case, spec, picks, best_t, os.path.join(OUT, f"후보_{case}.png"))
    items = []
    for i, (gen, f, r) in enumerate(picks):
        j = G.build(spec, gen)
        items.append((f"후보{i + 1}", j, geom.slabs(j)))
    export3dm.export_slabs(items, os.path.join(OUT, f"후보_{case}.3dm"))
    for i, (gen, f, r) in enumerate(picks):
        lin, near = G.lineage(gen)
        summary.append({"조건": case, "단면·각도": spec.label(), "후보": i + 1, "점수": r["score"],
                        "판정": r["lock"], "빠지는방향": r["escape"], "계보": lin,
                        "A단면_남은비율": round(r["A_left"], 2), "주먹장벌어짐_mm": round(r["flare_mm"], 1), "접촉면적_cm2": round(r["contact_cm2"]),
                        "유전자": gen})
with open(os.path.join(OUT, "후보목록.json"), "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=1)
