/* cycler.js — the creativity cycle, done properly.
 *
 * What was wrong before: it was a form. You copied a prompt, went away, came back, found the right
 * textarea, pasted, pressed a button. Four decisions per step.
 *
 * What it is now: one button. It reads your clipboard itself, works out which step the answer
 * belongs to, files it, and copies the next prompt — so the whole loop is
 *
 *     click → paste into your AI → copy → click
 *
 * and nothing else. If the browser will not hand over the clipboard, the same button falls back to
 * a paste target; it never dead-ends.
 *
 * Endpoints are SHAPES, not providers. Nothing here names or defaults to any company's service,
 * and the shipped presets are the two request shapes a local server on your own machine speaks.
 */

/* ── endpoint shapes. A local server needs no key and leaves your machine at no point. ── */
export const SHAPES = [
  { id: 'local-chat', label: 'Local server · chat-completions shape',
    url: 'http://localhost:8080/v1/chat/completions', keyless: true, local: true,
    body: '{"model":"{model}","messages":[{"role":"user","content":"{prompt}"}],"stream":false}',
    reply: 'choices.0.message.content', model: 'local-model' },
  { id: 'local-gen', label: 'Local server · single-generate shape',
    url: 'http://localhost:11434/api/generate', keyless: true, local: true,
    body: '{"model":"{model}","prompt":"{prompt}","stream":false}',
    reply: 'response', model: 'local-model' },
  { id: 'remote-chat', label: 'Remote service · chat-completions shape (your key)',
    url: '', keyless: false, local: false,
    body: '{"model":"{model}","messages":[{"role":"user","content":"{prompt}"}]}',
    reply: 'choices.0.message.content', model: '' },
  { id: 'custom', label: 'Something else — describe it yourself',
    url: '', keyless: false, local: false, body: '{"prompt":"{prompt}"}', reply: 'text', model: '' }
];

export function shape(id) { return SHAPES.find(s => s.id === id) || SHAPES[3]; }

export function dig(obj, path) {
  return String(path || '').split('.').reduce(
    (o, k) => (o == null ? o : o[/^\d+$/.test(k) ? Number(k) : k]), obj);
}

/** Build the request without sending it — so a test can check the shape, and so can the operator. */
export function request(cfg, prompt) {
  if (!cfg || !cfg.url) throw new Error('No endpoint set. Use copy-and-paste, or point this at a server on your machine.');
  const body = (cfg.body || '{"prompt":"{prompt}"}')
    .replace('"{prompt}"', JSON.stringify(prompt))
    .replace('{model}', cfg.model || '');
  let parsed; try { parsed = JSON.parse(body); }
  catch (e) { throw new Error('The request body is not valid JSON once the prompt is put in.'); }
  const headers = { 'content-type': 'application/json' };
  if (cfg.key) headers.authorization = 'Bearer ' + cfg.key;
  return { url: cfg.url, method: 'POST', headers, body: parsed };
}

export async function ask(cfg, prompt, fetcher) {
  const r = request(cfg, prompt);
  const f = fetcher || fetch;
  let res;
  try { res = await f(r.url, { method: 'POST', headers: r.headers, body: JSON.stringify(r.body) }); }
  catch (e) {
    throw new Error(cfg.local
      ? 'No answer from ' + r.url + '. Is the server running on this machine? Copy-and-paste still works.'
      : 'Could not reach ' + r.url + '. Copy-and-paste still works.');
  }
  if (!res.ok) throw new Error('The endpoint answered ' + res.status + '. Copy-and-paste still works.');
  const j = await res.json();
  const v = dig(j, cfg.reply || 'text');
  if (typeof v !== 'string')
    throw new Error('Nothing found at "' + (cfg.reply || 'text') + '". Check where the reply lives in the response.');
  return v;
}

/* ── reading an answer ────────────────────────────────────────────────────
 * The answer arrives from a clipboard, so it is whatever the AI wrote plus whatever the human
 * selected. Be generous about the wrapping and strict about the content.
 */
export function unwrap(text) {
  let t = String(text == null ? '' : text).replace(/\r/g, '').trim();
  const fence = t.match(/^```[a-z]*\n([\s\S]*?)\n?```$/i);
  if (fence) t = fence[1].trim();
  return t;
}

export function asJson(text) {
  const t = unwrap(text);
  const a = t.indexOf('['), o = t.indexOf('{');
  if (a === -1 && o === -1) return null;
  const start = (a !== -1 && (o === -1 || a < o)) ? a : o;
  const end = Math.max(t.lastIndexOf(']'), t.lastIndexOf('}'));
  if (end <= start) return null;
  try { return JSON.parse(t.slice(start, end + 1)); } catch (e) { return null; }
}

/** Which step does this answer belong to? The point of click-and-go: the operator does not say. */
export function route(text, steps, current) {
  const t = unwrap(text);
  if (!t) return { step: null, why: 'The clipboard is empty.' };
  const j = asJson(t);
  if (j) {
    for (const s of steps) {
      if (!s.jsonKeys) continue;
      const probe = Array.isArray(j) ? j[0] : j;
      // ALL keys must be present: the distinguishing one is what separates the steps.
      if (probe && typeof probe === 'object' && s.jsonKeys.every(k => k in probe)) {
        if (Array.isArray(j) && !s.array) continue;
        return { step: s, value: j };
      }
    }
  }
  if (current && !current.jsonKeys) return { step: current, value: t };
  const prose = steps.find(s => !s.jsonKeys);
  if (prose) return { step: prose, value: t };
  return { step: null, why: 'That does not match any step. It is not JSON any step expects, and no prose step is open.' };
}

/* ── the queue ────────────────────────────────────────────────────────────
 * A flat list of (subject, step) pairs so progress is countable and the next prompt is never a
 * guess. Subjects are shots, plates, tracks — whatever the tool is composing.
 */
export function queue(subjects, steps, book) {
  const q = [];
  for (const st of steps) {
    if (st.optional) continue;
    if (st.once) { if (!dig(book, st.target.replace(/^@/, ''))) q.push({ step: st, subject: null }); continue; }
    for (const s of subjects) if (!s[st.target]) q.push({ step: st, subject: s });
  }
  return q;
}

export function fill(tpl, ctx) {
  return String(tpl).replace(/\{(\w+(?:\.\w+)*)\}/g, (_, k) => {
    const v = dig(ctx, k); return v == null ? '' : String(v);
  }).trim();
}

/** Apply a routed answer. Returns {ok, added, note} and never throws at the operator. */
export function apply(text, task, state, steps) {
  const r = route(text, steps, task && task.step);
  if (!r.step) return { ok: false, why: r.why };
  const step = r.step;
  const subject = (task && task.subject && task.step && task.step.id === step.id)
    ? task.subject
    : (state.subjects.find(s => !s[step.target]) || (task && task.subject));

  if (step.array) {
    let arr = Array.isArray(r.value) ? r.value : [r.value];
    if (!arr.length || typeof arr[0] !== 'object') return { ok: false, why: 'Expected a JSON array of objects.' };
    if (!subject) return { ok: false, why: 'Nothing left to expand.' };
    const at = state.subjects.indexOf(subject), made = [];
    arr.forEach((o, i) => {
      const s = i === 0 ? subject : { ...subject, id: subject.id + '-' + (i + 1), derivedFrom: subject.id, part: subject.part };
      Object.assign(s, o);
      if (i > 0) made.push(s);
    });
    made.forEach((s, i) => state.subjects.splice(at + 1 + i, 0, s));
    return { ok: true, added: made.length, note: 'expanded into ' + arr.length };
  }
  if (step.jsonKeys) {
    const o = Array.isArray(r.value) ? r.value[0] : r.value;
    if (!o || typeof o !== 'object') return { ok: false, why: 'Expected a JSON object.' };
    if (!subject) return { ok: false, why: 'Nothing left needs this.' };
    Object.assign(subject, o);
    return { ok: true, added: 0 };
  }
  if (step.once) { const k = step.target.replace(/^@/, ''); state.book[k] = r.value; return { ok: true, added: 0 }; }
  if (!subject) return { ok: false, why: 'Nothing left needs this.' };
  subject[step.target] = r.value;
  return { ok: true, added: 0 };
}

export function progress(state, steps) {
  const q = queue(state.subjects, steps, state.book);
  const total = steps.filter(s => !s.optional)
    .reduce((n, s) => n + (s.once ? 1 : state.subjects.length), 0);
  return { left: q.length, total, done: total - q.length,
           pct: total ? Math.round((total - q.length) * 100 / total) : 0 };
}

/* ── clipboard, with an honest fallback ─────────────────────────────────── */
export async function readClipboard(nav) {
  const n = nav || (typeof navigator !== 'undefined' ? navigator : null);
  if (!n || !n.clipboard || !n.clipboard.readText)
    throw new Error('no-clipboard-api');
  const t = await n.clipboard.readText();
  if (!t || !t.trim()) throw new Error('clipboard-empty');
  return t;
}

export async function writeClipboard(text, nav) {
  const n = nav || (typeof navigator !== 'undefined' ? navigator : null);
  if (!n || !n.clipboard || !n.clipboard.writeText) throw new Error('no-clipboard-api');
  await n.clipboard.writeText(text);
  return true;
}
