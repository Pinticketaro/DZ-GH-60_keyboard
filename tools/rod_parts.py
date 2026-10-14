"""真鍮丸棒の穴あけ治具（3Dプリント）と加工図（PDF/PNG）を作る。

出力
  case/stl/rod_jig_left_<ver>.stl   … 左端基準の治具（左から1・2番目の穴）
  case/stl/rod_jig_right_<ver>.stl  … 右端基準の治具（右から1・2番目の穴）
  case/rod_drawing_<ver>.pdf / docs/img/rod_drawing_<ver>.png … 加工図（持ち込み・外注用）

治具の使い方：丸棒を穴に差し込み、奥の壁に突き当てる → 上のガイド穴からφ2.5で下穴 → 治具を外してM3タップ。
印刷：図の向きのまま（底面を下）。丸棒の穴は上をとがらせた形（ティアドロップ）にしてあるので、サポートなしで刷れる。
"""
import math
import os
import sys

import manifold3d as m3

sys.path.insert(0, os.path.dirname(__file__))
import build3d as b3
import gen_case as g

BORE_CLEAR = 0.2      # 丸棒の通る穴：直径＋0.4
GUIDE_D = 2.7         # ドリルガイド穴（φ2.5ドリル＋印刷で縮む分）
WALL_END = 4.0        # 突き当ての壁
BOTTOM = 3.0
TOP = 10.0            # 丸棒の上〜治具上面（ガイドの長さ）
WIDTH = 26.0
MARGIN = 10.0         # いちばん遠い穴から治具の開いた端まで


def teardrop(r, n=64):
    pts = []
    for k in range(n + 1):
        a = math.radians(135 + (270 * k / n))       # 左上(135°)から下を回って右上(405°=45°)までの円弧
        pts.append((r * math.cos(a), r * math.sin(a)))
    pts.append((0, r * math.sqrt(2)))               # 上のとがり（45°の斜面）
    return pts


def jig(dists, label):
    """dists: 突き当て面（丸棒の端）からの穴の距離。X=0が突き当て面、+Xが開いた側。"""
    L = max(dists) + MARGIN
    D = g.ROD_D + 2 * BORE_CLEAR
    H = BOTTOM + D + TOP
    zc = BOTTOM + D / 2
    body = m3.Manifold.cube([L + WALL_END, WIDTH, H]).translate([-WALL_END, -WIDTH / 2, 0])
    # 丸棒の穴（X方向）。断面はYZ面のティアドロップ
    td = [(y, z + zc) for (y, z) in teardrop(D / 2)]
    # extrude はZ方向。Y軸まわりに90°回すと (u,v,w)→(w,v,-u) なので、断面は (u,v)=(-z,y) で作る
    # （座標を入れ替えると向きが裏返るので、点の順番を逆にして正の向きに戻す）
    sec = [(-z, y) for (y, z) in td]
    area2 = sum(sec[i][0] * sec[(i + 1) % len(sec)][1] - sec[(i + 1) % len(sec)][0] * sec[i][1] for i in range(len(sec)))
    if area2 < 0:
        sec = sec[::-1]
    bore = m3.Manifold.extrude(m3.CrossSection([sec]), L + 1).rotate([0, 90, 0])
    body = body - bore
    for d in dists:
        body = body - m3.Manifold.cylinder(H, GUIDE_D / 2, GUIDE_D / 2, 32).translate([d, 0, zc])
    # 突き当て壁ののぞき穴（丸棒の端が当たっているか見る）
    body = body - m3.Manifold.cylinder(WALL_END + 2, 2.0, 2.0, 24).rotate([0, 90, 0]).translate([-WALL_END - 1, 0, zc])
    return body, L


def check_bore(mf):
    """丸棒の穴が丸棒の中心線の真上をガイドしているか、断面の寸法を確認する。"""
    bb = mf.bounding_box()
    return [round(v, 2) for v in bb]


def drawing(path_pdf, path_png):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    from matplotlib.patches import Rectangle, Circle
    for f in font_manager.findSystemFonts():
        if "NotoSansCJK" in f:
            font_manager.fontManager.addfont(f)
    plt.rcParams["font.family"] = "Noto Sans CJK JP"
    r = g.rod()
    L, D = r["length"], g.ROD_D
    xs = r["holes_from_left_end"]
    fig = plt.figure(figsize=(16.5, 11.7))      # A3横
    ax = fig.add_axes([0.04, 0.42, 0.92, 0.5])
    ax.add_patch(Rectangle((0, 0), L, D, fc="#f3e4c4", ec="#000", lw=1.2))
    ax.plot([-6, L + 6], [D / 2, D / 2], color="#888", lw=0.6, ls="-.")
    for x in xs:
        ax.add_patch(Rectangle((x - g.ROD_TAP_DRILL / 2, D - g.ROD_HOLE_DEPTH), g.ROD_TAP_DRILL, g.ROD_HOLE_DEPTH,
                               fc="white", ec="#000", lw=0.8, ls="--"))
        ax.plot([x, x], [D + 2, D + 4 + 5 * xs.index(x)], color="#c00", lw=0.8)
        ax.annotate("", xy=(0, D + 4 + 5 * xs.index(x)), xytext=(x, D + 4 + 5 * xs.index(x)),
                    arrowprops=dict(arrowstyle="<->", color="#c00", lw=0.8))
        ax.text(x + 2, D + 4.6 + 5 * xs.index(x), f"{x:.2f}", color="#c00", fontsize=11)
    ax.annotate("", xy=(0, -6), xytext=(L, -6), arrowprops=dict(arrowstyle="<->", lw=0.8))
    ax.text(L / 2, -10, f"{L:.1f} ±0.3", ha="center", fontsize=12)
    ax.annotate("", xy=(L + 8, 0), xytext=(L + 8, D), arrowprops=dict(arrowstyle="<->", lw=0.8))
    ax.text(L + 10, D / 2, f"φ{D:g}", va="center", fontsize=12)
    ax.set_xlim(-15, L + 30)
    ax.set_ylim(-16, D + 30)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(f"真鍮丸棒 加工図（{g.VER}）　側面図：穴の位置は左端からの距離（mm）", fontsize=14, loc="left")
    # 断面図
    ax2 = fig.add_axes([0.04, 0.08, 0.22, 0.3])
    ax2.add_patch(Circle((0, 0), D / 2, fc="#f3e4c4", ec="#000", lw=1.2))
    ax2.add_patch(Rectangle((-g.ROD_TAP_DRILL / 2, D / 2 - g.ROD_HOLE_DEPTH), g.ROD_TAP_DRILL, g.ROD_HOLE_DEPTH,
                            fc="white", ec="#000", lw=0.8, ls="--"))
    ax2.annotate("", xy=(4.5, D / 2), xytext=(4.5, D / 2 - g.ROD_HOLE_DEPTH), arrowprops=dict(arrowstyle="<->", lw=0.8))
    ax2.text(5, D / 2 - g.ROD_HOLE_DEPTH / 2, f"深さ{g.ROD_HOLE_DEPTH:g}", va="center", fontsize=11)
    ax2.set_xlim(-10, 14)
    ax2.set_ylim(-9, 10)
    ax2.set_aspect("equal")
    ax2.axis("off")
    ax2.set_title("断面（穴は中心に向かって垂直）", fontsize=12)
    engage = g.ROD_BOLT_L - (g.TOP_T + g.STIFF_T + g.FRAME_H + g.BOTTOM_T) - g.rod_top_gap()
    notes = [
        "材料：快削黄銅 C3604　丸棒 φ" + f"{D:g}",
        f"長さ：{L:.1f} ±0.3　両端面：直角に仕上げ、C0.5面取り",
        f"横穴：4か所。下穴φ{g.ROD_TAP_DRILL} 深さ{g.ROD_HOLE_DEPTH:g} → M3×0.5 タップ（有効ねじ深さ5以上）",
        "4穴は同じ母線（一直線）上、丸棒の中心軸に向かって垂直",
        f"穴位置の許容：±0.3（相手側の穴をφ{g.REAR_HOLE_D:g}にしてある）",
        f"使用ボルト：M3×{g.ROD_BOLT_L:g} ボタンヘッド（ねじ込み約{engage:.1f}mm）",
        "表面：仕上げ自由（磨き・ヘアライン）。変色を止めるならクリア塗装",
    ]
    fig.text(0.32, 0.36, "\n".join("・" + n for n in notes), fontsize=13, va="top", linespacing=1.8)
    fig.savefig(path_pdf)
    fig.savefig(path_png, dpi=80)


def main():
    r = g.rod()
    L = r["length"]
    left_d = [r["holes_from_left_end"][0], r["holes_from_left_end"][1]]
    right_d = [round(L - r["holes_from_left_end"][3], 2), round(L - r["holes_from_left_end"][2], 2)]
    out = os.path.join(g.ROOT, "case/stl")
    os.makedirs(out, exist_ok=True)
    for name, d in (("left", left_d), ("right", right_d)):
        mf, jl = jig(d, name)
        b3.to_trimesh(mf).export(os.path.join(out, f"rod_jig_{name}_{g.VER}.stl"))
        bb = mf.bounding_box()
        print(name, "holes from rod end", d, "jig size", [round(bb[i + 3] - bb[i], 1) for i in range(3)],
              "watertight", b3.to_trimesh(mf).is_watertight)
    # 加工図は rod_drawing.py（図枠・表題欄つき）で作る
    import rod_drawing
    rod_drawing.main()


if __name__ == "__main__":
    main()
