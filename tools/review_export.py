"""確認ボード用に、今の版の部品を組んだ位置のままSTLで書き出し、scene.json を作る（Z上、mm）。
使い方: python3 tools/review_export.py  → out/<ver>/model/*.stl, out/<ver>/scene.json
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import build3d as b3
import gen_case as g

# 3Dプリントする部品と印刷の向き（-z＝上面を下にして刷る）。monozukuri の雛形 common.py の overhangs と同じ考え方
PRINT_UP = {"frame_left": "-z" if g.SKIRT else "z", "frame_right": "-z" if g.SKIRT else "z", "foot": "z"}   # トレー（v18）は底を下に


def overhangs(mesh, deg=45.0, up="z", min_area=1.0):
    import numpy as np
    import trimesh
    dirs = {"z": (0, 0, 1), "-z": (0, 0, -1)}
    R = trimesh.geometry.align_vectors(dirs[up], (0, 0, 1))
    m = mesh.copy()
    m.apply_transform(R)
    n = m.face_normals
    zmin = m.bounds[0][2]
    on_bed = np.all(m.triangles[:, :, 2] < zmin + 0.05, axis=1)
    sel = np.nonzero((-n[:, 2] > np.cos(np.radians(deg)) + 1e-9) & ~on_bed)[0]
    if not len(sel):
        return []
    inset = set(sel.tolist())
    adj = [e for e in m.face_adjacency if e[0] in inset and e[1] in inset]
    out = []
    for grp in trimesh.graph.connected_components(adj, nodes=sel, min_len=1):
        grp = np.asarray(list(grp))
        area = float(m.area_faces[grp].sum())
        if area < min_area:
            continue
        c = (mesh.triangles_center[grp] * mesh.area_faces[grp, None]).sum(axis=0) / area
        h = float((m.triangles_center[grp, 2] * m.area_faces[grp]).sum() / area - zmin)
        out.append({"area": area, "x": float(c[0]), "y": float(c[1]), "h": h})
    return sorted(out, key=lambda r: -r["area"])


def overhang_note(name, mesh, up):
    regs = overhangs(mesh, 45.0, up)
    if not regs:
        return None
    where = "、".join(f"ベッドから{r['h']:.1f}mm（X{r['x']:+.0f}・Y{r['y']:+.0f}付近）約{r['area']:.0f}mm²" for r in regs[:3])
    more = f" ほか{len(regs) - 3}か所" if len(regs) > 3 else ""
    orient = "上面を下にして印刷" if up == "-z" else "底を下にして印刷"
    return f"{name}（{orient}）の下向きの面にサポートが要りそう：{where}{more}（張り出し45°より浅い）"

PARTS = [("top", "トッププレート", "#e6eef2", 0.7, 0.55), ("stiffener", "補強板", "#e6eef2", 0.7, 0.55),
         ("frame_left", "枠（左）", "#d9d4cb", 1, 0.85), ("frame_right", "枠（右）", "#cfc9bf", 1, 0.85),
         ("bottom", "ボトムプレート", "#bcd6e4", 0.8, 0.3), ("pcb", "PCB", "#2d4a35", 1, 0.5)]


def main():
    parts, z = b3.build_parts()
    out = os.path.join(g.ROOT, "out", g.VER)
    os.makedirs(os.path.join(out, "model"), exist_ok=True)
    scene = {"title": f"DZ60ケース {g.VER}", "lang": "ja", "up": "z", "notes": [], "views": ["iso", "back", "side"], "parts": []}
    for key, name, col, op, rough in PARTS:
        if parts.get(key) is None:
            continue
        if g.CASE == "tray" and key.startswith("frame_"):
            name = name.replace("枠", "トレー")
        fn = f"model/{key}.stl"
        tm = b3.to_trimesh(parts[key])
        tm.export(os.path.join(out, fn))
        if key in PRINT_UP:
            note = overhang_note(name, tm, PRINT_UP[key])
            if note:
                scene["notes"].append(note)
        scene["parts"].append({"file": fn, "name": name, "color": col, "opacity": op, "roughness": rough, "metalness": 0})
    for i, f in enumerate(parts["feet"]):
        fn = f"model/foot_{i + 1}.stl"
        tm = b3.to_trimesh(f)
        tm.export(os.path.join(out, fn))
        if i == 0:
            note = overhang_note("足", tm, PRINT_UP["foot"])
            if note:
                scene["notes"].append(note)
        scene["parts"].append({"file": fn, "name": f"足{i + 1}", "color": "#d9d4cb", "opacity": 1, "roughness": 0.85, "metalness": 0})
    json.dump(scene, open(os.path.join(out, "scene.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(os.path.join(out, "scene.json"))
    for n in scene["notes"]:
        print("注意:", n)


if __name__ == "__main__":
    main()
