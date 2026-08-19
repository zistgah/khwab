import assert from 'node:assert/strict';
const K = await import('../docs/js/khwab.js');
const C = await import('../docs/js/cycler.js');
let n=0; const t=(m,f)=>{f();n++;console.log('  ok   '+m);};
const mk = () => ({ book:{ title:'A Reel', subtitle:'', repo:'you/reel', author:'A',
  description:'', duration:48, reel:'khwab-reel.mp4' },
  subjects:[{id:'s1',start:'0:00',end:'0:10',title:'',lead:'',explanation:'',topics:null}] });

t('the cycle breaks the reel into shots first', () => {
  assert.equal(K.nextTask(mk()).step.id, 'shots'); });
t('the poster step is BINARY and optional, so it never blocks', () => {
  const b = K.STEPS.filter(s => s.binary);
  assert.equal(b.length, 1); assert.equal(b[0].expect, 'image'); assert.equal(b[0].optional, true); });
t('every text step declares what it expects, so the inbox knows', () => {
  for (const s of K.STEPS) assert.ok(s.expect, s.id + ' declares no expect'); });
/* ── prompts and payload ── */
t('prompts interpolate the reel, the shot and the timecodes', () => {
  const s = mk(); s.subjects[0].title = 'Opening'; s.subjects[0].lead = 'L';
  const p = K.promptFor(s, { step: K.STEPS.find(x=>x.id==='cue'), subject: s.subjects[0] });
  assert.ok(p.includes('Opening') && p.includes('0:00') && p.includes('0:10') && p.includes('L'));
  assert.ok(!/\{\w+\}/.test(p), 'no placeholder left unfilled'); });
t('timecodes round-trip', () => {
  assert.equal(K.toSeconds('1:23'), 83); assert.equal(K.toTimecode(83), '1:23');
  assert.equal(K.toSeconds('0:07'), 7); assert.equal(K.toTimecode(48), '0:48'); });
t('the doctor catches overlaps, reversed shots and a run past the end', () => {
  const s = mk(); s.book.duration = 48;
  s.subjects = [{id:'a',start:'0:00',end:'0:20',title:'A',lead:'L'},
                {id:'b',start:'0:10',end:'0:05',title:'B',lead:'L'},
                {id:'c',start:'0:30',end:'2:00',title:'C',lead:'L'}];
  const f = K.doctor(s);
  assert.ok(f.some(x=>/ends before it starts/.test(x)));
  assert.ok(f.some(x=>/before the previous one ends/.test(x)));
  assert.ok(f.some(x=>/past the end of the reel/.test(x))); });
t('the payload is kitab-shaped with a cued video block', () => {
  const s = mk();
  s.subjects = [{id:'a',start:'0:00',end:'0:20',title:'A',lead:'L',explanation:'E',topics:['x'],part:'The Reel'},
                {id:'b',start:'0:20',end:'0:48',title:'B',lead:'L',explanation:'E',topics:['y'],part:'The Reel'}];
  s.book.description = '<p>a</p>';
  const p = K.buildPayload(s), cfg = p['book.config.json'];
  assert.equal(cfg.meta.doi, null); assert.equal(cfg.meta.repo, 'you/reel');
  assert.equal(cfg.meta.media.kind, 'video');
  assert.equal(cfg.structure.chapters.length, 2);
  const v = p.content['ch-01'].blocks.find(x => x.type === 'video');
  assert.equal(v.start, 0); assert.equal(v.end, 20);
  assert.equal(v.src, 'assets/khwab-reel.mp4');
  assert.ok(v.tts === true && v.seed.enabled === true, 'a talking artifact, like every kitab figure');
  assert.equal(p['index.json'].shots.length, 2); });
t('one reel serves every shot — the file is listed once', () => {
  const s = mk();
  s.subjects = [{id:'a',start:'0:00',end:'0:20',title:'A',lead:'L'},{id:'b',start:'0:20',end:'0:48',title:'B',lead:'L'}];
  const p = K.buildPayload(s);
  const srcs = Object.values(p.content).map(c => c.blocks.find(b=>b.type==='video').src);
  assert.equal(srcs[0], srcs[1]);
  assert.equal(p['index.json'].reel.file, 'assets/khwab-reel.mp4'); });

console.log(`\n  ===== ${n} pass, 0 fail =====`);
