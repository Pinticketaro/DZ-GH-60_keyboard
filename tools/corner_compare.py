"""角丸の候補を見比べる図と、1:1で確かめるテスト片SVGを作る。

使い方: python3 tools/corner_compare.py
出力:  docs/img/corner_compare.png（比較図）
       case/corner_test_A4.svg（A4・100%で印刷、またはレーザーで切って実物確認）
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

sys.path.insert(0, os.path.dirname(__file__))
import squircle as sq

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 315.0, 126.0          # ケース外形（旧デザイン踏襲）
RADII = [8, 12, 16]
APPLE = 0.6                  # Apple風のスムージング

for f in font_manager.findSystemFonts():
    if "NotoSansCJK" in f:
        font_manager.fontManager.addfont(f)
plt.rcParams["font.family"] = "Noto Sans CJK JP"


def outline(R, s, x=0, y=0, w=W, h=H):
    p = sq.rounded_rect_points(x, y, w, h, R, s, 0.05)
    return p + [p[0]]


def compare_png(path):
    fig = plt.figure(figsize=(15, 13))
    gs = fig.add_gridspec(4, 3, height_ratios=[1.25, 1.25, 1.0, 1.1], hspace=0.45, wspace=0.25)

    # 1-2段目：角の拡大（普通の円弧 vs Apple風）
    for j, R in enumerate(RADII):
        for row, s in enumerate([0.0, APPLE]):
            ax = fig.add_subplot(gs[row, j])
            p = outline(R, s)
            ax.fill([q[0] for q in p], [q[1] for q in p], color="#e9edf2")
            if s:  # 同じRの普通の円弧を点線で重ねる
                p0 = outline(R, 0.0)
                ax.plot([q[0] for q in p0], [q[1] for q in p0], color="#c55", lw=1, ls="--")
            ax.plot([q[0] for q in p], [q[1] for q in p], color="#223", lw=2)
            ax.set_xlim(W - 40, W + 3)
            ax.set_ylim(43, -3)
            ax.set_aspect("equal")
            ax.grid(color="#eee", lw=0.6)
            ax.tick_params(labelsize=7)
            kind = "普通の円弧" if not s else f"Apple風（スムージング{s}）\n赤点線＝同じRの普通の円弧"
            ax.set_title(f"R{R}  {kind}\nカーブの始まり：角から {sq.corner_extent(R, s):.1f}mm", fontsize=10)

    # 3段目：曲率のグラフ（なぜなめらかに見えるか）
    ax = fig.add_subplot(gs[2, :])
    R = 12
    for s, col, lab in [(0.0, "#c55", "普通の円弧 R12：直線から急に曲がる（段差）"),
                        (APPLE, "#258", "Apple風 R12：少しずつ曲がり始める（連続）")]:
        loc, p = sq._corner_local(R, s, 0.05)
        pre = [(-p - 8 + 0.05 * j, 0.0) for j in range(160)]
        post = [(0.0, p + 0.05 * j) for j in range(1, 161)]
        seg = pre + loc + post
        cv = sq.curvature_along(seg)
        ax.plot([c[0] for c in cv], [c[1] for c in cv], color=col, lw=2, label=lab)
    ax.set_xlabel("角に沿った距離 (mm)　※左右の平らな部分が直線")
    ax.set_ylabel("曲がり具合（曲率 1/mm）")
    ax.set_title("曲がり具合の変化：Apple風は0からなだらかに上がるので、光の映り込みや輪郭が途切れずに見える", fontsize=10)
    ax.legend(fontsize=9)
    ax.grid(color="#eee")

    # 4段目：ケース全体の見え方（Apple風）
    for j, R in enumerate(RADII):
        ax = fig.add_subplot(gs[3, j])
        p = outline(R, APPLE)
        ax.fill([q[0] for q in p], [q[1] for q in p], color="#d9dee5")
        ax.plot([q[0] for q in p], [q[1] for q in p], color="#223", lw=1.2, solid_joinstyle="round")
        ax.set_xlim(-5, W + 5)
        ax.set_ylim(H + 5, -5)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.set_title(f"全体 315×126  Apple風 R{R}", fontsize=10)

    fig.suptitle("ケースの角丸候補（外形315×126mm）", fontsize=15)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, dpi=110, bbox_inches="tight")


def test_svg(path):
    """A4横に6枚：R8/12/16 × 普通/Apple風。各片 90×60mm。"""
    pw, ph = 297, 210
    cw, ch, gap = 90, 60, 5
    x0 = (pw - (3 * cw + 2 * gap)) / 2
    y0 = 30
    body = []
    for row, s in enumerate([0.0, APPLE]):
        for j, R in enumerate(RADII):
            x = x0 + j * (cw + gap)
            y = y0 + row * (ch + 25)
            pts = sq.rounded_rect_points(x, y, cw, ch, R, s)
            body.append(f'<path d="{sq.to_svg_path(pts)}" fill="none" stroke="#ff0000" stroke-width="0.05"/>')
            lab = f"R{R} {'普通' if not s else 'Apple風'}"
            body.append(f'<text x="{x + cw / 2:.2f}" y="{y + ch / 2 + 2:.2f}" font-size="6" font-family="Hiragino Sans, Noto Sans CJK JP, sans-serif" '
                        f'text-anchor="middle" fill="#0000ff">{lab}</text>')
    body.append(f'<text x="{x0}" y="18" font-size="5" font-family="Hiragino Sans, Noto Sans CJK JP, sans-serif" fill="#000000">角丸テスト片（100%で印刷 / 赤=切断、青=彫刻）'
                f' 各片90×60mm。印刷したら定規で90mmを確認</text>')
    svg = (f'<?xml version="1.0" encoding="UTF-8"?>\n'
           f'<svg xmlns="http://www.w3.org/2000/svg" width="{pw}mm" height="{ph}mm" viewBox="0 0 {pw} {ph}">\n'
           + "\n".join(body) + "\n</svg>\n")
    open(path, "w", encoding="utf-8").write(svg)


if __name__ == "__main__":
    compare_png(os.path.join(ROOT, "docs/img/corner_compare.png"))
    test_svg(os.path.join(ROOT, "case/corner_test_A4.svg"))
    print("ok")
