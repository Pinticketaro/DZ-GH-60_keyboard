"""Fusion 360で編集できるソリッド（STEP）を部品ごとに書き出す（CadQuery / OpenCascade）。

STLは三角形の集まりで編集しにくいが、STEPは面・辺・円・スプラインを持つソリッドなので、
Fusionで開くと「押し出し／引き込み」「フィレット」「穴」などの直接編集ができる。
座標は図面・DXFと同じ：外形の左下が原点、X＝右、Y＝奥、Z＝上（ボトムプレートの下面＝0）。単位mm。

出力: case/step/<部品>_<ver>.step と、全部入りの assembly_<ver>.step
使い方: python3 tools/export_step.py
"""
import math
import os
import sys

import cadquery as cq
from cadquery import Vector

sys.path.insert(0, os.path.dirname(__file__))
import gen_case as g
import build3d as b3
import fusion_drawings as fd

OUT = os.path.join(g.ROOT, "case/step")


# ---------- 2D → ワイヤ（直線はそのまま、細かい点が続く所＝角のカーブはスプライン）
def wire_from_pts(pts, seg_long=1.2):
    P = [Vector(x, y, 0) for x, y in pts]
    # 重複点を除く
    Q = [P[0]]
    for p in P[1:]:
        if (p - Q[-1]).Length > 1e-4:
            Q.append(p)
    if (Q[0] - Q[-1]).Length < 1e-4:
        Q.pop()
    n = len(Q)
    long_seg = [(Q[(i + 1) % n] - Q[i]).Length > seg_long for i in range(n)]
    if all(long_seg) or not any(long_seg):
        if all(long_seg):
            return cq.Wire.makePolygon(Q, close=True)
        return cq.Wire.assembleEdges([cq.Edge.makeSpline(Q + [Q[0]], periodic=False)])
    # 長い辺から始まるように回す
    k = long_seg.index(True)
    Q = Q[k:] + Q[:k]
    long_seg = long_seg[k:] + long_seg[:k]
    edges = []
    i = 0
    while i < n:
        if long_seg[i]:
            edges.append(cq.Edge.makeLine(Q[i], Q[(i + 1) % n]))
            i += 1
        else:
            j = i
            run = [Q[i]]
            while j < n and not long_seg[j]:
                run.append(Q[(j + 1) % n])
                j += 1
            if len(run) == 2:
                edges.append(cq.Edge.makeLine(run[0], run[1]))
            else:
                edges.append(cq.Edge.makeSpline(run))
            i = j
    return cq.Wire.assembleEdges(edges)


def circle_wire(c, d):
    return cq.Wire.makeCircle(d / 2, Vector(c[0], c[1], 0), Vector(0, 0, 1))


def plate(outer, holes, z0, t):
    """外形と内側の抜き（ワイヤ）からZ=z0〜z0+tの板。"""
    face = cq.Face.makeFromWires(outer, holes)
    return cq.Solid.extrudeLinear(face, Vector(0, 0, t)).translate(Vector(0, 0, z0))


def box(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, Vector(x0, y0, z0))


def cyl(c, d, z0, z1):
    return cq.Solid.makeCylinder(d / 2, z1 - z0, Vector(c[0], c[1], z0), Vector(0, 0, 1))


def hex_prism(c, af, z0, z1, rot=0.0):
    rr = af / math.sqrt(3)
    pts = [Vector(c[0] + rr * math.cos(math.radians(60 * k + rot)), c[1] + rr * math.sin(math.radians(60 * k + rot)), 0) for k in range(6)]
    face = cq.Face.makeFromWires(cq.Wire.makePolygon(pts, close=True))
    return cq.Solid.extrudeLinear(face, Vector(0, 0, z1 - z0)).translate(Vector(0, 0, z0))


def build():
    D = fd.data()
    z = b3.z_levels()
    outer = wire_from_pts(D["outer"])
    hole_w = [circle_wire(c, d) for c, d in D["holes"]]
    parts = {}
    parts["top_plate"] = plate(outer, hole_w + [cq.Wire.makePolygon([Vector(x, y, 0) for x, y in p], close=True) for p in D["cuts"]],
                               z["st1"], g.TOP_T)
    parts["stiffener"] = plate(wire_from_pts(D["outer"]), [circle_wire(c, d) for c, d in D["holes"]] +
                               [wire_from_pts(p, seg_long=0.05) for p in D["stiff"]], z["fr1"], g.STIFF_T)
    parts["bottom_plate"] = plate(wire_from_pts(D["outer"]), [circle_wire(c, d) for c, d in D["holes"]], z["bot0"], g.BOTTOM_T)

    # 枠
    fo = wire_from_pts(D["frame_outer"])
    fi = wire_from_pts(D["frame_inner"])
    frame = plate(fo, [fi] + [circle_wire(c, d) for c, d in D["holes"]], z["bot1"], g.FRAME_H)
    ux = g.USB_X - fd.OX0
    frame = frame.cut(box(ux - g.USB_W / 2, ux + g.USB_W / 2, g.OUTER_H - g.WALL - 1, g.OUTER_H + 1, z["bot1"] - 1, z["fr1"] + 1))
    xs = g.SPLIT_X - fd.OX0
    big = 1000
    left = frame.intersect(box(-big, xs, -big, big, -big, big))
    right = frame.intersect(box(xs, big, -big, big, -big, big))
    zb, top = z["bot1"], z["fr1"]
    if g.JOINT == "tongue_vbolt":
        c = g.TONGUE_CLEAR
        for ycp in g.joint_wall_y():
            yc = fd.T((0, ycp))[1]
            bxp = (xs + g.JB_X, yc)
            tongue = box(xs - 0.5, xs + g.TONGUE_L, yc - g.TONGUE_W / 2, yc + g.TONGUE_W / 2, zb, zb + g.TONGUE_T)
            mortise = box(xs - 0.01, xs + g.TONGUE_L + c, yc - g.TONGUE_W / 2 - c, yc + g.TONGUE_W / 2 + c, zb - 1, zb + g.TONGUE_T + c)
            hole = cyl(bxp, g.HOLE_D, zb - 1, top + 1)
            cb = cyl(bxp, g.JB_CB_D, top - g.JB_CB_DEPTH, top + 1)
            nut = hex_prism(bxp, g.NUT_POCKET_AF, zb - 1, zb + g.JB_NUT_DEPTH)
            left = left.fuse(tongue).clean().cut(hole).cut(nut)
            right = right.cut(mortise).cut(hole).cut(cb)
    parts["frame_left"] = left
    parts["frame_right"] = right

    # 足（4本とも同じ形）
    feet = []
    fh = g.feet()[1]
    for b in D["bars"]:
        (ax_, ay_), (bx_, by_) = b["holes"]
        span = abs(bx_ - ax_)
        cx, cy = b["c"]
        w = g.RIB_W
        sk = cq.Workplane("XY").center(cx, cy).slot2D(span + w, w).extrude(fh).translate((0, 0, -fh))
        body = sk.val()
        for h in b["holes"]:
            body = body.cut(cyl(h, g.HOLE_D, -fh - 1, 1)).cut(hex_prism(h, g.NUT_POCKET_AF, -fh - 1, -g.FOOT_SKIN))
        feet.append(body)
    for i, f in enumerate(feet):
        parts[f"foot_{i + 1}"] = f
    parts["pcb_reference"] = box(*[v for v in (fd.T((0, g.PCB_H))[0], fd.T((g.PCB_W, 0))[0])],
                                 fd.T((0, g.PCB_H))[1], fd.T((0, 0))[1], z["pcb0"], z["pcb1"])
    return parts


COLORS = {"top_plate": (0.85, 0.9, 0.93, 0.6), "stiffener": (0.85, 0.9, 0.93, 0.6), "bottom_plate": (0.85, 0.9, 0.93, 0.6),
          "frame_left": (0.85, 0.83, 0.79, 1), "frame_right": (0.79, 0.76, 0.71, 1), "pcb_reference": (0.15, 0.3, 0.2, 1)}


def main():
    os.makedirs(OUT, exist_ok=True)
    parts = build()
    asm = cq.Assembly(name=f"DZ60_case_{g.VER}")
    for name, s in parts.items():
        assert s.isValid(), f"{name} のソリッドが不正"
        if not name.startswith("foot_") or name == "foot_1":
            fn = "foot" if name == "foot_1" else name
            cq.exporters.export(cq.Workplane().add(s), os.path.join(OUT, f"{fn}_{g.VER}.step"))
        col = COLORS.get(name, (0.8, 0.78, 0.74, 1))
        asm.add(s, name=name, color=cq.Color(*col))
        print(f"{name:14s} 体積 {s.Volume() / 1000:7.2f} cm3  面 {len(s.Faces())}")
    asm.save(os.path.join(OUT, f"assembly_{g.VER}.step"))
    print(OUT)


if __name__ == "__main__":
    main()
