/* media.js — the `video` / `audio` block for kitab.
 *
 * One file serves every chapter; each chapter plays its own cued span. The element seeks to the
 * cue on play and stops at the out point, so a reel reads as chapters without being cut up.
 * A talking artifact like every kitab figure: Explain, speak, and hand off to your AI.
 */
export function mount(root, block, ctx) {
  const kind = block.type === 'audio' ? 'audio' : 'video';
  const fig = document.createElement('figure');
  fig.className = 'k-media k-' + kind;
  const el = document.createElement(kind);
  el.controls = true; el.preload = 'metadata'; el.src = block.src;
  if (block.poster && kind === 'video') el.poster = block.poster;
  el.setAttribute('aria-label', block.alt || block.caption || 'media');

  const inPt = Number(block.start) || 0;
  const outPt = Number(block.end) || 0;
  const seek = () => { if (el.currentTime < inPt || (outPt && el.currentTime > outPt)) el.currentTime = inPt; };
  el.addEventListener('loadedmetadata', seek);
  el.addEventListener('play', seek);
  el.addEventListener('timeupdate', () => {
    if (outPt && el.currentTime >= outPt) { el.pause(); el.currentTime = inPt; }
  });

  const cap = document.createElement('figcaption');
  const tc = s => { s = Math.round(s || 0); return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0'); };
  cap.innerHTML = '<span class="k-cue">' + tc(inPt) + (outPt ? '–' + tc(outPt) : '') + '</span> ' +
                  (block.caption || '');
  fig.append(el, cap);

  const bar = document.createElement('div');
  bar.className = 'k-artifact';
  const btn = (label, fn) => { const b = document.createElement('button'); b.type = 'button';
    b.textContent = label; b.onclick = fn; bar.append(b); return b; };
  if (block.explanation) {
    const p = document.createElement('p'); p.className = 'k-explain'; p.hidden = true;
    p.textContent = block.explanation; fig.append(p);
    btn('Explain', () => { p.hidden = !p.hidden; });
  }
  if (block.tts && typeof speechSynthesis !== 'undefined') {
    btn('Speak', () => {
      const t = (block.explanation || block.caption || '');
      speechSynthesis.cancel(); speechSynthesis.speak(new SpeechSynthesisUtterance(t));
    });
  }
  if (block.seed && block.seed.enabled && block.seed.prompt) {
    btn('Ask AI', async () => {
      try { await navigator.clipboard.writeText(block.seed.prompt); bar.dataset.note = 'prompt copied'; }
      catch (e) { bar.dataset.note = block.seed.prompt; }
    });
  }
  if (bar.children.length) fig.append(bar);
  root.append(fig);
  return { destroy() { try { el.pause(); } catch (e) {} fig.remove(); } };
}
export default { mount };
