"""今の版の寸法を、根拠・資料・状態つきで monozukuri の寸法ファイルの形（params/params_<版>.json）に書き出す。
確認ボード（build_page.py）が「寸法と根拠」に載せる。値は gen_case.py から取るので、ここには根拠だけを書く。
使い方: python3 tools/dims_export.py  → params/params_<ver>.json
status：規格（規格・メーカー仕様）／決定（決定事項に理由あり）／計算（他の値から決まる）／仮（要実測・未確定）／初期値（試し片で測る）／経験則
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import gen_case as g

TRAY = getattr(g, "CASE", "sandwich") == "tray"
REC = getattr(g, "STIFF_RECESS", False)
KIJUN, JISSOKU, KETTEI = "基準寸法.md", "dz60_実測.md", "決定事項.md"


def it(value, label, basis, status, ref="", unit="mm"):
    return {"value": round(value, 3) if isinstance(value, float) else value, "unit": unit, "label": label,
            "basis": basis, "status": status, "ref": ref}


def build():
    P = {}
    P["outer_w"] = it(g.OUTER_W, "外形の幅（X）", "旧デザイン（swillkb で作ったケース）の外形を踏襲", "決定", KETTEI)
    P["outer_d"] = it(g.OUTER_H, "外形の奥行き（Y）", "同上", "決定", KETTEI)
    P["corner_r"] = it(g.CORNER_R, "外形の角の丸み（Apple風）", "v12 で R8・スムージング0.6 に（v11 までは R12）。角とネジ穴の距離から", "決定", KETTEI)
    P["wall"] = it(g.WALL, "枠の壁の幅", "旧デザイン。枠の内側 287×98 で PCB とのすき間 約1.0", "決定", KIJUN)
    P["pcb_w"] = it(g.PCB_W, "PCBの幅", "GH60 オープンソースPCB の外形。DZ60 は GH60 互換（要実測）", "規格", KIJUN)
    P["pcb_d"] = it(g.PCB_H, "PCBの奥行き", "同上", "規格", KIJUN)
    P["pcb_t"] = it(g.PCB_T, "PCBの厚さ", "一般的なFR4の1.6。DZ60 の実測で置き換える", "仮", JISSOKU)
    P["key_pitch"] = it(19.05, "キーの間隔（1U）", "MX 系キーボードの標準", "規格", KIJUN)
    P["plate_top_to_pcb"] = it(g.PLATE_TOP_TO_PCB_TOP, "プレート上面〜PCB上面", "MX スイッチの規格寸法", "規格", KIJUN)
    P["top_t"] = it(g.TOP_T, "トッププレートの厚さ（アクリル）", "MX の爪が掛かるのは1.6mm以下", "規格", KIJUN)
    P["switch_cut"] = it(14.0, "スイッチ穴（カーフ補正前）", "MX 標準。穴形状は旧 swillkb の出力（65キーと全数一致を確認）", "規格", "swillkb_switch_layer.svg")
    P["stiff_t"] = it(g.STIFF_T, "補強板の厚さ（アクリル）", "2026-10-15 決定（3mm1枚案は爪が掛からず不可）。2mm/3mm はテストカットで決める", "仮", KETTEI)
    P["stiff_offset"] = it(g.STIFF_OFFSET, "補強板の穴の逃げ（片側）", "スイッチの爪が開く空間。テストカットで確かめる", "仮", KIJUN)
    P["gap_stiff_pcb"] = it(g.GAP_STIFF_PCB, "補強板の下面〜PCB上面", "plate_top_to_pcb − top_t − stiff_t", "計算")
    P["under_pcb"] = it(g.UNDER_PCB, "PCB下面〜底の上面（台座の高さ）", "PCB裏の部品・USB-C より高く。DZ60 の実測で決める", "仮", JISSOKU)
    P["frame_h"] = it(g.FRAME_H, "枠の高さ（掘り込みの床まで、底を除く）", "gap_stiff_pcb ＋ pcb_t ＋ under_pcb", "計算")
    if TRAY:
        P["floor_t"] = it(g.FLOOR_T, "トレーの底の厚さ（PLA）", "v17 のボトムプレート3.0と同じにして全体の高さを変えない", "仮", KETTEI)
    else:
        P["bottom_t"] = it(g.BOTTOM_T, "ボトムプレートの厚さ（アクリル）", "手持ちの3mm（仮）。シートごとに実測", "仮", KETTEI)
        P["skirt_t"] = it(g.SKIRT_T, "スカートの厚さ", "v16：横からボトムプレートを見せないため", "決定", KETTEI)
        P["skirt_h"] = it(g.SKIRT_H, "スカートの高さ", "bottom_t − 0.1（足がボトムプレートを直接押さえる）", "計算", KETTEI)
    if REC:
        P["stiff_lip"] = it(g.STIFF_LIP, "補強板の掘り込みの外側の縁", "v17：側面に見えるアクリルをトッププレートだけにする。スカートと同じ2mm", "決定", KETTEI)
    P["total_h"] = it(round(g.TOP_T + g.STIFF_T + g.FRAME_H + g.BOTTOM_T, 2), "全体の高さ（足・キーキャップ別）", "各層の合計", "計算")
    P["usb_x"] = it(round(g.USB_X, 2), "USB切り欠きの中心（PCB左端から）", "GH60 標準の位置。DZ60 の実測で置き換える", "仮", JISSOKU)
    P["usb_w"] = it(g.USB_W, "USB切り欠きの幅", "ケーブルの太い部分（USB-C のオーバーモールド 約12.35）＋余裕。手持ちのいちばん太いケーブルで試す", "経験則")
    P["split_x"] = it(g.SPLIT_X, "枠の分割位置（X）", "中央。半分がプリンタの造形範囲に載る", "決定")
    P["bed"] = it(220, "プリンタの造形範囲（Ender-3 Pro）", "メーカー仕様 220×220×250", "規格")
    P["hole_d"] = it(g.HOLE_D, "M3ボルト穴", "JIS B 1001 2級（1級3.2／2級3.4／3級3.6）", "規格")
    P["bolt_l"] = it(g.BOLT_L, "M3ボルトの長さ（8本）", "全層＋足のナットまで。ナットの上に残る厚さ " + f"{g.FOOT_SKIN}", "計算")
    P["nut_af"] = it(g.NUT_AF, "M3ナットの二面幅", "ISO 4032／JIS B 1181", "規格")
    P["nut_t"] = it(g.NUT_T, "M3ナットの厚さ", "同上（最大2.4）", "規格")
    P["tilt"] = it(g.tilt_deg(), "傾き", "v14 で 0°（平ら）。3〜5° にするかは未決", "決定", KETTEI, unit="°")
    P["tongue_t"] = it(g.TONGUE_T, "継ぎ目のほぞ（舌）の厚さ", ("トレーは底を下に刷るので下側に。ナット溝3.4の上に2.1残る" if TRAY
                                                          else "枠は上面を下に刷るので上側に。ざぐりの下に1.9残る"), "計算")
    P["joint_bolt"] = it(g.JB_L, "継ぎ目のボルト M3（ボタンヘッド）の長さ", "頭のざぐりからナットまで。ナットに約" + (f"{g.check_joint().get('engagement', '')}" if TRAY else "2.4") + "mm掛かる", "計算")
    if getattr(g, "USB_H", None) and TRAY:     # v19
        P["usb_h"] = it(g.USB_H, "USBの窓の高さ（角丸の長穴）", "USB-C のオーバーモールド 約6.5＋余裕。窓の上下にPLAを残す（フィードバック：上下が薄くて折れそう）", "仮", JISSOKU)
        P["usb_zc"] = it(round(g.usb_zc(), 2), "USBの窓の中心の高さ（トレーの下面から）", "底の上面と掘り込みの床の中間（仮）。DZ60 の USB-C の高さを実測して決める", "仮", JISSOKU)
        P["usb_boss"] = it(g.USB_BOSS, "USBの窓の上で掘り込みを止める範囲（窓の左右に足す幅）", "窓の上の壁を上まで残す（補強板はそこを切り欠く）", "決定")
    if getattr(g, "STIFF_NOTCH", False):
        P["stiff_notch"] = it("U字", "補強板のネジ穴の形", "縁へ開いたU字の切り欠き（フィードバック：穴と縁の間が約2.8mmで割れが不安）", "決定", unit="")
    if getattr(g, "SEAM_V", 0):
        P["seam_v"] = it(g.SEAM_V, "継ぎ目のV溝の深さ（90°）", "継ぎ目の線を意図した線に見せる（確認ボードの答え）", "決定", KETTEI)
    if getattr(g, "BED_CHAMFER", 0) and TRAY:
        P["bed_chamfer"] = it(g.BED_CHAMFER, "トレーの下面の外周の面取り（45°、0.2mmの段）", "反り・エレファントフットの対策。ベッドに接する縁は面取りにする（Hubs）。ブリムはスライサーで", "経験則")
    if getattr(g, "BOLT_HEAD", None):
        P["bolt_head"] = it(g.BOLT_HEAD, "天面のボルトの頭", "確認ボードの答え：頭の低いもの", "決定", unit="")
    F = {}
    F["kerf"] = it(g.KERF, "レーザーのカーフ（切断溝の全幅）", "まだ補正していない（0）。3mmアクリル・CO2 の公開値は0.125〜0.18。試し片で測る", "初期値")
    F["clr_tongue"] = it(g.TONGUE_CLEAR, "ほぞ穴のすき間（片側）", "FDM の一般クリアランス0.2。±0.1 の3段の試し片で決める", "初期値")
    if REC:
        F["clr_stiff"] = it(g.STIFF_CLEAR, "補強板の掘り込みのすき間（片側）", "同上。アクリルの外形のばらつきも見る", "初期値")
    if not TRAY:
        F["clr_skirt"] = it(g.SKIRT_CLEAR, "スカートとボトムプレートのすき間（片側）", "同上", "初期値")
    F["nut_pocket"] = it(g.NUT_POCKET_AF, "ナット溝の二面幅", "ナット5.5＋0.6（少しきつめ）。印刷して調整", "初期値")
    if getattr(g, "RELIEF", 0):
        F["relief"] = it(g.RELIEF, "内角の逃げ（ほぞ穴の奥の角・掘り込みの床と縁のL字）", "3Dプリントの内角はノズル径ほど丸くなり、相手の角が当たる。試し片で要否と大きさを決める", "初期値")
    if TRAY and getattr(g, "NUT_ENGAGE", None):
        F["nut_engage"] = it(g.NUT_ENGAGE, "足のナットへのボルトの掛かり", "M3×16 で全層13.6＋ナットの上の肉0.6。ねじ山3山（ピッチ0.5）", "計算")
    F["overhang_deg"] = it(45, "サポートなしで刷れる張り出し角", "FDM の一般的な目安（45°ルール）", "経験則", unit="°")
    for v in list(P.values()) + list(F.values()):
        if not v["ref"]:
            v.pop("ref")
    return {"meta": {"version": g.VER, "parent": getattr(g, "PARENT", None), "lang": "ja",
                     "note": "tools/dims_export.py が gen_case.py の値から書き出す。手で直さない（根拠は dims_export.py に書く）"},
            "params": P, "fab": F}


def main():
    os.makedirs(os.path.join(g.ROOT, "params"), exist_ok=True)
    out = os.path.join(g.ROOT, "params", f"params_{g.VER}.json")
    d = build()
    json.dump(d, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n = len(d["params"]) + len(d["fab"])
    loose = [k for s in ("params", "fab") for k, v in d[s].items() if v["status"] in ("仮", "初期値")]
    print(f"{out}（{n}項目。仮・初期値 {len(loose)}：{', '.join(loose)}）")


if __name__ == "__main__":
    main()
