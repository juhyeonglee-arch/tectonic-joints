/* 계산 일꾼: 브라우저 안의 Python(Pyodide)으로 src/run_m3.py 를 그대로 돌린다. */
import { loadPyodide } from "./vendor/pyodide/pyodide.mjs";
import rhino3dm from "./vendor/rhino3dm/rhino3dm.module.min.js";

let py = null;
const say = (msg) => postMessage({ type: "log", msg });

async function boot() {
  const t0 = performance.now();
  say("Python 불러오는 중…");
  py = await loadPyodide({ indexURL: new URL("./vendor/pyodide/", import.meta.url).href });
  say("계산 꾸러미 불러오는 중 (numpy, scipy, shapely, matplotlib)…");
  await py.loadPackage(["numpy", "scipy", "matplotlib", "shapely", "micropip", "pyparsing", "fonttools", "typing-extensions"]);
  const manifest = await (await fetch(new URL("./manifest.json", import.meta.url))).json();
  const micropip = py.pyimport("micropip");
  await micropip.install(new URL("./" + manifest.ezdxf, import.meta.url).href, { deps: false });
  say("라이노 3dm 모듈 불러오는 중…");
  self.rhino = await rhino3dm({ locateFile: (f) => new URL("./vendor/rhino3dm/" + f, import.meta.url).href });
  say("결구 생성기 코드 불러오는 중…");
  for (const f of manifest.files) {
    const buf = new Uint8Array(await (await fetch(new URL("./" + f, import.meta.url))).arrayBuffer());
    const dest = "/app/" + f;
    py.FS.mkdirTree(dest.slice(0, dest.lastIndexOf("/")));
    py.FS.writeFile(dest, buf);
  }
  py.runPython(`
import sys, os
sys.path[:0] = ["/app/py", "/app/src"]
os.environ["MPLBACKEND"] = "Agg"
`);
  say(`준비 완료 (${((performance.now() - t0) / 1000).toFixed(0)}초)`);
  postMessage({ type: "ready" });
}

async function run(p) {
  const t0 = performance.now();
  say("판으로 썰고 DXF 만드는 중… (보통 30초~2분)");
  if (p.candidates) py.FS.writeFile("/app/user_candidates.json", new TextEncoder().encode(p.candidates));
  py.globals.set("P", py.toPy(p));
  const res = py.runPython(`
import os, sys, io, json, runpy, zipfile, shutil
from pathlib import Path
out = Path("/tmp/m3_out"); shutil.rmtree(out, ignore_errors=True)
cand = "/app/user_candidates.json" if P.get("candidates") else "/app/examples/node3_후보목록.json"
for k in ("M3_T", "M3_KERF", "M3_CLEAR", "M3_PIN", "M3_BED", "M3_SCALES"):
    os.environ[k] = str(P[k])
sys.argv = ["run_m3.py", str(out), cand]
runpy.run_path("/app/src/run_m3.py", run_name="__main__")
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
    for f in sorted(out.rglob("*")):
        if f.is_file():
            z.write(f, "레이저적층/" + str(f.relative_to(out)))
imgs = [(str(f.relative_to(out)), f.read_bytes()) for f in sorted(out.rglob("*.png"))]
rep = (out / "출력보고.json").read_text(encoding="utf-8")
(buf.getvalue(), imgs, rep)
`);
  const [zip, imgs, rep] = res.toJs({ create_proxies: false });
  res.destroy();
  const images = imgs.map(([name, b]) => ({ name, data: b }));
  postMessage({ type: "done", zip, images, report: JSON.parse(rep),
                secs: (performance.now() - t0) / 1000 });
}

onmessage = async (e) => {
  try {
    if (e.data.type === "boot") await boot();
    else if (e.data.type === "run") await run(e.data.params);
  } catch (err) {
    postMessage({ type: "error", msg: String(err && err.message || err) });
  }
};
