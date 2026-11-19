"""웹앱(GitHub Pages) 묶기.

python tools/build_web.py _site [--pyodide-dir 풀어둔/pyodide] [--rhino3dm-dir node_modules/rhino3dm]

- web/ 의 화면 파일, src/ 코드, examples/ 예제 입력을 복사하고 manifest.json 을 만든다.
- 브라우저 속 Python(Pyodide)은 필요한 꾸러미만 골라 같이 올린다(외부 CDN에 기대지 않음).
- 라이노 3dm 은 rhino3dm.js, DXF 는 ezdxf(순수 파이썬 휠)로 만든다.
"""
import argparse
import io
import json
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYODIDE_VER = "314.0.8"
RHINO3DM_VER = "8.35.0"
EZDXF_VER = "1.4.3"
PACKAGES = ["numpy", "scipy", "matplotlib", "shapely", "micropip", "pyparsing", "fonttools", "typing-extensions"]
CORE = ["pyodide.js", "pyodide.mjs", "pyodide.asm.mjs", "pyodide.asm.wasm", "python_stdlib.zip",
        "pyodide-lock.json", "package.json"]


def fetch(url):
    print("내려받는 중", url, flush=True)
    with urllib.request.urlopen(url) as r:
        return r.read()


def closure(lock):
    need, stack = set(), list(PACKAGES)
    while stack:
        p = stack.pop()
        if p in need:
            continue
        need.add(p)
        stack += lock["packages"][p]["depends"]
    return [lock["packages"][p]["file_name"] for p in sorted(need)]


def pyodide(dst, src_dir):
    dst.mkdir(parents=True, exist_ok=True)
    if src_dir:
        src = Path(src_dir)
        lock = json.loads((src / "pyodide-lock.json").read_text())
        for f in CORE + closure(lock):
            shutil.copy(src / f, dst / f)
        return
    url = f"https://github.com/pyodide/pyodide/releases/download/{PYODIDE_VER}/pyodide-{PYODIDE_VER}.tar.bz2"
    tmp = ROOT / ".cache" / f"pyodide-{PYODIDE_VER}.tar.bz2"
    if not tmp.exists():
        tmp.parent.mkdir(exist_ok=True)
        tmp.write_bytes(fetch(url))
    with tarfile.open(tmp, "r:bz2") as t:
        lock = json.load(t.extractfile("pyodide/pyodide-lock.json"))
        want = {"pyodide/" + f for f in CORE + closure(lock)}
        for m in t:
            if m.name in want:
                (dst / Path(m.name).name).write_bytes(t.extractfile(m).read())


def rhino(dst, src_dir):
    dst.mkdir(parents=True, exist_ok=True)
    if src_dir:
        for f in ("rhino3dm.module.min.js", "rhino3dm.wasm"):
            shutil.copy(Path(src_dir) / f, dst / f)
        return
    data = fetch(f"https://registry.npmjs.org/rhino3dm/-/rhino3dm-{RHINO3DM_VER}.tgz")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as t:
        for f in ("rhino3dm.module.min.js", "rhino3dm.wasm"):
            (dst / f).write_bytes(t.extractfile("package/" + f).read())


def ezdxf(dst, wheel):
    dst.mkdir(parents=True, exist_ok=True)
    if wheel:
        shutil.copy(wheel, dst)
    else:
        subprocess.run([sys.executable, "-m", "pip", "download", "--no-deps", "--only-binary=:all:",
                        "--platform", "any", "--python-version", "3.14", "-d", str(dst),
                        f"ezdxf=={EZDXF_VER}"], check=True)
    return next(dst.glob("ezdxf-*.whl"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--pyodide-dir")
    ap.add_argument("--rhino3dm-dir")
    ap.add_argument("--ezdxf-wheel")
    a = ap.parse_args()
    out = Path(a.out)
    shutil.rmtree(out, ignore_errors=True)
    shutil.copytree(ROOT / "web", out)
    files = ["py/rhino3dm.py"]
    for d in ("src", "examples"):
        shutil.copytree(ROOT / d, out / d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        files += [p.relative_to(out).as_posix() for p in sorted((out / d).rglob("*")) if p.is_file()]
    pyodide(out / "vendor" / "pyodide", a.pyodide_dir)
    rhino(out / "vendor" / "rhino3dm", a.rhino3dm_dir)
    whl = ezdxf(out / "vendor" / "wheels", a.ezdxf_wheel)
    manifest = {"files": files, "ezdxf": whl.relative_to(out).as_posix()}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / ".nojekyll").write_text("")
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"완료: {out} ({size / 1e6:.0f} MB, 코드 파일 {len(files)}개)")


if __name__ == "__main__":
    main()
