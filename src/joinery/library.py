"""전통 한옥 결구 라이브러리 (복셀로 옮긴 것).

치수는 칸 수. 기본 단면 = 폭 12칸 × 높이 15칸 (1칸 10mm → 120×150mm).
비율은 전통 목구조 관례(장부 두께 ≈ 부재 폭의 1/3, 주먹장 목 ≈ 1/3,
머리 ≈ 1/2 등)를 따랐고, 실제 치목 치수와는 다를 수 있다.
"""
from .grid import Joint, new_grid, box, trapezoid_xy, A, B

S = 2              # 해상도 배율: 1칸 = 10mm / S
CELL = 10.0 / S
W, H = 12 * S, 15 * S   # 단면 폭, 높이 (칸) = 120×150mm
L = 18 * S              # 부재가 접합부 밖으로 나와 있는 길이 (칸)


def _t_layout(w=W, h=H, l=L):
    """T자: A는 x 방향으로 가로지르고, B는 +y 쪽에서 A의 옆면으로 들어온다."""
    nx = l * 2 + w
    ny = w + l
    g = new_grid(nx, ny, h)
    box(g, A, 0, nx, 0, w, 0, h)          # A (y: 0~w)
    bx0 = l                               # B의 x 시작
    box(g, B, bx0, bx0 + w, w, ny, 0, h)  # B (y: w~)
    return g, bx0


def tenon_t():
    """장부맞춤 (통장부): B 끝의 장부가 A의 장부구멍을 관통."""
    g, bx = _t_layout()
    t = W // 3
    box(g, B, bx + t, bx + 2 * t, 0, W, 2 * S, H - 2 * S)
    return Joint("tenon_t", "장부맞춤", "맞춤", g, "x", "y", cell_mm=CELL,
                 note="장부 두께 = 폭의 1/3, 관통. 뒤로만 빠진다 → 산지(핀)로 고정.")


def shouldered_tenon_t():
    """턱장부맞춤: 장부 + 아랫면 턱(걸침)으로 하중을 받는다."""
    g, bx = _t_layout()
    t = W // 3
    # 턱: B 아랫부분 1/3 높이가 A 안으로 3칸 들어가 걸침
    box(g, B, bx, bx + W, W - 3 * S, W, 0, H // 3)
    # 장부: 가운데 1/3 폭, 턱 위쪽
    box(g, B, bx + t, bx + 2 * t, 2 * S, W, H // 3, H - 2 * S)
    return Joint("shouldered_tenon_t", "턱장부맞춤", "맞춤", g, "x", "y", cell_mm=CELL,
                 note="아래 턱이 하중을 받고 장부는 비틀림을 잡는다.")


def dovetail_t():
    """주먹장맞춤: 위에서 내려 꽂는 주먹장. 위로만 빠진다."""
    g, bx = _t_layout()
    d = W * 2 // 3                        # 주먹장 깊이
    neck, head = W / 3, W * 0.62
    z0 = H // 3                           # 아래 1/3은 A가 받친다
    trapezoid_xy(g, B, "y", W, W - d, neck, head, bx + W / 2, z0, H)
    # 주먹장 주변 B 몸통 쪽은 빈 공간이 아니라 A가 그대로 (위 trapezoid가 덮어씀)
    return Joint("dovetail_t", "주먹장맞춤", "맞춤", g, "x", "y", cell_mm=CELL,
                 note="목이 좁고 머리가 넓어 당겨도 안 빠진다. 위에서 내려 끼움.")


def half_lap_cross():
    """반턱맞춤 (십자): 서로 절반씩 따내 겹친다."""
    n = W + 2 * L
    g = new_grid(n, n, H)
    c0 = L
    box(g, A, 0, n, c0, c0 + W, 0, H)
    box(g, B, c0, c0 + W, 0, n, 0, H)
    box(g, A, c0, c0 + W, c0, c0 + W, 0, H // 2)   # 아래 절반 = A
    box(g, B, c0, c0 + W, c0, c0 + W, H // 2, H)   # 위 절반 = B
    return Joint("half_lap_cross", "반턱맞춤(십자)", "맞춤", g, "x", "y", cell_mm=CELL,
                 note="가장 단순한 십자 맞춤. 위로 들면 빠진다.")


def dovetail_lap_t():
    """반턱 주먹장맞춤: B의 위 절반이 주먹장 모양으로 A 위에 걸친다."""
    g, bx = _t_layout()
    neck, head = W * 0.45, W * 0.8
    trapezoid_xy(g, B, "y", W, S, neck, head, bx + W / 2, H // 2, H)
    return Joint("dovetail_lap_t", "반턱주먹장맞춤", "맞춤", g, "x", "y", cell_mm=CELL,
                 note="장선·멍에를 걸 때 쓰는 방식. 위에서 내려 끼운다.")


def _splice_layout(w=W, h=H, l=L, overlap=10 * S):
    """일자 이음: A는 x 0~m, B는 m~끝. overlap 구간이 맞물리는 부분."""
    n = 2 * l + overlap
    g = new_grid(n, w, h)
    m = l + overlap // 2
    box(g, A, 0, m, 0, w, 0, h)
    box(g, B, m, n, 0, w, 0, h)
    return g, m


def dovetail_splice():
    """주먹장이음: 평면 주먹장, 높이 전체. 위·아래로만 움직인다."""
    g, m = _splice_layout()
    d = 7 * S
    trapezoid_xy(g, B, "x", m, m - d, W / 3, W * 0.62, W / 2, 0, H)
    return Joint("dovetail_splice", "주먹장이음", "이음", g, "x", "x", cell_mm=CELL,
                 note="잡아당겨도 안 빠지지만 위아래로는 움직인다 → 위 부재 무게로 누른다.")


def grasshopper_splice():
    """메뚜기장이음: 목이 길고 머리가 넓은 장부를 위 절반에만 두고 위에서 내려 끼운다."""
    g, m = _splice_layout(overlap=14 * S)
    d = 9 * S
    z0 = H // 2 - S
    # 목(곧은 부분) + 머리(사다리꼴)
    box(g, B, m - 4 * S, m, int(W / 2 - 2 * S), int(W / 2 + 2 * S), z0, H)
    trapezoid_xy(g, B, "x", m - 4 * S, m - d, W * 0.34, W * 0.7, W / 2, z0, H)
    # 아래 절반: B 쪽으로 A가 턱으로 받침 (하중 전달)
    box(g, A, m, m + 3 * S, 0, W, 0, z0)
    return Joint("grasshopper_splice", "메뚜기장이음", "이음", g, "x", "x", cell_mm=CELL,
                 note="도리·장혀 이음. 메뚜기 머리 모양 장부 + 아래 받침턱. 위에서 내려 끼움.")


def half_lap_splice():
    """반턱이음: 절반씩 겹치기만 한 이음. 비교용(약한 예)."""
    g, m = _splice_layout()
    box(g, A, m - 5 * S, m + 5 * S, 0, W, 0, H // 2)
    box(g, B, m - 5 * S, m + 5 * S, 0, W, H // 2, H)
    return Joint("half_lap_splice", "반턱이음", "이음", g, "x", "x", cell_mm=CELL,
                 note="위로도, 옆(길이 방향)으로도 빠진다 → 못·산지 없이는 약하다. 비교용.")


def saddle_post_beam():
    """안장맞춤(사개 기둥머리 + 보): 기둥머리를 네 갈래로 따내고 보를 내려 앉힌다."""
    pw = 14 * S                                  # 기둥 단면 14×14
    ph = 26 * S                                  # 기둥 높이(격자 안)
    bw, bh = W, H                            # 보 단면
    nx = pw + 2 * L
    ny = pw
    nz = ph + 6 * S
    g = new_grid(nx, ny, nz)
    px0 = L
    seat = ph - 10 * S                           # 보 밑면 높이
    box(g, A, px0, px0 + pw, 0, pw, 0, ph)                    # 기둥
    y0 = (pw - bw) // 2
    box(g, B, 0, nx, y0, y0 + bw, seat, seat + bh)            # 보
    # 기둥 귀(사개): 보 양옆 바깥으로 남는 기둥 살 — 보 폭보다 바깥이라 이미 A.
    # 보 아랫면을 기둥 귀 사이에 끼우기 위해 보 양옆을 2칸씩 따낸다(턱).
    box(g, A, px0, px0 + pw, y0, y0 + 2 * S, seat, ph)
    box(g, A, px0, px0 + pw, y0 + bw - 2 * S, y0 + bw, seat, ph)
    return Joint("saddle_post_beam", "안장맞춤(기둥-보)", "맞춤", g, "z", "x", cell_mm=CELL,
                 note="기둥머리를 갈라 보를 내려 앉힌다. 보는 위로만 빠진다.")


ALL = [tenon_t, shouldered_tenon_t, dovetail_t, half_lap_cross, dovetail_lap_t,
       dovetail_splice, grasshopper_splice, half_lap_splice, saddle_post_beam]


def build_all():
    return [f() for f in ALL]
