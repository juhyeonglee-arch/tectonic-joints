"""세 부재 모서리: 같은 구조 조건에서 표현 목표(드러냄/숨김)만 바꿔 생성·비교."""
import json
import os
import sys
import textwrap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import rhino3dm as r3  # noqa: E402
from joinery import node3 as N, assembly as AS, render, geom  # noqa: E402
from joinery.raster import render as raster  # noqa: E402
from joinery.export3dm import _layer  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else "node3_out"
os.makedirs(OUT, exist_ok=True)
SPEC = N.Spec3(leg=120, aw=60, ah=120, ext=150, below=120)
COLORS = {1: np.array([0.86, 0.86, 0.86]), 2: np.array([0.30, 0.52, 0.90]),
          3: np.array([0.15, 0.27, 0.52])}
HEX = {1: "#dbdbdb", 2: "#4d85e6", 3: "#264685"}
TARGET_KO = {"reveal": "드러냄", "hide": "숨김"}
DIRV = {"위로": (0, 0, 1), "아래로": (0, 0, -1), "+x": (1, 0, 0), "−x": (-1, 0, 0),
        "+y": (0, 1, 0), "−y": (0, -1, 0)}


def explode_offsets(r):
    order = r["assembly"]["order"]
    off = {}
    gap = SPEC.ah * 1.25
    movers = [(p, ds) for p, ds in order if p != 1]
    for k, (p, ds) in enumerate(movers):
        v = np.array(DIRV.get(ds[0], (0, 0, 1)), float)
        off[p] = tuple(v * gap * (len(movers) - k))
    return off


def plans(ax, node):
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path
    sl = [s for s in node["slabs"] if not (s[2][2].is_empty and s[2][3].is_empty)]
    sl = sorted(sl, key=lambda t: -t[1])
    n = len(sl)
    w = 1.0 / max(n, 1)
    L = SPEC.leg
    for k, (z0, z1, parts) in enumerate(sl):
        sub = ax.inset_axes([k * w + 0.01, 0.05, w - 0.02, 0.9])
        for p in (1, 2, 3):
            for poly in geom._polys(parts[p]):
                v = [np.asarray(poly.exterior.coords)] + [np.asarray(i.coords) for i in poly.interiors]
                codes = []
                for a in v:
                    cd = [Path.LINETO] * len(a)
                    cd[0] = Path.MOVETO
                    codes += cd
                sub.add_patch(PathPatch(Path(np.concatenate(v), codes), fc=HEX[p], ec="#111", lw=0.6))
        sub.set_xlim(-8, L * 1.7)
        sub.set_ylim(-8, L * 1.7)
        sub.set_aspect("equal")
        sub.set_xticks([]); sub.set_yticks([])
        for s_ in sub.spines.values():
            s_.set_color("#bbb")
        sub.set_title(f"{k + 1}층 z {z0 - SPEC.below:.0f}~{z1 - SPEC.below:.0f}", fontsize=8, color="#444", pad=2)


def sheet(rows, path):
    fig = plt.figure(figsize=(19, 5.0 * len(rows)), dpi=120, facecolor="white")
    gs = fig.add_gridspec(len(rows), 3, width_ratios=[1, 1, 1.25], hspace=0.5, wspace=0.03)
    for i, (title, gen, r, node) in enumerate(rows):
        a1 = fig.add_subplot(gs[i, 0])
        a1.imshow(raster(N.quads(node, COLORS), azim=-135, elev=32, size=640))   # 바깥 모서리 쪽
        a1.set_axis_off()
        a2 = fig.add_subplot(gs[i, 1])
        a2.imshow(raster(N.quads(node, COLORS, explode_offsets(r)), azim=45, elev=30, size=640))
        a2.set_axis_off()
        a2.set_title("분해 (빠지는 방향으로 띄움)", fontsize=10, color="#1f4fb4")
        a3 = fig.add_subplot(gs[i, 2])
        a3.set_axis_off()
        a3.set_title("층별 평면 (위→아래)", fontsize=10, color="#1f4fb4")
        plans(a3, node)
        a1.text(0.0, 1.13, title + "   (왼쪽: 바깥 모서리에서 본 모습)", transform=a1.transAxes, fontsize=14, color="#111")
        a1.text(0.0, 1.02, f"구조 {r['structure']:.0f} · 표현 {r['expression']:.0f} · 보이는 경계 {r['exposure']:.1f}"
                f" · 다리 단면 {r['leg_left'] * 100:.0f}% 남음", transform=a1.transAxes, fontsize=10, color="#1f4fb4", va="bottom")
        txt = N.describe(gen) + "\n" + AS.assembly_text(r["assembly"], N.NAMES).replace("\n", "  ")
        a2.text(-1.0, -0.04, "\n".join(sum((textwrap.wrap(t, 110) for t in txt.split("\n")), [])),
                transform=a2.transAxes, ha="left", va="top", fontsize=9, color="#444")
    fig.suptitle(f"세 부재 모서리 — {SPEC.label()}   회색 = 다리  파랑 = 장선 X  남색 = 장선 Y",
                 fontsize=16, color="#111", y=0.995)
    fig.savefig(path, facecolor="white", bbox_inches="tight")
    plt.close(fig)


def export(rows, path):
    model = r3.File3dm()
    model.Settings.ModelUnitSystem = r3.UnitSystem.Millimeters
    root = _layer(model, "세부재모서리", (40, 40, 40, 255))
    x = 0.0
    cols = {1: (200, 200, 200, 255), 2: (77, 133, 230, 255), 3: (38, 70, 133, 255)}
    for title, gen, r, node in rows:
        jl = _layer(model, title.replace(":", ""), (40, 40, 40, 255), root)
        lys = {p: _layer(model, N.NAMES[p], cols[p], jl) for p in (1, 2, 3)}
        for z0, z1, parts in node["slabs"]:
            for p, g in parts.items():
                for poly in geom._polys(g):
                    crv = r3.PolylineCurve([r3.Point3d(px + x, py, z0) for px, py in poly.exterior.coords])
                    ex = r3.Extrusion.Create(crv, -(z1 - z0), True)
                    if ex is None:
                        continue
                    at = r3.ObjectAttributes()
                    at.LayerIndex = lys[p].Index
                    model.Objects.AddExtrusion(ex, at)
        at = r3.ObjectAttributes()
        at.LayerIndex = jl.Index
        model.Objects.AddTextDot(title, r3.Point3d(x + 100, -60, 0), at)
        x += node["size"][0] + 200
    model.Write(path, 7)


rows_all = []
summary = {}
cache = os.environ.get("N3_CACHE")
prev = json.load(open(cache, encoding="utf-8")) if cache else None
if prev:
    prev = {k: [{"유전자": x["유전자"]} for x in v] for k, v in prev.items()}
for tgt in ("reveal", "hide"):
    if prev:
        gens = [x["유전자"] for x in prev[tgt]]
        picks = [(g, N.evaluate(N.build(SPEC, g), tgt)) for g in gens]
    else:
        res = N.search(SPEC, tgt, pop=60, gens=40,
                       log=lambda gi, f: print(tgt, gi, round(f, 1), flush=True) if gi % 10 == 0 else None)
        picks = [(g, N.evaluate(N.build(SPEC, g), tgt)) for g, _ in N.pick(res, 3)]
    rows = [(f"{TARGET_KO[tgt]} 후보 {i + 1}", g, r, N.build(SPEC, g)) for i, (g, r) in enumerate(picks)]
    rows_all += rows
    summary[tgt] = [{"제목": t, "점수": r["score"], "구조": r["structure"], "표현": r["expression"],
                     "보이는경계": r["exposure"], "조립": AS.assembly_text(r["assembly"], N.NAMES),
                     "설명": N.describe(g), "유전자": g} for t, g, r, _ in rows]
    sheet(rows, os.path.join(OUT, f"세부재모서리_{TARGET_KO[tgt]}.png"))
# 비교 기준: 기존 꼴
base_rows = []
for name, g in N.TRADITIONAL.items():
    r = N.evaluate(N.build(SPEC, g), "reveal")
    base_rows.append((f"기존 꼴: {name}", g, r, N.build(SPEC, g)))
sheet(base_rows, os.path.join(OUT, "세부재모서리_기존꼴.png"))
export(base_rows + rows_all, os.path.join(OUT, "세부재모서리.3dm"))
with open(os.path.join(OUT, "후보목록.json"), "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=1)
