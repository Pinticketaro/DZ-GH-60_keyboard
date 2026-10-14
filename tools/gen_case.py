"""積層ケース（旧デザイン2025-03-05踏襲）の図面を生成する。

構成（上から）
  プレート  … レーザー加工（1.5mm）。スイッチ穴・スタビ穴は旧swillkb出力をそのまま使う
  枠        … PLAで3Dプリント（Ender-3 Proに収まるよう左右2分割）
  底板      … レーザー加工
  3層をM3ネジ8本で共締め。PCBはスイッチを介してプレートからぶら下がる（サンドイッチ方式）

座標：原点＝PCB外形の左上、X右・Y下、単位mm（README のルール）。
SVGは viewBox に負の原点を使い、Inkscapeでは外形の左上がページの左上になる。

使い方: python3 tools/gen_case.py
"""
import json
import os
import re
import sys

from shapely.geometry import Point, Polygon, box
from shapely import affinity

sys.path.insert(0, os.path.dirname(__file__))
import squircle as sq

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VER = "v02"

# ---- パラメータ（ここだけ直せば全図面が追従する） ---------------------------
PCB_W, PCB_H = 285.0, 94.6          # GH60基準（要実測）
OUTER_W, OUTER_H = 315.0, 126.0     # 旧デザインの外形
WALL = 14.0                         # 枠の幅 → 枠の内側 287×98（旧デザイン）
CORNER_R = 12.0                     # 角丸（仮）※比較図を見て決める
CORNER_SMOOTH = 0.6                 # 0=普通の円弧、0.6前後=Apple風（仮）
INNER_R = 4.5                       # 枠の内側の角丸。PCBの角とのすき間0.5mm以上を保てる最大がR4.5（Apple風）
INNER_SMOOTH = 0.6
PCB_MIN_CLEAR = 0.5                 # 枠の内側とPCBの最小すき間（これを下回るとエラー）
HOLE_D = 3.4                        # M3通し穴（旧デザイン）
# ネジ穴：旧デザインの位置（外形の左上からの距離）。下側中央2個の旧Y=120.7は119に揃えた
HOLES_FROM_OUTER = [(7, 7), (107.7, 7), (192, 7), (308, 7),
                    (7, 119), (107.7, 119), (192, 119), (308, 119)]
KERF = 0.0                          # レーザーのカーフ（M1で決める）
SPLIT_X = PCB_W / 2                 # 枠の分割位置（中央）
USB_X = 142.5 - 124.3               # USB中心X：GH60標準（swillkb −124.3）。要実測
USB_W = 13.0                        # USB切り欠き幅（ケーブルの太い部分が通る幅。旧10mm）
FRAME_H = 10.0                      # 枠の厚み（仮）＝プレート下3.5＋PCB1.6＋PCB下クリアランス約4.9
SWILLKB = os.path.join(ROOT, "tools/data/swillkb_switch_layer_2025.svg")
# -----------------------------------------------------------------------------

OX = PCB_W / 2 - OUTER_W / 2        # 外形の左上（PCB座標）
OY = PCB_H / 2 - OUTER_H / 2


def outer_pts():
    return sq.rounded_rect_points(OX, OY, OUTER_W, OUTER_H, CORNER_R, CORNER_SMOOTH)


def holes():
    """角の4穴は角丸に合わせて対角線上を内側へずらし、外周と枠の内側からの距離が等しくなる位置に置く。"""
    from shapely.geometry import Point
    outer = Polygon(outer_pts())
    inner = Polygon(frame_inner_pts())
    ring = outer.difference(inner)
    out = []
    for x, y in HOLES_FROM_OUTER:
        c = (OX + x, OY + y)
        is_corner = x in (7, 308) and y in (7, 119)
        if is_corner and CORNER_R > 0:
            vx = OX if x < OUTER_W / 2 else OX + OUTER_W
            vy = OY if y < OUTER_H / 2 else OY + OUTER_H
            sx = 1 if vx == OX else -1
            sy = 1 if vy == OY else -1
            best = None
            for i in range(1, 400):
                t = i * 0.05
                q = Point(vx + sx * t, vy + sy * t)
                if not ring.contains(q):
                    continue
                m = min(outer.exterior.distance(q), inner.exterior.distance(q))
                if best is None or m > best[0]:
                    best = (m, (round(q.x, 2), round(q.y, 2)))
            c = best[1]
        out.append(c)
    return out


def switch_cutouts():
    """swillkbのスイッチ層（キー領域の左上が(5.001,5.001)）をPCB座標へ。"""
    t = open(SWILLKB, encoding="utf-8").read()
    polys = []
    for m in re.finditer(r'<polygon points="([^"]+)"', t):
        pts = [tuple(map(float, p.split(","))) for p in m.group(1).split()]
        polys.append(pts)
    polys = polys[1:]               # 1つ目はキー領域の外枠（切らない）
    # キー領域の左上はPCB座標で(-0.375, -0.325)（基準寸法.md）
    dx, dy = -5.001 - 0.375, -5.001 - 0.325
    return [[(x + dx, y + dy) for x, y in p] for p in polys]


def kerf_in(pts):     # 穴：内側へ k/2
    if not KERF:
        return pts
    return list(Polygon(pts).buffer(-KERF / 2, join_style=2).exterior.coords)[:-1]


def kerf_out(pts):    # 外形：外側へ k/2
    if not KERF:
        return pts
    return list(Polygon(pts).buffer(KERF / 2, join_style=1).exterior.coords)[:-1]


def circle_path(c, d, k_in=True):
    r = d / 2 - (KERF / 2 if (KERF and k_in) else 0)
    x, y = c
    return f"M {x - r:.4f},{y:.4f} A {r:.4f},{r:.4f} 0 1 0 {x + r:.4f},{y:.4f} A {r:.4f},{r:.4f} 0 1 0 {x - r:.4f},{y:.4f} Z"


def frame_inner_pts():
    return sq.rounded_rect_points(OX + WALL, OY + WALL, OUTER_W - 2 * WALL, OUTER_H - 2 * WALL,
                                  INNER_R, INNER_SMOOTH)


def check_pcb_clearance():
    pcb = box(0, 0, PCB_W, PCB_H).buffer(-2).buffer(2, quad_segs=32)   # PCBの角R2
    inner = Polygon(frame_inner_pts())
    clear = inner.exterior.distance(pcb) if inner.contains(pcb) else -1
    if clear < PCB_MIN_CLEAR:
        raise SystemExit(f"枠の内側とPCBのすき間が {clear:.2f}mm しかない（最小{PCB_MIN_CLEAR}mm）。INNER_Rを小さくする")
    return round(clear, 2)


def svg(path, layers, title, extra_note=""):
    """layers: [(id, color, [path_d...], 説明)]  赤=切断、青=参考線"""
    vb = f"{OX - 5:.4f} {OY - 5:.4f} {OUTER_W + 10:.4f} {OUTER_H + 10:.4f}"
    out = [f'<?xml version="1.0" encoding="UTF-8"?>',
           f'<!-- {title} / 原点=PCB外形の左上・単位mm / 生成: tools/gen_case.py {extra_note} -->',
           f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
           f'width="{OUTER_W + 10:.4f}mm" height="{OUTER_H + 10:.4f}mm" viewBox="{vb}">']
    for lid, color, ds, desc in layers:
        out.append(f'<g id="{lid}" inkscape:groupmode="layer" inkscape:label="{lid}：{desc}">')
        for d in ds:
            out.append(f'  <path d="{d}" fill="none" stroke="{color}" stroke-width="0.05"/>')
        out.append("</g>")
    out.append("</svg>\n")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8").write("\n".join(out))


def main():
    pcb_clear = check_pcb_clearance()
    outer_d = sq.to_svg_path(kerf_out(outer_pts()))
    hole_ds = [circle_path(c, HOLE_D) for c in holes()]
    sw_ds = [sq.to_svg_path(kerf_in(p)) for p in switch_cutouts()]
    inner = frame_inner_pts()
    note = f"R{CORNER_R} smoothing{CORNER_SMOOTH} kerf{KERF}"

    # プレート（スイッチ穴→ネジ穴→外形の順。外形は最後に切る）
    svg(os.path.join(ROOT, f"plate/plate_{VER}_kerf{KERF:g}.svg"),
        [("switch", "#ff0000", sw_ds, "スイッチ・スタビ穴（先に切る）"),
         ("holes", "#ff0000", hole_ds, "M3穴"),
         ("outline", "#ff0000", [outer_d], "外形（最後に切る）")],
        "プレート", note)

    # 底板
    svg(os.path.join(ROOT, f"case/bottom_{VER}_kerf{KERF:g}.svg"),
        [("holes", "#ff0000", hole_ds, "M3穴"),
         ("outline", "#ff0000", [outer_d], "外形（最後に切る）")],
        "底板", note)

    # 枠（3Dプリント用の2D形状。Fusion 360で押し出す元）
    split_d = f"M {SPLIT_X:.4f},{OY - 3:.4f} L {SPLIT_X:.4f},{OY + OUTER_H + 3:.4f}"
    usb_d = (f"M {USB_X - USB_W / 2:.4f},{OY:.4f} L {USB_X - USB_W / 2:.4f},{OY + WALL:.4f} "
             f"L {USB_X + USB_W / 2:.4f},{OY + WALL:.4f} L {USB_X + USB_W / 2:.4f},{OY:.4f}")
    svg(os.path.join(ROOT, f"case/frame_{VER}.svg"),
        [("outline", "#000000", [sq.to_svg_path(outer_pts()), sq.to_svg_path(inner)], "枠の外形と内側"),
         ("holes", "#000000", [circle_path(c, HOLE_D, False) for c in holes()], "M3穴"),
         ("split", "#0000ff", [split_d], f"分割線 X={SPLIT_X}"),
         ("usb", "#0000ff", [usb_d], f"USB切り欠き 幅{USB_W}（位置は要実測）")],
        f"枠（厚さ{FRAME_H}mm・PLA・左右2分割）", note)

    params = dict(version=VER, pcb=[PCB_W, PCB_H], outer=[OUTER_W, OUTER_H], outer_origin=[OX, OY],
                  wall=WALL, frame_inner=[OUTER_W - 2 * WALL, OUTER_H - 2 * WALL],
                  corner_r=CORNER_R, corner_smoothing=CORNER_SMOOTH,
                  corner_extent=round(sq.corner_extent(CORNER_R, CORNER_SMOOTH), 2),
                  inner_r=INNER_R, inner_smoothing=INNER_SMOOTH,
                  inner_corner_extent=round(sq.corner_extent(INNER_R, INNER_SMOOTH), 2),
                  pcb_min_clearance=pcb_clear,
                  hole_d=HOLE_D, holes_pcb=[[round(a, 3), round(b, 3)] for a, b in holes()],
                  kerf=KERF, split_x=SPLIT_X, usb_x=round(USB_X, 2), usb_w=USB_W, frame_h=FRAME_H,
                  switch_cutouts=len(sw_ds))
    open(os.path.join(ROOT, f"case/params_{VER}.json"), "w", encoding="utf-8").write(
        json.dumps(params, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(params, ensure_ascii=False))


if __name__ == "__main__":
    main()
