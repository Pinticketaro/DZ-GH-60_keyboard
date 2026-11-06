"""monozukuri の make_version.py から呼ぶ、このプロジェクトの形のツール（mock.py の代わり）。
このプロジェクトは monozukuri のテンプレート（mock.py の build()）ではなく、自前の gen_case.py → build3d.py で形を作る。
make_version.py が要るもの（out/<版>/scene.json・部品ごとの STL・step/index.json・params/params_<版>.json）をそろえる。

使い方
  python3 tools/model.py vNN                                     … 単独でも動く
  python3 <review-page の scripts>/make_version.py . vNN --tool tools/model.py   … ふつうはこちら（画像・ページまで）

決まり
  - 寸法は tools/gen_case.py に書く（VER・PARENT もそこ）。引数の版は gen_case.VER と同じでないと止まる
    （版を上げるときは gen_case.py の VER・PARENT を先に書き換える）。
  - 寸法の根拠は tools/dims_export.py に書く。params/params_<版>.json はそこから書き出す（手で直さない）。
  - STEP は CadQuery があるときだけ（tools/export_step.py。case/step/ に出し、out/<版>/step/index.json に並べる）。
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_case as g  # noqa: E402

STEP_NAMES = {"assembly": "組み立て", "top_plate": "トッププレート", "stiffener": "補強板", "bottom_plate": "ボトムプレート",
              "frame_left": "枠（左）", "frame_right": "枠（右）", "foot": "足（4個同じ）", "pcb_reference": "PCB（参考）"}


def run(*args):
    r = subprocess.run([sys.executable, *args], cwd=g.ROOT, capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    if r.returncode:
        raise SystemExit(f"!! {' '.join(args)} で止まりました\n{out[-2000:]}")
    return out


def main():
    ver = sys.argv[1] if len(sys.argv) > 1 else g.VER
    if ver != g.VER:
        raise SystemExit(f"!! 版が違います：引数 {ver}、tools/gen_case.py の VER = {g.VER}。"
                         f"版を上げるときは gen_case.py の VER（と PARENT）を先に書き換えてください")
    out = os.path.join(g.ROOT, "out", ver)
    run("tools/gen_case.py")                                  # SVG・寸法の JSON（case/params_<版>.json）
    print(run("tools/dims_export.py").splitlines()[-1])       # params/params_<版>.json（根拠つき）
    for ln in run("tools/review_export.py").splitlines():     # 部品ごとの STL と scene.json（注意つき）
        if "注意" in ln or "全体" in ln:
            print(ln)
    tray = getattr(g, "CASE", "sandwich") == "tray"
    try:
        import cadquery  # noqa: F401
        log = run("tools/export_step.py")
        idx = []
        for k, name in STEP_NAMES.items():
            if tray and k == "frame_left":
                name = "トレー（左）"
            if tray and k == "frame_right":
                name = "トレー（右）"
            src = f"case/step/{k}_{ver}.step"
            if os.path.exists(os.path.join(g.ROOT, src)):
                idx.append({"src": src, "name": name, "file": f"{k}_{ver}.step"})
        os.makedirs(os.path.join(out, "step"), exist_ok=True)
        with open(os.path.join(out, "step", "index.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(idx, f, ensure_ascii=False, indent=1)
        print(f"STEP: {len(idx)}個（case/step/）。" + ("体積の確認は export_step.py の出力" if "体積" in log else ""))
    except ImportError:
        print("STEP は書き出しません（CadQuery がありません）")


if __name__ == "__main__":
    main()
