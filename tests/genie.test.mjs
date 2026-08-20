import assert from 'node:assert/strict';
const G = await import('./genie.js');
const W = await import('./workflows.js');
let n=0; const t=(m,f)=>{f();n++;console.log('  ok   '+m);};
const flat = s => String(s).replace(/\s+/g,' ');

t('every cycle node declares a verb and what it leaves behind', () => {
  for (const s of G.CYCLE) {
    const v = G.validateStep(s);
    assert.ok(v.ok, s.id + ': ' + v.problems.join('; ')); } });
t('AB INITIO exists — a person with only an idea can start', () => {
  assert.ok(G.MODES['ab-initio']);
  assert.equal(G.MODES['ab-initio'].starts, 'discover');
  assert.match(G.MODES['ab-initio'].what, /No artifact exists yet/); });
t('and the mode I had built is the LESSER one, not the only one', () => {
  assert.equal(G.MODES.ingest.starts, 'specify');
  assert.equal(Object.keys(G.MODES).length, 3, 'ab-initio, ingest, correct'); });
t('a step that produces PROSE ABOUT a thing is refused', () => {
  for (const bad of ['describe the shot','explain what happens','summarise the passage','discuss the result']) {
    const v = G.validateStep({ verb:'CREATE', produces: bad });
    assert.ok(!v.ok, 'accepted: ' + bad);
    assert.match(v.problems.join(' '), /rather than the thing/); }
  assert.ok(G.validateStep({verb:'CREATE',produces:'a Lean file that typechecks'}).ok); });
t('THE OLD WORKFLOWS FAIL THIS — which is the point', () => {
  // My published steps produced prose. That is the defect, stated as a test.
  const old = [{verb:'CREATE',produces:'describe the shot'},
               {verb:'CREATE',produces:'explain what to listen for'}];
  assert.ok(old.every(s => !G.validateStep(s).ok)); });

t('a prompt CARRIES the verb, the artifact and the tags — it is not a sentence with a slot', () => {
  const p = G.buildPrompt({ node:'formalize', mode:'ab-initio', domain:'a claim about time',
    constitution:['Act = executable intent','Inclination is signed, on edges'],
    state:{ known:[{tag:'AX',what:'events are partially ordered',source:'PEDLER'}],
            missing:['a metric estimator'] } });
  const f = flat(p);
  assert.ok(f.includes('FORMALIZE') && f.includes('CREATE'));
  assert.ok(f.includes('[AX] events are partially ordered (PEDLER)'));
  assert.ok(f.includes('a metric estimator'));
  assert.ok(f.includes('Act = executable intent'));
  assert.ok(f.includes('Produce the artifact component, not a description of it'));
  assert.ok(!/\{\w+\}/.test(p), 'no unfilled slot'); });
t('every prompt forbids supplying a plausible value where nothing is known', () => {
  for (const node of G.CYCLE.map(x=>x.id))
    assert.ok(flat(G.buildPrompt({node, mode:'ab-initio'}))
      .includes('write UNRESOLVED. Do not supply a plausible value')); });
t('the falsify node is told it is trying to KILL it', () => {
  assert.ok(flat(G.buildPrompt({node:'falsify',mode:'ab-initio'})).includes('You are trying to kill it')); });
t('the measure node refuses a number without units and uncertainty', () => {
  assert.ok(flat(G.buildPrompt({node:'experiment',mode:'ab-initio'}))
    .includes('A number without them is not a measurement')); });
t('the execute node refuses "what should happen"', () => {
  assert.ok(flat(G.buildPrompt({node:'simulate',mode:'ab-initio'}))
    .includes('not what should happen')); });
t('an unknown node or mode throws rather than guessing', () => {
  assert.throws(()=>G.buildPrompt({node:'nope',mode:'ab-initio'}), /no such cycle node/);
  assert.throws(()=>G.buildPrompt({node:'discover',mode:'nope'}), /no such mode/); });

t('a hypothesis cannot silently become a derived fact', () => {
  assert.ok(G.TAGS.HYP && G.TAGS.DER && G.TAGS.FAIL);
  const p = flat(G.buildPrompt({node:'formalize',mode:'ab-initio'}));
  assert.ok(p.includes('untagged will be read as derived, which would be a lie')); });
t('retrieved, inferred, proposed and unresolved are kept apart', () => {
  assert.deepEqual(Object.keys(G.PROVENANCE), ['RETRIEVED','INFERRED','PROPOSED','UNRESOLVED']);
  const p = flat(G.buildPrompt({node:'specify',mode:'ab-initio'}));
  assert.ok(p.includes('Mark anything you inferred as inferred')); });

t('completeness NEVER says the work is complete', () => {
  const req=[{id:'a',title:'Definition',required:true},{id:'b',title:'Derivation',required:true},
             {id:'c',title:'Physical validation',required:true}];
  const c = G.completeness(req, {a:{status:'done'},b:{status:'partial'}});
  assert.equal(c.done,1); assert.equal(c.partial,1); assert.equal(c.missing,1);
  assert.match(c.statement, /Physical validation does not exist yet/);
  const all = G.completeness(req, {a:{status:'done'},b:{status:'done'},c:{status:'done'}});
  assert.equal(all.ratio, 1);
  assert.match(all.statement, /That is not the same as correct/); });
t('the ratio is reported beside the components, not instead of them', () => {
  const c = G.completeness([{id:'a',title:'A'},{id:'b',title:'B'}], {a:{status:'done'}});
  assert.equal(c.ratio, 0.5);
  assert.equal(c.components.length, 2);
  assert.equal(c.components[1].status, 'missing'); });

t('a gate cannot pass silently', () => {
  assert.ok(!G.gate('G1',{verdict:'PASS'}).ok, 'a PASS with no evidence must be refused');
  assert.match(G.gate('G1',{verdict:'PASS'}).why, /assertion, not a gate/);
  assert.ok(!G.gate('G1',{verdict:'FAIL'}).ok, 'a FAIL must name the correction');
  assert.ok(!G.gate('G1',{verdict:'BLOCKED'}).ok);
  assert.ok(!G.gate('G1',{verdict:'ok'}).ok, 'only PASS/FAIL/BLOCKED/PARTIAL');
  assert.ok(G.gate('G1',{verdict:'PASS',evidence:'the suite runs green from a clean clone'}).ok); });

t('the six verbs are the only ones, and each is defined', () => {
  assert.deepEqual(Object.keys(G.VERBS).sort(),
    ['CREATE','EXECUTE','FALSIFY','INTEGRATE','MEASURE','VERIFY']);
  for (const [k,v] of Object.entries(G.VERBS)) assert.ok(v.length > 25, k + ' is not defined'); });
t('genie names no service, like everything else here', () => {
  const src = JSON.stringify([G.VERBS,G.TAGS,G.CYCLE,G.MODES,G.PROVENANCE]).toLowerCase();
  for (const v of ['openai','anthropic','claude','chatgpt','gemini','grok'])
    assert.ok(!src.includes(v), 'names ' + v); });

console.log(`\n  ===== ${n} pass, 0 fail =====`);
