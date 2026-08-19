import assert from 'node:assert/strict';
const I = await import('../docs/js/inbox.js');
let n=0; const t=(m,f)=>{f();n++;console.log('  ok   '+m);};
const ta=async(m,f)=>{await f();n++;console.log('  ok   '+m);};
const F=(name,size,mod,type)=>({name,size,modified:mod,type:type||''});

/* ── AI sources: shipped empty, nothing named ── */
t('the source table ships EMPTY — no service is named or defaulted', () => {
  const store = { getItem: () => null, setItem: () => {} };
  assert.deepEqual(I.loadSources(store), []);
  const blob = JSON.stringify(I.SOURCE_KINDS).toLowerCase();
  for (const v of ['openai','anthropic','claude','chatgpt','gemini','google','ollama','mistral','perplexity'])
    assert.ok(!blob.includes(v), 'names a service: ' + v); });
t('the operator adds their own, and bad ones are refused with a reason', () => {
  let l = [];
  assert.match(I.addSource(l,{name:'',kind:'compose',url:'https://x'}).why, /name/);
  assert.match(I.addSource(l,{name:'Mine',kind:'nope',url:'https://x'}).why, /how it is reached/);
  assert.match(I.addSource(l,{name:'Mine',kind:'compose',url:'x'}).why, /http/);
  const r = I.addSource(l,{name:'Mine',kind:'compose',url:'https://x/'});
  assert.ok(r.ok); l = r.list; assert.equal(l.length,1);
  assert.match(I.addSource(l,{name:'mine',kind:'compose',url:'https://y/'}).why, /already have/); });
t('three ways to reach an AI, and one of them is local and keyless', () => {
  assert.ok(I.SOURCE_KINDS.some(k => k.id === 'local' && /keyless/i.test(k.hint))); });
await ta('opening a source copies the prompt and opens the tab the operator chose', async () => {
  let copied=null, opened=null;
  const r = await I.openWith({name:'Mine',url:'https://x/chat'}, 'THE PROMPT',
    { writeClipboard: async t => { copied=t; }, open: u => { opened=u; } });
  assert.equal(copied,'THE PROMPT'); assert.equal(opened,'https://x/chat'); assert.ok(r.copied); });
await ta('a {prompt} placeholder in the address is filled instead', async () => {
  let opened=null;
  await I.openWith({url:'https://x/?q={prompt}'}, 'a b',
    { writeClipboard: async()=>{}, open:u=>{opened=u;} });
  assert.equal(opened,'https://x/?q=a%20b'); });
await ta('a blocked clipboard does not stop the tab — it says so instead', async () => {
  const r = await I.openWith({url:'https://x'}, 'p',
    { writeClipboard: async()=>{throw new Error('blocked')}, open:()=>{} });
  assert.equal(r.copied,false); assert.match(r.note,/by hand/); });

/* ── the inbox: N files, no assumptions ── */
t('what a step expects filters, but never forbids', () => {
  assert.ok(I.matches(F('a.png',1,1,'image/png'),'image'));
  assert.ok(!I.matches(F('a.pdf',1,1,'application/pdf'),'image'));
  assert.ok(I.matches(F('a.pdf',1,1),'any'), 'any accepts everything');
  assert.ok(I.matches(F('x.MP4',1,1),'video'), 'case does not matter');
  assert.ok(I.matches(F('m.glb',1,1),'model')); });
t('new files are detected by name AND by size+time — a rewritten file counts', () => {
  const base=[F('a.png',10,100),F('b.png',20,100)];
  const now =[F('a.png',10,100),F('b.png',99,200),F('c.png',5,300)];
  const fresh = I.newSince(base, now).map(f=>f.name).sort();
  assert.deepEqual(fresh,['b.png','c.png']); });
t('the panel says VISIBLE, never GENERATED — provenance is not claimed', () => {
  const p = I.present([F('a.png',1,300,'image/png'),F('note.txt',1,200)],
    { expect:'image', baseline:[F('note.txt',1,200)] });
  assert.match(p.notice, /new file is visible/);
  assert.ok(!/generat|produced|created by|your ai/i.test(p.notice)); });
t('no baseline means no claim at all', () => {
  assert.equal(I.present([F('a.png',1,1)], { expect:'image' }).notice, null); });
t('nothing new is stated plainly rather than left blank', () => {
  const b=[F('a.png',1,1)];
  assert.match(I.present(b,{expect:'image',baseline:b}).notice, /No new files/); });
t('N files means N files — 100 in, 100 shown, counted and sorted', () => {
  const many = Array.from({length:100},(_,i)=>F('f'+i+'.png', i, 1000-i,'image/png'));
  many.push(F('doc.pdf',5,9999,'application/pdf'));
  const p = I.present(many,{expect:'image',sort:'modified'});
  assert.equal(p.counts.total,101); assert.equal(p.counts.fitting,100);
  assert.equal(p.rows[0].name,'doc.pdf','newest first, and it is still shown though it does not fit');
  assert.equal(p.rows[0].fits,false); });
t('filtering to what fits is a CHOICE, not the default', () => {
  const l=[F('a.png',1,1,'image/png'),F('b.pdf',1,2,'application/pdf')];
  assert.equal(I.present(l,{expect:'image'}).rows.length,2);
  assert.equal(I.present(l,{expect:'image',onlyFitting:true}).rows.length,1); });
t('sorting by name is numeric, so shot10 follows shot9', () => {
  const l=[F('shot10.png',1,1),F('shot9.png',1,2),F('shot1.png',1,3)];
  assert.deepEqual(I.present(l,{sort:'name'}).rows.map(r=>r.name),
    ['shot1.png','shot9.png','shot10.png']); });

/* ── import: the operator decides, and we record only what we know ── */
t('nothing enters the work without a selection', () => {
  assert.equal(I.importSelection([], null, 'image').ok, false);
  assert.equal(I.importSelection(null, null, 'image').ok, false); });
t('an imported artefact records operator-selected, and claims nobody', () => {
  const r = I.importSelection([{...F('a.png',9,5,'image/png'), mechanism:'file-picker'}],
    { step:{id:'visual'}, subject:{id:'shot-1'} }, 'image');
  assert.ok(r.ok);
  const a = r.artefacts[0];
  assert.equal(a.provenance.origin,'operator-selected');
  assert.equal(a.provenance.claimedBy, null, 'we never say which AI made it');
  assert.equal(a.provenance.mechanism,'file-picker');
  assert.equal(a.step,'visual'); assert.equal(a.subject,'shot-1'); });
t('an unexpected type is imported anyway, with a note — the operator chose it', () => {
  const r = I.importSelection([F('a.pdf',1,1,'application/pdf')], null, 'image');
  assert.ok(r.ok); assert.match(r.warning, /not the expected image/); });
t('multi-select imports all of them', () => {
  const r = I.importSelection([F('a.png',1,1),F('b.png',1,2),F('c.png',1,3)], null, 'image');
  assert.equal(r.artefacts.length,3); });

/* ── mechanisms ── */
t('the picker is always offered, and is the only one guaranteed', () => {
  const m = I.mechanisms({}, false).map(x=>x.id);
  assert.deepEqual(m,['picker']);
  assert.deepEqual(I.mechanisms({}, true).map(x=>x.id),['endpoint','picker']);
  assert.deepEqual(I.mechanisms({showDirectoryPicker(){}}, true).map(x=>x.id),
    ['endpoint','fsa','picker']); });
t('folder watching is refused honestly where the browser cannot do it', async () => {
  assert.equal(I.fsaAvailable({}), false);
  await assert.rejects(() => I.fsaPick({}), /cannot watch a folder/); });
t('the picker accept string follows what the step expects', () => {
  assert.ok(I.pickerAccept('image').includes('image/*'));
  assert.ok(I.pickerAccept('video').includes('.mp4'));
  assert.equal(I.pickerAccept('any'), '', 'any means no restriction'); });
await ta('the local endpoint lists a folder and tags the mechanism', async () => {
  const r = await I.endpointList('http://127.0.0.1:8711', '/home/x/Downloads',
    async () => ({ ok:true, json: async () => ({ dir:'/home/x/Downloads', roots:['/home/x'],
      files:[{name:'a.png',size:1,modified:5,type:'image/png'}] }) }));
  assert.equal(r.dir,'/home/x/Downloads');
  assert.equal(r.files[0].mechanism,'local-endpoint'); });
await ta('a local server that is not running says so, and points at the fallback', async () => {
  await assert.rejects(() => I.endpointList('http://127.0.0.1:8711', null,
    async () => { throw new Error('ECONNREFUSED'); }), /Choose files still works/); });

console.log(`\n  ===== ${n} pass, 0 fail =====`);
