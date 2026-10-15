"""打鍵感・外観に関わる数値の見積もり（概算）。結果は docs/改善案.md の根拠に使う。

使い方: python3 tools/analysis.py
注意: 板の曲げは「単純支持の長方形板の中央に集中荷重」の式（Timoshenko）で見た概算。
      穴あき板の剛性は「穴と穴の間の幅 / ピッチ」で割り引いた目安。桁を見るためのもの。
"""
import json
import math
import os
import sys

from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

sys.path.insert(0, os.path.dirname(__file__))
import gen_case as g

E_ACR, NU_ACR = 3.2e9, 0.35      # アクリル
E_FR4, NU_FR4 = 20e9, 0.15       # PCB（FR4）
PITCH = 19.05


def D(E, t_mm, nu, eff=1.0):
    t = t_mm / 1000
    return eff * E * t ** 3 / (12 * (1 - nu ** 2))


def main():
    res = {}
    # 穴あき板の割引（穴と穴の間の幅 / ピッチ）
    eff_top = (PITCH - 14.0) / PITCH
    eff_st = (PITCH - (14.0 + 2 * g.STIFF_OFFSET)) / PITCH
    d_top = D(E_ACR, g.TOP_T, NU_ACR, eff_top)
    d_st = D(E_ACR, g.STIFF_T, NU_ACR, eff_st)
    d_pcb = D(E_FR4, g.PCB_T, NU_FR4, 0.9)
    # プレートとPCBはスイッチ65個でつながる → 2枚の板が5mm離れたサンドイッチとして働く（上限の目安）
    k_top = E_ACR * g.TOP_T / 1000 * eff_top
    k_pcb = E_FR4 * g.PCB_T / 1000 * 0.9
    h = (g.PLATE_TOP_TO_PCB_TOP - g.TOP_T / 2 + g.PCB_T / 2) / 1000
    d_sand = k_top * k_pcb / (k_top + k_pcb) * h ** 2 + d_top + d_pcb
    b = (g.OUTER_H - 2 * g.WALL) / 1000          # 短い方のスパン（枠の内側）
    alpha = 0.01695                               # 細長い単純支持板・中央集中荷重
    P = 1.0                                       # 1N（底打ち時の指の力の目安は1〜3N）
    defl = lambda d: alpha * P * b ** 2 / d * 1000  # mm
    res["bending_stiffness_Nm"] = {
        "top_plate": round(d_top, 3), "stiffener": round(d_st, 3),
        "pcb": round(d_pcb, 2), "plate+switch+pcb_upper_bound": round(d_sand, 1)}
    res["center_deflection_mm_per_1N"] = {
        "top_plate_only": round(defl(d_top), 3), "top+stiffener(not bonded)": round(defl(d_top + d_st), 3),
        "pcb_only": round(defl(d_pcb), 4), "plate+switch+pcb": round(defl(d_sand), 4)}

    # 重さ（ケース部品）
    outer = Polygon(g.outer_pts())
    inner = Polygon(g.frame_inner_pts())
    holes = unary_union([Point(c).buffer(g.hole_d(c) / 2) for c in g.holes()])
    sw = unary_union([Polygon(p) for p in g.switch_cutouts()])
    st = unary_union([Polygon(p) for p in g.stiffener_openings()])
    cm2 = lambda p: p.area / 100
    rho_a, rho_pla = 1.19, 1.24
    res["mass_g"] = {
        "top_plate": round(cm2(outer.difference(sw).difference(holes)) * g.TOP_T / 10 * rho_a),
        "stiffener": round(cm2(outer.difference(st).difference(holes)) * g.STIFF_T / 10 * rho_a),
        "bottom_plate": round(cm2(outer.difference(holes)) * g.BOTTOM_T / 10 * rho_a),
        "frame_100pct": round(cm2(outer.difference(inner).difference(holes)) * g.FRAME_H / 10 * rho_pla),
    }
    res["mass_g"]["case_total_100pct"] = sum(res["mass_g"].values())

    # 傾きと手前の高さ（キーキャップ別）
    stack = g.TOP_T + g.STIFF_T + g.FRAME_H + g.BOTTOM_T
    span = 103.3 - (-8.7)   # 前後のネジ列の間隔（中央の穴）
    rows = []
    for deg in (0, 3, 5, 7):
        tan = math.tan(math.radians(deg))
        nut_r = g.NUT_POCKET_AF / math.sqrt(3)
        front = math.ceil((g.FOOT_SKIN + g.NUT_T + 0.3 + nut_r * tan) * 10) / 10
        rear = front + span * tan
        rows.append({"deg": deg, "front_foot": round(front, 1), "rear_foot": round(rear, 1),
                     "front_height_no_keycap": round(front + stack, 1)})
    res["tilt_pucks"] = rows
    # 真鍮丸棒の太さと傾き・重さ
    if g.REAR_FOOT == "brass_rod":
        keep = g.ROD_D
        rod_rows = []
        for rd in (6.0, 8.0, 10.0, 12.0, 14.0):
            g.ROD_D = rd
            _, hf, tn, _ = g.feet()
            L = g.rod()["length"]
            rod_rows.append({"rod_d": rd, "tilt_deg": round(math.degrees(math.atan(tn)), 1), "front_foot": hf,
                             "front_height_no_keycap": round(hf + stack, 1),
                             "rod_mass_g": round(math.pi * (rd / 20) ** 2 * L / 10 * 8.5)})
        g.ROD_D = keep
        res["tilt_brass_rod"] = rod_rows
    res["plate_open_ratio"] = round(sw.area / box(-0.375, -0.325, 285.375, 94.925).area, 2)
    path = os.path.join(g.ROOT, f"case/analysis_{g.VER}.json")
    open(path, "w", encoding="utf-8").write(json.dumps(res, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
