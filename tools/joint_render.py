"""枠の継ぎ目（ほぞ＋ボルト）の拡大図を、少し離した状態でレンダリングする（ヘッドレスChromium＋three.js）。

使い方: python3 tools/joint_render.py   → docs/img/joint_<ver>.png
"""
import http.server
import math
import os
import shutil
import socketserver
import sys
import tempfile
import threading

import manifold3d as m3
import trimesh

sys.path.insert(0, os.path.dirname(__file__))
import build3d as b3
import gen_case as g
from render_preview import hex2rgba, mesh_of

HTML = r"""<!doctype html><html><head><meta charset="utf-8">
<style>html,body{margin:0;background:#f4f3f0;font-family:'Noto Sans CJK JP',sans-serif}.lab{position:absolute;font-size:17px;color:#333}</style></head><body>
<canvas id="c" width="1600" height="900"></canvas>
<div class="lab" style="left:24px;top:14px;font-size:21px">__TITLE__</div>
<div class="lab" style="left:24px;top:46px">__SUB__</div>
<script type="importmap">{"imports":{"three":"./three/build/three.module.js","three/addons/":"./three/examples/jsm/"}}</script>
<script type="module">
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
const r=new THREE.WebGLRenderer({canvas:document.getElementById('c'),antialias:true,preserveDrawingBuffer:true});
r.outputColorSpace=THREE.SRGBColorSpace; r.setClearColor(0xf4f3f0,1); r.shadowMap.enabled=true;
const s=new THREE.Scene();
s.add(new THREE.HemisphereLight(0xffffff,0xd8d4cc,1.5));
const d=new THREE.DirectionalLight(0xffffff,2.0); d.position.set(-60,160,120); d.castShadow=true; s.add(d);
const f=new THREE.DirectionalLight(0xffffff,0.7); f.position.set(120,60,-80); s.add(f);
new GLTFLoader().load('./model.glb',(gl)=>{
  s.add(gl.scene);
  const box=new THREE.Box3().setFromObject(gl.scene); const c=box.getCenter(new THREE.Vector3());
  const p=new THREE.PerspectiveCamera(30,1600/900,1,2000);
  p.position.set(c.x+30,c.y+28,c.z+78); p.lookAt(c.x,c.y-6,c.z);
  r.render(s,p); window.DONE=true;
});
</script></body></html>"""


def main():
    parts, z = b3.build_parts()
    sx = g.SPLIT_X
    yc = g.joint_wall_y()[1]                     # 手前の壁
    zc = z["bot1"] + g.FRAME_H / 2
    win = m3.Manifold.cube([70, 26, 30]).translate([sx - 45, -yc - 13, -5])
    gap = 14.0                                   # 右半分を離して見せる
    L = parts["frame_left"] ^ win
    R = (parts["frame_right"] ^ win.translate([0, 0, 0])).translate([gap, 0, 0])
    bx_ = sx + g.JB_X
    top = z["bot1"] + g.FRAME_H
    lift = 12.0                                  # ボルトを持ち上げて見せる
    # v16：ほぞは左半分の上側。ボルトはほぞの上から、ナットは右半分の下面（ボトムプレートが当たる段差の面）へ
    bolt = (m3.Manifold.cylinder(1.65, 2.85, 2.6, 40).translate([bx_, -yc, top - g.JB_CB_DEPTH + lift])
            + m3.Manifold.cylinder(g.JB_L, 1.5, 1.5, 32).translate([bx_, -yc, top - g.JB_CB_DEPTH - g.JB_L + lift]))
    rr = 5.5 / math.sqrt(3)
    hexa = m3.CrossSection([[(rr * math.cos(math.radians(60 * k)), rr * math.sin(math.radians(60 * k))) for k in range(6)]])
    nut = (m3.Manifold.extrude(hexa, 2.4) - m3.Manifold.cylinder(3, 1.5, 1.5, 24).translate([0, 0, -0.2])).translate(
        [bx_ + gap, -yc, z["bot1"] - 9])
    frame_c = "#d9d4cb"
    meshes = [mesh_of(L, hex2rgba(frame_c), 0.85), mesh_of(R, hex2rgba("#c9c2b6"), 0.85),
              mesh_of(bolt, hex2rgba("#8a8d91"), 0.35, 0.9), mesh_of(nut, hex2rgba("#6f7276"), 0.35, 0.9)]
    C = [[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]]
    scene = trimesh.Scene()
    for i, m in enumerate(meshes):
        m.apply_transform(C)
        scene.add_geometry(m, node_name=f"p{i}")
    work = tempfile.mkdtemp()
    three = os.environ.get("THREE_DIR", os.path.join(g.ROOT, "tools/.three"))
    shutil.copytree(os.path.join(three, "node_modules/three"), os.path.join(work, "three"))
    scene.export(os.path.join(work, "model.glb"))
    title = f"枠の継ぎ目 {g.VER}：ほぞ＋縦のM3×{g.JB_L:g}ボタンヘッド（手前の壁。右半分を{gap:g}mm離して表示）"
    sub = (f"左半分の上側のほぞ（{g.TONGUE_W:g}×{g.TONGUE_T:g}×{g.TONGUE_L:g}）が右半分の上の溝に入る。ボルトはほぞの上から（頭はざぐりに沈む）、"
           f"ナットは右半分の下面に埋め込む。下のスカートの内側にボトムプレートが入る")
    open(os.path.join(work, "index.html"), "w", encoding="utf-8").write(HTML.replace("__TITLE__", title).replace("__SUB__", sub))

    class Q(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=work, **k)

        def log_message(self, *a):
            pass
    httpd = socketserver.TCPServer(("127.0.0.1", 0), Q)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    out = os.path.join(g.ROOT, f"docs/img/joint_{g.VER}.png")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        br = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        pg = br.new_page(viewport={"width": 1600, "height": 900})
        pg.goto(f"http://127.0.0.1:{httpd.server_address[1]}/index.html")
        pg.wait_for_function("window.DONE===true", timeout=120000)
        pg.screenshot(path=out)
        br.close()
    httpd.shutdown()
    print(out)


if __name__ == "__main__":
    main()
