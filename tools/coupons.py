"""テストピース（クーポン）を作る。公開されている数値は機材・材料ごとに圧入とガタの差ほどずれるので、
本番の前にこれをレーザーカット・3Dプリントして、自分の機材の値を決める。結果は measurements/試し片記録.csv に書き、
パラメータファイルの fab の値を「実測」に置き換える。

出力: out/coupons/
  laser_<板厚>.svg      … レーザー用。カーフテスト（20mm角＋10mm角の穴）、スロット幅を
                          板厚−0.20〜+0.20mm（0.05刻み・9本）で並べたコーム、タブ
                          赤＝カット（内側の穴→外形の順にカットする）、青＝刻印（番号の点）。カーフ補正なしで描いてある
  fdm_fit.stl           … 3Dプリント用。ピン（φ6）と、穴 φ6＋2×クリアランス（clr_fit−0.1〜+0.1、0.05刻み）の板
  fdm_insert.stl        … ヒートセットインサートの下穴 4.0〜4.4mm（0.1刻み）、深さ insert_depth
  coupons.md            … 番号と値の対応、測り方、どの値をどこに書くか
番号は「点の数」で示す（1点＝1番）。文字は使わない（レーザーソフト・スライサーでの文字化けを避けるため）。

使い方: python tools/coupons.py [v03] [--lang ja|en]

English: makes coupons (test pieces). Published values for each machine and material differ by about as much as
the gap between a press fit and a loose fit, so cut and print these before the real part and set the values for
your own machine. Write the results in measurements/coupon_log.csv (Japanese projects: measurements/試し片記録.csv)
and replace the fab values in the params file with "measured" ones.
Output: out/coupons/
  laser_<thickness>.svg … for the laser: a square to measure kerf (20mm square with a 10mm square hole), a comb with
                          slot widths from thickness −0.20 to +0.20mm (0.05 steps, 9 slots), and a strip to insert.
                          Red = cut (inner hole first, then outline), blue = engrave (number dots). Drawn without kerf compensation
  fdm_fit.stl           … for 3D printing: a pin (φ6) and a plate with holes φ6 + 2 × clearance (clr_fit −0.1 to +0.1, 0.05 steps)
  fdm_insert.stl        … pilot holes for heat-set inserts, 4.0 to 4.4mm (0.1 steps), depth insert_depth
  coupons.md            … which number has which value, how to measure, and where to write each value
Numbers are shown by the count of dots (1 dot = No. 1). No text is used, so nothing gets garbled in laser software or slicers.
Language: meta.lang in the params file (or --lang ja|en).
"""
import os
import sys

import manifold3d as m3
import numpy as np
import trimesh

sys.path.insert(0, os.path.dirname(__file__))
import common  # noqa: E402

SEG = 48
STEPS = [-0.20, -0.15, -0.10, -0.05, 0.0, 0.05, 0.10, 0.15, 0.20]

TXT = {
    "ja": {
        "svg_note": "板厚 {T}mm 用。赤=カット、青=刻印。カーフ補正なし",
        "title": "# テストピース {title}（{ver} の値から作成）",
        "intro": "番号は点の数（1点＝1番）。結果は `measurements/試し片記録.csv` に書き、パラメータファイルの `fab` を更新して状態を「実測」にする。",
        "laser_h": "## レーザー：{fn}（板厚 {T:g}mm 用）",
        "laser_steps": [
            "1. **板厚を測る**：シートの4隅と中央をノギスで測り、平均を `t_` の値にする（呼び寸法と違うことが多い）",
            "2. **カーフ**：20mm角の外形を測る。カーフ k（全幅）＝ 20 − 測った値。X方向とY方向を別に記録する",
            "   - 確かめ：10mm角の穴は 10 ＋ k、抜けた中身は 10 − k になる",
            "3. **スロットのコーム**：タブを各スロットに差し、指で押して入り・抜けない番号を選ぶ",
            "", "| 番号 | 描いたスロット幅 | 板厚との差 |", "|---:|---:|---:|"],
        "laser_after": [
            "", "- コームは**カーフ補正なし**で描いてある。本番も補正なしで描くなら、選んだ「板厚との差」をそのまま使う。"
            "補正ありで描くなら、カーフ k を `kerf` に入れて k/2 ずつずらす（外形は外へ、穴は内へ）。どちらか一方に決める",
            "- アクリルは圧入しない（締め付けで内角から割れる）。すきまばめ＋ネジか接着にする", ""],
        "fit_head": [
            "## 3Dプリント：fdm_fit.stl", "",
            "平置きで、本番と同じフィラメント・同じ設定で印刷する。スライサーの穴補正は本番と同じにする。", "",
            "| 番号 | 穴径（φ6＋2×クリアランス） | クリアランス（片側） |", "|---:|---:|---:|"],
        "fit_after": [
            "", "- 力を入れずに入って回る番号 → `clr_slide`、軽く押して入りガタがない番号 → `clr_fit`",
            "- このクリアランスにはプリンターの穴の縮みが含まれる。ピンと穴のはめ合いは `clr_*` だけで描き、`hole_comp` は重ねない", ""],
        "insert_head": [
            "## 3Dプリント：fdm_insert.stl", "",
            "M3インサート用の下穴 {h0}〜{h1}mm、深さ {depth:g}mm。外周4本・インフィル25%以上で印刷する（UW–Madison）。", "",
            "- こては印刷温度＋10〜20℃から始め、約90%まで沈めてから平らな物で面一に押さえ、15〜30秒冷ます（CNC Kitchen・UW）",
            "- まっすぐ入り、周りが盛り上がらず、ネジを締めても回らない番号 → `insert_hole`",
            "", "| 番号 | 下穴径 |", "|---:|---:|"],
        "partial": [
            "", "## 部分試作（本番の前に）", "",
            "いちばん合わせが難しい所（差し込み・ネジ・中身の角など）だけを取り出してレーザーカット・3Dプリントする。実物を合わせて確かめる。"
            "USB-C の切り欠きがあるなら、いちばん太いケーブルで試す（切り欠きはケーブル側の太さで決まる）。"],
    },
    "en": {
        "svg_note": "For {T}mm sheet. Red = cut, blue = engrave. No kerf compensation",
        "title": "# Coupons {title} (made from the {ver} values)",
        "intro": "Numbers are the count of dots (1 dot = No. 1). Write the results in `measurements/coupon_log.csv`, "
                 "then update `fab` in the params file and set the status to \"measured\".",
        "laser_h": "## Laser: {fn} (for {T:g}mm sheet)",
        "laser_steps": [
            "1. **Measure the sheet thickness**: measure the 4 corners and the center with calipers, and use the average "
            "as the `t_` value (it often differs from the nominal size)",
            "2. **Kerf**: measure the 20mm square outline. Kerf k (full cut width) = 20 − measured value. "
            "Record X and Y separately",
            "   - Check: the 10mm square hole becomes 10 + k, and the piece that fell out becomes 10 − k",
            "3. **Slot comb**: push the strip into each slot by hand, and pick the number where it goes in and does not fall out",
            "", "| No. | Drawn slot width | Difference from thickness |", "|---:|---:|---:|"],
        "laser_after": [
            "", "- The comb is drawn **without kerf compensation**. If you also draw the real parts without compensation, "
            "use the chosen \"difference from thickness\" as is. "
            "If you draw with compensation, put kerf k in `kerf` and offset by k/2 (outlines outward, holes inward). "
            "Pick one of the two",
            "- Do not press-fit acrylic (the pressure cracks it from inside corners). Use a clearance fit with screws or glue", ""],
        "fit_head": [
            "## 3D print: fdm_fit.stl", "",
            "Print it flat, with the same filament and the same settings as the real part. "
            "Keep the slicer hole compensation the same as for the real part.", "",
            "| No. | Hole diameter (φ6 + 2 × clearance) | Clearance (per side) |", "|---:|---:|---:|"],
        "fit_after": [
            "", "- The number that goes in and turns without force → `clr_slide`; "
            "the number that goes in with a light push and has no play → `clr_fit`",
            "- This clearance already includes the printer's hole shrinkage. Draw pin and hole fits with `clr_*` only, "
            "and do not add `hole_comp` on top", ""],
        "insert_head": [
            "## 3D print: fdm_insert.stl", "",
            "Pilot holes for M3 inserts, {h0} to {h1}mm, depth {depth:g}mm. "
            "Print with 4 perimeters and at least 25% infill (UW–Madison).", "",
            "- Start the iron at print temperature + 10 to 20°C, sink the insert to about 90%, press it flush with "
            "a flat object, and let it cool for 15 to 30 seconds (CNC Kitchen, UW)",
            "- The number where the insert goes in straight, the surface around it does not bulge, and it does not spin "
            "when you tighten a screw → `insert_hole`",
            "", "| No. | Pilot hole diameter |", "|---:|---:|"],
        "partial": [
            "", "## Partial test (before the real part)", "",
            "Cut or print only the hardest fits (slots, screws, corners around the contents, and so on), "
            "and check them against the real objects. "
            "If there is a USB-C cutout, test it with your thickest cable (the cutout size is set by the cable plug)."],
    },
}


# ---------------- レーザー（SVG、単位mm）
def svg_rect(x, y, w, h, color="#ff0000"):
    return f'<rect x="{x:.3f}" y="{y:.3f}" width="{w:.3f}" height="{h:.3f}" fill="none" stroke="{color}" stroke-width="0.01"/>'


def svg_dots(cx, y, n, color="#0000ff"):
    """n個の点（刻印）。1行5個まで、中心 cx にそろえる"""
    out = []
    for i in range(n):
        row, col = divmod(i, 5)
        cnt = min(5, n - row * 5)
        x = cx - (cnt - 1) * 0.6 + col * 1.2
        out.append(f'<circle cx="{x:.3f}" cy="{y + row * 1.3:.3f}" r="0.35" fill="{color}" stroke="none"/>')
    return "".join(out)


def comb_path(x0, y0, T, widths, depth=10.0, pitch_gap=6.0, h=24.0):
    """下の辺からスロットをカットした細長い板の外形（1本の閉じたパス）"""
    pts = [(x0, y0)]
    x = x0 + pitch_gap
    for w in widths:
        pts += [(x, y0), (x, y0 + depth), (x + w, y0 + depth), (x + w, y0)]
        x += w + pitch_gap
    L = x - x0
    pts += [(x0 + L, y0), (x0 + L, y0 + h), (x0, y0 + h)]
    d = "M " + " L ".join(f"{a:.3f},{b:.3f}" for a, b in pts) + " Z"
    return f'<path d="{d}" fill="none" stroke="#ff0000" stroke-width="0.01"/>', L


def laser_svg(T, out, lang="ja"):
    widths = [round(T + s, 3) for s in STEPS]
    parts, notes = [], []
    # 1) カーフテスト：外形20mm角、穴10mm角（穴を先にカットする）
    parts.append(svg_rect(10, 10, 10, 10))              # 内側の穴
    parts.append(svg_rect(5, 5, 20, 20))                # 外形
    # 2) スロットのコーム（スロットの奥に番号の点）
    comb, L = comb_path(35, 5, T, widths)
    x = 35 + 6.0
    for i, w in enumerate(widths):
        parts.append(svg_dots(x + w / 2, 5 + 10 + 3, i + 1))
        x += w + 6.0
    parts.append(comb)
    # 3) タブ（同じシートから。幅10mm）
    parts.append(svg_rect(35, 36, 40, 10))
    W, H = max(35 + L + 5, 80), 52
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.2f}mm" height="{H:.2f}mm" '
           f'viewBox="0 0 {W:.3f} {H:.3f}">\n<!-- {TXT[lang]["svg_note"].format(T=T)} -->\n'
           + "\n".join(parts) + "\n</svg>\n")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(svg)
    return widths


# ---------------- 3Dプリント（STL）
def cyl(x, y, d, z0, h):
    return m3.Manifold.cylinder(h, d / 2, d / 2, SEG).translate([x, y, z0])


def box(x0, y0, z0, w, d, h):
    return m3.Manifold.cube([w, d, h]).translate([x0, y0, z0])


def dimples(x, y, z_top, n):
    s = None
    for i in range(n):
        c = cyl(x + i * 1.8, y, 1.0, z_top - 0.6, 1.0)
        s = c if s is None else s + c
    return s


def to_mesh(mf):
    g = mf.to_mesh()
    return trimesh.Trimesh(np.asarray(g.vert_properties)[:, :3], np.asarray(g.tri_verts), process=False)


def fdm_fit(clr, out):
    pin_d, pitch, H = 6.0, 12.0, 5.0
    clrs = [round(clr + s, 3) for s in (-0.10, -0.05, 0.0, 0.05, 0.10)]
    n = len(clrs)
    plate = box(0, 0, 0, pitch * n + 4, 22, H)
    for i, c in enumerate(clrs):
        x = 2 + pitch / 2 + i * pitch
        plate = plate - cyl(x, 8, pin_d + 2 * c, -1, H + 2) - dimples(x - (i * 0.9), 18, H, i + 1)
    # ピン（土台つき）。土台の上に高さ8のピン
    pin = box(0, 26, 0, 14, 14, 2) + cyl(7, 33, pin_d, 2, 8)
    to_mesh(plate + pin).export(out)
    return clrs


def fdm_insert(depth, out):
    holes = [4.0, 4.1, 4.2, 4.3, 4.4]
    pitch, H = 12.0, depth + 2.0
    blk = box(0, 0, 0, pitch * len(holes) + 4, 20, H)
    for i, d in enumerate(holes):
        x = 2 + pitch / 2 + i * pitch
        blk = blk - cyl(x, 8, d, H - depth, depth + 1) - dimples(x - (i * 0.9), 16.5, H, i + 1)
    to_mesh(blk).export(out)
    return holes


def main():
    for _s in (sys.stdout, sys.stderr):        # Windows のパイプは ANSI コードページになるので UTF-8 にそろえる
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8", errors="replace")
    ver = common.version_from_argv()
    prm = common.load(ver, lang=common.lang_from_argv())
    P, lang = prm.P, prm.lang
    t = TXT[lang]
    out = os.path.join(common.ROOT, "out", "coupons")
    os.makedirs(out, exist_ok=True)
    lines = [t["title"].format(title=prm.meta.get('title', ''), ver=ver), "", t["intro"], ""]

    thick = sorted({v for k, v in vars(P).items() if k.startswith("t_") and isinstance(v, (int, float))})
    for T in thick:
        fn = f"laser_{T:g}mm.svg"
        widths = laser_svg(T, os.path.join(out, fn), lang)
        lines += [t["laser_h"].format(fn=fn, T=T), ""] + t["laser_steps"]
        lines += [f"| {i + 1} | {w:.2f} | {s:+.2f} |" for i, (w, s) in enumerate(zip(widths, STEPS))]
        lines += t["laser_after"]

    if not hasattr(P, "clr_fit"):                      # 3Dプリントを使わないプロジェクト（fab に clr_fit が無い）
        lines += partial_lines(lang)
        return finish(out, lines)
    clrs = fdm_fit(P.clr_fit, os.path.join(out, "fdm_fit.stl"))
    lines += t["fit_head"]
    lines += [f"| {i + 1} | {6 + 2 * c:.2f} | {c:.2f} |" for i, c in enumerate(clrs)]
    lines += t["fit_after"]

    if hasattr(P, "insert_depth"):
        holes = fdm_insert(P.insert_depth, os.path.join(out, "fdm_insert.stl"))
        lines += [x.format(h0=holes[0], h1=holes[-1], depth=P.insert_depth) for x in t["insert_head"]] \
            + [f"| {i + 1} | {d:.1f} |" for i, d in enumerate(holes)]
    lines += partial_lines(lang)
    finish(out, lines)


def partial_lines(lang="ja"):
    return list(TXT[lang]["partial"])


def finish(out, lines):
    with open(os.path.join(out, "coupons.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print(out)
    for f in sorted(os.listdir(out)):
        print(" ", f)


if __name__ == "__main__":
    main()
