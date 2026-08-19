import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
const W = await import('./workflows.js');
let n=0; const t=(m,f)=>{f();n++;console.log('  ok   '+m);};

/* ── the nine things ── */
t('all six declare their own nine things', () => {
  for (const id of Object.keys(W.WORKFLOWS)) {
    const d = W.declared(id);
    assert.ok(d.ok, id + ' is missing: ' + (d.missing||[]).join(', ')); } });
t('no two cyclers share a purpose, a contract or an artifact', () => {
  for (const field of ['purpose','contract','artifact']) {
    const vals = Object.values(W.WORKFLOWS).map(w => w[field]);
    assert.equal(new Set(vals).size, vals.length, 'duplicated ' + field); } });
t('no two cyclers share a workflow — the step ids differ', () => {
  const sigs = Object.entries(W.WORKFLOWS).map(([id,w]) => [id, w.workflow.map(s=>s.id).join('>')]);
  const seen = new Map();
  for (const [id,s] of sigs) {
    assert.ok(!seen.has(s), id + ' has the same steps as ' + seen.get(s) + ': ' + s);
    seen.set(s,id); } });
t('every step asks a QUESTION, not a noun-slot template', () => {
  for (const [id,w] of Object.entries(W.WORKFLOWS))
    for (const s of w.workflow) {
      assert.ok(s.ask && s.ask.length > 12, id+'/'+s.id+' asks nothing');
      assert.ok(!/\{\w+\}/.test(s.ask), id+'/'+s.id+' has a template slot: '+s.ask); } });

/* ── THE LEAK. This is the defect that reached six live DOIs. ── */
t('THE LEAK: no cycler borrows a sibling vocabulary', () => {
  for (const [id,w] of Object.entries(W.WORKFLOWS)) {
    const text = [w.purpose,w.contract,w.artifact,...w.context,...w.state,...w.invariants,
                  ...w.failures,...w.evidence,...w.workflow.map(s=>s.ask)].join(' ');
    const found = W.leaks(id, text);
    assert.deepEqual(found, [], id + ' borrows: ' +
      found.map(f=>`"${f.word}" from ${f.from}`).join(', ')); } });
t('the leak check CATCHES what actually shipped', () => {
  // These are verbatim from the published pages.
  assert.ok(W.leaks('yadein', 'Chapters are cues into one entry, not cut copies.').length,
    'must catch the yadein page');
  assert.ok(W.leaks('tilasm', 'Chapters are cues into one station, not cut copies.').length,
    'must catch the tilasm page');
  assert.ok(W.leaks('pench',  'Shots, descriptions, cues, index terms, abstract.').length,
    'must catch khwab\u2019s step list on the workshop page');
  assert.ok(W.leaks('tilasm', 'A recording goes in. Cued chapters.').length,
    'must catch awaz vocabulary on the staging room'); });
t('and does NOT fire where a timeline is real', () => {
  assert.deepEqual(W.leaks('khwab','Chapters are cues into one reel, not cut copies.'), []);
  assert.deepEqual(W.leaks('awaz','Passages are cues into one recording. Timecodes carry hours.'), []); });

/* ── the AI config: he asked for DEFAULTS, in a config file ── */
t('the AI config ships WITH defaults — an empty table was the error', () => {
  const c = JSON.parse(readFileSync(new URL('./ai.config.json', import.meta.url)));
  assert.ok(c.open_in_a_tab.length >= 5, 'links to standard AI must be there by default');
  assert.ok(c.on_this_machine.every(x => x.keyless), 'the local paths need no key');
  assert.ok(c.no_ai_at_all.allowed === true, 'answering by hand must remain allowed'); });
t('the config is DATA — no service is compiled into the code', () => {
  const src = readFileSync(new URL('./workflows.js', import.meta.url), 'utf8').toLowerCase();
  for (const v of ['claude','chatgpt','openai','gemini','anthropic','perplexity','deepseek','grok'])
    assert.ok(!src.includes(v), 'workflows.js names ' + v); });
t('the order is alphabetical, so the file expresses no preference', () => {
  const c = JSON.parse(readFileSync(new URL('./ai.config.json', import.meta.url)));
  const names = c.open_in_a_tab.map(x => x.name);
  assert.deepEqual(names, [...names].sort((a,b)=>a.localeCompare(b)), 'not alphabetical — that reads as a ranking'); });

/* ── against the LIVE pages, if they are here ── */
t('every live page, if present, is checked for the leak', () => {
  let checked = 0, bad = [];
  for (const id of Object.keys(W.WORKFLOWS)) {
    const p = new URL(`./live/${id}.html`, import.meta.url);
    if (!existsSync(p)) continue;
    checked++;
    const found = W.leaks(id, readFileSync(p, 'utf8'));
    if (found.length) bad.push(id + ': ' + found.map(f=>f.word).join(', '));
  }
  console.log('       (' + checked + ' live pages present)');
  assert.deepEqual(bad, [], 'live pages still leaking: ' + bad.join(' | ')); });

console.log(`\n  ===== ${n} pass, 0 fail =====`);
