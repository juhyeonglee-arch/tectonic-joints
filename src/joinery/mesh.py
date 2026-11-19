"""복셀 → 바깥 면 사각형 메시 (같은 평면의 칸은 한 줄로 합쳐 면 수를 줄인다)."""
import numpy as np

# 면 방향: (축, 부호)
FACES = [(0, 1), (0, -1), (1, 1), (1, -1), (2, 1), (2, -1)]


def exposed_quads(mask, cell=1.0, offset=(0, 0, 0)):
    """mask 바깥 면 사각형 목록 [(4×3 꼭짓점 배열, 법선)].

    각 면 방향마다 2D 단면에서 직사각형 탐욕 병합(greedy meshing)을 한다.
    """
    quads = []
    m = np.pad(mask, 1)
    for ax, s in FACES:
        nb = np.roll(m, -s, axis=ax)
        face = (m & ~nb)[1:-1, 1:-1, 1:-1]
        u, v = [a for a in range(3) if a != ax]
        for k in range(face.shape[ax]):
            sl = [slice(None)] * 3
            sl[ax] = k
            f = face[tuple(sl)].copy()           # 2D (u, v)
            nu, nv = f.shape
            for i in range(nu):
                j = 0
                while j < nv:
                    if not f[i, j]:
                        j += 1
                        continue
                    # v 방향으로 늘이기
                    j2 = j
                    while j2 < nv and f[i, j2]:
                        j2 += 1
                    # u 방향으로 늘이기
                    i2 = i + 1
                    while i2 < nu and f[i2, j:j2].all():
                        i2 += 1
                    f[i:i2, j:j2] = False
                    plane = k + (1 if s > 0 else 0)
                    corners = []
                    for (a, b) in ((i, j), (i2, j), (i2, j2), (i, j2)):
                        p = [0.0, 0.0, 0.0]
                        p[ax] = plane
                        p[u] = a
                        p[v] = b
                        corners.append(p)
                    c = np.array(corners) * cell + np.asarray(offset)
                    if (s < 0) != (ax == 1):
                        c = c[::-1]
                    n = [0, 0, 0]
                    n[ax] = s
                    quads.append((c, np.array(n, float)))
                    j = j2
    return quads
