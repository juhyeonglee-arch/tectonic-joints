"""여러 부재 노드의 조립 순서 찾기.

격자 라벨 1..n = 부재 번호. 다 조립된 상태에서 부재를 하나씩 빼낼 수 있는
순서(분해 순서)를 찾고, 그 역순이 조립 순서다.
  - 다 조립된 상태에서 빠지는 부재가 딱 하나뿐이면, 그 부재가 '열쇠'(마지막에 끼워
    전체를 잠그는 부재)다. 열쇠가 하나뿐인 노드가 가장 단단히 맞물린 노드.
  - 어떤 순서로도 못 빼면 = 조립 불가.
"""
import numpy as np
from scipy import ndimage

AXIS_DIRS = {"위로": (0, 0, 1), "아래로": (0, 0, -1), "+x": (1, 0, 0), "−x": (-1, 0, 0),
             "+y": (0, 1, 0), "−y": (0, -1, 0)}


def free_along(mover, fixed, d):
    """mover 마스크를 d 방향으로 끝까지 밀어 낼 때 fixed와 부딪히지 않는가."""
    if not mover.any() or not fixed.any():
        return True
    d = np.asarray(d, float)
    d[np.abs(d) < 1e-9] = 0
    nz = np.count_nonzero(d)
    if nz == 1:                                     # 축 방향: 누적으로 정확히
        ax = int(np.flatnonzero(d)[0])
        s = d[ax] > 0
        f = np.flip(fixed, ax) if s else fixed
        ahead = np.logical_or.accumulate(f, axis=ax)
        ahead = np.roll(ahead, 1, axis=ax)
        idx = [slice(None)] * 3
        idx[ax] = 0
        ahead[tuple(idx)] = False
        if s:
            ahead = np.flip(ahead, ax)
        return not np.any(ahead & mover)
    fx = ndimage.binary_erosion(fixed, border_value=1)   # 빗방향 계단 충돌 완화
    surf = mover & ~ndimage.binary_erosion(mover, border_value=0)
    pts = np.argwhere(surf).astype(float) + 0.5
    step = d / np.abs(d).max() * 0.7
    shp = np.array(mover.shape)
    for k in range(1, int(shp.max() * 1.6 / 0.7) + 2):
        q = np.floor(pts + step * k).astype(int)
        inside = np.all((q >= 0) & (q < shp), axis=1)
        if not inside.any():
            return True
        qi = q[inside]
        if fx[qi[:, 0], qi[:, 1], qi[:, 2]].any():
            return False
        pts = pts[inside]
    return True


def removable(g, part, remaining, dirs):
    mover = g == part
    fixed = np.isin(g, [p for p in remaining if p != part])
    return [n for n, d in dirs.items() if free_along(mover, fixed, d)]


def disassemble(g, parts=None, dirs=None, base=None):
    """분해 순서 찾기 (깊이 우선, 작은 n이라 전수 탐색).

    base: 땅에 붙어 끝까지 남는 부재(예: 기둥). 마지막에 남으면 된다.
    반환: dict(order=[(부재, 방향들)], keys=[다 조립된 상태에서 빠지는 부재], ok=bool)
    """
    parts = parts or sorted(int(p) for p in np.unique(g) if p)
    dirs = dirs or AXIS_DIRS
    full = {p: removable(g, p, parts, dirs) for p in parts}
    keys = [p for p in parts if full[p] and p != base]

    best = None

    def dfs(remaining, seq):
        nonlocal best
        if best is not None:
            return
        if len(remaining) == 1 or (base is not None and remaining == [base]):
            best = seq + [(remaining[0], ["(마지막에 남음)"])]
            return
        for p in remaining:
            if p == base:
                continue
            ds = full[p] if len(remaining) == len(parts) else removable(g, p, remaining, dirs)
            if ds:
                dfs([q for q in remaining if q != p], seq + [(p, ds)])
                if best is not None:
                    return

    dfs(list(parts), [])
    return {"ok": best is not None, "order": best or [], "keys": keys,
            "full_free": full}


def assembly_text(res, names):
    if not res["ok"]:
        return "조립 불가: 어떤 순서로도 부재를 뺄 수 없음"
    steps = list(reversed(res["order"]))
    out = []
    for i, (p, ds) in enumerate(steps, 1):
        if i == 1:
            out.append(f"{i}. {names[p]} 놓기")
        else:
            inv = {"위로": "위에서 내려", "아래로": "아래에서 올려"}.get(ds[0], f"{ds[0]} 쪽에서 밀어")
            out.append(f"{i}. {names[p]} — {inv} 끼움")
    key = "열쇠 부재: " + (", ".join(names[k] for k in res["keys"]) if res["keys"] else "없음")
    return "\n".join(out) + "\n" + key
