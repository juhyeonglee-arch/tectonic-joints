"""조립 가능성·제작 가능성 검사기.

1) 빠지는 방향: A를 고정했을 때 B가 6방향 중 어디로 끝까지 빠져나갈 수 있는가.
   - 1방향 = 좋은 맞춤 (그 방향으로 끼우고, 나머지는 잠김)
   - 2방향(서로 반대) = 미끄러지는 축이 하나 → 다른 부재 무게나 산지로 잡아야
   - 0방향 = 끼울 수 없음 (쐐기·제3부재 없이는 조립 불가)
2) 덩어리: 각 부재가 한 덩어리로 이어져 있는가 (떨어진 조각이 있으면 불량).
3) 얇은 살: 어느 방향으로든 두께가 min_cells 미만인 칸의 비율.
4) 결 방향 짧은 살(short grain): 부재 결(길이) 방향으로 짧게 끊긴 칸 → 쪼개지기 쉬움.
"""
import numpy as np
from scipy import ndimage

from .grid import A, B, DIRS


def escape_dirs(g, mover=B, fixed=A):
    out = []
    pm = g == mover
    pf = g == fixed
    for name, (dx, dy, dz) in DIRS.items():
        ax = [i for i, v in enumerate((dx, dy, dz)) if v][0]
        s = (dx, dy, dz)[ax]
        # 각 칸에서 d 방향 '앞쪽'에 fixed가 하나라도 있는가 → 누적 OR
        f = np.flip(pf, ax) if s > 0 else pf
        ahead = np.logical_or.accumulate(f, axis=ax)
        # 자기 칸 제외: 한 칸 밀기
        ahead = np.roll(ahead, 1, axis=ax)
        idx = [slice(None)] * 3
        idx[ax] = 0
        ahead[tuple(idx)] = False
        if s > 0:
            ahead = np.flip(ahead, ax)
        if not np.any(ahead & pm):
            out.append(name)
    return out


def components(mask):
    _, n = ndimage.label(mask)
    return n


def run_lengths(mask, axis):
    """각 칸이 속한 axis 방향 연속 구간의 길이 (벡터 계산)."""
    m = np.moveaxis(mask, axis, -1)
    shp = m.shape
    r = m.reshape(-1, shp[-1]).astype(np.int8)
    pad = np.zeros((r.shape[0], 1), np.int8)
    rp = np.concatenate([pad, r], 1)
    start = (rp[:, 1:] == 1) & (rp[:, :-1] == 0)
    rid = np.cumsum(start.ravel()).reshape(r.shape)
    rid = np.where(r == 1, rid, 0)
    cnt = np.bincount(rid.ravel())
    cnt[0] = 0
    out = cnt[rid].reshape(shp)
    return np.moveaxis(out, -1, axis)


AX = {"x": 0, "y": 1, "z": 2}


def thin_and_grain(g, label, grain_axis, min_cells=3, min_grain=4, zone_cells=4):
    mask = g == label
    other = (g != label) & (g != 0)
    # 접합 구역: 상대 부재에서 zone_cells칸(약 20mm) 이내의 내 칸만 따진다 (부재 몸통은 제외)
    zone = ndimage.binary_dilation(other, iterations=zone_cells) & mask
    rl = [run_lengths(mask, a) for a in range(3)]
    tmin = np.minimum(np.minimum(rl[0], rl[1]), rl[2])
    n = max(1, zone.sum())
    mask = zone
    thin = int(((tmin < min_cells) & mask).sum())
    grain = rl[AX[grain_axis]]
    short = int(((grain < min_grain) & mask).sum())
    return thin / n, short / n


def evaluate(j, min_mm=25.0, min_grain_mm=40.0):
    g = j.grid
    c = j.cell_mm
    mc = max(1, int(round(min_mm / c)))
    mg = max(1, int(round(min_grain_mm / c)))
    esc = escape_dirs(g)
    comps = {"A": components(g == A), "B": components(g == B)}
    zc = max(1, int(round(20.0 / c)))
    tA, sA = thin_and_grain(g, A, j.axis_a, mc, mg, zc)
    tB, sB = thin_and_grain(g, B, j.axis_b, mc, mg, zc)

    if len(esc) == 1:
        lock = "좋음: 한 방향으로만 끼워짐"
    elif len(esc) == 2 and _opposite(esc):
        lock = "보통: 한 축으로 미끄러짐 (눌러 주거나 산지 필요)"
    elif len(esc) == 0:
        lock = "끼울 수 없음 (쐐기·제3부재 필요)"
    else:
        lock = "약함: 여러 방향으로 빠짐"
    ok_parts = comps["A"] == 1 and comps["B"] == 1

    # 점수 (0~100): 잠김 50 + 덩어리 10 + 얇은 살 20 + 결 20
    s_lock = {1: 50, 0: 10}.get(len(esc), 30 if (len(esc) == 2 and _opposite(esc)) else 10)
    score = (s_lock + (10 if ok_parts else 0)
             + 20 * (1 - min(1, (tA + tB) * 5))
             + 20 * (1 - min(1, (sA + sB) * 5)))
    return {
        "escape": esc, "lock": lock, "components": comps,
        "thin_A": tA, "thin_B": tB, "short_grain_A": sA, "short_grain_B": sB,
        "score": round(score, 1),
    }


def _opposite(esc):
    a, b = esc
    return a[1] == b[1] and a[0] != b[0]
