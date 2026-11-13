# Pillar 6Q GitOps Workflow

This document describes the declarative lifecycle in
[`workflow/crowd_cinema_workflow.json`](../workflow/crowd_cinema_workflow.json)
and the implementation evidence summarized in
[`workflow/requirements_traceability.json`](../workflow/requirements_traceability.json).
The workflow defines human review responsibilities and routing; it does not
claim that every stage is automated or that a release contains verified media.

## RACI and notifications

For each stage, its `owner_role` is Responsible (R) for preparing the stage
record and Accountable (A) for its human decision. Consulted (C) roles are the
adjacent artifact owners and relevant subject reviewers. The GitHub issue
intake action mentions the reporter and, when configured, the routed stage
owner. Other RACI roles are not automatically notified unless they are listed
as the configured role mention or subscribe to the Issue. For post-release
work, the feedback triager is R/A for triage, while the confirmed artifact
owner becomes R/A for the proposed artifact change.

`notification_variable` contains a repository-variable **key**, not a GitHub
handle. Configure each key in the repository's Actions variables with the real,
mentionable GitHub username or team handle for the assigned role. Do not put
placeholder or invented handles in the manifest. Team assignments can be
changed by updating the variable value without changing the stable role ID.

| Role | R/A stage and responsibility | Consulted (C) | Informed (I) | Repository variable key |
|---|---|---|---|---|
| `source_steward` | `source_intake`; source lineage and rights claims | `textual_editor`, `assurance_lead` | `feedback_triager` | `CROWD_CINEMA_NOTIFY_SOURCE_STEWARD` |
| `textual_editor` | `textual_collation`; witnesses, readings, and textual review | `source_steward`, `adaptation_lead` | `feedback_triager` | `CROWD_CINEMA_NOTIFY_TEXTUAL_EDITOR` |
| `adaptation_lead` | `adaptation`; passage mapping and genre disclosure | `textual_editor`, `shot_designer` | `feedback_triager` | `CROWD_CINEMA_NOTIFY_ADAPTATION_LEAD` |
| `shot_designer` | `shot_design`; scenes, shots, and keyframes | `adaptation_lead`, `volunteer_coordinator` | `technical_reviewer` | `CROWD_CINEMA_NOTIFY_SHOT_DESIGNER` |
| `volunteer_coordinator` | `volunteer_render`; task and take records | `shot_designer`, `technical_reviewer` | `feedback_triager` | `CROWD_CINEMA_NOTIFY_VOLUNTEER_COORDINATOR` |
| `technical_reviewer` | `technical_review`; findings and declared checks | `volunteer_coordinator`, `community_moderator` | `assurance_lead` | `CROWD_CINEMA_NOTIFY_TECHNICAL_REVIEWER` |
| `community_moderator` | `community_selection`; vote policy, quorum, and appeals | `technical_reviewer`, `assurance_lead` | `release_manager` | `CROWD_CINEMA_NOTIFY_COMMUNITY_MODERATOR` |
| `assembly_editor` | `assembly`; timeline and media references | `community_moderator`, `localization_lead` | `assurance_lead` | `CROWD_CINEMA_NOTIFY_ASSEMBLY_EDITOR` |
| `localization_lead` | `localization`; supplied text, subtitle cues, and declared audio | `assembly_editor`, `assurance_lead` | `release_manager` | `CROWD_CINEMA_NOTIFY_LOCALIZATION_LEAD` |
| `assurance_lead` | `release_assurance`; release evidence and limitations | Relevant artifact owners | `release_manager`, `feedback_triager` | `CROWD_CINEMA_NOTIFY_ASSURANCE_LEAD` |
| `release_manager` | `release`; versioned release record | `assurance_lead`, affected artifact owner | `feedback_triager` | `CROWD_CINEMA_NOTIFY_RELEASE_MANAGER` |
| `feedback_triager` | `post_release_feedback`; issue triage and owner confirmation | The owner selected from `artifact_owners` | Reporter, `release_manager` when applicable | `CROWD_CINEMA_NOTIFY_FEEDBACK_TRIAGER` |

These are role notifications, not a RACI assignment of actual GitHub accounts.
The current router can return a role's variable key; a notification is sent
only by an Actions workflow that consumes that result and runs with the
variable configured.

## Lifecycle stages

The forward lifecycle is ordered in the manifest. Stage entry and exit arrays
contain gate IDs; every ID resolves to a gate object. A gate's `stage_id`
identifies the stage that owns/evaluates it. A transition uses a gate owned by
its `from_stage`. Entry gates can therefore reference an upstream stage's
completed gate, or the post-release triager's owner-confirmation gate.

| Order | Stage | Owner | Forward gate and review intent |
|---:|---|---|---|
| 1 | `source_intake` | `source_steward` | `source_lineage_reviewed`: record citations, source links, rights notes, and uncertainties; do not infer authenticity. |
| 2 | `textual_collation` | `textual_editor` | `collation_reviewed`: parse TEI apparatus as data and have a human review readings and interpretation. |
| 3 | `adaptation` | `adaptation_lead` | `adaptation_approved`: link the brief to reviewed passages and preserve genre/speculative disclosures. |
| 4 | `shot_design` | `shot_designer` | `shot_manifest_approved`: validate shot structure and obtain human continuity/content review. |
| 5 | `volunteer_render` | `volunteer_coordinator` | `render_take_submitted`: record a task, provider declaration, take, and artifact reference; this is not a remote render queue. |
| 6 | `technical_review` | `technical_reviewer` | `technical_review_passed`: record findings, methods, and evidence without claiming video decoding or proof of media quality. |
| 7 | `community_selection` | `community_moderator` | `community_selection_met`: apply the declared local quorum/tally policy; identity and reputation claims remain unverified. |
| 8 | `assembly` | `assembly_editor` | `timeline_assembled`: validate timeline continuity and OTIO metadata; optional local FFmpeg stream-copy stitching is limited to compatible video-only H.264 clips. |
| 9 | `localization` | `localization_lead` | `localization_ready`: check supplied localization text and cue windows; no translation or audio is generated. |
| 10 | `release_assurance` | `assurance_lead` | `release_gate_passed`: collect available CI, schema, safety, provenance, and review evidence with limitations stated. |
| 11 | `release` | `release_manager` | `release_published`: record a versioned package and release notes; publishing infrastructure is not present here. |
| 12 | `post_release_feedback` | `feedback_triager` | `post_release_owner_confirmed`: confirm an artifact owner or retain the report in triage; never auto-edit an artifact. |

## Review gates

The manifest's top-level `gates` array is the gate catalogue. Each gate has a
stable ID, owning stage, title, explicit criteria, verification references,
and a status:

- `implemented`: the stated check is supported by an existing executable check
  for its defined scope.
- `partial`: some structure or local check exists, but a human decision,
  external verifier, or capability limit remains.
- `planned`: the operational check or integration is not implemented.

`verification.status` distinguishes `available` evidence references from
`manual_required` review and `not_implemented` integrations. An available
schema or test is not a claim that a real production artifact passed it. The
gate status must reflect the narrowest applicable limitation; for example,
the C motion check can inspect supplied buffers but does not decode video or
prove liveness.

Before a forward transition, the source stage's exit gate must be satisfied
and its evidence attached to the change. For an upstream transition, the
finding and evidence are recorded first, then the destination owner reviews
the correction. A gate declaration does not itself enforce the decision:
human approvals and artifact-level evidence must be captured in the Issue/PR
and its review history.

## Upstream feedback routes

`source_stages` names plausible downstream stages where a finding is detected;
`target_stage` is where it returns for review or triage. Each source/target pair
is represented by a transition whose gate is owned by the source stage.

| Event | Detection stages (`source_stages`) | Return target |
|---|---|---|
| `source_provenance` | `textual_collation`, `release_assurance`, `post_release_feedback` | `source_intake` |
| `attestation_rejected` | `technical_review`, `release_assurance`, `post_release_feedback` | `textual_collation` |
| `canonical_mismatch` | `release_assurance`, `post_release_feedback` | `adaptation` |
| `storyboard_defect` | `technical_review`, `post_release_feedback` | `shot_design` |
| `render_failure` | `technical_review`, `post_release_feedback` | `volunteer_render` |
| `liveness_failure` | `technical_review`, `post_release_feedback` | `volunteer_render` |
| `anachronism_flag` | `technical_review`, `post_release_feedback` | `adaptation` |
| `vote_appeal` | `community_selection`, `release_assurance`, `post_release_feedback` | `community_selection` |
| `timeline_continuity` | `release_assurance`, `post_release_feedback` | `assembly` |
| `translation_correction` | `localization`, `release_assurance`, `post_release_feedback` | `localization` |
| `subtitle_timing` | `localization`, `release_assurance`, `post_release_feedback` | `localization` |
| `dub_audio_issue` | `localization`, `release_assurance`, `post_release_feedback` | `localization` |
| `provenance_credits` | `release`, `post_release_feedback` | `release_assurance` |
| `release_defect` | `post_release_feedback` | `post_release_feedback` by default; a single recognized typed artifact may route to its owner |
| `general_feedback` | `release`, `post_release_feedback` | `post_release_feedback` |

Reports use the parser's issue-form keys: `summary`, `observed_behavior`,
`expected_behavior`, `affected_artifacts`, `evidence_links`, and `priority`.
For a source or artifact URI, place the URI in `evidence_links`; do not invent
an additional form field. `release_defect` remains with the feedback triager
when the artifact type is unknown or spans owners. A typed-owner route is a
request for that owner to review, not a fix.

## Contribution routes

The manifest also declares these work-request/PR-proposal categories. A
contribution route assigns a proposed artifact to a stage owner; it does not
attest an identity, generate media or translations, approve a scholarly claim,
or cast a formal vote. Each label is exactly
`workflow:contribution:<contribution_type>`.

| Contribution type | Target stage |
|---|---|
| `source_material` | `source_intake` |
| `transcription` | `textual_collation` |
| `scholarly_review` | `textual_collation` |
| `adaptation_proposal` | `adaptation` |
| `shot_blueprint` | `shot_design` |
| `render_take` | `volunteer_render` |
| `technical_review` | `technical_review` |
| `assembly_change` | `assembly` |
| `localization_text` | `localization` |
| `voice_or_audio` | `localization` |
| `provenance_credit` | `release_assurance` |
| `release_package` | `release` |

Contribution `required_fields` are restricted to the same parser keys listed
above. `evidence_links` carries source/artifact URI evidence. The route table
also gives each type a default priority, which a submitted `priority` heading
can override. The local issue router can return the declared stage/role for a
contribution event, but that result does not import an uploaded artifact,
change GitHub state, or open a PR. A configured Action and human-reviewed PR
remain necessary for operational intake.

## GitOps operating procedure

1. **Open an Issue.** Choose either the `Feedback type` or `Contribution type`
   heading, then use the exposed headings: summary, observed behavior,
   expected behavior, affected artifacts, evidence links, and priority. For a typed artifact, use
   `artifact_type:artifact_id` in the affected-artifacts field; put external
   source and artifact URIs in evidence links.
2. **Route the request.** The current local issue router accepts a GitHub issue
   event document and returns a target stage/role, labels, route reason, and
   `notification_variable`. The intended command is
   `python -m crowd_cinema workflow route-issue --event-path <event.json>`.
   Missing or ambiguous fields should be clarified rather than silently
   treated as approval. Contribution routing produces a proposal assignment,
   not an artifact import or approval.
3. **Notify the assigned role.** The
   [`crowd-cinema-workflow.yml`](../.github/workflows/crowd-cinema-workflow.yml)
   issue action resolves the returned variable key and mentions the configured
   role in the routing comment. Notifications only happen when Actions run;
   there is no always-on server. The separate CI workflow validates code and
   matrices on pushes and pull requests. The action does not assign arbitrary
   users or guarantee GitHub's delivery of a team mention.
4. **Propose the artifact change.** The owner works on a branch and opens a PR
   linked to the Issue. Change canonical JSON/specification artifacts, not
   generated evidence or release output without review. Keep the issue, file
   path, artifact ID, and proposed correction linked.
5. **Attach CI and gate evidence.** Run the workflow/matrix check and relevant
   tests. The repository CI workflow runs the Python unittest suite and C11
   checks on push and pull request. Attach the actual results plus manual gate
   review notes; passing CI alone does not satisfy a human gate.
6. **Review and merge.** The accountable owner reviews the artifact change;
   consulted subject reviewers examine relevant claims. Record approvals and
   unresolved limitations in the PR before merge. No route auto-merges or
   edits a file.
7. **Release deliberately.** After merge, the release manager records a new
   release version and notes. A branch, Issue, PR, and commit become visible
   in hosted GitHub history only when the repository and changes are online
   (branches/commits require push).

## Post-release corrections and versioning

An Issue should identify the affected release version, artifact type/ID, and
evidence. The router sends a `release_defect` to `post_release_feedback` by
default. If exactly one recognized artifact type is cited, the local router
can return that artifact's declared owner; if ownership is unknown or spans
stages, the feedback triager keeps the case and splits it only after review.
This is triage, not a fictional automatic repair.

The confirmed artifact owner proposes a correction in a PR linked to the
Issue. The PR contains the changed canonical artifact, relevant gate evidence,
and review record. After merge, publish a **new** release version with updated
revision/release notes and links to the superseded version and corrective PR.
Do not silently overwrite an earlier release or imply that a correction was
published before its review and release steps complete.

## Current limits

- There is no always-on server or volunteer-render service. The exchange is a
  local SQLite facility; it is not a remote queue or Sybil-resistant identity
  system.
- The issue action sends role mentions only when a repository variable is
  configured with a real, mentionable GitHub user/team handle and the workflow
  runs in the hosted repository. The CI workflow tests code and matrices; it
  is separate from notification routing.
- The issue router produces a routing result; the GitHub issue action applies
  labels and comments on the hosted Issue. It mentions the reporter and a
  configured role handle but does not assign users. A local command alone does
  not alter GitHub state.
- Issues and PRs are GitHub online objects once the project is hosted. Local
  work is not online history until the corresponding branch/commit is pushed.
- SHA-256 and Ed25519 verification check exact bytes against a caller-supplied
  key; they do not authenticate the key owner, source authority, or provider.
  OpenTimestamps receipt parsing is not trusted timestamp verification. The
  repository does not implement C2PA verification, generated renders,
  translation/audio synthesis, formal CBMC/Z3 proofs, or MISRA certification.
- OTIO export validates ordered timeline metadata. Optional FFmpeg assembly
  requires installed ffmpeg/ffprobe and compatible local video-only H.264 clips;
  it does not provide decoded-frame accuracy, color grading, or A/V sync.
- Local release bundles are reproducible and integrity-tagged, but unsigned
  and unpublished. Release publication and post-release correction remain
  human GitOps procedures, not automated deployment or auto-fix pipelines.
