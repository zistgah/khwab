#!/usr/bin/env python3
"""khwab (خواب) — the dream. The creativity cycle for moving pictures.

    python3 khwab.py serve                    # cutting room at http://127.0.0.1:8711
    python3 khwab.py import <slug> pay.zip    # bring a studio export into a local project
    python3 khwab.py build  <slug>            # seeder + tarball
    python3 khwab.py run    <slug> stage|push|mint

Same engine as the press: it drives git, gh and misty rather than reimplementing them, and the
deployment carries the kitab plumbing so a reel reads in the same reader as every other book.
"""
import json, os, re, shutil, subprocess, sys, threading, io, time, zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

VERSION = "1.0.0"
HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.abspath(os.environ.get("KHWAB_HOME", os.path.join(os.getcwd(), "khwab-projects")))
KIND = os.environ.get("KHWAB_KIND", "video")          # awaz sets audio
MEDIA_EXT = {"video": (".mp4", ".webm", ".mov", ".m4v"),
             "audio": (".mp3", ".m4a", ".wav", ".ogg", ".flac")}


def pdir(s): return os.path.join(HOME, s)
def load(s):
    p = os.path.join(pdir(s), "project.json")
    if not os.path.exists(p): raise SystemExit("no such project: " + s)
    return json.load(open(p))
def save(p):
    os.makedirs(pdir(p["slug"]), exist_ok=True)
    json.dump(p, open(os.path.join(pdir(p["slug"]), "project.json"), "w"), indent=2, ensure_ascii=False)
    return p
def projects():
    if not os.path.isdir(HOME): return []
    out = []
    for s in sorted(os.listdir(HOME)):
        f = os.path.join(HOME, s, "project.json")
        if os.path.exists(f):
            try: out.append(json.load(open(f)))
            except Exception: pass
    return out


def cmd_import(slug, zip_path):
    d = pdir(slug); os.makedirs(os.path.join(d, "payload"), exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        if "project.json" not in names: raise SystemExit("not a cutting-room payload")
        t = json.loads(z.read("project.json"))
        prj = {"slug": slug, "kind": t.get("kind", KIND), "book": t.get("book", {}),
               "subjects": t.get("subjects", []),
               "repo": t.get("book", {}).get("repo") or ("zistgah/" + slug)}
        save(prj)
        n = 0
        for nm in names:
            if nm.startswith("payload/") and not nm.endswith("/"):
                out = os.path.join(d, nm)
                os.makedirs(os.path.dirname(out), exist_ok=True)
                open(out, "wb").write(z.read(nm)); n += 1
    return {"slug": slug, "files": n, "shots": len(prj["subjects"]),
            "doctor": doctor(prj)}


def doctor(prj):
    f, b = [], prj.get("book", {})
    if not b.get("title"): f.append("no title")
    if not b.get("description"): f.append("no abstract — a blank deposit abstract is permanent too")
    if not re.match(r"^[^/\s]+/[^/\s]+$", b.get("repo") or ""): f.append("repo must be owner/name")
    if not b.get("reel"): f.append("no media file recorded")
    if not prj.get("subjects"): f.append("no shots")
    for i, s in enumerate(prj.get("subjects", []), 1):
        if not s.get("title"): f.append("shot %d has no title" % i)
        if not s.get("lead"): f.append("shot %d has no description" % i)
    pay = os.path.join(pdir(prj["slug"]), "payload")
    if not os.path.exists(os.path.join(pay, "book.config.json")): f.append("payload not imported")
    med = os.path.join(pay, "assets", b.get("reel") or "")
    if b.get("reel") and not os.path.exists(med): f.append("the media file is not in the payload")
    return f


def cmd_build(slug):
    prj = load(slug); d = pdir(slug)
    fails = doctor(prj)
    if fails: return {"ok": False, "doctor": fails}
    env = re.sub(r"[^A-Z0-9]", "_", slug.upper())
    tmpl = open(os.path.join(HERE, "seed.tmpl.sh")).read()
    n = len(prj["subjects"])
    seeder = tmpl.replace("@@SLUG@@", slug).replace("@@REPO@@", prj["repo"]) \
                 .replace("@@ENV@@", env).replace("@@VERSION@@", VERSION) \
                 .replace("@@TITLE@@", (prj["book"].get("title") or slug).replace('"', "'")) \
                 .replace("@@NCHAP@@", str(n)).replace("@@KIND@@", prj.get("kind", KIND)) \
                 .replace("@@MEDIA@@", prj["book"].get("reel") or "")
    sp = os.path.join(d, "seed_%s.sh" % slug)
    open(sp, "w").write(seeder); os.chmod(sp, 0o755)
    rc = subprocess.run(["bash", "-n", sp], capture_output=True, text=True)
    if rc.returncode: return {"ok": False, "doctor": ["seeder does not parse: " + rc.stderr.strip()]}
    # metadata for the mint
    b = prj["book"]
    misty = {"upload_type": "video" if prj.get("kind") == "video" else "sound",
             "title": b.get("title", slug) + ((": " + b["subtitle"]) if b.get("subtitle") else ""),
             "creators": [{"name": b.get("author", "Choudhary, Abhishek"),
                           "affiliation": b.get("affiliation", "AyeAI"),
                           "orcid": b.get("orcid", "0009-0002-0684-8320")}],
             "description": b.get("description", ""), "keywords": b.get("keywords", []),
             "license": (b.get("license") or "CC-BY-SA-4.0").lower(), "language": "eng",
             "related_identifiers": b.get("related", [])}
    os.makedirs(os.path.join(d, "metadata"), exist_ok=True)
    json.dump(misty, open(os.path.join(d, "metadata", "misty.json"), "w"), indent=2, ensure_ascii=False)
    stage = os.path.join(d, "_pack", slug)
    shutil.rmtree(os.path.join(d, "_pack"), ignore_errors=True); os.makedirs(stage)
    for sub in ("payload", "metadata", "overlays"):
        if os.path.isdir(os.path.join(d, sub)): shutil.copytree(os.path.join(d, sub), os.path.join(stage, sub))
    shutil.copy2(sp, stage)
    tar = os.path.join(d, "%s.tar" % slug)
    subprocess.run(["tar", "--format=ustar", "-cf", tar, slug], cwd=os.path.join(d, "_pack"), check=True)
    shutil.rmtree(os.path.join(d, "_pack"), ignore_errors=True)
    return {"ok": True, "shots": n, "seeder": sp, "tar": tar}


def cmd_run(slug, stage, word=None, override=False):
    prj = load(slug); d = pdir(slug)
    sp = os.path.join(d, "seed_%s.sh" % slug)
    if not os.path.exists(sp): raise SystemExit("build first")
    args = []
    if stage == "push": args = ["--push"]
    elif stage == "mint":
        args = ["--mint"] + (["--override-rehearsal"] if override else [])
    work = os.path.join(d, "work"); os.makedirs(work, exist_ok=True)
    shutil.copy2(sp, work); shutil.copy2(os.path.join(d, "%s.tar" % slug), work)
    p = subprocess.Popen(["bash", os.path.basename(sp)] + args, cwd=work,
                         stdin=subprocess.PIPE if word else None,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    if word:
        p.stdin.write(word + "\n")
        if stage == "mint": p.stdin.write("MINT %s\n" % slug)
        p.stdin.close()
    return p


INBOX_MAX = 400

def inbox_roots():
    """Likely places, discovered — never a hardcoded path. The operator picks."""
    h = os.path.expanduser("~")
    names = ["Downloads", "Download", "Descargas", "Téléchargements", "Downloads/AI",
             "Desktop", "Documents", "Pictures", "Movies", "Videos", "Music"]
    out = []
    for n in names:
        p = os.path.join(h, n)
        if os.path.isdir(p): out.append(p)
    for p in (h, os.getcwd()):
        if os.path.isdir(p) and p not in out: out.append(p)
    return out


def inbox_list(d=None):
    roots = inbox_roots()
    d = os.path.abspath(os.path.expanduser(d)) if d else (roots[0] if roots else os.getcwd())
    if not os.path.isdir(d): return {"error": "not a folder: " + d, "roots": roots}
    files = []
    try: names = os.listdir(d)
    except PermissionError: return {"error": "no permission to read " + d, "roots": roots, "dir": d}
    for n in sorted(names):
        p = os.path.join(d, n)
        if n.startswith(".") or not os.path.isfile(p): continue
        try: st = os.stat(p)
        except OSError: continue
        ext = n.rsplit(".", 1)[-1].lower() if "." in n else ""
        files.append({"name": n, "size": st.st_size, "modified": int(st.st_mtime * 1000),
                      "type": _mime(ext), "path": p})
    files.sort(key=lambda f: -f["modified"])
    return {"dir": d, "roots": roots, "files": files[:INBOX_MAX],
            "truncated": len(files) > INBOX_MAX}


def _mime(ext):
    for pre, exts in (("image/", "png jpg jpeg webp gif svg avif"),
                      ("video/", "mp4 webm mov m4v mkv"),
                      ("audio/", "mp3 m4a wav ogg flac aac opus")):
        if ext in exts.split(): return pre + ext
    return {"pdf": "application/pdf", "json": "application/json"}.get(ext, "")


def _f(name):
    return os.path.join(HERE, "docs", name)


class H(BaseHTTPRequestHandler):
    runs = {}
    def _s(self, o, code=200, ct="application/json"):
        b = o if isinstance(o, bytes) else (o if isinstance(o, str) else json.dumps(o)).encode()
        self.send_response(code); self.send_header("Content-Type", ct)
        # the studio may be served from Pages while the server runs here; loopback only
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def log_message(self, *a): pass
    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        served = {"/": "index.html", "/index.html": "index.html",
                  "/studio": "studio.html", "/studio.html": "studio.html"}
        if u.path in served:
            f = _f(served[u.path])
            if os.path.exists(f): return self._s(open(f, "rb").read(), ct="text/html; charset=utf-8")
            return self._s("<p>docs/ is not beside khwab.py</p>", 404, "text/html")
        if u.path.startswith("/js/") and u.path.endswith(".js"):
            f = _f(os.path.join("js", os.path.basename(u.path)))
            if os.path.exists(f): return self._s(open(f, "rb").read(), ct="text/javascript; charset=utf-8")
            return self._s("// not found", 404, "text/javascript")
        if u.path == "/api/inbox":
            return self._s(inbox_list(q.get("dir", [None])[0]))
        if u.path == "/api/inbox/file":
            p = q.get("path", [""])[0]
            if not p or not os.path.isfile(p): return self._s({"error": "no such file"}, 404)
            ext = p.rsplit(".", 1)[-1].lower() if "." in p else ""
            return self._s(open(p, "rb").read(), ct=_mime(ext) or "application/octet-stream")
        if u.path == "/api/projects": return self._s({"version": VERSION, "home": HOME, "kind": KIND,
                                                      "projects": projects()})
        if u.path == "/api/project":
            p = load(q["slug"][0]); return self._s({"project": p, "doctor": doctor(p), "dir": pdir(p["slug"])})
        if u.path == "/api/log":
            r = self.runs.get(q["slug"][0])
            if not r: return self._s({"log": "", "running": False})
            return self._s({"log": r["buf"].getvalue(), "running": r["proc"].poll() is None})
        return self._s({"error": "not found"}, 404)
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.end_headers()
    def do_POST(self):
        u = urlparse(self.path)
        b = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or "{}")
        try:
            if u.path == "/api/build": return self._s(cmd_build(b["slug"]))
            if u.path == "/api/run":
                s = b["slug"]; old = self.runs.get(s)
                if old and old["proc"].poll() is None: return self._s({"error": "already running"}, 409)
                p = cmd_run(s, b["stage"], b.get("word"), b.get("override"))
                buf = io.StringIO(); self.runs[s] = {"proc": p, "buf": buf}
                threading.Thread(target=lambda: [buf.write(l) for l in p.stdout], daemon=True).start()
                return self._s({"started": True})
        except SystemExit as e: return self._s({"error": str(e)}, 400)
        except Exception as e: return self._s({"error": "%s: %s" % (type(e).__name__, e)}, 500)
        return self._s({"error": "not found"}, 404)


def serve(port=8711):
    os.makedirs(HOME, exist_ok=True)
    print("khwab %s — http://127.0.0.1:%d   projects: %s" % (VERSION, port, HOME))
    print("cutting room: http://127.0.0.1:%d/studio" % port)
    print("artefact inbox: %s" % (inbox_roots()[0] if inbox_roots() else os.getcwd()))
    print("Nothing pushes or mints without you typing the gate word.")
    try: ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
    except KeyboardInterrupt: print("\nstopped.")


def main(a):
    if len(a) < 2: print(__doc__); return 0
    c = a[1]
    if c == "serve": return serve(int(a[2]) if len(a) > 2 else 8711)
    if c == "import": print(json.dumps(cmd_import(a[2], a[3]), indent=2)); return 0
    if c == "doctor":
        f = doctor(load(a[2])); print("\n".join("FAIL " + x for x in f) if f else "no failures")
        return 1 if f else 0
    if c == "build":
        r = cmd_build(a[2]); print(json.dumps(r, indent=2)); return 0 if r["ok"] else 1
    if c == "run":
        p = cmd_run(a[2], a[3], override="--override-rehearsal" in a)
        for line in p.stdout: sys.stdout.write(line)
        return p.wait()
    print("unknown command: " + c); return 2


if __name__ == "__main__":
    try: rc = main(sys.argv)
    except BrokenPipeError:
        try: sys.stdout.close()
        except Exception: pass
        os._exit(0)
    except KeyboardInterrupt: print(); rc = 130
    try: sys.stdout.flush()
    except BrokenPipeError: os._exit(rc or 0)
    sys.exit(rc)
