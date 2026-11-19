"""M1: 전통 결구 라이브러리 → 검사 → 확인 그림 + 3dm + 보고표."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from joinery import library, check, render, export3dm  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "m1_out")
os.makedirs(OUT, exist_ok=True)
os.makedirs(os.path.join(OUT, "결구별"), exist_ok=True)

joints = library.build_all()
results = [check.evaluate(j) for j in joints]

render.joint_sheet(joints, results, os.path.join(OUT, "전통결구_라이브러리_검사.png"))
for k, (j, r) in enumerate(zip(joints, results), 1):
    render.joint_pair(j, r, os.path.join(OUT, "결구별", f"{k:02d}_{j.name}.png"))
export3dm.export(joints, results, os.path.join(OUT, "전통결구_라이브러리_조립.3dm"))
export3dm.export(joints, results, os.path.join(OUT, "전통결구_라이브러리_분해.3dm"), explode=True)

rows = []
for j, r in zip(joints, results):
    rows.append({"이름": j.name, "종류": j.kind, "빠지는방향": r["escape"], "판정": r["lock"],
                 "얇은살_A": round(r["thin_A"], 3), "얇은살_B": round(r["thin_B"], 3),
                 "짧은결_A": round(r["short_grain_A"], 3), "짧은결_B": round(r["short_grain_B"], 3),
                 "점수": r["score"], "설명": j.note})
with open(os.path.join(OUT, "검사결과.json"), "w", encoding="utf-8") as f:
    json.dump(rows, f, ensure_ascii=False, indent=1)
for row in rows:
    print(row["이름"], row["빠지는방향"], row["점수"])
