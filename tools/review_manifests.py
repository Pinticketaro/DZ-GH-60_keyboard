"""確認ボードに載せる版（節目）の説明 manifest を out/<版>/manifest.json に書く。
使い方: python3 tools/review_manifests.py <review-pageのscriptsフォルダ>
"""
import json, os, subprocess, sys
S = sys.argv[1]
V = [("v05", None, "2026-10-15",
      "足をナット受けの丸台8個（傾き5°仮）にし、PCBの下と補強板の下にフォームを入れた版。打鍵感は板厚より留め方とフォームで決まる、という調査結果を反映。",
      ["外観・打鍵感の改善を調査して反映（docs/改善案.md）", "足兼ナット受け：φ12×8、傾き5°（仮）", "ケースフォーム（PCBの台座）とプレートフォームの型紙を追加"],
      [("docs/img/preview_v05.png", "外観", "外観"), ("docs/img/section_v05.png", "断面", "断面")]),
     ("v06", "v05", "2026-10-15", "奥側の足を真鍮丸棒φ12に。横から端の丸が見える「アイコニック」な案。",
      ["奥の足を真鍮丸棒φ12（仮）に。後ろの4穴を一直線に並べ、M3×20を丸棒のめねじへ", "傾きは丸棒の太さから自動計算"],
      [("docs/img/preview_v06.png", "外観", "外観")]),
     ("v09", "v06", "2026-10-15", "足を左右ずつまとめた形（手前バー×2＋奥の丸棒受け×2）。中央2本のネジを左右対称にして、左右の部品を同じ形に。",
      ["v07：丸棒とボトムプレートの間にPLAの受け台（割れ防止）", "v08：前後一体の足（取り消し）", "足を左右ずつまとめる（手前バー×2＋奥の丸棒受け×2）", "中央2本のネジを左右対称（X=92.7／192.3）"],
      [("docs/img/preview_v09.png", "外観", "外観")]),
     ("v11", "v09", "2026-10-15", "丸棒を旋盤の溝×4＋ゴムテープで固定する案。加工は旋盤とボール盤だけ、渡せる加工図つき。",
      ["v10：丸棒の上面を平面加工（フライス）する案", "丸棒に全周の溝×4（幅10.5・深さ0.8）、ゴムテープ（幅10・厚さ1）を巻く。締めると丸棒がほぼプレートに接する", "受け台をなくした"],
      [("docs/img/preview_v11.png", "外観", "外観"), ("docs/img/rod_mount_v11.png", "丸棒の固定（断面）", "断面")]),
     ("v13", "v11", "2026-10-15", "丸棒の加工がネックなので、奥の足も一旦PLAのバーに。穴位置と傾きは丸棒φ8版と同じで、あとで差し替えられる。",
      ["v12：角R8・丸棒φ8（めねじは貫通）", "奥の足もPLAのバー×2（高さ8.1）。ボルトは8本ともM3×18＋ナット", "傾き約2.2°"],
      [("docs/img/preview_v13.png", "外観", "外観")]),
     ("v14", "v13", "2026-10-15", "傾きをなくし（0°）、足を同じ形のPLAのバー×4に。部品の種類が減って、手前の高さ18.3mm。",
      ["傾き0°（手首の反りを減らすため）", "手前の角の穴を奥と前後対称に移し、足4本を同じ形に（foot_bar_x4）", "Fusion用の図面セット（A3）・DXF・CSVを追加"],
      [("docs/img/preview_v14.png", "外観", "外観"), ("docs/img/section_v14.png", "断面", "断面")]),
     ("v15", "v14", "2026-10-15", "枠の左右の継ぎ目を、ピンからほぞ＋縦向きのM3×6ボタンヘッドに。剛性のため。",
      ["継ぎ目：ほぞ（左半分の下側の舌 9×4.5×16）＋縦のM3×6（前後の壁に1組ずつ）", "最初の横向きボルト案は取り消し（他のボルトと同じ縦向きに）", "Fusion 360で寸法ベースに組み立てるスクリプトとSTEPを追加"],
      [("docs/img/preview_v15.png", "外観", "外観"), ("docs/img/joint_v15.png", "継ぎ目", "継ぎ目")])]


def diff(a, b):
    os.makedirs(f"out/{b}", exist_ok=True)
    subprocess.run(["python3", f"{S}/params_diff.py", f"case/params_{a}.json", f"case/params_{b}.json", "--json", f"out/{b}/params_diff.json"],
                   check=True, capture_output=True)
    return f"out/{b}/params_diff.json"


mans = []
for ver, prev, date, summ, chg, imgs in V:
    os.makedirs(f"out/{ver}", exist_ok=True)
    m = dict(version=ver, prev=prev, date=date, stage="モック", summary=summ, changes=chg, questions=[],
             images=[dict(src=s, caption=c, group=gp) for s, c, gp in imgs if os.path.exists(s)])
    if prev:
        m["params_diff"] = diff(prev, ver)
    mans.append(m)
mans[0]["project"] = "DZ60キーボード（DZ-GH-60）"
mans.append(dict(version="v16", prev="v15", date="2026-10-22", stage="モック",
    summary="ソリッド感を出すため、枠を下へスカート状に延ばしてボトムプレートを内側に収めた版。横から見えるのは枠と上のアクリル2枚だけ。高さは18.3mmのまま。",
    changes=["枠の下にスカート（厚さ2・高さ2.9）。ボトムプレートは内側にはめ込み、約310×121に（外部レビュー「塊か積層か」→ 塊を選択）",
             "ボトムプレートのネジ穴をU字の切り欠きに（位置はスカートで決まり、足と共締めのため）",
             "枠は上面を下にして印刷する前提に。継ぎ目のほぞを上側へ移し、ナットは右半分の下面（ボトムプレートで隠れる）",
             "図面8枚・DXF・STEP・Fusionスクリプトを更新"],
    questions=["補強板も枠の掘り込みに入れて、側面に見えるアクリルをトッププレート1.5mmだけにするか",
               "箱型（底一体のPLAトレイ）案と比べるか",
               "傾き：0°のままか、レビューの指摘どおり3〜5°にするか（手前の高さはキーキャップ込みで約27mm）",
               "天面のボルト：頭の低いもの／ケースと同じ色にするか",
               "手前の壁の中央に出る継ぎ目の線：浅いV溝で見せるか、そのままか",
               "色の組み合わせ（3トーンまで）"],
    notes="本番の前に試し片で測る値：レーザーのカーフ（今は0）、スイッチ穴14.0のはまり、ほぞのすき間0.2、スカートのすき間0.2、ナット溝の二面幅6.1。DZ60の実測（USBの位置）とボトムプレートの実際の厚さ（スカート2.9に対して）も必要。",
    images=[dict(src="docs/img/preview_v16.png", caption="外観（キーキャップ付き）", group="外観"),
            dict(src="out/v16/preview.png", caption="ケースだけ（斜め上・斜め後ろ・右横）", group="外観"),
            dict(src="docs/img/joint_v16.png", caption="継ぎ目（ほぞを上側へ）", group="継ぎ目"),
            dict(src="out/v16/section.png", caption="断面（手前のネジの列）：スカートとボトムプレート", group="断面"),
            dict(src="out/v16/plan.png", caption="平面図（各部品の輪郭の重ね合わせ）", group="平面")],
    compare=[dict(before="docs/img/preview_v15.png", after="docs/img/preview_v16.png", caption="外観 v15 → v16"),
             dict(src="docs/img/side_compare_v15_v16.png", caption="横から：ボトムプレートの層が消えた")],
    params_diff=diff("v15", "v16"), model="out/v16/model.glb"))
for m in mans:
    json.dump(m, open(f"out/{m['version']}/manifest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print([m["version"] for m in mans])
