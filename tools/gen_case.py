"""積層ケース（旧デザイン2025-03-05踏襲）の図面を生成する。

構成（上から）
  トッププレート … アクリル1.5mm・レーザー加工。スイッチ穴・スタビ穴は旧swillkb出力をそのまま使う
  補強板         … アクリル・レーザー加工。スイッチの周りを大きめに抜いた板。トッププレートの下に重ねる
  枠             … PLAで3Dプリント（Ender-3 Proに収まるよう左右2分割）
  ボトムプレート … アクリル・レーザー加工
  4層をM3ネジ8本で共締め（接着しない）。PCBはネジ止めせず、スイッチの爪（上方向）と肩（下方向）で
  トッププレートに固定し、ボトムプレート側の柔らかい台座で下から軽く支える

座標：原点＝PCB外形の左上、X右・Y下、単位mm（README のルール）。
SVGは viewBox に負の原点を使い、Inkscapeでは外形の左上がページの左上になる。

使い方: python3 tools/gen_case.py
"""
import json
import os
import re
import sys

from shapely.geometry import Point, Polygon, box
from shapely import affinity

sys.path.insert(0, os.path.dirname(__file__))
import squircle as sq

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VER = "v18"

# v18（ブランチ claude/tray-v18）：トレー型。枠とボトムプレートを1つのPLAのトレー（上だけ開いた箱）にする。
# トレーは底を下にして印刷（補強板の掘り込みは上向き、スカートは無し）→ サポートの要る面がほぼ無い
CASE = "tray"                       # "tray"＝トレー型（v18）／"sandwich"＝枠＋アクリルのボトムプレート（v17まで）
FLOOR_T = 3.0                       # トレーの底の厚さ（v17のボトムプレートと同じ。全体の高さを変えない）

# ---- パラメータ（ここだけ直せば全図面が追従する） ---------------------------
PCB_W, PCB_H = 285.0, 94.6          # GH60基準（要実測）
OUTER_W, OUTER_H = 315.0, 126.0     # 旧デザインの外形
WALL = 14.0                         # 枠の幅 → 枠の内側 287×98（旧デザイン）
CORNER_R = 8.0                      # 角丸（v12で一旦R8。v11まではR12）
CORNER_SMOOTH = 0.6                 # 0=普通の円弧、0.6前後=Apple風（仮）
INNER_R = 4.5                       # 枠の内側の角丸。PCBの角とのすき間0.5mm以上を保てる最大がR4.5（Apple風）
INNER_SMOOTH = 0.6
PCB_MIN_CLEAR = 0.5                 # 枠の内側とPCBの最小すき間（これを下回るとエラー）
HOLE_D = 3.4                        # M3通し穴（旧デザイン）
# ネジ穴：旧デザインの位置（外形の左上からの距離）。下側中央2個の旧Y=120.7は119に揃えた
# v09：中央2本を左右対称に（旧デザインの192→207.3）。左右の足を鏡像の同じ形にするため
HOLES_FROM_OUTER = [(7, 7), (107.7, 7), (207.3, 7), (308, 7),
                    (7, 119), (107.7, 119), (207.3, 119), (308, 119)]
KERF = 0.0                          # レーザーのカーフ（M1で決める）
SPLIT_X = PCB_W / 2                 # 枠の分割位置（中央）
# 枠の継ぎ目：ほぞ（左半分の上側から出る舌）＋縦向きのM3ボルト。前後の壁に1組ずつ（v16で上下を逆に：枠は上面を下にして印刷するため）。
# ボルトは他の8本と同じ縦向き。頭はほぞの上面のざぐり（補強板で隠れる）、ナットは右半分の下面（段差の面）に埋め込む（ボトムプレートで隠れる）
JOINT = "tongue_vbolt"              # "tongue_vbolt"＝ほぞ＋縦ボルト／"pin"＝φ1.75フィラメントの位置決めピン（v14まで）
TONGUE_W, TONGUE_T, TONGUE_L = 9.0, 3.8, 16.0   # ほぞ（舌）：幅（Y）・厚さ（Z、枠の上面から下へ）・長さ（継ぎ目から右へ）
if CASE == "tray":                  # トレーは底を下にして刷るので、ほぞは下側（ベッドの上）に戻す。底の分だけ壁が高いので舌も厚く
    TONGUE_T = 5.5                  # 舌の厚さ（トレーの下面から上へ）
TONGUE_CLEAR = 0.2                  # ほぞ穴のすき間（幅は片側、高さと長さも同じだけ）
JB_L = 6.0                          # 継ぎ目のボルト M3×6 ボタンヘッド（他の8本と同じ種類）
JB_X = 8.0                          # 継ぎ目からボルトの中心まで（右半分の側）
JB_CB_D, JB_CB_DEPTH = 6.2, 1.9     # 頭のざぐり（ボタンヘッドφ5.7×1.65）
JB_NUT_DEPTH = 2.6 if CASE != "tray" else 3.4   # ナット溝の深さ（二面幅 NUT_POCKET_AF）。サンドイッチ：右半分の枠の下面から。トレー：ナットは左の舌の下面（トレーの底面）から。ボルトの先が底面から出ない深さ
if CASE == "tray":
    JB_L = 8.0                      # トレー：M3×8（頭は右半分の上＝補強板の掘り込みの床、ナットは舌の下面）
USB_X = 142.5 - 124.3               # USB中心X：GH60標準（swillkb −124.3）。要実測
USB_W = 13.0                        # USB切り欠き幅（ケーブルの太い部分が通る幅。旧10mm）
# ---- 高さ方向（PCBはネジ止めしない）
# スイッチの爪をトッププレート（1.5mm）の裏に引っかけて上方向を止め、肩（フランジ）で下方向を止める。
# PCBはボトムプレート側の柔らかい台座で軽く押し上げる（支え＋ダンパー）。
# 剛性はトッププレートの下に重ねる補強板で確保し、補強板は枠との間に挟んでM3ネジで共締めする（接着しない）。
TOP_T = 1.5                         # トッププレート（アクリル）。MXの爪がかかる厚さ（1.6mm以下）
STIFF_T = 2.0                       # 補強板（アクリル）厚さ（仮）。3.0にするとPCBとのすき間は0.5mm
STIFF_OFFSET = 0.8                  # 補強板の抜き：トッププレートの穴より片側この分だけ大きく（スイッチ穴→15.6角。爪が開く空間）
STIFF_MIN_WEB = 2.0                 # 補強板の穴と穴の間の最小幅（これより細くなる所はつなげて抜く）
PLATE_TOP_TO_PCB_TOP = 5.0          # MXスイッチの規格寸法（プレート上面〜PCB上面）
PCB_T = 1.6                         # 要実測
UNDER_PCB = 5.0                     # PCB下面〜ボトムプレート上面（台座の高さ＝裏面部品・USB-Cより高く）。要実測
BOTTOM_T = 3.0                      # ボトムプレート（アクリル）厚さ（仮）
# v16：枠を下へスカート状に延ばし、ボトムプレートをその内側にはめ込む（横からボトムプレートが見えない＝塊に見せる）
SKIRT = CASE != "tray"
SKIRT_T = 2.0                       # スカートの厚さ（枠の外面から）
SKIRT_CLEAR = 0.2                   # スカートの内面とボトムプレートの縁のすき間
SKIRT_H = BOTTOM_T - 0.1            # スカートの高さ。ボトムプレートより0.1低く、足がボトムプレートを確実に押さえる
# v17：補強板を枠の上面の掘り込みに入れる（横から見えるアクリルはトッププレート1.5mmだけ）。全体の高さは変わらない
STIFF_RECESS = True
STIFF_LIP = 2.0                     # 掘り込みの外側に残す枠の縁の幅（スカートと同じ2mm）
STIFF_CLEAR = 0.2                   # 掘り込みの内面と補強板の縁のすき間
BP_NOTCH = True                     # ボトムプレートのネジ穴を、縁から切り込んだU字の切り欠きにする（位置はスカートで決まる）
GAP_STIFF_PCB = round(PLATE_TOP_TO_PCB_TOP - TOP_T - STIFF_T, 2)      # 補強板の下面〜PCB上面
FRAME_H = round(GAP_STIFF_PCB + PCB_T + UNDER_PCB, 2)                   # 枠の厚さ（自動計算）
assert TOP_T <= 1.6, "トッププレートが1.6mmを超えるとMXの爪がかからない"
assert GAP_STIFF_PCB >= 0.3, "補強板が厚すぎてPCBに当たる"
# ---- 外観
FRAME_INSET = 0.3                   # 枠の外周をアクリルより内側へ下げる量。印刷の誤差で枠がはみ出さず、細い影の線になる
# ---- ボルト・足（ボトムプレートの下にナット受けを兼ねた足。M3ボルトを上から通して全層を共締め）
BOLT_L = 18.0                       # M3ボルトの長さ（8本共通）
NUT_AF, NUT_T = 5.5, 2.4            # M3ナット（二面幅・厚さ）
NUT_POCKET_AF = 6.1                 # 足のナット溝の二面幅（少しきつめ。印刷して調整）
FOOT_D = 12.0                       # 足（丸い台）の直径。外形より1mm以上内側に収まり、浮いて見える
TILT_DEG = 5.0                      # キーボードの傾き（仮）。0〜7°程度
FOOT_SKIN = round(BOLT_L - (TOP_T + STIFF_T + FRAME_H + BOTTOM_T) - NUT_T, 2)  # ナットの上に残るPLAの厚さ
# ---- 奥側の足：真鍮の丸棒（ボトムプレートの奥側の下面に沿わせて左右方向に置く。横から見ると端の丸が見える）
PLA_TILT_DEG = 0.0                  # 奥もPLAのとき（pla_bars）の傾き。None＝丸棒（ROD_D）と同じ傾き。v14で0°（平ら）
REAR_FOOT = "pla_bars"              # "pla_bars"＝奥もPLAのバー（v13、丸棒の代わり。傾き・穴位置は丸棒φ8と同じ）／"brass_rod"／"pucks"（丸台8個）
ROD_D = 8.0                         # 丸棒の直径。傾きはこれで決まる（v12で一旦φ8。v11まではφ12）
ROD_BOLT_L = 20.0                   # 後ろ4本のボルト長さ（丸棒のめねじにねじ込む）
ROD_TAP_DRILL = 2.5                 # M3めねじの下穴
ROD_HOLE_DEPTH = 7.5                # 下穴の深さ（平面または上端から）。φ12なら下に約4mm残る
ROD_TAP_DEPTH = 6.0                 # 有効ねじ深さ（ねじ込み量より深く）
ROD_HOLE_THROUGH = True             # めねじを貫通にする（φ8では溝底から下まで6.4mmしかないので貫通。ドリル・タップとも通しで加工が楽）
ROD_TIP_MARGIN_MIN = 1.0            # 貫通のとき、ボルトの先端から穴の下の出口までの最小距離（先端が下のテープを押さない）
ROD_FLAT_W = 0.0                    # 丸棒の上面をフライスで平らにする幅（0＝平面なし）。v10は6.0
# ---- v11：旋盤で各ねじ穴の位置に浅い溝を掘り、ゴムテープを巻く（ボトムプレートと机の両方にテープが当たる）
ROD_TAPE = True
TAPE_W = 10.0                       # テープの幅
GROOVE_W = 10.5                     # 溝の幅（テープ＋0.5）
GROOVE_DEPTH = 0.8                  # 溝の深さ。テープより少し浅く → 締めるとテープが沈み、丸棒の外周がほぼプレートに接する（溝底φ10.4）
TAPE_T = 1.0                        # テープの厚さ（仮）。溝より0.2厚い分だけ締めるとつぶれる
TAPE_SQUEEZE_TOP = 1 - GROOVE_DEPTH / TAPE_T   # 上側は溝の深さまでつぶれる＝丸棒の外周がプレートに接する（金属で止まるので4層もしっかり締まる）
TAPE_SQUEEZE_BOTTOM = 0.1           # 下側（机側）のつぶれ率（自重のみ）
ROD_END_MODE = "side"               # "side"＝端を側面にそろえる（横から丸がよく見える）／"inside"＝上から見て角丸の内側に収める
ROD_END_INSET = 0.5                 # 端を側面より内側に下げる量
ROD_HOLE_FROM_END_MIN = 6.0         # めねじの中心から丸棒の端までの最小距離（割れ防止）
ROD_GROOVE_END_LAND = 3.0           # 溝の縁から丸棒の端までの最小の幅（端の面取りと溝の間に残す肉）
HOLE_EDGE_MIN = 4.5                 # 後ろの角の穴を一直線に並べるときの、穴の縁から外周・枠の内側までの最小距離
REAR_HOLE_D = 4.0                   # 後ろの4穴（全層）。丸棒の穴位置が±0.3mmずれても組めるよう大きめ。ボタンヘッドφ5.7で隠れる
# ---- 丸棒の受け台（3Dプリント）：ボトムプレートと丸棒の間に挟み、丸棒が線で当たってアクリルが割れるのを防ぐ
SADDLE = True
SADDLE_T_MIN = 1.0                  # 受け台のいちばん薄い所（丸棒の真上）。ボルトのねじ込み量に直結
SADDLE_W = 9.0                      # 受け台の幅（前後方向）
SADDLE_CLEAR = 0.1                  # 受け台の凹面と丸棒のすき間（半径方向）
# ---- 足の形：手前のナット受けと奥の丸棒受けを、同じ列どうし前後につないだ1本の足×4（2026-10-15）
FOOT_STYLE = "pairs"                # "pairs"＝左右ずつまとめた足（手前バー×2＋奥の丸棒受け×2）／"ribs"＝前後一体×4／"separate"＝丸台＋受け台
RIB_W = 12.0                        # 足の幅（左右方向）
RIB_T = 3.0                         # 足の厚さ（手前の台と奥の丸棒受け以外の部分）。丸棒受けの高さ以上にする
SWILLKB = os.path.join(ROOT, "tools/data/swillkb_switch_layer_2025.svg")
# -----------------------------------------------------------------------------

OX = PCB_W / 2 - OUTER_W / 2        # 外形の左上（PCB座標）
OY = PCB_H / 2 - OUTER_H / 2


def outer_pts():
    return sq.rounded_rect_points(OX, OY, OUTER_W, OUTER_H, CORNER_R, CORNER_SMOOTH)


def frame_outer_pts():
    if not FRAME_INSET:
        return outer_pts()
    return list(Polygon(outer_pts()).buffer(-FRAME_INSET, join_style=1).exterior.coords)[:-1]


def stiff_pocket_poly():
    """枠の上面の掘り込み（補強板が入る所）：枠の外形から STIFF_LIP 内側。"""
    return Polygon(frame_outer_pts()).buffer(-STIFF_LIP, join_style=1, quad_segs=24)


def stiff_outer_pts():
    """補強板の外形。v17から掘り込みのすき間の分だけ小さい（v16までは外形と同じ）。"""
    if not STIFF_RECESS:
        return outer_pts()
    return list(stiff_pocket_poly().buffer(-STIFF_CLEAR, join_style=1, quad_segs=24).exterior.coords)[:-1]


def is_flat_pla():
    """奥もPLAで傾き0°：足4本を同じ形にする。"""
    return REAR_FOOT == "pla_bars" and PLA_TILT_DEG is not None and abs(PLA_TILT_DEG) < 1e-9


def joint_wall_y():
    """継ぎ目のボルト・ほぞを置く前後の壁の中心（PCB座標のY）。枠は外形より FRAME_INSET 内側。"""
    rear = ((OY + FRAME_INSET) + (OY + WALL)) / 2
    front = ((OY + OUTER_H - FRAME_INSET) + (OY + OUTER_H - WALL)) / 2
    return [round(rear, 3), round(front, 3)]


def tray_h():
    """トレーの壁の高さ（下面〜補強板の掘り込みの床）。"""
    return FLOOR_T + FRAME_H


def check_joint():
    """継ぎ目の寸法の確認：ほぞ穴の下の肉とナット、ほぞのざぐりの下の肉、ボルトの先がナットの下面と合うか。"""
    if JOINT != "tongue_vbolt":
        return
    if CASE == "tray":     # 舌は下側（左半分）、ナットは舌の下面、頭は右半分の上面のざぐり
        H = tray_h()
        above = H - (TONGUE_T + TONGUE_CLEAR)              # 右半分：ほぞ穴の上に残る厚さ
        seat = H - JB_CB_DEPTH
        tip = seat - JB_L
        nut_bottom = JB_NUT_DEPTH - NUT_T
        assert above - JB_CB_DEPTH >= 1.5, "ざぐりとほぞ穴の間の肉が薄い"
        assert TONGUE_T - JB_NUT_DEPTH >= 1.5, "舌のナット溝の上の肉が薄い"
        assert 0.0 <= tip <= JB_NUT_DEPTH - 0.6, f"ボルトの先が底面から出る／ナットにかからない（{tip:.2f}）"
        return dict(above=round(above, 2), seat=round(seat, 2), tip=round(tip, 2),
                    engagement=round(JB_NUT_DEPTH - max(tip, nut_bottom), 2))
    under = FRAME_H - (TONGUE_T + TONGUE_CLEAR)        # 右半分：ほぞ穴の下に残る厚さ
    seat = FRAME_H - JB_CB_DEPTH                        # 頭の座面（枠の下面から）
    tip = seat - JB_L
    assert under - JB_NUT_DEPTH >= 1.2, "ナット溝とほぞ穴の間の肉が薄い"
    assert TONGUE_T - JB_CB_DEPTH >= 1.5, "ほぞのざぐりの下の肉が薄い"
    assert 0 <= tip <= JB_NUT_DEPTH - NUT_T + 0.1, f"ボルトの先がナットの下面に合わない（{tip:.2f}）"
    assert (TONGUE_W - JB_CB_D) / 2 >= 1.2, "ほぞのざぐりの横の肉が薄い"
    return dict(under=round(under, 2), seat=round(seat, 2), tip=round(tip, 2))


def bottom_outline():
    """ボトムプレートの外形：スカートの内側（外形から FRAME_INSET＋SKIRT_T＋SKIRT_CLEAR 内側）。"""
    if not SKIRT:
        return Polygon(outer_pts())
    return Polygon(outer_pts()).buffer(-(FRAME_INSET + SKIRT_T + SKIRT_CLEAR), join_style=1, quad_segs=24)


def bottom_poly():
    """ボトムプレート：外形からネジ穴の切り欠き（U字、近い方の縁＝前後へ開く）を除いた形。"""
    from shapely.geometry import Point, box as _b
    from shapely.ops import unary_union
    P = bottom_outline()
    if not BP_NOTCH:
        return P
    cuts = []
    ymid = OY + OUTER_H / 2
    for c in holes():
        d = hole_d(c)
        r = d / 2
        if c[1] < ymid:      # 奥の列（PCB座標でYが小さい）→ 奥の縁へ
            slot = _b(c[0] - r, OY - 5, c[0] + r, c[1])
        else:
            slot = _b(c[0] - r, c[1], c[0] + r, OY + OUTER_H + 5)
        cuts.append(unary_union([Point(c).buffer(r, quad_segs=24), slot]))
    return P.difference(unary_union(cuts))


def skirt_ring():
    """スカート：枠の外形から SKIRT_T 内側までの輪。"""
    fo = Polygon(frame_outer_pts())
    return fo.difference(fo.buffer(-SKIRT_T, join_style=1, quad_segs=24))


def rod_layout():
    """後ろの穴を一直線に並べ、傾きを丸棒（ROD_D）で決める配置。PLAのバーでも同じにして、あとで丸棒に差し替えられるようにする。"""
    return REAR_FOOT in ("brass_rod", "pla_bars")


def _h_front(tan):
    import math
    nut_r = NUT_POCKET_AF / math.sqrt(3)              # 六角の外接円の半径
    # 前の足：ナット（＋0.3mm）が傾いた底面から出ない最小の高さ
    return math.ceil((FOOT_SKIN + NUT_T + 0.3 + nut_r * tan) * 10) / 10


def rod_end_min():
    """めねじの中心から丸棒の端までの最小距離（テープの溝があれば、溝の縁から端までROD_GROOVE_END_LANDを残す）。"""
    m = ROD_HOLE_FROM_END_MIN
    if ROD_TAPE and ROD_FLAT_W <= 0:
        m = max(m, GROOVE_W / 2 + ROD_GROOVE_END_LAND)
    return m


def _rod_end_x(y_rear, sx=1):
    """丸棒の端のX（左端 sx=1／右端 sx=-1）。"""
    from shapely.geometry import LineString
    o = Polygon(outer_pts())
    y_check = y_rear if ROD_END_MODE == "side" else y_rear - ROD_D / 2
    x0 = max(LineString([(OX - 5, y_check), (OX + OUTER_W + 5, y_check)]).intersection(o).bounds[0], OX) + ROD_END_INSET
    return x0 if sx == 1 else OX + OUTER_W - (x0 - OX)


def rod():
    """真鍮丸棒：中心線のY、直径、両端のX、めねじの位置（丸棒の左端からの距離も）。"""
    hs = holes()
    y_rear = min(y for _, y in hs)
    rear = sorted(x for x, y in hs if abs(y - y_rear) < 1e-6)
    # 端：丸棒が上から見て外形の内側に収まる範囲（丸棒の奥側の縁＝いちばん角丸に近い所で判定）
    from shapely.geometry import LineString
    o = Polygon(outer_pts())
    y_check = y_rear if ROD_END_MODE == "side" else y_rear - ROD_D / 2
    x0 = max(LineString([(OX - 5, y_check), (OX + OUTER_W + 5, y_check)]).intersection(o).bounds[0], OX)
    x1 = OX + OUTER_W - (x0 - OX)
    x0, x1 = x0 + ROD_END_INSET, x1 - ROD_END_INSET
    # 上から見て外形からはみ出す量（丸棒の奥側の縁の高さで）
    xr = LineString([(OX - 5, y_rear - ROD_D / 2), (OX + OUTER_W + 5, y_rear - ROD_D / 2)]).intersection(o).bounds[0]
    info = dict(y=y_rear, d=ROD_D, x0=round(x0, 2), x1=round(x1, 2), length=round(x1 - x0, 1), end_mode=ROD_END_MODE,
                holes_x=rear, holes_from_left_end=[round(x - x0, 2) for x in rear],
                plan_overhang_at_rear_corner=round(max(0.0, xr - x0), 1))
    if min(info["holes_from_left_end"][0], x1 - rear[-1]) < rod_end_min() - 0.05:
        raise SystemExit(f"丸棒の端のめねじが端に近すぎる（{info['holes_from_left_end'][0]}mm）。ROD_END_MODEか穴位置を見直す")
    return info


def feet():
    """足の一覧と傾き。丸棒のときは前の4個だけを返し、傾きは「前の足の底」と「丸棒の下側」が同じ机の面に乗る角度で決める。"""
    import math
    hs = holes()
    y_front = max(y for _, y in hs)
    if REAR_FOOT == "pla_bars" and PLA_TILT_DEG is not None:
        tan = math.tan(math.radians(PLA_TILT_DEG))
        h_front = _h_front(tan)
        front = [(x, y) for x, y in hs if abs(y - y_front) < 8]
    elif rod_layout():
        r = rod()
        yc, zc, rr = r["y"], rod_center_z(), rod_contact_r()
        tan = 0.05
        for _ in range(60):          # 机の面が丸棒に接する傾きを求める（反復）
            hf = _h_front(tan)
            # 机の面：z = -(hf + (y_front - y)·tan)。丸棒の中心からの距離 = 半径
            f = lambda tt: (zc + _h_front(tt) + (y_front - yc) * tt) / math.sqrt(1 + tt * tt) - rr
            lo, hi = 0.0, 0.3
            for _ in range(60):
                mid = (lo + hi) / 2
                if f(mid) > 0:
                    hi = mid
                else:
                    lo = mid
            tan = (lo + hi) / 2
        h_front = _h_front(tan)
        front = [(x, y) for x, y in hs if abs(y - y_front) < 8]
    else:
        tan = math.tan(math.radians(TILT_DEG))
        h_front = _h_front(tan)
        front = hs
    out = []
    for x, y in front:
        h = h_front + (y_front - y) * tan
        out.append(dict(x=x, y=y, h=round(h, 2), pocket_top=FOOT_SKIN))
    return out, h_front, tan, y_front


def rod_flat_depth():
    """平面の深さ（丸棒の頂点から平面まで）。"""
    import math
    if ROD_FLAT_W <= 0:
        return 0.0
    R = ROD_D / 2
    return R - math.sqrt(R * R - (ROD_FLAT_W / 2) ** 2)


def rod_top_gap():
    """ボトムプレートの下面から丸棒の上端（外周、平面ありなら平面）までの距離。"""
    if not rod_layout():
        return 0.0
    if ROD_FLAT_W > 0:
        return 0.0
    if ROD_TAPE:
        return round(TAPE_T * (1 - TAPE_SQUEEZE_TOP) - GROOVE_DEPTH, 3)
    return SADDLE_T_MIN if SADDLE else 0.0


def rod_contact_r():
    """丸棒の中心から机に当たる所までの距離（テープなら溝底＋つぶれたテープ）。"""
    if rod_layout() and ROD_TAPE and ROD_FLAT_W <= 0:
        return ROD_D / 2 - GROOVE_DEPTH + TAPE_T * (1 - TAPE_SQUEEZE_BOTTOM)
    return ROD_D / 2


def rod_hole_top_z():
    """めねじの入口（平面・溝底・外周の上端）のZ。"""
    zt = rod_center_z() + ROD_D / 2 - rod_flat_depth()
    if rod_layout() and ROD_TAPE and ROD_FLAT_W <= 0:
        zt -= GROOVE_DEPTH
    return zt


def rod_hole_len():
    """下穴の長さ。貫通なら入口（溝底・平面・上端）から丸棒の下側（溝底）まで。"""
    if ROD_HOLE_THROUGH:
        bottom = rod_center_z() - ROD_D / 2 + (GROOVE_DEPTH if (ROD_TAPE and ROD_FLAT_W <= 0) else 0.0)
        return round(rod_hole_top_z() - bottom, 3)
    return ROD_HOLE_DEPTH


def rod_tap_len():
    return rod_hole_len() if ROD_HOLE_THROUGH else ROD_TAP_DEPTH


def rod_engagement():
    return round(ROD_BOLT_L - (TOP_T + STIFF_T + FRAME_H + BOTTOM_T) + rod_hole_top_z(), 2)


def rod_hole_text(entry=True):
    """図面用のめねじの指示。"""
    if ROD_HOLE_THROUGH:
        return f"下穴φ{ROD_TAP_DRILL} 貫通 → M3×0.5 タップ貫通"
    where = "溝底" if (ROD_TAPE and ROD_FLAT_W <= 0) else ("平面" if ROD_FLAT_W > 0 else "上端")
    return f"下穴φ{ROD_TAP_DRILL} 深さ{ROD_HOLE_DEPTH:g}（{where}から）→ M3×0.5 タップ 有効深さ{ROD_TAP_DEPTH:g}以上"


def rod_center_z():
    """丸棒の中心のZ（ボトムプレートの下面＝0、下向きが負）。"""
    return -(rod_top_gap() + ROD_D / 2 - rod_flat_depth())


def saddle():
    """受け台：左右2分割（枠と同じ位置で分ける）。上は平ら、下は丸棒に沿う凹面。"""
    import math
    r = rod()
    R = ROD_D / 2 + SADDLE_CLEAR
    sag = R - math.sqrt(R * R - (SADDLE_W / 2) ** 2)
    # 端：上から見て外形の内側（受け台の奥側の縁で判定）。ただし端の穴より4mm以上外まで
    from shapely.geometry import LineString
    o = Polygon(outer_pts())
    ye = r["y"] - SADDLE_W / 2
    xo = LineString([(OX - 5, ye), (OX + OUTER_W + 5, ye)]).intersection(o).bounds[0] + 0.5
    x0 = min(xo, r["holes_x"][0] - (REAR_HOLE_D / 2 + 3.0))
    x1 = OX + OUTER_W - (x0 - OX)
    return dict(y=r["y"], w=SADDLE_W, t_min=SADDLE_T_MIN, height=round(SADDLE_T_MIN + sag, 2), x0=round(x0, 2), x1=round(x1, 2),
                split_x=SPLIT_X, R=R)


def ribs():
    """前後一体の足：列ごとに、手前の足（ナット受け）と奥の穴（丸棒）を結ぶ。平面形（外形の0.5mm内側で切る）と寸法。"""
    from shapely.geometry import Point, box as _b
    from shapely.ops import unary_union
    fl = feet()[0]
    r = rod()
    o = Polygon(outer_pts()).buffer(-0.5)
    y_rear = r["y"] - SADDLE_W / 2
    out = []
    for f in sorted(fl, key=lambda q: q["x"]):
        hx = min(r["holes_x"], key=lambda x: abs(x - f["x"]))
        xc = (f["x"] + hx) / 2
        plan = unary_union([_b(xc - RIB_W / 2, y_rear, xc + RIB_W / 2, f["y"]), Point(f["x"], f["y"]).buffer(RIB_W / 2, quad_segs=24)])
        plan = plan.intersection(o)
        out.append(dict(x=round(xc, 2), front=(f["x"], f["y"]), rear=(hx, r["y"]), h_front=f["h"],
                        length=round(plan.bounds[3] - plan.bounds[1], 1), plan=list(plan.exterior.coords)[:-1]))
    return out


def pairs():
    """左右ずつまとめた足：手前は2つのナット受けをつないだバー、奥は2穴ぶんの丸棒受け。左右で同じX範囲にそろえる。"""
    from shapely.geometry import Point, box as _b
    from shapely.geometry import MultiPoint
    fl = sorted(feet()[0], key=lambda q: q["x"])
    r = rod()
    o = Polygon(outer_pts()).buffer(-0.5)
    rx = sorted(r["holes_x"])
    out = []
    for side, fs, hs in (("left", fl[:2], rx[:2]), ("right", fl[2:], rx[2:])):
        x0 = min(min(f["x"] for f in fs), min(hs)) - RIB_W / 2
        x1 = max(max(f["x"] for f in fs), max(hs)) + RIB_W / 2
        # 手前：2つの丸の凸包（角丸のバー）
        front = MultiPoint([(f["x"], f["y"]) for f in fs]).buffer(RIB_W / 2, quad_segs=24).convex_hull.intersection(o)
        # 奥：PLAのバーなら手前と同じ形（2つの丸の凸包）、丸棒なら丸棒受け（幅SADDLE_W）
        fl_all, hf, tan, y_front = feet()
        rear_bar = []
        if REAR_FOOT == "pla_bars":
            rear = MultiPoint([(x, r["y"]) for x in hs]).buffer(RIB_W / 2, quad_segs=24).convex_hull.intersection(o)
            rear_bar = [(x, r["y"], round(hf + (y_front - r["y"]) * tan, 2)) for x in hs]
        else:
            rear = _b(x0, r["y"] - SADDLE_W / 2, x1, r["y"] + SADDLE_W / 2).intersection(o)
        out.append(dict(side=side, x0=round(x0, 2), x1=round(x1, 2), _front=front, _rear=rear, _fc=fs, _hs=hs,
                        front_plan=list(front.exterior.coords)[:-1], rear_plan=list(rear.exterior.coords)[:-1],
                        front_holes=[(f["x"], f["y"], f["h"]) for f in fs], rear_holes=[(x, r["y"]) for x in hs], rear_bar_holes=rear_bar,
                        front_len=round(front.bounds[2] - front.bounds[0], 1), rear_len=round(rear.bounds[2] - rear.bounds[0], 1)))
    if is_flat_pla():
        # 4本を同じ形に：各バーを自分の中心へ移し、全部の共通部分を取り、前後・左右に対称化してから戻す
        from shapely import affinity
        def ctr(h2):
            return ((h2[0][0] + h2[1][0]) / 2, (h2[0][1] + h2[1][1]) / 2)
        bars = []
        for pr in out:
            bars.append((pr["_front"], ctr([(f["x"], f["y"]) for f in pr["_fc"]])))
            bars.append((pr["_rear"], ctr([(x, r["y"]) for x in pr["_hs"]])))
        S = None
        for poly, (cx, cy) in bars:
            loc = affinity.translate(poly, -cx, -cy)
            S = loc if S is None else S.intersection(loc)
        S = S.intersection(affinity.scale(S, -1, 1, origin=(0, 0))).intersection(affinity.scale(S, 1, -1, origin=(0, 0)))
        S = S.simplify(0.01)
        for pr in out:
            fc = ctr([(f["x"], f["y"]) for f in pr["_fc"]])
            rc = ctr([(x, r["y"]) for x in pr["_hs"]])
            pr["front_plan"] = list(affinity.translate(S, *fc).exterior.coords)[:-1]
            pr["rear_plan"] = list(affinity.translate(S, *rc).exterior.coords)[:-1]
            pr["bar_len"] = round(S.bounds[2] - S.bounds[0], 1)
            pr["front_len"] = pr["rear_len"] = pr["bar_len"]
    for pr in out:
        for k in ("_front", "_rear", "_fc", "_hs"):
            pr.pop(k, None)
    return out


def hole_d(c):
    """穴の直径：後ろの列（丸棒）はREAR_HOLE_D、ほかはHOLE_D。"""
    if rod_layout():
        y_rear = min(y for _, y in holes())
        if abs(c[1] - y_rear) < 1e-6:
            return REAR_HOLE_D
    return HOLE_D


def tilt_deg():
    import math
    return round(math.degrees(math.atan(feet()[2])), 2)


def holes():
    """角の4穴は角丸に合わせて対角線上を内側へずらし、外周と枠の内側からの距離が等しくなる位置に置く。"""
    from shapely.geometry import Point
    outer = Polygon(outer_pts())
    inner = Polygon(frame_inner_pts())
    ring = outer.difference(inner)
    out = []
    rear_corner = {}
    for x, y in HOLES_FROM_OUTER:
        c = (OX + x, OY + y)
        if is_flat_pla() and x in (7, 308) and y == 119 and x in rear_corner:
            # 平らなPLAの足：手前の角の穴を奥の角の穴と前後対称に置く（足4本を同じ形にする）
            out.append((rear_corner[x], round(OY + OUTER_H - (rear_y - OY), 2)))
            continue
        is_corner = x in (7, 308) and y in (7, 119)
        if is_corner and rod_layout() and y == 7:
            # 後ろの角の穴は中央の穴と同じ列に並べる（丸棒にまっすぐ穴を開けるため）
            sx = 1 if x < OUTER_W / 2 else -1
            x_edge = OX if sx == 1 else OX + OUTER_W
            for i in range(0, 600):
                q = Point(x_edge + sx * i * 0.05, OY + y)
                if ROD_TAPE and ROD_FLAT_W <= 0 and abs(q.x - _rod_end_x(OY + y, sx)) < rod_end_min():
                    continue
                if ring.contains(q) and min(outer.exterior.distance(q), inner.exterior.distance(q)) - HOLE_D / 2 >= HOLE_EDGE_MIN:
                    c = (round(q.x, 2), round(q.y, 2))
                    break
            rear_corner[x] = c[0]
            rear_y = c[1]
            out.append(c)
            continue
        if is_corner and CORNER_R > 0:
            vx = OX if x < OUTER_W / 2 else OX + OUTER_W
            vy = OY if y < OUTER_H / 2 else OY + OUTER_H
            sx = 1 if vx == OX else -1
            sy = 1 if vy == OY else -1
            best = None
            for i in range(1, 400):
                t = i * 0.05
                q = Point(vx + sx * t, vy + sy * t)
                if not ring.contains(q):
                    continue
                m = min(outer.exterior.distance(q), inner.exterior.distance(q))
                if best is None or m > best[0]:
                    best = (m, (round(q.x, 2), round(q.y, 2)))
            c = best[1]
        out.append(c)
    return out


def switch_cutouts():
    """swillkbのスイッチ層（キー領域の左上が(5.001,5.001)）をPCB座標へ。"""
    t = open(SWILLKB, encoding="utf-8").read()
    polys = []
    for m in re.finditer(r'<polygon points="([^"]+)"', t):
        pts = [tuple(map(float, p.split(","))) for p in m.group(1).split()]
        polys.append(pts)
    polys = polys[1:]               # 1つ目はキー領域の外枠（切らない）
    # キー領域の左上はPCB座標で(-0.375, -0.325)（基準寸法.md）
    dx, dy = -5.001 - 0.375, -5.001 - 0.325
    return [[(x + dx, y + dy) for x, y in p] for p in polys]


def stiffener_openings():
    """補強板の抜き：トッププレートの穴を片側STIFF_OFFSET広げ、近すぎる穴どうしはつなげる。"""
    from shapely.ops import unary_union
    grown = [Polygon(p).buffer(STIFF_OFFSET, join_style=2) for p in switch_cutouts()]
    # 穴の間がSTIFF_MIN_WEB未満になる所は、細い棒が残らないようにつなげる
    merged = unary_union([g.buffer(STIFF_MIN_WEB / 2, join_style=2) for g in grown]).buffer(-STIFF_MIN_WEB / 2, join_style=2)
    polys = list(merged.geoms) if hasattr(merged, "geoms") else [merged]
    return [list(q.exterior.coords)[:-1] for q in polys]


def stiffener_min_web(openings):
    ps = [Polygon(p) for p in openings]
    m = min((ps[i].distance(ps[j]) for i in range(len(ps)) for j in range(i + 1, len(ps))
             if ps[i].distance(ps[j]) < 10), default=None)
    return round(m, 2) if m is not None else None


def kerf_in(pts):     # 穴：内側へ k/2
    if not KERF:
        return pts
    return list(Polygon(pts).buffer(-KERF / 2, join_style=2).exterior.coords)[:-1]


def kerf_out(pts):    # 外形：外側へ k/2
    if not KERF:
        return pts
    return list(Polygon(pts).buffer(KERF / 2, join_style=1).exterior.coords)[:-1]


def circle_path(c, d, k_in=True):
    r = d / 2 - (KERF / 2 if (KERF and k_in) else 0)
    x, y = c
    return f"M {x - r:.4f},{y:.4f} A {r:.4f},{r:.4f} 0 1 0 {x + r:.4f},{y:.4f} A {r:.4f},{r:.4f} 0 1 0 {x - r:.4f},{y:.4f} Z"


def frame_inner_pts():
    return sq.rounded_rect_points(OX + WALL, OY + WALL, OUTER_W - 2 * WALL, OUTER_H - 2 * WALL,
                                  INNER_R, INNER_SMOOTH)


def check_pcb_clearance():
    pcb = box(0, 0, PCB_W, PCB_H).buffer(-2).buffer(2, quad_segs=32)   # PCBの角R2
    inner = Polygon(frame_inner_pts())
    clear = inner.exterior.distance(pcb) if inner.contains(pcb) else -1
    if clear < PCB_MIN_CLEAR:
        raise SystemExit(f"枠の内側とPCBのすき間が {clear:.2f}mm しかない（最小{PCB_MIN_CLEAR}mm）。INNER_Rを小さくする")
    return round(clear, 2)


def svg(path, layers, title, extra_note=""):
    """layers: [(id, color, [path_d...], 説明)]  赤=切断、青=参考線"""
    vb = f"{OX - 5:.4f} {OY - 5:.4f} {OUTER_W + 10:.4f} {OUTER_H + 10:.4f}"
    out = [f'<?xml version="1.0" encoding="UTF-8"?>',
           f'<!-- {title} / 原点=PCB外形の左上・単位mm / 生成: tools/gen_case.py {extra_note} -->',
           f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
           f'width="{OUTER_W + 10:.4f}mm" height="{OUTER_H + 10:.4f}mm" viewBox="{vb}">']
    for lid, color, ds, desc in layers:
        out.append(f'<g id="{lid}" inkscape:groupmode="layer" inkscape:label="{lid}：{desc}">')
        for d in ds:
            out.append(f'  <path d="{d}" fill="none" stroke="{color}" stroke-width="0.05"/>')
        out.append("</g>")
    out.append("</svg>\n")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8").write("\n".join(out))


def check_rod_hole():
    """めねじ：ねじ込み量と、貫通のときはボルトの先端が下の出口に届かないこと。"""
    if REAR_FOOT != "brass_rod":
        return
    e = rod_engagement()
    if e < 3.0:
        raise SystemExit(f"丸棒へのねじ込みが{e}mmしかない。ROD_BOLT_Lを長くする")
    if ROD_HOLE_THROUGH:
        m = rod_hole_len() - e
        if m < ROD_TIP_MARGIN_MIN:
            raise SystemExit(f"ボルトの先端が丸棒の下の出口から{m:.2f}mm（最小{ROD_TIP_MARGIN_MIN}）。ROD_BOLT_Lを短くする")
    elif e > ROD_TAP_DEPTH - 0.5:
        raise SystemExit(f"ねじ込み{e}mmが有効ねじ深さ{ROD_TAP_DEPTH}に近すぎる")


def main():
    check_joint()
    check_rod_hole()
    pcb_clear = check_pcb_clearance()
    outer_d = sq.to_svg_path(kerf_out(outer_pts()))
    hole_ds = [circle_path(c, hole_d(c)) for c in holes()]
    sw_ds = [sq.to_svg_path(kerf_in(p)) for p in switch_cutouts()]
    inner = frame_inner_pts()
    note = f"R{CORNER_R} smoothing{CORNER_SMOOTH} kerf{KERF}"

    # プレート（スイッチ穴→ネジ穴→外形の順。外形は最後に切る）
    svg(os.path.join(ROOT, f"plate/plate_{VER}_kerf{KERF:g}.svg"),
        [("switch", "#ff0000", sw_ds, "スイッチ・スタビ穴（先に切る）"),
         ("holes", "#ff0000", hole_ds, "M3穴"),
         ("outline", "#ff0000", [outer_d], "外形（最後に切る）")],
        "プレート", note)

    # 底板
    st_open = stiffener_openings()
    st_ds = [sq.to_svg_path(kerf_in(p)) for p in st_open]
    svg(os.path.join(ROOT, f"plate/stiffener_{VER}_t{STIFF_T:g}_kerf{KERF:g}.svg"),
        [("openings", "#ff0000", st_ds, f"スイッチ・スタビの逃げ（穴より片側{STIFF_OFFSET}mm大きい）"),
         ("holes", "#ff0000", hole_ds, "M3穴"),
         ("outline", "#ff0000", [sq.to_svg_path(kerf_out(stiff_outer_pts())) if STIFF_RECESS else outer_d],
          f"外形（最後に切る。枠の掘り込みに入るので外形より片側{FRAME_INSET + STIFF_LIP + STIFF_CLEAR:g}小さい）" if STIFF_RECESS else "外形（最後に切る）")],
        f"補強板（アクリル{STIFF_T}mm・トッププレートの下に重ねて共締め）", note)
    web = stiffener_min_web(st_open)

    if CASE == "tray":
        pass                        # トレー型：ボトムプレートは無い（底はトレーと一体）
    elif SKIRT:
        bp = bottom_poly()
        bp_d = sq.to_svg_path(kerf_out(list(bp.exterior.coords)[:-1]))
        svg(os.path.join(ROOT, f"case/bottom_{VER}_kerf{KERF:g}.svg"),
            [("outline", "#ff0000", [bp_d], "外形とネジの切り欠き（スカートの内側にはめ込む）")],
            f"底板（スカートの内側。外形より片側{FRAME_INSET + SKIRT_T + SKIRT_CLEAR:g}小さい）", note)
    else:
        svg(os.path.join(ROOT, f"case/bottom_{VER}_kerf{KERF:g}.svg"),
            [("holes", "#ff0000", hole_ds, "M3穴"),
             ("outline", "#ff0000", [outer_d], "外形（最後に切る）")],
            "底板", note)

    # 枠（3Dプリント用の2D形状。Fusion 360で押し出す元）
    split_d = f"M {SPLIT_X:.4f},{OY - 3:.4f} L {SPLIT_X:.4f},{OY + OUTER_H + 3:.4f}"
    usb_d = (f"M {USB_X - USB_W / 2:.4f},{OY:.4f} L {USB_X - USB_W / 2:.4f},{OY + WALL:.4f} "
             f"L {USB_X + USB_W / 2:.4f},{OY + WALL:.4f} L {USB_X + USB_W / 2:.4f},{OY:.4f}")
    svg(os.path.join(ROOT, f"case/frame_{VER}.svg"),
        [("outline", "#000000", [sq.to_svg_path(frame_outer_pts()), sq.to_svg_path(inner)], f"枠の外形（アクリルより{FRAME_INSET}mm内側）と内側"),
         ("holes", "#000000", [circle_path(c, hole_d(c), False) for c in holes()], "M3穴（後ろはφ4.0）"),
         ("split", "#0000ff", [split_d], f"分割線 X={SPLIT_X}"),
         ("usb", "#0000ff", [usb_d], f"USB切り欠き 幅{USB_W}（位置は要実測）")],
        (f"トレー（高さ{round(FLOOR_T + FRAME_H + (STIFF_T if STIFF_RECESS else 0), 2)}mm・底{FLOOR_T}mm・PLA・左右2分割）" if CASE == "tray"
         else f"枠（厚さ{FRAME_H}mm・PLA・左右2分割）"), note)

    # フォームの型紙（紙に100%で印刷して切る。PORON＝ポリウレタンはレーザーで切らない）
    from shapely.geometry import box as _box
    cav = Polygon(frame_inner_pts()).buffer(-0.5, join_style=1)
    usb_zone = _box(USB_X - 9, 0, USB_X + 9, 12)                     # USB-C裏側の逃げ（仮・要実測）
    case_foam = cav.difference(usb_zone)
    pcb_poly = _box(0, 0, PCB_W, PCB_H).buffer(-2).buffer(2)
    plate_foam = pcb_poly.buffer(-0.5).difference(
        __import__("shapely.ops", fromlist=["unary_union"]).unary_union([Polygon(p) for p in st_open]))
    def poly_ds(geom):
        gs = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
        ds = []
        for gg in gs:
            ds.append(sq.to_svg_path(list(gg.exterior.coords)[:-1]))
            ds += [sq.to_svg_path(list(r.coords)[:-1]) for r in gg.interiors]
        return ds
    svg(os.path.join(ROOT, f"case/foam_case_{VER}.svg"),
        [("cut", "#000000", poly_ds(case_foam), f"ケースフォーム兼台座（PCB下、厚さ{UNDER_PCB}＋つぶし代）。USB-C付近は仮の逃げ")],
        "ケースフォーム型紙（100%で印刷して切る）", note)
    svg(os.path.join(ROOT, f"case/foam_plate_{VER}.svg"),
        [("cut", "#000000", poly_ds(plate_foam), f"プレートフォーム（補強板とPCBの間、厚さ{GAP_STIFF_PCB}以下）")],
        "プレートフォーム型紙（100%で印刷して切る）", note)

    # 足（ナット受け）の平面図
    fl, h_front, _, _ = feet()
    foot_ds = [circle_path((f["x"], f["y"]), FOOT_D, False) for f in fl]
    import math as _m
    hex_ds = []
    for f in fl:
        r = NUT_POCKET_AF / _m.sqrt(3)
        pts = [(f["x"] + r * _m.cos(_m.radians(60 * k)), f["y"] + r * _m.sin(_m.radians(60 * k))) for k in range(6)]
        hex_ds.append(sq.to_svg_path(pts))
    feet_layers = [("outline", "#000000", [sq.to_svg_path(outer_pts())], "参考：ケース外形"),
                   ("feet", "#0000ff", foot_ds, f"足 φ{FOOT_D}×{len(fl)}（前{h_front}mm、傾き{tilt_deg()}°）"),
                   ("nut", "#ff0000", hex_ds, f"ナット溝（二面幅{NUT_POCKET_AF}、下から）")]
    rod_info = None
    if REAR_FOOT == "brass_rod":
        rod_info = rod()
        ry, rd = rod_info["y"], ROD_D
        rect = [(rod_info["x0"], ry - rd / 2), (rod_info["x1"], ry - rd / 2), (rod_info["x1"], ry + rd / 2), (rod_info["x0"], ry + rd / 2)]
        feet_layers.append(("rod", "#b8860b", [sq.to_svg_path(rect)] + [circle_path((x, ry), ROD_TAP_DRILL, False) for x in rod_info["holes_x"]],
                            f"真鍮丸棒 φ{ROD_D}×{rod_info['length']}（M3めねじ×{len(rod_info['holes_x'])}）"))
        # 丸棒の穴あけ型紙（100%で印刷し、丸棒に巻いて/当ててポンチを打つ）
        L = rod_info["length"]
        marks = []
        for k, xh in enumerate(rod_info["holes_from_left_end"]):
            marks.append(f'<line x1="{xh + 5:.2f}" y1="8" x2="{xh + 5:.2f}" y2="{8 + rd * 3.1416 / 2:.2f}" stroke="#ff0000" stroke-width="0.2"/>'
                         f'<circle cx="{xh + 5:.2f}" cy="{8 + rd * 3.1416 / 4:.2f}" r="1.25" fill="none" stroke="#ff0000" stroke-width="0.2"/>'
                         f'<text x="{xh + 5:.2f}" y="6" font-size="3" text-anchor="middle" font-family="Hiragino Sans, Noto Sans CJK JP, sans-serif">{xh:.2f}</text>')
        tw = L + 10
        th = 8 + rd * 3.1416 / 2 + 22
        tpl = (f'<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="{tw:.1f}mm" height="{th:.1f}mm" viewBox="0 0 {tw:.1f} {th:.1f}">'
               f'<rect x="5" y="8" width="{L:.2f}" height="{rd * 3.1416 / 2:.2f}" fill="none" stroke="#000" stroke-width="0.2"/>'
               + "".join(marks) +
               f'<text x="5" y="{th - 10:.1f}" font-size="3.2" font-family="Hiragino Sans, Noto Sans CJK JP, sans-serif">真鍮丸棒 φ{rd:g}×{L:g}mm の穴あけ型紙（100%で印刷）。左端をそろえ、赤丸の中心にポンチ。'
               f'{rod_hole_text()}。数字は左端からの距離(mm)</text>'
               f'<text x="5" y="{th - 5:.1f}" font-size="3.2" font-family="Hiragino Sans, Noto Sans CJK JP, sans-serif">丸棒の上側（ボトムプレートに当たる線）に4穴を一直線に。V字の台に載せ、ボール盤で垂直に開ける</text></svg>\n')
        open(os.path.join(ROOT, f"case/rod_drill_template_{VER}.svg"), "w", encoding="utf-8").write(tpl)
    if rod_layout() and FOOT_STYLE == "pairs":
        ds, nuts = [], []
        for pr in pairs():
            ds += [sq.to_svg_path(pr["front_plan"]), sq.to_svg_path(pr["rear_plan"])]
            if REAR_FOOT == "pla_bars":
                for hx, hy, _ in pr["rear_bar_holes"]:
                    rr = NUT_POCKET_AF / _m.sqrt(3)
                    nuts.append(sq.to_svg_path([(hx + rr * _m.cos(_m.radians(60 * k)), hy + rr * _m.sin(_m.radians(60 * k))) for k in range(6)]))
        lab = ("足：手前バー×2＋奥バー×2（すべてPLA・ナット受け、左右ずつ）" if REAR_FOOT == "pla_bars"
               else "足：手前バー×2（ナット受け）＋奥の丸棒受け×2（左右ずつ）")
        feet_layers.append(("pairs", "#008800", ds, lab))
        if nuts:
            feet_layers.append(("nut_rear", "#ff0000", nuts, f"奥バーのナット溝（二面幅{NUT_POCKET_AF}、下から）"))
    if REAR_FOOT == "brass_rod" and FOOT_STYLE == "ribs":
        feet_layers.append(("ribs", "#008800", [sq.to_svg_path(rb["plan"]) for rb in ribs()],
                            f"前後一体の足×4（幅{RIB_W}、厚さ{RIB_T}、手前はナット受け・奥は丸棒受け）"))
    svg(os.path.join(ROOT, f"case/feet_{VER}.svg"), feet_layers, "足（ナット受け）と真鍮丸棒 平面図", note)

    params = dict(version=VER, pcb=[PCB_W, PCB_H], outer=[OUTER_W, OUTER_H], outer_origin=[OX, OY],
                  wall=WALL, frame_inner=[OUTER_W - 2 * WALL, OUTER_H - 2 * WALL],
                  corner_r=CORNER_R, corner_smoothing=CORNER_SMOOTH,
                  corner_extent=round(sq.corner_extent(CORNER_R, CORNER_SMOOTH), 2),
                  inner_r=INNER_R, inner_smoothing=INNER_SMOOTH,
                  inner_corner_extent=round(sq.corner_extent(INNER_R, INNER_SMOOTH), 2),
                  pcb_min_clearance=pcb_clear,
                  hole_d=HOLE_D, holes_pcb=[[round(a, 3), round(b, 3)] for a, b in holes()],
                  kerf=KERF, split_x=SPLIT_X, usb_x=round(USB_X, 2), usb_w=USB_W, frame_h=FRAME_H,
                  top_t=TOP_T, stiff_t=STIFF_T, stiff_offset=STIFF_OFFSET, stiff_openings=len(st_open),
                  stiff_min_web=web, gap_stiff_pcb=GAP_STIFF_PCB,
                  pcb_t=PCB_T, under_pcb=UNDER_PCB, bottom_t=BOTTOM_T,
                  total_height=round(TOP_T + STIFF_T + FRAME_H + BOTTOM_T, 2),
                  switch_cutouts=len(sw_ds), frame_inset=FRAME_INSET,
                  bolt=f"M3x{BOLT_L:g}", foot_skin=FOOT_SKIN, tilt_deg=tilt_deg(), foot_d=FOOT_D,
                  rear_foot=REAR_FOOT, rod=rod_info,
                  rod_bolt=(f"M3x{ROD_BOLT_L:g}" if rod_info else None),
                  skirt=(dict(t=SKIRT_T, clear=SKIRT_CLEAR, h=SKIRT_H, bottom_plate_size=[round(v, 2) for v in
                              (bottom_outline().bounds[2] - bottom_outline().bounds[0], bottom_outline().bounds[3] - bottom_outline().bounds[1])],
                              notch=BP_NOTCH) if SKIRT else None),
                  stiff_recess=(dict(lip=STIFF_LIP, clear=STIFF_CLEAR, depth=STIFF_T, stiffener_size=[round(b[2] - b[0], 2), round(b[3] - b[1], 2)])
                                if STIFF_RECESS and (b := Polygon(stiff_outer_pts()).bounds) else None),
                  case=CASE, floor_t=(FLOOR_T if CASE == "tray" else None),
                  frame_total_h=round(FRAME_H + (FLOOR_T if CASE == "tray" else 0) + (STIFF_T if STIFF_RECESS else 0), 2),
                  joint=(dict(kind=JOINT, tongue=[TONGUE_W, TONGUE_T, TONGUE_L], clear=TONGUE_CLEAR, bolt=f"M3x{JB_L:g} button",
                              bolt_x_from_split=JB_X, counterbore=[JB_CB_D, JB_CB_DEPTH], nut_depth=JB_NUT_DEPTH,
                              wall_centers_y=joint_wall_y(), check=check_joint()) if JOINT == "tongue_vbolt" else dict(kind=JOINT)),
                  rear_bolt=(f"M3x{BOLT_L:g}+nut" if REAR_FOOT == "pla_bars" else None),
                  rear_bar_heights=([h for pr in pairs() for _, _, h in pr["rear_bar_holes"]] if REAR_FOOT == "pla_bars" else None),
                  rod_thread_engagement=(rod_engagement() if rod_info else None), rod_hole_through=ROD_HOLE_THROUGH, rod_hole_len=(rod_hole_len() if rod_info else None),
                  rod_tape=(dict(tape_w=TAPE_W, groove_w=GROOVE_W, groove_depth=GROOVE_DEPTH, groove_dia=ROD_D - 2 * GROOVE_DEPTH,
                                 tape_t=TAPE_T, squeeze_top=TAPE_SQUEEZE_TOP, gap_rod_to_plate=rod_top_gap())
                            if (rod_info and ROD_TAPE and ROD_FLAT_W <= 0) else None),
                  saddle=(saddle() if (rod_info and SADDLE and FOOT_STYLE == "separate" and ROD_FLAT_W <= 0 and not ROD_TAPE) else None), rear_hole_d=REAR_HOLE_D,
                  rod_flat_w=ROD_FLAT_W, rod_flat_depth=round(rod_flat_depth(), 3), rod_center_z=round(rod_center_z(), 3),
                  rod_tap_depth=(rod_tap_len() if rod_info else ROD_TAP_DEPTH), rod_hole_depth=(rod_hole_len() if rod_info else ROD_HOLE_DEPTH),
                  pairs=([{k: v for k, v in pr.items() if not k.endswith("plan")} for pr in pairs()]
                         if (rod_layout() and FOOT_STYLE == "pairs") else None),
                  foot_style=FOOT_STYLE, ribs=([{k: v for k, v in rb.items() if k != "plan"} for rb in ribs()]
                                               if (rod_info and FOOT_STYLE == "ribs") else None),
                  feet=[{k: (round(v, 2) if isinstance(v, float) else v) for k, v in f.items()} for f in fl],
                  front_height_no_keycap=round(h_front + TOP_T + STIFF_T + FRAME_H + BOTTOM_T, 2))
    open(os.path.join(ROOT, f"case/params_{VER}.json"), "w", encoding="utf-8").write(
        json.dumps(params, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(params, ensure_ascii=False))


if __name__ == "__main__":
    main()
