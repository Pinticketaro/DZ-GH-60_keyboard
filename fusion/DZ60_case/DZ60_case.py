"""DZ60 ケース：寸法ベース（パラメトリック）のモデルを組み立てる Fusion 360 スクリプト。

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

DATA = json.loads(r"""{"params": [["outer_w", "315 mm", "外形の幅"], ["outer_h", "126 mm", "外形の奥行き"], ["corner_r", "8 mm", "外形の角（曲率連続のフィレット）"], ["inset", "0.3 mm", "枠を外形より内側へ下げる量"], ["wall", "14 mm", "枠の幅（外形から枠の内側まで）"], ["inner_r", "4.5 mm", "枠の内側の角"], ["bottom_t", "3 mm", "ボトムプレートの厚さ"], ["skirt_t", "2 mm", "枠のスカートの厚さ（ボトムプレートを囲む）"], ["skirt_c", "0.2 mm", "スカートとボトムプレートのすき間"], ["skirt_h", "bottom_t - 0.1 mm", "スカートの高さ（ボトムプレートより少し低く）"], ["under_pcb", "5 mm", "PCBの下（ケースフォーム）"], ["pcb_t", "1.6 mm", "PCBの厚さ"], ["gap_stiff_pcb", "1.5 mm", "補強板とPCBの間（プレートフォーム）"], ["frame_h", "under_pcb + pcb_t + gap_stiff_pcb", "枠の高さ（自動）"], ["stiff_t", "2 mm", "補強板の厚さ"], ["top_t", "1.5 mm", "トッププレートの厚さ（MXの爪は1.6以下）"], ["hole_d", "3.4 mm", "M3の通し穴（手前の列・枠のつなぎ目・足）"], ["rear_hole_d", "4 mm", "奥の列の穴（丸棒に戻すときの余裕）"], ["hx1", "9.15 mm", "ネジ穴のX（左端）"], ["hx2", "107.7 mm", "ネジ穴のX（中央左）"], ["hx3", "outer_w - hx2", "ネジ穴のX（中央右・左右対称）"], ["hx4", "outer_w - hx1", "ネジ穴のX（右端・左右対称）"], ["hy_f", "7 mm", "手前の列のY"], ["hy_r", "outer_h - hy_f", "奥の列のY（前後対称）"], ["sw", "14 mm", "スイッチ穴（1u）。カーフ補正はここで"], ["stiff_off", "0.8 mm", "補強板の抜きの広げ量（片側）"], ["usb_x", "33.2 mm", "USB切り欠きの中心X（要実測）"], ["usb_w", "13 mm", "USB切り欠きの幅（要実測）"], ["split_x", "outer_w / 2", "枠の分割位置"], ["tongue_w", "9 mm", "つなぎ目のほぞの幅"], ["tongue_t", "3.8 mm", "ほぞの厚さ（枠の上面から下へ）"], ["tongue_l", "16 mm", "ほぞの長さ（分割位置から右へ）"], ["tongue_c", "0.2 mm", "ほぞ穴のすき間"], ["jb_x", "8 mm", "分割位置からつなぎ目のボルトまで"], ["jy_f", "(inset + wall) / 2", "つなぎ目の手前の壁の中心Y"], ["jy_r", "outer_h - jy_f", "つなぎ目の奥の壁の中心Y"], ["cb_d", "6.2 mm", "ボルトの頭のざぐり径"], ["cb_depth", "1.9 mm", "ざぐりの深さ"], ["nut_depth", "2.6 mm", "つなぎ目のナット溝の深さ"], ["foot_w", "12 mm", "足の幅"], ["foot_h", "3.7 mm", "足の高さ"], ["foot_skin", "1 mm", "足のナットの上の肉"]], "sw1": [[24.15, 101.1], [43.2, 101.1], [62.25, 101.1], [81.3, 101.1], [100.35, 101.1], [119.399, 101.1], [138.45, 101.1], [157.5, 101.1], [176.55, 101.1], [195.6, 101.1], [214.65, 101.1], [233.7, 101.1], [252.75, 101.1], [28.912, 82.05], [52.725, 82.05], [71.775, 82.05], [90.825, 82.05], [109.875, 82.05], [128.925, 82.05], [147.975, 82.05], [167.025, 82.05], [186.075, 82.05], [205.125, 82.05], [224.175, 82.05], [243.225, 82.05], [262.274, 82.05], [31.293, 63.0], [57.487, 63.0], [76.537, 63.0], [95.587, 63.0], [114.637, 63.0], [133.687, 63.0], [152.737, 63.0], [171.787, 63.0], [190.837, 63.0], [209.887, 63.0], [228.937, 63.0], [247.987, 63.0], [267.037, 63.0], [24.15, 43.95], [43.2, 43.95], [62.25, 43.95], [81.3, 43.95], [100.35, 43.95], [119.399, 43.95], [138.45, 43.95], [157.5, 43.95], [176.55, 43.95], [195.6, 43.95], [214.65, 43.95], [233.7, 43.95], [252.75, 43.95], [271.8, 43.95], [290.85, 43.95], [26.531, 24.9], [50.343, 24.9], [74.156, 24.9], [214.65, 24.9], [233.7, 24.9], [252.75, 24.9], [271.8, 24.9], [290.85, 24.9]], "stab": [{"no": 14, "kind": "2u（横）", "rects": [["スイッチ", 281.325, 101.1, 14.0, 14.0], ["ワイヤーの溝", 281.325, 101.1, 17.05, 4.6], ["ハウジング", 269.425, 100.48, 6.75, 12.3], ["切り欠き", 269.425, 100.451, 3.3, 14.201], ["張り出し", 265.637, 102.0, 0.825, 2.8], ["ハウジング", 293.225, 100.48, 6.75, 12.3], ["切り欠き", 293.225, 100.451, 3.3, 14.201], ["張り出し", 297.012, 102.0, 0.825, 2.8]]}, {"no": 28, "kind": "2u（縦）", "rects": [["スイッチ", 288.468, 72.525, 14.0, 14.0], ["ワイヤーの溝", 288.468, 72.525, 4.6, 17.05], ["ハウジング", 287.848, 60.625, 12.3, 6.75], ["切り欠き", 287.818, 60.625, 14.2, 3.3], ["張り出し", 289.368, 56.838, 2.8, 0.825], ["ハウジング", 287.848, 84.425, 12.3, 6.75], ["切り欠き", 287.818, 84.425, 14.2, 3.3], ["張り出し", 289.368, 88.213, 2.8, 0.825]]}, {"no": 60, "kind": "6.25u（横）", "rects": [["スイッチ", 145.593, 24.9, 14.0, 14.0], ["ワイヤーの溝", 145.593, 24.9, 93.25, 4.6], ["ハウジング", 95.593, 24.28, 6.75, 12.3], ["切り欠き", 95.593, 24.25, 3.3, 14.2], ["張り出し", 91.805, 25.8, 0.825, 2.8], ["ハウジング", 195.593, 24.28, 6.75, 12.3], ["切り欠き", 195.593, 24.25, 3.3, 14.2], ["張り出し", 199.38, 25.8, 0.825, 2.8]]}], "stiff_stab": [[[264.425, 104.2], [264.425, 99.8], [265.25, 99.8], [265.25, 93.53], [266.974, 93.53], [266.974, 92.55], [271.875, 92.55], [271.875, 93.3], [290.775, 93.3], [290.775, 92.55], [295.675, 92.55], [295.675, 93.53], [297.4, 93.53], [297.4, 99.8], [298.225, 99.8], [298.225, 104.2], [297.4, 104.2], [297.4, 107.43], [295.675, 107.43], [295.675, 108.351], [289.125, 108.351], [289.125, 108.9], [273.525, 108.9], [273.525, 108.351], [266.974, 108.351], [266.974, 107.43], [265.25, 107.43], [265.25, 104.2]], [[279.918, 86.875], [279.918, 81.975], [280.668, 81.975], [280.668, 63.075], [279.918, 63.075], [279.918, 58.175], [280.898, 58.175], [280.898, 56.45], [287.168, 56.45], [287.168, 55.625], [291.568, 55.625], [291.568, 56.45], [294.798, 56.45], [294.798, 58.175], [295.718, 58.175], [295.718, 64.725], [296.268, 64.725], [296.268, 80.325], [295.718, 80.325], [295.718, 86.875], [294.798, 86.875], [294.798, 88.6], [291.568, 88.6], [291.568, 89.425], [287.168, 89.425], [287.168, 88.6], [280.898, 88.6], [280.898, 86.875]], [[90.593, 28.0], [90.593, 23.6], [91.418, 23.6], [91.418, 17.33], [93.143, 17.33], [93.143, 16.35], [98.043, 16.35], [98.043, 17.33], [99.768, 17.33], [99.768, 21.8], [137.792, 21.8], [137.792, 17.1], [153.393, 17.1], [153.393, 21.8], [191.418, 21.8], [191.418, 17.33], [193.143, 17.33], [193.143, 16.35], [198.043, 16.35], [198.043, 17.33], [199.768, 17.33], [199.768, 23.6], [200.593, 23.6], [200.593, 28.0], [199.768, 28.0], [199.768, 31.23], [198.043, 31.23], [198.043, 32.15], [193.143, 32.15], [193.143, 31.23], [191.418, 31.23], [191.418, 28.0], [153.393, 28.0], [153.393, 32.7], [137.792, 32.7], [137.792, 28.0], [99.768, 28.0], [99.768, 31.23], [98.043, 31.23], [98.043, 32.15], [93.143, 32.15], [93.143, 31.23], [91.418, 31.23], [91.418, 28.0]]], "feet": [[["hx1", "hy_f"], ["hx2", "hy_f"]], [["hx1", "hy_r"], ["hx2", "hy_r"]], [["hx3", "hy_f"], ["hx4", "hy_f"]], [["hx3", "hy_r"], ["hx4", "hy_r"]]], "nut_af": 6.1, "ver": "v16"}""")
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

        # ---- ボトムプレート（スカートの内側。ネジ穴はU字の切り欠き）
        stage = "ボトムプレート"
        comp = new_comp("Bottom plate")
        e = "(inset + skirt_t + skirt_c)"
        sk = comp.sketches.add(comp.xYConstructionPlane)
        sk.name = "ボトムプレートの外形（スカートの内側）"
        dim_rect(sk, e, e, f"outer_w - 2 * {e}", f"outer_h - 2 * {e}")
        f = extrude(comp, sk.profiles.item(0), "0 mm", "bottom_t", name="ボトムプレート")
        ev_e = ev(e)
        g2_fillet(comp, vertical_edges_at(f.bodies.item(0), [(ev_e, ev_e), (W - ev_e, ev_e), (W - ev_e, H - ev_e), (ev_e, H - ev_e)]),
                  f"corner_r - {e}", "外形の角")
        f.bodies.item(0).name = "bottom_plate"
        stage = "ボトムプレートの切り欠き"
        sk = comp.sketches.add(comp.xYConstructionPlane)
        sk.name = "ネジの切り欠き（U字、縁へ開く）"
        for xe in ("hx1", "hx2", "hx3", "hx4"):
            dim_circle(sk, xe, "hy_f", "hole_d")
            dim_rect(sk, f"{xe} - hole_d / 2", "0.5 mm", "hole_d", "hy_f - 0.5 mm")
            dim_circle(sk, xe, "hy_r", "rear_hole_d")
            dim_rect(sk, f"{xe} - rear_hole_d / 2", "hy_r", "rear_hole_d", "outer_h - hy_r - 0.5 mm")
        extrude(comp, all_profiles(sk), "-1 mm", "bottom_t + 2 mm", adsk.fusion.FeatureOperations.CutFeatureOperation, name="ネジの切り欠き")

        # ---- 枠
        stage = "枠"
        comp = new_comp("Frame")
        sk = outline_sketch(comp, "枠の外形・内側・ネジ穴", "inset", "inset", "outer_w - 2 * inset", "outer_h - 2 * inset")
        dim_rect(sk, "wall", "wall", "outer_w - 2 * wall", "outer_h - 2 * wall")
        f = extrude(comp, main_profile(sk), z_frame, "frame_h", name="枠")
        frame = f.bodies.item(0)
        stage = "スカート"
        sk = comp.sketches.add(comp.xYConstructionPlane)
        sk.name = "スカート（ボトムプレートを囲む輪）"
        dim_rect(sk, "inset", "inset", "outer_w - 2 * inset", "outer_h - 2 * inset")
        dim_rect(sk, "inset + skirt_t", "inset + skirt_t", "outer_w - 2 * (inset + skirt_t)", "outer_h - 2 * (inset + skirt_t)")
        extrude(comp, main_profile(sk), "bottom_t - skirt_h", "skirt_h", adsk.fusion.FeatureOperations.JoinFeatureOperation,
                bodies=[frame], name="スカート")
        frame = comp.bRepBodies.item(0)
        ins = ev("inset")
        g2_fillet(comp, vertical_edges_at(frame, [(ins, ins), (W - ins, ins), (W - ins, H - ins), (ins, H - ins)]),
                  "corner_r - inset", "枠の外の角")
        sti = ev("inset + skirt_t")
        g2_fillet(comp, vertical_edges_at(comp.bRepBodies.item(0), [(sti, sti), (W - sti, sti), (W - sti, H - sti), (sti, H - sti)]),
                  "corner_r - inset - skirt_t", "スカートの内の角")
        wl = ev("wall")
        g2_fillet(comp, vertical_edges_at(comp.bRepBodies.item(0), [(wl, wl), (W - wl, wl), (W - wl, H - wl), (wl, H - wl)]),
                  "inner_r", "枠の内の角")
        frame = comp.bRepBodies.item(0)
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
        extrude(comp, all_profiles(sk), "bottom_t + frame_h - tongue_t - tongue_c", "tongue_t + tongue_c + 1 mm",
                adsk.fusion.FeatureOperations.CutFeatureOperation, bodies=[B("frame_right")], name="ほぞ穴（右半分の上側）")
        stage = "つなぎ目（ほぞ）"
        sk = comp.sketches.add(comp.xYConstructionPlane)
        sk.name = "ほぞ"
        for jy in ("jy_f", "jy_r"):
            dim_rect(sk, "split_x - 0.5 mm", f"{jy} - tongue_w / 2", "tongue_l + 0.5 mm", "tongue_w")
        extrude(comp, all_profiles(sk), "bottom_t + frame_h - tongue_t", "tongue_t", adsk.fusion.FeatureOperations.JoinFeatureOperation,
                bodies=[B("frame_left")], name="ほぞ（左半分の上側）")
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
                bodies=[B("frame_left")], negative=True, name="ざぐり（ほぞの上面）")
        sk = comp.sketches.add(comp.xYConstructionPlane)
        sk.name = "つなぎ目のナット溝（二面幅は固定）"
        for jy in ("jy_f", "jy_r"):
            hexagon(sk, ev("split_x + jb_x"), ev(jy), DATA["nut_af"])
        extrude(comp, all_profiles(sk), z_frame, "nut_depth", adsk.fusion.FeatureOperations.CutFeatureOperation,
                bodies=[B("frame_right")], name="つなぎ目のナット溝（右半分の下面）")

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
