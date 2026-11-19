"""시험 결과 폴더의 대표 그림을 한 장(확인그림.png)으로 모은다. PR 확인용.

python tools/contact_sheet.py <시험결과폴더>
"""
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / "src" / "joinery" / "fonts" / "PretendardVariable.ttf"
PICKS = [
    "m1_전통결구/전통결구_라이브러리_검사.png",
    "node3_세부재모서리/세부재모서리_드러냄.png",
    "node3_세부재모서리/세부재모서리_숨김.png",
    "m2_생성후보/후보_직교_90도.png",
    "m3_레이저적층_기본_3mm/1대1/드러냄_R/조립순서도.png",
    "m3_레이저적층_기본_3mm/1대1/숨김_H/조립순서도.png",
    "m3_레이저적층_기본_3mm/1대1/드러냄_R/배치_미리보기.png",
    "m3_레이저적층_기본_3mm/공차시험편/공차시험편.png",
]


def main(d):
    d = Path(d)
    found = [(p, d / p) for p in PICKS if (d / p).exists()]
    if not found:
        print("모을 그림이 없음")
        return
    if FONT.exists():
        font_manager.fontManager.addfont(str(FONT))
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(FONT)).get_name()
    cols = 2
    rows = (len(found) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 9, rows * 6.5), facecolor="white")
    for ax in axes.flat:
        ax.axis("off")
    for ax, (name, path) in zip(axes.flat, found):
        ax.imshow(plt.imread(str(path)))
        ax.set_title(name, fontsize=11, color="#111", loc="left")
    fig.tight_layout()
    out = d / "확인그림.png"
    fig.savefig(out, dpi=80, facecolor="white")
    print(out, os.path.getsize(out))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "test-output")
