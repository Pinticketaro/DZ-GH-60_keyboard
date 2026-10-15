"""Fusion 360で実行すると、寸法（ユーザーパラメータ）で動くケースのモデルを組み立てるスクリプトを生成する。

出力: fusion/DZ60_case/DZ60_case.py と DZ60_case.manifest
Fusion: ユーティリティ → アドイン → スクリプトとアドイン →「＋」（マイスクリプト）→ fusion/DZ60_case フォルダを選ぶ → 実行
使い方: python3 tools/make_fusion_script.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import gen_case as g
import fusion_drawings as fd

OUT = os.path.join(g.ROOT, "fusion/DZ60_case")


def r3(v):
    return round(float(v), 3)


def main():
    D = fd.data()
    holes = sorted(D["holes"], key=lambda h: (h[0][1], h[0][0]))
    hx = sorted({r3(c[0]) for c, _ in holes})
    hy = sorted({r3(c[1]) for c, _ in holes})
    sw1 = [(r3(s["x"]), r3(s["y"])) for s in D["sw"] if s["kind"] == "1u"]
    stab = []
    for s in D["sw"]:
        if s["kind"] != "1u":
            rr, _ = fd.stab_rects(s)
            stab.append(dict(no=s["no"], kind=s["kind"], rects=[(n, r3(x), r3(y), r3(w), r3(h)) for n, x, y, w, h in rr]))
    stiff_stab = [[(r3(x), r3(y)) for x, y in p] for p in D["stiff"] if len(p) > 4]
    bars = [dict(a=(r3(b["holes"][0][0]), r3(b["holes"][0][1])), b=(r3(b["holes"][1][0]), r3(b["holes"][1][1]))) for b in D["bars"]]
    # 足の穴は外形のネジ穴と同じ位置 → パラメータ名で表す
    xname = {hx[0]: "hx1", hx[1]: "hx2", hx[2]: "hx3", hx[3]: "hx4"}
    yname = {hy[0]: "hy_f", hy[1]: "hy_r"}
    feet = []
    for b in bars:
        feet.append([(xname[b["a"][0]], yname[b["a"][1]]), (xname[b["b"][0]], yname[b["b"][1]])])
    params = [
        ("outer_w", f"{g.OUTER_W:g} mm", "外形の幅"),
        ("outer_h", f"{g.OUTER_H:g} mm", "外形の奥行き"),
        ("corner_r", f"{g.CORNER_R:g} mm", "外形の角（曲率連続のフィレット）"),
        ("inset", f"{g.FRAME_INSET:g} mm", "枠を外形より内側へ下げる量"),
        ("wall", f"{g.WALL:g} mm", "枠の幅（外形から枠の内側まで）"),
        ("inner_r", f"{g.INNER_R:g} mm", "枠の内側の角"),
        ("bottom_t", f"{g.BOTTOM_T:g} mm", "ボトムプレートの厚さ"),
        ("under_pcb", f"{g.UNDER_PCB:g} mm", "PCBの下（ケースフォーム）"),
        ("pcb_t", f"{g.PCB_T:g} mm", "PCBの厚さ"),
        ("gap_stiff_pcb", f"{g.GAP_STIFF_PCB:g} mm", "補強板とPCBの間（プレートフォーム）"),
        ("frame_h", "under_pcb + pcb_t + gap_stiff_pcb", "枠の高さ（自動）"),
        ("stiff_t", f"{g.STIFF_T:g} mm", "補強板の厚さ"),
        ("top_t", f"{g.TOP_T:g} mm", "トッププレートの厚さ（MXの爪は1.6以下）"),
        ("hole_d", f"{g.HOLE_D:g} mm", "M3の通し穴（手前の列・枠のつなぎ目・足）"),
        ("rear_hole_d", f"{g.REAR_HOLE_D:g} mm", "奥の列の穴（丸棒に戻すときの余裕）"),
        ("hx1", f"{hx[0]:g} mm", "ネジ穴のX（左端）"),
        ("hx2", f"{hx[1]:g} mm", "ネジ穴のX（中央左）"),
        ("hx3", "outer_w - hx2", "ネジ穴のX（中央右・左右対称）"),
        ("hx4", "outer_w - hx1", "ネジ穴のX（右端・左右対称）"),
        ("hy_f", f"{hy[0]:g} mm", "手前の列のY"),
        ("hy_r", "outer_h - hy_f", "奥の列のY（前後対称）"),
        ("sw", "14 mm", "スイッチ穴（1u）。カーフ補正はここで"),
        ("stiff_off", f"{g.STIFF_OFFSET:g} mm", "補強板の抜きの広げ量（片側）"),
        ("usb_x", f"{g.USB_X - fd.OX0:g} mm", "USB切り欠きの中心X（要実測）"),
        ("usb_w", f"{g.USB_W:g} mm", "USB切り欠きの幅（要実測）"),
        ("split_x", "outer_w / 2", "枠の分割位置"),
        ("tongue_w", f"{g.TONGUE_W:g} mm", "つなぎ目のほぞの幅"),
        ("tongue_t", f"{g.TONGUE_T:g} mm", "ほぞの厚さ（下面から）"),
        ("tongue_l", f"{g.TONGUE_L:g} mm", "ほぞの長さ（分割位置から右へ）"),
        ("tongue_c", f"{g.TONGUE_CLEAR:g} mm", "ほぞ穴のすき間"),
        ("jb_x", f"{g.JB_X:g} mm", "分割位置からつなぎ目のボルトまで"),
        ("jy_f", "(inset + wall) / 2", "つなぎ目の手前の壁の中心Y"),
        ("jy_r", "outer_h - jy_f", "つなぎ目の奥の壁の中心Y"),
        ("cb_d", f"{g.JB_CB_D:g} mm", "ボルトの頭のざぐり径"),
        ("cb_depth", f"{g.JB_CB_DEPTH:g} mm", "ざぐりの深さ"),
        ("nut_depth", f"{g.JB_NUT_DEPTH:g} mm", "つなぎ目のナット溝の深さ"),
        ("foot_w", f"{g.RIB_W:g} mm", "足の幅"),
        ("foot_h", f"{g.feet()[1]:g} mm", "足の高さ"),
        ("foot_skin", f"{g.FOOT_SKIN:g} mm", "足のナットの上の肉"),
    ]
    data = dict(params=params, sw1=sw1, stab=stab, stiff_stab=stiff_stab, feet=feet,
                nut_af=g.NUT_POCKET_AF, ver=g.VER)
    os.makedirs(OUT, exist_ok=True)
    src = TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    open(os.path.join(OUT, "DZ60_case.py"), "w", encoding="utf-8").write(src)
    open(os.path.join(OUT, "DZ60_case.manifest"), "w", encoding="utf-8").write(json.dumps({
        "autodeskProduct": "Fusion360", "type": "script", "author": "DZ-GH-60_keyboard",
        "description": {"": f"DZ60ケース（{g.VER}）を寸法ベースで組み立てる"}, "supportedOS": "windows|mac", "editEnabled": True},
        ensure_ascii=False, indent=2))
    print(os.path.join(OUT, "DZ60_case.py"))


TEMPLATE = r'''"""DZ60 ケース：寸法ベース（パラメトリック）のモデルを組み立てる Fusion 360 スクリプト。

実行すると新しいデザインを作り、ユーザーパラメータ（修正 → パラメータを変更）と、
寸法つきのスケッチ・押し出し・フィレット・分割のタイムラインでケースを組み立てる。
パラメータの値を変えると、外形・厚さ・ネジ穴・枠・つなぎ目・足が追従する。
座標：外形の左下が原点、X＝右、Y＝奥、Z＝上（ボトムプレートの下面＝0）。
このファイルは tools/make_fusion_script.py で生成（手で直すより、生成元を直して作り直す）。
"""
import json
import math
import traceback

import adsk.core
import adsk.fusion

DATA = json.loads(r"""__DATA__""")
CM = 0.1                                  # Fusionの内部単位はcm


def run(context):
    app = adsk.core.Application.get()
    ui = app.userInterface
    stage = "開始"
    try:
        doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        design = adsk.fusion.Design.cast(app.activeProduct)
        design.designType = adsk.fusion.DesignTypes.ParametricDesignType
        design.fusionUnitsManager.distanceDisplayUnits = adsk.fusion.DistanceUnits.MillimeterDistanceUnits
        root = design.rootComponent
        root.name = "DZ60 case " + DATA["ver"]
        um = design.unitsManager

        stage = "パラメータ"
        up = design.userParameters
        for name, expr, comment in DATA["params"]:
            up.add(name, adsk.core.ValueInput.createByString(expr), "mm", comment)

        def ev(expr):
            """式の値（mm）"""
            return um.evaluateExpression(expr, "mm") * 10

        def V(expr):
            return adsk.core.ValueInput.createByString(expr)

        def P(x, y):
            return adsk.core.Point3D.create(x * CM, y * CM, 0)

        def new_comp(name):
            occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            c = occ.component
            c.name = name
            return c

        def dist_dim(sk, p1, p2, horizontal, expr, tx, ty):
            o = (adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation if horizontal
                 else adsk.fusion.DimensionOrientations.VerticalDimensionOrientation)
            d = sk.sketchDimensions.addDistanceDimension(p1, p2, o, P(tx, ty))
            d.parameter.expression = expr
            return d

        def corners(lines):
            pts = []
            for i in range(lines.count):
                pts += [lines.item(i).startSketchPoint, lines.item(i).endSketchPoint]
            ll = min(pts, key=lambda s: s.geometry.x + s.geometry.y)
            ur = max(pts, key=lambda s: s.geometry.x + s.geometry.y)
            lr = max(pts, key=lambda s: s.geometry.x - s.geometry.y)
            return ll, lr, ur

        def dim_rect(sk, x0, y0, w, h):
            """寸法つきの長方形：左下の角の位置（原点から）と幅・高さを式で。"""
            lines = sk.sketchCurves.sketchLines.addTwoPointRectangle(P(ev(x0), ev(y0)), P(ev(x0) + ev(w), ev(y0) + ev(h)))
            ll, lr, ur = corners(lines)
            o = sk.originPoint
            if abs(ev(x0)) < 1e-9 and abs(ev(y0)) < 1e-9:
                sk.geometricConstraints.addCoincident(ll, o)
            else:
                dist_dim(sk, o, ll, True, x0, ev(x0) / 2, ev(y0) - 4)
                dist_dim(sk, o, ll, False, y0, ev(x0) - 4, ev(y0) / 2)
            dist_dim(sk, ll, lr, True, w, ev(x0) + ev(w) / 2, ev(y0) - 6)
            dist_dim(sk, lr, ur, False, h, ev(x0) + ev(w) + 4, ev(y0) + ev(h) / 2)
            return lines

        def dim_circle(sk, xe, ye, de):
            c = sk.sketchCurves.sketchCircles.addByCenterRadius(P(ev(xe), ev(ye)), ev(de) / 2 * CM)
            d = sk.sketchDimensions.addDiameterDimension(c, P(ev(xe) + ev(de), ev(ye) + ev(de)))
            d.parameter.expression = de
            dist_dim(sk, sk.originPoint, c.centerSketchPoint, True, xe, ev(xe) / 2, ev(ye) + 3)
            dist_dim(sk, sk.originPoint, c.centerSketchPoint, False, ye, ev(xe) + 3, ev(ye) / 2)
            return c

        def centered_rect(sk, cx, cy, wexpr, hexpr=None):
            """中心を固定し、幅・高さを式で決める長方形（スイッチ穴など）。"""
            hexpr = hexpr or wexpr
            w, h = ev(wexpr), ev(hexpr)
            lines = sk.sketchCurves.sketchLines.addTwoPointRectangle(P(cx - w / 2, cy - h / 2), P(cx + w / 2, cy + h / 2))
            ll, lr, ur = corners(lines)
            cp = sk.sketchPoints.add(P(cx, cy))
            cp.isFixed = True
            diag = sk.sketchCurves.sketchLines.addByTwoPoints(ll, ur)
            diag.isConstruction = True
            sk.geometricConstraints.addMidPoint(cp, diag)
            sk.sketchDimensions.addDistanceDimension(ll, lr, adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
                                                     P(cx, cy - h / 2 - 2)).parameter.expression = wexpr
            sk.sketchDimensions.addDistanceDimension(lr, ur, adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
                                                     P(cx + w / 2 + 2, cy)).parameter.expression = hexpr
            return lines

        def fixed_rect(sk, cx, cy, w, h):
            lines = sk.sketchCurves.sketchLines.addTwoPointRectangle(P(cx - w / 2, cy - h / 2), P(cx + w / 2, cy + h / 2))
            for i in range(lines.count):
                lines.item(i).isFixed = True
            return lines

        def fixed_poly(sk, pts):
            L = sk.sketchCurves.sketchLines
            first = L.addByTwoPoints(P(*pts[0]), P(*pts[1]))
            prev = first
            made = [first]
            for q in pts[2:]:
                prev = L.addByTwoPoints(prev.endSketchPoint, P(*q))
                made.append(prev)
            made.append(L.addByTwoPoints(prev.endSketchPoint, first.startSketchPoint))
            for ln in made:
                ln.isFixed = True

        def hexagon(sk, cx, cy, af):
            rr = af / math.sqrt(3)
            pts = [(cx + rr * math.cos(math.radians(60 * k)), cy + rr * math.sin(math.radians(60 * k))) for k in range(6)]
            L = sk.sketchCurves.sketchLines
            first = L.addByTwoPoints(P(*pts[0]), P(*pts[1]))
            prev = first
            made = [first]
            for q in pts[2:]:
                prev = L.addByTwoPoints(prev.endSketchPoint, P(*q))
                made.append(prev)
            made.append(L.addByTwoPoints(prev.endSketchPoint, first.startSketchPoint))
            for ln in made:
                ln.isFixed = True

        def outline_sketch(comp, name, x0="0 mm", y0="0 mm", w="outer_w", h="outer_h", holes=True):
            sk = comp.sketches.add(comp.xYConstructionPlane)
            sk.name = name
            dim_rect(sk, x0, y0, w, h)
            if holes:
                for xe in ("hx1", "hx2", "hx3", "hx4"):
                    dim_circle(sk, xe, "hy_f", "hole_d")
                    dim_circle(sk, xe, "hy_r", "rear_hole_d")
            return sk

        def main_profile(sk):
            """いちばん多くの輪（穴）を持つ領域＝板そのもの。"""
            best = None
            for i in range(sk.profiles.count):
                pr = sk.profiles.item(i)
                if best is None or pr.profileLoops.count > best.profileLoops.count:
                    best = pr
            return best

        def extrude(comp, prof, start_expr, dist_expr, op=adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
                    bodies=None, negative=False, name=None):
            ex = comp.features.extrudeFeatures
            inp = ex.createInput(prof, op)
            inp.setOneSideExtent(adsk.fusion.DistanceExtentDefinition.create(V(dist_expr)),
                                 adsk.fusion.ExtentDirections.NegativeExtentDirection if negative
                                 else adsk.fusion.ExtentDirections.PositiveExtentDirection)
            if start_expr and start_expr != "0 mm":
                inp.startExtent = adsk.fusion.OffsetStartDefinition.create(V(start_expr))
            if bodies is not None:
                inp.participantBodies = bodies
            f = ex.add(inp)
            if name:
                f.name = name
            return f

        def all_profiles(sk):
            col = adsk.core.ObjectCollection.create()
            for i in range(sk.profiles.count):
                col.add(sk.profiles.item(i))
            return col

        def vertical_edges_at(body, pts_mm, tol=0.6):
            col = adsk.core.ObjectCollection.create()
            for e in body.edges:
                gm = e.geometry
                if not isinstance(gm, adsk.core.Line3D):
                    continue
                s, t = gm.startPoint, gm.endPoint
                if abs(s.x - t.x) > 1e-6 or abs(s.y - t.y) > 1e-6:
                    continue
                for (x, y) in pts_mm:
                    if abs(s.x * 10 - x) < tol and abs(s.y * 10 - y) < tol:
                        col.add(e)
            return col

        def g2_fillet(comp, edges, expr, name):
            fl = comp.features.filletFeatures
            fi = fl.createInput()
            try:
                es = fi.edgeSetInputs.addConstantRadiusEdgeSet(edges, V(expr), False)
                try:
                    es.continuity = adsk.fusion.SurfaceContinuityTypes.CurvatureSurfaceContinuityType
                except Exception:
                    pass
            except AttributeError:
                fi.addConstantRadiusEdgeSet(edges, V(expr), False)
                try:
                    fi.isG2 = True
                except Exception:
                    pass
            f = fl.add(fi)
            f.name = name
            return f

        W, H = ev("outer_w"), ev("outer_h")
        outer_corners = [(0, 0), (W, 0), (W, H), (0, H)]
        z_frame = "bottom_t"
        z_stiff = "bottom_t + frame_h"
        z_top = "bottom_t + frame_h + stiff_t"

        # ---- ボトムプレート
        stage = "ボトムプレート"
        comp = new_comp("Bottom plate")
        sk = outline_sketch(comp, "外形とネジ穴")
        f = extrude(comp, main_profile(sk), "0 mm", "bottom_t", name="ボトムプレート")
        g2_fillet(comp, vertical_edges_at(f.bodies.item(0), outer_corners), "corner_r", "外形の角")
        f.bodies.item(0).name = "bottom_plate"

        # ---- 枠
        stage = "枠"
        comp = new_comp("Frame")
        sk = outline_sketch(comp, "枠の外形・内側・ネジ穴", "inset", "inset", "outer_w - 2 * inset", "outer_h - 2 * inset")
        dim_rect(sk, "wall", "wall", "outer_w - 2 * wall", "outer_h - 2 * wall")
        f = extrude(comp, main_profile(sk), z_frame, "frame_h", name="枠")
        frame = f.bodies.item(0)
        ins = ev("inset")
        g2_fillet(comp, vertical_edges_at(frame, [(ins, ins), (W - ins, ins), (W - ins, H - ins), (ins, H - ins)]),
                  "corner_r - inset", "枠の外の角")
        wl = ev("wall")
        g2_fillet(comp, vertical_edges_at(frame, [(wl, wl), (W - wl, wl), (W - wl, H - wl), (wl, H - wl)]),
                  "inner_r", "枠の内の角")
        stage = "USBの切り欠き"
        sk = comp.sketches.add(comp.xYConstructionPlane)
        sk.name = "USB切り欠き"
        dim_rect(sk, "usb_x - usb_w / 2", "outer_h - wall - 1 mm", "usb_w", "wall + 2 mm")
        extrude(comp, sk.profiles.item(0), z_frame, "frame_h", adsk.fusion.FeatureOperations.CutFeatureOperation, name="USB切り欠き")
        stage = "枠の分割"
        pl_in = comp.constructionPlanes.createInput()
        pl_in.setByOffset(comp.yZConstructionPlane, V("split_x"))
        split_plane = comp.constructionPlanes.add(pl_in)
        split_plane.name = "分割面"
        sp_in = comp.features.splitBodyFeatures.createInput(frame, split_plane, True)
        comp.features.splitBodyFeatures.add(sp_in)
        bodies = sorted([comp.bRepBodies.item(i) for i in range(comp.bRepBodies.count)], key=lambda b: b.boundingBox.minPoint.x)
        bodies[0].name, bodies[1].name = "frame_left", "frame_right"

        def B(name):
            for i in range(comp.bRepBodies.count):
                if comp.bRepBodies.item(i).name == name:
                    return comp.bRepBodies.item(i)
            raise RuntimeError(name + " が見つからない")

        stage = "つなぎ目（ほぞ穴）"
        sk = comp.sketches.add(comp.xYConstructionPlane)
        sk.name = "ほぞ穴"
        for jy in ("jy_f", "jy_r"):
            dim_rect(sk, "split_x - 0.01 mm", f"{jy} - tongue_w / 2 - tongue_c", "tongue_l + tongue_c + 0.01 mm", "tongue_w + 2 * tongue_c")
        extrude(comp, all_profiles(sk), z_frame, "tongue_t + tongue_c", adsk.fusion.FeatureOperations.CutFeatureOperation,
                bodies=[B("frame_right")], name="ほぞ穴")
        stage = "つなぎ目（ほぞ）"
        sk = comp.sketches.add(comp.xYConstructionPlane)
        sk.name = "ほぞ"
        for jy in ("jy_f", "jy_r"):
            dim_rect(sk, "split_x - 0.5 mm", f"{jy} - tongue_w / 2", "tongue_l + 0.5 mm", "tongue_w")
        extrude(comp, all_profiles(sk), z_frame, "tongue_t", adsk.fusion.FeatureOperations.JoinFeatureOperation,
                bodies=[B("frame_left")], name="ほぞ")
        stage = "つなぎ目（ボルト穴・ざぐり・ナット溝）"
        sk = comp.sketches.add(comp.xYConstructionPlane)
        sk.name = "つなぎ目のボルト穴"
        for jy in ("jy_f", "jy_r"):
            dim_circle(sk, "split_x + jb_x", jy, "hole_d")
        extrude(comp, all_profiles(sk), z_frame, "frame_h", adsk.fusion.FeatureOperations.CutFeatureOperation,
                bodies=[B("frame_left"), B("frame_right")], name="つなぎ目のボルト穴")
        sk = comp.sketches.add(comp.xYConstructionPlane)
        sk.name = "ざぐり"
        for jy in ("jy_f", "jy_r"):
            dim_circle(sk, "split_x + jb_x", jy, "cb_d")
        extrude(comp, all_profiles(sk), "bottom_t + frame_h", "cb_depth", adsk.fusion.FeatureOperations.CutFeatureOperation,
                bodies=[B("frame_right")], negative=True, name="ざぐり")
        sk = comp.sketches.add(comp.xYConstructionPlane)
        sk.name = "つなぎ目のナット溝（二面幅は固定）"
        for jy in ("jy_f", "jy_r"):
            hexagon(sk, ev("split_x + jb_x"), ev(jy), DATA["nut_af"])
        extrude(comp, all_profiles(sk), z_frame, "nut_depth", adsk.fusion.FeatureOperations.CutFeatureOperation,
                bodies=[B("frame_left")], name="つなぎ目のナット溝")

        # ---- 補強板
        stage = "補強板"
        comp = new_comp("Stiffener")
        sk = outline_sketch(comp, "補強板（外形・ネジ穴・抜き）")
        for (x, y) in DATA["sw1"]:
            centered_rect(sk, x, y, "sw + 2 * stiff_off")
        for poly in DATA["stiff_stab"]:
            fixed_poly(sk, poly)
        f = extrude(comp, main_profile(sk), z_stiff, "stiff_t", name="補強板")
        g2_fillet(comp, vertical_edges_at(f.bodies.item(0), outer_corners), "corner_r", "外形の角")
        f.bodies.item(0).name = "stiffener"

        # ---- トッププレート
        stage = "トッププレート"
        comp = new_comp("Top plate")
        sk = outline_sketch(comp, "トッププレート（外形・ネジ穴・スイッチ穴）")
        for (x, y) in DATA["sw1"]:
            centered_rect(sk, x, y, "sw")
        for st in DATA["stab"]:
            for (nm, x, y, w, h) in st["rects"]:
                fixed_rect(sk, x, y, w, h)
        f = extrude(comp, main_profile(sk), z_top, "top_t", name="トッププレート")
        g2_fillet(comp, vertical_edges_at(f.bodies.item(0), outer_corners), "corner_r", "外形の角")
        f.bodies.item(0).name = "top_plate"

        # ---- 足（4本）
        stage = "足"
        comp = new_comp("Feet")
        sk = comp.sketches.add(comp.xYConstructionPlane)
        sk.name = "足の形（穴の中心に合わせた長丸）"
        for (a, b) in DATA["feet"]:
            ca = dim_circle(sk, a[0], a[1], "foot_w")
            cb = dim_circle(sk, b[0], b[1], "foot_w")
            r = ev("foot_w") / 2
            ax_, ay_, bx_, by_ = ev(a[0]), ev(a[1]), ev(b[0]), ev(b[1])
            for s in (1, -1):
                ln = sk.sketchCurves.sketchLines.addByTwoPoints(P(ax_, ay_ + s * r), P(bx_, by_ + s * r))
                sk.geometricConstraints.addCoincident(ln.startSketchPoint, ca)
                sk.geometricConstraints.addCoincident(ln.endSketchPoint, cb)
                sk.geometricConstraints.addTangent(ln, ca)
                sk.geometricConstraints.addTangent(ln, cb)
        extrude(comp, all_profiles(sk), "0 mm", "foot_h", negative=True, name="足")
        sk = comp.sketches.add(comp.xYConstructionPlane)
        sk.name = "足の穴"
        for pair in DATA["feet"]:
            for (xe, ye) in pair:
                dim_circle(sk, xe, ye, "hole_d")
        extrude(comp, all_profiles(sk), "-foot_h - 1 mm", "foot_h + 2 mm", adsk.fusion.FeatureOperations.CutFeatureOperation, name="足の穴")
        sk = comp.sketches.add(comp.xYConstructionPlane)
        sk.name = "足のナット溝（二面幅は固定）"
        for pair in DATA["feet"]:
            for (xe, ye) in pair:
                hexagon(sk, ev(xe), ev(ye), DATA["nut_af"])
        extrude(comp, all_profiles(sk), "-foot_h", "foot_h - foot_skin", adsk.fusion.FeatureOperations.CutFeatureOperation, name="足のナット溝")
        for i in range(comp.bRepBodies.count):
            comp.bRepBodies.item(i).name = f"foot_{i + 1}"

        app.activeViewport.fit()
        ui.messageBox("DZ60ケースを組み立てました。\n修正 → パラメータを変更 で寸法を変えられます。", "DZ60 case")
    except Exception:
        ui.messageBox(f"「{stage}」で止まりました。\n\n{traceback.format_exc()}", "DZ60 case")
'''

if __name__ == "__main__":
    main()
