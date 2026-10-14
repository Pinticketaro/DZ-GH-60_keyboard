"""Apple風の角丸（曲率が連続する角丸）を作るモジュール。

普通の角丸（円弧）は、直線から円弧に入る点で曲がり具合（曲率）が 0 → 1/R へ急に跳ぶ。
目はこの段差を「角のカクつき」や映り込みの途切れとして感じる。
Apple製品の角は、直線から少しずつ曲がり始めて、また少しずつ直線に戻る。

ここでは道路・線路のカーブと同じ作り方をする：
    直線 → クロソイド（曲率が 0 から 1/R まで一定の割合で増える）→ 円弧（半径R）→ クロソイド → 直線
曲率がどこでも途切れない（G2連続）。

パラメータ
  R          … 角のいちばん曲がっている部分の半径（mm）
  smoothing  … 90°の曲がりのうち、クロソイドが受け持つ割合
                0 = 普通の円弧の角丸、0.6前後 = Apple風、1 = 円弧なし（全部クロソイド）
smoothing を上げるほど、カーブが角から遠くまで伸びる（corner_extent で確認できる）。

座標はmm、Y下向き（SVGと同じ）。出力は細かい折れ線（既定0.1mm刻み、形の誤差は0.001mm未満）。
"""
from __future__ import annotations

import math


def _corner_local(R: float, s: float, step: float):
    """頂点(0,0)、(-p,0)から+x向きに入り、(0,p)へ+y向きに出る角の点列と p を返す。"""
    th_s = s * math.pi / 4            # クロソイド1本が曲がる角度
    Ls = 2 * R * th_s                 # クロソイド1本の長さ
    phi = math.pi / 2 - 2 * th_s      # 円弧が曲がる角度
    La = R * phi
    total = 2 * Ls + La
    n = max(8, int(math.ceil(total / step)) * 4)
    dl = total / n

    def heading(l):
        if l <= Ls:
            return l * l / (2 * R * Ls) if Ls > 0 else 0.0
        if l <= Ls + La:
            return th_s + (l - Ls) / R
        m = total - l
        return math.pi / 2 - (m * m / (2 * R * Ls) if Ls > 0 else 0.0)

    x = y = 0.0
    pts = [(0.0, 0.0)]
    for i in range(n):
        h = heading((i + 0.5) * dl)   # 中点法で積分
        x += math.cos(h) * dl
        y += math.sin(h) * dl
        if (i + 1) % 4 == 0:
            pts.append((x, y))
    p = (x + y) / 2                   # 対称なので x ≒ y ≒ p
    return [(q[0] - p, q[1]) for q in pts], p


def corner_extent(R: float, smoothing: float) -> float:
    """カーブが角からどこまで伸びるか（mm）。"""
    if R <= 0:
        return 0.0
    return _corner_local(R, smoothing, 0.1)[1]


def rounded_rect_points(x, y, w, h, R, smoothing, step=0.1):
    """左上(x,y)・幅w・高さhの角丸長方形の外周点列（時計回り、閉じていない）。"""
    if R <= 0:
        return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    local, p = _corner_local(R, smoothing, step)
    lim = min(w, h) / 2
    if p > lim:                        # 辺が足りなければ R を縮める
        k = lim / p
        R *= k
        local, p = _corner_local(R, smoothing, step)
    corners = [
        ((x + w, y), (1, 0), (0, 1)),
        ((x + w, y + h), (0, 1), (-1, 0)),
        ((x, y + h), (-1, 0), (0, -1)),
        ((x, y), (0, -1), (1, 0)),
    ]
    out = []
    for V, i, o in corners:
        for u, v in local:
            out.append((V[0] + u * i[0] + v * o[0], V[1] + u * i[1] + v * o[1]))
    return out


def to_svg_path(pts, nd=4):
    f = lambda v: f"{round(v, nd):g}"
    return "M " + " L ".join(f"{f(a)},{f(b)}" for a, b in pts) + " Z"


def curvature_along(pts):
    """折れ線の各点の曲率(1/mm)と累積長さ（比較図用）。"""
    out = []
    acc = 0.0
    for j in range(1, len(pts) - 1):
        A, B, C = pts[j - 1], pts[j], pts[j + 1]
        ab, bc, ca = math.dist(A, B), math.dist(B, C), math.dist(C, A)
        acc += ab
        cross = abs((B[0] - A[0]) * (C[1] - A[1]) - (B[1] - A[1]) * (C[0] - A[0]))
        out.append((acc, 0.0 if ab * bc * ca == 0 else 2 * cross / (ab * bc * ca)))
    return out
