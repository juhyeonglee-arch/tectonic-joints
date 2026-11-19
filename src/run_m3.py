"""M3 레이저 적층 출력: 세 부재 모서리 드러냄 1 + 숨김 1 → 판 DXF + 조립 순서도.

python run_m3.py <출력폴더> <node3 후보목록.json>
환경변수(없으면 기본값): M3_T=3.0  M3_KERF=0.2  M3_CLEAR=0.2  M3_PIN=4.0  M3_BED=600x400  M3_SCALES=1,0.5
"""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import PathPatch, Rectangle  # noqa: E402
from matplotlib.path import Path  # noqa: E402
import rhino3dm as r3  # noqa: E402
from shapely.geometry import box as sbox  # noqa: E402

from joinery import node3 as N, assembly as AS, laser as LZ, geom, render  # noqa: E402,F401
from joinery.raster import render as raster  # noqa: E402
from joinery.export3dm import _layer  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else "m3_out"
CAND = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(__file__), "..", "node3_세부재모서리_v0.1", "후보목록.json")
env = os.environ.get
T = float(env("M3_T", 3.0))
KERF = float(env("M3_KERF", 0.2))
CLEAR = float(env("M3_CLEAR", 0.2))
PIN = float(env("M3_PIN", 4.0))
BED = tuple(float(v) for v in env("M3_BED", "600x400").lower().split("x"))
SCALES = [float(v) for v in env("M3_SCALES", "1,0.5").split(",")]

SPEC = N.Spec3(leg=120, aw=60, ah=120, ext=150, below=120)
COLORS = {1: np.array([0.86, 0.86, 0.86]), 2: np.array([0.30, 0.52, 0.90]), 3: np.array([0.15, 0.27, 0.52])}
HEX = {1: "#d6d6d6", 2: "#4d85e6", 3: "#264685"}
BLUE, INK, GREY = "#1f4fb4", "#111111", "#555555"
DIRV = {"위로": (0, 0, 1), "아래로": (0, 0, -1), "+x": (1, 0, 0), "−x": (-1, 0, 0), "+y": (0, 1, 0), "−y": (0, -1, 0)}
DIR_IN = {"위로": "위에서 내려", "아래로": "아래에서 올려", "+x": "+x 쪽(장선 X 끝 방향)에서 밀어",
          "+y": "+y 쪽(장선 Y 끝 방향)에서 밀어", "−x": "−x 쪽에서 밀어", "−y": "−y 쪽에서 밀어"}
NODES = [("reveal", 0, "R", "드러냄"), ("hide", 0, "H", "숨김")]


def scale_tag(s):
    return "1대1" if abs(s - 1) < 1e-9 else f"1대{round(1 / s):d}"


def draw_poly(ax, g, fc, ec="#111", lw=0.6, off=(0, 0)):
    for poly in geom._polys(g):
        v = [np.asarray(poly.exterior.coords)] + [np.asarray(i.coords) for i in poly.interiors]
        codes = []
        for a in v:
            cd = [Path.LINETO] * len(a)
            cd[0] = Path.MOVETO
            codes += cd
        ax.add_patch(PathPatch(Path(np.concatenate(v) + np.asarray(off), codes), fc=fc, ec=ec, lw=lw))


def explode(order, gap):
    movers = [(p, ds) for p, ds in order if p != 1]
    off = {}
    for k, (p, ds) in enumerate(movers):
        off[p] = tuple(np.array(DIRV.get(ds[0], (0, 0, 1)), float) * gap * (len(movers) - k))
    return off


def node_quads(node, members, offs=None):
    out = []
    for p in members:
        sl = [(z0, z1, parts[p], parts[p]) for z0, z1, parts in node["slabs"] if not parts[p].is_empty]
        out += geom.slab_quads(sl, p, COLORS[p], (offs or {}).get(p, (0, 0, 0)))
    return out


def groups(sheets):
    """같은 모양이 이어지는 판 묶음 [(k0, k1, fit)]."""
    out = []
    for sh in sheets:
        if out and out[-1][2] is sh["fit"]:
            out[-1][1] = sh["k"]
        else:
            out.append([sh["k"], sh["k"], sh["fit"]])
    return out


def order_sheet(title, sub, node, sn, res, info, P, tag, path):
    steps = list(reversed(res["order"]))
    L = node["spec"].leg * P.scale
    fig = plt.figure(figsize=(20, 25), dpi=110, facecolor="white")
    gs = fig.add_gridspec(3, 3, height_ratios=[0.9, 1.5, 0.95], hspace=0.22, wspace=0.08, top=0.915)
    fig.text(0.06, 0.985, title, fontsize=22, color=INK, ha="left", va="top")
    fig.text(0.06, 0.962, sub, fontsize=12, color=BLUE, ha="left", va="top", linespacing=1.6)
    # 맨 위: 조립 모습 / 분해 모습 / 요약
    a = fig.add_subplot(gs[0, 0]); a.imshow(raster(node_quads(sn, (1, 2, 3)), azim=-135, elev=32, size=700)); a.set_axis_off()
    a.set_title("다 끼운 모습 (바깥 모서리 쪽)", fontsize=13, color=INK)
    a = fig.add_subplot(gs[0, 1])
    a.imshow(raster(node_quads(sn, (1, 2, 3), explode(res["order"], sn["spec"].ah * 1.25)), azim=45, elev=30, size=700))
    a.set_axis_off(); a.set_title("분해 (빠지는 방향으로 띄움)", fontsize=13, color=INK)
    a = fig.add_subplot(gs[0, 2]); a.set_axis_off()
    lines = ["판 수"]
    for p in (1, 2, 3):
        n = len(info[p]["sheets"])
        pcs = sum(len(s["fit"]) for s in info[p]["sheets"])
        lines.append(f"  {LZ.MEMBER_KO[p]}: {n}장" + (f" (조각 {pcs}개)" if pcs != n else ""))
    lines.append("")
    lines.append("정렬 핀 (지름 {:g}mm 목봉)".format(P.pin))
    for p in (1, 2, 3):
        for q in info[p]["pins"]:
            lines.append(f"  {LZ.MEMBER_CODE[p]}-{q['name']}: {LZ.MEMBER_CODE[p]}{q['k0']:02d}~{q['k1']:02d}, 길이 {q['len']:.0f}mm")
    a.text(0, 1, "\n".join(lines), va="top", fontsize=11.5, color=INK, linespacing=1.55, transform=a.transAxes)
    # 가운데: 부재별 판 쌓기
    for ci, p in enumerate((1, 2, 3)):
        a = fig.add_subplot(gs[1, ci]); a.set_axis_off()
        sheets = info[p]["sheets"]
        gr = groups(sheets)[::-1]
        a.set_title(f"① {LZ.MEMBER_KO[p]} 만들기 — 판 {len(sheets)}장을 아래(01)부터 쌓아 붙임",
                    fontsize=13, color=INK, loc="left")
        n = len(gr)
        allg = [g for _, _, f in gr for g in f]
        x0, y0, x1, y1 = np.array([g.bounds for g in allg]).T
        bx = (x0.min(), y0.min(), x1.max(), y1.max())
        cw = max(bx[2] - bx[0], bx[3] - bx[1])
        rowh = 1.0 / max(n, 4)
        for r, (k0, k1, fit) in enumerate(gr):
            sub_ax = a.inset_axes([0.0, 1 - (r + 1) * rowh + 0.01, 0.42, rowh - 0.02])
            for g in fit:
                draw_poly(sub_ax, g, HEX[p])
            if p != 1:
                draw_poly(sub_ax, sbox(0, 0, L, L), "none", ec="#999", lw=0.6)
            for q in info[p]["pins"]:
                if q["k0"] <= k1 and q["k1"] >= k0:
                    sub_ax.plot(q["x"], q["y"], "o", ms=4, mfc="white", mec=INK, mew=0.8)
                    sub_ax.text(q["x"] + cw * 0.03, q["y"], q["name"], fontsize=7.5, color=INK, va="center")
            sub_ax.set_xlim(bx[0] - 6, bx[0] + cw + 6); sub_ax.set_ylim(bx[1] - 6, bx[1] + cw + 6)
            sub_ax.set_aspect("equal"); sub_ax.set_xticks([]); sub_ax.set_yticks([])
            for s_ in sub_ax.spines.values():
                s_.set_color("#ddd")
            c = LZ.MEMBER_CODE[p]
            cnt = k1 - k0 + 1
            z0 = sheets[k0 - 1]["z0"]; z1 = sheets[k1 - 1]["z1"]
            pins_here = [q["name"] for q in info[p]["pins"] if q["k0"] <= k1 and q["k1"] >= k0]
            txt = f"{tag}-{c}{k0:02d} ~ {c}{k1:02d}   {cnt}장\n높이 {z0:.0f}~{z1:.0f}mm"
            if len(fit) > 1:
                txt += f"\n한 장이 조각 {len(fit)}개 (a, b…)"
            if pins_here:
                txt += "\n핀 " + ", ".join(pins_here)
            if k1 == len(sheets):
                txt += "\n맨 윗장(T)은 글자 면을 아래로"
            a.text(0.46, 1 - (r + 0.5) * rowh, txt, va="center", fontsize=10.5, color=INK, linespacing=1.4,
                   transform=a.transAxes)
        if info[p]["loose"]:
            a.text(0, 1 - n * rowh - 0.01, f"핀 없는 조각 {len(info[p]['loose'])}개 (맨 윗장" + ("" if p == 1 else "·맨 아랫장")
                   + ": 핀이 겉에 안 보이게 일부러 구멍을 안 뚫음)\n→ 바로 아랫장(윗장) 옆면에 직각자를 대고 맞춰 붙일 것",
                   fontsize=10, color=BLUE, transform=a.transAxes, va="top", linespacing=1.5)
    # 아래: 끼우는 순서
    have = []
    for i, (p, ds) in enumerate(steps[:3]):
        a = fig.add_subplot(gs[2, i]); a.set_axis_off()
        offs = {}
        if i > 0:
            offs[p] = tuple(np.array(DIRV.get(ds[0], (0, 0, 1))) * sn["spec"].ah * 0.9)
        have.append(p)
        a.imshow(raster(node_quads(sn, have, offs), azim=45 if i else -135, elev=30, size=640))
        if i == 0:
            t = f"② {i + 1}. {LZ.MEMBER_KO[p]} 세우기"
        else:
            t = f"② {i + 1}. {LZ.MEMBER_KO[p]} — {DIR_IN.get(ds[0], ds[0])} 끼움"
        if p in res["keys"]:
            t += "  ← 열쇠 부재"
        a.set_title(t, fontsize=13, color=BLUE if p in res["keys"] else INK, loc="left")
    fig.text(0.06, 0.015, "부재끼리는 붙이지 않는다 (마른 상태로 끼워 보고 헐거움·뻑뻑함·빠짐을 기록).  "
             "판끼리만 목공풀로 붙이고, 핀에 꿰어 누른 뒤 굳힌다.  회색 = 다리  파랑 = 장선 X  남색 = 장선 Y",
             fontsize=11, color=GREY)
    fig.savefig(path, facecolor="white", bbox_inches="tight")
    plt.close(fig)


def bed_preview(beds, title, path, P):
    W, H = P.bed
    n = len(beds)
    cols = 3
    rows = (n + cols - 1) // cols
    fig = plt.figure(figsize=(cols * 6.2, rows * 4.6 + 0.8), dpi=90, facecolor="white")
    for i, bed in enumerate(beds):
        a = fig.add_subplot(rows, cols, i + 1)
        a.add_patch(Rectangle((0, 0), W, H, fc="#f4f4f4", ec="#999", lw=0.8))
        for q in bed:
            draw_poly(a, q["cut"], HEX[q.get("member", 1)] if q.get("member") else "#e6e6e6", lw=0.4)
            for h in q["holes"]:
                draw_poly(a, h, "white", lw=0.3)
            if q["label"]:
                vs = [np.vstack([t, t[:1]]) for t in q["label"]]
                cd = sum(([Path.MOVETO] + [Path.LINETO] * (len(v) - 1) for v in vs), [])
                a.add_patch(PathPatch(Path(np.concatenate(vs), cd), fc="#0b2a6b" if q.get("member") != 1 else BLUE, lw=0))
        a.set_xlim(-5, W + 5); a.set_ylim(-5, H + 5); a.set_aspect("equal"); a.set_axis_off()
        a.set_title(f"판{i + 1:02d}.dxf — 부품 {len(bed)}개", fontsize=11, color=INK)
    fig.suptitle(title, fontsize=15, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def add_3dm(model, root, node_parts, name, dx, P):
    jl = _layer(model, name, (40, 40, 40, 255), root)
    cols = {1: (200, 200, 200, 255), 2: (77, 133, 230, 255), 3: (38, 70, 133, 255)}
    lys = {p: _layer(model, LZ.MEMBER_KO[p], cols[p], jl) for p in (1, 2, 3)}
    for q in node_parts:
        g = q["design"]
        for poly in geom._polys(g):
            crv = r3.PolylineCurve([r3.Point3d(x + dx, y, q["z0"]) for x, y in poly.exterior.coords])
            ex = r3.Extrusion.Create(crv, -(q["z1"] - q["z0"]), True)
            if ex is None:
                continue
            at = r3.ObjectAttributes(); at.LayerIndex = lys[q["member"]].Index; at.Name = q["id"]
            model.Objects.AddExtrusion(ex, at)


def main():
    os.makedirs(OUT, exist_ok=True)
    cand = json.load(open(CAND, encoding="utf-8"))
    report = {"가정": {"판두께": T, "커프": KERF, "맞춤공차": CLEAR, "핀지름": PIN, "작업대": BED}, "노드": {}}
    model = r3.File3dm(); model.Settings.ModelUnitSystem = r3.UnitSystem.Millimeters
    root = _layer(model, "M3 레이저 적층 (판 경계·공차 반영)", (40, 40, 40, 255))
    dx3 = 0.0
    for s in SCALES:
        P = LZ.Params(t=T, kerf=KERF, clear=CLEAR, pin=PIN, bed=BED, scale=s)
        sdir = os.path.join(OUT, scale_tag(s) + ("" if s == 1 else "_시험"))
        for tgt, i, tag, ko in NODES:
            c = cand[tgt][i]
            gen = c["유전자"]
            node = N.build(SPEC, gen)
            r0 = N.evaluate(node, tgt)
            sn = LZ.snapped_node(node, P)
            r1 = N.evaluate(sn, tgt)
            _, zrep = LZ.snap_slabs(node, P)
            parts, info = LZ.build_parts(node, P, tag)
            thin = LZ.thin_warnings(parts)
            beds = LZ.nest(parts, P)
            d = os.path.join(sdir, f"{ko}_{tag}")
            os.makedirs(d, exist_ok=True)
            for bi, bed in enumerate(beds, 1):
                LZ.write_dxf(bed, os.path.join(d, f"{tag}_판{bi:02d}.dxf"), P)
            bed_preview(beds, f"{ko} 노드 ({scale_tag(s)}) — 작업대 {BED[0]:.0f}×{BED[1]:.0f}mm, {len(beds)}판", os.path.join(d, "배치_미리보기.png"), P)
            with open(os.path.join(d, "판목록.csv"), "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(["판번호", "부재", "아래에서 몇째", "높이 아래(mm)", "높이 위(mm)", "작업대 파일", "핀 구멍 수", "뒤집어 놓기"])
                where = {q["id"]: bi for bi, bed in enumerate(beds, 1) for q in bed}
                for q in sorted(parts, key=lambda q: (q["member"], q["k"], q["id"])):
                    w.writerow([q["id"], LZ.MEMBER_KO[q["member"]], q["k"], f"{q['z0']:.1f}", f"{q['z1']:.1f}",
                                f"{tag}_판{where[q['id']]:02d}.dxf", len(q["holes"]), "예" if q["top"] else ""])
            sub = (f"{c['설명'].splitlines()[0]} · {c['설명'].splitlines()[1].replace('위→아래  ', '위→아래: ')}\n"
                   f"축척 {scale_tag(s)} · 판 {T:g}mm MDF · 커프 {KERF:g} · 맞춤 공차 {CLEAR:g} (부재 사이 틈) · "
                   f"판 경계 맞춘 뒤 검사: 열쇠 = {', '.join(N.NAMES[k] for k in r1['assembly']['keys']) or '없음'}, 구조 {r1['structure']:.0f}")
            order_sheet(f"{ko} 노드 — 레이저 적층 조립 순서도 ({scale_tag(s)})", sub, node, sn, r1["assembly"], info, P, tag,
                        os.path.join(d, "조립순서도.png"))
            add_3dm(model, root, parts, f"{scale_tag(s)} {ko}", dx3, P)
            dx3 += 400 * s + 150
            key = f"{scale_tag(s)} {ko}"
            report["노드"][key] = {
                "원래 후보": c["제목"], "판 수": {LZ.MEMBER_KO[p]: len(info[p]["sheets"]) for p in (1, 2, 3)},
                "부품 수": len(parts), "작업대 수": len(beds),
                "층 경계(설계→판)": [[round(a, 1), round(b, 1), round(c_, 1), round(d_, 1)] for a, b, c_, d_ in zrep],
                "조립 원래": AS.assembly_text(r0["assembly"], N.NAMES),
                "조립 판맞춤": AS.assembly_text(r1["assembly"], N.NAMES),
                "빠짐 원래": r0["assembly"]["full_free"], "빠짐 판맞춤": r1["assembly"]["full_free"],
                "구조 원래": r0["structure"], "구조 판맞춤": r1["structure"],
                "핀": {LZ.MEMBER_KO[p]: [{k: (round(v, 1) if isinstance(v, float) else v) for k, v in q.items()} for q in info[p]["pins"]] for p in (1, 2, 3)},
                "핀 없는 조각": {LZ.MEMBER_KO[p]: info[p]["loose"] for p in (1, 2, 3)},
                "가는 살 경고(3mm 미만, 면적 mm²)": thin,
            }
            print(key, "판", len(parts), "작업대", len(beds), "열쇠", r0["assembly"]["keys"], "→", r1["assembly"]["keys"],
                  "핀", {p: len(info[p]["pins"]) for p in info}, "느슨", {p: len(info[p]["loose"]) for p in info},
                  "가는살", len(thin), flush=True)
    cdir = os.path.join(OUT, "공차시험편")
    os.makedirs(cdir, exist_ok=True)
    P = LZ.Params(t=T, kerf=KERF, clear=CLEAR, pin=PIN, bed=BED)
    cb = LZ.coupon(P)
    LZ.write_dxf(cb[0], os.path.join(cdir, "공차시험편.dxf"), P)
    P2 = LZ.Params(t=T, kerf=KERF, clear=CLEAR, pin=PIN, bed=(290, 72))
    bed_preview(cb, "공차 시험편 — 먼저 이것부터 잘라 틈·핀 구멍·커프를 정한다", os.path.join(cdir, "공차시험편.png"), P2)
    model.Write(os.path.join(OUT, "적층확인.3dm"), 7)
    with open(os.path.join(OUT, "출력보고.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
