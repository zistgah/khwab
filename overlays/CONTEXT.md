# CONTEXT — a khwab-seeded media book

**What this is.** A kitab-derived book whose chapters are cued spans of one media file. The reel or
recording sits in `assets/`; each chapter declares `start` and `end`, and `readers/media.js` plays
that span. Everything else — the reader, the theme, the AI seeding, the contribution paths — is
kitab's, unchanged.

**Why cues rather than cuts.** A cut copy per chapter multiplies the artifact and breaks the claim
that one recording was published. Cues keep one file, one hash, one deposit.

**Provenance.** The media file's sha256 is recorded in `config/book.config.json` under
`meta.media`, and the whole tree is sealed in `MANIFEST.sha256` before the push.

**Disclaimer carried on the plates.** Where a poster or a reel names a repository, a DOI or a
figure that does not exist, the canon in `zistgah/governance` governs, not the artwork. The plates
are records of intent; the contract is the record of fact.
