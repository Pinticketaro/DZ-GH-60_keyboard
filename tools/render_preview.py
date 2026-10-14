"""外観プレビューを影付きでレンダリングする（ヘッドレスChromium＋three.js）。

使い方: python3 tools/render_preview.py [--frame "#d9d4cb"] [--top frosted|clear|smoke] [--out docs/img/preview_v05.png]
前提: pip install playwright trimesh manifold3d、npm で three@0.160.0 を THREE_DIR に入れておく
      （既定は環境変数 THREE_DIR、なければ tools/.three）
"""
import argparse
import http.server
import math
import os
import shutil
import socketserver
import sys
import tempfile
import threading

import numpy as np
import trimesh

sys.path.insert(0, os.path.dirname(__file__))
import build3d as b3
import gen_case as g

TOP_STYLES = {
    "frosted": ([0.93, 0.95, 0.96, 0.92], 0.55),
    "clear": ([0.80, 0.90, 0.95, 0.45], 0.05),
    "smoke": ([0.25, 0.27, 0.30, 0.80], 0.15),
}


def hex2rgba(h, a=1.0):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)] + [a]


def mesh_of(mf, rgba, rough=0.6, metal=0.0):
    tm = b3.to_trimesh(mf)
    mat = trimesh.visual.material.PBRMaterial(baseColorFactor=rgba, roughnessFactor=rough, metallicFactor=metal,
                                              alphaMode="BLEND" if rgba[3] < 1 else "OPAQUE", doubleSided=True)
    tm.visual = trimesh.visual.TextureVisuals(material=mat)
    return tm


def build_scene(frame_hex, top_style):
    parts, z = b3.build_parts()
    fl, h_front, tan, y_front = g.feet()
    tilt = math.atan(tan)
    # 傾け（前の足の接地点を軸に回す）→ three.js座標（Y上）へ
    T1 = trimesh.transformations.translation_matrix([0, y_front, h_front])
    R = trimesh.transformations.rotation_matrix(tilt, [1, 0, 0])
    C = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]], dtype=float)
    M = C @ R @ T1
    top_rgba, top_rough = TOP_STYLES[top_style]
    acrylic = [0.86, 0.91, 0.94, 0.9]
    meshes = [
        mesh_of(parts["top"], top_rgba, top_rough),
        mesh_of(parts["stiffener"], top_rgba if top_style != "clear" else acrylic, top_rough),
        mesh_of(parts["bottom"], acrylic, 0.3),
        mesh_of(parts["frame_left"], hex2rgba(frame_hex), 0.85),
        mesh_of(parts["frame_right"], hex2rgba(frame_hex), 0.85),
        mesh_of(parts["pcb"], hex2rgba("#1d1f22"), 0.5),
    ] + [mesh_of(f, hex2rgba("#2a2a2a"), 0.9) for f in parts["feet"]] \
      + [mesh_of(c, hex2rgba("#ecebe6"), 0.7) for c in b3.keycaps(z["top1"])]
    import manifold3d as m3
    # スイッチの上部ハウジング（簡略：15.6角×高さ6.6、上面は少し小さく）
    for x, y, w, h in b3.keys():
        u = 19.05
        cx = -0.375 + (x + w / 2) * u
        cy = -0.325 + (y + h / 2) * u
        if w == 1.25 and h == 2:          # ISO Enterのスイッチは縦長部分の中心
            cy = -0.325 + (y + 1) * u
        sw = m3.Manifold.extrude(m3.CrossSection([[(-7.8, -7.8), (7.8, -7.8), (7.8, 7.8), (-7.8, 7.8)]]), 6.0, 0, 0,
                                 [0.75, 0.75]).translate([cx, -cy, z["top1"]])
        meshes.append(mesh_of(sw, hex2rgba("#3a3d42"), 0.6))
    if parts.get("rod") is not None:
        meshes.append(mesh_of(parts["rod"], [0.83, 0.66, 0.36, 1.0], 0.32, 0.0))
    for sd in parts.get("saddle") or []:
        meshes.append(mesh_of(sd, hex2rgba(frame_hex), 0.85))
    # ボルトの頭（ボタンヘッド φ5.7×1.65）
    for (x, y) in g.holes():
        head = m3.Manifold.cylinder(1.65, 2.85, 2.6, 32).translate([x, -y, z["top1"]])
        meshes.append(mesh_of(head, hex2rgba("#8a8d91"), 0.35, 0.9))
    scene = trimesh.Scene()
    for i, m in enumerate(meshes):
        m.apply_transform(M)
        scene.add_geometry(m, node_name=f"p{i}")
    return scene, h_front + z["top1"]


HTML = r"""<!doctype html><html><head><meta charset="utf-8">
<style>html,body{margin:0;background:#f4f3f0;font-family:'Noto Sans CJK JP',sans-serif}
#c{display:block}.lab{position:absolute;font-size:15px;color:#333}</style></head><body>
<canvas id="c" width="1800" height="1150"></canvas>
<div class="lab" style="left:24px;top:14px;font-size:20px">__TITLE__</div>
<div class="lab" style="left:24px;top:760px">斜め後ろから</div>
<div class="lab" style="left:924px;top:760px">右横から</div>
<script type="importmap">{"imports":{"three":"./three/build/three.module.js","three/addons/":"./three/examples/jsm/"}}</script>
<script type="module">
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
const canvas=document.getElementById('c');
const r=new THREE.WebGLRenderer({canvas,antialias:true,preserveDrawingBuffer:true});
r.setPixelRatio(1); r.shadowMap.enabled=true; r.shadowMap.type=THREE.PCFSoftShadowMap;
r.outputColorSpace=THREE.SRGBColorSpace; r.setClearColor(0xf4f3f0,1); r.autoClear=false;
const s=new THREE.Scene();
s.add(new THREE.HemisphereLight(0xffffff,0xd8d4cc,1.4));
const d=new THREE.DirectionalLight(0xffffff,2.2); d.position.set(-120,320,260); d.castShadow=true;
d.shadow.mapSize.set(4096,4096); const sc=d.shadow.camera; sc.left=-260;sc.right=260;sc.top=260;sc.bottom=-260;sc.far=1200; s.add(d);
const fill=new THREE.DirectionalLight(0xffffff,0.6); fill.position.set(250,120,-200); s.add(fill);
const ground=new THREE.Mesh(new THREE.PlaneGeometry(3000,3000),new THREE.ShadowMaterial({opacity:0.18}));
ground.rotation.x=-Math.PI/2; ground.receiveShadow=true; s.add(ground);
new GLTFLoader().load('./model.glb',(gl)=>{
  gl.scene.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true;
    if(o.material.transparent){o.material.depthWrite=false;}}});
  s.add(gl.scene);
  const box=new THREE.Box3().setFromObject(gl.scene); const c=box.getCenter(new THREE.Vector3()); const sz=box.getSize(new THREE.Vector3());
  const W=1800,H=1150;
  // 1) 斜め（透視）
  const p=new THREE.PerspectiveCamera(24,W/700,1,5000);
  p.position.set(c.x-210,c.y+250,c.z+430); p.lookAt(c.x+8,c.y-18,c.z);
  r.setViewport(0,H-740,W,700); r.setScissor(0,H-740,W,700); r.setScissorTest(true); r.clear(); r.render(s,p);
  // 2) 斜め後ろ（透視・低め）
  const p2=new THREE.PerspectiveCamera(24,880/380,1,5000);
  p2.position.set(c.x+235,c.y+62,c.z-330); p2.lookAt(c.x+5,c.y-10,c.z);
  r.setViewport(10,10,880,380); r.setScissor(10,10,880,380); r.clear(); r.render(s,p2);
  // 3) 右横（平行投影）
  const half2=sz.z*0.62, hh2=half2*(380/880);
  const o2=new THREE.OrthographicCamera(-half2,half2,hh2,-hh2,1,5000);
  const yb=box.min.y+hh2*0.85;
  o2.position.set(c.x+800,yb,c.z); o2.lookAt(c.x,yb,c.z);
  r.setViewport(910,10,880,380); r.setScissor(910,10,880,380); r.clear(); r.render(s,o2);
  window.DONE=true;
});
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frame", default="#d9d4cb")
    ap.add_argument("--top", default="frosted", choices=list(TOP_STYLES))
    ap.add_argument("--out", default=os.path.join(g.ROOT, f"docs/img/preview_{g.VER}.png"))
    a = ap.parse_args()
    three = os.environ.get("THREE_DIR", os.path.join(g.ROOT, "tools/.three"))
    work = tempfile.mkdtemp()
    shutil.copytree(os.path.join(three, "node_modules/three"), os.path.join(work, "three"))
    scene, fh = build_scene(a.frame, a.top)
    scene.export(os.path.join(work, "model.glb"))
    top_name = {"frosted": "すりガラス", "clear": "透明", "smoke": "スモーク"}[a.top]
    title = (f"外観プレビュー {g.VER}：トッププレート{top_name}・枠{a.frame}、傾き{g.tilt_deg():g}°{"（真鍮丸棒φ%g）" % g.ROD_D if g.REAR_FOOT == "brass_rod" else ""}、"
             f"手前の高さ{fh:.1f}mm（キーキャップ別）、角R{g.CORNER_R:g}・スムージング{g.CORNER_SMOOTH}")
    open(os.path.join(work, "index.html"), "w", encoding="utf-8").write(HTML.replace("__TITLE__", title))

    class Q(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *x, **k):
            super().__init__(*x, directory=work, **k)

        def log_message(self, *x):
            pass

    httpd = socketserver.TCPServer(("127.0.0.1", 0), Q)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        br = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        pg = br.new_page(viewport={"width": 1800, "height": 1150})
        pg.goto(f"http://127.0.0.1:{port}/index.html")
        pg.wait_for_function("window.DONE===true", timeout=120000)
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        pg.screenshot(path=a.out)
        br.close()
    httpd.shutdown()
    print(a.out)


if __name__ == "__main__":
    main()
