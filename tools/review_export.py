"""確認ボード用に、今の版の部品を組んだ位置のままSTLで書き出し、scene.json を作る（Z上、mm）。
使い方: python3 tools/review_export.py  → out/<ver>/model/*.stl, out/<ver>/scene.json
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import build3d as b3
import gen_case as g

PARTS = [("top", "トッププレート", "#e6eef2", 0.7, 0.55), ("stiffener", "補強板", "#e6eef2", 0.7, 0.55),
         ("frame_left", "枠（左）", "#d9d4cb", 1, 0.85), ("frame_right", "枠（右）", "#cfc9bf", 1, 0.85),
         ("bottom", "ボトムプレート", "#bcd6e4", 0.8, 0.3), ("pcb", "PCB", "#2d4a35", 1, 0.5)]


def main():
    parts, z = b3.build_parts()
    out = os.path.join(g.ROOT, "out", g.VER)
    os.makedirs(os.path.join(out, "model"), exist_ok=True)
    scene = {"title": f"DZ60ケース {g.VER}", "up": "z", "views": ["iso", "back", "side"], "parts": []}
    for key, name, col, op, rough in PARTS:
        fn = f"model/{key}.stl"
        b3.to_trimesh(parts[key]).export(os.path.join(out, fn))
        scene["parts"].append({"file": fn, "name": name, "color": col, "opacity": op, "roughness": rough, "metalness": 0})
    for i, f in enumerate(parts["feet"]):
        fn = f"model/foot_{i + 1}.stl"
        b3.to_trimesh(f).export(os.path.join(out, fn))
        scene["parts"].append({"file": fn, "name": f"足{i + 1}", "color": "#d9d4cb", "opacity": 1, "roughness": 0.85, "metalness": 0})
    json.dump(scene, open(os.path.join(out, "scene.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(os.path.join(out, "scene.json"))


if __name__ == "__main__":
    main()
