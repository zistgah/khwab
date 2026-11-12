"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .broker import create_packet
from .attestation import VERIFIED, inspect_opentimestamps_receipt, verify_source_attestation
from .collation import collate, export_tei_apparatus
from .compiler import compile_shot
from .formal_checks import run_bounded_checks
from .gymnasium import export_notebook, load_notebook
from .media import (
    FFmpegError,
    assemble_otio_json,
    assemble_with_ffmpeg,
    check_continuity,
)
from .release import build_release_bundle
from .subtitles import make_webvtt
from .workflow import (
    WorkflowError,
    build_workflow_board,
    load_json,
    route_issue_event,
    validate_matrices,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="crowd-cinema")
    commands = parser.add_subparsers(dest="command", required=True)

    collate_command = commands.add_parser("collate", help="collate TEI apparatus entries")
    collate_command.add_argument("tei_files", nargs="+")
    collate_command.add_argument("--tei-output", help="write the merged TEI apparatus to this path")

    formal_command = commands.add_parser(
        "formal-check",
        help="run bounded exhaustive checks (not a formal proof)",
    )
    formal_command.add_argument("--max-authorities", type=int, default=5)
    formal_command.add_argument("--max-voters", type=int, default=4)
    formal_command.add_argument("--max-candidates", type=int, default=3)
    formal_command.add_argument("--max-shots", type=int, default=5)

    release_command = commands.add_parser(
        "release-bundle",
        help="build an unsigned local ZIP release bundle",
    )
    release_command.add_argument("--root", default=".")
    release_command.add_argument("--output", required=True)
    release_command.add_argument("version")
    release_command.add_argument("artifacts", nargs="+")

    attestation_command = commands.add_parser(
        "verify-attestation",
        help="check exact-byte digest and an optional Ed25519 detached signature",
    )
    attestation_command.add_argument("content_path")
    attestation_command.add_argument("--sha256", required=True)
    attestation_command.add_argument("--signature-file")
    attestation_command.add_argument("--public-key-file")
    attestation_command.add_argument("--key-id")
    attestation_command.add_argument("--signer-id")
    attestation_command.add_argument("--opentimestamps-receipt")

    timeline_command = commands.add_parser(
        "timeline",
        help="validate ordered clip metadata and write deterministic OTIO JSON",
    )
    timeline_command.add_argument("--input", required=True, help="JSON file with a clips array")
    timeline_command.add_argument("--otio-output")
    timeline_command.add_argument("--name", default="Crowd Cinema")

    media_command = commands.add_parser(
        "assemble-media",
        help="concatenate compatible local H.264 clips with FFmpeg stream copy",
    )
    media_command.add_argument("--input", required=True, help="JSON file with a clips array")
    media_command.add_argument("--output", required=True)
    media_command.add_argument("--ffmpeg", default="ffmpeg")
    media_command.add_argument("--ffprobe", default="ffprobe")
    media_command.add_argument("--timeout", type=float, default=120.0)

    gymnasium_command = commands.add_parser(
        "gymnasium",
        help="validate or export local instructional notebooks",
    )
    gymnasium_commands = gymnasium_command.add_subparsers(
        dest="gymnasium_command",
        required=True,
    )
    notebook_check_command = gymnasium_commands.add_parser(
        "check",
        help="validate one or more notebook JSON files",
    )
    notebook_check_command.add_argument("notebook_paths", nargs="+")
    notebook_export_command = gymnasium_commands.add_parser(
        "export",
        help="export one notebook to self-contained escaped HTML",
    )
    notebook_export_command.add_argument("notebook_path")
    notebook_export_command.add_argument("--output", required=True)

    shot_command = commands.add_parser("compile-shot", help="validate and compile one shot JSON")
    shot_command.add_argument("shot_json")

    packet_command = commands.add_parser("packet", help="create a deterministic render packet")
    packet_command.add_argument("shot_json")

    subtitle_command = commands.add_parser("subtitle", help="write one WebVTT cue")
    subtitle_command.add_argument("--language", required=True)
    subtitle_command.add_argument("--text", required=True)
    subtitle_command.add_argument("--duration", required=True, type=int)
    subtitle_command.add_argument("--output")

    workflow_command = commands.add_parser(
        "workflow",
        help="validate workflow matrices, route feedback, or export the workflow board",
    )
    workflow_commands = workflow_command.add_subparsers(dest="workflow_command", required=True)

    check_command = workflow_commands.add_parser(
        "check",
        help="validate the lifecycle and requirements traceability matrices",
    )
    check_command.add_argument(
        "--manifest",
        default="workflow/crowd_cinema_workflow.json",
    )
    check_command.add_argument(
        "--traceability",
        default="workflow/requirements_traceability.json",
    )

    route_command = workflow_commands.add_parser(
        "route-issue",
        help="route a GitHub issue-form event to its accountable workflow stage",
    )
    route_command.add_argument("--event-path", required=True)
    route_command.add_argument(
        "--manifest",
        default="workflow/crowd_cinema_workflow.json",
    )
    route_command.add_argument(
        "--traceability",
        default="workflow/requirements_traceability.json",
    )

    board_command = workflow_commands.add_parser(
        "board",
        help="generate a static workflow and traceability board",
    )
    board_command.add_argument(
        "--manifest",
        default="workflow/crowd_cinema_workflow.json",
    )
    board_command.add_argument(
        "--traceability",
        default="workflow/requirements_traceability.json",
    )
    board_command.add_argument("--output", default="docs/workflow-board.html")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "collate":
            result = collate(args.tei_files)
            if args.tei_output:
                Path(args.tei_output).write_text(
                    export_tei_apparatus(result),
                    encoding="utf-8",
                    newline="\n",
                )
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == "formal-check":
            report = run_bounded_checks(
                max_authorities=args.max_authorities,
                max_voters=args.max_voters,
                max_candidates=args.max_candidates,
                max_shots=args.max_shots,
            )
            print(json.dumps(report, ensure_ascii=False, indent=2))
        elif args.command == "release-bundle":
            result = build_release_bundle(
                args.root,
                args.artifacts,
                args.version,
                args.output,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == "verify-attestation":
            if bool(args.signature_file) != bool(args.public_key_file):
                raise ValueError("--signature-file and --public-key-file must be supplied together")
            content = Path(args.content_path).read_bytes()
            signature = (
                Path(args.signature_file).read_bytes()
                if args.signature_file
                else None
            )
            public_key = (
                Path(args.public_key_file).read_bytes()
                if args.public_key_file
                else None
            )
            result = verify_source_attestation(
                content,
                args.sha256,
                signature,
                public_key,
                key_id=args.key_id,
                signer_id=args.signer_id,
            )
            if args.opentimestamps_receipt:
                result["timestamp_receipt"] = inspect_opentimestamps_receipt(
                    Path(args.opentimestamps_receipt).read_bytes()
                )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            if result["status"] != VERIFIED:
                return 1
        elif args.command in {"timeline", "assemble-media"}:
            input_document = load_json(args.input)
            if not isinstance(input_document, dict):
                raise ValueError("timeline input must be an object containing a clips array")
            clips = input_document.get("clips")
            if args.command == "timeline":
                continuity = check_continuity(clips)
                timeline = assemble_otio_json(clips, name=args.name)
                if args.otio_output:
                    Path(args.otio_output).write_text(
                        json.dumps(timeline, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                        newline="\n",
                    )
                print(
                    json.dumps(
                        {"continuity": continuity, "timeline": timeline},
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            else:
                output = assemble_with_ffmpeg(
                    clips,
                    args.output,
                    ffmpeg_executable=args.ffmpeg,
                    ffprobe_executable=args.ffprobe,
                    timeout=args.timeout,
                )
                print(json.dumps({"status": "assembled", "output": str(output)}, indent=2))
        elif args.command == "gymnasium":
            if args.gymnasium_command == "check":
                results = [
                    {"path": path, "valid": bool(load_notebook(path))}
                    for path in args.notebook_paths
                ]
                print(json.dumps({"status": "valid", "notebooks": results}, indent=2))
            else:
                output = export_notebook(args.notebook_path, args.output)
                print(json.dumps({"status": "exported", "output": str(output)}, indent=2))
        elif args.command == "compile-shot":
            print(json.dumps(compile_shot(args.shot_json), ensure_ascii=False, indent=2))
        elif args.command == "packet":
            print(json.dumps(create_packet(compile_shot(args.shot_json)), ensure_ascii=False, indent=2))
        elif args.command == "subtitle":
            output = make_webvtt(args.language, args.text, args.duration)
            if args.output:
                Path(args.output).write_text(output, encoding="utf-8", newline="\n")
            else:
                sys.stdout.write(output)
        elif args.workflow_command == "check":
            manifest = load_json(args.manifest)
            traceability = load_json(args.traceability)
            errors = validate_matrices(manifest, traceability)
            if errors:
                raise WorkflowError("; ".join(errors))
            print(
                json.dumps(
                    {
                        "status": "valid",
                        "stages": len(manifest["stages"]),
                        "gates": len(manifest["gates"]),
                        "feedback_routes": len(manifest["feedback_routes"]),
                        "contribution_routes": len(manifest["contribution_routes"]),
                        "requirements": len(traceability["requirements"]),
                    },
                    indent=2,
                )
            )
        elif args.workflow_command == "route-issue":
            manifest = load_json(args.manifest)
            traceability = load_json(args.traceability)
            errors = validate_matrices(manifest, traceability)
            if errors:
                raise WorkflowError("; ".join(errors))
            event_document = load_json(args.event_path)
            print(json.dumps(route_issue_event(event_document, manifest), ensure_ascii=False))
        else:
            output = build_workflow_board(
                args.manifest,
                args.traceability,
                args.output,
            )
            print(f"Workflow board written to {output}")
    except (OSError, ValueError, json.JSONDecodeError, WorkflowError, FFmpegError) as error:
        print(f"crowd-cinema: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
