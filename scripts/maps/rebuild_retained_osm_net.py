from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

NET_BODY_MARKER = b"<net version="
NET_BODY_CHUNK_SIZE = 1024 * 1024
ALLOWED_OPTIONS = {
    "--proj.utm",
    "--geometry.remove",
    "--roundabouts.guess",
    "--tls.discard-simple",
    "--tls.guess-signals",
    "--ramps.guess",
    "--no-turnarounds",
    "--junctions.join",
    "--verbose",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Rebuild a candidate SUMO net from a local OSM source and compare it with the "
            "retained net. This does not download OSM data or replace the retained net."
        )
    )
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--qa", type=Path, required=True)
    return parser


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(NET_BODY_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _net_body_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    overlap = b""
    found = False
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(NET_BODY_CHUNK_SIZE), b""):
            if found:
                digest.update(chunk)
                continue
            data = overlap + chunk
            offset = data.find(NET_BODY_MARKER)
            if offset >= 0:
                digest.update(data[offset:])
                found = True
            else:
                overlap = data[-(len(NET_BODY_MARKER) - 1) :]
    if not found:
        raise ValueError(f"SUMO net body marker not found in {path}")
    return digest.hexdigest()


def _resolve_profile_path(profile_path: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"profile {label} must be a non-empty path")
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = profile_path.parent / candidate
    return candidate.resolve(strict=True)


def _load_context(profile_path: Path) -> dict[str, Any]:
    profile_path = profile_path.expanduser().resolve(strict=True)
    profile_bytes = profile_path.read_bytes()
    profile = json.loads(profile_bytes)
    if (
        not isinstance(profile, dict)
        or profile.get("schema_version") != "sumo_netconvert_profile.v1"
    ):
        raise ValueError("profile must use sumo_netconvert_profile.v1")

    converter = profile.get("converter")
    if not isinstance(converter, dict):
        raise ValueError("profile converter must be an object")
    expected_version = converter.get("version")
    if not isinstance(expected_version, str) or not expected_version:
        raise ValueError("profile converter.version must be a non-empty string")
    binary_name = converter.get("binary", "netconvert")
    if not isinstance(binary_name, str) or not binary_name:
        raise ValueError("profile converter.binary must be a non-empty string")

    options = profile.get("options")
    if not isinstance(options, list):
        raise ValueError("profile options must be an array")
    parsed_options: list[tuple[str, bool]] = []
    for option in options:
        if not isinstance(option, dict):
            raise ValueError("profile option rows must be objects")
        name, value = option.get("name"), option.get("value")
        if name not in ALLOWED_OPTIONS or not isinstance(value, bool):
            raise ValueError(f"unsupported or malformed netconvert option: {option!r}")
        parsed_options.append((name, value))
    if {name for name, _ in parsed_options} != ALLOWED_OPTIONS or len(parsed_options) != len(
        ALLOWED_OPTIONS
    ):
        raise ValueError("profile must specify each approved import option exactly once")

    project_path = _resolve_profile_path(
        profile_path, profile.get("project_descriptor"), "project_descriptor"
    )
    project = json.loads(project_path.read_text(encoding="utf-8"))
    if not isinstance(project, dict) or project.get("id") != profile.get("project_id"):
        raise ValueError("profile project_id does not match the project descriptor")
    project_source = project.get("source")
    if not isinstance(project_source, dict) or project_source.get("kind") != "sumo_net_xml":
        raise ValueError("project descriptor source.kind must be sumo_net_xml")
    project_net_value = project_source.get("net_path")
    if not isinstance(project_net_value, str) or not project_net_value:
        raise ValueError("project descriptor source.net_path must be a non-empty path")
    project_net = (project_path.parent / project_net_value).resolve(strict=True)
    retained_net = _resolve_profile_path(profile_path, profile.get("retained_net"), "retained_net")
    if retained_net != project_net or not retained_net.is_file():
        raise ValueError("profile retained_net must resolve to the project descriptor's SUMO net")

    source_osm = _resolve_profile_path(profile_path, profile.get("source_osm"), "source_osm")
    if not source_osm.is_file():
        raise FileNotFoundError(f"OSM source is not a file: {source_osm}")
    provenance = profile.get("source_provenance", {})
    if not isinstance(provenance, dict):
        raise ValueError("profile source_provenance must be an object")
    query_file = None
    if provenance.get("query_file"):
        query_file = _resolve_profile_path(
            profile_path, provenance["query_file"], "source_provenance.query_file"
        )
        if not query_file.is_file():
            raise FileNotFoundError(f"Overpass query file is not a file: {query_file}")

    expected_source_sha = profile.get("source_osm_sha256")
    expected_net_body_sha = profile.get("retained_net_body_sha256")
    if not isinstance(expected_source_sha, str) or not re.fullmatch(
        r"[0-9a-f]{64}", expected_source_sha
    ):
        raise ValueError("profile source_osm_sha256 must be a lowercase SHA256")
    if not isinstance(expected_net_body_sha, str) or not re.fullmatch(
        r"[0-9a-f]{64}", expected_net_body_sha
    ):
        raise ValueError("profile retained_net_body_sha256 must be a lowercase SHA256")

    source_osm_sha = _sha256_file(source_osm)
    retained_body_sha = _net_body_sha256(retained_net)
    return {
        "profile_path": profile_path,
        "profile": profile,
        "profile_sha256": hashlib.sha256(profile_bytes).hexdigest(),
        "project_path": project_path,
        "project_id": project["id"],
        "source_osm": source_osm,
        "source_osm_sha256": source_osm_sha,
        "expected_source_osm_sha256": expected_source_sha,
        "source_osm_matches_profile": source_osm_sha == expected_source_sha,
        "query_file": query_file,
        "retained_net": retained_net,
        "retained_net_sha256": _sha256_file(retained_net),
        "retained_net_body_sha256": retained_body_sha,
        "expected_retained_net_body_sha256": expected_net_body_sha,
        "retained_net_matches_profile": retained_body_sha == expected_net_body_sha,
        "expected_netconvert_version": expected_version,
        "netconvert_binary": binary_name,
        "options": parsed_options,
    }


def _version(binary: str) -> tuple[str, str]:
    completed = subprocess.run(
        [binary, "--version"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
    match = re.search(r"\bnetconvert\s+(\d+\.\d+\.\d+)\b", output, flags=re.IGNORECASE)
    if completed.returncode != 0 or not match:
        raise RuntimeError(f"could not identify netconvert version from --version output: {output}")
    return match.group(1), output


def _log_path(qa_path: Path) -> Path:
    return qa_path.with_name(f"{qa_path.stem}.netconvert.log")


def _check_new_paths(paths: list[Path], protected_sources: set[Path]) -> None:
    if len(set(paths)) != len(paths):
        raise ValueError("--output, --qa, and generated log path must be distinct")
    if any(path in protected_sources for path in paths):
        raise ValueError("output, QA, and log paths must not point to source files")
    existing = [path for path in paths if path.exists()]
    if existing:
        raise FileExistsError(
            "refusing to overwrite existing artifact(s): " + ", ".join(map(str, existing))
        )


def _publish_exclusive(candidate: Path, output_path: Path) -> None:
    created = False
    try:
        with candidate.open("rb") as source:
            destination = output_path.open("xb")
            created = True
            with destination:
                shutil.copyfileobj(source, destination, length=NET_BODY_CHUNK_SIZE)
    except OSError:
        if created:
            output_path.unlink(missing_ok=True)
        raise


def _write_reserved_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def run(profile_arg: Path, output_arg: Path, qa_arg: Path) -> int:
    profile_arg = profile_arg.expanduser().resolve()
    output_path = output_arg.expanduser().resolve()
    qa_path = qa_arg.expanduser().resolve()
    log_path = _log_path(qa_path)
    _check_new_paths([output_path, qa_path, log_path], set())

    context = _load_context(profile_arg)
    binary = shutil.which(context["netconvert_binary"])
    if binary is None:
        raise FileNotFoundError(f"netconvert binary not found: {context['netconvert_binary']}")
    actual_version, version_output = _version(binary)
    if actual_version != context["expected_netconvert_version"]:
        raise ValueError(
            "netconvert version mismatch: "
            f"expected {context['expected_netconvert_version']}, got {actual_version}"
        )

    for path in (output_path, qa_path, log_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    _check_new_paths(
        [output_path, qa_path, log_path],
        {
            context["profile_path"],
            context["project_path"],
            context["source_osm"],
            context["retained_net"],
            *([context["query_file"]] if context["query_file"] else []),
        },
    )
    qa_path.open("x", encoding="utf-8").close()
    log_path.open("x", encoding="utf-8").close()

    command: list[str] = [
        binary,
        "--osm-files",
        str(context["source_osm"]),
        "--output-file",
        "<temporary-candidate-net.xml>",
    ]
    for name, value in context["options"]:
        command.extend((name, "true" if value else "false"))

    report: dict[str, Any] = {
        "schema_version": "retained_osm_rebuild_qa.v1",
        "status": "netconvert_failed",
        "review_required": True,
        "profile_id": context["profile"].get("profile_id"),
        "profile_path": str(context["profile_path"]),
        "profile_sha256": context["profile_sha256"],
        "project_id": context["project_id"],
        "project_descriptor": str(context["project_path"]),
        "source_osm": str(context["source_osm"]),
        "source_osm_sha256": context["source_osm_sha256"],
        "expected_source_osm_sha256": context["expected_source_osm_sha256"],
        "source_osm_matches_profile": context["source_osm_matches_profile"],
        "overpass_query_file": str(context["query_file"]) if context["query_file"] else None,
        "retained_net": str(context["retained_net"]),
        "retained_net_sha256": context["retained_net_sha256"],
        "retained_net_body_sha256": context["retained_net_body_sha256"],
        "expected_retained_net_body_sha256": context["expected_retained_net_body_sha256"],
        "retained_net_matches_profile": context["retained_net_matches_profile"],
        "candidate_net": str(output_path),
        "qa_path": str(qa_path),
        "netconvert_log": str(log_path),
        "netconvert_binary": str(Path(binary).resolve()),
        "netconvert_version": actual_version,
        "netconvert_version_output": version_output,
        "netconvert_options": [
            {"name": name, "value": value} for name, value in context["options"]
        ],
        "command_template": command,
        "overpass_download_performed": False,
        "retained_net_replaced": False,
    }

    log_lines = ["VERSION CHECK:", version_output, "", "COMMAND TEMPLATE:", json.dumps(command)]
    status_code = 1
    try:
        with tempfile.TemporaryDirectory(
            prefix="district7-netconvert-",
            dir=output_path.parent,
        ) as temp_dir:
            candidate = Path(temp_dir) / "candidate.net.xml"
            command[command.index("<temporary-candidate-net.xml>")] = str(candidate)
            report["command"] = command
            log_lines.extend(
                ("", "EXECUTED COMMAND:", json.dumps(command), "", "NETCONVERT OUTPUT:")
            )
            completed = subprocess.run(
                command,
                cwd=PROJECT_ROOT,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            log_lines.append(completed.stdout or "")
            report["netconvert_return_code"] = completed.returncode
            if completed.returncode != 0:
                report["error"] = "netconvert exited with a non-zero return code"
            elif not candidate.is_file() or candidate.stat().st_size == 0:
                report["error"] = "netconvert succeeded without producing a non-empty candidate net"
            else:
                candidate_body_sha = _net_body_sha256(candidate)
                candidate_sha = _sha256_file(candidate)
                retained_match = candidate_body_sha == context["retained_net_body_sha256"]
                profile_baseline_match = context["retained_net_matches_profile"]
                source_match = context["source_osm_matches_profile"]
                review_required = not (retained_match and profile_baseline_match and source_match)
                report.update(
                    {
                        "candidate_net_sha256": candidate_sha,
                        "candidate_net_body_sha256": candidate_body_sha,
                        "candidate_matches_retained_body": retained_match,
                        "candidate_vs_retained": "match"
                        if retained_match
                        else "drift_requires_review",
                        "review_required": review_required,
                    }
                )
                try:
                    _publish_exclusive(candidate, output_path)
                except OSError as exc:
                    report["error"] = f"candidate output could not be published exclusively: {exc}"
                else:
                    report["status"] = "drift_requires_review" if review_required else "match"
                    status_code = 2 if review_required else 0
    except OSError as exc:
        report["error"] = f"netconvert execution or candidate handling failed: {exc}"

    _write_reserved_json(qa_path, report)
    log_path.write_text("\n".join(log_lines).rstrip() + "\n", encoding="utf-8")
    if report["status"] == "match":
        print(f"[OK] Rebuilt candidate matches the retained net body: {output_path}")
    elif report["status"] == "drift_requires_review":
        print(
            "[REVIEW] Candidate saved; body drift or provenance mismatch needs review: "
            f"{output_path}"
        )
    else:
        print(
            f"[FAIL] OSM-to-SUMO rebuild did not complete: {report.get('error', 'unknown error')}"
        )
    print(f"[QA] Report: {qa_path}")
    print(f"[LOG] Netconvert log: {log_path}")
    return status_code


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run(args.profile, args.output, args.qa)
    except (OSError, ValueError, KeyError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"[FAIL] OSM-to-SUMO rebuild QA could not start: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
