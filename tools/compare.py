"""前の版と今の版の画像を並べた比較画像を作る（左：前、中：今、右：変わった所を赤で強調）。
使い方: python compare.py before.png after.png --out compare.png [--labels "v02" "v03"] [--no-diff]
  --labels は --labels v02,v03 とも書ける（PowerShell はカンマで2つに分けて渡すので、どちらでも同じ）。
大きさが違う画像は、同じ高さにそろえてから比べる（差分は形がそろっているときだけ意味がある）。
言葉（見出し・表示）は --lang ja|en、無ければ環境変数 MONOZUKURI_LANG、どちらも無ければ ja。
"""
import argparse
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

WIN_FONTS = os.path.join(os.environ.get("WINDIR") or "C:/Windows", "Fonts")      # Windows のフォントのフォルダ
FONT_CANDIDATES = ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                   "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
                   "/System/Library/Fonts/Hiragino Sans GB.ttc"] + \
                  [os.path.join(WIN_FONTS, n) for n in ("YuGothM.ttc", "YuGothR.ttc", "meiryo.ttc", "msgothic.ttc")]


def resolve_lang(explicit=None, data=None):
    """言葉を決める：引数の --lang ＞ データ ＞ 環境変数 MONOZUKURI_LANG ＞ ja"""
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


def font(size):
    try:
        import json
        cache = os.path.expanduser(os.environ.get("MONOZUKURI_CACHE") or "~/.cache/monozukuri")
        with open(os.path.join(cache, "env.json"), encoding="utf-8-sig") as fp:
            env = json.load(fp)
        if env.get("cjk_font_path"):
            return ImageFont.truetype(env["cjk_font_path"], size)
    except Exception:
        pass
    for f in FONT_CANDIDATES:
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def fit(im, h):
    return im.resize((max(1, round(im.width * h / im.height)), h), Image.LANCZOS)


def diff_image(a, b):
    """b を薄くして、a と違う所を赤く塗る。"""
    if a.size != b.size:
        a = a.resize(b.size, Image.LANCZOS)
    d = ImageChops.difference(a.convert("RGB"), b.convert("RGB")).convert("L")
    mask = d.point(lambda v: 255 if v > 28 else 0).filter(ImageFilter.MaxFilter(5))
    base = Image.blend(b.convert("RGB"), Image.new("RGB", b.size, "white"), 0.6)
    red = Image.new("RGB", b.size, (214, 48, 39))
    base.paste(red, mask=mask)
    import numpy as np
    changed = float((np.asarray(mask) > 0).mean())
    return base, changed


def split_labels(argv):
    """--labels a,b（カンマ区切りの1つの引数）と --labels=a,b を --labels a b にする。
    PowerShell は引用符の無い a,b を2つに分けて渡すので、どのシェルでも同じになる。
    分けるのは、次がオプションか終わりのとき、または分けないと画像（before・after）が2つそろわないときだけ
    （--labels "幅160, 高さ80" v03 のように2つ渡したときは、カンマもそのまま）"""
    out = []
    for s in argv:
        out += ["--labels", s[len("--labels="):]] if s.startswith("--labels=") else [s]
    if "--labels" not in out:
        return out
    i = out.index("--labels")
    if i + 1 >= len(out) or "," not in out[i + 1]:
        return out

    def images(args):          # --labels が2つ取ったときに残る、位置引数の数
        n = j = 0
        while j < len(args):
            s = args[j]
            j += 3 if s == "--labels" else 2 if s in ("--out", "--height", "--lang") else 1
            n += not s.startswith("-")
        return n
    nxt = out[i + 2] if i + 2 < len(out) else None
    if nxt is None or nxt.startswith("-") or images(out) < 2:
        return out[:i + 1] + out[i + 1].split(",", 1) + out[i + 2:]
    return out


def main():
    for _s in (sys.stdout, sys.stderr):        # Windows のパイプは ANSI コードページになるので UTF-8 にそろえる
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8", errors="replace")
    ja = help_lang(sys.argv[1:]) == "ja"
    ap = argparse.ArgumentParser()
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--out", required=True)
    ap.add_argument("--labels", nargs=2, default=None, help="既定：前の版 この版" if ja else "default: Previous, This version")
    ap.add_argument("--height", type=int, default=520)
    ap.add_argument("--no-diff", action="store_true")
    ap.add_argument("--lang", choices=["ja", "en"], help="見出し・表示の言葉（既定：環境変数 MONOZUKURI_LANG ＞ ja）" if ja
                    else "language of labels and messages (default: MONOZUKURI_LANG > ja)")
    a = ap.parse_args(split_labels(sys.argv[1:]))
    a.before, a.after, a.out = (os.path.expanduser(p) for p in (a.before, a.after, a.out))   # PowerShell は ~ をそのまま渡す
    lang = resolve_lang(a.lang)
    if a.labels is None:
        a.labels = ["前の版", "この版"] if lang == "ja" else ["Previous", "This version"]

    A, B = Image.open(a.before).convert("RGB"), Image.open(a.after).convert("RGB")
    h = a.height
    tiles = [(fit(A, h), a.labels[0]), (fit(B, h), a.labels[1])]
    note = ""
    if not a.no_diff:
        d, changed = diff_image(A, B)
        tiles.append((fit(d, h), "変わった所（赤）" if lang == "ja" else "Changed (red)"))
        note = f"画素の変化 {changed * 100:.1f}%" if lang == "ja" else f"Pixels changed {changed * 100:.1f}%"
    pad, top = 16, 46
    W = sum(t.width for t, _ in tiles) + pad * (len(tiles) + 1)
    out = Image.new("RGB", (W, h + top + pad), (244, 245, 242))
    dr = ImageDraw.Draw(out)
    f = font(24)
    x = pad
    for im, lab in tiles:
        out.paste(im, (x, top))
        dr.text((x + 4, 10), lab, fill=(40, 48, 44), font=f)
        x += im.width + pad
    if note:
        dr.text((W - pad - dr.textlength(note, font=font(18)), 14), note, fill=(110, 120, 114), font=font(18))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    out.save(a.out)
    print(a.out, note)


if __name__ == "__main__":
    main()
