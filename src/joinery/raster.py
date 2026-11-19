"""작은 소프트웨어 렌더러 (정사영 + 깊이 버퍼 + 윤곽선).

matplotlib 3D는 면 앞뒤 순서를 자주 틀려서, 결구 그림은 이걸로 그린다.
"""
import numpy as np


def view_matrix(azim_deg, elev_deg):
    a, e = np.radians(azim_deg), np.radians(elev_deg)
    # 카메라가 바라보는 방향의 반대(카메라 위치 방향)
    f = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
    up = np.array([0, 0, 1.0])
    r = np.cross(up, f)
    r /= np.linalg.norm(r)
    u = np.cross(f, r)
    return np.stack([r, u, f]), f      # 행: 화면 x, 화면 y, 깊이(카메라쪽 +)


def render(quads, azim=-58, elev=28, size=900, pad=0.06, light=(0.45, -0.35, 0.82),
           bg=(1, 1, 1), line=(0.08, 0.08, 0.08)):
    """quads: [(corners 4×3, normal 3, color 3, key)] → (H×W×3 이미지)."""
    R, fwd = view_matrix(azim, elev)
    L = np.asarray(light, float)
    L /= np.linalg.norm(L)
    pts = np.concatenate([q[0] for q in quads]) @ R.T
    lo, hi = pts[:, :2].min(0), pts[:, :2].max(0)
    span = (hi - lo).max() * (1 + 2 * pad)
    ctr = (lo + hi) / 2
    scale = size / span
    W = H = size
    zbuf = np.full((H, W), -np.inf)
    kid = np.full((H, W), -1, np.int32)
    img = np.ones((H, W, 3)) * np.asarray(bg)

    keys = {}
    for corners, n, col, key in quads:
        if n @ fwd <= 0:          # 뒷면 제거
            continue
        k = keys.setdefault(key, len(keys))
        p = corners @ R.T
        sx = (p[:, 0] - ctr[0]) * scale + W / 2
        sy = H / 2 - (p[:, 1] - ctr[1]) * scale
        sz = p[:, 2]
        shade = 0.58 + 0.42 * max(0.0, float(n @ L))
        c = np.clip(np.asarray(col) * shade, 0, 1)
        for tri in ((0, 1, 2), (0, 2, 3)):
            _tri(sx[list(tri)], sy[list(tri)], sz[list(tri)], c, k, zbuf, kid, img)

    # 윤곽선: 이웃 픽셀과 면 묶음(key)이 다르면 선
    edge = np.zeros((H, W), bool)
    edge[:, 1:] |= kid[:, 1:] != kid[:, :-1]
    edge[1:, :] |= kid[1:, :] != kid[:-1, :]
    img[edge] = img[edge] * 0.15 + np.asarray(line) * 0.85
    return img


def _tri(x, y, z, col, k, zbuf, kid, img):
    H, W = zbuf.shape
    x0, x1 = int(max(0, np.floor(x.min()))), int(min(W - 1, np.ceil(x.max())))
    y0, y1 = int(max(0, np.floor(y.min()))), int(min(H - 1, np.ceil(y.max())))
    if x1 < x0 or y1 < y0:
        return
    xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
    d = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2])
    if abs(d) < 1e-12:
        return
    w0 = ((y[1] - y[2]) * (xs - x[2]) + (x[2] - x[1]) * (ys - y[2])) / d
    w1 = ((y[2] - y[0]) * (xs - x[2]) + (x[0] - x[2]) * (ys - y[2])) / d
    w2 = 1 - w0 - w1
    eps = -1e-6
    inside = (w0 >= eps) & (w1 >= eps) & (w2 >= eps)
    zz = w0 * z[0] + w1 * z[1] + w2 * z[2]
    sub = zbuf[y0:y1 + 1, x0:x1 + 1]
    m = inside & (zz > sub + 1e-7)
    sub[m] = zz[m]
    kid[y0:y1 + 1, x0:x1 + 1][m] = k
    img[y0:y1 + 1, x0:x1 + 1][m] = col
