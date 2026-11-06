"""立体モデル（STL / OBJ / 3MF / GLB / STEP）をシェーディング付きでレンダリングして1枚のPNGにする。
モックでも、Fusion などで人が作ってエクスポートしたモデルでも同じように使える。

使い方
  python render_model.py --scene scene.json --out preview.png [--glb model.glb]
  python render_model.py frame.stl:#d9d4cb plate.stl:#bcd6e4:0.6 --out preview.png --title "v03 外観"

部品の指定は  ファイル[:色[:不透明度[:粗さ[:メタリック]]]]  （色は #rrggbb、不透明度 0〜1）
  Windows のドライブ名（C:\\...）はそのまま書ける。ファイル名そのものに : は使えない。
scene.json の形
  {"title": "...", "up": "z", "views": ["iso", "back", "side"],
   "parts": [{"file": "parts/frame.stl", "name": "枠", "color": "#d9d4cb",
              "opacity": 1, "roughness": 0.8, "metalness": 0}]}
  file は scene.json からの相対パス（区切りは /）。up はモデルの上方向（Fusion・多くのCADは z）。
  views に使える名前: iso（等角）, back（斜め後ろ）, front（正面）, side（右側面）, top（上面）
  先頭のビューが大きく、残りが下に並ぶ。平行投影（front・side・top）は地面の影をレンダリングせず、
  ビューごとに枠いっぱいに合わせ、隅にスケールバー（例「スケールバー 20mm」）を入れる。
  --same-scale を付けると、平行投影のビューの縮尺をそろえる（上面と正面の大きさを見比べるとき）。
--glb を付けると、確認ページの3Dビュー用の GLB も保存する。
言葉（ビュー名・スケールバー・表示）は --lang ja|en、無ければ scene.json の "lang"、環境変数 MONOZUKURI_LANG、どれも無ければ ja。

前提: monozukuri-setup スキルで trimesh・playwright・three.js を入れておく（STEP は cascadio も）
"""
import argparse
import http.server
import json
import os
import shutil
import socketserver
import sys
import tempfile
import threading

import numpy as np
import trimesh

DOC_EN = """Render 3D models (STL / OBJ / 3MF / GLB / STEP) with shadows into one PNG.
Works the same for mocks and for models exported from Fusion or other CAD.

Usage
  python render_model.py --scene scene.json --out preview.png [--glb model.glb]
  python render_model.py frame.stl:#d9d4cb plate.stl:#bcd6e4:0.6 --out preview.png --title "v03 exterior"

Part spec:  file[:color[:opacity[:roughness[:metalness]]]]  (color #rrggbb, opacity 0-1)
  A Windows drive (C:\\...) is fine. The file name itself must not contain ":".
scene.json shape
  {"title": "...", "up": "z", "views": ["iso", "back", "side"], "lang": "en",
   "parts": [{"file": "parts/frame.stl", "name": "Frame", "color": "#d9d4cb",
              "opacity": 1, "roughness": 0.8, "metalness": 0}]}
  file is relative to scene.json (use / between folders). up is the model's up axis (z for Fusion and most CAD).
  View names: iso (from above, front left), back (from above, rear), front, side (right), top (straight down)
  The first view is large; the rest line up below it. Parallel views (front, side, top) draw no ground
  shadow, each fills its own frame, and gets a scale bar in the corner (e.g. "Scale 20 mm").
  --same-scale gives the parallel views one scale (to compare the top and front sizes).
--glb also writes a GLB to rotate on the review page.
Language (view names, scale bar, messages): --lang ja|en, else scene.json "lang", else MONOZUKURI_LANG, else ja.

Requires: trimesh, playwright and three.js from the monozukuri-setup skill (cascadio for STEP)
"""

CACHE = os.path.expanduser(os.environ.get("MONOZUKURI_CACHE", "~/.cache/monozukuri"))
VIEW_LABEL = {"ja": {"iso": "等角", "back": "斜め後ろ", "front": "正面", "side": "右側面", "top": "上面"},
              "en": {"iso": "Isometric", "back": "Rear isometric", "front": "Front", "side": "Right side", "top": "Top"}}
BAR_LABEL = {"ja": "スケールバー ${L}mm", "en": "Scale ${L} mm"}       # 縮尺の目安（three.js 側のテンプレート文字列）
BG = "#f4f5f2"


def resolve_lang(explicit=None, data=None):
    """言葉を決める：引数の --lang ＞ データ（scene.json の "lang"）＞ 環境変数 MONOZUKURI_LANG ＞ ja"""
    for v in (explicit, data, os.environ.get("MONOZUKURI_LANG")):
        if v in ("ja", "en"):
            return v
    return "ja"


def help_lang(argv):
    """--help の言葉。引数を読む前なので、--lang と --scene の scene.json だけ先に見る"""
    got = {}
    for i, s in enumerate(argv):
        for k in ("--lang", "--scene"):
            if s == k and i + 1 < len(argv):
                got[k] = argv[i + 1]
            elif s.startswith(k + "="):
                got[k] = s[len(k) + 1:]
    data = None
    try:
        data = read_json(os.path.expanduser(got["--scene"])).get("lang")
    except Exception:
        pass
    return resolve_lang(got.get("--lang"), data)


def read_json(path):
    """scene.json を読む。utf-8-sig なので、PowerShell 5.1・メモ帳が付ける BOM があっても読める"""
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def hex2rgba(h, a=1.0):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)] + [float(a)]


def parse_part(spec):
    # Windows のドライブ名（C:\ や \\server\share）は先に外し、残りを : で分ける。
    # macOS・Linux の splitdrive はいつも "" を返すので、そのまま : で分ける
    drive, rest = os.path.splitdrive(spec)
    if drive and rest[:1] not in ("\\", "/"):    # 「a:#fff」は 1文字のファイル名 a として読む
        drive, rest = "", spec
    bits = rest.split(":")
    p = {"file": drive + bits[0]}
    if len(bits) > 1 and bits[1]:
        p["color"] = bits[1]
    if len(bits) > 2 and bits[2]:
        p["opacity"] = float(bits[2])
    if len(bits) > 3 and bits[3]:
        p["roughness"] = float(bits[3])
    if len(bits) > 4 and bits[4]:
        p["metalness"] = float(bits[4])
    return p


def load_mm(path):
    """メッシュとして読み、mm にそろえる。STEP は cascadio 経由でメートルになるので換算する
    （組み立て STEP はシーンとして読まれるので、シーンの単位で換算してから1つにまとめる）。"""
    obj = trimesh.load(path)
    units = getattr(obj, "units", None)
    if units and units not in ("millimeters", "mm"):
        obj = obj.convert_units("millimeters")
    if isinstance(obj, trimesh.Scene):
        obj = obj.to_mesh() if hasattr(obj, "to_mesh") else obj.dump(concatenate=True)
    return obj


def load_mesh(path, lang="ja"):
    m = load_mm(path)
    if m.is_empty:
        raise SystemExit(f"中身が空です: {path}" if lang == "ja" else f"The model is empty: {path}")
    return m


def report_size(scene, up, lang="ja"):
    """全体の大きさを mm で出す。読み込みのたびに既知の寸法と見比べる（単位の取り違え＝25.4倍・1000倍などを止める）"""
    ext = scene.extents
    if up == "z":                       # three.js 座標（Y上）から元の X・Y・Z に戻して表示
        ext = [ext[0], ext[2], ext[1]]
    if lang == "ja":
        print(f"全体の大きさ X {ext[0]:.1f} × Y {ext[1]:.1f} × Z {ext[2]:.1f} mm")
    else:
        print(f"Overall size X {ext[0]:.1f} × Y {ext[1]:.1f} × Z {ext[2]:.1f} mm")
    big = max(ext)
    if big < 5 or big > 2000:
        if lang == "ja":
            print("!! 大きさが不自然です。単位（mm・m・インチ）の取り違えを疑ってください。"
                  "既知の寸法と比べ、25.4倍・1000倍・1/1000 になっていないか確認")
        else:
            print("!! The size looks wrong. Suspect a unit mix-up (mm, m, inch). "
                  "Compare with a known dimension and check it is not 25.4x, 1000x or 1/1000.")


def build_scene(parts, base, up, lang="ja"):
    scene = trimesh.Scene()
    # three.js は Y が上。Z上のモデルは X軸まわりに -90° 回転して合わせる
    R = np.eye(4)
    if up == "z":
        R = trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0])
    for i, p in enumerate(parts):
        # Windows で書いた scene.json（model\frame.stl）も macOS・Linux で読めるよう、区切りを / にそろえる
        # （Windows は / も受け付ける）。PowerShell は ~ を展開しないので、ここで展開する
        rel = os.path.expanduser(p["file"].replace("\\", "/"))
        f = rel if os.path.isabs(rel) else os.path.join(base, rel)
        m = load_mesh(f, lang)
        m.apply_transform(R)
        rgba = hex2rgba(p.get("color", "#c9ccc6"), p.get("opacity", 1.0))
        mat = trimesh.visual.material.PBRMaterial(
            baseColorFactor=rgba, roughnessFactor=p.get("roughness", 0.7), metallicFactor=p.get("metalness", 0.0),
            alphaMode="BLEND" if rgba[3] < 1 else "OPAQUE", doubleSided=True)
        m.visual = trimesh.visual.TextureVisuals(material=mat)
        # 確認ページの「エクスポート」が部品を見分けられるよう、ノード名は p<番号>_<キー>（英数字）にする
        key = p.get("key") or os.path.splitext(os.path.basename(f))[0]
        scene.add_geometry(m, node_name=f"p{i}_{key}")
    return scene


HTML = r"""<!doctype html><html lang="__LANG__"><head><meta charset="utf-8">
<style>html,body{margin:0;background:__BG__;font-family:'Noto Sans CJK JP','Hiragino Sans','Yu Gothic UI','Yu Gothic','Meiryo',sans-serif}
#c{display:block}.lab{position:absolute;font-size:15px;color:#3b4540}
.bar{position:absolute;height:6px;border:2px solid #3b4540;border-top:0}
.barlab{position:absolute;font-size:13px;color:#3b4540;white-space:nowrap}</style></head><body>
<canvas id="c" width="__W__" height="__H__"></canvas>
<div class="lab" style="left:24px;top:14px;font-size:20px">__TITLE__</div>
__LABELS__
<script>// モジュールが読み込めない（MIME・404）・WebGL が作れない・読み込み後の例外を ERR に入れる（180 秒待たずに止める）
addEventListener('error',e=>{window.ERR=window.ERR||String(e.message||(e.target&&(e.target.src||'script load failed: '+(e.target.type||e.target.tagName)))||e);},true);
addEventListener('unhandledrejection',e=>{window.ERR=window.ERR||String(e.reason);});</script>
<script type="importmap">{"imports":{"three":"./three/build/three.module.js","three/addons/":"./three/examples/jsm/"}}</script>
<script type="module">
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
const VIEWS=__VIEWS__, CELLS=__CELLS__, SAME=__SAME__, PAD=__PAD__, H=__H__;
const canvas=document.getElementById('c');
const r=new THREE.WebGLRenderer({canvas,antialias:true,preserveDrawingBuffer:true});
r.setPixelRatio(1); r.shadowMap.enabled=true; r.shadowMap.type=THREE.PCFSoftShadowMap;
r.outputColorSpace=THREE.SRGBColorSpace; r.setClearColor(new THREE.Color('__BG__'),1); r.autoClear=false;
const s=new THREE.Scene();
s.add(new THREE.HemisphereLight(0xffffff,0xd6d9d2,1.4));
new GLTFLoader().load('./model.glb',(gl)=>{
  gl.scene.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true;
    if(o.material.transparent){o.material.depthWrite=false;}}});
  s.add(gl.scene);
  // 平行投影（上面・正面・右側面）では面の陰影だけだと穴や段差が見えないので、稜線を重ねる
  const edges=new THREE.Group(); gl.scene.updateMatrixWorld(true);
  gl.scene.traverse(o=>{if(o.isMesh){const e=new THREE.LineSegments(new THREE.EdgesGeometry(o.geometry,30),
    new THREE.LineBasicMaterial({color:0x2f3a34,transparent:true,opacity:0.55}));
    e.applyMatrix4(o.matrixWorld); edges.add(e);}});
  edges.visible=false; s.add(edges);
  const box=new THREE.Box3().setFromObject(gl.scene), c=box.getCenter(new THREE.Vector3()), sz=box.getSize(new THREE.Vector3());
  const R=Math.max(sz.x,sz.y,sz.z);
  // 主の光は右手前の上から。斜め上（左手前）から見たとき、影が左奥に見える（見る側と同じ向きからだと影が物の後ろに隠れる）
  const d=new THREE.DirectionalLight(0xffffff,2.2); d.position.set(c.x+0.5*R,c.y+1.2*R,c.z+0.8*R); d.target.position.copy(c);
  d.castShadow=true; d.shadow.mapSize.set(4096,4096); const sc=d.shadow.camera;
  sc.left=-R;sc.right=R;sc.top=R;sc.bottom=-R;sc.near=1;sc.far=6*R; d.shadow.bias=-0.0005; s.add(d); s.add(d.target);
  const fill=new THREE.DirectionalLight(0xffffff,0.6); fill.position.set(c.x+0.8*R,c.y+0.4*R,c.z-0.7*R); s.add(fill);
  // 横からの光：右側面の図でも、面の向き（面取り・斜面）で明暗が付くように
  const sideL=new THREE.DirectionalLight(0xffffff,0.7); sideL.position.set(c.x+1.0*R,c.y+0.35*R,c.z+0.25*R); s.add(sideL);
  const ground=new THREE.Mesh(new THREE.PlaneGeometry(20*R,20*R),new THREE.ShadowMaterial({opacity:0.18}));
  ground.rotation.x=-Math.PI/2; ground.position.y=box.min.y-0.01; ground.receiveShadow=true; s.add(ground);
  const dirs={iso:[-0.55,0.62,1.0],back:[0.6,0.28,-1.0],front:[0,0,1],side:[1,0,0],top:[0,1,0.0001]};
  const ortho={side:1,top:1,front:1};
  // 平行投影：見える2辺の長さで、ビューごとに枠いっぱいに合わせる（PAD＝図に対する枠の大きさ）。
  // --same-scale のときは、いちばん小さく写るビューの縮尺にそろえる
  const fit={};
  VIEWS.forEach((v,i)=>{
    if(!ortho[v]) return;
    const [x,y,w,h]=CELLS[i], asp=w/h;
    const span = v==='side' ? [sz.z,sz.y] : v==='top' ? [sz.x,sz.z] : [sz.x,sz.y];
    let hw=Math.max(span[0],1e-3)*PAD/2, hh=Math.max(span[1],1e-3)*PAD/2; if(hw/hh>asp) hh=hw/asp; else hw=hh*asp;
    fit[i]={hw,hh,ppm:h/(2*hh)};
  });
  if(SAME){
    const ppm=Math.min(...Object.values(fit).map(f=>f.ppm));
    for(const i in fit){ const [x,y,w,h]=CELLS[i]; fit[i]={hw:w/2/ppm,hh:h/2/ppm,ppm}; }
  }
  // 縮尺の目安：1・2・5×10^k mm のうち、枠の幅の1割前後になる長さ
  const barLen=(w,ppm)=>{ let L=0.1; for(const c of [0.1,0.2,0.5,1,2,5,10,20,50,100,200,500,1000,2000]){ if(c*ppm<=Math.max(60,w*0.12)) L=c; } return L; };
  const sameL=SAME&&Object.keys(fit).length ? Math.min(...Object.keys(fit).map(i=>barLen(CELLS[i][2],fit[i].ppm))) : 0;
  for(const i in fit){
    const [x,y,w,h]=CELLS[i], ppm=fit[i].ppm, L=sameL||barLen(w,ppm);
    const bar=document.createElement('div'); bar.className='bar';
    bar.style.left=(x+18)+'px'; bar.style.top=(H-y-22)+'px'; bar.style.width=Math.round(L*ppm)+'px'; document.body.appendChild(bar);
    const lab=document.createElement('div'); lab.className='barlab'; lab.textContent=`__BARLAB__`;
    lab.style.left=(x+18)+'px'; lab.style.top=(H-y-44)+'px'; document.body.appendChild(lab);
  }
  VIEWS.forEach((v,i)=>{
    const [x,y,w,h]=CELLS[i]; const asp=w/h; const dv=new THREE.Vector3(...dirs[v]).normalize();
    let cam;
    if(ortho[v]){
      const {hw,hh}=fit[i];
      cam=new THREE.OrthographicCamera(-hw,hw,hh,-hh,0.1,10*R);
      cam.position.copy(c).addScaledVector(dv,3*R); if(v==='top') cam.up.set(0,0,-1); cam.lookAt(c);
    } else {
      cam=new THREE.PerspectiveCamera(24,asp,0.1,20*R);
      const sph=box.getBoundingSphere(new THREE.Sphere()).radius;
      const dist=sph/Math.sin(THREE.MathUtils.degToRad(Math.min(24,24*asp)/2))*0.92;
      cam.position.copy(c).addScaledVector(dv,dist); cam.lookAt(c);
    }
    edges.visible=!!ortho[v];
    ground.visible=!ortho[v];          // 上面・正面・右側面では地面の影をレンダリングしない（大きな灰色の形になって読みにくい）
    r.setViewport(x,y,w,h); r.setScissor(x,y,w,h); r.setScissorTest(true); r.clear(); r.render(s,cam);
  });
  window.DONE=true;
},undefined,(e)=>{window.ERR=String(e);});
</script></body></html>"""


ORTHO = ("front", "side", "top")
PAD = 1.1           # 平行投影の枠は図の 1.1 倍（図が枠の約9割を占める）
PERSP_ASPECT = 1.6  # 斜めの図の枠の縦横比の目安


def view_aspect(v, ext):
    """ビューに写る形の横÷縦（ext は three.js の座標＝Y上の大きさ）"""
    x, y, z = (max(float(e), 1e-3) for e in ext)
    return {"side": z / y, "top": x / z, "front": x / y}.get(v, PERSP_ASPECT)


def layout(views, W, ext, lang="ja"):
    """先頭のビューを大きく、残りを下に1列に並べる。three.js のビューポートは左下原点。
    下の列は、形の縦横比に合う高さにする（細長い枠に縦長の正面図が小さく入るのを避ける）。"""
    big_h = int(W * 0.42)
    rest = views[1:]
    n, gap = len(rest), 10
    small_h, widths = 0, []
    if rest:
        avail = W - gap * (n + 1)
        asp = [min(4.0, max(0.3, view_aspect(v, ext))) for v in rest]
        cap = big_h if all(v in ORTHO for v in rest) else int(W * 0.3)
        small_h = int(max(W * 0.24, min(cap, avail / (sum(asp) * PAD))))
        natural = [a * PAD * small_h for a in asp]
        if sum(natural) <= avail:                       # 縦横比どおりの幅に、余りを等しく足す
            extra = (avail - sum(natural)) / n
            widths = [int(w + extra) for w in natural]
        else:                                           # 入りきらないときは等分（従来どおり）
            widths = [avail // n] * n
    H = 40 + big_h + (small_h + 40 if rest else 0) + 10
    cells, labels, names = [], [], VIEW_LABEL[lang]
    cells.append([0, H - 40 - big_h, W, big_h])
    x = gap
    for i, w in enumerate(widths):
        cells.append([x, 10, w, small_h])
        labels.append(f'<div class="lab" style="left:{x + 14}px;top:{H - 10 - small_h - 30}px">{names[rest[i]]}</div>')
        x += w + gap
    labels.insert(0, f'<div class="lab" style="left:24px;top:44px">{names[views[0]]}</div>')
    return H, cells, "\n".join(labels)


def three_dir(lang="ja"):
    d = os.path.expanduser(os.environ.get("THREE_DIR") or os.path.join(CACHE, "three", "node_modules", "three"))
    if not os.path.isfile(os.path.join(d, "build", "three.module.js")):
        raise SystemExit("three.js が見つかりません。monozukuri-setup スキルを実行してください" if lang == "ja"
                         else "three.js was not found. Run the monozukuri-setup skill.")
    return d


# 配信するファイルの種類。Windows の mimetypes はレジストリを読み、.js が text/plain になっている PC がある
# （そのままだとブラウザがモジュールを読まない）。ここで決めておけば OS によらず同じになる
MIME = {".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".json": "application/json",
        ".glb": "model/gltf-binary", ".wasm": "application/wasm", ".css": "text/css"}


def render(scene, title, views, out, width=1800, bg=BG, same_scale=False, lang="ja"):
    three = three_dir(lang)              # 先に確かめる（無ければ作業フォルダを作らずに止める）
    work = tempfile.mkdtemp()
    try:
        _render_in(work, three, scene, title, views, out, width, bg, same_scale, lang)
    finally:
        shutil.rmtree(work, ignore_errors=True)     # 作業フォルダ（model.glb など）を消す。消せなくても止めない


def _render_in(work, three, scene, title, views, out, width, bg, same_scale, lang):
    scene.export(os.path.join(work, "model.glb"))
    H, cells, labels = layout(views, width, scene.extents, lang)
    html = (HTML.replace("__TITLE__", title).replace("__LABELS__", labels).replace("__BARLAB__", BAR_LABEL[lang])
            .replace("__W__", str(width)).replace("__LANG__", lang)
            .replace("__H__", str(H)).replace("__VIEWS__", json.dumps(views)).replace("__CELLS__", json.dumps(cells))
            .replace("__BG__", bg).replace("__SAME__", "true" if same_scale else "false").replace("__PAD__", str(PAD)))
    with open(os.path.join(work, "index.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(html)

    class Q(http.server.SimpleHTTPRequestHandler):
        extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, **MIME}

        def __init__(self, *a, **k):
            super().__init__(*a, directory=work, **k)

        def translate_path(self, path):
            # /three/... は three.js のフォルダから配信する（シンボリックリンクは Windows では
            # 管理者権限か開発者モードが要るので使わない。別のドライブにあっても読める）
            if path.startswith("/three/"):
                self.directory = three
                try:
                    return super().translate_path(path[len("/three"):])
                finally:
                    self.directory = work
            return super().translate_path(path)

        def log_message(self, *a):
            pass

    httpd = socketserver.TCPServer(("127.0.0.1", 0), Q)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as p:
            br = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
            pg = br.new_page(viewport={"width": width, "height": H})
            pg.goto(f"http://127.0.0.1:{port}/index.html")
            pg.wait_for_function("window.DONE===true || window.ERR", timeout=180000)
            err = pg.evaluate("window.ERR")
            if err:
                raise SystemExit(f"レンダリングに失敗しました: {err}" if lang == "ja" else f"Rendering failed: {err}")
            os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
            pg.screenshot(path=out)
            br.close()
    finally:
        httpd.shutdown()
        httpd.server_close()


def main():
    for _s in (sys.stdout, sys.stderr):        # Windows のパイプは ANSI コードページになるので UTF-8 にそろえる
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8", errors="replace")
    ja = help_lang(sys.argv[1:]) == "ja"
    ap = argparse.ArgumentParser(description=__doc__ if ja else DOC_EN, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("parts", nargs="*", help="ファイル[:色[:不透明度[:粗さ[:メタリック]]]]" if ja
                    else "file[:color[:opacity[:roughness[:metalness]]]]")
    ap.add_argument("--scene", help="scene.json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--views", nargs="+", default=None, help="カンマ区切り（空白区切りも可）。例: iso,back,side" if ja
                    else "comma-separated (spaces also work), e.g. iso,back,side")
    ap.add_argument("--up", default=None, choices=["z", "y"])
    ap.add_argument("--glb", help="確認ページ用のGLBも保存する" if ja else "also write a GLB for the review page")
    ap.add_argument("--width", type=int, default=1800)
    ap.add_argument("--same-scale", action="store_true", help="平行投影のビューの縮尺をそろえる" if ja
                    else "use one scale for the parallel views")
    ap.add_argument("--lang", choices=["ja", "en"], help="図と表示の言葉（既定：scene.json の lang ＞ 環境変数 MONOZUKURI_LANG ＞ ja）" if ja
                    else "language of labels and messages (default: scene.json lang > MONOZUKURI_LANG > ja)")
    a = ap.parse_args()
    # --views は nargs="+" なので、すぐ後ろの部品まで取ってしまう（--views iso,top a.stl:#fff …）。
    # ビュー名には . : / \ が入らないので、それを含む語は部品に戻す
    if a.views:
        is_part = lambda t: any(c in t for c in ".:/\\")
        a.parts += [t for t in a.views if is_part(t)]
        a.views = [t for t in a.views if not is_part(t)] or None
    # PowerShell は ~ を展開せずに渡すので、ここで展開する
    a.out = os.path.expanduser(a.out)
    a.scene = a.scene and os.path.expanduser(a.scene)
    a.glb = a.glb and os.path.expanduser(a.glb)

    if a.scene:
        sc = read_json(a.scene)
        base = os.path.dirname(os.path.abspath(a.scene))
        parts = sc["parts"]
    else:
        sc, base, parts = {}, os.getcwd(), [parse_part(s) for s in a.parts]
    lang = resolve_lang(a.lang, sc.get("lang"))
    # --views は「iso,top」でも「iso top」でも受ける（PowerShell がカンマで分けて渡すことがある）。
    # 部品の有無より先に確かめる（--views が部品の名前を取ったときに、その名前を示せる）
    views = [v.strip() for v in ",".join(a.views).split(",") if v.strip()] if a.views else None
    views = views or sc.get("views") or ["iso", "back", "side"]
    for v in views:
        if v not in VIEW_LABEL[lang]:
            raise SystemExit(f"ビュー名が違います: {v}（{', '.join(VIEW_LABEL[lang])}）" if lang == "ja"
                             else f"Unknown view name: {v} ({', '.join(VIEW_LABEL[lang])})")
    if not parts:
        raise SystemExit("部品がありません（--scene か ファイル名を指定）" if lang == "ja"
                         else "No parts (give --scene or file names)")
    up = a.up or sc.get("up", "z")
    title = a.title or sc.get("title", "")
    scene = build_scene(parts, base, up, lang)
    report_size(scene, up, lang)
    if a.glb:
        os.makedirs(os.path.dirname(os.path.abspath(a.glb)), exist_ok=True)
        scene.export(a.glb)
    render(scene, title, views, a.out, a.width, same_scale=a.same_scale, lang=lang)
    print(a.out)


if __name__ == "__main__":
    main()
