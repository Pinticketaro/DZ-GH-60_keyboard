"""確認ページを PC で開く（Artifact を公開できない環境、たとえば Claude Code 用）。
# monozukuri プラグイン（review-page スキル）の scripts/serve_review.py の写し。PC で確認ボードを開くため、プロジェクトに置いた
プロジェクトの review/ を localhost の空いているポートで配り、ブラウザで開く。
three.js や 3D モデルの読み込みは file:// では動かないので、ローカルのサーバーで配る。

使い方
  python3 serve_review.py <プロジェクト>             … 配ってブラウザを開く（止めるまで動き続ける。裏で動かす）
  python3 serve_review.py <プロジェクト> --no-open   … ブラウザを開かない
  python3 serve_review.py <プロジェクト> --stop      … 動いているサーバーを止める
すでに同じプロジェクトのサーバーが動いていれば、新しく立てずにそのページを開く。

ページに書いたフィードバック・問いの答えは review/feedback_local.json に保存される（Artifact の db と同じ形）：
  {"feedback": {"<id>": {...}}, "answers": {"<版>~q<番号>~local": {...}}, "decisions": {"<版>~q<番号>": {...}}}
Claude は「フィードバックを読んで」と頼まれたらこのファイルを読み、返信（status・resolvedIn・reply）と
決定（decisions）を同じファイルに書く。ページを開き直す（タブに戻る）と見える。
サーバーの場所は review/.serve.json に書く（--stop が使う）。
表示の言語：--lang ja|en ＞ review/board.json の "lang" ＞ 環境変数 MONOZUKURI_LANG ＞ ja。
ページの文言は board.html が board.json の "lang" で選ぶ。

English
  Opens the review page on this PC (for setups that cannot publish an Artifact, e.g. Claude Code).
  Serves <project>/review/ on a free localhost port and opens the browser.
    serve_review.py <project> [--no-open] [--stop] [--lang ja|en]
  Feedback and answers written on the page are saved to review/feedback_local.json (same shape as the
  Artifact db). Message language: --lang > review/board.json "lang" > env MONOZUKURI_LANG > ja.
"""
import argparse
import datetime
import http.server
import json
import os
import secrets
import signal
import socketserver
import subprocess
import sys
import threading

STORE = "feedback_local.json"
STATE = ".serve.json"
WRITABLE = {"feedback", "answers"}       # ページから書けるのはこの2つ。decisions は Claude がファイルに書く
MAX_BODY = 64 * 1024
lock = threading.Lock()

# 表示する文言（ja／en）
MSG = {
    "ja": {
        "open_manually": "ブラウザで開いてください: {url}",
        "stopped": "止めました（{url}）",
        "not_running": "動いているサーバーはありません",
        "no_index": "{rv}/index.html がありません。先に build_page.py で確認ページを作ってください",
        "running": "すでに動いています: {url}（止めるとき: python3 {cmd} {project} --stop）",
        "page": "確認ページ: {url}",
        "store": "フィードバックの保存先: {path}",
        "stop_hint": "止めるとき: python3 {cmd} {project} --stop",
        "port_help": "ポート（既定：空いているもの）",
    },
    "en": {
        "open_manually": "Open this in a browser: {url}",
        "stopped": "Stopped ({url})",
        "not_running": "No server is running",
        "no_index": "{rv}/index.html not found. Build the review page with build_page.py first",
        "running": "Already running: {url} (to stop: python3 {cmd} {project} --stop)",
        "page": "Review page: {url}",
        "store": "Feedback is saved to: {path}",
        "stop_hint": "To stop: python3 {cmd} {project} --stop",
        "port_help": "port (default: any free port)",
    },
}


def resolve_lang(explicit=None, data=None):
    for v in (explicit, data, os.environ.get("MONOZUKURI_LANG")):
        if v in ("ja", "en"):
            return v
    return "ja"


def board_lang(rv):
    """review/board.json の lang（無ければ None）"""
    try:
        return json.load(open(os.path.join(rv, "board.json"), encoding="utf-8")).get("lang")
    except (OSError, ValueError, AttributeError):
        return None


def load_store(path):
    try:
        d = json.load(open(path, encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        d = {}
    for k in ("feedback", "answers", "decisions"):
        d.setdefault(k, {})
    return d


def save_store(path, d):
    tmp = path + ".tmp"
    json.dump(d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except (OSError, TypeError):
        return False


def open_browser(url, lang="ja"):
    cmd = {"darwin": ["open", url]}.get(sys.platform, ["xdg-open", url])
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        print(MSG[lang]["open_manually"].format(url=url))


def make_handler(rv):
    store_path = os.path.join(rv, STORE)

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=rv, **k)

        def log_message(self, *a):
            pass

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")     # 作り直したページ・Claude の返信がすぐ見えるように
            super().end_headers()

        def send_json(self, code, obj):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path.split("?")[0] == "/feedback":
                with lock:
                    return self.send_json(200, load_store(store_path))
            if os.path.basename(self.path.split("?")[0]) in (STORE, STATE):
                return self.send_json(404, {"error": "not_found"})
            return super().do_GET()

        def do_POST(self):
            if self.path.split("?")[0] != "/feedback":
                return self.send_json(404, {"error": "not_found"})
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0 or n > MAX_BODY:
                return self.send_json(413, {"error": "too_large"})
            try:
                req = json.loads(self.rfile.read(n))
            except json.JSONDecodeError:
                return self.send_json(400, {"error": "bad_json"})
            col = req.get("collection")
            if col not in WRITABLE:
                return self.send_json(403, {"error": "not_writable"})
            with lock:
                d = load_store(store_path)
                if req.get("delete"):
                    d[col].pop(str(req.get("id")), None)
                else:
                    doc = req.get("doc")
                    if not isinstance(doc, dict):
                        return self.send_json(400, {"error": "bad_doc"})
                    did = str(req.get("id") or datetime.datetime.now().strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(3))
                    d[col][did] = doc
                save_store(store_path, d)
                return self.send_json(200, d)

    return H


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--port", type=int, default=0, help=MSG[resolve_lang()]["port_help"])
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--stop", action="store_true")
    ap.add_argument("--lang", choices=["ja", "en"])
    a = ap.parse_args()
    rv = os.path.join(os.path.abspath(a.project), "review")
    lang = resolve_lang(a.lang, board_lang(rv))
    m = MSG[lang]
    state = os.path.join(rv, STATE)
    st = json.load(open(state)) if os.path.exists(state) else {}

    if a.stop:
        if st.get("pid") and alive(st["pid"]):
            os.kill(st["pid"], signal.SIGTERM)
            print(m["stopped"].format(url=st.get("url")))
        else:
            print(m["not_running"])
        if os.path.exists(state):
            os.remove(state)
        return
    if not os.path.isfile(os.path.join(rv, "index.html")):
        sys.exit(m["no_index"].format(rv=rv))
    if st.get("pid") and alive(st["pid"]):
        print(m["running"].format(url=st["url"], cmd=sys.argv[0], project=a.project))
        if not a.no_open:
            open_browser(st["url"], lang)
        return

    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", a.port), make_handler(rv))
    url = f"http://127.0.0.1:{httpd.server_address[1]}/index.html"
    json.dump({"pid": os.getpid(), "url": url}, open(state, "w"))
    print(m["page"].format(url=url), flush=True)
    print(m["store"].format(path=os.path.join(rv, STORE)), flush=True)
    print(m["stop_hint"].format(cmd=sys.argv[0], project=a.project), flush=True)
    if not a.no_open:
        open_browser(url, lang)

    def bye(*_):
        threading.Thread(target=httpd.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, bye)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        try:
            if json.load(open(state)).get("pid") == os.getpid():
                os.remove(state)
        except (FileNotFoundError, json.JSONDecodeError):
            pass


if __name__ == "__main__":
    main()
