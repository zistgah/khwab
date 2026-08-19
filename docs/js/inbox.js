/* inbox.js — the Local Artefact Inbox, and the AI source table.
 *
 * Text comes back on the clipboard. An image, a reel, a track, a mesh does not: the operator saves
 * it out of whichever AI they used and comes back. That return is a first-class step here, not an
 * afterthought.
 *
 * Three mechanisms, because no single one works everywhere:
 *
 *     File System Access  │  File Picker  │  Local Endpoint
 *     (desktop Chromium)     (everywhere)    (khwab serve)
 *
 * and one interaction across all three:
 *
 *     Detect → Present → the operator selects → Import → Continue
 *
 * The rule that governs the whole module: FILESYSTEM VISIBILITY IS NOT PROVENANCE. A folder holds
 * photographs, documents, other AIs' output and files a different process wrote. We may say "three
 * new files are visible". We may never say "three files your AI generated". The operator says which
 * artefact belongs to this step, always.
 */

/* ── AI sources ───────────────────────────────────────────────────────────
 * Shipped EMPTY. No service is named, defaulted to or suggested — the operator adds the ones they
 * use. Seeding must not be limited to any one AI; that is the invariance clause, made concrete.
 */
export const SOURCE_KINDS = [
  { id: 'compose', label: 'Open in a tab', needs: ['url'],
    hint: 'The address of the AI you use. The prompt is copied and the tab opens; you paste, generate, save the file, and come back.' },
  { id: 'endpoint', label: 'Call an address', needs: ['url', 'reply'],
    hint: 'Answers in place. Text only — a binary artefact still comes back through the inbox.' },
  { id: 'local', label: 'A server on this machine', needs: ['url', 'reply'],
    hint: 'Keyless. Nothing leaves the machine.' }
];

export function loadSources(store) {
  try { const v = JSON.parse((store || localStorage).getItem('zistgah.sources') || '[]');
        return Array.isArray(v) ? v : []; } catch (e) { return []; }
}
export function saveSources(list, store) {
  try { (store || localStorage).setItem('zistgah.sources', JSON.stringify(list)); return true; }
  catch (e) { return false; }
}
export function addSource(list, s) {
  if (!s || !s.name || !s.name.trim()) return { ok: false, why: 'Give it a name.' };
  if (!s.kind || !SOURCE_KINDS.some(k => k.id === s.kind)) return { ok: false, why: 'Choose how it is reached.' };
  if (!s.url || !/^https?:\/\//i.test(s.url)) return { ok: false, why: 'The address must start with http:// or https://.' };
  if (list.some(x => x.name.toLowerCase() === s.name.trim().toLowerCase()))
    return { ok: false, why: 'You already have one by that name.' };
  return { ok: true, list: list.concat([{ ...s, name: s.name.trim(), id: 'src-' + Date.now() }]) };
}

/** Open a compose-style source. The prompt goes to the clipboard; the tab is the operator's. */
export async function openWith(src, prompt, deps) {
  const d = deps || {};
  const clip = d.writeClipboard || (async t => navigator.clipboard.writeText(t));
  const open = d.open || ((u) => window.open(u, '_blank', 'noopener'));
  let copied = true;
  try { await clip(prompt); } catch (e) { copied = false; }
  const u = src.url.includes('{prompt}')
    ? src.url.replace('{prompt}', encodeURIComponent(prompt))
    : src.url;
  open(u);
  return { copied, url: u,
    note: copied ? 'Prompt copied. Paste it there, generate, save the file, then come back.'
                 : 'Could not copy — the prompt is shown below; copy it by hand.' };
}

/* ── what a step expects ─────────────────────────────────────────────────── */
export const ACCEPTS = {
  text:  { label: 'Text',  ext: [], mime: [] },
  image: { label: 'Image', ext: ['png','jpg','jpeg','webp','gif','svg','avif'], mime: ['image/'] },
  audio: { label: 'Audio', ext: ['mp3','m4a','wav','ogg','flac','aac','opus'],  mime: ['audio/'] },
  video: { label: 'Video', ext: ['mp4','webm','mov','m4v','mkv'],               mime: ['video/'] },
  model: { label: '3D',    ext: ['glb','gltf','obj','stl','ply','usdz'],        mime: [] },
  doc:   { label: 'PDF',   ext: ['pdf'],                                        mime: ['application/pdf'] },
  data:  { label: 'Data',  ext: ['json','csv','tsv','yaml','yml'],              mime: [] },
  any:   { label: 'Any',   ext: [], mime: [] }
};

export function matches(file, expect) {
  const a = ACCEPTS[expect] || ACCEPTS.any;
  if (expect === 'any' || (!a.ext.length && !a.mime.length)) return true;
  const ext = (file.name.split('.').pop() || '').toLowerCase();
  if (a.ext.includes(ext)) return true;
  return a.mime.some(m => (file.type || '').startsWith(m));
}

/* ── the inbox ────────────────────────────────────────────────────────────
 * `listing` is whatever a mechanism produced: [{name, size, modified, type, handle|file|path}].
 * Everything below is pure, so the same logic serves all three mechanisms and can be tested.
 */
export function newSince(baseline, listing) {
  const b = new Map((baseline || []).map(f => [f.name, f.size + ':' + (f.modified || 0)]));
  return listing.filter(f => {
    const k = b.get(f.name);
    return k === undefined || k !== (f.size + ':' + (f.modified || 0));
  });
}

/** What the panel shows. Never asserts where a file came from. */
export function present(listing, opts) {
  const o = opts || {};
  const expect = o.expect || 'any';
  const baseline = o.baseline || null;
  const fresh = baseline ? newSince(baseline, listing) : [];
  const freshNames = new Set(fresh.map(f => f.name));
  let rows = listing.map(f => ({
    ...f,
    fits: matches(f, expect),
    fresh: freshNames.has(f.name)
  }));
  if (o.onlyFitting) rows = rows.filter(r => r.fits);
  const sort = o.sort || 'modified';
  rows.sort((a, b) => sort === 'name' ? a.name.localeCompare(b.name, undefined, { numeric: true })
    : sort === 'size' ? (b.size || 0) - (a.size || 0)
    : (b.modified || 0) - (a.modified || 0));
  const n = fresh.length;
  return {
    rows,
    counts: { total: listing.length, fitting: rows.filter(r => r.fits).length, fresh: n },
    // Wording is load-bearing: visible, not generated. We do not know who wrote these.
    notice: baseline === null ? null
      : n === 0 ? 'No new files are visible since you left.'
      : n + (n === 1 ? ' new file is visible' : ' new files are visible') +
        ' — pick the one that belongs to this step.'
  };
}

/** Nothing enters the work without this call. */
export function importSelection(selected, task, expect) {
  if (!selected || !selected.length) return { ok: false, why: 'Nothing selected.' };
  const wrong = selected.filter(f => !matches(f, expect));
  return {
    ok: true,
    artefacts: selected.map(f => ({
      name: f.name, size: f.size, modified: f.modified || null, type: f.type || '',
      step: task && task.step ? task.step.id : null,
      subject: task && task.subject ? task.subject.id : null,
      // provenance is what we can honestly assert, and no more
      provenance: { origin: 'operator-selected', mechanism: f.mechanism || 'unknown',
                    claimedBy: null, at: new Date().toISOString() }
    })),
    warning: wrong.length
      ? wrong.length + ' of these are not the expected ' + (ACCEPTS[expect] || ACCEPTS.any).label.toLowerCase() +
        '. Imported anyway — you chose them.'
      : null
  };
}

/* ── mechanism 1: File System Access. Desktop Chromium only, and it must be asked for. ── */
export function fsaAvailable(w) {
  const g = w || (typeof window !== 'undefined' ? window : {});
  return typeof g.showDirectoryPicker === 'function';
}
export async function fsaPick(w) {
  const g = w || window;
  if (!fsaAvailable(g)) throw new Error('This browser cannot watch a folder. Use Choose files, or run the local server.');
  return g.showDirectoryPicker({ id: 'zistgah-inbox', mode: 'read', startIn: 'downloads' });
}
export async function fsaList(dir) {
  const out = [];
  for await (const [name, h] of dir.entries()) {
    if (h.kind !== 'file') continue;
    let f; try { f = await h.getFile(); } catch (e) { continue; }
    out.push({ name, size: f.size, modified: f.lastModified, type: f.type,
               handle: h, mechanism: 'file-system-access' });
  }
  return out;
}

/* ── mechanism 2: the picker. Everywhere, including phones. ── */
export function pickerAccept(expect) {
  const a = ACCEPTS[expect] || ACCEPTS.any;
  if (expect === 'any') return '';
  return a.mime.map(m => m + '*').concat(a.ext.map(e => '.' + e)).join(',');
}
export function fromPicker(fileList) {
  return [...fileList].map(f => ({ name: f.name, size: f.size, modified: f.lastModified,
                                   type: f.type, file: f, mechanism: 'file-picker' }));
}

/* ── mechanism 3: the local endpoint. The substrate adapter, where the browser cannot look. ── */
export async function endpointList(base, folder, fetcher) {
  const f = fetcher || fetch;
  const u = (base || '').replace(/\/+$/, '') + '/api/inbox' + (folder ? '?dir=' + encodeURIComponent(folder) : '');
  let r;
  try { r = await f(u); }
  catch (e) { throw new Error('No answer from the local server. Is it running? Choose files still works.'); }
  if (!r.ok) throw new Error('The local server answered ' + r.status + '.');
  const j = await r.json();
  if (j.error) throw new Error(j.error);
  return { dir: j.dir, roots: j.roots || [],
           files: (j.files || []).map(x => ({ ...x, mechanism: 'local-endpoint' })) };
}

/** Which mechanism should the page offer first? Ask, do not assume. */
export function mechanisms(w, hasEndpoint) {
  const out = [];
  if (hasEndpoint) out.push({ id: 'endpoint', label: 'This machine', why: 'the local server can see the folder and tell you when it changes' });
  if (fsaAvailable(w)) out.push({ id: 'fsa', label: 'Watch a folder', why: 'this browser can read a folder you choose' });
  out.push({ id: 'picker', label: 'Choose files', why: 'works everywhere, including phones' });
  return out;
}
