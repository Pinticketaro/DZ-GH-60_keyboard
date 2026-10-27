"""補強板のネジ穴（v18b：丸穴／v19：U字の切り欠き）と USB の上の切り欠きを並べた図。→ out/<ver>/stiffener_notch.png"""
import os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from shapely.geometry import Polygon, Point
sys.path.insert(0, os.path.dirname(__file__))
import gen_case as g
for f in font_manager.findSystemFonts():
    if "NotoSansCJK" in f:
        font_manager.fontManager.addfont(f); plt.rcParams["font.family"] = font_manager.FontProperties(fname=f).get_name(); break

old = Polygon(g.stiff_outer_pts()).difference(Point(0, 0).buffer(0))
for c in g.holes():
    old = old.difference(Point(c).buffer(g.hole_d(c) / 2, quad_segs=24))
new = g.stiff_poly()
fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
win = (g.OX - 2, g.OX + 60, g.OY - 2, g.OY + 22)      # 奥の左の角（USB の所）
for ax, (P, t) in zip(axes, [(old, "v18b：丸穴（縁まで約2.8mm）"), (new, f"{g.VER}：U字の切り欠き＋USBの上の切り欠き")]):
    for pg in getattr(P, "geoms", [P]):
        x, y = pg.exterior.xy
        ax.fill(x, [-v for v in y], color="#dfe7ea", ec="#456", lw=1)
        for r in pg.interiors:
            x, y = r.xy
            ax.fill(x, [-v for v in y], color="white", ec="#456", lw=1)
    fo = Polygon(g.outer_pts()).exterior.xy
    ax.plot(fo[0], [-v for v in fo[1]], color="#999", lw=0.8, ls="--")
    ax.set_xlim(win[0], win[1]); ax.set_ylim(-win[3], -win[2]); ax.set_aspect("equal")
    ax.set_title(t, fontsize=11); ax.set_xlabel("X (mm)")
axes[0].text(win[0] + 1, -win[2] - 1.5, "点線＝外形（トッププレート）", fontsize=8, color="#666")
fig.suptitle(f"DZ60ケース {g.VER} 補強板（奥の左の角）", fontsize=12)
fig.tight_layout()
out = os.path.join(g.ROOT, "out", g.VER, "stiffener_notch.png"); fig.savefig(out, dpi=150); print(out)
