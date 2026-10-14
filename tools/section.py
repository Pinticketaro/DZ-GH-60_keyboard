"""高さ方向の断面図 docs/img/section_<ver>.png（模式図。高さの寸法は gen_case.py の値）"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Polygon as MPoly, Rectangle

sys.path.insert(0, os.path.dirname(__file__))
import gen_case as g

for f in font_manager.findSystemFonts():
    if "NotoSansCJK" in f:
        font_manager.fontManager.addfont(f)
plt.rcParams["font.family"] = "Noto Sans CJK JP"


def main():
    W = 74.0
    wall = g.WALL
    z_bot0, z_bot1 = 0.0, g.BOTTOM_T
    z_pcb0 = z_bot1 + g.UNDER_PCB
    z_pcb1 = z_pcb0 + g.PCB_T
    z_fr1 = z_bot1 + g.FRAME_H
    z_st0, z_st1 = z_fr1, z_fr1 + g.STIFF_T
    z_top0, z_top1 = z_st1, z_st1 + g.TOP_T
    fig, ax = plt.subplots(figsize=(14, 6))
    acr = dict(fc="#cfe6f2", ec="#4a8aa8", lw=1)
    stf = dict(fc="#a9d3e8", ec="#4a8aa8", lw=1)
    ax.add_patch(Rectangle((0, z_bot0), W, g.BOTTOM_T, **acr))
    ax.add_patch(Rectangle((0, z_bot1), wall, g.FRAME_H, fc="#f1dfc4", ec="#a7834f", lw=1))
    ax.add_patch(Rectangle((wall + 1.0, z_pcb0), W - wall - 1.0, g.PCB_T, fc="#2f6d4f", ec="#1d4532"))
    for x in (wall + 8, wall + 37, wall + 54):
        ax.add_patch(Rectangle((x, z_bot1), 6, g.UNDER_PCB, fc="#f2c94c", ec="#b8902a", hatch="///", lw=0.8))

    centers = (wall + 1 + 9.5, wall + 1 + 28.55, wall + 1 + 47.6)

    def plate_with_holes(z0, t, hole, style):
        x = 0.0
        for c in centers:
            ax.add_patch(Rectangle((x, z0), (c - hole / 2) - x, t, **style))
            x = c + hole / 2
        ax.add_patch(Rectangle((x, z0), W - x, t, **style))

    plate_with_holes(z_top0, g.TOP_T, 14.0, acr)
    plate_with_holes(z_st0, g.STIFF_T, 14.0 + 2 * g.STIFF_OFFSET, stf)
    for c in centers:
        ax.add_patch(Rectangle((c - 7.8, z_top1), 15.6, 5.0, fc="#ddd", ec="#777"))
        ax.add_patch(Rectangle((c - 6.9, z_pcb1), 13.8, z_top1 - z_pcb1, fc="#f2f2f2", ec="#999", ls="--"))
        for s in (-1, 1):
            x0 = c + s * 6.9
            ax.add_patch(MPoly([(x0, z_top0 - 0.1), (x0 + s * 0.6, z_top0 - 0.7), (x0, z_top0 - 1.6)],
                               closed=True, fc="#c33", ec="#c33"))
    c = centers[1]
    ax.annotate("爪がトッププレートの裏に掛かる\n＝上へ抜けない", xy=(c + 7.4, z_top0 - 0.5), xytext=(14, -7.5),
                fontsize=9, color="#c33", ha="center", arrowprops=dict(arrowstyle="->", color="#c33"))
    ax.annotate("肩がプレート上面に乗る\n＝下へ沈まない", xy=(c - 7.6, z_top1 + 0.1), xytext=(c - 28, z_top1 + 9),
                fontsize=9, color="#333", ha="center", arrowprops=dict(arrowstyle="->", color="#333"))
    ax.annotate("台座がPCBを軽く支える\n（ダンパー）", xy=(wall + 40, z_bot1 + 2.5), xytext=(wall + 50, -7.5),
                fontsize=9, color="#9a7414", ha="center", arrowprops=dict(arrowstyle="->", color="#9a7414"))
    ax.plot([wall / 2] * 2, [z_bot0 - 1.5, z_top1 + 1.5], color="#555", lw=3)
    ax.text(wall / 2, z_top1 + 2.2, "M3（4層を共締め）", ha="center", fontsize=9)
    ax.text(wall / 2, z_bot1 + g.FRAME_H / 2, "枠", ha="center", va="center", fontsize=9)

    rows = [
        (z_top0, z_top1, f"トッププレート（アクリル） {g.TOP_T:g}　穴14.0"),
        (z_st0, z_st1, f"補強板（アクリル） {g.STIFF_T:g}　穴{14 + 2 * g.STIFF_OFFSET:g}（爪の逃げ）"),
        (z_pcb1, z_st0, f"補強板〜PCB上面 {g.GAP_STIFF_PCB:g}"),
        (z_pcb0, z_pcb1, f"PCB {g.PCB_T:g}"),
        (z_bot1, z_pcb0, f"台座（柔らかい素材） {g.UNDER_PCB:g}"),
        (z_bot0, z_bot1, f"ボトムプレート（アクリル） {g.BOTTOM_T:g}"),
    ]
    ty = z_top1 + 2.0
    for z0, z1, label in rows:
        ax.annotate("", xy=(W + 1, z0), xytext=(W + 1, z1), arrowprops=dict(arrowstyle="<->", color="#333", lw=0.8))
        ax.plot([W + 1.5, W + 6], [(z0 + z1) / 2, ty], color="#999", lw=0.6)
        ax.text(W + 6.5, ty, label, va="center", fontsize=9)
        ty -= 3.3
    ax.text(W + 6.5, ty, f"枠（PLA） {g.FRAME_H:g} ＝ {g.GAP_STIFF_PCB:g}＋{g.PCB_T:g}＋{g.UNDER_PCB:g}",
            va="center", fontsize=9, color="#a7834f")
    total = g.TOP_T + g.STIFF_T + g.FRAME_H + g.BOTTOM_T
    ax.text(W + 6.5, ty - 3.3, f"合計の高さ {total:g}（キーキャップ・足を除く）", va="center", fontsize=9, weight="bold")
    ax.text(W + 6.5, ty - 6.6, f"プレート上面〜PCB上面 {g.PLATE_TOP_TO_PCB_TOP:g}（MX規格）", va="center", fontsize=9)
    ax.set_xlim(-2, W + 78)
    ax.set_ylim(-10, z_top1 + 12)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(f"断面（模式図・高さは実寸mm）{g.VER}：1.5mmプレート＋補強板、PCBはネジ止めなし", fontsize=12)
    path = os.path.join(g.ROOT, f"docs/img/section_{g.VER}.png")
    fig.savefig(path, dpi=110, bbox_inches="tight")
    print(path)


if __name__ == "__main__":
    main()
