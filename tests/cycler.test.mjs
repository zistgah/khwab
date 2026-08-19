import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const C = await import('../docs/js/cycler.js');

let n=0; const t=(m,f)=>{f();n++;console.log('  ok   '+m);};
const ta=async(m,f)=>{await f();n++;console.log('  ok   '+m);};

/* A fixture, not a model: the engine must be provable without any one tool's steps. */
const K = { STEPS: [
  { id:'split',  title:'Split it up',   target:'parts',  array:true, expect:'text', jsonKeys:['start','title'],
    prompt:'Split "{book}"{subtitle}, {duration} long. Reply with a JSON array.' },
  { id:'describe', title:'Describe it', target:'lead',   expect:'text',
    prompt:'Describe part {n} of "{book}", {start}-{end}, titled "{title}".' },
  { id:'cue',    title:'What to note',  target:'explanation', expect:'text',
    prompt:'For "{title}" ({start}-{end}), what matters? Already written:\n{lead}' },
  { id:'index',  title:'Title & terms', target:'topics', expect:'text', jsonKeys:['topics'],
    prompt:'Reply with {"title":"…","topics":["…"]}' },
  { id:'abstract', title:'Abstract',    target:'@description', once:true, expect:'text',
    prompt:'Abstract for "{book}", {count} parts:\n{toc}' }
] };
const mk = () => ({ book:{ title:'A Reel', subtitle:'', repo:'you/reel', author:'A',
  description:'', duration:48, reel:'fixture.bin' },
  subjects:[{id:'s1',start:'0:00',end:'0:10',title:'',lead:'',explanation:'',topics:null}] });

/* ── the point of the rebuild: routing, so the operator never picks a field ── */
t('a fenced JSON array routes to the array step by itself', () => {
  const r = C.route('```json\n[{"start":"0:00","end":"0:05","title":"T","beat":"b"}]\n```', K.STEPS, null);
  assert.equal(r.step.id, 'split'); assert.equal(r.value.length, 1); });
t('a JSON object with topics routes to the index step', () => {
  const r = C.route('{"title":"T","subtitle":"s","topics":["a"]}', K.STEPS, null);
  assert.equal(r.step.id, 'index'); });
t('prose routes to the step the cycle is actually on', () => {
  const cur = K.STEPS.find(s => s.id === 'cue');
  assert.equal(C.route('Just a paragraph of prose.', K.STEPS, cur).step.id, 'cue'); });
t('prose with no current step falls to the first prose step, never nowhere', () => {
  assert.equal(C.route('prose', K.STEPS, null).step.id, 'describe'); });
t('an empty clipboard is refused with a reason', () => {
  const r = C.route('   ', K.STEPS, null);
  assert.equal(r.step, null); assert.match(r.why, /empty/); });
t('chatty preamble around JSON is tolerated', () => {
  const r = C.route('Sure! Here you go:\n\n{"title":"T","topics":["x"]}\n\nHope that helps.', K.STEPS, null);
  assert.equal(r.step.id, 'index'); assert.equal(r.value.title, 'T'); });

/* ── the queue and the loop ── */
t('the cycle asks for the array step first, and counts what is left', () => {
  const s = mk(), q = C.queue(s.subjects, K.STEPS, s.book);
  assert.equal(q[0].step.id, 'split');
  const p = C.progress(s, K.STEPS); assert.ok(p.left > 0 && p.total > 0 && p.pct < 100); });
t('one answer expands one subject into several parts', () => {
  const s = mk();
  const r = C.apply('[{"start":"0:00","end":"0:12","title":"One","beat":"b"},' +
    '{"start":"0:12","end":"0:30","title":"Two","beat":"b"},' +
    '{"start":"0:30","end":"0:48","title":"Three","beat":"b"}]',
    { step: K.STEPS[0], subject: s.subjects[0] }, s, K.STEPS);
  assert.ok(r.ok); assert.equal(r.added, 2); assert.equal(s.subjects.length, 3);
  assert.equal(s.subjects[0].title, 'One'); assert.equal(s.subjects[2].title, 'Three');
  assert.equal(new Set(s.subjects.map(x => x.id)).size, 3, 'ids stay unique'); });
t('prose fills the first subject that still needs it, then the next', () => {
  const s = mk();
  C.apply('[{"start":"0:00","end":"0:20","title":"A"},{"start":"0:20","end":"0:48","title":"B"}]',
    { step: K.STEPS[0], subject: s.subjects[0] }, s, K.STEPS);
  s.subjects.forEach(x => { x.shots = 1; });
  C.apply('first description', { step: K.STEPS[1], subject: s.subjects[0] }, s, K.STEPS);
  assert.equal(s.subjects[0].lead, 'first description');
  C.apply('second description', { step: K.STEPS[1], subject: s.subjects[1] }, s, K.STEPS);
  assert.equal(s.subjects[1].lead, 'second description'); });
t('the abstract is filed on the book, not on a subject', () => {
  const s = mk();
  const r = C.apply('<p>abs</p>', { step: K.STEPS.find(x=>x.id==='abstract'), subject:null }, s, K.STEPS);
  assert.ok(r.ok); assert.equal(s.book.description, '<p>abs</p>'); });
t('the ENGINE carries no model — this file imports only cycler.js', () => {
  const src = readFileSync(new URL('./cycler.test.mjs', import.meta.url), 'utf8');
  const imports = [...src.matchAll(/from '([^']+)'|import\('([^']+)'\)/g)].map(m => m[1] || m[2]);
  const local = imports.filter(x => x.startsWith('.'));
  assert.deepEqual(local, ['../docs/js/cycler.js'], 'the shared engine must travel alone'); });

/* ── endpoints: shapes, never providers ── */
t('the shipped presets are request SHAPES and two are local and keyless', () => {
  const local = C.SHAPES.filter(x => x.local);
  assert.equal(local.length, 2); assert.ok(local.every(x => x.keyless));
  assert.ok(local.every(x => /localhost|127\.0\.0\.1/.test(x.url)));
  const blob = JSON.stringify(C.SHAPES).toLowerCase();
  for (const v of ['openai','anthropic','claude','gemini','chatgpt','google','ollama','mistral'])
    assert.ok(!blob.includes(v), 'names a provider: ' + v); });
t('a request is built without being sent, and carries no key when keyless', () => {
  const r = C.request({ ...C.shape('local-chat') }, 'hello "quoted"');
  assert.equal(r.url, 'http://localhost:8080/v1/chat/completions');
  assert.equal(r.body.messages[0].content, 'hello "quoted"');
  assert.ok(!r.headers.authorization); });
t('a key is sent only when one is given', () => {
  const r = C.request({ ...C.shape('remote-chat'), url:'https://x/y', key:'K' }, 'p');
  assert.equal(r.headers.authorization, 'Bearer K'); });
t('no endpoint is ever assumed', () => {
  assert.throws(() => C.request({}, 'p'), /No endpoint set/); });
await ta('a local server that is not running says so plainly', async () => {
  await assert.rejects(() => C.ask({ ...C.shape('local-gen') }, 'p',
    async () => { throw new Error('ECONNREFUSED'); }), /running on this machine/); });
await ta('a reply is dug out of the shape the operator described', async () => {
  const out = await C.ask({ ...C.shape('local-chat') }, 'p',
    async () => ({ ok:true, json: async () => ({ choices:[{ message:{ content:'ANSWER' } }] }) }));
  assert.equal(out, 'ANSWER'); });
await ta('a reply in the wrong place is reported, not silently empty', async () => {
  await assert.rejects(() => C.ask({ ...C.shape('local-chat') }, 'p',
    async () => ({ ok:true, json: async () => ({ nope:1 }) })), /Nothing found at/); });

/* ── clipboard ── */
await ta('the clipboard is read directly when the browser allows it', async () => {
  const nav = { clipboard: { readText: async () => 'pasted text' } };
  assert.equal(await C.readClipboard(nav), 'pasted text'); });
await ta('a browser without the clipboard API fails with a code the UI can fall back on', async () => {
  await assert.rejects(() => C.readClipboard({}), /no-clipboard-api/);
  await assert.rejects(() => C.readClipboard({ clipboard:{ readText: async () => '  ' } }), /clipboard-empty/); });


console.log(`\n  ===== ${n} pass, 0 fail =====`);
