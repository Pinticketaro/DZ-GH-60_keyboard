"""3Dモデル（STL）と外観プレビューを作る。

出力
  case/stl/frame_left_<ver>.stl, frame_right_<ver>.stl … 枠（PLA）左右。継ぎ目にφ1.9の位置決め穴（1.75mmフィラメントを差す）
  case/stl/feet_<ver>.stl                            … 足（ナット受け）8個を並べたもの
  case/stl/assembly_<ver>.stl                        … 組み立て状態（確認用）
  docs/img/preview_<ver>.png                         … 外観プレビュー（斜め・横）
座標：X右・Y奥・Z上（PCB座標のYを反転）。Z=0はボトムプレートの下面。

使い方: python3 tools/build3d.py
"""
import math
import os
import sys

import numpy as np
import manifold3d as m3
import trimesh
from shapely.geometry import Polygon

sys.path.insert(0, os.path.dirname(__file__))
import gen_case as g

OUT = os.path.join(g.ROOT, "case/stl")
SEG = 48


def flip(pts):
    return [(x, -y) for x, y in pts]


def xs(outer, holes=()):
    polys = [flip(outer)] + [flip(h) for h in holes]
    return m3.CrossSection(polys, m3.FillRule.EvenOdd)


def slab(outer, holes, z0, t):
    return m3.Manifold.extrude(xs(outer, holes), t).translate([0, 0, z0])


def circle(c, d, n=SEG):
    return [(c[0] + d / 2 * math.cos(2 * math.pi * k / n), c[1] + d / 2 * math.sin(2 * math.pi * k / n)) for k in range(n)]


def to_trimesh(mf, color=None):
    mesh = mf.to_mesh()
    tm = trimesh.Trimesh(vertices=np.array(mesh.vert_properties)[:, :3], faces=np.array(mesh.tri_verts), process=False)
    if color is not None:
        tm.visual.face_colors = color
    return tm


def z_levels():
    z = {}
    z["bot0"] = 0.0
    z["bot1"] = g.BOTTOM_T
    z["fr1"] = z["bot1"] + g.FRAME_H
    z["st1"] = z["fr1"] + g.STIFF_T
    z["top1"] = z["st1"] + g.TOP_T
    z["pcb0"] = z["bot1"] + g.UNDER_PCB
    z["pcb1"] = z["pcb0"] + g.PCB_T
    return z


def build_parts():
    z = z_levels()
    hole_polys = [circle(c, g.hole_d(c)) for c in g.holes()]
    parts = {}
    parts["top"] = slab(g.outer_pts(), g.switch_cutouts() + hole_polys, z["st1"], g.TOP_T)
    parts["stiffener"] = slab(g.outer_pts(), g.stiffener_openings() + hole_polys, z["fr1"], g.STIFF_T)
    parts["bottom"] = slab(g.outer_pts(), hole_polys, z["bot0"], g.BOTTOM_T)

    # 枠：外周（少し内側）− 内側 − 穴 − USB切り欠き（全高）
    frame = slab(g.frame_outer_pts(), [g.frame_inner_pts()] + hole_polys, z["bot1"], g.FRAME_H)
    usb = m3.Manifold.cube([g.USB_W, g.WALL + 2, g.FRAME_H + 2]).translate(
        [g.USB_X - g.USB_W / 2, -(g.OY + g.WALL + 1), z["bot1"] - 1])
    frame = frame - usb
    # 分割と位置決め穴（前後の壁の中央、継ぎ目の両側に深さ6mm）
    big = 1000
    left = frame ^ m3.Manifold.cube([big, big, big]).translate([g.SPLIT_X - big, -big / 2, -big / 2])
    right = frame ^ m3.Manifold.cube([big, big, big]).translate([g.SPLIT_X, -big / 2, -big / 2])
    for yw in (g.OY + g.WALL / 2, g.OY + g.OUTER_H - g.WALL / 2):
        pin = m3.Manifold.cylinder(12, 0.95, 0.95, 24).rotate([0, 90, 0]).translate(
            [g.SPLIT_X - 6, -yw, z["bot1"] + g.FRAME_H / 2])
        left, right = left - pin, right - pin
    parts["frame_left"], parts["frame_right"] = left, right

    # 足（ナット受け）：円柱を傾いた机の面で切り、下から六角のナット溝
    fl, h_front, tan, y_front = g.feet()
    feet = []
    for f in fl:
        hmax = f["h"] + g.FOOT_D / 2 * tan + 1
        cyl = m3.Manifold.cylinder(hmax, g.FOOT_D / 2, g.FOOT_D / 2, SEG).translate([f["x"], -f["y"], -hmax])
        # 机の面：z = -(h_front + (y_front - y)·tan)。それより下を取り除く
        ang = math.degrees(math.atan(tan))
        cutter = m3.Manifold.cube([big, big, big]).translate([-big / 2, -big / 2, -big])
        cutter = cutter.rotate([-ang, 0, 0]).translate([0, -y_front, -h_front])
        foot = cyl - cutter
        r = g.NUT_POCKET_AF / math.sqrt(3)
        hexagon = [(f["x"] + r * math.cos(math.radians(60 * k)), f["y"] + r * math.sin(math.radians(60 * k))) for k in range(6)]
        pocket = m3.Manifold.extrude(xs(hexagon), hmax + 1).translate([0, 0, -(hmax + 1) - g.FOOT_SKIN])
        bolt = m3.Manifold.cylinder(hmax + 2, g.HOLE_D / 2, g.HOLE_D / 2, 24).translate([f["x"], -f["y"], -hmax - 1])
        feet.append(foot - pocket - bolt)
    parts["feet"] = feet
    big = 1000

    # 真鍮丸棒（奥側の足）：X方向の円柱、上面がボトムプレートの下面に接する。M3めねじの下穴つき
    parts["rod"] = None
    if g.REAR_FOOT == "brass_rod":
        r = g.rod()
        L = r["x1"] - r["x0"]
        gap = g.rod_top_gap()
        rodm = m3.Manifold.cylinder(L, g.ROD_D / 2, g.ROD_D / 2, 64).rotate([0, 90, 0]).translate([r["x0"], -r["y"], -gap - g.ROD_D / 2])
        for x in r["holes_x"]:
            hole = m3.Manifold.cylinder(g.ROD_HOLE_DEPTH, g.ROD_TAP_DRILL / 2, g.ROD_TAP_DRILL / 2, 24).translate(
                [x, -r["y"], -gap - g.ROD_HOLE_DEPTH])
            rodm = rodm - hole
        parts["rod"] = rodm
        # 受け台：上は平ら（ボトムプレートの下面に接する）、下は丸棒に沿う凹面。左右2分割
        parts["saddle"] = []
        if g.FOOT_STYLE == "ribs":
            # 前後一体の足×4：厚さRIB_Tの板＋手前の台（机の面まで）−丸棒の溝−ナット溝−ボルト穴
            ang = math.degrees(math.atan(tan))
            cutter = m3.Manifold.cube([big, big, big]).translate([-big / 2, -big / 2, -big])
            cutter = cutter.rotate([-ang, 0, 0]).translate([0, -y_front, -h_front])
            Rg = g.ROD_D / 2 + g.SADDLE_CLEAR
            groove = m3.Manifold.cylinder(L + 40, Rg, Rg, 96).rotate([0, 90, 0]).translate([r["x0"] - 20, -r["y"], -gap - g.ROD_D / 2])
            ribs = []
            for rb in g.ribs():
                fx, fy = rb["front"]
                hx, hy = rb["rear"]
                plate = m3.Manifold.extrude(xs(rb["plan"]), g.RIB_T).translate([0, 0, -g.RIB_T])
                hmax = rb["h_front"] + g.RIB_W / 2 * tan + 1
                pad = m3.Manifold.cylinder(hmax, g.RIB_W / 2, g.RIB_W / 2, SEG).translate([fx, -fy, -hmax]) - cutter
                body = (plate + pad) - groove
                rr = g.NUT_POCKET_AF / math.sqrt(3)
                hexagon = [(fx + rr * math.cos(math.radians(60 * k)), fy + rr * math.sin(math.radians(60 * k))) for k in range(6)]
                body = body - m3.Manifold.extrude(xs(hexagon), hmax + 1).translate([0, 0, -(hmax + 1) - g.FOOT_SKIN])
                body = body - m3.Manifold.cylinder(hmax + 2, g.HOLE_D / 2, g.HOLE_D / 2, 24).translate([fx, -fy, -hmax - 1])
                body = body - m3.Manifold.cylinder(30, g.REAR_HOLE_D / 2, g.REAR_HOLE_D / 2, 24).translate([hx, -hy, -15])
                ribs.append(body)
            parts["feet"] = ribs
        elif g.SADDLE:
            s = g.saddle()
            body = m3.Manifold.cube([s["x1"] - s["x0"], s["w"], s["height"]]).translate([s["x0"], -s["y"] - s["w"] / 2, -s["height"]])
            groove = m3.Manifold.cylinder(L + 40, s["R"], s["R"], 96).rotate([0, 90, 0]).translate([r["x0"] - 20, -r["y"], -gap - g.ROD_D / 2])
            body = body - groove
            for x in r["holes_x"]:
                body = body - m3.Manifold.cylinder(20, g.REAR_HOLE_D / 2, g.REAR_HOLE_D / 2, 24).translate([x, -r["y"], -10])
            big = 1000
            left = body ^ m3.Manifold.cube([big, big, big]).translate([g.SPLIT_X - big, -big / 2, -big / 2])
            right = body ^ m3.Manifold.cube([big, big, big]).translate([g.SPLIT_X, -big / 2, -big / 2])
            parts["saddle"] = [left, right]

    # 参考：PCB・スイッチ・キーキャップ（簡略形状）
    parts["pcb"] = m3.Manifold.cube([g.PCB_W, g.PCB_H, g.PCB_T]).translate([0, -g.PCB_H, z["pcb0"]])
    return parts, z


def keys():
    import json
    kle = json.load(open(os.path.join(g.ROOT, "layout/layout_kle.json")))
    out, y = [], 0
    for row in kle:
        x, w, h = 0, 1, 1
        for k in row:
            if isinstance(k, dict):
                x += k.get("x", 0); y += k.get("y", 0); w = k.get("w", w); h = k.get("h", h)
            else:
                out.append((x, y, w, h)); x += w; w = h = 1
        y += 1
    return out


def keycaps(z_top):
    caps = []
    for x, y, w, h in keys():
        u = 19.05
        x0 = -0.375 + x * u + 0.5
        y0 = -0.325 + y * u + 0.5
        cw, ch = w * u - 1.0, h * u - 1.0
        # 中心を原点にして上面を縮めた台形（キーキャップの簡略形）を作り、位置へ移す
        cx, cy = x0 + cw / 2, -(y0 + ch / 2)
        cap = m3.Manifold.extrude(m3.CrossSection([[(-cw / 2, -ch / 2), (cw / 2, -ch / 2), (cw / 2, ch / 2), (-cw / 2, ch / 2)]]),
                                  10.5, 0, 0, [(cw - 4) / cw, (ch - 4) / ch]).translate([cx, cy, z_top + 6.0])
        caps.append(cap)
    return caps


def export(parts, z):
    os.makedirs(OUT, exist_ok=True)
    to_trimesh(parts["frame_left"]).export(os.path.join(OUT, f"frame_left_{g.VER}.stl"))
    to_trimesh(parts["frame_right"]).export(os.path.join(OUT, f"frame_right_{g.VER}.stl"))
    # 足は印刷向きに：天地を反転（ボトムプレートに当たる平らな面を下に）して並べる
    feet = []
    step = 20 if g.FOOT_STYLE != "ribs" else 22
    for i, f in enumerate(parts["feet"]):
        bb = f.bounding_box()
        c = ((bb[0] + bb[3]) / 2, (bb[1] + bb[4]) / 2)
        f2 = f.translate([-c[0], -c[1], 0]).rotate([180, 0, 0]).translate([(i % 4) * step, (i // 4) * step, 0])
        feet.append(f2)
        if g.FOOT_STYLE == "ribs":
            to_trimesh(f.translate([-c[0], -c[1], 0]).rotate([180, 0, 0])).export(os.path.join(OUT, f"foot_{i + 1}_{g.VER}.stl"))
    # 足は印刷向きに：前の足だけ（丸棒のとき）
    allfeet = feet[0]
    for f in feet[1:]:
        allfeet = allfeet + f
    to_trimesh(allfeet).export(os.path.join(OUT, f"feet_{g.VER}.stl"))
    asm = parts["top"] + parts["stiffener"] + parts["frame_left"] + parts["frame_right"] + parts["bottom"] + parts["pcb"]
    for k, sd in enumerate(parts.get("saddle") or []):
        asm = asm + sd
        # 印刷向き：平らな面（ボトムプレート側）を下に
        to_trimesh(sd.rotate([180, 0, 0])).export(os.path.join(OUT, f"rod_saddle_{'left' if k == 0 else 'right'}_{g.VER}.stl"))
    if parts.get("rod") is not None:
        asm = asm + parts["rod"]
        to_trimesh(parts["rod"]).export(os.path.join(OUT, f"brass_rod_reference_{g.VER}.stl"))
    for f in parts["feet"]:
        asm = asm + f
    to_trimesh(asm).export(os.path.join(OUT, f"assembly_{g.VER}.stl"))


def render(parts, z, path, frame_color="#e9e4da", acrylic="#bcd6e4"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    from matplotlib.colors import to_rgb
    for fpath in font_manager.findSystemFonts():
        if "NotoSansCJK" in fpath:
            font_manager.fontManager.addfont(fpath)
    plt.rcParams["font.family"] = "Noto Sans CJK JP"

    tilt = math.radians(g.tilt_deg())
    fl, h_front, tan, y_front = g.feet()
    light = np.array([-0.35, -0.55, 0.76]); light /= np.linalg.norm(light)

    def tris(mf, color, alpha=1.0):
        mesh = mf.to_mesh()
        v = np.array(mesh.vert_properties)[:, :3].copy()
        # 傾ける：前の足の接地点（Y=-y_front, Z=-h_front）を軸にX軸まわりに回転
        v[:, 1] += y_front; v[:, 2] += h_front
        c, s = math.cos(tilt), math.sin(tilt)
        y2 = v[:, 1] * c - v[:, 2] * s
        z2 = v[:, 1] * s + v[:, 2] * c
        v[:, 1], v[:, 2] = y2, z2
        t = v[np.array(mesh.tri_verts)]
        n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
        n /= (np.linalg.norm(n, axis=1)[:, None] + 1e-12)
        shade = 0.55 + 0.45 * np.clip(n @ light, 0, 1)
        rgb = np.clip(np.array(to_rgb(color))[None, :] * shade[:, None], 0, 1)
        return t, np.c_[rgb, np.full(len(rgb), alpha)]

    caps = keycaps(z["top1"])
    layers = [(parts["bottom"], acrylic, 0.95), (parts["frame_left"], frame_color, 1), (parts["frame_right"], frame_color, 1),
              (parts["stiffener"], acrylic, 0.95), (parts["top"], acrylic, 0.95)] + \
             [(f, "#333333", 1) for f in parts["feet"]] + [(c, "#d8d8d4", 1) for c in caps]
    fig = plt.figure(figsize=(16, 9))
    views = [(fig.add_axes([0.0, 0.32, 1.0, 0.68], projection="3d"), (24, -62), "斜め前から"),
             (fig.add_axes([0.02, 0.0, 0.47, 0.34], projection="3d"), (0, -90), "正面（手前）から"),
             (fig.add_axes([0.51, 0.0, 0.47, 0.34], projection="3d"), (0, 0), "右横から")]
    allt, allc = [], []
    for mf, col, a in layers:
        t, c = tris(mf, col, a)
        allt.append(t); allc.append(c)
    T = np.concatenate(allt); C = np.concatenate(allc)
    mn, mx = T.reshape(-1, 3).min(0), T.reshape(-1, 3).max(0)
    for ax, (el, az), title in views:
        pc = Poly3DCollection(T, facecolors=C, edgecolors="none", linewidths=0)
        ax.add_collection3d(pc)
        ctr = (mn + mx) / 2
        r = (mx - mn).max() / 2
        ax.set_xlim(ctr[0] - r, ctr[0] + r); ax.set_ylim(ctr[1] - r, ctr[1] + r); ax.set_zlim(ctr[2] - r, ctr[2] + r)
        ax.set_box_aspect((1, 1, 1))
        ax.view_init(el, az)
        ax.set_axis_off()
        if title != "斜め前から":
            ax.set_proj_type("ortho")
            ax.dist = 6
            # 横・正面は薄いので拡大
            ax.set_xlim(ctr[0] - r, ctr[0] + r); ax.set_ylim(ctr[1] - r, ctr[1] + r)
            ax.set_zlim(ctr[2] - r * 0.18, ctr[2] + r * 0.18)
            ax.set_box_aspect((1, 1, 0.18))
        ax.set_title(title, fontsize=11)
    fig.suptitle(f"外観プレビュー {g.VER}：傾き{g.tilt_deg():g}°、手前の高さ{h_front + z['top1']:.1f}mm（キーキャップ別）、"
                 f"角R{g.CORNER_R:g}・スムージング{g.CORNER_SMOOTH}", fontsize=13)
    fig.savefig(path, dpi=100, bbox_inches="tight", facecolor="white")
    print(path)


def main():
    parts, z = build_parts()
    export(parts, z)
    render(parts, z, os.path.join(g.ROOT, f"docs/img/preview_{g.VER}.png"))
    for k in ("frame_left", "frame_right"):
        bb = parts[k].bounding_box()
        print(k, "size", [round(bb[i + 3] - bb[i], 1) for i in range(3)], "volume_cm3", round(parts[k].volume() / 1000, 1))
    print("feet heights", [round(-(f.bounding_box()[2]), 2) for f in parts["feet"]])


if __name__ == "__main__":
    main()
