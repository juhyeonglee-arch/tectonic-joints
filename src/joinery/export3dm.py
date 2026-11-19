"""Rhino 3dm 내보내기: 결구마다 레이어 '결구::이름::A/B', 단위 mm."""
import numpy as np
import rhino3dm as r3

from .grid import A, B
from .mesh import exposed_quads


def _mesh(mask, cell, offset):
    m = r3.Mesh()
    for c, _ in exposed_quads(mask, cell, offset):
        i0 = len(m.Vertices)
        for p in c:
            m.Vertices.Add(float(p[0]), float(p[1]), float(p[2]))
        m.Faces.AddFace(i0, i0 + 1, i0 + 2, i0 + 3)
    m.Normals.ComputeNormals()
    m.Compact()
    return m


def _layer(model, name, color, parent=None):
    ly = r3.Layer()
    ly.Name = name
    ly.Color = color
    if parent is not None:
        ly.ParentLayerId = parent.Id
    idx = model.Layers.Add(ly)
    return model.Layers[idx]


def export(joints, results, path, spacing_mm=150.0, explode=False):
    model = r3.File3dm()
    model.Settings.ModelUnitSystem = r3.UnitSystem.Millimeters
    root = _layer(model, "결구", (40, 40, 40, 255))
    x = 0.0
    for j, r in zip(joints, results):
        c = j.cell_mm
        jl = _layer(model, j.name, (40, 40, 40, 255), root)
        la = _layer(model, "A_고정", (200, 200, 200, 255), jl)
        lb = _layer(model, "B_끼움", (61, 120, 217, 255), jl)
        offB = np.zeros(3)
        if explode and r["escape"]:
            from .grid import DIRS
            offB = np.array(DIRS[r["escape"][0]], float) * max(j.shape) * c * 0.45
        for lab, ly, off in ((A, la, np.zeros(3)), (B, lb, offB)):
            at = r3.ObjectAttributes()
            at.LayerIndex = ly.Index
            at.Name = f"{j.name}_{'A' if lab == A else 'B'}"
            model.Objects.AddMesh(_mesh(j.grid == lab, c, np.array([x, 0, 0]) + off), at)
        # 이름 표시
        at = r3.ObjectAttributes()
        at.LayerIndex = jl.Index
        model.Objects.AddTextDot(f"{j.name} ({', '.join(r['escape']) or '-'})",
                                 r3.Point3d(x, -60, 0), at)
        x += j.shape[0] * c + spacing_mm
    model.Write(path, 7)


def export_slabs(items, path, spacing_mm=200.0):
    """생성 결구를 층별 솔리드(Extrusion)로. items = [(이름, joint, slabs)]."""
    from .geom import _polys
    model = r3.File3dm()
    model.Settings.ModelUnitSystem = r3.UnitSystem.Millimeters
    root = _layer(model, "생성결구", (40, 40, 40, 255))
    x = 0.0
    for name, j, sl in items:
        jl = _layer(model, name, (40, 40, 40, 255), root)
        la = _layer(model, "A_고정", (200, 200, 200, 255), jl)
        lb = _layer(model, "B_끼움", (61, 120, 217, 255), jl)
        width = j.grid.shape[0] * j.cell_mm
        for z0, z1, gA, gB in sl:
            for g, ly, tag in ((gA, la, "A"), (gB, lb, "B")):
                for poly in _polys(g):
                    pts = [r3.Point3d(px + x, py, z0) for px, py in poly.exterior.coords]
                    crv = r3.PolylineCurve(pts)
                    ex = r3.Extrusion.Create(crv, -(z1 - z0), True)
                    if ex is None:
                        continue
                    at = r3.ObjectAttributes()
                    at.LayerIndex = ly.Index
                    at.Name = f"{name}_{tag}_z{z0:.0f}-{z1:.0f}"
                    model.Objects.AddExtrusion(ex, at)
        at = r3.ObjectAttributes()
        at.LayerIndex = jl.Index
        model.Objects.AddTextDot(name, r3.Point3d(x + width / 2, -80, 0), at)
        x += width + spacing_mm
    model.Write(path, 7)
