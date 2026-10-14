"""プレート・枠・底板・PCBを重ねた確認図 docs/img/overlay_<ver>.png を作る。"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Circle, FancyBboxPatch, Polygon as MPoly

sys.path.insert(0, os.path.dirname(__file__))
import gen_case as g

for f in font_manager.findSystemFonts():
    if "NotoSansCJK" in f:
        font_manager.fontManager.addfont(f)
plt.rcParams["font.family"] = "Noto Sans CJK JP"

# GH60のPCBネジ穴（基準寸法.md）。サンドイッチ方式では使わないが、位置の参考に表示
PCB_HOLES = [(25.20, 27.90), (128.20, 47.00), (190.50, 85.20), (260.05, 27.90)]


def main():
    fig, ax = plt.subplots(figsize=(16, 7.5))
    ax.add_patch(MPoly(g.outer_pts(), closed=True, fc="#e6e1d6", ec="#333", lw=1.2, label="プレート／底板の外形"))
    ax.add_patch(MPoly(g.frame_inner_pts(), closed=True, fc="#ffffff", ec="#8a6", lw=1.2, ls="--", label="枠の内側（3Dプリント）"))
    ax.add_patch(FancyBboxPatch((0, 0), g.PCB_W, g.PCB_H, boxstyle="round,pad=0,rounding_size=2",
                                fc="#2f6d4f22", ec="#2f6d4f", lw=1.2, label="PCB 285×94.6"))
    if hasattr(g, "stiffener_openings"):
        for p in g.stiffener_openings():
            ax.add_patch(MPoly(p, closed=True, fc="#cfe6f2", ec="#4a8aa8", lw=0.6, ls="--"))
        ax.plot([], [], color="#4a8aa8", lw=0.8, ls="--", label=f"補強板の抜き（{g.STIFF_T:g}mm）")
    for p in g.switch_cutouts():
        ax.add_patch(MPoly(p, closed=True, fc="none", ec="#c33", lw=0.6))
    for c in g.holes():
        ax.add_patch(Circle(c, g.HOLE_D / 2, fc="#333", ec="none"))
    for c in PCB_HOLES:
        ax.add_patch(Circle(c, 1.25, fc="none", ec="#2f6d4f", lw=0.8))
    ax.plot([g.SPLIT_X] * 2, [g.OY - 4, g.OY + g.OUTER_H + 4], color="#36c", lw=1.2, ls="-.", label="枠の分割線")
    ax.add_patch(plt.Rectangle((g.USB_X - g.USB_W / 2, g.OY), g.USB_W, g.WALL, fc="#36c5", ec="#36c",
                               label="USB切り欠き（位置は要実測）"))
    if getattr(g, "REAR_FOOT", "") == "brass_rod":
        r = g.rod()
        ax.add_patch(plt.Rectangle((r["x0"], r["y"] - g.ROD_D / 2), r["x1"] - r["x0"], g.ROD_D, fc="#d4a85a55", ec="#b8860b",
                                   ls="--", lw=1.0, label=f"真鍮丸棒 φ{g.ROD_D:g}（下面）"))
    for f in g.feet()[0]:
        ax.add_patch(Circle((f["x"], f["y"]), g.FOOT_D / 2, fc="none", ec="#555", ls=":", lw=0.9))
    ax.plot([], [], color="#c33", lw=0.8, label="スイッチ・スタビ穴（旧swillkb）")
    ax.plot([], [], "o", color="#333", label="M3ネジ穴×8")
    ax.set_xlim(g.OX - 6, g.OX + g.OUTER_W + 6)
    ax.set_ylim(g.OY + g.OUTER_H + 6, g.OY - 6)
    ax.set_aspect("equal")
    ax.grid(color="#eee", lw=0.5)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.07), ncol=4, fontsize=9, frameon=False)
    ax.set_title(f"重ね合わせ確認 {g.VER}：外形{g.OUTER_W:g}×{g.OUTER_H:g}、角R{g.CORNER_R:g}・スムージング{g.CORNER_SMOOTH}（仮）"
                 f"／原点＝PCB左上", fontsize=12)
    path = os.path.join(g.ROOT, f"docs/img/overlay_{g.VER}.png")
    fig.savefig(path, dpi=110, bbox_inches="tight")
    print(path)


if __name__ == "__main__":
    main()
