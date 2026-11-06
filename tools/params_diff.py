"""2つの版のパラメータファイル（params_vNN.json）を比べて、変わった値の一覧を出す。
使い方: python params_diff.py params_v02.json params_v03.json [--json out.json]

パラメータファイルの形（monozukuri のテンプレート）
  {"meta": {...}, "params": {"outer_w": {"value": 160, "unit": "mm", "label": "外形の幅"}, ...}}
値だけの形 {"outer_w": 160, ...} や、入れ子の JSON でも比べられる（キーを a.b.c とつなげる）。
表示の言葉は --lang ja|en、無ければ新しい版の meta.lang、環境変数 MONOZUKURI_LANG、どれも無ければ ja。
--json の中身（キーの名前）は言葉によらず同じ。
"""
import argparse
import json
import os
import sys


def resolve_lang(explicit=None, data=None):
    """言葉を決める：引数の --lang ＞ データ（新しい版の meta.lang）＞ 環境変数 MONOZUKURI_LANG ＞ ja"""
    for v in (explicit, data, os.environ.get("MONOZUKURI_LANG")):
        if v in ("ja", "en"):
            return v
    return "ja"


def help_lang(argv):
    """--help の言葉。引数を読む前なので、--lang だけ先に見る"""
    got = None
    for i, s in enumerate(argv):
        if s == "--lang" and i + 1 < len(argv):
            got = argv[i + 1]
        elif s.startswith("--lang="):
            got = s[len("--lang="):]
    return resolve_lang(got)


def meta_lang(d):
    """パラメータファイルの meta.lang（無ければ None）"""
    meta = d.get("meta") if isinstance(d, dict) else None
    return meta.get("lang") if isinstance(meta, dict) else None


def flatten(d, prefix=""):
    out = {}
    if isinstance(d, dict) and ("params" in d or "fab" in d) and not prefix:
        d = {**d.get("params", {}), **d.get("fab", {})}     # monozukuri のパラメータファイル（形の寸法＋加工パラメータ）
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict) and "value" in v:
            out[key] = {"value": v["value"], "unit": v.get("unit", ""), "label": v.get("label", k)}
        elif isinstance(v, dict):
            out.update(flatten(v, key + "."))
        else:
            out[key] = {"value": v, "unit": "", "label": key}
    return out


def diff(a, b):
    A, B = flatten(a), flatten(b)
    rows = []
    for k in sorted(set(A) | set(B), key=lambda x: (list(B).index(x) if x in B else 10 ** 6, x)):
        va, vb = A.get(k), B.get(k)
        if va and vb and va["value"] == vb["value"]:
            continue
        src = vb or va
        row = {"key": k, "label": src["label"], "unit": src["unit"],
               "before": va["value"] if va else None, "after": vb["value"] if vb else None}
        if va is None:
            row["kind"] = "added"
        elif vb is None:
            row["kind"] = "removed"
        else:
            row["kind"] = "changed"
            if isinstance(va["value"], (int, float)) and isinstance(vb["value"], (int, float)) \
                    and not isinstance(va["value"], bool):
                row["delta"] = round(vb["value"] - va["value"], 6)
        rows.append(row)
    return rows


def read_json(p):
    """人や AI が書く JSON。utf-8-sig なら、PowerShell 5.1・メモ帳が付ける BOM があっても読める"""
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def main():
    for _s in (sys.stdout, sys.stderr):        # Windows のパイプは ANSI コードページになるので UTF-8 にそろえる
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8", errors="replace")
    ja = help_lang(sys.argv[1:]) == "ja"
    ap = argparse.ArgumentParser()
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--json")
    ap.add_argument("--lang", choices=["ja", "en"], help="表示の言葉（既定：新しい版の meta.lang ＞ 環境変数 MONOZUKURI_LANG ＞ ja）" if ja
                    else "language of the printed list (default: meta.lang of the newer file > MONOZUKURI_LANG > ja)")
    a = ap.parse_args()
    before, after = (read_json(os.path.expanduser(p)) for p in (a.before, a.after))   # PowerShell は ~ をそのまま渡す
    lang = resolve_lang(a.lang, meta_lang(after))
    rows = diff(before, after)
    if a.json:
        with open(os.path.expanduser(a.json), "w", encoding="utf-8", newline="\n") as f:   # 改行は LF（どの OS でも同じ）
            json.dump(rows, f, ensure_ascii=False, indent=1)
    if not rows:
        print("変わった値はありません" if lang == "ja" else "No values changed")
    for r in rows:
        if lang == "ja":
            d = f"（{r['delta']:+g}{r['unit']}）" if "delta" in r else ""
        else:
            d = f" ({r['delta']:+g}{r['unit']})" if "delta" in r else ""
        print(f"- {r['label']}: {r['before']} → {r['after']}{r['unit'] if r['after'] is not None else ''}{d}")


if __name__ == "__main__":
    main()
