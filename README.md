# khwab (خواب) — the cutting room

A reel goes in. A published book comes out: cued chapters, checked, sealed, timestamped and minted
with a DOI. On your own machine, with your own tokens, with whichever AI you already use.

```bash
curl -O https://raw.githubusercontent.com/zistgah/khwab/main/khwab.py
python3 khwab.py serve        # cutting room at http://127.0.0.1:8711/studio
```

Or open the static page with nothing installed — it works from the site, from the local server, or
embedded in someone else's page: **[the cutting room](https://zistgah.github.io/khwab/studio.html)**.
Or **[open in Colab](https://colab.research.google.com/github/zistgah/khwab/blob/main/khwab.ipynb)**.

## The loop is one button

The old cycler was a form: copy a prompt, go away, come back, find the right box, paste, press.
Four decisions a step. This one:

1. **Press 1** — the prompt goes to your clipboard.
2. Paste it into whichever AI you use, with the reel. Copy the answer.
3. **Press 2** — it *reads your clipboard*, works out which step the answer belongs to, files it,
   and copies the next prompt.

You never choose a field. Pasting anywhere on the page does the same thing. If the browser refuses
the clipboard, the same button opens a paste box — it never dead-ends.

## Which AI? Yours.

The AI source table **ships empty**. No service is named, defaulted to or suggested anywhere in this
repository — you add the ones you use, by name and address, and they are kept in your browser. Three
ways to reach one: open it in a tab (most AIs), call an address, or a server on this machine.

Seeding is not tied to any one AI. That is the invariance clause, made concrete.

## Coming back with a file

Text returns on the clipboard. An image, a reel, a track or a mesh does not — you save it out of
whichever AI you used and come back. That return is a first-class step here.

Press your AI's button and the cutting room notes what is in your folder *before* you go. When you
return it shows you what is **newly visible**, and you pick the one that belongs to this step.

**Three mechanisms, because no single one works everywhere.**

| | works where | what it gives |
|---|---|---|
| **This machine** | `khwab serve` is running | the folder is read by the local server, which is the only thing that can see it on most platforms |
| **Watch a folder** | desktop Chromium | the browser reads a folder you granted, once you grant it |
| **Choose files** | everywhere, including phones | the platform's own picker |

**And one rule the whole panel obeys: filesystem visibility is not provenance.** The folder holds
photographs, documents, other AIs' output and files another program wrote. The panel says *"three
new files are visible"* — never *"three files your AI made"* — and an imported artefact records
`operator-selected`, with nobody claimed as its author. Tests assert that wording.

Nothing is assumed. Not the folder — the roots are discovered on your machine and you switch between
them. Not the count — a hundred files is a hundred files, previewed, sorted and filtered. Not the
type — a step says what it expects and dims the rest, but never stops you choosing something else.

## Answer it locally instead

Two request shapes are offered for a server running on your own machine. Both are keyless and
nothing leaves the machine. A remote address with your own key works identically. **No service is
named, defaulted to or suggested anywhere in this repository.**

## What it seeds

A **kitab-shaped** book: `index.html` at root, `js/`, `readers/`, `assets/theme/` from the template
verbatim; `config/`, `content/` and `assets/` ours. The only new part is `readers/media.js`, a block
that plays a cued span. It reads in the same reader as every other book in the estate.

Chapters are **cues into one file**, not cut copies. One file, one hash, one deposit. The reel is
minted with the book.

## Commands

```
khwab serve                        the cutting room + the run panel
khwab import <slug> payload.zip    bring a studio export into a project
khwab doctor <slug>                exits 1 on any failure
khwab build  <slug>                seeder + tarball
khwab run    <slug> stage|push|mint
```

Gate words are `PUSH seed` and `MINT <slug>`. A mismatch exits 3 and records nothing.

## Note on the plates

Where a poster or a reel in this repository names a repository, a DOI or a figure that does not
exist, **the canon in `zistgah/governance` governs, not the artwork.** The plates record intent; the
contract records fact.

---

Copyright © 1993–2026 Abhishek Choudhary · AyeAI · ORCID 0009-0002-0684-8320 · Apache-2.0
*Kaivalyik Immutabilis*
