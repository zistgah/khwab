/* khwab.js (خواب — the dream) — the creativity cycle for moving pictures.
 *
 * A reel goes in. Shots come out, each with a title, a beat, a description and a cue. The book it
 * builds is kitab-shaped, so it reads in the same reader as every other book in the estate — the
 * only new thing is a `video` block that plays a cued span of the reel.
 */
import { fill, queue, apply, progress } from './cycler.js';

export const STEPS = [
  { id: 'shots', title: 'Break it into shots', target: 'shots', array: true, expect: 'text', jsonKeys: ['start', 'title'],
    prompt:
`You are given a reel from "{book}"{subtitle}, {duration} long.

Break it into shots. Reply with ONLY a JSON array, in order:

[{"start":"0:00","end":"0:07","title":"…","beat":"…"}]

start/end: m:ss timecodes.
title: how a contents list would name the shot, under 60 characters.
beat: one clause naming what changes in it.
If the reel is a single unbroken shot, return an array of length 1.` },

  { id: 'describe', title: 'Describe the shot', target: 'lead', expect: 'text',
    prompt:
`Shot {n} of "{book}", {start}–{end}, titled "{title}".

Write ONE paragraph of 50–90 words describing what is on screen, in the vocabulary the reel itself
uses. State what happens; do not praise it and do not explain its significance.

Reply with the paragraph only.` },

  { id: 'cue', title: 'What to watch for', target: 'explanation', expect: 'text',
    prompt:
`Same shot: "{title}", {start}–{end}.

Write ONE paragraph of 50–90 words naming the single thing a viewer should watch for, and why it
carries the shot rather than decorating it. Preserve any hedging the reel uses.

Already written:
{lead}

Reply with the paragraph only.` },

  { id: 'index', title: 'Title and index terms', target: 'topics', expect: 'text', jsonKeys: ['topics'],
    prompt:
`Same shot. Reply with ONLY this JSON:

{"title":"…","subtitle":"…","topics":["…","…","…"]}

topics: 3–5 lowercase index terms taken from the reel's own vocabulary.` },

  { id: 'abstract', title: 'The abstract', target: '@description', once: true, expect: 'text',
    prompt:
`Write the deposit abstract for "{book}"{subtitle}, a reel of {duration} in {count} shots, as 2–3
HTML paragraphs in <p> tags. State what the work contains, not why it matters. No first person,
no marketing language.

Shots:
{toc}

Reply with the HTML only.` }
  ,
  /* A BINARY step: the answer is a FILE, so it returns through the artefact inbox rather than the
     clipboard. Optional, so it never blocks the cycle — a reel may not need stills made for it. */
  { id: 'poster', title: 'A still for the shot', target: 'poster',
    expect: 'image', optional: true, binary: true,
    prompt:
`Make a single still image for shot {n} of "{book}", titled "{title}" ({start}-{end}).

{lead}

One image. No text baked in unless the shot itself carries text. When it is made, save it to your
device and come back: the cutting room will show what is newly visible in your folder, and you pick
the one that belongs to this shot.` }
];

export const slugify = s => String(s).toLowerCase().replace(/\.[a-z0-9]+$/, '')
  .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').replace(/-+/g, '-') || 'shot';

export const toSeconds = t => {
  const p = String(t || '0').split(':').map(Number).reverse();
  return (p[0] || 0) + (p[1] || 0) * 60 + (p[2] || 0) * 3600;
};
export const toTimecode = s => {
  s = Math.max(0, Math.round(Number(s) || 0));
  const m = Math.floor(s / 60), r = s % 60;
  return m + ':' + String(r).padStart(2, '0');
};

export function context(state, subject) {
  const i = state.subjects.indexOf(subject);
  return {
    book: state.book.title || 'this reel',
    subtitle: state.book.subtitle ? ' — ' + state.book.subtitle : '',
    duration: toTimecode(state.book.duration || 0),
    count: state.subjects.length,
    n: i + 1,
    title: subject ? (subject.title || 'untitled') : '',
    start: subject ? (subject.start || '0:00') : '',
    end: subject ? (subject.end || '') : '',
    lead: subject ? (subject.lead || '') : '',
    toc: state.subjects.map((s, k) =>
      `${k + 1}. ${s.start || '?'}–${s.end || '?'}  ${s.title || 'untitled'}`).join('\n')
  };
}

export function nextTask(state) {
  const q = queue(state.subjects, STEPS, state.book);
  return q.length ? q[0] : null;
}

export function promptFor(state, task) {
  return fill(task.step.prompt, context(state, task.subject));
}

export { apply, progress };

/* ── the doctor ─────────────────────────────────────────────────────────── */
export function doctor(state) {
  const f = [];
  if (!state.book.reel) f.push('No reel. Drop a video file.');
  if (!state.subjects.length) f.push('No shots yet. Run the first step of the cycle.');
  if (!state.book.title) f.push('No title.');
  if (!state.book.description) f.push('No abstract. A deposit with a blank abstract is permanent too.');
  if (!/^[^/\s]+\/[^/\s]+$/.test(state.book.repo || '')) f.push('Repository must be owner/name.');
  const ids = state.subjects.map(s => s.id);
  new Set(ids.filter(x => ids.filter(y => y === x).length > 1)).forEach(x => f.push('Duplicate shot id: ' + x));
  let last = -1;
  state.subjects.forEach((s, i) => {
    if (!s.title) f.push('Shot ' + (i + 1) + ' has no title.');
    if (!s.lead) f.push('Shot ' + (i + 1) + ' has no description.');
    const a = toSeconds(s.start), b = toSeconds(s.end);
    if (s.end && b <= a) f.push('Shot ' + (i + 1) + ' ends before it starts.');
    if (a < last) f.push('Shot ' + (i + 1) + ' starts before the previous one ends.');
    if (state.book.duration && b > state.book.duration + 1)
      f.push('Shot ' + (i + 1) + ' runs past the end of the reel.');
    last = b || a;
  });
  return f;
}

/* ── payload — kitab-shaped, so it reads in the same reader ─────────────── */
export function buildPayload(state) {
  const b = state.book, chapters = [], content = {}, parts = [];
  const partOf = s => s.part || 'The Reel';
  const order = [...new Set(state.subjects.map(partOf))];
  let n = 0;
  for (const title of order) {
    const ids = [];
    for (const s of state.subjects.filter(x => partOf(x) === title)) {
      n++; const cid = 'ch-' + String(n).padStart(2, '0');
      const start = toSeconds(s.start), end = toSeconds(s.end);
      content[cid] = {
        id: cid, title: s.title, subtitle: s.subtitle || (s.start + '–' + s.end),
        blocks: [
          { type: 'paragraph', text: s.lead },
          { type: 'video', id: s.id, src: 'assets/' + (b.reel || 'reel.mp4'),
            poster: 'assets/figures/' + s.id + '.png',
            start, end, alt: s.title,
            caption: s.subtitle ? s.title + ' — ' + s.subtitle : s.title,
            explanation: s.explanation || s.lead, tts: true,
            seed: { enabled: true, prompt: fill(b.seedPrompt || '', context(state, s)) } },
          ...(b.plateNote ? [{ type: 'callout', variant: 'note', text: b.plateNote }] : []),
          ...(s.exercises && s.exercises.length ? [{ type: 'exercise', id: cid + '-ex', items: s.exercises }] : [])
        ]
      };
      chapters.push({ id: cid, number: n, title: s.title,
                      subtitle: s.subtitle || (s.start + '–' + s.end),
                      source: 'content/' + cid + '.json', topics: s.topics || [] });
      ids.push(s.id);
    }
    parts.push({ id: slugify(title), title, chapters: ids });
  }
  return {
    'book.config.json': {
      meta: { title: b.title, subtitle: b.subtitle || '', author: b.author, affiliation: b.affiliation,
              orcid: b.orcid, copyright: `Copyright (c) ${b.copyrightYears || '1993-2026'} ${b.author}. All rights reserved.`,
              license: b.license || 'CC-BY-SA-4.0', doi: null, repo: b.repo,
              cover: 'assets/figures/cover.png', language: 'en',
              media: { kind: 'video', file: 'assets/' + (b.reel || 'reel.mp4'),
                       duration: b.duration || 0, sha256: b.reelSha || null } },
      theme: { tokens: b.tokens || { '--ink': '#0a0e27', '--acc': '#d4a843', '--light': '#fbf6e9' } },
      structure: { parts, chapters }
    },
    'index.json': { generator: 'khwab', book: b.title, kind: 'video',
                    reel: { file: 'assets/' + (b.reel || 'reel.mp4'), sha256: b.reelSha || null,
                            duration: b.duration || 0 },
                    shots: state.subjects.map((s, i) => ({
                      chapter: 'ch-' + String(i + 1).padStart(2, '0'), id: s.id, title: s.title,
                      start: toSeconds(s.start), end: toSeconds(s.end) })) },
    content, chapterCount: chapters.length
  };
}
