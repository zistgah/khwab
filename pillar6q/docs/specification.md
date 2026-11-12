# Pillar 6Q production fixture

`examples/full_production_spec.json` is an illustrative full document using the
`pillar6qDocument` root in `crowd_cinema_spec.schema.yaml`. The schema also
accepts the legacy single-shot form. The production fixture uses only fields
declared by the full-document schema.

## Entity model

- **Platform and project** identify the local example and its overall
  canonical-classical framing. The project makes clear that this label is not a
  scholarly or religious finding.
- **Source lineage** declares the two bundled illustrative TEI files. Witnesses
  and a passage connect their fixture readings to shots through `source_ids`
  and `passage_ids`. Canonical basis and speculative disclosure use the
  schema's `source_lineage` fields.
- **Scenes and shots** contain two 12-second shots in a
  `CANONICAL_CLASSICAL` scene and two in a distinct `SPECULATIVE_ALTERNATE`
  scene. Each shot nests start/end placeholder keyframes and carries its
  declared source and passage references.
- **Render, review, and voting** use the schema's `render_tasks`, `findings`,
  `vote_policy`, and `votes`. There are no render tasks or takes; findings say
  `not_run`, and there are no votes or outcomes.
- **Timeline** is a planned 24 fps sequence of the four shots, using integer
  presentation timestamps and a 1/24 time base. It is not a rendered or
  validated media timeline.
- **Localizations** list all 22 Scheduled Indian languages and the 16 global
  languages in the project metadata registry. The schema represents
  not-supplied translations with `translation_status: "not_started"` and
  empty `cues`; `notes` clarifies that no text is supplied. No audio tracks are
  present.
- **Provenance and safety** contain explicitly non-person placeholder
  contributors, no contribution events, no hazard ratings, and a pending
  screening summary. The declared proof status is `not_a_formal_proof`.

## Nonclaims

`validation_notice`, field notes, and this document describe limits, not
verification. The `examples/tei/` texts are illustrative fixtures, not
scholarly editions. Source IDs record declared lineage and do not establish
authenticity, scholarly interpretation, or support for any depicted action.
The canonical genre is a planning label. The lantern and doorway are invented
and must remain labeled speculative.

No actual generated video, keyframe image, render metric, translation, audio,
vote, review decision, real contributor, cryptographic signature, verification
receipt, or formal proof is included. JSON Schema validation checks structure
and declared values only; it does not verify identities, sources, providers,
signatures, timestamps, motion, media quality, safety, or accessibility.
