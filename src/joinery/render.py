"""확인 그림: 조립 상태 + 분해 상태(빠지는 방향으로 B를 띄움)."""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

from .grid import A, B, DIRS, DIR_KO
from .mesh import exposed_quads
from .raster import render as raster_render

_FONT = os.path.join(os.path.dirname(__file__), "fonts", "PretendardVariable.ttf")
font_manager.fontManager.addfont(_FONT)
plt.rcParams["font.family"] = font_manager.FontProperties(fname=_FONT).get_name()

# 무채색 + 블루
COL = {A: np.array([0.86, 0.86, 0.86]), B: np.array([0.30, 0.52, 0.90])}


def joint_quads(joint, explode=None, gap=None):
    g = joint.grid
    off = np.zeros(3)
    if explode is not None:
        gap = gap if gap is not None else max(g.shape) * 0.55
        v = np.array(DIRS[explode] if isinstance(explode, str) else explode, float)
        off = v / np.linalg.norm(v) * gap
    out = []
    for lab in (A, B):
        o = off if lab == B else np.zeros(3)
        for c, n in exposed_quads(g == lab, 1.0, o):
            ax = int(np.argmax(np.abs(n)))
            key = (lab, ax, int(n[ax]), round(float(c[0][ax]), 3))
            out.append((c, n, COL[lab], key))
    return out


def best_view(joint, explode):
    """맞물리는 면이 잘 보이도록 시점 고르기: 빠지는 방향 쪽에서 내려다본다."""
    if explode in ("+y", "-y"):
        return (-35 if explode == "+y" else 35), 38
    if explode in ("+x", "-x"):
        return (-125 if explode == "+x" else -55), 34
    return -58, 48


def image(joint, explode=None, size=900):
    az, el = best_view(joint, explode)
    return raster_render(joint_quads(joint, explode), azim=az, elev=el, size=size)


def joint_sheet(joints, results, path, cols=3):
    n = len(joints)
    rows = (n + cols - 1) // cols
    fig = plt.figure(figsize=(cols * 5.0, rows * 6.0), dpi=140, facecolor="white")
    for i, (j, r) in enumerate(zip(joints, results)):
        ax = fig.add_subplot(rows, cols, i + 1)
        esc = r["escape"]
        ax.imshow(image(j, esc[0] if esc else None, 700))
        ax.set_axis_off()
        dirs = ", ".join(DIR_KO[e] for e in esc) or "없음"
        ax.set_title(j.name, fontsize=15, color="#111", pad=22)
        ax.text(0.5, 1.02, f"빠지는 방향: {dirs}  ·  점수 {r['score']:.0f}",
                transform=ax.transAxes, ha="center", fontsize=10.5, color="#1f4fb4")
        ax.text(0.5, -0.03, r["lock"], transform=ax.transAxes, ha="center",
                fontsize=10, color="#444")
    fig.suptitle("전통 결구 라이브러리 v0.1   회색 = 부재 A(고정)   파랑 = 부재 B(빠지는 방향으로 띄움)",
                 fontsize=16, color="#111")
    fig.tight_layout(rect=(0, 0, 1, 0.97), h_pad=4.5)
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def joint_pair(joint, result, path):
    fig = plt.figure(figsize=(12, 6.2), dpi=150, facecolor="white")
    esc = result["escape"]
    ex = esc[0] if esc else None
    az, el = best_view(joint, ex)
    for k, e in enumerate((None, ex)):
        ax = fig.add_subplot(1, 2, k + 1)
        ax.imshow(raster_render(joint_quads(joint, e), azim=az, elev=el, size=900))
        ax.set_axis_off()
        ax.set_title("조립" if k == 0 else "분해", fontsize=13, color="#111")
    dirs = ", ".join(DIR_KO[e] for e in esc) or "없음"
    fig.suptitle(f"{joint.name}   빠지는 방향: {dirs}   {result['lock']}",
                 fontsize=14, color="#111")
    fig.text(0.5, 0.04, joint.note, ha="center", fontsize=11, color="#444")
    fig.savefig(path, facecolor="white")
    plt.close(fig)
