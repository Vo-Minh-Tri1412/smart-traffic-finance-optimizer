"""Plan or fetch a small, checksum-verified Poly Haven city asset set.

By default this is a dry-run:

    python scripts/render/fetch_city_assets.py

Pass ``--fetch`` to download the selected files. Files are stored under the
ignored artifacts/city_assets/polyhaven directory. Existing files are reused
only when their API size and MD5 match; mismatches are never overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "render_unreal" / "Config" / "city_asset_sources.v1.json"
API_HOST = "api.polyhaven.com"
DOWNLOAD_HOST = "dl.polyhaven.org"
ALLOWED_RESOLUTIONS = {"1k", "2k", "4k", "8k"}
HEX_MD5 = re.compile(r"^[0-9a-fA-F]{32}$")


class AssetFetchError(RuntimeError):
    """Invalid API data or a file that cannot be safely verified."""


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssetFetchError(f"expected a JSON object in {path}")
    return value


def _api_request(url: str, user_agent: str) -> Any:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != API_HOST:
        raise AssetFetchError(f"refusing non-Poly Haven API URL: {url}")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": user_agent, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            if urllib.parse.urlparse(response.geturl()).hostname != API_HOST:
                raise AssetFetchError(f"Poly Haven API redirected outside {API_HOST}")
            return json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise AssetFetchError(f"Poly Haven API request failed: {url}: {exc}") from exc


def _safe_relative_path(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise AssetFetchError(f"unsafe asset-relative path from API: {value!r}")
    return path.as_posix()


def _validate_file_record(
    record: Any, asset_id: str, relative_path: str, role: str
) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise AssetFetchError(f"missing file record for {asset_id}/{relative_path}")
    url = record.get("url")
    size = record.get("size")
    md5 = record.get("md5")
    parsed = urllib.parse.urlparse(url if isinstance(url, str) else "")
    if (
        parsed.scheme != "https"
        or parsed.hostname != DOWNLOAD_HOST
        or not parsed.path.startswith("/file/ph-assets/")
    ):
        raise AssetFetchError(
            f"refusing non-Poly Haven download URL for {asset_id}/{relative_path}: {url!r}"
        )
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        raise AssetFetchError(f"invalid API byte size for {asset_id}/{relative_path}: {size!r}")
    if not isinstance(md5, str) or not HEX_MD5.fullmatch(md5):
        raise AssetFetchError(f"invalid API MD5 for {asset_id}/{relative_path}")
    return {
        "relative_path": _safe_relative_path(relative_path),
        "role": role,
        "url": url,
        "size_bytes": size,
        "md5": md5.lower(),
    }


def _filename_from_url(url: str) -> str:
    filename = urllib.parse.unquote(urllib.parse.urlparse(url).path.rsplit("/", 1)[-1])
    if not filename or filename in {".", ".."}:
        raise AssetFetchError(f"download URL has no safe filename: {url}")
    return filename


def _selected_files(
    asset_id: str, asset_type: str, resolution: str, selector: dict[str, Any], file_data: Any
) -> list[dict[str, Any]]:
    if not isinstance(file_data, dict):
        raise AssetFetchError(f"files endpoint returned malformed data for {asset_id}")
    result: list[dict[str, Any]] = []
    if asset_type == "model":
        file_format = selector.get("format")
        variant = file_data.get(file_format, {}).get(resolution, {})
        main = variant.get(file_format) if isinstance(variant, dict) else None
        if not isinstance(main, dict):
            raise AssetFetchError(
                f"Poly Haven has no {file_format} {resolution} variant for {asset_id}"
            )
        result.append(
            _validate_file_record(main, asset_id, _filename_from_url(main.get("url", "")), "model")
        )
        dependencies = main.get("include", {}) if selector.get("include_dependencies") else {}
        if not isinstance(dependencies, dict):
            raise AssetFetchError(f"malformed GLTF dependency list for {asset_id}")
        for relative_path, dependency in sorted(dependencies.items()):
            result.append(
                _validate_file_record(dependency, asset_id, relative_path, "model_dependency")
            )
    elif asset_type == "texture":
        file_format = selector.get("format")
        maps = selector.get("maps")
        if not isinstance(maps, list) or not maps:
            raise AssetFetchError(f"texture selection has no maps for {asset_id}")
        for map_name in maps:
            variant = file_data.get(map_name, {}).get(resolution, {})
            record = variant.get(file_format) if isinstance(variant, dict) else None
            if not isinstance(record, dict):
                raise AssetFetchError(
                    f"Poly Haven has no {map_name}/{file_format} {resolution} file for {asset_id}"
                )
            result.append(
                _validate_file_record(
                    record,
                    asset_id,
                    _filename_from_url(record.get("url", "")),
                    f"texture_{map_name}",
                )
            )
    else:
        raise AssetFetchError(f"unsupported asset type in config for {asset_id}: {asset_type!r}")

    seen: dict[str, dict[str, Any]] = {}
    for item in result:
        prior = seen.get(item["relative_path"])
        if prior and prior != item:
            raise AssetFetchError(
                f"conflicting API records use the same path: {asset_id}/{item['relative_path']}"
            )
        seen[item["relative_path"]] = item
    return list(seen.values())


def _asset_plan(config: dict[str, Any]) -> list[dict[str, Any]]:
    api_base = config.get("api_base_url")
    user_agent = config.get("api_user_agent")
    if api_base != f"https://{API_HOST}":
        raise AssetFetchError(f"api_base_url must be https://{API_HOST}")
    if not isinstance(user_agent, str) or "AIQuantumHVTC-CityAssetFetcher/" not in user_agent:
        raise AssetFetchError("api_user_agent must use the project's unique fetcher identity")
    assets = config.get("assets")
    if not isinstance(assets, list) or not assets:
        raise AssetFetchError("config assets must be a non-empty array")

    plan = []
    seen_ids: set[str] = set()
    for spec in assets:
        if not isinstance(spec, dict):
            raise AssetFetchError("asset config contains a non-object row")
        asset_id = spec.get("id")
        resolution = spec.get("resolution")
        asset_type = spec.get("type")
        selector = spec.get("selection")
        if not isinstance(asset_id, str) or not re.fullmatch(r"[a-z0-9_]+", asset_id):
            raise AssetFetchError(f"invalid Poly Haven asset id: {asset_id!r}")
        if asset_id in seen_ids:
            raise AssetFetchError(f"duplicate asset id in config: {asset_id}")
        seen_ids.add(asset_id)
        if resolution not in ALLOWED_RESOLUTIONS:
            raise AssetFetchError(f"unsupported resolution for {asset_id}: {resolution!r}")
        if asset_type not in {"model", "texture"} or not isinstance(selector, dict):
            raise AssetFetchError(f"invalid source type/selection for {asset_id}")

        info = _api_request(f"{api_base}/info/{asset_id}", user_agent)
        files = _api_request(f"{api_base}/files/{asset_id}", user_agent)
        expected_type = 2 if asset_type == "model" else 1
        if not isinstance(info, dict) or info.get("type") != expected_type:
            raise AssetFetchError(f"Poly Haven asset type does not match config for {asset_id}")
        selected = _selected_files(asset_id, asset_type, resolution, selector, files)
        plan.append(
            {
                "id": asset_id,
                "type": asset_type,
                "role": spec.get("role", "unspecified"),
                "download": bool(spec.get("download", False)),
                "resolution": resolution,
                "selection": selector,
                "source_page": f"https://polyhaven.com/a/{asset_id}",
                "api_info": {
                    "name": info.get("name", asset_id),
                    "authors": info.get("authors", {}),
                    "polycount": info.get("polycount"),
                    "dimensions": info.get("dimensions"),
                    "max_resolution": info.get("max_resolution"),
                    "files_hash": info.get("files_hash"),
                },
                "files": selected,
                "total_bytes": sum(item["size_bytes"] for item in selected),
                "note": spec.get("note", ""),
            }
        )
    return plan


def _destination(root: Path, asset_id: str, resolution: str, relative_path: str) -> Path:
    base = root / asset_id / resolution
    destination = base.joinpath(*PurePosixPath(relative_path).parts)
    resolved_root = root.resolve()
    resolved_destination = destination.resolve()
    if not resolved_destination.is_relative_to(resolved_root):
        raise AssetFetchError(f"refusing output path outside download root: {destination}")
    return destination


def _hash_file(path: Path) -> tuple[str, str, int]:
    md5 = hashlib.md5()
    sha256 = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            size += len(block)
            md5.update(block)
            sha256.update(block)
    return md5.hexdigest(), sha256.hexdigest(), size


def _verify_existing(path: Path, file_record: dict[str, Any]) -> str:
    actual_md5, actual_sha256, actual_size = _hash_file(path)
    if actual_size != file_record["size_bytes"] or actual_md5 != file_record["md5"]:
        raise AssetFetchError(
            f"existing file does not match Poly Haven metadata; refusing overwrite: {path}"
        )
    return actual_sha256


def _download_file(
    url: str, user_agent: str, destination: Path, file_record: dict[str, Any]
) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return _verify_existing(destination, file_record)

    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.part")
    request = urllib.request.Request(
        url, headers={"User-Agent": user_agent, "Accept-Encoding": "identity"}
    )
    md5 = hashlib.md5()
    sha256 = hashlib.sha256()
    size = 0
    try:
        with (
            urllib.request.urlopen(request, timeout=90) as response,
            temporary.open("xb") as output,
        ):
            final_host = urllib.parse.urlparse(response.geturl()).hostname
            if final_host != DOWNLOAD_HOST:
                raise AssetFetchError(
                    f"download redirected outside {DOWNLOAD_HOST}: {response.geturl()}"
                )
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                output.write(block)
                md5.update(block)
                sha256.update(block)
                size += len(block)
        if size != file_record["size_bytes"] or md5.hexdigest() != file_record["md5"]:
            raise AssetFetchError(
                f"download failed size/MD5 verification for {destination}: "
                f"size={size}/{file_record['size_bytes']} md5={md5.hexdigest()}"
            )
        # Rename is exclusive on Windows if a destination appeared after preflight.
        temporary.rename(destination)
        return sha256.hexdigest()
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        if isinstance(exc, AssetFetchError):
            raise
        raise AssetFetchError(f"download request failed for {destination}: {exc}") from exc


def _selection_fingerprint(plan: list[dict[str, Any]]) -> str:
    selected = []
    for asset in plan:
        if not asset["download"]:
            continue
        selected.append(
            {
                "id": asset["id"],
                "resolution": asset["resolution"],
                "selection": asset["selection"],
                "files": [
                    {
                        "path": item["relative_path"],
                        "size_bytes": item["size_bytes"],
                        "md5": item["md5"],
                    }
                    for item in asset["files"]
                ],
            }
        )
    canonical = json.dumps(selected, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()[:16]


def _manifest_payload(
    config: dict[str, Any],
    plan: list[dict[str, Any]],
    download_root: Path,
    user_agent: str,
    selection_fingerprint: str,
) -> dict[str, Any]:
    assets: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    for planned in plan:
        if not planned["download"]:
            deferred.append(
                {
                    "id": planned["id"],
                    "role": planned["role"],
                    "resolution": planned["resolution"],
                    "estimated_bytes": planned["total_bytes"],
                    "source_page": planned["source_page"],
                }
            )
            continue
        file_rows = []
        for file_record in planned["files"]:
            local_path = _destination(
                download_root, planned["id"], planned["resolution"], file_record["relative_path"]
            )
            sha256 = _download_file(file_record["url"], user_agent, local_path, file_record)
            file_rows.append(
                {
                    "path": str(local_path.relative_to(ROOT).as_posix()),
                    "role": file_record["role"],
                    "url": file_record["url"],
                    "size_bytes": file_record["size_bytes"],
                    "md5": file_record["md5"],
                    "sha256": sha256,
                }
            )
        assets.append(
            {
                "id": planned["id"],
                "name": planned["api_info"]["name"],
                "type": planned["type"],
                "role": planned["role"],
                "authors": planned["api_info"]["authors"],
                "polycount": planned["api_info"]["polycount"],
                "dimensions": planned["api_info"]["dimensions"],
                "source_page": planned["source_page"],
                "license": config["license"],
                "license_url": config["license_url"],
                "resolution": planned["resolution"],
                "selection": planned["selection"],
                "api_files_hash": planned["api_info"]["files_hash"],
                "total_bytes": sum(row["size_bytes"] for row in file_rows),
                "files": file_rows,
            }
        )
    return {
        "schema_version": "polyhaven_city_assets.v1",
        "selection_fingerprint": selection_fingerprint,
        "provider": "Poly Haven",
        "api_base_url": config["api_base_url"],
        "api_user_agent": user_agent,
        "api_credit_required": config["api_credit_required"],
        "api_credit_text": config["api_credit_text"],
        "license": config["license"],
        "license_url": config["license_url"],
        "download_root": str(download_root.relative_to(ROOT).as_posix()),
        "downloaded_total_bytes": sum(asset["total_bytes"] for asset in assets),
        "deferred": deferred,
        "assets": assets,
    }


def _write_manifest_exclusive(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        current = _read_json(path)
        if current != payload:
            raise AssetFetchError(
                "existing manifest differs from the verified download plan; "
                f"refusing overwrite: {path}"
            )
        print(f"Verified existing manifest: {path.relative_to(ROOT)}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as output:
        json.dump(payload, output, indent=2, sort_keys=True)
        output.write("\n")


def _print_plan(plan: list[dict[str, Any]], maximum_bytes: int) -> int:
    selected_total = 0
    deferred_total = 0
    print("Poly Haven city asset plan (all sizes from the official files API):")
    for asset in plan:
        state = "FETCH" if asset["download"] else "DEFER"
        print(
            f"  {state:6} {asset['id']} {asset['resolution']}: "
            f"{asset['total_bytes']:,} bytes, {len(asset['files'])} files ({asset['role']})"
        )
        for item in asset["files"]:
            print(f"           {item['relative_path']}  {item['size_bytes']:,} bytes")
        if asset["download"]:
            selected_total += asset["total_bytes"]
        else:
            deferred_total += asset["total_bytes"]
    print(f"Selected total: {selected_total:,} bytes ({selected_total / (1024 * 1024):.2f} MiB)")
    print(f"Deferred total: {deferred_total:,} bytes ({deferred_total / (1024 * 1024):.2f} MiB)")
    print(f"Configured maximum: {maximum_bytes:,} bytes")
    return selected_total


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="source selection JSON")
    parser.add_argument(
        "--fetch", action="store_true", help="download selected files after planning"
    )
    args = parser.parse_args(argv)

    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    config = _read_json(config_path.resolve())
    if config.get("schema_version") != "city_asset_sources.v1":
        raise AssetFetchError("unsupported city asset source config schema")
    maximum_bytes = config.get("max_download_bytes")
    if isinstance(maximum_bytes, bool) or not isinstance(maximum_bytes, int) or maximum_bytes <= 0:
        raise AssetFetchError("max_download_bytes must be a positive integer")
    download_root = (ROOT / config["download_root"]).resolve()
    expected_download_root = (ROOT / "artifacts" / "city_assets" / "polyhaven").resolve()
    if download_root != expected_download_root:
        raise AssetFetchError("downloads are restricted to artifacts/city_assets/polyhaven")
    plan = _asset_plan(config)
    selected_total = _print_plan(plan, maximum_bytes)
    selection_fingerprint = _selection_fingerprint(plan)
    manifest_path = download_root / f"manifest.v1-{selection_fingerprint}.json"
    print(f"Manifest target: {manifest_path.relative_to(ROOT)}")
    if not args.fetch:
        print("Dry-run only; pass --fetch to write verified files.")
        return 0
    if selected_total > maximum_bytes:
        raise AssetFetchError(
            f"selected asset set is {selected_total:,} bytes, "
            f"above configured limit {maximum_bytes:,}"
        )
    if selected_total == 0:
        raise AssetFetchError("no selected files are configured for download")

    user_agent = config["api_user_agent"]
    manifest = _manifest_payload(config, plan, download_root, user_agent, selection_fingerprint)
    _write_manifest_exclusive(manifest_path, manifest)
    print(
        f"Fetched and verified {len(manifest['assets'])} assets / "
        f"{sum(len(asset['files']) for asset in manifest['assets'])} files; "
        f"{manifest['downloaded_total_bytes']:,} bytes."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except AssetFetchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
