"""Fusion 360で自分でモデリングするための図面セット（A3横・寸法入り）とDXF・CSVを作る。

座標：外形の左下を原点、X＝右、Y＝奥（平面図の上）、Z＝上（ボトムプレートの下面＝0）。単位mm。
出力:
  case/drawings/DZ60_drawings_<ver>.pdf   … 図面セット（全7枚）
  case/drawings/dxf/*.dxf                 … Fusionの「挿入 → DXFを挿入」でスケッチに読み込める（同じ座標）
  case/drawings/switch_cutouts_<ver>.csv  … スイッチ穴の中心座標
  docs/img/drawings_<ver>_p<N>.png        … 確認用
使い方: python3 tools/fusion_drawings.py
"""
import csv
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Circle, Polygon as MPoly, Rectangle
from shapely.geometry import Polygon, box

sys.path.insert(0, os.path.dirname(__file__))
import gen_case as g
import build3d as b3
from rod_drawing import (THICK, THIN, FS, setup, line, arrow, hdim, vdim, leader, centerline)

OUTDIR = os.path.join(g.ROOT, "case/drawings")
OX0, OY0 = g.OX, g.OY + g.OUTER_H        # PCB座標でのこの図の原点（外形の左下）
DATE = "2026-10-15"


# ---------- 座標変換（PCB座標 → 図面座標：左下原点・Y上向き）
def T(p):
    return (round(p[0] - OX0, 4), round(OY0 - p[1], 4))


def TP(pts):
    return [T(p) for p in pts]


def r2(v):
    return f"{v:.2f}".rstrip("0").rstrip(".") if abs(v - round(v, 2)) < 1e-9 else f"{v:.2f}"


def fmt(v):
    return f"{v:.2f}"


# ---------- データ
def data():
    z = b3.z_levels()
    outer = TP(g.outer_pts())
    frame_outer = TP(g.frame_outer_pts())
    frame_inner = TP(g.frame_inner_pts())
    holes = [(T(c), g.hole_d(c)) for c in g.holes()]
    cuts = [TP(p) for p in g.switch_cutouts()]
    stiff = [TP(p) for p in g.stiffener_openings()]
    sw = switch_centers(cuts)
    fl = g.pairs()
    bars = []
    for pr in fl:
        for key, hs in (("front", [(x, y) for x, y, _ in pr["front_holes"]]), ("rear", [(x, y) for x, y, _ in pr["rear_bar_holes"]])):
            a, b = T(hs[0]), T(hs[1])
            bars.append(dict(side=pr["side"], pos=key, c=((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), holes=(a, b),
                             plan=TP(pr["front_plan"] if key == "front" else pr["rear_plan"])))
    return dict(z=z, outer=outer, frame_outer=frame_outer, frame_inner=frame_inner, holes=holes, cuts=cuts,
                stiff=stiff, sw=sw, bars=bars)


def switch_centers(cuts):
    """スイッチ穴の中心（14角の部分の中心）と種類。スタビつきは長手方向とスタビの中心距離も。"""
    out = []
    for p in cuts:
        P = Polygon(p)
        b = P.bounds
        if len(p) == 4:
            out.append(dict(x=(b[0] + b[2]) / 2, y=(b[1] + b[3]) / 2, kind="1u", poly=p))
            continue
        xs = sorted({round(x, 3) for x, _ in p})
        ys = sorted({round(y, 3) for _, y in p})

        def pair(vals, mid):
            best = None
            for i, a in enumerate(vals):
                for c in vals[i + 1:]:
                    if abs(c - a - 14.0) < 0.006:
                        m = (a + c) / 2
                        if best is None or abs(m - mid) < abs(best - mid):
                            best = m
            return best
        cx = pair(xs, (b[0] + b[2]) / 2)
        cy = pair(ys, (b[1] + b[3]) / 2)
        horiz = (b[2] - b[0]) > (b[3] - b[1])
        along = [abs(x - cx) for x, _ in p] if horiz else [abs(y - cy) for _, y in p]
        u = cluster([v for v in along if v > 7.5])
        off = (u[0] + u[3]) / 2
        out.append(dict(x=cx, y=cy, kind=("6.25u" if off > 30 else "2u") + ("（横）" if horiz else "（縦）"),
                        horiz=horiz, stab_off=off, poly=p))
    # 並び：奥の段から、左から
    out.sort(key=lambda s: (-round(s["y"], 0), s["x"]))
    for i, s in enumerate(out, 1):
        s["no"] = i
    return out


def cluster(vals, tol=0.01):
    """近い値（tol以内）をまとめて平均にする。"""
    out = []
    for v in sorted(vals):
        if out and v - out[-1][-1] < tol:
            out[-1].append(v)
        else:
            out.append([v])
    return [sum(c) / len(c) for c in out]


def stab_rects(s):
    """スタビつきの穴を、スケッチで描く長方形（中心・幅・高さ）に分解する。和集合が元の形と一致するか確かめる。"""
    p = s["poly"]
    cx, cy = s["x"], s["y"]
    # 局所座標：a＝長手方向（スタビの並ぶ向き）、c＝それと直角
    if s["horiz"]:
        loc = [(x - cx, y - cy) for x, y in p]
    else:
        loc = [(y - cy, x - cx) for x, y in p]
    A = cluster([abs(a) for a, _ in loc if abs(a) > 7.5])       # 例: 46.625, 48.35, 51.65, 53.375, 54.2
    assert len(A) == 5, A
    off = (A[0] + A[3]) / 2
    # 張り出し・ハウジング・切り欠き・溝のc範囲
    nub_c = cluster([c for a, c in loc if abs(abs(a) - A[4]) < 0.01])
    house_c = cluster([c for a, c in loc if abs(abs(a) - A[3]) < 0.01])
    notch_c = cluster([c for a, c in loc if abs(abs(a) - A[2]) < 0.01])
    chan_c = cluster([c for a, c in loc if abs(abs(a) - A[0]) < 0.01 and abs(c) < 3])
    rects_loc = [("スイッチ", 0, 0, 14.0, 14.0)]
    rects_loc.append(("ワイヤーの溝", 0, (chan_c[0] + chan_c[-1]) / 2, 2 * A[0], chan_c[-1] - chan_c[0]))
    for sgn in (-1, 1):
        rects_loc.append(("ハウジング", sgn * off, (house_c[0] + house_c[-1]) / 2, A[3] - A[0], house_c[-1] - house_c[0]))
        rects_loc.append(("切り欠き", sgn * off, (notch_c[0] + notch_c[-1]) / 2, A[2] - A[1], notch_c[-1] - notch_c[0]))
        rects_loc.append(("張り出し", sgn * (A[3] + A[4]) / 2, (nub_c[0] + nub_c[-1]) / 2, A[4] - A[3], nub_c[-1] - nub_c[0]))
    rects = []
    for name, a, c, wa, wc in rects_loc:
        if s["horiz"]:
            rects.append((name, cx + a, cy + c, wa, wc))
        else:
            rects.append((name, cx + c, cy + a, wc, wa))
    from shapely.ops import unary_union
    U = unary_union([box(x - w / 2, y - h / 2, x + w / 2, y + h / 2) for _, x, y, w, h in rects])
    err = U.symmetric_difference(Polygon(p)).area
    assert err < 0.05, f"スタビ穴の分解が一致しない（差 {err}）"
    return rects, dict(off=off, house_w=A[3] - A[0], house_h=house_c[-1] - house_c[0], notch_w=A[2] - A[1],
                       notch_h=notch_c[-1] - notch_c[0], nub_w=A[4] - A[3], nub_h=nub_c[-1] - nub_c[0],
                       chan_h=chan_c[-1] - chan_c[0])


# ---------- 図枠・表題欄
def frame_and_title(ax, name, no, material, scale, page, total):
    ax.add_patch(Rectangle((10, 10), 400, 277, fill=False, lw=1.0))
    bx, by, bw, bh = 250, 10, 160, 42
    ax.add_patch(Rectangle((bx, by), bw, bh, fill=False, lw=1.0))
    rows = [("品名", name), ("図番", f"DZ60-{no}-{g.VER}"), ("材質", material), ("尺度", f"{scale}　単位 mm"),
            ("投影法", "第三角法"), ("日付", f"{DATE}　{page}/{total}枚")]
    rh = bh / len(rows)
    for k, (kn, val) in enumerate(rows):
        yy = by + bh - (k + 1) * rh
        line(ax, [(bx, yy), (bx + bw, yy)], lw=0.4)
        ax.text(bx + 2, yy + rh / 2, kn, va="center", fontsize=7.5)
        ax.text(bx + 20, yy + rh / 2, val, va="center", fontsize=8.5)
    line(ax, [(bx + 18, by), (bx + 18, by + bh)], lw=0.4)
    sx, sy = bx + 136, by + rh * 1.5
    ax.add_patch(MPoly([(sx, sy - 2.5), (sx + 9, sy - 4), (sx + 9, sy + 4), (sx, sy + 2.5)], closed=True, fill=False, lw=0.5))
    ax.add_patch(Circle((sx + 17, sy), 4, fill=False, lw=0.5))
    ax.add_patch(Circle((sx + 17, sy), 2.5, fill=False, lw=0.5))
    ax.text(410, 290, f"DZ-GH-60_keyboard / {g.VER}", ha="right", fontsize=7, color="#555")


def poly(ax, pts, x0, y0, s=1.0, lw=THICK, ls="-", fill=None, color="k"):
    q = [(x0 + x * s, y0 + y * s) for x, y in pts]
    ax.add_patch(MPoly(q, closed=True, fill=fill is not None, fc=fill or "none", ec=color, lw=lw, ls=ls))


def circ(ax, c, d, x0, y0, s=1.0, lw=THICK):
    ax.add_patch(Circle((x0 + c[0] * s, y0 + c[1] * s), d / 2 * s, fill=False, lw=lw))
    centerline(ax, (x0 + c[0] * s - d * s * 0.9, y0 + c[1] * s), (x0 + c[0] * s + d * s * 0.9, y0 + c[1] * s))
    centerline(ax, (x0 + c[0] * s, y0 + c[1] * s - d * s * 0.9), (x0 + c[0] * s, y0 + c[1] * s + d * s * 0.9))


def origin_mark(ax, x0, y0):
    ax.add_patch(Circle((x0, y0), 1.6, fill=False, lw=0.6))
    ax.add_patch(MPoly([(x0, y0), (x0 + 1.6, y0), (x0, y0 + 1.6)], closed=True, fc="k", lw=0))
    ax.text(x0 - 2.5, y0 - 2.5, "原点(0,0)", ha="right", va="top", fontsize=6.5)


def ordinate_x(ax, xs, x0, y0, y_line, ref_y, s=1.0, label_up=True):
    """X方向の座標寸法（原点からの距離を縦書き風に並べる）"""
    line(ax, [(x0, ref_y), (x0, y_line + (3 if label_up else -3))])
    ax.text(x0, y_line + (4 if label_up else -4), "0", ha="center", va="bottom" if label_up else "top", fontsize=FS)
    for x in xs:
        px = x0 + x * s
        line(ax, [(px, ref_y), (px, y_line + (3 if label_up else -3))])
        ax.text(px, y_line + (4 if label_up else -4), fmt(x), ha="center", va="bottom" if label_up else "top", fontsize=FS,
                rotation=90)


def ordinate_y(ax, ys, x0, y0, x_line, ref_x, s=1.0):
    line(ax, [(ref_x, y0), (x_line - 3, y0)])
    ax.text(x_line - 4, y0, "0", ha="right", va="center", fontsize=FS)
    for y in ys:
        py = y0 + y * s
        line(ax, [(ref_x, py), (x_line - 3, py)])
        ax.text(x_line - 4, py, fmt(y), ha="right", va="center", fontsize=FS)


def trow(ax, x, y, cells, cols, fs=7.0, bold=False):
    """表の1行：cols＝各列の右端（数値は右寄せ）または(左端, 'l')。"""
    for cell, c in zip(cells, cols):
        if isinstance(c, tuple):
            ax.text(x + c[0], y, cell, fontsize=fs, va="top", ha="left", fontweight="bold" if bold else "normal")
        else:
            ax.text(x + c, y, cell, fontsize=fs, va="top", ha="right", fontweight="bold" if bold else "normal")


def notes(ax, x, y, lines, fs=7.6, head="注記"):
    ax.text(x, y, "\n".join([head] + lines), fontsize=fs, va="top", linespacing=1.7)


# ---------- 各ページ
def page_assembly(D, pdf, total):
    fig, ax = setup()
    frame_and_title(ax, "キーボードケース 組立図（積層断面・部品表）", "ASSY", "—", "断面 4:1", 1, total)
    z = D["z"]
    s = 4.0
    # 断面 A-A：X=107.7（中央左のネジの列）で切り、左から見る。横軸＝Y（手前が左）、0〜40の範囲
    x0, z0 = 70, 185
    Ymax = 36

    def R(y0_, y1_, za, zb, fc, hatch=None, lw=THICK):
        ax.add_patch(Rectangle((x0 + y0_ * s, z0 + za * s), (y1_ - y0_) * s, (zb - za) * s, fc=fc, ec="k", lw=lw, hatch=hatch))
    hole_y = D["holes"][4][0][1]                      # 手前の穴のY（7.0）
    hd = g.HOLE_D
    # ボトムプレート・補強板・トップ（穴の所は切れている）
    for za, zb, fc in ((z["bot0"], z["bot1"], "#e8f1f6"), (z["fr1"], z["st1"], "#e8f1f6"), (z["st1"], z["top1"], "#dfeaf2")):
        R(0, hole_y - hd / 2, za, zb, fc, "///")
        R(hole_y + hd / 2, Ymax, za, zb, fc, "///")
    # 枠（前の壁）：Y=0.3〜14、穴あり
    wall_in = g.WALL
    R(g.FRAME_INSET, hole_y - hd / 2, z["bot1"], z["fr1"], "#f6e3d6", "\\\\\\")
    R(hole_y + hd / 2, wall_in, z["bot1"], z["fr1"], "#f6e3d6", "\\\\\\")
    # 中：ケースフォーム、PCB、プレートフォーム
    pcb_front = T((0, g.PCB_H))[1]                    # PCBの手前の縁のY
    R(wall_in, Ymax, z["bot1"], z["pcb0"], "#eeeeee", "..", THIN)
    R(pcb_front, Ymax, z["pcb0"], z["pcb1"], "#dbe8d4", None)
    R(wall_in, Ymax, z["pcb1"], z["fr1"], "#eeeeee", "..", THIN)
    # 足（Y=1〜13）とナット溝
    fh = D["bars"][0]
    foot_h = g.feet()[1]
    R(hole_y - g.RIB_W / 2, hole_y + g.RIB_W / 2, -foot_h, 0, "#f6e3d6", "\\\\\\")
    nut_af = g.NUT_POCKET_AF
    ax.add_patch(Rectangle((x0 + (hole_y - nut_af / 2) * s, z0 - foot_h * s), nut_af * s, (foot_h - g.FOOT_SKIN) * s, fc="white", ec="k", lw=THICK))
    ax.add_patch(Rectangle((x0 + (hole_y - 5.5 / 2) * s, z0 + (-(foot_h) + 0.3) * s), 5.5 * s, g.NUT_T * s, fc="#9a9da2", ec="k", lw=THIN))
    # ボルト（ボタンヘッドφ5.7×1.65、軸φ3、長さ18）
    L = g.BOLT_L
    ax.add_patch(Rectangle((x0 + (hole_y - 1.5) * s, z0 + (z["top1"] - L) * s), 3 * s, L * s, fc="#c9cbce", ec="k", lw=THIN))
    ax.add_patch(Rectangle((x0 + (hole_y - 2.85) * s, z0 + z["top1"] * s), 5.7 * s, 1.65 * s, fc="#c9cbce", ec="k", lw=THIN))
    centerline(ax, (x0 + hole_y * s, z0 + (z["top1"] + 4) * s), (x0 + hole_y * s, z0 - (foot_h + 3) * s))
    # 破断線（右端）
    ax.plot([x0 + Ymax * s] * 2, [z0 - 2 * s, z0 + (z["top1"] + 1) * s], color="k", lw=THIN, ls=(0, (6, 2)))
    # 高さ寸法（右側にチェーン）
    xr = x0 + Ymax * s + 8
    levels = [(-foot_h, 0, f"足 {foot_h:g}"), (z["bot0"], z["bot1"], f"ボトム {g.BOTTOM_T:g}"), (z["bot1"], z["pcb0"], f"ケースフォーム {g.UNDER_PCB:g}"),
              (z["pcb0"], z["pcb1"], f"PCB {g.PCB_T:g}"), (z["pcb1"], z["fr1"], f"プレートフォーム {g.GAP_STIFF_PCB:g}"),
              (z["fr1"], z["st1"], f"補強板 {g.STIFF_T:g}"), (z["st1"], z["top1"], f"トップ {g.TOP_T:g}")]
    for za, zb, t in levels:
        vdim(ax, z0 + za * s, z0 + zb * s, xr, x0 + Ymax * s, t)
    vdim(ax, z0 + z["bot1"] * s, z0 + z["fr1"] * s, x0 - 14, x0 + g.FRAME_INSET * s, f"枠 {g.FRAME_H:g}", right=False)
    vdim(ax, z0 + z["bot0"] * s, z0 + z["top1"] * s, x0 - 30, x0, f"{z['top1']:g}", right=False)
    vdim(ax, z0 - foot_h * s, z0 + z["top1"] * s, x0 - 44, x0 + (hole_y - g.RIB_W / 2) * s, f"{z['top1'] + foot_h:g}", right=False)
    # Y方向
    hdim(ax, x0, x0 + hole_y * s, z0 + (z["top1"] + 6) * s, z0 + z["top1"] * s, z0 + (z["top1"] + 2) * s, f"{fmt(hole_y)}（ネジ）")
    hdim(ax, x0, x0 + wall_in * s, z0 - (foot_h + 8) * s, z0, z0 + z["bot1"] * s, f"{wall_in:g}（枠の幅）", above=False)
    hdim(ax, x0 + wall_in * s, x0 + pcb_front * s, z0 + (z["top1"] + 6) * s, z0 + z["fr1"] * s, z0 + z["pcb1"] * s, f"{fmt(pcb_front - wall_in)}")
    ax.text(x0, z0 + (z["top1"] + 9) * s, "断面 A-A（X=107.7のネジの列で切り、左から見る。手前が左）　尺度 4:1", fontsize=9)
    ax.text(x0 + 2, z0 - (foot_h + 3.5) * s, "足（ナットは下から）", fontsize=7)
    ax.text(x0 + (wall_in + 3) * s, z0 + (z["pcb0"] + 0.35) * s, "PCB（ネジ止めなし）", fontsize=7, va="bottom")
    # 部品表
    tx, ty = 282, 280
    ax.text(tx, ty, "部品表", fontsize=9, va="top")
    head = ["No", "部品", "材料・厚さ", "数", "図"]
    rows = [["1", "トッププレート", "アクリル 1.5（キャスト）", "1", "2・3・4枚目"],
            ["2", "補強板", "アクリル 2", "1", "2・5枚目"],
            ["3", "枠（左右2分割）", "PLA 高さ8.1", "2", "6枚目"],
            ["4", "ボトムプレート", "アクリル 3", "1", "2枚目"],
            ["5", "足（同じ形）", "PLA 高さ3.7", "4", "7枚目"],
            ["6", "ボルト", "M3×18 ボタンヘッド", "8", "—"],
            ["7", "ナット", "M3（二面幅5.5・厚さ2.4）", "8", "—"],
            ["8", "継ぎ目のボルト・ナット", f"M3×{g.JB_L:g} キャップ＋M3ナット", "各2", "6枚目"],
            ["9", "ケースフォーム", f"厚さ{g.UNDER_PCB + 0.5:g}〜{g.UNDER_PCB + 1:g}", "1", "型紙SVG"],
            ["10", "プレートフォーム", f"厚さ{g.GAP_STIFF_PCB:g}", "1", "型紙SVG"]]
    cw = [8, 30, 54, 8, 26]
    yy = ty - 7
    for r in [head] + rows:
        xx = tx
        for w, cell in zip(cw, r):
            ax.text(xx + 1, yy, cell, fontsize=7.0, va="center")
            xx += w
        line(ax, [(tx, yy - 3), (tx + sum(cw), yy - 3)], lw=0.3)
        yy -= 6.2
    notes(ax, 16, 122, [
        "1. 座標：外形の左下を原点、X＝右、Y＝奥、Z＝上（ボトムプレートの下面＝0）。全ページ共通",
        "2. Fusionでは XY平面にスケッチし、原点を外形の左下に合わせる。DXF（case/drawings/dxf）も同じ座標",
        "3. 外形の角はR8・曲率連続（Apple風）。2枚目の点列をフィット点スプラインで通すか、DXFの外形を使う",
        "4. ボルトは上から全層を通し、足の六角溝のナットで締める（8本とも同じ）",
        "5. PCBはネジ止めしない。スイッチの爪でトッププレートに吊られ、下のケースフォームで支える",
        "6. 指示のない寸法の許容差：±0.2（レーザー・3Dプリントの精度に合わせる）",
        f"7. 枠は外形より全周{g.FRAME_INSET:g}内側（印刷の誤差で枠がはみ出さず、層の間に細い影の線が出る）",
    ])
    pdf.savefig(fig)
    return fig


def corner_points(D, n=9):
    """外形の左下の角：カーブの区間を等間隔に取った点列（フィット点スプライン用）。"""
    ext = g.sq.corner_extent(g.CORNER_R, g.CORNER_SMOOTH) if hasattr(g, "sq") else 12.04
    pts = [p for p in D["outer"] if p[0] <= ext + 1e-6 and p[1] <= ext + 1e-6]
    # 弧長で並べ替え（Y軸側→X軸側）
    pts.sort(key=lambda p: (p[1] - p[0]))
    pts = pts[::-1]
    import numpy as np
    P = np.array(pts)
    d = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(P, axis=0).T))])
    out = []
    for t in np.linspace(0, d[-1], n):
        i = min(np.searchsorted(d, t), len(P) - 1)
        if i == 0:
            out.append(tuple(P[0]))
        else:
            f = (t - d[i - 1]) / (d[i] - d[i - 1] + 1e-12)
            out.append(tuple(P[i - 1] + (P[i] - P[i - 1]) * f))
    return out, ext


def page_outline(D, pdf, total):
    fig, ax = setup()
    frame_and_title(ax, "外形・ネジ穴（共通）／ボトムプレート", "OUT", "アクリル 3（ボトムプレート）", "1:1", 2, total)
    x0, y0 = 62, 128
    poly(ax, D["outer"], x0, y0)
    for c, d in D["holes"]:
        circ(ax, c, d, x0, y0)
    origin_mark(ax, x0, y0)
    xs = sorted({c[0] for c, _ in D["holes"]})
    ys = sorted({c[1] for c, _ in D["holes"]})
    ordinate_x(ax, xs + [g.OUTER_W], x0, y0, y0 + g.OUTER_H + 8, y0 + g.OUTER_H + 1)
    ordinate_y(ax, ys + [g.OUTER_H], x0, y0, x0 - 6, x0 - 1)
    leader(ax, (x0 + xs[0] + 1.2, y0 + ys[0] + 1.2), (x0 + 28, y0 + 26), f"4-φ{g.HOLE_D:g} 貫通（手前の列）")
    leader(ax, (x0 + xs[1] + 1.4, y0 + ys[1] - 1.4), (x0 + 128, y0 + 100), f"4-φ{g.REAR_HOLE_D:.1f} 貫通（奥の列）")
    centerline(ax, (x0 - 3, y0 + ys[0]), (x0 + g.OUTER_W + 3, y0 + ys[0]))
    centerline(ax, (x0 - 3, y0 + ys[1]), (x0 + g.OUTER_W + 3, y0 + ys[1]))
    ax.text(x0, y0 - 6, f"外形 {g.OUTER_W:g} × {g.OUTER_H:g}、角R{g.CORNER_R:g}（曲率連続、詳細は右下）。トッププレート・補強板・ボトムプレートで共通", fontsize=8, va="top")
    # 角の詳細 5:1
    pts, ext = corner_points(D)
    s = 4.0
    cx0, cy0 = 150, 58
    allp = [p for p in D["outer"] if p[0] <= 16 and p[1] <= 16]
    allp.sort(key=lambda p: (p[1] - p[0]))
    line(ax, [(cx0 + x * s, cy0 + y * s) for x, y in allp], lw=THICK)
    for i, (x, y) in enumerate(pts):
        ax.add_patch(Circle((cx0 + x * s, cy0 + y * s), 0.8, fc="k"))
        ax.text(cx0 + x * s + 1.6, cy0 + y * s + 1.2, f"P{i}", fontsize=6.5)
    line(ax, [(cx0, cy0), (cx0 + 16 * s, cy0)], lw=THIN, ls=(0, (2, 2)))
    line(ax, [(cx0, cy0), (cx0, cy0 + 16 * s)], lw=THIN, ls=(0, (2, 2)))
    ax.text(cx0, cy0 - 4, f"左下の角の詳細　尺度 4:1（カーブは角から{ext:.2f}の所で直線につながる）", fontsize=7.5, va="top")
    tx = 222
    ax.text(tx, 118, "角のカーブの点列（左下、原点基準）", fontsize=7.6, va="top")
    for i, (x, y) in enumerate(pts):
        trow(ax, tx, 110 - i * 5.2, [f"P{i}", f"X {x:.3f}", f"Y {y:.3f}"], [(0, "l"), 30, 56], fs=7.2)
    ax.text(tx, 110 - len(pts) * 5.2 - 1, "ほかの3つの角は左右・上下の対称（X→315−X、Y→126−Y）", fontsize=7, va="top")
    notes(ax, 14, 118, [
        "1. Fusion：スケッチで P0〜P8 を通るフィット点スプライン、",
        "   両端は直線と接線（曲率）連続にする。または",
        "   長方形を押し出し → 縦の4辺にフィレットR8の",
        "   「曲率（G2）連続」でも近い形になる",
        "2. 正確な形はDXF（dxf/plate_*.dxf の外形）",
        "3. ボトムプレートはこの図のまま、厚さ3",
        "4. 奥の列φ4.0は丸棒（保留）に戻すときの",
        "   位置のずれ吸収用。PLAの足ならφ3.4でも可",
    ])
    pdf.savefig(fig)
    return fig


def page_top(D, pdf, total):
    fig, ax = setup()
    frame_and_title(ax, "トッププレート", "TOP", "アクリル 1.5（キャスト・すりガラス推奨）", "1:1", 3, total)
    x0, y0 = 62, 140
    poly(ax, D["outer"], x0, y0)
    for c, d in D["holes"]:
        circ(ax, c, d, x0, y0, lw=THIN)
    for p in D["cuts"]:
        poly(ax, p, x0, y0, lw=0.45)
    for s in D["sw"]:
        ax.text(x0 + s["x"], y0 + s["y"], str(s["no"]), ha="center", va="center", fontsize=4.6, color="#c33")
    origin_mark(ax, x0, y0)
    # 段（行）のY座標
    rows = sorted({round(s["y"], 3) for s in D["sw"] if s["kind"] == "1u"})
    ordinate_y(ax, rows, x0, y0, x0 - 6, x0 - 1)
    ax.text(x0, y0 + g.OUTER_H + 5, "スイッチ穴 65か所（番号は4枚目の座標表）。穴の段のY座標を左に示す。外形・ネジ穴は2枚目と同じ",
            fontsize=8, va="bottom")
    # スタビ穴の詳細（スペースの右側）：寸法と、長方形の分解
    sp = [s for s in D["sw"] if s["kind"].startswith("6.25u")][0]
    rects, dim = stab_rects(sp)
    S = 4.0
    dx0, dy0 = 40, 66
    # 局所：スイッチ中心から右へ off の所がハウジング中心。図ではハウジング中心を(dx0+?..)
    hx = dx0 + 62
    def L(a, c):
        return (hx + a * S, dy0 + c * S)
    # ハウジング部分（局所座標で描く：a＝ハウジング中心から、c＝スイッチ中心から（Y上向き））
    loc = [((x - sp["x"]) - dim["off"], (y - sp["y"])) for x, y in sp["poly"] if x > sp["x"] + 7.5]
    # 長方形で描く
    for name, X, Y, w, h in rects:
        a = (X - sp["x"]) - dim["off"]
        c = Y - sp["y"]
        if a < -10 or name in ("スイッチ",):
            continue
        if name == "ワイヤーの溝":
            ax.add_patch(Rectangle(L(-10, c - h / 2), (10 - dim["house_w"] / 2) * S, h * S, fill=False, lw=THIN, ls=(0, (3, 1.5))))
            continue
        ax.add_patch(Rectangle(L(a - w / 2, c - h / 2), w * S, h * S, fill=False, lw=THIN, ls=(0, (3, 1.5))))
    # 外形（太線）：元の多角形の右側
    from shapely.geometry import box as _b
    Pp = Polygon([((x - sp["x"]) - dim["off"], (y - sp["y"])) for x, y in sp["poly"]]).intersection(_b(-10, -20, 20, 20))
    xs_, ys_ = Pp.exterior.xy
    line(ax, [L(a, c) for a, c in zip(xs_, ys_)], lw=THICK)
    centerline(ax, L(0, -11), L(0, 11))
    centerline(ax, L(-14, 0), L(8, 0))
    ax.text(*L(-14.5, 0), "スイッチ中心の高さ", fontsize=6, va="center", ha="right")
    # 寸法
    hc = [r for r in rects if r[0] == "ハウジング" and r[1] > sp["x"]][0]
    nc = [r for r in rects if r[0] == "切り欠き" and r[1] > sp["x"]][0]
    bc = [r for r in rects if r[0] == "張り出し"][0]
    ch = [r for r in rects if r[0] == "ワイヤーの溝"][0]
    def cc(r):
        return r[2] - sp["y"]
    hdim(ax, L(-dim["house_w"] / 2, 0)[0], L(dim["house_w"] / 2, 0)[0], L(0, cc(nc) + nc[4] / 2 + 2)[1], L(0, cc(hc) + hc[4] / 2)[1], L(0, cc(hc) + hc[4] / 2)[1], f"{dim['house_w']:.2f}")
    hdim(ax, L(-dim["notch_w"] / 2, 0)[0], L(dim["notch_w"] / 2, 0)[0], L(0, cc(nc) - nc[4] / 2 - 2)[1], L(0, cc(nc) - nc[4] / 2)[1], L(0, cc(nc) - nc[4] / 2)[1], f"{dim['notch_w']:.2f}", above=False)
    vdim(ax, L(0, cc(hc) - hc[4] / 2)[1], L(0, cc(hc) + hc[4] / 2)[1], L(-dim["house_w"] / 2 - 4, 0)[0], L(-dim["house_w"] / 2, 0)[0], f"{dim['house_h']:.2f}", right=False)
    vdim(ax, L(0, cc(nc) - nc[4] / 2)[1], L(0, cc(nc) + nc[4] / 2)[1], L(dim["house_w"] / 2 + dim["nub_w"] + 4, 0)[0], L(dim["notch_w"] / 2, 0)[0], f"{dim['notch_h']:.2f}")
    vdim(ax, L(0, cc(ch) - ch[4] / 2)[1], L(0, cc(ch) + ch[4] / 2)[1], L(-11.5, 0)[0], L(-10, 0)[0], f"{dim['chan_h']:.2f}", right=False)
    leader(ax, L(dim["house_w"] / 2 + dim["nub_w"], cc(bc)), L(dim["house_w"] / 2 + 3, cc(bc) - 12), f"張り出し {dim['nub_w']:.3f}×{dim['nub_h']:.2f}")
    ax.text(dx0, dy0 + 16 * S - 2, "スタビ穴の詳細（スペースの右側。3か所とも同じ形）　尺度 4:1", fontsize=7.5, va="bottom")
    # 長方形の表（Fusionで中心の長方形として描く）：2列
    ax.text(150, 124, "スタビつきの穴は、次の長方形を重ねた形（原点基準。幅＝X方向、高さ＝Y方向）", fontsize=7.4, va="top")
    SC = [(0, "l"), (8, "l"), 60, 82, 101, 120]
    groups = [[s for s in D["sw"] if s["kind"] != "1u" and not s["kind"].startswith("6.25")],
              [s for s in D["sw"] if s["kind"].startswith("6.25")]]
    for gi, grp in enumerate(groups):
        tx = 150 if gi == 0 else 285
        yy = 117
        trow(ax, tx, yy, ["No", "部品", "中心X", "中心Y", "幅", "高さ"], SC, fs=6.4, bold=True)
        yy -= 4.0
        for s in grp:
            ax.text(tx + 8, yy, f"No.{s['no']}：{s['kind']}", fontsize=6.2, va="top", color="#555")
            yy -= 3.4
            rr, _ = stab_rects(s)
            for name, X, Y, w, h in rr:
                trow(ax, tx, yy, [str(s["no"]), name, f"{X:.3f}", f"{Y:.3f}", f"{w:.3f}", f"{h:.3f}"], SC, fs=6.0)
                yy -= 3.25
    pdf.savefig(fig)
    return fig


def page_table(D, pdf, total):
    fig, ax = setup()
    frame_and_title(ax, "スイッチ穴の中心座標表", "TBL", "—", "—", 4, total)
    ax.text(16, 280, "スイッチ穴の中心（14.0角の中心）。原点＝外形の左下。1uの穴はすべて 14.0 × 14.0 の正方形（カーフ補正前）", fontsize=8.5, va="top")
    cols = 3
    per = math.ceil(len(D["sw"]) / cols)
    for k in range(cols):
        tx = 16 + k * 130
        yy = 268
        TC = [8, (14, "l"), 64, 92]
        trow(ax, tx, yy, ["No", "種類", "X", "Y"], TC, fs=7.2, bold=True)
        yy -= 5
        for s in D["sw"][k * per:(k + 1) * per]:
            trow(ax, tx, yy, [str(s["no"]), s["kind"], f"{s['x']:.2f}", f"{s['y']:.2f}"], TC, fs=7.2)
            yy -= 4.6
    notes(ax, 16, 120, [
        "1. Fusionの例：1か所目を「中心の長方形」14×14で描き、残りは座標表どおりに配置（または「矩形状パターン」で 19.05 ピッチ）",
        "2. 1段の中では X が 19.05 ずつ（1u）並ぶ。段のずれはキーの幅（1.25u・1.5u・1.75u など）による",
        "3. スタビつきの3か所（2u・ISO Enter・スペース）は3枚目の長方形の表で描く",
        "4. いちばん確実なのは DXF（dxf/plate_*.dxf）をスケッチに挿入する方法。座標は同じ",
        f"5. 同じ内容の CSV：case/drawings/switch_cutouts_{g.VER}.csv",
    ])
    pdf.savefig(fig)
    return fig


def page_stiff(D, pdf, total):
    fig, ax = setup()
    frame_and_title(ax, "補強板", "STF", "アクリル 2（押し出し材で可）", "1:1", 5, total)
    x0, y0 = 62, 140
    poly(ax, D["outer"], x0, y0)
    for c, d in D["holes"]:
        circ(ax, c, d, x0, y0, lw=THIN)
    for p in D["stiff"]:
        poly(ax, p, x0, y0, lw=0.45)
    origin_mark(ax, x0, y0)
    ax.text(x0, y0 + g.OUTER_H + 5, "外形・ネジ穴は2枚目と同じ。抜きはトッププレートの穴を全周に広げた形", fontsize=8, va="bottom")
    notes(ax, 16, 118, [
        f"1. 抜き：トッププレートのスイッチ・スタビ穴を全周 {g.STIFF_OFFSET:g} 外側へオフセット（角は直角のまま）。1uは {14 + 2 * g.STIFF_OFFSET:.1f} 角",
        f"   スイッチの爪（{g.STIFF_OFFSET:g}）とPCBマウントスタビのハウジングの逃げ",
        f"2. 抜きと抜きの間が {g.STIFF_MIN_WEB:g} 未満になる所はつなげて1つの穴にする（細い棒が残ると割れる）",
        "   → スタビ穴の周りの細かい凹凸は埋まる。この図とDXFはその処理済み",
        "3. Fusion：トッププレートのスケッチを複製し「オフセット」0.8。スタビ穴の3か所はDXF（dxf/stiffener_*.dxf）を推奨",
        "4. トッププレートとの間は接着しない。ボルト8本で共締め",
    ])
    pdf.savefig(fig)
    return fig


def page_frame(D, pdf, total):
    fig, ax = setup()
    frame_and_title(ax, "枠（左右2分割）", "FRM", "PLA（インフィル高め・壁4周以上）", "1:1（詳細 2:1）", 6, total)
    x0, y0 = 62, 136
    poly(ax, D["frame_outer"], x0, y0)
    poly(ax, D["frame_inner"], x0, y0)
    for c, d in D["holes"]:
        circ(ax, c, d, x0, y0, lw=THIN)
    split = g.SPLIT_X - OX0
    line(ax, [(x0 + split, y0 - 4), (x0 + split, y0 + g.OUTER_H + 4)], lw=THIN, ls=(0, (10, 2, 2, 2)))
    ax.text(x0 + split + 1, y0 - 4, f"分割 X={split:g}", fontsize=7, va="top")
    # USB切り欠き（奥の壁、全高）
    ux = g.USB_X - OX0
    ax.add_patch(Rectangle((x0 + ux - g.USB_W / 2, y0 + g.OUTER_H - g.WALL), g.USB_W, g.WALL, fc="#ddd", ec="k", lw=THICK))
    leader(ax, (x0 + ux + g.USB_W / 2, y0 + g.OUTER_H - 3), (x0 + ux + 20, y0 + g.OUTER_H + 10),
           f"USB切り欠き 幅{g.USB_W:g}（中心X={ux:g}）全高・壁を貫通　※実測で確定")
    # 継ぎ目（ほぞ＋ボルト）の位置
    for yc in [T((0, y))[1] for y in g.joint_wall_y()]:
        ax.add_patch(Rectangle((x0 + split - g.JB_HEAD_SEAT - g.JB_POCKET_L, y0 + yc - g.JB_POCKET_W / 2), g.JB_POCKET_L, g.JB_POCKET_W, fill=False, lw=THIN))
        ax.add_patch(Rectangle((x0 + split + g.JB_NUT_X, y0 + yc - g.JB_NUT_SLOT_W / 2), g.JB_NUT_SLOT_T, g.JB_NUT_SLOT_W, fill=False, lw=THIN))
        ax.add_patch(Rectangle((x0 + split - g.TENON_L, y0 + yc - g.TENON_W / 2), g.TENON_L, g.TENON_W, fill=False, lw=THIN, ls=(0, (2, 1))))
    yj = T((0, g.joint_wall_y()[1]))[1]
    leader(ax, (x0 + split - g.JB_HEAD_SEAT - 8, y0 + yj + g.JB_POCKET_W / 2), (x0 + split - 60, y0 + 30), "継ぎ目：ほぞ＋M3ボルト（前後の壁、詳細は左下）", ha="right")
    origin_mark(ax, x0, y0)
    fi = Polygon(D["frame_inner"]).bounds
    fo = Polygon(D["frame_outer"]).bounds
    hdim(ax, x0 + fi[0], x0 + fi[2], y0 + fi[1] + 10, y0 + fi[1], y0 + fi[1], f"内側 {fi[2] - fi[0]:g}")
    vdim(ax, y0 + fi[1], y0 + fi[3], x0 + fi[2] - 12, x0 + fi[2], f"内側 {fi[3] - fi[1]:g}", right=False)
    hdim(ax, x0 + fo[0], x0 + fo[2], y0 - 9, y0 + fo[1], y0 + fo[1], f"{fo[2] - fo[0]:.1f}（外形−{g.FRAME_INSET:g}×2）", above=False)
    vdim(ax, y0 + fo[1], y0 + fo[3], x0 + g.OUTER_W + 8, x0 + fo[2], f"{fo[3] - fo[1]:.1f}")
    hdim(ax, x0, x0 + fi[0], y0 + 40, y0 + 40, y0 + 40, f"{fi[0]:g}")
    vdim(ax, y0, y0 + fi[1], x0 + 70, x0 + 70, f"{fi[1]:g}")
    ax.text(x0, y0 + g.OUTER_H + 16, "平面図（上から）。外形は2枚目の外形を全周0.3内側へオフセット。内側の角はR4.5・曲率連続（Apple風）", fontsize=8, va="bottom")
    joint_detail(ax, split)
    notes(ax, 175, 118, [
        f"1. 高さ {g.FRAME_H:g}（下面＝ボトムプレートの上面、Z=3）",
        f"2. ネジ穴：手前 φ{g.HOLE_D:g}、奥 φ{g.REAR_HOLE_D:.1f}（全高を貫通）。位置は2枚目",
        f"3. 分割はX={split:g}。左右とも Ender-3 Pro（220角）に収まる",
        f"4. 継ぎ目：右半分のほぞ（{g.TENON_W:g}×{g.TENON_H:g}、長さ{g.TENON_L:g}）を左半分のほぞ穴に差し、",
        f"   M3×{g.JB_L:g}キャップボルトで横から締める。頭とナットは上面から入れる（補強板で隠れる）",
        "5. 印刷の向き：下面（ボトムプレート側）をベッドに。サポート不要",
        "6. 内側の角の正確な形はDXF（dxf/frame_*.dxf）",
    ])
    pdf.savefig(fig)
    return fig


def draw_geom(ax, geom, x0, y0, s, hatch=None, lw=THICK, ls="-"):
    """shapelyの形（穴あきも）を描く。"""
    from matplotlib.path import Path
    from matplotlib.patches import PathPatch
    polys = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
    for P in polys:
        verts, codes = [], []
        for ring in [P.exterior] + list(P.interiors):
            pts = [(x0 + x * s, y0 + y * s) for x, y in ring.coords]
            verts += pts
            codes += [Path.MOVETO] + [Path.LINETO] * (len(pts) - 2) + [Path.CLOSEPOLY]
        ax.add_patch(PathPatch(Path(verts, codes), fc="none", ec="k", lw=lw, ls=ls, hatch=hatch))


def joint_detail(ax, split):
    """継ぎ目の詳細（奥の壁）：上から見た図と、壁の中心で切った断面。尺度 2:1。u＝継ぎ目からのX、v＝壁の中心からのY。"""
    from shapely.geometry import box as B
    S = 2.0
    u0, u1 = -30, 14
    wall = g.WALL - g.FRAME_INSET
    H = g.FRAME_H
    zc = H / 2
    c = g.TENON_CLEAR
    ux0 = 46 - u0 * S                     # u=0（継ぎ目）の紙の上のX
    # ---- 断面（壁の中心、横から）
    zy0 = 30
    leftG = B(u0, 0, 0, H).difference(B(-g.TENON_L - c, -1, 0.01, g.TENON_H + c)).difference(
        B(-g.JB_HEAD_SEAT - g.JB_POCKET_L, zc - g.JB_HEAD_D / 2 - 0.25, -g.JB_HEAD_SEAT, H + 1)).difference(
        B(-g.JB_HEAD_SEAT - 0.01, zc - g.HOLE_D / 2, 0.02, zc + g.HOLE_D / 2))
    rightG = B(0, 0, u1, H).union(B(-g.TENON_L, 0, 0, g.TENON_H)).difference(
        B(g.JB_NUT_X, zc - 5.5 / math.sqrt(3) - 0.1, g.JB_NUT_X + g.JB_NUT_SLOT_T, H + 1)).difference(
        B(-g.TENON_L - 0.01, zc - g.HOLE_D / 2, g.JB_NUT_X + g.JB_NUT_SLOT_T + 3.5, zc + g.HOLE_D / 2))
    draw_geom(ax, leftG, ux0, zy0, S, hatch="////")
    draw_geom(ax, rightG, ux0, zy0, S, hatch="\\\\")
    # ボルトとナット（灰色）
    hs = -g.JB_HEAD_SEAT
    ax.add_patch(Rectangle((ux0 + (hs - g.JB_HEAD_H) * S, zy0 + (zc - g.JB_HEAD_D / 2) * S), g.JB_HEAD_H * S, g.JB_HEAD_D * S, fc="#b9bcc0", ec="k", lw=THIN))
    ax.add_patch(Rectangle((ux0 + hs * S, zy0 + (zc - 1.5) * S), g.JB_L * S, 3 * S, fc="#d5d7da", ec="k", lw=THIN))
    ax.add_patch(Rectangle((ux0 + (g.JB_NUT_X + 0.15) * S, zy0 + (zc - 5.5 / math.sqrt(3)) * S), 2.4 * S, 11 / math.sqrt(3) * S, fc="#9a9da2", ec="k", lw=THIN))
    centerline(ax, (ux0 + (u0 - 2) * S, zy0 + zc * S), (ux0 + (u1 + 2) * S, zy0 + zc * S))
    line(ax, [(ux0, zy0 - 3), (ux0, zy0 + H * S + 3)], lw=THIN, ls=(0, (10, 2, 2, 2)))
    vdim(ax, zy0, zy0 + H * S, ux0 + u0 * S - 4, ux0 + u0 * S, f"{H:g}", right=False)
    vdim(ax, zy0, zy0 + zc * S, ux0 + u1 * S + 5, ux0 + u1 * S, f"{zc:.2f}（ボルトの軸）")
    hdim(ax, ux0 + hs * S, ux0, zy0 - 6, zy0, zy0, f"{g.JB_HEAD_SEAT:g}", above=False)
    hdim(ax, ux0, ux0 + g.JB_NUT_X * S, zy0 - 6, zy0, zy0, f"{g.JB_NUT_X:g}", above=False)
    hdim(ax, ux0 + (hs - g.JB_POCKET_L) * S, ux0 + hs * S, zy0 + H * S + 5, zy0 + H * S, zy0 + H * S, f"{g.JB_POCKET_L:g}（レンチ用）")
    hdim(ax, ux0 + (-g.TENON_L - c) * S, ux0, zy0 + H * S + 5, zy0 + H * S, zy0 + H * S, f"{g.TENON_L + c:.1f}")
    hdim(ax, ux0 + g.JB_NUT_X * S, ux0 + (g.JB_NUT_X + g.JB_NUT_SLOT_T) * S, zy0 + H * S + 5, zy0 + H * S, zy0 + H * S, f"{g.JB_NUT_SLOT_T:g}")
    ax.text(ux0 + u0 * S, zy0 - 13, f"断面（壁の中心）。高さは下面から：ほぞ{g.TENON_H:g}・ほぞ穴{g.TENON_H + c:.1f}、頭のざぐりの底{zc - g.JB_HEAD_D / 2 - 0.25:.2f}、ナットの溝の底{zc - 5.5 / math.sqrt(3) - 0.1:.2f}", fontsize=6.6, va="top")
    # ---- 上から見た図（奥の壁、外側が上）
    py0 = 74
    v0 = -wall / 2
    leftP = B(u0, v0, 0, v0 + wall).difference(B(-g.JB_HEAD_SEAT - g.JB_POCKET_L, -g.JB_POCKET_W / 2, -g.JB_HEAD_SEAT, g.JB_POCKET_W / 2))
    rightP = B(0, v0, u1, v0 + wall).difference(B(g.JB_NUT_X, -g.JB_NUT_SLOT_W / 2, g.JB_NUT_X + g.JB_NUT_SLOT_T, g.JB_NUT_SLOT_W / 2))
    pv0 = py0 + wall / 2 * S
    draw_geom(ax, leftP, ux0, pv0, S)
    draw_geom(ax, rightP, ux0, pv0, S)
    ax.add_patch(Rectangle((ux0 + (-g.TENON_L - c) * S, pv0 + (-g.TENON_W / 2 - c) * S), (g.TENON_L + c) * S, (g.TENON_W + 2 * c) * S, fill=False, lw=THIN, ls=(0, (3, 1.5))))
    ax.add_patch(Rectangle((ux0 + hs * S, pv0 - g.HOLE_D / 2 * S), (g.JB_HEAD_SEAT + g.JB_NUT_X + g.JB_NUT_SLOT_T + 3.5) * S, g.HOLE_D * S, fill=False, lw=THIN, ls=(0, (3, 1.5))))
    centerline(ax, (ux0 + (u0 - 2) * S, pv0), (ux0 + (u1 + 2) * S, pv0))
    vdim(ax, pv0 - g.JB_POCKET_W / 2 * S, pv0 + g.JB_POCKET_W / 2 * S, ux0 + (hs - g.JB_POCKET_L) * S - 4, ux0 + (hs - g.JB_POCKET_L) * S, f"{g.JB_POCKET_W:g}", right=False)
    vdim(ax, pv0 - (g.TENON_W / 2 + c) * S, pv0 + (g.TENON_W / 2 + c) * S, ux0 - 3, ux0 + (-g.TENON_L - c) * S, f"{g.TENON_W + 2 * c:.1f}", right=False)
    vdim(ax, pv0 - g.JB_NUT_SLOT_W / 2 * S, pv0 + g.JB_NUT_SLOT_W / 2 * S, ux0 + u1 * S + 5, ux0 + (g.JB_NUT_X + g.JB_NUT_SLOT_T) * S, f"{g.JB_NUT_SLOT_W:g}（ナット二面幅5.5）")
    vdim(ax, pv0 - wall / 2 * S, pv0 + wall / 2 * S, ux0 + u0 * S - 4, ux0 + u0 * S, f"{wall:g}", right=False)
    ax.text(ux0 + u0 * S, py0 + wall * S + 4, f"継ぎ目の詳細（奥の壁、上から。手前の壁も同じ）　尺度 2:1。左＝左半分、右＝右半分", fontsize=7.5, va="bottom")
    ax.text(ux0 + u0 * S, py0 - 3, f"ほぞ {g.TENON_W:g}×{g.TENON_L:g}（高さ{g.TENON_H:g}、下面から）。ほぞ穴は片側{c:g}大きい（点線）。ボルト穴 φ{g.HOLE_D:g}", fontsize=6.6, va="top")


def page_foot(D, pdf, total):
    fig, ax = setup()
    frame_and_title(ax, "足（4本とも同じ形）", "FT", "PLA（インフィル100%）　数量 4", "2:1", 7, total)
    b0 = D["bars"][0]
    (ax_, ay_), (bx_, by_) = b0["holes"]
    span = abs(bx_ - ax_)
    Lb = span + g.RIB_W
    S = 2.0
    # 平面図
    px0, py0 = 70, 200
    W = g.RIB_W
    r = W / 2
    import numpy as np
    th = np.linspace(-math.pi / 2, math.pi / 2, 40)
    right = [(span / 2 + r * math.cos(t), r * math.sin(t)) for t in th]
    left = [(-span / 2 - r * math.cos(t), -r * math.sin(t)) for t in th]
    pts = right + left
    poly(ax, [(px0 + Lb / 2 * S + x * S, py0 + y * S) for x, y in pts], 0, 0)
    cxp = px0 + Lb / 2 * S
    for sx in (-1, 1):
        hx = cxp + sx * span / 2 * S
        ax.add_patch(Circle((hx, py0), g.HOLE_D / 2 * S, fill=False, lw=THICK))
        rr = g.NUT_POCKET_AF / math.sqrt(3)
        hexp = [(hx + rr * S * math.cos(math.radians(60 * k)), py0 + rr * S * math.sin(math.radians(60 * k))) for k in range(6)]
        ax.add_patch(MPoly(hexp, closed=True, fill=False, lw=THIN, ls=(0, (3, 1.5))))
        centerline(ax, (hx, py0 - 9 * S), (hx, py0 + 9 * S))
    centerline(ax, (px0 - 6, py0), (px0 + Lb * S + 6, py0))
    hdim(ax, px0, px0 + Lb * S, py0 + 12 * S, py0, py0, f"{Lb:.2f}")
    hdim(ax, cxp - span / 2 * S, cxp + span / 2 * S, py0 + 9 * S, py0 + 1.7 * S, py0 + 1.7 * S, f"{span:.2f}（穴の間隔）")
    vdim(ax, py0 - r * S, py0 + r * S, px0 - 8, px0 + r * S, f"{W:g}", right=False)
    leader(ax, (cxp + span / 2 * S + r * S * 0.7, py0 - r * S * 0.7), (cxp + span / 2 * S + 14, py0 - 20), f"両端 R{r:g}")
    leader(ax, (cxp - span / 2 * S + 1.2 * S, py0 - 1.2 * S), (cxp - span / 2 * S + 14, py0 - 24), f"2-φ{g.HOLE_D:g} 貫通")
    leader(ax, (cxp + span / 2 * S - 2.6 * S, py0 - 2.0 * S), (cxp + 20, py0 - 24),
           f"2-六角 二面幅{g.NUT_POCKET_AF:g}（かくれ線、下から深さ{g.feet()[1] - g.FOOT_SKIN:.1f}）", ha="right")
    ax.text(px0, py0 + 26 * S, "平面図（上から＝ボトムプレートに当たる面）　尺度 2:1。六角は辺が長手方向と平行", fontsize=8, va="bottom")
    # 断面 B-B（穴を通る長手方向）：右の穴まわりだけ 4:1
    S2 = 4.0
    sx0, sy0 = 60, 92
    fh = g.feet()[1]
    seg = 22
    ax.add_patch(Rectangle((sx0, sy0), seg * S2, fh * S2, fill=False, lw=THICK))
    hc = sx0 + 12 * S2
    nut = g.NUT_POCKET_AF
    ax.add_patch(Rectangle((hc - nut / 2 * S2, sy0), nut * S2, (fh - g.FOOT_SKIN) * S2, fc="white", ec="k", lw=THICK))
    ax.add_patch(Rectangle((hc - g.HOLE_D / 2 * S2, sy0 + (fh - g.FOOT_SKIN) * S2), g.HOLE_D * S2, g.FOOT_SKIN * S2, fc="white", ec="k", lw=THICK))
    for xa, xb in ((sx0, hc - nut / 2 * S2), (hc + nut / 2 * S2, sx0 + seg * S2)):
        ax.add_patch(Rectangle((xa, sy0), xb - xa, fh * S2, fill=False, hatch="\\\\\\", lw=0))
    for xa, xb in ((hc - nut / 2 * S2, hc - g.HOLE_D / 2 * S2), (hc + g.HOLE_D / 2 * S2, hc + nut / 2 * S2)):
        ax.add_patch(Rectangle((xa, sy0 + (fh - g.FOOT_SKIN) * S2), xb - xa, g.FOOT_SKIN * S2, fill=False, hatch="\\\\\\", lw=0))
    ax.plot([sx0, sx0], [sy0 - 2, sy0 + fh * S2 + 2], color="k", lw=THIN, ls=(0, (6, 2)))
    centerline(ax, (hc, sy0 - 6), (hc, sy0 + fh * S2 + 6))
    vdim(ax, sy0, sy0 + fh * S2, sx0 + seg * S2 + 8, sx0 + seg * S2, f"{fh:g}")
    vdim(ax, sy0, sy0 + (fh - g.FOOT_SKIN) * S2, sx0 - 8, hc - nut / 2 * S2, f"{fh - g.FOOT_SKIN:.1f}（六角の深さ）", right=False)
    vdim(ax, sy0 + (fh - g.FOOT_SKIN) * S2, sy0 + fh * S2, sx0 + seg * S2 + 24, hc + nut / 2 * S2, f"{g.FOOT_SKIN:g}（上の肉）")
    hdim(ax, hc - nut / 2 * S2, hc + nut / 2 * S2, sy0 - 7, sy0, sy0, f"{nut:g}（二面幅）", above=False)
    hdim(ax, hc - g.HOLE_D / 2 * S2, hc + g.HOLE_D / 2 * S2, sy0 + fh * S2 + 6, sy0 + fh * S2, sy0 + fh * S2, f"φ{g.HOLE_D:g}")
    ax.text(sx0, sy0 + fh * S2 + 14, "断面 B-B（穴の中心を通る）　尺度 4:1。上＝ボトムプレート側、下＝机側", fontsize=7.5, va="bottom")
    # 取り付け位置
    tx = 225
    ax.text(tx, 118, "取り付け位置（足の中心、原点基準）", fontsize=7.6, va="top")
    for i, b in enumerate(D["bars"]):
        nm = {"front": "手前", "rear": "奥"}[b["pos"]] + {"left": "左", "right": "右"}[b["side"]]
        trow(ax, tx, 111 - i * 5, [nm, f"X {b['c'][0]:.3f}", f"Y {b['c'][1]:.3f}"], [(0, "l"), 40, 70], fs=7.2)
    notes(ax, 225, 86, [
        f"1. 4本とも同じ形。ナットM3（二面幅5.5・厚さ2.4）を下から入れる",
        f"2. ボルトM3×{g.BOLT_L:g}の先端はナットの下面とほぼ同じ高さ",
        "3. 印刷の向き：上面（ボトムプレート側）をベッドに。六角が上を向く",
        "4. 底に滑り止めゴムを貼ると、ナットも落ちない",
    ])
    pdf.savefig(fig)
    return fig


# ---------- DXF・CSV
def write_dxf(path, layers):
    import ezdxf
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 4         # mm
    msp = doc.modelspace()
    for lname, color, items in layers:
        if lname not in doc.layers:
            doc.layers.add(lname, color=color)
        for it in items:
            if it[0] == "poly":
                msp.add_lwpolyline(it[1], close=True, dxfattribs={"layer": lname})
            elif it[0] == "circle":
                msp.add_circle(it[1], it[2] / 2, dxfattribs={"layer": lname})
            elif it[0] == "line":
                msp.add_line(it[1], it[2], dxfattribs={"layer": lname})
    doc.saveas(path)


def exports(D):
    dd = os.path.join(OUTDIR, "dxf")
    os.makedirs(dd, exist_ok=True)
    out = [("poly", D["outer"])]
    holes = [("circle", c, d) for c, d in D["holes"]]
    write_dxf(os.path.join(dd, f"plate_{g.VER}.dxf"), [("OUTLINE", 7, out), ("HOLES", 1, holes), ("SWITCH", 3, [("poly", p) for p in D["cuts"]])])
    write_dxf(os.path.join(dd, f"stiffener_{g.VER}.dxf"), [("OUTLINE", 7, out), ("HOLES", 1, holes), ("OPENINGS", 3, [("poly", p) for p in D["stiff"]])])
    write_dxf(os.path.join(dd, f"bottom_{g.VER}.dxf"), [("OUTLINE", 7, out), ("HOLES", 1, holes)])
    split = g.SPLIT_X - OX0
    ux = g.USB_X - OX0
    usb = [(ux - g.USB_W / 2, g.OUTER_H - g.WALL), (ux + g.USB_W / 2, g.OUTER_H - g.WALL), (ux + g.USB_W / 2, g.OUTER_H), (ux - g.USB_W / 2, g.OUTER_H)]
    write_dxf(os.path.join(dd, f"frame_{g.VER}.dxf"), [("OUTLINE", 7, [("poly", D["frame_outer"]), ("poly", D["frame_inner"])]),
                                                       ("HOLES", 1, holes), ("USB", 5, [("poly", usb)]),
                                                       ("SPLIT", 2, [("line", (split, -5), (split, g.OUTER_H + 5))])])
    b = D["bars"][0]
    c = b["c"]
    plan = [(x - c[0], y - c[1]) for x, y in b["plan"]]
    hs = [("circle", (h[0] - c[0], h[1] - c[1]), g.HOLE_D) for h in b["holes"]]
    rr = g.NUT_POCKET_AF / math.sqrt(3)
    hexes = [("poly", [(h[0] - c[0] + rr * math.cos(math.radians(60 * k)), h[1] - c[1] + rr * math.sin(math.radians(60 * k))) for k in range(6)]) for h in b["holes"]]
    write_dxf(os.path.join(dd, f"foot_{g.VER}.dxf"), [("OUTLINE", 7, [("poly", plan)]), ("HOLES", 1, hs), ("NUT_POCKET", 3, hexes)])
    # 足の位置（ボトムプレートの座標に置いた版）
    allb = []
    for b in D["bars"]:
        allb.append(("poly", b["plan"]))
    write_dxf(os.path.join(dd, f"feet_layout_{g.VER}.dxf"), [("OUTLINE", 7, out), ("FEET", 4, allb), ("HOLES", 1, holes)])
    with open(os.path.join(OUTDIR, f"switch_cutouts_{g.VER}.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["no", "kind", "center_x_mm", "center_y_mm", "w_mm", "h_mm"])
        for s in D["sw"]:
            if s["kind"] == "1u":
                w.writerow([s["no"], "1u", f"{s['x']:.3f}", f"{s['y']:.3f}", "14.000", "14.000"])
            else:
                for name, X, Y, ww, hh in stab_rects(s)[0]:
                    w.writerow([s["no"], f"{s['kind']}:{name}", f"{X:.3f}", f"{Y:.3f}", f"{ww:.3f}", f"{hh:.3f}"])


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    D = data()
    assert len(D["sw"]) == 65
    pages = [page_assembly, page_outline, page_top, page_table, page_stiff, page_frame, page_foot]
    pdfp = os.path.join(OUTDIR, f"DZ60_drawings_{g.VER}.pdf")
    with PdfPages(pdfp) as pdf:
        for i, fn in enumerate(pages, 1):
            fig = fn(D, pdf, len(pages))
            fig.savefig(os.path.join(g.ROOT, f"docs/img/drawings_{g.VER}_p{i}.png"), dpi=90)
            plt.close(fig)
    exports(D)
    print(pdfp)


if __name__ == "__main__":
    main()
