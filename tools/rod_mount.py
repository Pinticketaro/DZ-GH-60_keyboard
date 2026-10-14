"""真鍮丸棒の固定方法の断面図 docs/img/rod_mount_<ver>.png（後ろのネジ位置、傾き0°で表示）"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Circle, Polygon as MPoly, Rectangle

sys.path.insert(0, os.path.dirname(__file__))
import gen_case as g

for f in font_manager.findSystemFonts():
    if "NotoSansCJK" in f:
        font_manager.fontManager.addfont(f)
plt.rcParams["font.family"] = "Noto Sans CJK JP"


def main():
    import math
    fig, ax = plt.subplots(figsize=(10.5, 7))
    D, W = g.ROD_D, g.WALL
    ry = -g.OY + g.rod()["y"]
    gap = g.rod_top_gap()
    zs = 0.0
    for name, t, c in [("ボトムプレート（アクリル）", g.BOTTOM_T, "#cfe6f2"), ("枠（PLA）", g.FRAME_H, "#f1dfc4"),
                       ("補強板（アクリル）", g.STIFF_T, "#a9d3e8"), ("トッププレート（アクリル）", g.TOP_T, "#cfe6f2")]:
        w = W if name.startswith("枠") else 40
        ax.add_patch(Rectangle((0, zs), w, t, fc=c, ec="#4a8aa8" if "アクリル" in name else "#a7834f"))
        ax.text(41, zs + t / 2, f"{name} {t:g}", va="center", fontsize=10)
        zs += t
    zrod = -gap - D / 2
    if g.SADDLE:
        s = g.saddle()
        R = s["R"]
        pts = [(ry - s["w"] / 2, 0), (ry + s["w"] / 2, 0), (ry + s["w"] / 2, -s["height"])]
        a0 = math.asin((s["w"] / 2) / R)
        for k in range(41):
            a = a0 - 2 * a0 * k / 40
            pts.append((ry + R * math.sin(a), zrod + R * math.cos(a)))
        pts.append((ry - s["w"] / 2, -s["height"]))
        ax.add_patch(MPoly(pts, closed=True, fc="#e8d9bf", ec="#a7834f"))
        lab = "前後一体の足（PLA）の奥側＝丸棒受け" if g.FOOT_STYLE == "ribs" else "受け台（PLA・3Dプリント）"
        ax.annotate(f"{lab}\n上は平ら・下は丸棒に沿う凹面、最も薄い所{g.SADDLE_T_MIN:g}mm",
                    xy=(ry + s["w"] / 2 - 0.5, -1.2), xytext=(ry + 30, -4.0), fontsize=10, color="#7a5a2a",
                    arrowprops=dict(arrowstyle="->", color="#7a5a2a"))
    ax.add_patch(Circle((ry, zrod), D / 2, fc="#d4a85a", ec="#8a6a2a"))
    ax.add_patch(Rectangle((ry - 1.5, zs - g.ROD_BOLT_L), 3.0, g.ROD_BOLT_L, fc="#9a9da2", ec="#555"))
    ax.add_patch(Rectangle((ry - 2.85, zs), 5.7, 1.65, fc="#9a9da2", ec="#555"))
    ax.add_patch(Rectangle((ry - g.ROD_TAP_DRILL / 2, -gap - g.ROD_HOLE_DEPTH), g.ROD_TAP_DRILL, g.ROD_HOLE_DEPTH,
                           fc="none", ec="#c33", ls="--"))
    engage = g.ROD_BOLT_L - zs - gap
    ax.annotate(f"M3×{g.ROD_BOLT_L:g} ボタンヘッド（上から全層を通す。穴はφ{g.REAR_HOLE_D:g}）", xy=(ry, zs + 1.6),
                xytext=(ry + 8, zs + 6), fontsize=10, arrowprops=dict(arrowstyle="->"))
    ax.annotate(f"丸棒のめねじにねじ込む（{engage:.1f}mm）\n下穴φ{g.ROD_TAP_DRILL}・深さ{g.ROD_HOLE_DEPTH:g}・M3タップ",
                xy=(ry + 1.3, -gap - 4), xytext=(ry + 30, -12.5), fontsize=10, color="#c33",
                arrowprops=dict(arrowstyle="->", color="#c33"))
    ax.annotate(f"真鍮丸棒 φ{D:g}（4本のボルトで引き寄せて固定）", xy=(ry + 4, zrod - D / 2 + 2), xytext=(ry + 30, -21),
                fontsize=10, color="#8a6a2a", arrowprops=dict(arrowstyle="->", color="#8a6a2a"))
    zdesk = zrod - D / 2
    ax.plot([-5, 95], [zdesk, zdesk], color="#888", lw=1)
    ax.text(-4, zdesk - 2.2, "机（薄いゴムを貼る）", fontsize=10, color="#666")
    ax.text(0, zs + 9, "奥 ←", fontsize=10)
    ax.text(30, zs + 9, "→ 手前", fontsize=10)
    ax.set_xlim(-6, 96)
    ax.set_ylim(zdesk - 8, zs + 12)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(f"真鍮丸棒の固定 {g.VER}（後ろのネジ位置での断面・傾き0°で表示）", fontsize=12)
    path = os.path.join(g.ROOT, f"docs/img/rod_mount_{g.VER}.png")
    fig.savefig(path, dpi=110, bbox_inches="tight")
    print(path)


if __name__ == "__main__":
    main()
