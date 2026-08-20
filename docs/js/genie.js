/* genie.js — the Prompt Operating System.
 *
 * WHAT WAS WRONG WITH THE PROMPTS
 * -------------------------------
 * Every workflow I wrote assumed the artifact already existed. "Describe this plate." "What is
 * heard in this passage." They were DESCRIPTION pipelines: you bring a thing, they annotate it.
 *
 * That is one entry mode out of two, and it is the lesser one. A person with an idea and nothing
 * else could not start. **Ab initio** — from the beginning — means the cycle CONSTRUCTS the
 * artifact rather than captioning one you already made.
 *
 * THE RULE, from the plate
 * ------------------------
 *   Every prompt must either CREATE, VERIFY, EXECUTE, MEASURE, FALSIFY or INTEGRATE an artifact.
 *   Each cycle must leave behind a more complete, executable artifact than the previous cycle.
 *
 * A step that only explains is not a step. A step that produces prose about a thing is not
 * producing the thing. That is the whole correction.
 */

/* ── the six verbs. A step declares exactly one. ── */
export const VERBS = {
  CREATE:    'brings a component of the artifact into existence that was not there before',
  VERIFY:    'independently attacks a component that exists and reports what held',
  EXECUTE:   'runs it and returns what happened, not what should happen',
  MEASURE:   'produces a number, with its units and its uncertainty',
  FALSIFY:   'tries to kill the claim with the smallest counterexample it can find',
  INTEGRATE: 'folds a verified component back into the whole and states what changed'
};

/* ── epistemic status. A hypothesis must never silently become a derived fact. ── */
export const TAGS = {
  DEF:    'definition — true by stipulation',
  AX:     'axiom — assumed without proof, and named as such',
  ASSUMP: 'assumption — held for now, and revisable',
  DER:    'derived — follows from what is above it, and the derivation exists',
  CONJ:   'conjecture — believed, not shown',
  HYP:    'hypothesis — proposed in order to be attacked',
  EMP:    'empirically supported — an observation exists',
  OPEN:   'unresolved — nobody has settled it',
  FAIL:   'falsified — an attempt to kill it succeeded'
};
export const TAG_ORDER = ['DEF', 'AX', 'ASSUMP', 'DER', 'CONJ', 'HYP', 'EMP', 'OPEN', 'FAIL'];

/* ── provenance. Retrieved and inferred must not contaminate each other silently. ── */
export const PROVENANCE = {
  RETRIEVED:  'read from a source that exists, and the source is named',
  INFERRED:   'concluded here, from something retrieved',
  PROPOSED:   'offered by this cycle, resting on nothing yet',
  UNRESOLVED: 'known to be missing'
};

/* ── the core cycle. Every node produces an artifact. ── */
export const CYCLE = [
  { id: 'discover',  verb: 'CREATE',    produces: 'a framed opportunity, written down' },
  { id: 'specify',   verb: 'CREATE',    produces: 'a specification precise enough to be wrong' },
  { id: 'formalize', verb: 'CREATE',    produces: 'the formal statement, with every line tagged' },
  { id: 'implement', verb: 'CREATE',    produces: 'the thing itself — code, a model, a build' },
  { id: 'verify',    verb: 'VERIFY',    produces: 'a verification report naming what held and what did not' },
  { id: 'simulate',  verb: 'EXECUTE',   produces: 'a run, reproducible by someone else' },
  { id: 'experiment',verb: 'MEASURE',   produces: 'a protocol and a measurement with its uncertainty' },
  { id: 'falsify',   verb: 'FALSIFY',   produces: 'the smallest test that could kill it, and its result' },
  { id: 'document',  verb: 'INTEGRATE', produces: 'the record: method, result, context' },
  { id: 'audit',     verb: 'VERIFY',    produces: 'a completeness report — what is missing, named' },
  { id: 'refine',    verb: 'INTEGRATE', produces: 'the next cycle\'s starting artifact' }
];

/* ── ENTRY MODES. This is what was missing. ── */
export const MODES = {
  'ab-initio': {
    title: 'From nothing',
    what: 'You have an idea, a question, or a problem. No artifact exists yet.',
    starts: 'discover',
    note: 'The cycle constructs the artifact. Every step leaves something behind that was not there before.'
  },
  ingest: {
    title: 'From material',
    what: 'The artifact exists — plates, a reel, a recording, a run, a folder of notes.',
    starts: 'specify',
    note: 'Discovery already happened, outside. The cycle formalises, verifies and completes what you brought.'
  },
  correct: {
    title: 'From something wrong',
    what: 'A published artifact is defective and you know it.',
    starts: 'falsify',
    note: 'Establish the defect first, then re-enter at the step that produces the component it broke. Never edit a sealed artifact; make the next one.'
  }
};

/* ── the artifact model. A cycler declares its required components. ── */
export function completeness(required, have) {
  const done = required.filter(c => (have[c.id] || {}).status === 'done');
  const partial = required.filter(c => (have[c.id] || {}).status === 'partial');
  const missing = required.filter(c => !have[c.id] || have[c.id].status === 'missing');
  return {
    // C_A = completed components / required components. Reported per component, because a
    // single number invites "it is basically finished".
    ratio: required.length ? done.length / required.length : 0,
    components: required.map(c => ({
      id: c.id, title: c.title, required: !!c.required,
      status: (have[c.id] || {}).status || 'missing',
      evidence: (have[c.id] || {}).evidence || null
    })),
    done: done.length, partial: partial.length, missing: missing.length,
    // The system does not say "this research is complete".
    statement: missing.length
      ? 'Incomplete: ' + missing.map(c => c.title).join(', ') + ' ' +
        (missing.length === 1 ? 'does not exist yet.' : 'do not exist yet.')
      : partial.length
        ? 'Every component exists; ' + partial.length + ' ' +
          (partial.length === 1 ? 'is' : 'are') + ' partial.'
        : 'Every required component exists and is marked done. That is not the same as correct.'
  };
}

/* ── prompt construction ──────────────────────────────────────────────────
 * A prompt is built from the cycle node, the mode, the artifact state and the domain. It is not a
 * sentence with a noun slot.
 */
export function buildPrompt(spec) {
  const { node, mode, domain, state, constitution } = spec;
  const n = CYCLE.find(x => x.id === node);
  if (!n) throw new Error('no such cycle node: ' + node);
  const m = MODES[mode];
  if (!m) throw new Error('no such mode: ' + mode);
  const known = (state && state.known) || [];
  const missing = (state && state.missing) || [];

  const L = [];
  L.push(`You are one node of a construction cycle. This node is ${n.id.toUpperCase()}.`);
  L.push(`Its verb is ${n.verb}: it ${VERBS[n.verb]}.`);
  L.push(`It must leave behind: ${n.produces}.`);
  L.push('');
  L.push(`Mode: ${m.title}. ${m.what}`);
  if (domain) L.push(`Domain: ${domain}`);
  L.push('');
  if (constitution && constitution.length) {
    L.push('The constitution of this work, which you may not contradict:');
    for (const c of constitution) L.push('  · ' + c);
    L.push('');
  }
  if (known.length) {
    L.push('What already exists, with its status:');
    for (const k of known) L.push(`  [${k.tag}] ${k.what}` + (k.source ? `  (${k.source})` : ''));
    L.push('');
  }
  if (missing.length) {
    L.push('What is known to be missing:');
    for (const k of missing) L.push('  · ' + k);
    L.push('');
  }
  L.push('Rules for your reply:');
  L.push('  1. Produce the artifact component, not a description of it.');
  L.push(`  2. Tag every statement you make with one of: ${TAG_ORDER.join(', ')}.`);
  L.push('     A hypothesis that arrives untagged will be read as derived, which would be a lie.');
  L.push('  3. Mark anything you retrieved with its source. Mark anything you inferred as inferred.');
  L.push('     If you propose something resting on nothing, say PROPOSED.');
  L.push('  4. Where you do not know, write UNRESOLVED. Do not supply a plausible value.');
  L.push('  5. Name what this component still needs before it could be called done.');
  if (n.verb === 'FALSIFY')
    L.push('  6. You are trying to kill it. A falsification step that finds nothing must say what it tried.');
  if (n.verb === 'MEASURE')
    L.push('  6. Every number carries its units and its uncertainty. A number without them is not a measurement.');
  if (n.verb === 'EXECUTE')
    L.push('  6. Report what happened when it ran, not what should happen. If it did not run, say so.');
  return L.join('\n');
}

/** A step is only legitimate if it declares a verb and names what it leaves behind. */
export function validateStep(s) {
  const bad = [];
  if (!s.verb || !VERBS[s.verb]) bad.push('no verb, or an unknown one: ' + s.verb);
  if (!s.produces) bad.push('does not say what it leaves behind');
  if (s.produces && /^(describe|explain|summari[sz]e|discuss|reflect)/i.test(s.produces))
    bad.push('produces prose about a thing rather than the thing: "' + s.produces + '"');
  return { ok: !bad.length, problems: bad };
}

/** The gate at the end of a node. PASS/FAIL/BLOCKED/PARTIAL — never a silent success. */
export function gate(id, result) {
  const v = ['PASS', 'FAIL', 'BLOCKED', 'PARTIAL'];
  if (!v.includes(result.verdict)) return { ok: false, why: 'verdict must be one of ' + v.join('/') };
  if (result.verdict === 'PASS' && !result.evidence)
    return { ok: false, why: 'a PASS without evidence is an assertion, not a gate' };
  if (result.verdict === 'FAIL' && !result.correction)
    return { ok: false, why: 'a FAIL must name the correction required' };
  if (result.verdict === 'BLOCKED' && !result.blockedBy)
    return { ok: false, why: 'BLOCKED must name what is blocking it' };
  return { ok: true, gate: id, ...result };
}
