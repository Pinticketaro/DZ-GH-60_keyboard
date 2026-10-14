"""積層ケース（旧デザイン2025-03-05踏襲）の図面を生成する。

構成（上から）
  トッププレート … アクリル1.5mm・レーザー加工。スイッチ穴・スタビ穴は旧swillkb出力をそのまま使う
  補強板         … アクリル・レーザー加工。スイッチの周りを大きめに抜いた板。トッププレートの下に重ねる
  枠             … PLAで3Dプリント（Ender-3 Proに収まるよう左右2分割）
  ボトムプレート … アクリル・レーザー加工
  4層をM3ネジ8本で共締め（接着しない）。PCBはネジ止めせず、スイッチの爪（上方向）と肩（下方向）で
  トッププレートに固定し、ボトムプレート側の柔らかい台座で下から軽く支える

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
VER = "v05"

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
# ---- 高さ方向（PCBはネジ止めしない）
# スイッチの爪をトッププレート（1.5mm）の裏に引っかけて上方向を止め、肩（フランジ）で下方向を止める。
# PCBはボトムプレート側の柔らかい台座で軽く押し上げる（支え＋ダンパー）。
# 剛性はトッププレートの下に重ねる補強板で確保し、補強板は枠との間に挟んでM3ネジで共締めする（接着しない）。
TOP_T = 1.5                         # トッププレート（アクリル）。MXの爪がかかる厚さ（1.6mm以下）
STIFF_T = 2.0                       # 補強板（アクリル）厚さ（仮）。3.0にするとPCBとのすき間は0.5mm
STIFF_OFFSET = 0.8                  # 補強板の抜き：トッププレートの穴より片側この分だけ大きく（スイッチ穴→15.6角。爪が開く空間）
STIFF_MIN_WEB = 2.0                 # 補強板の穴と穴の間の最小幅（これより細くなる所はつなげて抜く）
PLATE_TOP_TO_PCB_TOP = 5.0          # MXスイッチの規格寸法（プレート上面〜PCB上面）
PCB_T = 1.6                         # 要実測
UNDER_PCB = 5.0                     # PCB下面〜ボトムプレート上面（台座の高さ＝裏面部品・USB-Cより高く）。要実測
BOTTOM_T = 3.0                      # ボトムプレート（アクリル）厚さ（仮）
GAP_STIFF_PCB = round(PLATE_TOP_TO_PCB_TOP - TOP_T - STIFF_T, 2)      # 補強板の下面〜PCB上面
FRAME_H = round(GAP_STIFF_PCB + PCB_T + UNDER_PCB, 2)                   # 枠の厚さ（自動計算）
assert TOP_T <= 1.6, "トッププレートが1.6mmを超えるとMXの爪がかからない"
assert GAP_STIFF_PCB >= 0.3, "補強板が厚すぎてPCBに当たる"
# ---- 外観
FRAME_INSET = 0.3                   # 枠の外周をアクリルより内側へ下げる量。印刷の誤差で枠がはみ出さず、細い影の線になる
# ---- ボルト・足（ボトムプレートの下にナット受けを兼ねた足。M3ボルトを上から通して全層を共締め）
BOLT_L = 18.0                       # M3ボルトの長さ（8本共通）
NUT_AF, NUT_T = 5.5, 2.4            # M3ナット（二面幅・厚さ）
NUT_POCKET_AF = 6.1                 # 足のナット溝の二面幅（少しきつめ。印刷して調整）
FOOT_D = 12.0                       # 足（丸い台）の直径。外形より1mm以上内側に収まり、浮いて見える
TILT_DEG = 5.0                      # キーボードの傾き（仮）。0〜7°程度
FOOT_SKIN = round(BOLT_L - (TOP_T + STIFF_T + FRAME_H + BOTTOM_T) - NUT_T, 2)  # ナットの上に残るPLAの厚さ
SWILLKB = os.path.join(ROOT, "tools/data/swillkb_switch_layer_2025.svg")
# -----------------------------------------------------------------------------

OX = PCB_W / 2 - OUTER_W / 2        # 外形の左上（PCB座標）
OY = PCB_H / 2 - OUTER_H / 2


def outer_pts():
    return sq.rounded_rect_points(OX, OY, OUTER_W, OUTER_H, CORNER_R, CORNER_SMOOTH)


def frame_outer_pts():
    if not FRAME_INSET:
        return outer_pts()
    return list(Polygon(outer_pts()).buffer(-FRAME_INSET, join_style=1).exterior.coords)[:-1]


def feet():
    """足（ナット受け）の一覧：中心(x,y)、中心での高さ、ナット溝の深さ。傾きは前のネジ列を基準に後ろを高くする。"""
    import math
    hs = holes()
    y_front = max(y for _, y in hs)
    tan = math.tan(math.radians(TILT_DEG))
    nut_r = NUT_POCKET_AF / math.sqrt(3)              # 六角の外接円の半径
    # 前の足：ナット（＋0.3mm）が傾いた底面から出ない最小の高さ
    h_front = math.ceil((FOOT_SKIN + NUT_T + 0.3 + nut_r * tan) * 10) / 10
    out = []
    for x, y in hs:
        h = h_front + (y_front - y) * tan
        out.append(dict(x=x, y=y, h=round(h, 2), pocket_top=FOOT_SKIN))
    return out, h_front, tan, y_front


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


def stiffener_openings():
    """補強板の抜き：トッププレートの穴を片側STIFF_OFFSET広げ、近すぎる穴どうしはつなげる。"""
    from shapely.ops import unary_union
    grown = [Polygon(p).buffer(STIFF_OFFSET, join_style=2) for p in switch_cutouts()]
    # 穴の間がSTIFF_MIN_WEB未満になる所は、細い棒が残らないようにつなげる
    merged = unary_union([g.buffer(STIFF_MIN_WEB / 2, join_style=2) for g in grown]).buffer(-STIFF_MIN_WEB / 2, join_style=2)
    polys = list(merged.geoms) if hasattr(merged, "geoms") else [merged]
    return [list(q.exterior.coords)[:-1] for q in polys]


def stiffener_min_web(openings):
    ps = [Polygon(p) for p in openings]
    m = min((ps[i].distance(ps[j]) for i in range(len(ps)) for j in range(i + 1, len(ps))
             if ps[i].distance(ps[j]) < 10), default=None)
    return round(m, 2) if m is not None else None


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
    st_open = stiffener_openings()
    st_ds = [sq.to_svg_path(kerf_in(p)) for p in st_open]
    svg(os.path.join(ROOT, f"plate/stiffener_{VER}_t{STIFF_T:g}_kerf{KERF:g}.svg"),
        [("openings", "#ff0000", st_ds, f"スイッチ・スタビの逃げ（穴より片側{STIFF_OFFSET}mm大きい）"),
         ("holes", "#ff0000", hole_ds, "M3穴"),
         ("outline", "#ff0000", [outer_d], "外形（最後に切る）")],
        f"補強板（アクリル{STIFF_T}mm・トッププレートの下に重ねて共締め）", note)
    web = stiffener_min_web(st_open)

    svg(os.path.join(ROOT, f"case/bottom_{VER}_kerf{KERF:g}.svg"),
        [("holes", "#ff0000", hole_ds, "M3穴"),
         ("outline", "#ff0000", [outer_d], "外形（最後に切る）")],
        "底板", note)

    # 枠（3Dプリント用の2D形状。Fusion 360で押し出す元）
    split_d = f"M {SPLIT_X:.4f},{OY - 3:.4f} L {SPLIT_X:.4f},{OY + OUTER_H + 3:.4f}"
    usb_d = (f"M {USB_X - USB_W / 2:.4f},{OY:.4f} L {USB_X - USB_W / 2:.4f},{OY + WALL:.4f} "
             f"L {USB_X + USB_W / 2:.4f},{OY + WALL:.4f} L {USB_X + USB_W / 2:.4f},{OY:.4f}")
    svg(os.path.join(ROOT, f"case/frame_{VER}.svg"),
        [("outline", "#000000", [sq.to_svg_path(frame_outer_pts()), sq.to_svg_path(inner)], f"枠の外形（アクリルより{FRAME_INSET}mm内側）と内側"),
         ("holes", "#000000", [circle_path(c, HOLE_D, False) for c in holes()], "M3穴"),
         ("split", "#0000ff", [split_d], f"分割線 X={SPLIT_X}"),
         ("usb", "#0000ff", [usb_d], f"USB切り欠き 幅{USB_W}（位置は要実測）")],
        f"枠（厚さ{FRAME_H}mm・PLA・左右2分割）", note)

    # フォームの型紙（紙に100%で印刷して切る。PORON＝ポリウレタンはレーザーで切らない）
    from shapely.geometry import box as _box
    cav = Polygon(frame_inner_pts()).buffer(-0.5, join_style=1)
    usb_zone = _box(USB_X - 9, 0, USB_X + 9, 12)                     # USB-C裏側の逃げ（仮・要実測）
    case_foam = cav.difference(usb_zone)
    pcb_poly = _box(0, 0, PCB_W, PCB_H).buffer(-2).buffer(2)
    plate_foam = pcb_poly.buffer(-0.5).difference(
        __import__("shapely.ops", fromlist=["unary_union"]).unary_union([Polygon(p) for p in st_open]))
    def poly_ds(geom):
        gs = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
        ds = []
        for gg in gs:
            ds.append(sq.to_svg_path(list(gg.exterior.coords)[:-1]))
            ds += [sq.to_svg_path(list(r.coords)[:-1]) for r in gg.interiors]
        return ds
    svg(os.path.join(ROOT, f"case/foam_case_{VER}.svg"),
        [("cut", "#000000", poly_ds(case_foam), f"ケースフォーム兼台座（PCB下、厚さ{UNDER_PCB}＋つぶし代）。USB-C付近は仮の逃げ")],
        "ケースフォーム型紙（100%で印刷して切る）", note)
    svg(os.path.join(ROOT, f"case/foam_plate_{VER}.svg"),
        [("cut", "#000000", poly_ds(plate_foam), f"プレートフォーム（補強板とPCBの間、厚さ{GAP_STIFF_PCB}以下）")],
        "プレートフォーム型紙（100%で印刷して切る）", note)

    # 足（ナット受け）の平面図
    fl, h_front, _, _ = feet()
    foot_ds = [circle_path((f["x"], f["y"]), FOOT_D, False) for f in fl]
    import math as _m
    hex_ds = []
    for f in fl:
        r = NUT_POCKET_AF / _m.sqrt(3)
        pts = [(f["x"] + r * _m.cos(_m.radians(60 * k)), f["y"] + r * _m.sin(_m.radians(60 * k))) for k in range(6)]
        hex_ds.append(sq.to_svg_path(pts))
    svg(os.path.join(ROOT, f"case/feet_{VER}.svg"),
        [("outline", "#000000", [sq.to_svg_path(outer_pts())], "参考：ケース外形"),
         ("feet", "#0000ff", foot_ds, f"足 φ{FOOT_D}×8（前{h_front}mm〜後{max(f['h'] for f in fl)}mm、傾き{TILT_DEG}°）"),
         ("nut", "#ff0000", hex_ds, f"ナット溝（二面幅{NUT_POCKET_AF}、下から）")],
        "足（ナット受け）平面図", note)

    params = dict(version=VER, pcb=[PCB_W, PCB_H], outer=[OUTER_W, OUTER_H], outer_origin=[OX, OY],
                  wall=WALL, frame_inner=[OUTER_W - 2 * WALL, OUTER_H - 2 * WALL],
                  corner_r=CORNER_R, corner_smoothing=CORNER_SMOOTH,
                  corner_extent=round(sq.corner_extent(CORNER_R, CORNER_SMOOTH), 2),
                  inner_r=INNER_R, inner_smoothing=INNER_SMOOTH,
                  inner_corner_extent=round(sq.corner_extent(INNER_R, INNER_SMOOTH), 2),
                  pcb_min_clearance=pcb_clear,
                  hole_d=HOLE_D, holes_pcb=[[round(a, 3), round(b, 3)] for a, b in holes()],
                  kerf=KERF, split_x=SPLIT_X, usb_x=round(USB_X, 2), usb_w=USB_W, frame_h=FRAME_H,
                  top_t=TOP_T, stiff_t=STIFF_T, stiff_offset=STIFF_OFFSET, stiff_openings=len(st_open),
                  stiff_min_web=web, gap_stiff_pcb=GAP_STIFF_PCB,
                  pcb_t=PCB_T, under_pcb=UNDER_PCB, bottom_t=BOTTOM_T,
                  total_height=round(TOP_T + STIFF_T + FRAME_H + BOTTOM_T, 2),
                  switch_cutouts=len(sw_ds), frame_inset=FRAME_INSET,
                  bolt=f"M3x{BOLT_L:g}", foot_skin=FOOT_SKIN, tilt_deg=TILT_DEG, foot_d=FOOT_D,
                  feet=[{k: (round(v, 2) if isinstance(v, float) else v) for k, v in f.items()} for f in fl],
                  front_height_no_keycap=round(h_front + TOP_T + STIFF_T + FRAME_H + BOTTOM_T, 2))
    open(os.path.join(ROOT, f"case/params_{VER}.json"), "w", encoding="utf-8").write(
        json.dumps(params, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(params, ensure_ascii=False))


if __name__ == "__main__":
    main()
