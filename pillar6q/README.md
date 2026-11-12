# Crowdsourced Scripture & Multiverse Cinema Factory

The executable specification workspace combines TEI collation and export,
content/signature checks, deterministic local release bundles, OTIO timeline
assembly, optional local FFmpeg media stitching, instructional notebooks,
GitOps workflow routing, and bounded review checks. A dependency-free C11
library covers authority quorum checks, deterministic vote tallies, zone-motion
activity checks, and SHA-256 frame chains.

The canonical schema is JSON-compatible YAML in
`crowd_cinema_spec.schema.yaml`, allowing it to be parsed with Python's
standard-library JSON reader.

Open `docs/index.html` directly in a browser to preview a shot JSON file.
The static page validates the blueprint locally and does not upload it, play
video, or record votes.

## Run

Requires Python 3.11 or newer. From this directory:

```powershell
$env:PYTHONPATH = "src"
python -m pip install -e ".[test]"
python -m unittest discover -s tests -v
python -m crowd_cinema --help
```

The package can be run from this directory without installation. For example:

```powershell
$env:PYTHONPATH = "src"
python -m crowd_cinema collate examples/tei/recension-a.xml examples/tei/recension-b.xml
python -m crowd_cinema collate examples/tei/recension-a.xml examples/tei/recension-b.xml --tei-output merged-collation.xml
python -m crowd_cinema compile-shot examples/shot.json
python -m crowd_cinema formal-check
python -m crowd_cinema release-bundle --output release-1.0.0.zip 1.0.0 README.md examples/shot.json
$digest = (Get-FileHash path\to\source -Algorithm SHA256).Hash
python -m crowd_cinema verify-attestation path\to\source --sha256 $digest
python -m crowd_cinema gymnasium check notebooks\01-tei-collation.ipynb notebooks\02-genre-shot-blueprint.ipynb notebooks\03-local-render-task-packet.ipynb notebooks\04-exchange-voting.ipynb notebooks\05-workflow-formal-check-limitations.ipynb
python -m crowd_cinema gymnasium export notebooks/01-tei-collation.ipynb --output studio.html
```

## GitOps lifecycle and feedback

The Git-tracked [workflow manifest](./workflow/crowd_cinema_workflow.json)
defines stages, owners, gates, contribution intake, feedback routes, artifact
ownership, and notification-variable names. The
[requirements traceability matrix](./workflow/requirements_traceability.json)
links requirements to stages, artifacts, and verification evidence.

Validate the matrices and generate the static lifecycle/traceability snapshot:

```powershell
python -m crowd_cinema workflow check
python -m crowd_cinema workflow board --output docs/workflow-board.html
python -m crowd_cinema workflow route-issue --event-path examples/workflow/liveness-failure.issue.json
```

GitHub Issue Forms provide [contribution requests](./.github/ISSUE_TEMPLATE/workflow_contribution.yml)
and [feedback reports](./.github/ISSUE_TEMPLATE/workflow_feedback.yml). The
GitHub Actions intake workflow routes them to the owning stage, updates stage
and status labels, and comments with the route. Feedback about a released item
can include a typed reference such as `shot:canonical-shot-001`; an untyped or
cross-stage report stays in post-release triage. Editing an issue re-runs
routing, and changing its owner creates a new route comment so the newly
configured team is mentioned.

For role notifications, set the repository variable named by the role's
`notification_variable` to a permitted `@user` or `@org/team` mention. If it
is missing or invalid, the action mentions the reporter and states that the
stage owner was not notified. Team access and GitHub's delivery of mentions
remain repository configuration responsibilities.

Corrections and contributions are proposed through pull requests using the
[traceability template](./.github/PULL_REQUEST_TEMPLATE.md). PRs should cite
the work item, affected artifacts, requirement IDs, and executed gate evidence.
Use `Fixes #123` when the merged PR resolves an issue; GitHub then closes it.
Issue closure is a tracking state, not evidence that a scholarly or technical
gate passed. Pushes and PRs run matrix validation and the project test gates.

The project is initialized as a local Git repository. The Actions workflows
and issue notifications will run only after the repository is pushed to
GitHub; there is no remote or configured team account in this workspace.

Compile and run the C11 checks with a local GCC or Clang:

```text
cc -std=c11 -O2 -Wall -Wextra -Werror -pedantic -Wconversion -Wshadow \
  -I crowd_cinema_core/include crowd_cinema_core/src/crowd_cinema.c \
  crowd_cinema_core/src/sha256.c crowd_cinema_core/tests/test_core.c \
  -o test_core
./test_core
```

## Implemented behavior and boundaries

- TEI `<app>`, `<lem>`, and `<rdg>` elements are collated by witness ID and can
  be exported as a merged TEI apparatus; source XML is parsed as data and not
  executed. The export preserves readings but does not choose an authoritative
  text or authenticate witnesses.
- Shot manifests require a supported genre, 10–15 second duration, two keyframe
  anchors, and explicit foreground, secondary-character, and crowd actions.
- Render packets are deterministic JSON objects with a SHA-256 packet digest.
  The local SQLite exchange accepts content-digested takes, records one vote
  per identity per take, and reports quorum and deterministic winners; it is
  not a remote volunteer queue or Sybil-resistant identity system.
- Subtitle modules include language/script metadata for the Scheduled Indian
  languages and selected global languages, and validate/export supplied
  translations. They do not translate text, synthesize audio, or claim
  phonetic/lip-sync alignment.
- The C11 motion gate compares caller-supplied grayscale frame buffers across
  three image zones, or consumes caller-supplied zone activity samples. It
  does not decode video or calculate optical flow.
- Python assurance checks validate genre/source linkage, shot timing, and
  deterministic quorum/vote invariants. `formal-check` exhaustively evaluates
  these invariants only within explicit small bounds; it is not a CBMC/Z3 proof
  or a proof of the C implementation. The HAZOP/FMECA output is a structured
  checklist, not a safety certification. The provenance ledger hashes
  canonical JSON and renders credits, but does not authenticate real
  contributors.
- A local release bundle command records sorted artifact paths, byte counts,
  SHA-256 digests, and a version label in a reproducible ZIP. The bundle is
  unsigned, unpublished, and does not constitute a release approval.
- Source attestation can verify exact-byte SHA-256 digests and optional Ed25519
  detached signatures against caller-supplied raw public keys (install
  `.[crypto]`). Key and signer labels are not identities. OpenTimestamps receipt
  parsing is explicitly not timestamp verification.
- Timeline metadata can be checked for continuity and exported as OTIO JSON.
  When FFmpeg and ffprobe are installed, the optional adapter concatenates
  compatible, local, video-only H.264 media with stream copy; it does not
  transcode or synchronize audio.
- Five local studio notebooks teach collation, shot design, render packets,
  exchange voting, and workflow/formal-check limitations. The gymnasium
  validator checks notebook structure and can produce self-contained escaped
  HTML; it does not execute remote services.
- The frame chain hashes supplied frame digests and presentation timestamps.
  It does not decode video or color-grade media. FFmpeg assembly is unavailable
  until the caller installs FFmpeg/ffprobe and supplies compatible local clips.
- C2PA, OpenTimestamps calendar verification, key identity, real-time external
  workers, multilingual translation and audio generation, CBMC/Z3 proofs,
  MISRA certification, hosted notifications, and publication are not provided
  by the local package. GitHub-hosted issue automation requires pushing the
  repository and configuring role variables. Dependency-free local shot and
  workflow pages are at `docs/index.html` and `docs/workflow-board.html`.

No sample scholarly signatures, vote outcomes, generated clips, or verification
results are represented as real. The included TEI fixtures are clearly marked
illustrative.
