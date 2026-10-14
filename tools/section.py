"""高さ方向の断面図 docs/img/section_<ver>.png（模式図。高さの寸法は gen_case.py の値）"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Rectangle

sys.path.insert(0, os.path.dirname(__file__))
import gen_case as g

for f in font_manager.findSystemFonts():
    if "NotoSansCJK" in f:
        font_manager.fontManager.addfont(f)
plt.rcParams["font.family"] = "Noto Sans CJK JP"


def main():
    W = 60.0                      # 図の横幅（左端の壁＋キー2個分ほど）
    wall = g.WALL
    z_bot0 = 0.0
    z_bot1 = g.BOTTOM_T
    z_pcb0 = z_bot1 + g.UNDER_PCB
    z_pcb1 = z_pcb0 + g.PCB_T
    z_top0 = z_bot1 + g.FRAME_H
    z_top1 = z_top0 + g.TOP_T
    fig, ax = plt.subplots(figsize=(13, 5.5))
    acr = dict(fc="#cfe6f2", ec="#4a8aa8", lw=1)
    ax.add_patch(Rectangle((0, z_bot0), W, g.BOTTOM_T, **acr))
    ax.add_patch(Rectangle((0, z_top0), W, g.TOP_T, **acr))
    ax.add_patch(Rectangle((0, z_bot1), wall, g.FRAME_H, fc="#f1dfc4", ec="#a7834f", lw=1))
    ax.add_patch(Rectangle((wall + 1.0, z_pcb0), W - wall - 1.0, g.PCB_T, fc="#2f6d4f", ec="#1d4532"))
    for x in (wall + 8, wall + 36):   # 柔らかい台座
        ax.add_patch(Rectangle((x, z_bot1), 6, g.UNDER_PCB, fc="#f2c94c", ec="#b8902a", hatch="///", lw=0.8))
    ax.plot([wall / 2] * 2, [z_bot0 - 1.5, z_top1 + 1.5], color="#555", lw=3)   # M3ネジ
    # スイッチ2個（模式）：フランジがプレート上面に乗り、下部ハウジングがPCBまで
    for cx in (wall + 1 + 9.5, wall + 1 + 28.55):
        ax.add_patch(Rectangle((cx - 7.8, z_top1), 15.6, 5.0, fc="#ddd", ec="#777"))
        ax.add_patch(Rectangle((cx - 7.0, z_pcb1), 14.0, z_top1 - z_pcb1, fc="#eee", ec="#999", ls="--"))
        ax.annotate("", xy=(cx + 9.5, z_top1 + 0.2), xytext=(cx + 9.5, z_pcb1 + 2.6),
                    arrowprops=dict(arrowstyle="->", color="#c33"))
    ax.text(0, -1.5, "台座がPCBを下から押し上げ →\nスイッチの肩（フランジ）がプレート上面に当たって固定（赤矢印）",
            ha="left", va="top", fontsize=9, color="#c33")

    rows = [  # 上から順に、右側へ寸法の一覧
        (z_top0, z_top1, f"トッププレート（アクリル） {g.TOP_T:g}"),
        (z_pcb1, z_top0, f"プレート下面〜PCB上面 {g.PLATE_TOP_TO_PCB_TOP - g.TOP_T:g}（プレート上面〜PCB上面＝{g.PLATE_TOP_TO_PCB_TOP:g}・MX規格）"),
        (z_pcb0, z_pcb1, f"PCB {g.PCB_T:g}"),
        (z_bot1, z_pcb0, f"台座（柔らかい素材） {g.UNDER_PCB:g}"),
        (z_bot0, z_bot1, f"ボトムプレート（アクリル） {g.BOTTOM_T:g}"),
    ]
    ty = z_top1 + 1.0
    for z0, z1, label in rows:
        ax.annotate("", xy=(W + 1, z0), xytext=(W + 1, z1), arrowprops=dict(arrowstyle="<->", color="#333", lw=0.8))
        ax.plot([W + 1.5, W + 6], [(z0 + z1) / 2, ty], color="#999", lw=0.6)
        ax.text(W + 6.5, ty, label, va="center", fontsize=9)
        ty -= 3.6
    ax.text(W + 6.5, ty, f"枠（PLA） {g.FRAME_H:g} ＝ {g.PLATE_TOP_TO_PCB_TOP - g.TOP_T:g}＋{g.PCB_T:g}＋{g.UNDER_PCB:g}",
            va="center", fontsize=9, color="#a7834f")
    ax.text(W + 6.5, ty - 3.6, f"合計の高さ {g.TOP_T + g.FRAME_H + g.BOTTOM_T:g}（キーキャップ・足を除く）",
            va="center", fontsize=9, weight="bold")
    ax.text(wall / 2, z_top1 + 2.2, "M3", ha="center", fontsize=9)
    ax.text(wall + 2, z_pcb0 + g.PCB_T / 2, f"PCB {g.PCB_T:g}", color="white", va="center", fontsize=8)
    ax.text(wall / 2, z_bot1 + g.FRAME_H / 2, "枠", ha="center", va="center", fontsize=9)
    ax.set_xlim(-2, W + 75)
    ax.set_ylim(-8, z_top1 + 7.5)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(f"断面（模式図・高さは実寸mm）{g.VER}：PCBはネジ止めせず挟み込み", fontsize=12)
    path = os.path.join(g.ROOT, f"docs/img/section_{g.VER}.png")
    fig.savefig(path, dpi=110, bbox_inches="tight")
    print(path)


if __name__ == "__main__":
    main()
