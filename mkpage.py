#!/usr/bin/env python3
"""Render a cycler's page from its OWN workflow. No template with a noun slot."""
import json, os, re, subprocess, sys, tempfile

def workflow(cid):
    js = """import {WORKFLOWS} from '%s/workflows.js';
console.log(JSON.stringify(WORKFLOWS['%s']));""" % (os.path.dirname(os.path.abspath(__file__)), cid)
    f = tempfile.NamedTemporaryFile('w', suffix='.mjs', delete=False); f.write(js); f.close()
    out = subprocess.run(['node', f.name], capture_output=True, text=True)
    os.unlink(f.name)
    if out.returncode: sys.exit(out.stderr)
    return json.loads(out.stdout)

def render(cid, repo, doi=None, ai=None):
    w = workflow(cid)
    e = lambda t: str(t).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
    li = lambda xs: ''.join('<li>%s</li>' % e(x) for x in xs)
    steps = ''.join(
        '<li><b>%s</b><span>%s</span>%s</li>'
        % (e(s['id']), e(s['ask']),
           '<em>%s</em>' % ('answered by hand' if s.get('human')
                            else 'brings back a file' if s.get('binary') else 'optional')
           if (s.get('human') or s.get('binary') or s.get('optional')) else '')
        for s in w['workflow'])
    tabs = ''.join('<a href="%s" rel="noopener nofollow">%s</a>' % (e(x['url']), e(x['name']))
                   for x in (ai or {}).get('open_in_a_tab', []))
    badge = ('<a class=doi href="https://doi.org/%s">%s</a>' % (doi, doi)) if doi else '<span class=doi>not yet minted</span>'
    return """<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>%(id)s — the %(room)s</title>
<meta name=description content="%(purpose)s">
<style>
:root{--ink:#0c0f14;--paper:#e7ecef;--dim:rgba(231,236,239,.55);--rule:rgba(231,236,239,.13);
--acc:#c8a44a;--warn:#b8543f;--ok:#5ea88a;
--disp:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;--body:Georgia,serif;
--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
*{box-sizing:border-box}body{margin:0;background:var(--ink);color:var(--paper);font:17px/1.65 var(--body)}
.wrap{max-width:64rem;margin:0 auto;padding:0 1.4rem}a{color:var(--paper);text-decoration-color:var(--acc)}
:focus-visible{outline:2px solid var(--acc);outline-offset:3px}
header{padding:4.5rem 0 3rem;border-bottom:1px solid var(--rule)}
.spec{display:flex;align-items:flex-end;gap:1.2rem;flex-wrap:wrap}
h1{font-family:var(--disp);font-size:clamp(3.4rem,12vw,7rem);line-height:.82;letter-spacing:-.05em;margin:0;font-weight:400}
.ar{font-size:clamp(1.4rem,4vw,2.4rem);color:var(--acc);padding-bottom:.5rem}
.line{display:flex;gap:1rem;flex-wrap:wrap;border-top:1px solid var(--rule);padding-top:.7rem;margin-top:1.2rem;
font:500 .66rem/1 var(--mono);letter-spacing:.2em;text-transform:uppercase;color:var(--dim)}
.line .doi{color:var(--acc);text-transform:none;letter-spacing:.04em}
.purpose{font-family:var(--disp);font-size:clamp(1.2rem,2.5vw,1.6rem);line-height:1.4;max-width:44ch;margin:1.8rem 0 0}
.contract{border-left:3px solid var(--warn);padding-left:1rem;margin:1.6rem 0 0;color:var(--dim);max-width:56ch}
section{padding:3.5rem 0;border-bottom:1px solid var(--rule)}
.eyebrow{font:600 .64rem/1 var(--mono);letter-spacing:.26em;text-transform:uppercase;color:var(--acc);margin:0 0 .7rem}
h2{font-family:var(--disp);font-size:clamp(1.6rem,3.4vw,2.3rem);font-weight:400;margin:0 0 1.2rem;letter-spacing:-.02em}
ol.steps{list-style:none;counter-reset:s;padding:0;margin:0}
ol.steps li{counter-increment:s;padding:.9rem 0 .9rem 3rem;border-bottom:1px solid var(--rule);position:relative}
ol.steps li::before{content:counter(s);position:absolute;left:0;top:1rem;width:1.9rem;text-align:center;
font:600 .68rem/1.7rem var(--mono);color:var(--acc);border:1px solid var(--rule)}
ol.steps b{font:600 .64rem/1 var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--dim);display:block;margin-bottom:.25rem}
ol.steps span{font-family:var(--disp);font-size:1.1rem}
ol.steps em{font-style:normal;font:.62rem/1 var(--mono);letter-spacing:.1em;text-transform:uppercase;
color:var(--acc);border:1px solid var(--rule);padding:.2rem .4rem;margin-left:.5rem;white-space:nowrap}
.cols{display:grid;gap:2rem}@media(min-width:50rem){.cols{grid-template-columns:1fr 1fr}}
h3{font:600 .66rem/1 var(--mono);letter-spacing:.16em;text-transform:uppercase;color:var(--acc);margin:0 0 .5rem}
ul.p{list-style:none;padding:0;margin:0 0 1.6rem}ul.p li{padding:.35rem 0;color:var(--dim);border-bottom:1px solid rgba(231,236,239,.05)}
ul.p.warn li{color:var(--paper)}ul.p.warn li::before{content:"× ";color:var(--warn)}
ul.p.inv li::before{content:"✓ ";color:var(--ok)}
.ais{display:flex;gap:.5rem;flex-wrap:wrap;margin:.8rem 0 0}
.ais a{font:600 .68rem/1 var(--mono);letter-spacing:.08em;border:1px solid var(--rule);padding:.55rem .8rem;
text-decoration:none;color:var(--acc)}
.ais a:hover{border-color:var(--acc)}
pre{background:#080a0e;border:1px solid var(--rule);border-left:3px solid var(--acc);padding:1rem;
overflow-x:auto;font:13px/1.8 var(--mono);margin:1rem 0 0}
footer{padding:2.5rem 0 4rem;color:var(--dim);font-size:.85rem}
</style></head><body><div class=wrap>

<header><div class=spec><h1>%(id)s</h1><span class=ar>%(script)s</span></div>
<div class=line><span>the %(room)s</span><span>%(output)s</span>%(badge)s</div>
<p class=purpose>%(purpose)s</p>
<p class=contract>%(contract)s</p></header>

<section><p class=eyebrow>The workflow</p>
<h2>What it asks you, in order.</h2>
<p style="color:var(--dim);max-width:56ch;margin:0 0 1.4rem">These questions are this room's own. The
cycling mechanism is shared with the other rooms; the questions are not, because the work is not.</p>
<ol class=steps>%(steps)s</ol></section>

<section><p class=eyebrow>Which AI</p>
<h2>Yours. Or none.</h2>
<p style="color:var(--dim);max-width:56ch">The cycler is not an AI provider. It puts a question on
your clipboard and takes an answer back. Links below come from <code>ai.config.json</code> — edit it,
add to it, delete from it. The list is alphabetical, not a ranking, and a server on your own machine
or your own typing works exactly as well.</p>
<div class=ais>%(tabs)s</div></section>

<section><div class=cols>
<div><h3>What it must know first</h3><ul class=p>%(context)s</ul>
<h3>What it holds between steps</h3><ul class=p>%(state)s</ul>
<h3>What comes out</h3><ul class=p><li>%(artifact)s</li></ul></div>
<div><h3>What must never stop being true</h3><ul class="p inv">%(invariants)s</ul>
<h3>How it goes wrong</h3><ul class="p warn">%(failures)s</ul>
<h3>What it needs before it will publish</h3><ul class=p>%(evidence)s</ul></div>
</div></section>

<section><p class=eyebrow>Run it</p><h2>On your own machine.</h2>
<pre>curl -O https://raw.githubusercontent.com/%(repo)s/main/zcycler.py
ZCYCLER_MODEL=%(id)s python3 zcycler.py serve</pre></section>

<footer><p>Copyright © 1993–2026 Abhishek Choudhary · AyeAI · ORCID 0009-0002-0684-8320 ·
Apache-2.0 · <a href="https://github.com/%(repo)s">source</a></p>
<p><em>Kaivalyik Immutabilis</em></p>
<p>Where anything in this repository names a repository, a DOI or a figure that does not exist, the
canon in <code>zistgah/governance</code> governs. The artwork records intent; the contract records fact.</p>
</footer></div></body></html>""" % dict(
    id=e(w['id']), script=w['script'], room=e(w['room']), output=e(w['output']),
    purpose=e(w['purpose']), contract=e(w['contract']), artifact=e(w['artifact']),
    steps=steps, tabs=tabs, badge=badge, repo=e(repo),
    context=li(w['context']), state=li(w['state']), invariants=li(w['invariants']),
    failures=li(w['failures']), evidence=li(w['evidence']))

if __name__ == '__main__':
    cid, repo = sys.argv[1], sys.argv[2]
    doi = sys.argv[3] if len(sys.argv) > 3 else None
    here = os.path.dirname(os.path.abspath(__file__))
    ai = json.load(open(os.path.join(here, 'ai.config.json')))
    out = os.path.join(os.getcwd(), 'docs'); os.makedirs(out, exist_ok=True)
    p = os.path.join(out, 'index.html')
    open(p, 'w').write(render(cid, repo, doi, ai))
    print("docs/index.html written from %s's OWN workflow (%d bytes)" % (cid, os.path.getsize(p)))
