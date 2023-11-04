#!/usr/bin/env python3
"""Export the URDF meshes from the SCOBO STEP file, in metres in the base_link frame.

    python3 export_meshes.py [step_file] [output_dir]
"""
import os
import sys

import collada
import numpy as np
import pyfqmr
from OCP.BRep import BRep_Tool
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.IFSelect import IFSelect_RetDone
from OCP.Quantity import Quantity_Color
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDF import TDF_Label, TDF_LabelSequence
from OCP.TDocStd import TDocStd_Document
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS
from OCP.XCAFDoc import XCAFDoc_ColorGen, XCAFDoc_ColorSurf, XCAFDoc_ColorTool, XCAFDoc_DocumentTool

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
DEFAULT_STEP = os.path.join(REPO, "cad", "scobo", "scobo_final.step")
DEFAULT_OUT = os.path.join(HERE, "..", "meshes")

# tessellation: max distance to the surface (mm) and max angle between segments (rad)
LINEAR_DEFLECTION = 1.0
ANGULAR_DEFLECTION = 0.5

# bought-in parts came in as one face per triangle, big ones are thinned
DECIMATE_ABOVE = 3000
DECIMATE_RATIO = 0.35

# edges sharper than this stay sharp, flatter ones are shaded smooth
CREASE_ANGLE = np.radians(35.0)

# parts smaller than this (mm, bounding box diagonal) are left out
MIN_PART_SIZE = 4.0

GREY = (0.35, 0.35, 0.35)  # parts with no colour in the CAD

# sub-assemblies whose parts are grouped one by one, they are named like "Display:1/iPAD:1"
EXPAND = ("Display", "RPLidar")

# part name prefix -> mesh file, first match wins, parts not listed go into lower_body
GROUPS = [
    ("Display:1/iPAD", "display"),
    ("Display:1/MG995 (1)", "display"),  # tilt servo horns
    ("Display:1/MG995 Left", "display"),
    ("Display:1/MG995_Bracket", "display_pan"),
    ("Display:1/MG995", "mg995"),
    ("Display:1/pan-tilt plate", "upper_frame"),  # fixed half of the pan bearing
    ("Display", "display_pan"),
    ("Upper half", "upper_frame"),
    ("Camera", "upper_frame"),  # MLX90640 thermal camera
    ("Banner Green LED", "upper_frame"),
    ("pill_dispenser", "upper_frame"),
    ("GLASS BOWL", "upper_frame"),
    ("Bowl Block", "upper_frame"),
    ("Conveyer", "upper_frame"),
    ("SG30", "sg30"),
    ("RPLidar", "laser"),
    ("Wheel", "wheel"),
]
BOXES = ("LEDLB",)  # UV lamp bars, drawn as boxes in the xacro

# parts used more than once, only this copy is written, centred on its bounding box
INSTANCES = {
    "wheel": "Wheel v2:1",  # front right
    "sg30": "SG30:1",
    "mg995": "Display:1/MG995:1",  # left, the right one is turned by 180 deg
}

# the tablet holder is fused to the pan yoke in the CAD, split it off by position (mm)
YOKE = "Display:1/=>[0:1:1:71]"
HOLDER_X = (368.0, 618.0)
HOLDER_Z_MIN = 1090.0


def label_name(label):
    attr = TDataStd_Name()
    if label.FindAttribute(TDataStd_Name.GetID_s(), attr):
        return attr.Get().ToExtString()
    return ""


class StepReader:
    def __init__(self, path):
        self.doc = TDocStd_Document(TCollection_ExtendedString("doc"))
        reader = STEPCAFControl_Reader()
        reader.SetNameMode(True)
        reader.SetColorMode(True)
        if reader.ReadFile(path) != IFSelect_RetDone:
            sys.exit(f"could not read {path}")
        reader.Transfer(self.doc)
        self.shapes = XCAFDoc_DocumentTool.ShapeTool_s(self.doc.Main())
        self.colours = XCAFDoc_DocumentTool.ColorTool_s(self.doc.Main())

    def colour(self, item):
        # item is a label or a shape, None if it has no colour of its own
        c = Quantity_Color()
        for kind in (XCAFDoc_ColorSurf, XCAFDoc_ColorGen):
            if isinstance(item, TDF_Label):
                found = XCAFDoc_ColorTool.GetColor_s(item, kind, c)
            else:
                found = self.colours.GetColor(item, kind, c)
            if found:
                return (round(c.Red(), 3), round(c.Green(), 3), round(c.Blue(), 3))
        return None

    def parts(self):
        """List of (name, location, [(face, colour)]) for every simple shape."""
        out = []

        def walk(label, loc, name, colour, split):
            kids = TDF_LabelSequence()
            self.shapes.GetComponents_s(label, kids)
            for j in range(1, kids.Length() + 1):
                comp = kids.Value(j)
                ref = TDF_Label()
                sub_loc = loc
                if self.shapes.IsReference_s(comp):
                    self.shapes.GetReferredShape_s(comp, ref)
                    sub_loc = loc.Multiplied(self.shapes.GetLocation_s(comp))
                else:
                    ref = comp
                sub_name = name + label_name(comp) if split else name
                sub_colour = self.colour(comp) or self.colour(ref) or colour
                if self.shapes.IsAssembly_s(ref):
                    expand = split and not name and sub_name.startswith(EXPAND)
                    walk(ref, sub_loc, sub_name + "/" if expand else sub_name,
                         sub_colour, expand)
                else:
                    out.append((sub_name, sub_loc, self.faces(ref, sub_colour)))

        roots = TDF_LabelSequence()
        self.shapes.GetFreeShapes(roots)
        for i in range(1, roots.Length() + 1):
            walk(roots.Value(i), TopLoc_Location(), "", None, True)
        return out

    def faces(self, label, colour):
        shape = self.shapes.GetShape_s(label)
        BRepMesh_IncrementalMesh(shape, LINEAR_DEFLECTION, False, ANGULAR_DEFLECTION, True)
        faces = []
        solids = TopExp_Explorer(shape, TopAbs_SOLID)
        while solids.More():
            solid_colour = self.colour(solids.Current()) or colour
            exp = TopExp_Explorer(solids.Current(), TopAbs_FACE)
            while exp.More():
                face = TopoDS.Face_s(exp.Current())
                faces.append((face, self.colour(face) or solid_colour or GREY))
                exp.Next()
            solids.Next()
        # surface bodies that are not part of a solid
        exp = TopExp_Explorer(shape, TopAbs_FACE, TopAbs_SOLID)
        while exp.More():
            face = TopoDS.Face_s(exp.Current())
            faces.append((face, self.colour(face) or colour or GREY))
            exp.Next()
        return faces


def triangulate(loc, faces):
    """Triangles of one part in CAD mm, as {colour: (verts, tris)}."""
    part_trsf = loc.Transformation()
    out = {}
    for face, colour in faces:
        face_loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, face_loc)
        if tri is None:
            continue
        trsf = part_trsf.Multiplied(face_loc.Transformation())
        flip = face.Orientation() == TopAbs_REVERSED
        v = []
        for k in range(1, tri.NbNodes() + 1):
            p = tri.Node(k).Transformed(trsf)
            v.append((p.X(), p.Y(), p.Z()))
        t = []
        for k in range(1, tri.NbTriangles() + 1):
            a, b, c = tri.Triangle(k).Get()
            t.append((a - 1, c - 1, b - 1) if flip else (a - 1, b - 1, c - 1))
        out.setdefault(colour, []).append((np.array(v), np.array(t)))
    return {c: merge(pieces) for c, pieces in out.items()}


def merge(pieces):
    # pieces are (verts, tris) or (verts, normals, tris), index offsets are fixed up
    start = 0
    arrays = [[] for _ in pieces[0]]
    for piece in pieces:
        for k, a in enumerate(piece[:-1]):
            arrays[k].append(a)
        arrays[-1].append(piece[-1] + start)
        start += len(piece[0])
    return tuple(np.vstack(a) for a in arrays)


def cut(mesh, keep):
    # keep only the triangles where keep is true, drop unused vertices
    v, t = mesh
    used, inv = np.unique(t[keep], return_inverse=True)
    return v[used], inv.reshape(-1, 3)


def weld(v, t):
    # join vertices closer than 1 um
    _, first, inv = np.unique(np.round(v * 1000.0).astype(np.int64), axis=0,
                              return_index=True, return_inverse=True)
    t = inv.reshape(-1)[t]
    t = t[(t[:, 0] != t[:, 1]) & (t[:, 1] != t[:, 2]) & (t[:, 0] != t[:, 2])]
    return v[first], t


def decimate(v, t):
    if len(t) <= DECIMATE_ABOVE:
        return v, t
    simp = pyfqmr.Simplify()
    simp.setMesh(v, t)
    target = max(DECIMATE_ABOVE, int(len(t) * DECIMATE_RATIO))
    simp.simplify_mesh(target_count=target, aggressiveness=7, preserve_border=True, verbose=0)
    v, t, _ = simp.getMesh()
    return v, t


def smooth_normals(v, t):
    """Split vertices along edges sharper than CREASE_ANGLE, smooth normals elsewhere."""
    fn = np.cross(v[t[:, 1]] - v[t[:, 0]], v[t[:, 2]] - v[t[:, 0]])  # length is 2x area
    keep = np.linalg.norm(fn, axis=1) > 1e-9
    t, fn = t[keep], fn[keep]
    unit = fn / np.linalg.norm(fn, axis=1, keepdims=True)
    corner_v = t.reshape(-1)
    corner_f = np.repeat(np.arange(len(t)), 3)
    order = np.argsort(corner_v, kind="stable")
    groups = np.split(order, np.flatnonzero(np.diff(corner_v[order])) + 1)
    cos = np.cos(CREASE_ANGLE)
    normals = np.empty((len(corner_v), 3))
    for g in groups:
        f = corner_f[g]
        # area weighted sum of the faces at this vertex that are close in angle
        normals[g] = ((unit[f] @ unit[f].T) > cos) @ fn[f]
    normals /= np.linalg.norm(normals, axis=1, keepdims=True)
    key = np.column_stack((corner_v, np.round(normals * 100)))
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    return v[corner_v[first]], normals[first], inv.reshape(-1, 3)


def finish(mesh):
    v, t = weld(*mesh)
    return smooth_normals(*decimate(v, t))


def cad_to_robot(points, origin, vector=False):
    # +90 deg yaw: CAD -Y is robot +x, CAD +X is robot +y. mm to m.
    p = points if vector else (points - origin) / 1000.0
    return np.column_stack((-p[:, 1], p[:, 0], p[:, 2]))


def write_dae(path, meshes):
    """meshes is {colour: (verts, normals, tris)} in metres."""
    dae = collada.Collada()
    dae.assetInfo.upaxis = collada.asset.UP_AXIS.Z_UP
    dae.assetInfo.unitmeter = 1.0
    dae.assetInfo.unitname = "meter"
    nodes = []
    for i, (colour, (v, n, t)) in enumerate(sorted(meshes.items())):
        effect = collada.material.Effect(f"effect{i}", [], "phong", diffuse=(*colour, 1.0),
                                         ambient=(*colour, 1.0), specular=(0.2, 0.2, 0.2, 1.0),
                                         shininess=20.0)
        material = collada.material.Material(f"material{i}", f"material{i}", effect)
        dae.effects.append(effect)
        dae.materials.append(material)
        sources = [
            collada.source.FloatSource(f"verts{i}", np.round(v, 4).ravel(), ("X", "Y", "Z")),
            collada.source.FloatSource(f"normals{i}", np.round(n, 2).ravel(), ("X", "Y", "Z")),
        ]
        geom = collada.geometry.Geometry(dae, f"geometry{i}", f"part{i}", sources)
        inputs = collada.source.InputList()
        inputs.addInput(0, "VERTEX", f"#verts{i}")
        inputs.addInput(1, "NORMAL", f"#normals{i}")
        indices = np.repeat(t.ravel(), 2)
        geom.primitives.append(geom.createTriangleSet(indices, inputs, f"mat{i}"))
        dae.geometries.append(geom)
        nodes.append(collada.scene.GeometryNode(
            geom, [collada.scene.MaterialNode(f"mat{i}", material, inputs=[])]))
    scene = collada.scene.Scene("scene", [collada.scene.Node("robot", children=nodes)])
    dae.scenes.append(scene)
    dae.scene = scene
    dae.write(path)


def main():
    step = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_STEP
    out = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUT
    os.makedirs(out, exist_ok=True)

    groups = {}
    verts = {}
    boxes = {}
    seen = set()
    for name, loc, faces in StepReader(step).parts():
        meshes = triangulate(loc, faces)
        if not meshes:
            continue
        v = np.vstack([m[0] for m in meshes.values()])
        if np.linalg.norm(v.max(axis=0) - v.min(axis=0)) < MIN_PART_SIZE:
            continue
        # the display servos and brackets are in the file twice
        key = (tuple(np.round(np.r_[v.min(axis=0), v.max(axis=0)], 1)), len(v))
        if key in seen:
            continue
        seen.add(key)
        verts[name] = np.vstack([verts[name], v]) if name in verts else v
        if name.startswith(BOXES):
            boxes[name] = verts[name]
            continue

        group = next((g for prefix, g in GROUPS if name.startswith(prefix)), "lower_body")
        if group in INSTANCES and name != INSTANCES[group]:
            continue
        for colour, mesh in meshes.items():
            if name == YOKE:
                c = mesh[0][mesh[1]].mean(axis=1)
                holder = ((c[:, 0] > HOLDER_X[0]) & (c[:, 0] < HOLDER_X[1])
                          & (c[:, 2] > HOLDER_Z_MIN))
                groups.setdefault("display", {}).setdefault(colour, []).append(
                    finish(cut(mesh, holder)))
                mesh = cut(mesh, ~holder)
            groups.setdefault(group, {}).setdefault(colour, []).append(finish(mesh))

    def centre(name):
        v = verts[name]
        return (v.min(axis=0) + v.max(axis=0)) / 2

    def robot(p, origin):
        return cad_to_robot(p[None, :], origin)[0]

    # base_link: floor point under the centre of the four wheels
    wheels = [n for n in verts if n.startswith("Wheel")]
    centres = np.array([centre(n) for n in wheels])
    floor = min(verts[n][:, 2].min() for n in wheels)
    origin = np.array([centres[:, 0].mean(), centres[:, 1].mean(), floor])
    wheel = verts[wheels[0]]
    radius = (wheel[:, 2].max() - wheel[:, 2].min()) / 2
    width = wheel[:, 0].max() - wheel[:, 0].min()

    print("base_link origin in CAD (mm): %.1f %.1f %.1f" % tuple(origin))
    print("wheel radius %.4f m, width %.4f m" % (radius / 1000, width / 1000))

    def face_centre(name, axis, side):
        # centre of the vertices within 3 mm of one face of the bounding box
        v = verts[name]
        edge = v[:, axis].max() if side > 0 else v[:, axis].min()
        c = centre(name)
        c[axis] = edge
        near = v[np.abs(v[:, axis] - edge) < 3.0]
        for k in range(3):
            if k != axis:
                c[k] = (near[:, k].min() + near[:, k].max()) / 2
        return c

    pan = centre("Display:1/base (16) (1):1")
    pan[2] = verts["Display:1/base (16) (1):1"][:, 2].min()

    # MAX30102 board lies on the 45 deg face of its wedge, take the centre of its back
    board_name = "MAX30102_MH_ET_LIVE_BOARD_v8:1"
    slope = np.array([0.0, -1.0, 1.0]) / np.sqrt(2)
    board = centre(board_name)
    board += slope * ((verts[board_name] - board) @ slope).min()

    points = {n: centre(n) for n in wheels}
    points.update({n: centre(n) for n in sorted(verts) if n.startswith(("SG30", "Display:1/MG995"))
                   and "_Bracket" not in n})
    points.update({
        "laser scan centre": centre("RPLidar:1/Component17:1"),  # rotating head
        "display pan axis": pan,
        # midpoint of the two MG995 horns
        "display tilt axis": (centre("Display:1/MG995 (1):1") + centre("Display:1/MG995 Left:1")) / 2,
        "display screen centre": centre("Display:1/iPAD:1"),
        "display screen top": face_centre("Display:1/iPAD:1", 2, +1),
        "thermal camera lens": face_centre("Camera:1", 1, -1),
        "ultrasonic face": face_centre("HC-SR04:1", 1, +1),
        "max30102 back": board,
    })
    for name, p in points.items():
        print("  %-30s xyz %+.4f %+.4f %.4f" % (name, *robot(p, origin)))

    for name, v in boxes.items():
        a, b = cad_to_robot(np.array([v.min(axis=0), v.max(axis=0)]), origin)
        c, size = (a + b) / 2, np.abs(b - a)
        print("  %-30s xyz %.4f %.4f %.4f  size %.4f %.4f %.4f" % (name, *c, *size))

    for group, by_colour in groups.items():
        mid = centre(INSTANCES[group]) if group in INSTANCES else origin
        meshes = {}
        for colour, pieces in by_colour.items():
            v, n, t = merge(pieces)
            meshes[colour] = (cad_to_robot(v, mid), cad_to_robot(n, None, vector=True), t)
        path = os.path.join(out, group + ".dae")
        write_dae(path, meshes)
        v = np.vstack([m[0] for m in meshes.values()])
        lo, hi = v.min(axis=0), v.max(axis=0)
        faces = sum(len(m[2]) for m in meshes.values())
        print("%-12s %2d colours %6d faces %6.0f kB  x %+.3f..%+.3f  y %+.3f..%+.3f  z %+.3f..%+.3f"
              % (group, len(meshes), faces, os.path.getsize(path) / 1024,
                 lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]))


if __name__ == "__main__":
    main()
