"""브라우저(Pyodide)용 rhino3dm 대역.

이 프로그램이 쓰는 rhino3dm(파이썬) 기능만, 같은 이름으로 rhino3dm.js에 넘긴다.
그래서 src/ 코드는 고치지 않고 브라우저에서도 같은 .3dm을 만든다.
"""
from js import Object, rhino as _rh
from pyodide.ffi import to_js


def _obj(d):
    return to_js(d, dict_converter=Object.fromEntries)


class UnitSystem:
    Millimeters = _rh.UnitSystem.Millimeters


class Point3d:
    def __init__(self, x, y, z):
        self.X, self.Y, self.Z = float(x), float(y), float(z)


class PolylineCurve:
    def __init__(self, pts):
        pl = _rh.Polyline.new(0)
        for p in pts:
            pl.add(p.X, p.Y, p.Z)
        self._js = pl.toPolylineCurve()


class Extrusion:
    def __init__(self, js):
        self._js = js

    @staticmethod
    def Create(curve, height, cap):
        ex = _rh.Extrusion.create(curve._js, float(height), bool(cap))
        return None if ex is None else Extrusion(ex)


class _List(list):
    def Add(self, *a):
        self.append(a)
        return len(self) - 1


class _Faces(list):
    def AddFace(self, *idx):
        self.append(idx)
        return len(self) - 1


class _Normals:
    def ComputeNormals(self):
        return True


class Mesh:
    def __init__(self):
        self.Vertices = _List()
        self.Faces = _Faces()
        self.Normals = _Normals()

    def Compact(self):
        return True

    def _to_js(self):
        m = _rh.Mesh.new()
        vs = m.vertices()
        for x, y, z in self.Vertices:
            vs.add(float(x), float(y), float(z))
        fs = m.faces()
        for f in self.Faces:
            if len(f) == 4:
                fs.addQuadFace(*map(int, f))
            else:
                fs.addTriFace(*map(int, f))
        m.normals().computeNormals()
        m.compact()
        return m


class Layer:
    def __init__(self):
        self.Name = ""
        self.Color = (0, 0, 0, 255)
        self.ParentLayerId = None


class _LayerRef:
    def __init__(self, idx, js):
        self.Index = idx
        self.Id = js.id
        self.Name = js.name


class ObjectAttributes:
    def __init__(self):
        self.LayerIndex = 0
        self.Name = ""


class _Settings:
    def __init__(self, doc):
        self._doc = doc

    @property
    def ModelUnitSystem(self):
        return self._doc.settings().modelUnitSystem

    @ModelUnitSystem.setter
    def ModelUnitSystem(self, v):
        self._doc.settings().modelUnitSystem = v


class _Layers:
    def __init__(self, doc):
        self._doc = doc

    def Add(self, ly):
        js = _rh.Layer.new()
        js.name = ly.Name
        r, g, b, *a = ly.Color
        js.color = _obj({"r": int(r), "g": int(g), "b": int(b), "a": int(a[0]) if a else 255})
        if ly.ParentLayerId is not None:
            js.parentLayerId = ly.ParentLayerId
        return int(self._doc.layers().add(js))

    def __getitem__(self, idx):
        return _LayerRef(idx, self._doc.layers().get(idx))

    def __len__(self):
        return int(self._doc.layers().count)


def _attr(at):
    js = _rh.ObjectAttributes.new()
    if at is not None:
        js.layerIndex = int(at.LayerIndex)
        js.name = at.Name
    return js


class _Objects:
    def __init__(self, doc):
        self._doc = doc
        self._n = 0

    def _add(self, geo, at):
        self._doc.objects().add(geo, _attr(at))
        self._n += 1

    def AddExtrusion(self, ex, at=None):
        self._add(ex._js, at)

    def AddMesh(self, m, at=None):
        self._add(m._to_js(), at)

    def AddTextDot(self, text, pt, at=None):
        self._add(_rh.TextDot.new(text, to_js([pt.X, pt.Y, pt.Z])), at)

    def __len__(self):
        return self._n


class File3dm:
    def __init__(self):
        self._doc = _rh.File3dm.new()
        self.Settings = _Settings(self._doc)
        self.Layers = _Layers(self._doc)
        self.Objects = _Objects(self._doc)

    def Write(self, path, version=7):
        opts = _rh.File3dmWriteOptions.new()
        opts.version = int(version)
        data = self._doc.toByteArrayOptions(opts).to_py()
        with open(path, "wb") as f:
            f.write(bytes(data))
        return True
