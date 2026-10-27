"""枠の壁の断面（寸法から）を2つの印刷の向きで描き、サポートが要る下向きの面を赤で示す（確認ボードの問い用）。
使い方: python3 tools/print_orient.py  → out/<ver>/print_orient.png
"""
import os
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

sys.path.insert(0, os.path.dirname(__file__))
import gen_case as g

for f in font_manager.findSystemFonts():
    if "NotoSansCJK" in f:
        font_manager.fontManager.addfont(f)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=f).get_name()
        break

# 壁の断面（u＝外面からの距離、z＝ボトムプレートの下面から）。外面 u=0、内側へ WALL-FRAME_INSET
W = g.WALL - g.FRAME_INSET
z0, zb, zf = g.BOTTOM_T - g.SKIRT_H, g.BOTTOM_T, g.BOTTOM_T + g.FRAME_H
zt = zf + (g.STIFF_T if g.STIFF_RECESS else 0)
lip = g.STIFF_LIP if g.STIFF_RECESS else W
prof = [(0, z0), (g.SKIRT_T, z0), (g.SKIRT_T, zb), (W, zb), (W, zf), (lip, zf), (lip, zt), (0, zt)]
# 下向きの水平な面（材料が上にある水平な辺）
down = [((g.SKIRT_T, zb), (W, zb))]
up_faces = [((lip, zf), (W, zf))]

fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
cases = [("A：上面を下にして印刷（いまの向き）", True), ("B：下面を下にして印刷", False)]
for ax, (title, flip) in zip(axes, cases):
    T = (lambda u, z: (u, zt - z)) if flip else (lambda u, z: (u, z - z0))
    pts = [T(u, z) for u, z in prof]
    ax.fill([p[0] for p in pts], [p[1] for p in pts], color="#d9d4cb", ec="#555", lw=1)
    faces = up_faces if flip else down      # 向きを変えると、上向きの面が下向きになる
    for a, b in faces:
        (u0, h), (u1, _) = T(*a), T(*b)
        ax.add_patch(plt.Rectangle((min(u0, u1), 0), abs(u1 - u0), h, color="#e05a4f", alpha=0.25, lw=0))
        ax.plot([u0, u1], [h, h], color="#d33", lw=2.5)
        ax.annotate(f"サポート 幅{abs(u1 - u0):.1f}×高さ{h:.1f}mm\n（ぐるりと1周）", ((u0 + u1) / 2, h / 2), ha="center", va="center", fontsize=9, color="#a22")
    ax.axhline(0, color="#333", lw=2)
    ax.text(W + 0.5, 0.3, "ベッド", fontsize=9, color="#333")
    ax.text(-0.3, (zt - z0) + 0.6, "外側", fontsize=9, ha="left")
    ax.set_title(title, fontsize=11)
    ax.set_xlim(-1, W + 3)
    ax.set_ylim(-0.8, zt - z0 + 2)
    ax.set_aspect("equal")
    ax.set_xlabel("外面からの距離 (mm)")
    ax.set_ylabel("ベッドからの高さ (mm)")
fig.suptitle(f"DZ60ケース {g.VER} 枠の壁の断面：赤＝サポートが要る所（補強板の掘り込みの床／スカートの内側の床）", fontsize=11)
fig.tight_layout()
out = os.path.join(g.ROOT, "out", g.VER, "print_orient.png")
fig.savefig(out, dpi=150)
print(out)
