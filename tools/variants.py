"""色の組み合わせ違いの外観比較 docs/img/color_variants_<ver>.png（render_preview.pyを3回呼ぶ）"""
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(__file__))
import gen_case as g

VARIANTS = [("A：すりガラス＋ウォームグレー", "frosted", "#d9d4cb"),
            ("B：透明＋白", "clear", "#f2f0ec"),
            ("C：スモーク＋チャコール", "smoke", "#3b3d40")]


def main():
    tmp = tempfile.mkdtemp()
    font = ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 34)
    out = Image.new("RGB", (900 * len(VARIANTS), 490), "#f4f3f0")
    for i, (lab, top, frame) in enumerate(VARIANTS):
        p = os.path.join(tmp, f"{i}.png")
        subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "render_preview.py"),
                        "--top", top, "--frame", frame, "--out", p], check=True, capture_output=True)
        im = Image.open(p).crop((300, 120, 1500, 700)).resize((900, 435))
        t = Image.new("RGB", (900, 490), "#f4f3f0")
        t.paste(im, (0, 50))
        ImageDraw.Draw(t).text((20, 6), lab, fill="#333", font=font)
        out.paste(t, (i * 900, 0))
    path = os.path.join(g.ROOT, f"docs/img/color_variants_{g.VER}.png")
    out.save(path)
    print(path)


if __name__ == "__main__":
    main()
