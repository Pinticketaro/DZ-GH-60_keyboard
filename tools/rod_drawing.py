"""真鍮丸棒の加工図（A3横・第三角法・図枠と表題欄つき）を作る。加工を頼む人にそのまま渡せる形。

出力: case/rod_drawing_<ver>.pdf（印刷用、正面図・平面図は1:1）、docs/img/rod_drawing_<ver>.png
使い方: python3 tools/rod_drawing.py
"""
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Arc, Circle, Polygon as MPoly, Rectangle

sys.path.insert(0, os.path.dirname(__file__))
import gen_case as g

for f in font_manager.findSystemFonts():
    if "NotoSansCJK" in f:
        font_manager.fontManager.addfont(f)
plt.rcParams["font.family"] = "Noto Sans CJK JP"

THICK, THIN = 0.7, 0.3          # 外形線・細線（図上のpt）
FS = 7.0                        # 寸法文字（pt）
POS_TOL = 0.1                   # 穴位置の公差
LEN_TOL = 0.2                   # 全長の公差


def setup():
    fig = plt.figure(figsize=(420 / 25.4, 297 / 25.4))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 420)
    ax.set_ylim(0, 297)
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax


def line(ax, pts, lw=THIN, ls="-", color="k"):
    xs, ys = zip(*pts)
    ax.plot(xs, ys, lw=lw, ls=ls, color=color, solid_capstyle="butt")


def arrow(ax, p, d, size=2.2):
    """p: 矢の先、d: 矢の向き（単位ベクトル、先の方向）"""
    dx, dy = d
    nx, ny = -dy, dx
    b = (p[0] - dx * size, p[1] - dy * size)
    ax.add_patch(MPoly([p, (b[0] + nx * size * 0.28, b[1] + ny * size * 0.28), (b[0] - nx * size * 0.28, b[1] - ny * size * 0.28)],
                       closed=True, fc="k", ec="k", lw=0.2))


def hdim(ax, x0, x1, y, yref0, yref1, text, above=True, ext=1.5):
    """水平寸法：x0〜x1、寸法線の高さy、補助線はyref0/yref1から"""
    for x, yr in ((x0, yref0), (x1, yref1)):
        line(ax, [(x, yr + (1 if y > yr else -1)), (x, y + (ext if y > yr else -ext))])
    line(ax, [(x0, y), (x1, y)])
    arrow(ax, (x0, y), (-1, 0))
    arrow(ax, (x1, y), (1, 0))
    ax.text((x0 + x1) / 2, y + (0.8 if above else -0.8), text, ha="center", va="bottom" if above else "top", fontsize=FS)


def vdim(ax, y0, y1, x, xref, text, right=True, ext=1.5):
    for y in (y0, y1):
        line(ax, [(xref + (1 if x > xref else -1), y), (x + (ext if x > xref else -ext), y)])
    line(ax, [(x, y0), (x, y1)])
    arrow(ax, (x, y0), (0, -1))
    arrow(ax, (x, y1), (0, 1))
    ax.text(x + (1.0 if right else -1.0), (y0 + y1) / 2, text, ha="left" if right else "right", va="center",
            fontsize=FS, rotation=0)


def leader(ax, p, q, text, ha="left"):
    line(ax, [p, q])
    line(ax, [q, (q[0] + (14 if ha == "left" else -14), q[1])])
    arrow(ax, p, ((p[0] - q[0]) / math.dist(p, q), (p[1] - q[1]) / math.dist(p, q)), 2.0)
    ax.text(q[0] + (1 if ha == "left" else -1), q[1] + 0.8, text, ha=ha, va="bottom", fontsize=FS)


def centerline(ax, p, q):
    line(ax, [p, q], lw=THIN, ls=(0, (8, 2, 1.5, 2)))


def main():
    r = g.rod()
    L, D = r["length"], g.ROD_D
    R = D / 2
    xs_ = r["holes_from_left_end"]
    flat_w = g.ROD_FLAT_W
    fd = g.rod_flat_depth()
    H = D - fd                                  # 平面から下端まで
    drill_d, drill_depth, tap_depth = g.ROD_TAP_DRILL, g.rod_hole_len(), g.rod_tap_len()
    thru = g.ROD_HOLE_THROUGH
    engage = g.ROD_BOLT_L - (g.TOP_T + g.STIFF_T + g.FRAME_H + g.BOTTOM_T) + g.rod_hole_top_z()
    tape = g.ROD_TAPE and flat_w <= 0
    gw, gd = g.GROOVE_W, g.GROOVE_DEPTH
    Dg = D - 2 * gd                             # 溝底の直径

    def stepped(y_edge, sign):
        """外形線（上下の縁）を溝の所で内側へ段付きにした折れ線。sign=+1は上側の縁。"""
        pts = [(X0, y_edge)]
        for x in xs_:
            a, b = X0 + x - gw / 2, X0 + x + gw / 2
            pts += [(a, y_edge), (a, y_edge - sign * gd), (b, y_edge - sign * gd), (b, y_edge)]
        pts.append((X0 + L, y_edge))
        return pts

    fig, ax = setup()
    # 図枠
    ax.add_patch(Rectangle((10, 10), 400, 277, fill=False, lw=1.0))
    X0 = 55                                     # 丸棒の左端（図上）

    # ---- 平面図（上から見た図。第三角法なので正面図の上に置く）
    yt = 222
    if tape:
        line(ax, stepped(yt + R, 1), lw=THICK)
        line(ax, stepped(yt - R, -1), lw=THICK)
        line(ax, [(X0, yt - R), (X0, yt + R)], lw=THICK)
        line(ax, [(X0 + L, yt - R), (X0 + L, yt + R)], lw=THICK)
        for x in xs_:   # 溝の両肩（稜線）
            for xx in (X0 + x - gw / 2, X0 + x + gw / 2):
                line(ax, [(xx, yt - R + gd), (xx, yt + R - gd)], lw=THIN)
    else:
        ax.add_patch(Rectangle((X0, yt - R), L, D, fill=False, lw=THICK))
    if flat_w > 0:
        line(ax, [(X0, yt - flat_w / 2), (X0 + L, yt - flat_w / 2)], lw=THICK)
        line(ax, [(X0, yt + flat_w / 2), (X0 + L, yt + flat_w / 2)], lw=THICK)
    # 面取り
    for xe in (X0, X0 + L):
        s = 1 if xe == X0 else -1
        line(ax, [(xe + s * 0.5, yt - R), (xe + s * 0.5, yt + R)], lw=THIN)
    centerline(ax, (X0 - 6, yt), (X0 + L + 6, yt))
    for x in xs_:
        cx = X0 + x
        ax.add_patch(Circle((cx, yt), drill_d / 2, fill=False, lw=THICK))
        ax.add_patch(Arc((cx, yt), 3.0, 3.0, theta1=100, theta2=370, lw=THIN))   # めねじ（3/4円）
        centerline(ax, (cx, yt - 4.5), (cx, yt + 4.5))
    # 穴位置（左端基準の累進寸法）
    for k, x in enumerate(xs_):
        y = yt + R + 6 + 5.5 * k
        hdim(ax, X0, X0 + x, y, yt + R, yt + 2, f"{x:.2f}±{POS_TOL}")
    if flat_w > 0:
        vdim(ax, yt - flat_w / 2, yt + flat_w / 2, X0 + L + 10, X0 + L, f"{flat_w:g}（平面の幅）")
        vdim(ax, yt - R, yt + R, X0 - 10, X0, f"φ{D:g}", right=False)
    leader(ax, (X0 + xs_[0] + 1.1, yt - 1.1), (X0 + 22, yt - 16),
           (f"4-M3×0.5 貫通（下穴φ{drill_d} 貫通）" if thru else f"4-M3×0.5 ねじ深さ{tap_depth:g}／下穴φ{drill_d} 深さ{drill_depth:g}（{'平面' if flat_w > 0 else ('溝底' if tape else '上端')}から）"))
    if tape:
        cx2 = X0 + xs_[1]
        hdim(ax, cx2 - gw / 2, cx2 + gw / 2, yt - R - 7, yt - R + gd, yt - R + gd, f"{gw:g}±0.1", above=False)
        vdim(ax, yt - R, yt + R, X0 - 10, X0, f"φ{D:g}", right=False)
    ax.text(X0, yt + R + 6 + 5.5 * 4 + 4, "平面図（上面）　尺度 1:1", fontsize=9)

    # ---- 正面図（横から見た図）
    yf = 150                                     # 下端
    top = yf + H
    if tape:
        line(ax, stepped(yf + D, 1), lw=THICK)
        line(ax, stepped(yf, -1), lw=THICK)
        line(ax, [(X0, yf), (X0, yf + D)], lw=THICK)
        line(ax, [(X0 + L, yf), (X0 + L, yf + D)], lw=THICK)
        for x in xs_:
            for xx in (X0 + x - gw / 2, X0 + x + gw / 2):
                line(ax, [(xx, yf + gd), (xx, yf + D - gd)], lw=THIN)
        top = yf + D - gd                       # ねじ穴の入口＝溝底
    else:
        ax.add_patch(Rectangle((X0, yf), L, H, fill=False, lw=THICK))
    centerline(ax, (X0 - 6, yf + R), (X0 + L + 6, yf + R))
    for x in xs_:
        cx = X0 + x
        # 下穴（かくれ線）と先端118°、ねじ（かくれ線）
        line(ax, [(cx - drill_d / 2, top), (cx - drill_d / 2, top - drill_depth)], ls=(0, (3, 1.5)))
        line(ax, [(cx + drill_d / 2, top), (cx + drill_d / 2, top - drill_depth)], ls=(0, (3, 1.5)))
        tip = drill_d / 2 / math.tan(math.radians(59))
        if not thru:
            line(ax, [(cx - drill_d / 2, top - drill_depth), (cx, top - drill_depth - tip), (cx + drill_d / 2, top - drill_depth)],
                 ls=(0, (3, 1.5)))
        line(ax, [(cx - 1.5, top), (cx - 1.5, top - tap_depth)], ls=(0, (1.5, 1)))
        line(ax, [(cx + 1.5, top), (cx + 1.5, top - tap_depth)], ls=(0, (1.5, 1)))
        centerline(ax, (cx, top + 3), (cx, yf - 3))
    hdim(ax, X0, X0 + L, yf - 12, yf, yf, f"{L:.1f}±{LEN_TOL}", above=False)
    if flat_w > 0:
        vdim(ax, yf, top, X0 + L + 10, X0 + L, f"{H:.2f}±0.1（平面まで）")
    if tape:
        cx3 = X0 + xs_[1]
        leader(ax, (cx3 + gw / 2 - 1, yf + D - gd), (cx3 + 18, yf + D + 9),
               f"4-溝 φ{Dg:g}±0.05（深さ{gd:g}）幅{gw:g}±0.1、ねじ穴を中心")
    if flat_w <= 0:
        vdim(ax, yf, yf + D, X0 - 10, X0, f"φ{D:g}", right=False)
    leader(ax, (X0 + L - 0.3, top - 0.3), (X0 + L - 25, top + 10), "C0.5（両端）", ha="right")
    # 断面の切断線 A-A（1番目の穴）
    xa = X0 + xs_[0]
    line(ax, [(xa, top + 6), (xa, top + 2)], lw=THICK)
    line(ax, [(xa, yf - 2), (xa, yf - 6)], lw=THICK)
    ax.text(xa + 1.5, top + 4.5, "A", fontsize=9)
    ax.text(xa + 1.5, yf - 7.5, "A", fontsize=9)
    ax.text(X0, yf - 22, "正面図　尺度 1:1", fontsize=9)

    # ---- 断面 A-A（尺度 5:1）
    S = 5.0
    cxs, cys = 95, 75
    if tape:
        ax.add_patch(Circle((cxs, cys), S * R, fill=False, lw=THIN))            # 溝の外の外周（奥に見える）
        ax.add_patch(Circle((cxs, cys), S * Dg / 2, fill=False, lw=THICK, hatch="////"))
    elif flat_w > 0:
        a = math.degrees(math.asin((flat_w / 2) / R))
        arc_pts = [(cxs + S * R * math.sin(math.radians(t)), cys + S * R * math.cos(math.radians(t)))
                   for t in [a + (360 - 2 * a) * k / 200 for k in range(201)]]
        ax.add_patch(MPoly(arc_pts, closed=True, fill=False, lw=THICK, hatch="////", ec="k"))
    else:
        ax.add_patch(Circle((cxs, cys), S * R, fill=False, lw=THICK, hatch="////"))
    ytop = cys + S * (Dg / 2 if tape else (R - fd))
    ax.add_patch(Rectangle((cxs - S * drill_d / 2, ytop - S * drill_depth), S * drill_d, S * drill_depth, fc="white", ec="white"))
    line(ax, [(cxs - S * drill_d / 2, ytop), (cxs - S * drill_d / 2, ytop - S * drill_depth)], lw=THICK)
    line(ax, [(cxs + S * drill_d / 2, ytop), (cxs + S * drill_d / 2, ytop - S * drill_depth)], lw=THICK)
    tip = drill_d / 2 / math.tan(math.radians(59))
    if not thru:
        ax.add_patch(MPoly([(cxs - S * drill_d / 2, ytop - S * drill_depth), (cxs, ytop - S * (drill_depth + tip)),
                            (cxs + S * drill_d / 2, ytop - S * drill_depth)], closed=True, fc="white", ec="k", lw=THICK))
    line(ax, [(cxs - S * 1.5, ytop), (cxs - S * 1.5, ytop - S * tap_depth)], lw=THIN)
    line(ax, [(cxs + S * 1.5, ytop), (cxs + S * 1.5, ytop - S * tap_depth)], lw=THIN)
    centerline(ax, (cxs, ytop + 6), (cxs, cys - S * R - 6))
    centerline(ax, (cxs - S * R - 6, cys), (cxs + S * R + 6, cys))
    if thru:
        ax.text(cxs + S * R + 8, cys, f"M3×0.5 貫通\n（下穴φ{drill_d} 貫通）", fontsize=8.5, va="center")
    else:
        vdim(ax, ytop - S * tap_depth, ytop, cxs + S * R + 10, cxs + S * 1.5, f"ねじ深さ {tap_depth:g}")
        vdim(ax, ytop - S * drill_depth, ytop, cxs + S * R + 26, cxs + S * drill_d / 2, f"下穴深さ {drill_depth:g}")
    if tape:
        hdim(ax, cxs - S * Dg / 2, cxs + S * Dg / 2, cys - S * R - 7, cys, cys, f"φ{Dg:g}（溝底）", above=False)
        hdim(ax, cxs - S * R, cxs + S * R, cys + S * R + 9, cys, cys, f"φ{D:g}")
    else:
        vdim(ax, cys - S * R, ytop, cxs - S * R - 10, cxs - S * R, f"{H:.2f}", right=False)
    if flat_w > 0:
        hdim(ax, cxs - S * flat_w / 2, cxs + S * flat_w / 2, ytop + 9, ytop, ytop, f"{flat_w:g}")
    ax.text(cxs - 30, cys - S * R - 16, "断面 A-A　尺度 5:1", fontsize=9)

    # ---- 注記
    notes = [
        "注記",
        f"1. 材質：C3604BD（快削黄銅 引抜棒）φ{D:g}",
        f"2. 全長 {L:.1f}±{LEN_TOL}。両端面は軸に直角に仕上げ、C0.5",
        (f"3. 上面に幅{flat_w:g}の平面を全長にわたり加工（平面から下端まで{H:.2f}、削り深さ約{fd:.2f}）" if flat_w > 0
         else (f"3. ねじ穴を中心に全周の溝×4：幅{gw:g}±0.1、溝底φ{Dg:g}±0.05（深さ{gd:g}）。溝の角は糸面取り（旋盤）" if tape
               else "3. 平面加工なし")),
(f"4. 4-M3×0.5 めねじ：下穴φ{drill_d} 貫通、タップ貫通（溝底から反対側の溝底まで{drill_depth:g}）" if thru else
         f"4. 4-M3×0.5 めねじ：下穴φ{drill_d} 深さ{drill_depth:g}（{'溝底' if tape else ('平面' if flat_w > 0 else '上端')}から）、有効ねじ深さ{tap_depth:g}以上"),
        f"5. ねじ穴は{'平面' if flat_w > 0 else '軸'}に直角、4穴とも{'平面の幅の中央' if flat_w > 0 else '同一母線'}の一直線上",
        f"6. 穴位置は左端基準、公差±{POS_TOL}（相手側の穴はφ{g.REAR_HOLE_D:g}）",
        "7. 指示のない寸法公差：JIS B 0405 中級（m）",
        "8. 全周バリなきこと。表面処理なし（磨き・クリア塗装は後工程で行う）。端面は旋盤仕上げ（刃物目のまま）",
        f"9. 使用ボルト：M3×{g.ROD_BOLT_L:g} ボタンヘッド（ねじ込み約{engage:.1f}" + (f"、先端は下の出口から{drill_depth - engage:.1f}手前）" if thru else "）"),
    ] + ([f"10. 組立時、溝にゴムテープ（幅{g.TAPE_W:g}・厚さ{g.TAPE_T:g}）を巻く（加工範囲外）。ボルトはテープを貫通"] if tape else [])
    ax.text(205, 118, "\n".join(notes), fontsize=8.2, va="top", linespacing=1.75)

    # ---- 表題欄
    bx, by, bw, bh = 250, 10, 160, 42
    ax.add_patch(Rectangle((bx, by), bw, bh, fill=False, lw=1.0))
    rows = [("品名", "キーボード 奥側の足（真鍮丸棒）"), ("図番", f"DZ60-ROD-{g.VER}"), ("材質", f"C3604BD φ{D:g}　数量 1"),
            ("尺度", "1:1（断面 5:1）　単位 mm"), ("投影法", "第三角法"), ("日付", "2026-10-15　作成：")]
    rh = bh / len(rows)
    for k, (kname, val) in enumerate(rows):
        yy = by + bh - (k + 1) * rh
        line(ax, [(bx, yy), (bx + bw, yy)], lw=0.4)
        ax.text(bx + 2, yy + rh / 2, kname, va="center", fontsize=7.5)
        ax.text(bx + 20, yy + rh / 2, val, va="center", fontsize=8.5)
    line(ax, [(bx + 18, by), (bx + 18, by + bh)], lw=0.4)
    # 第三角法の記号
    sx, sy = bx + 128, by + rh * 1.5
    ax.add_patch(MPoly([(sx, sy - 2.5), (sx + 9, sy - 4), (sx + 9, sy + 4), (sx, sy + 2.5)], closed=True, fill=False, lw=0.5))
    ax.add_patch(Circle((sx + 20, sy), 4, fill=False, lw=0.5))
    ax.add_patch(Circle((sx + 20, sy), 2.5, fill=False, lw=0.5))
    ax.text(410, 290, f"DZ-GH-60_keyboard / {g.VER}", ha="right", fontsize=7, color="#555")

    pdf = os.path.join(g.ROOT, f"case/rod_drawing_{g.VER}.pdf")
    png = os.path.join(g.ROOT, f"docs/img/rod_drawing_{g.VER}.png")
    fig.savefig(pdf)
    fig.savefig(png, dpi=110)
    print(pdf)


if __name__ == "__main__":
    main()
