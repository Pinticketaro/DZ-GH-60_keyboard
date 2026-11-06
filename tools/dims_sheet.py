"""モデル化する人に渡す寸法表 docs/寸法表_<版>.md を作る。
形の寸法、加工パラメータ（実測か初期値か・根拠）、モックで見つかった注意点、前の版から変わった値を1枚にまとめる。
使い方: python tools/dims_sheet.py [v03] [--lang ja|en]

English: writes the dimension sheet for the person who builds the CAD model: docs/dims_<version>.md
(Japanese projects: docs/寸法表_<version>.md), plus docs/fusion_params_<version>.csv for Fusion user parameters.
One page with the shape dimensions, the fabrication values (measured or initial, and the basis), notes found in
the mock, and the values changed from the previous version. Language: meta.lang in the params file (or --lang ja|en).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import common  # noqa: E402

TXT = {
    "ja": {
        "file": "寸法表_{ver}.md",
        "added": "追加",
        "title": "# 寸法表 {title} {ver}",
        "intro": ["モックで決めた寸法と、加工パラメータです。モデル化はこの値を出発点にしてください。",
                  "単位はmm、原点と向きは README の決まりに従います。"],
        "shape_h": "## 形の寸法",
        "shape_cols": ["| 項目 | 値 | 単位 | キー | 根拠 | 前の版から |", "|---|---:|---|---|---|---|"],
        "no_basis": "**根拠が書かれていない寸法：** ",
        "refs_h": "## 資料",
        "refs_intro": "寸法の根拠にした図面・データシート・写真・実測の記録（`refs/`）。一覧は `{index}`。",
        "ref_link": "資料",
        "fab_h": "## 加工パラメータ（テストピースで決める値を含む）",
        "fab_intro": "Fusion ではユーザーパラメータに同じ名前（キー）で入れる。状態が「初期値」のものは、"
                     "製作の前にテストピースで実測して置き換える（`tools/coupons.py`、`measurements/試し片記録.csv`）。",
        "fab_cols": ["| 項目 | 値 | 単位 | キー | 状態 | 根拠 | 前の版から |", "|---|---:|---|---|---|---|---|"],
        "todo": "**まだ実測していない値：** ",
        "notes_h": "## モックで見つかった注意点",
        "img_h": "## 画像",
        "img": "`out/{ver}/` の外観・平面図・断面図を参照。",
        "csv_status": "（{st}）",
        "locked": "{path} に書き込めません。Excel などのアプリで開いていたら閉じて、もう一度実行してください",
    },
    "en": {
        "file": "dims_{ver}.md",
        "added": "added",
        "title": "# Dimension sheet {title} {ver}",
        "intro": ["These are the dimensions decided with the mock, and the fabrication values. "
                  "Use them as the starting point for the CAD model.",
                  "Units are mm. The origin and axes follow the rules in README."],
        "shape_h": "## Shape dimensions",
        "shape_cols": ["| Item | Value | Unit | Key | Basis | Change from previous version |", "|---|---:|---|---|---|---|"],
        "no_basis": "**Dimensions without a basis:** ",
        "refs_h": "## References",
        "refs_intro": "Drawings, datasheets, photos and measurement records used as the basis (`refs/`). Index: `{index}`.",
        "ref_link": "ref",
        "fab_h": "## Fabrication values (including values set with coupons)",
        "fab_intro": "In Fusion, enter them as user parameters with the same names (keys). Values with the status \"initial\" "
                     "must be measured with coupons and replaced before fabrication "
                     "(`tools/coupons.py`, `measurements/coupon_log.csv`).",
        "fab_cols": ["| Item | Value | Unit | Key | Status | Basis | Change from previous version |",
                     "|---|---:|---|---|---|---|---|"],
        "todo": "**Not measured yet:** ",
        "notes_h": "## Notes found in the mock",
        "img_h": "## Images",
        "img": "See the exterior views, plan views and sections in `out/{ver}/`.",
        "csv_status": " ({st})",
        "locked": "Cannot write {path}. If it is open in Excel or another app, close it and run again",
    },
}


def not_measured(status):
    """まだテストピースで測っていない値か（状態が「初期値」、英語のパラメータファイルでは "initial"）"""
    s = str(status)
    return s.startswith("初期値") or s.lower().startswith("initial")


def write_text(path, text, t):
    """生成したファイルを LF で書く。Windows では Excel などで開いているファイルに書き込めない（PermissionError）ので、
    トレースバックでなく案内を出して止める"""
    try:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    except PermissionError:
        raise SystemExit(t["locked"].format(path=os.path.relpath(path, common.ROOT).replace(os.sep, "/")))


def main():
    for _s in (sys.stdout, sys.stderr):        # Windows のパイプは ANSI コードページになるので UTF-8 にそろえる
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8", errors="replace")
    ver = common.version_from_argv()
    prm = common.load(ver, lang=common.lang_from_argv())
    t = TXT[prm.lang]
    prev = common.prev_version(ver)
    old = common.load(prev) if prev else None

    def changed(k, v):
        if old is None:
            return ""
        ov = getattr(old.P, k, None)
        return t["added"] if ov is None else (f"{ov} → {v}" if ov != v else "")

    lines = [t["title"].format(title=prm.meta.get('title', ''), ver=ver), ""] + t["intro"] + [""]
    if prm.meta.get("note"):
        lines += [f"> {prm.meta['note']}", ""]
    def basis(item):
        """根拠（basis）と資料（ref：refs/ のファイルか URL）"""
        if not isinstance(item, dict):
            return ""
        b, r = str(item.get("basis", "")), item.get("ref")
        if r:
            r = str(r)
            href = r if "://" in r else "../" + r.replace("\\", "/")   # docs/ から見た相対パス（Windows の区切り \ も / にする）
            b = (b + " " if b else "") + f"[{t['ref_link']}]({href})"
        return b.replace("|", "／")

    lines += [t["shape_h"], ""] + t["shape_cols"]
    params = prm.raw.get("params", {})
    for k in params:
        v = getattr(prm.P, k)
        lines.append(f"| {prm.labels[k]} | {v} | {prm.units[k]} | `{k}` | {basis(params[k])} | {changed(k, v)} |")
    nob = [k for k, it in params.items() if isinstance(it, dict) and not it.get("basis")]
    if nob:
        lines += ["", f"{t['no_basis']}{', '.join('`' + k + '`' for k in nob)}"]

    if prm.fab:
        todo = [k for k, f in prm.fab.items() if not_measured(f.get("status", ""))]
        lines += ["", t["fab_h"], "", t["fab_intro"], ""] + t["fab_cols"]
        for k, f in prm.fab.items():
            v = getattr(prm.P, k)
            lines.append(f"| {prm.labels[k]} | {v} | {prm.units[k]} | `{k}` | {f.get('status', '')} | "
                         f"{basis(f)} | {changed(k, v)} |")
        if todo:
            lines += ["", f"{t['todo']}{', '.join('`' + k + '`' for k in todo)}"]

    sp = os.path.join(common.ROOT, "out", ver, "scene.json")
    if os.path.exists(sp):
        notes = common.read_json(sp, prm.lang).get("notes") or []
        if notes:
            lines += ["", t["notes_h"], ""] + [f"- {n}" for n in notes]
    rdir = os.path.join(common.ROOT, "refs")
    if os.path.isdir(rdir):
        # 隠しファイルは除く：.DS_Store など、Windows の desktop.ini・Thumbs.db、Office が開いている間の ~$ファイル
        files = sorted(f for f in os.listdir(rdir)
                       if not f.startswith((".", "~$")) and f.lower() not in ("desktop.ini", "thumbs.db"))
        index = next((f for f in ("資料.md", "index.md") if f in files), None)
        if files:
            lines += ["", t["refs_h"], "", t["refs_intro"].format(index="refs/" + (index or ""))]
            lines += [""] + [f"- [{f}](../refs/{f})" for f in files if f != index]
    lines += ["", t["img_h"], "", t["img"].format(ver=ver)]
    out = os.path.join(common.ROOT, "docs", t["file"].format(ver=ver))

    # Fusion のユーザーパラメータに写すための一覧（名前・値・単位・コメント）。ファイル名はどの言語でも同じ
    csv = os.path.join(common.ROOT, "docs", f"fusion_params_{ver}.csv")
    rows = ["name,value,unit,comment"]
    for k, v in vars(prm.P).items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            st = prm.fab.get(k, {}).get("status", "")
            rows.append(f"{k},{v},{prm.units[k]},\"{prm.labels[k]}{t['csv_status'].format(st=st) if st else ''}\"")
    # CSV を先に書く（Excel で開いていて書けないとき、寸法表だけが新しくなってずれないように）
    write_text(csv, "\n".join(rows) + "\n", t)
    write_text(out, "\n".join(lines) + "\n", t)
    print(out)
    print(csv)


if __name__ == "__main__":
    main()
