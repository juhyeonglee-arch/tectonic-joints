"""접합부를 복셀 격자로 표현한다.

격자의 한 칸(cell)은 0 = 빈칸, 1 = 부재 A, 2 = 부재 B.
좌표: x, y = 수평, z = 위. 한 칸의 크기는 cell_mm (기본 10mm).
"""
from dataclasses import dataclass, field
import numpy as np

EMPTY, A, B = 0, 1, 2

# 6방향: 이름, 벡터
DIRS = {
    "+x": (1, 0, 0), "-x": (-1, 0, 0),
    "+y": (0, 1, 0), "-y": (0, -1, 0),
    "+z": (0, 0, 1), "-z": (0, 0, -1),
}
DIR_KO = {"+x": "x+ 방향", "-x": "x− 방향", "+y": "y+ 방향",
          "-y": "y− 방향", "+z": "위로", "-z": "아래로"}


@dataclass
class Joint:
    key: str                      # 영문 식별자
    name: str                     # 한글 이름
    kind: str                     # "맞춤"(T·L·十) 또는 "이음"(일자)
    grid: np.ndarray              # (nx, ny, nz) uint8
    axis_a: str                   # 부재 A의 길이 방향(결 방향) "x"/"y"/"z"
    axis_b: str
    cell_mm: float = 10.0
    note: str = ""
    meta: dict = field(default_factory=dict)

    @property
    def shape(self):
        return self.grid.shape

    def part(self, label):
        return self.grid == label


def new_grid(nx, ny, nz):
    return np.zeros((nx, ny, nz), dtype=np.uint8)


def box(g, label, x0, x1, y0, y1, z0, z1):
    """[x0,x1) × [y0,y1) × [z0,z1) 칸을 label로 채운다 (격자 밖은 잘라냄)."""
    nx, ny, nz = g.shape
    x0, x1 = max(0, int(x0)), min(nx, int(x1))
    y0, y1 = max(0, int(y0)), min(ny, int(y1))
    z0, z1 = max(0, int(z0)), min(nz, int(z1))
    if x0 < x1 and y0 < y1 and z0 < z1:
        g[x0:x1, y0:y1, z0:z1] = label


def trapezoid_xy(g, label, axis, a0, a1, w0, w1, c, z0, z1, mask_from=None):
    """평면 사다리꼴(주먹장 모양).

    axis="x": x가 a0→a1로 가면서 폭(y 방향)이 w0→w1로 선형 변화, 중심 y=c.
    axis="y": y가 a0→a1로 가면서 폭(x 방향)이 w0→w1, 중심 x=c.
    a0 > a1 이어도 된다(뒤쪽으로 넓어지는 경우).
    """
    lo, hi = sorted((a0, a1))
    n = hi - lo
    for i in range(n):
        a = lo + i
        t = (a + 0.5 - a0) / (a1 - a0)
        w = w0 + (w1 - w0) * t
        s0 = int(round(c - w / 2))
        s1 = int(round(c + w / 2))
        if axis == "x":
            box(g, label, a, a + 1, s0, s1, z0, z1)
        else:
            box(g, label, s0, s1, a, a + 1, z0, z1)
