/* workflows.js — the correction.
 *
 * WHAT WENT WRONG
 * ---------------
 * The cycler ENGINE is common. The WORKFLOW is not. I built one workflow, parameterised the noun,
 * and shipped it six times. The evidence is on the published pages:
 *
 *   yadein  — "Chapters are cues into one entry, not cut copies"   (a diary entry has no timeline)
 *   tilasm  — "Chapters are cues into one station"                 (a station has no timeline)
 *   all six — "Shots, descriptions, cues, index terms, abstract"   (that is khwab's step list)
 *   all six — "A entry goes in", "A station goes in"               (ungrammatical: a noun slot)
 *
 * Shared code is an implementation optimisation. It is not an ontological claim.
 *
 * THE RULE THIS FILE ENFORCES
 * ---------------------------
 * Every component declares NINE things of its own, and a test fails the build if any is missing or
 * if any is copied from a sibling:
 *
 *   1 purpose        what a person is trying to do
 *   2 contract       what it promises and what it refuses
 *   3 context        what it must know before it can help
 *   4 state          what it is holding between steps
 *   5 invariants     what must never stop being true
 *   6 failures       how it goes wrong in practice
 *   7 evidence       what it must have before it will publish
 *   8 workflow       ITS OWN steps, in its own vocabulary
 *   9 artifact       what actually comes out
 *
 * The cycler is not a content-production engine. It is an AI-agnostic human–AI work protocol:
 * intent → context → a meaningful prompt → whichever AI → human inspection → the next prompt →
 * an artifact the human authored. It must not become an AI provider, and it must stay useful if
 * every commercial provider vanishes tomorrow.
 */

/* ── matba · print ────────────────────────────────────────────────────────── */
export const matba = {
  id: 'matba', script: 'مطبع', room: 'press room', output: 'print',
  purpose: 'Set something that will be read on a page: a paper, a book, a poster, a manual, a curriculum, a report, a catalogue, a legal filing.',
  contract: 'It will not take an impression on a broken forme. Eight checks stand between a folder of plates and a permanent record, and each exists because that defect reached one.',
  context: ['the plates themselves', 'which plate is the jacket', 'the parts a reader moves through', 'who is publishing it and under what licence'],
  state: ['plate table', 'part structure', 'cover selection', 'the abstract'],
  invariants: ['a plate is never minted twice under two names',
               'the jacket is never counted as a chapter',
               'no file reaches the deposit that no chapter declares'],
  failures: ['duplicate bytes under different filenames', 'template placeholders riding along',
             'a stale title inherited from the book it was derived from', 'a blank deposit abstract'],
  evidence: ['a content hash per plate', 'a sealed manifest', 'a timestamp before the mint'],
  workflow: [
    { id: 'plates',   ask: 'What is on each plate?' },
    { id: 'place',    ask: 'Which part does it belong to, and in what order?' },
    { id: 'lead',     ask: 'What does a reader meet before they see it?' },
    { id: 'look',     ask: 'What should they look at first, and why is it load-bearing?' },
    { id: 'index',    ask: 'How would a contents list name it? What are its index terms?' },
    { id: 'abstract', ask: 'What does the whole work contain?' }
  ],
  artifact: 'A kitab-shaped book: parts, chapters, figures that talk, a sealed manifest and a DOI.'
};

/* ── awaz · audio ─────────────────────────────────────────────────────────── */
export const awaz = {
  id: 'awaz', script: 'آواز', room: 'listening room', output: 'audio',
  purpose: 'Make something to be heard: a song, a podcast, a lecture, an oral history, an audiobook, a language lesson, an interview, a sound work.',
  contract: 'Passages are cues into one recording, never cut copies. One file, one hash, one deposit — so what was published is what was recorded.',
  context: ['the recording and its duration', 'whether it is speech, music or neither', 'who is speaking, if anyone'],
  state: ['passage boundaries in timecode', 'transcripts where speech exists', 'the waveform, which is the only picture a recording has'],
  invariants: ['a cue never ends before it starts and never runs past the end',
               'a transcript marks [inaudible] rather than guessing',
               'the recording is deposited with the work, not linked from elsewhere'],
  failures: ['passages that overlap', 'a transcript that invents a word it could not hear',
             'timecodes that lose the hour on a long recording'],
  evidence: ['the recording sha256 in the metadata', 'a waveform computed from the samples, not drawn'],
  workflow: [
    { id: 'passages',   ask: 'Where does it change — a key, a speaker, a section, a turn?' },
    { id: 'transcript', ask: 'What is actually said here, verbatim?', optional: true },
    { id: 'describe',   ask: 'What is heard in this passage?' },
    { id: 'listen',     ask: 'What should a listener attend to, and why does it carry the passage?' },
    { id: 'index',      ask: 'How would a contents list name it?' },
    { id: 'abstract',   ask: 'What does the whole recording contain?' }
  ],
  artifact: 'A book whose chapters play cued spans of one recording, with waveforms as figures.'
};

/* ── khwab · visual ───────────────────────────────────────────────────────── */
export const khwab = {
  id: 'khwab', script: 'خواب', room: 'cutting room', output: 'visual',
  purpose: 'Make something to be watched, at any length: a single image, an illustration, a diagram, an animation, a skit, a documentary, a feature, an episodic series.',
  contract: 'A shot is a span of one reel, and the reel travels with the work. Length is not the unit — an image and a series are the same shape at different scales.',
  context: ['the reel or the images', 'its running time if it moves', 'the order a viewer meets it in'],
  state: ['shot boundaries', 'stills grabbed as posters', 'the running order'],
  invariants: ['one image file serves every chapter that cues into it',
               'a still is grabbed from the reel, never generated to look like one'],
  failures: ['a chapter pointing at an image that is not there',
             'panels split into chapters that lose their shared source'],
  evidence: ['the reel sha256', 'a poster per shot, cut from the reel itself'],
  workflow: [
    { id: 'shots',    ask: 'Where does it cut?' },
    { id: 'describe', ask: 'What is on screen here?' },
    { id: 'watch',    ask: 'What should a viewer watch for, and why does it carry the shot?' },
    { id: 'index',    ask: 'How would a contents list name it?' },
    { id: 'abstract', ask: 'What does the whole piece contain?' },
    { id: 'poster',   ask: 'Make a still for this shot.', binary: 'image', optional: true }
  ],
  artifact: 'A book whose chapters play cued spans of one reel.'
};

/* ── tilasm · immersive ───────────────────────────────────────────────────── */
export const tilasm = {
  id: 'tilasm', script: 'طلسم', room: 'staging room', output: 'immersive',
  purpose: 'Build somewhere a person can be: an exhibition, a training environment, a spatial narrative, a virtual laboratory, an interactive place.',
  contract: 'A station is a place, not a moment. There is no timeline and there are no chapters in sequence — a visitor is not on rails, and the work is a graph they walk.',
  context: ['the space it inhabits', 'what hardware it is for', 'what a visitor can physically do there'],
  state: ['stations and their anchors', 'the exit graph between them', 'comfort and reach per station'],
  invariants: ['every station leads somewhere — a piece you cannot move through is a picture',
               'no exit names a station that does not exist',
               'a comfort note exists even when the answer is that nothing is needed'],
  failures: ['a linear reading imposed on a place', 'a hazard with no mitigation offered',
             'assuming a standing visitor with two hands and hearing'],
  evidence: ['the exit graph, traversable', 'a stated floor-space requirement', 'a stated locomotion mode'],
  workflow: [
    { id: 'stations', ask: 'Where does a visitor stand, and what leads where?' },
    { id: 'describe', ask: 'What is seen and heard standing here?' },
    { id: 'act',      ask: 'What can the visitor DO, what answers them, and what if they do nothing?' },
    { id: 'comfort',  ask: 'Who could this hurt, what mitigates it, and what does a visitor who cannot stand do?' },
    { id: 'index',    ask: 'How would a contents list name this station?' },
    { id: 'abstract', ask: 'What does the whole piece contain?' },
    { id: 'asset',    ask: 'Make the model or the panorama for this station.', binary: 'model', optional: true }
  ],
  artifact: 'A navigable graph of stations with assets, anchors, exits and a comfort statement per station.'
};

/* ── pench · embodied ─────────────────────────────────────────────────────── */
export const pench = {
  id: 'pench', script: 'پیچ', room: 'workshop', output: 'embodied',
  purpose: 'Put intent into the physical world: a robot, a cyberphysical system, factory automation, instrumentation, a digital twin, transfer in either direction between simulation and reality.',
  contract: 'The thing described here can move and can injure. It refuses to publish a manoeuvre with no stated operating envelope, and it refuses an invented limit in place of an unknown one.',
  context: ['the platform', 'what is physically near it', 'what has actually been run, and where'],
  state: ['manoeuvres and their preconditions', 'the envelope per manoeuvre', 'the simulation-to-reality gap', 'captured runs'],
  invariants: ['no manoeuvre publishes without an envelope',
               'an unknown limit is written "not established", never estimated',
               'a transfer claim names the hardware run that supports it'],
  failures: ['a plausible torque figure nobody measured', 'a sim2real claim that only ever ran in sim',
             'a stop procedure nobody has tested', 'no account of what happens when a sensor drops out'],
  evidence: ['what a run produced — a log, a bag file, a plot, a capture', 'stated limits, or a stated absence of them'],
  workflow: [
    { id: 'manoeuvres', ask: 'What does it do, in order, and what must be true before each starts?' },
    { id: 'describe',   ask: 'What happens — which actuators, which sensors?' },
    { id: 'envelope',   ask: 'What are the limits, what is in range, how does it stop, and what if power drops?' },
    { id: 'gap',        ask: 'What ran in simulation, what ran on hardware, and where did they disagree?' },
    { id: 'index',      ask: 'How would a runbook name it?' },
    { id: 'abstract',   ask: 'What does the whole body of work contain?' },
    { id: 'evidence',   ask: 'Bring back what an actual run produced — a log, a bag file, a plot, a capture.', binary: 'any', optional: true }
  ],
  artifact: 'A runbook of manoeuvres, each with a precondition, an envelope, a sim-versus-real account and captured evidence.'
};

/* ── yadein · record ──────────────────────────────────────────────────────── */
export const yadein = {
  id: 'yadein', script: 'یادیں', room: 'memory room', output: 'record',
  purpose: 'Keep a life: a diary, an oral history, a family archive, a research notebook, a longitudinal record — accumulated in fragments, out of order, over years.',
  contract: 'This is somebody\'s life, so the default inverts. Nothing publishes unless that entry was marked for it, one entry at a time. Marking everything private is a valid outcome.',
  context: ['when something happened, which is not when it was written', 'who is in it', 'what already exists to attach'],
  state: ['entries by their own date', 'a private/public mark per entry', 'attachments found rather than made'],
  invariants: ['an unmarked entry never reaches a deposit',
               'a vague date stays vague — it is never sharpened into a precise one',
               'a person is named only as the material names them',
               'the count withheld is recorded; the content withheld is not'],
  failures: ['a date guessed to look tidy', 'a surname supplied that the source never gave',
             'a lesson drawn where only a record was asked for', 'publication by default'],
  evidence: ['an explicit mark per entry', 'the source material the entry was made from'],
  workflow: [
    { id: 'entries',  ask: 'What happened, and when — at whatever precision you actually have?' },
    { id: 'record',   ask: 'What happened here? Record it; do not interpret it.' },
    { id: 'hold',     ask: 'What is worth holding on to, for a later reader or a later you?' },
    { id: 'people',   ask: 'Who is in it, named only as the material names them?' },
    { id: 'mark',     ask: 'Is this one private or public?', human: true },
    { id: 'abstract', ask: 'What does the record contain?' },
    { id: 'attach',   ask: 'Find the photograph, the voice note, the scan that belongs here.', binary: 'any', optional: true }
  ],
  artifact: 'A dated record of marked entries with their attachments, accumulating toward identity continuity.'
};

export const WORKFLOWS = { matba, awaz, khwab, tilasm, pench, yadein };

export const REQUIRED = ['purpose', 'contract', 'context', 'state', 'invariants',
                         'failures', 'evidence', 'workflow', 'artifact'];

/** Every vocabulary that belongs to exactly one cycler. Used to catch a leak. */
export const VOCABULARY = {
  matba:  ['plate', 'forme', 'impression', 'jacket', 'chase', 'quoin'],
  awaz:   ['passage', 'waveform', 'transcript', 'listener', 'recording'],
  khwab:  ['shot', 'reel', 'still', 'viewer', 'on screen'],
  tilasm: ['station', 'anchor', 'exit', 'visitor', 'locomotion', 'floor space'],
  pench:  ['manoeuvre', 'envelope', 'actuator', 'sim2real', 'precondition'],
  yadein: ['entry', 'withheld', 'private', 'attachment']
};

/** Words that describe a cued span of a media file. Meaningless for tilasm, pench, yadein. */
export const TIMELINE_WORDS = ['cue', 'cued', 'timecode', 'span of one', 'cut copies', 'running time'];
export const TIMELINE_OK = ['awaz', 'khwab'];

export function declared(id) {
  const w = WORKFLOWS[id];
  if (!w) return { ok: false, why: 'no such cycler: ' + id };
  const missing = REQUIRED.filter(k => !w[k] || (Array.isArray(w[k]) && !w[k].length));
  return { ok: !missing.length, missing };
}

/** Does this cycler's text borrow a sibling's vocabulary? That is the leak that shipped. */
const WORD = w => new RegExp('\\b' + w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + 's?\\b', 'i');

export function leaks(id, text) {
  // Word boundaries, not substrings: "exit" must not fire inside a longer word in a URL, and
  // "plate" must not fire inside "template". A trailing "s" still counts — a leak is a leak in the plural.
  const t = String(text);
  const found = [];
  for (const [other, words] of Object.entries(VOCABULARY)) {
    if (other === id) continue;
    for (const w of words) if (WORD(w).test(t)) found.push({ from: other, word: w });
  }
  if (!TIMELINE_OK.includes(id))
    for (const w of TIMELINE_WORDS) if (WORD(w).test(t))
      found.push({ from: 'a timeline it does not have', word: w });
  return found;
}
