#!/usr/bin/env python3
"""Import accepted asset draft ZIP archives into a visual profile asset pack."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True, slots=True)
class DraftAsset:
    """Single asset entry read from a draft archive registry."""

    asset_id: str
    source_path: str
    archive_path: Path
    batch_id: str
    batch_version: str


@dataclass(frozen=True, slots=True)
class ManifestTarget:
    """Resolved target asset entry from assets_manifest.json."""

    asset_id: str
    kind: str
    relative_path: Path


def _read_json_object(path: Path) -> dict[str, Any]:
    """Read a JSON object from disk."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def _read_zip_json_object(archive: zipfile.ZipFile, member: str) -> dict[str, Any]:
    """Read a JSON object from a ZIP member."""
    with archive.open(member) as stream:
        data = json.loads(stream.read().decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {member}")
    return data


def _resolve_asset_root(profile_dir: Path, manifest: dict[str, Any], override: Path | None) -> Path:
    """Resolve the filesystem root where real PNG assets are stored."""
    if override is not None:
        return override.resolve()
    raw_root = manifest.get("asset_root")
    if isinstance(raw_root, str) and raw_root:
        root = Path(raw_root)
        if root.is_absolute():
            return root
        return (profile_dir / root).resolve()
    return profile_dir.resolve()


def _load_alias_map(profile_dir: Path) -> dict[str, str]:
    """Load optional draft-to-manifest asset aliases from the profile."""
    path = profile_dir / "asset_import_aliases.json"
    if not path.exists():
        return {}
    data = _read_json_object(path)
    mappings = data.get("mappings")
    if not isinstance(mappings, dict):
        raise ValueError(f"Expected mapping 'mappings' in {path}")
    result: dict[str, str] = {}
    for source, target in mappings.items():
        if not isinstance(source, str) or not isinstance(target, str):
            raise ValueError(f"Aliases in {path} must be string-to-string mappings")
        result[source] = target
    return result


def _manifest_targets(manifest: dict[str, Any]) -> dict[str, ManifestTarget]:
    """Return all tile and sprite targets available in assets_manifest.json."""
    targets: dict[str, ManifestTarget] = {}
    for kind in ("tiles", "sprites"):
        raw_entries = manifest.get(kind)
        if not isinstance(raw_entries, dict):
            raise ValueError(f"assets_manifest.json must contain mapping '{kind}'")
        for asset_id, entry in raw_entries.items():
            if not isinstance(asset_id, str) or not isinstance(entry, dict):
                continue
            raw_path = entry.get("path")
            if isinstance(raw_path, str) and raw_path:
                targets[asset_id] = ManifestTarget(
                    asset_id=asset_id,
                    kind="tile" if kind == "tiles" else "sprite",
                    relative_path=Path(raw_path),
                )
    return targets


def _candidate_asset_ids(source_id: str) -> list[str]:
    """Return deterministic fallback candidates for a source draft asset id."""
    candidates = [source_id]
    if "_" in source_id:
        prefix, rest = source_id.split("_", 1)
        candidates.append(f"{prefix}.{rest}")
        if rest.endswith("_01"):
            candidates.append(f"{prefix}.{rest[:-3]}")
    return candidates


def _resolve_target_id(source_id: str, aliases: dict[str, str], targets: dict[str, ManifestTarget]) -> str | None:
    """Resolve a draft asset id to a target manifest asset id."""
    alias = aliases.get(source_id)
    if alias is not None:
        return alias if alias in targets else None
    for candidate in _candidate_asset_ids(source_id):
        if candidate in targets:
            return candidate
    return None


def _archive_paths(paths: Iterable[Path]) -> list[Path]:
    """Expand files/directories into a sorted unique ZIP archive list."""
    archives: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        if path.is_dir():
            candidates = sorted(path.glob("*.zip"))
        else:
            candidates = [path]
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            if candidate.suffix.lower() != ".zip":
                raise ValueError(f"Expected .zip archive: {candidate}")
            if not candidate.exists():
                raise FileNotFoundError(candidate)
            seen.add(resolved)
            archives.append(candidate)
    return archives


def _find_registry_member(archive: zipfile.ZipFile) -> str:
    """Find the asset registry member inside a draft archive."""
    candidates = [name for name in archive.namelist() if name.endswith("manifest/asset_registry.json")]
    if not candidates:
        raise ValueError("Draft archive does not contain manifest/asset_registry.json")
    if len(candidates) > 1:
        candidates.sort(key=len)
    return candidates[0]


def _normalize_draft_assets(archive_path: Path) -> tuple[dict[str, Any], list[DraftAsset]]:
    """Read draft asset metadata from a ZIP archive."""
    with zipfile.ZipFile(archive_path) as archive:
        registry_member = _find_registry_member(archive)
        registry = _read_zip_json_object(archive, registry_member)
        archive_root = registry_member.removesuffix("manifest/asset_registry.json")
        raw_batch = registry.get("batch")
        batch = raw_batch if isinstance(raw_batch, dict) else {}
        batch_id = str(batch.get("batch_id", "unknown"))
        batch_version = str(batch.get("version", "unknown"))
        raw_assets = registry.get("assets")
        if not isinstance(raw_assets, list):
            raise ValueError(f"Expected asset list in {archive_path}:{registry_member}")

        assets: list[DraftAsset] = []
        members = set(archive.namelist())
        for raw_asset in raw_assets:
            if not isinstance(raw_asset, dict):
                continue
            asset_id = raw_asset.get("asset_id")
            if not isinstance(asset_id, str) or not asset_id:
                continue
            raw_source_path = raw_asset.get("file")
            source_path = raw_source_path if isinstance(raw_source_path, str) and raw_source_path else f"png/{asset_id}.png"
            member = f"{archive_root}{source_path}"
            if member not in members:
                # Keep it in the report later as a missing source.
                member = source_path
            assets.append(
                DraftAsset(
                    asset_id=asset_id,
                    source_path=member,
                    archive_path=archive_path,
                    batch_id=batch_id,
                    batch_version=batch_version,
                )
            )
        return registry, assets


def _copy_zip_member(archive_path: Path, member: str, target_path: Path, *, dry_run: bool) -> None:
    """Copy a ZIP member to a target path without extracting unrelated files."""
    if dry_run:
        return
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        if member not in archive.namelist():
            raise FileNotFoundError(f"{archive_path}:{member}")
        with archive.open(member) as source, target_path.open("wb") as target:
            shutil.copyfileobj(source, target)


def import_asset_drafts(
    profile_dir: Path,
    draft_inputs: Iterable[Path],
    *,
    output_dir: Path,
    asset_root: Path | None = None,
    dry_run: bool = False,
    overwrite: bool = True,
) -> dict[str, Any]:
    """Import accepted draft ZIP assets into the profile asset root.

    Args:
        profile_dir: Visual profile directory with assets_manifest.json.
        draft_inputs: ZIP archive paths or directories containing ZIP archives.
        output_dir: Directory where the import report will be written.
        asset_root: Optional asset root override.
        dry_run: Whether to only report planned imports.
        overwrite: Whether existing target PNG files may be overwritten.

    Returns:
        JSON-serializable import report.
    """
    manifest_path = profile_dir / "assets_manifest.json"
    manifest = _read_json_object(manifest_path)
    resolved_asset_root = _resolve_asset_root(profile_dir, manifest, asset_root)
    targets = _manifest_targets(manifest)
    aliases = _load_alias_map(profile_dir)
    archives = _archive_paths(draft_inputs)

    imported: list[dict[str, Any]] = []
    skipped_unmapped: list[dict[str, Any]] = []
    skipped_missing_source: list[dict[str, Any]] = []
    skipped_existing: list[dict[str, Any]] = []
    overwritten_targets: list[dict[str, Any]] = []
    seen_targets: set[str] = set()
    batches: dict[str, dict[str, Any]] = {}

    for archive_path in archives:
        _, draft_assets = _normalize_draft_assets(archive_path)
        for draft_asset in draft_assets:
            batches.setdefault(
                draft_asset.batch_id,
                {
                    "batch_id": draft_asset.batch_id,
                    "version": draft_asset.batch_version,
                    "archives": set(),
                    "assets_seen": 0,
                    "assets_imported": 0,
                },
            )
            batch_report = batches[draft_asset.batch_id]
            batch_report["archives"].add(str(archive_path))
            batch_report["assets_seen"] += 1

            target_id = _resolve_target_id(draft_asset.asset_id, aliases, targets)
            if target_id is None:
                skipped_unmapped.append(
                    {
                        "source_asset_id": draft_asset.asset_id,
                        "archive": str(archive_path),
                        "reason": "no matching target in assets_manifest.json or asset_import_aliases.json",
                    }
                )
                continue

            target = targets[target_id]
            target_path = resolved_asset_root / target.relative_path
            with zipfile.ZipFile(archive_path) as archive:
                if draft_asset.source_path not in archive.namelist():
                    skipped_missing_source.append(
                        {
                            "source_asset_id": draft_asset.asset_id,
                            "source_path": draft_asset.source_path,
                            "archive": str(archive_path),
                            "target_asset_id": target_id,
                        }
                    )
                    continue

            if target_id in seen_targets:
                overwritten_targets.append(
                    {
                        "target_asset_id": target_id,
                        "source_asset_id": draft_asset.asset_id,
                        "archive": str(archive_path),
                        "target_path": str(target_path),
                    }
                )
            if target_path.exists() and not overwrite:
                skipped_existing.append(
                    {
                        "source_asset_id": draft_asset.asset_id,
                        "target_asset_id": target_id,
                        "target_path": str(target_path),
                    }
                )
                continue

            _copy_zip_member(archive_path, draft_asset.source_path, target_path, dry_run=dry_run)
            imported.append(
                {
                    "source_asset_id": draft_asset.asset_id,
                    "target_asset_id": target_id,
                    "kind": target.kind,
                    "archive": str(archive_path),
                    "source_path": draft_asset.source_path,
                    "target_path": str(target_path),
                    "batch_id": draft_asset.batch_id,
                    "batch_version": draft_asset.batch_version,
                }
            )
            batch_report["assets_imported"] += 1
            seen_targets.add(target_id)

    normalized_batches = []
    for batch in sorted(batches.values(), key=lambda item: item["batch_id"]):
        normalized_batches.append(
            {
                "batch_id": batch["batch_id"],
                "version": batch["version"],
                "archives": sorted(batch["archives"]),
                "assets_seen": batch["assets_seen"],
                "assets_imported": batch["assets_imported"],
            }
        )

    by_kind: dict[str, int] = {}
    for item in imported:
        kind = str(item["kind"])
        by_kind[kind] = by_kind.get(kind, 0) + 1

    report = {
        "schema_version": "asset-draft-import-report-v1",
        "profile": manifest.get("profile", profile_dir.name),
        "manifest": str(manifest_path),
        "asset_root": str(resolved_asset_root),
        "dry_run": dry_run,
        "overwrite": overwrite,
        "archives_total": len(archives),
        "assets_seen": sum(batch["assets_seen"] for batch in normalized_batches),
        "imported": len(imported),
        "by_kind": by_kind,
        "skipped_unmapped": skipped_unmapped,
        "skipped_missing_source": skipped_missing_source,
        "skipped_existing": skipped_existing,
        "overwritten_targets": overwritten_targets,
        "batches": normalized_batches,
        "imported_assets": imported,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "asset_draft_import_report.json"
    report["report_path"] = str(report_path)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def _print_report(report: dict[str, Any]) -> None:
    """Print a compact human-readable import summary."""
    print("Asset draft import:")
    print(f"  archives:        {report['archives_total']}")
    print(f"  assets seen:     {report['assets_seen']}")
    print(f"  imported:        {report['imported']}")
    print(f"  skipped unmapped:{len(report['skipped_unmapped']):>6}")
    print(f"  missing sources: {len(report['skipped_missing_source']):>6}")
    print(f"  overwritten:     {len(report['overwritten_targets']):>6}")
    print(f"  asset root:      {report['asset_root']}")
    print(f"  report:          {report['report_path']}")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Import accepted asset draft ZIP archives.")
    parser.add_argument("profile", type=Path, help="Visual profile directory")
    parser.add_argument("drafts", nargs="+", type=Path, help="Draft ZIP archives or directories containing ZIP archives")
    parser.add_argument("--output", type=Path, default=Path("output/visual_map/debug"), help="Output report directory")
    parser.add_argument("--asset-root", type=Path, default=None, help="Override asset root from assets_manifest.json")
    parser.add_argument("--dry-run", action="store_true", help="Only report imports without writing PNG files")
    parser.add_argument("--no-overwrite", action="store_true", help="Do not overwrite existing target PNG files")
    parser.add_argument("--json-only", action="store_true", help="Do not print compact text summary")
    return parser.parse_args()


def main() -> int:
    """Run the asset draft importer CLI."""
    args = parse_args()
    try:
        report = import_asset_drafts(
            args.profile,
            args.drafts,
            output_dir=args.output,
            asset_root=args.asset_root,
            dry_run=args.dry_run,
            overwrite=not args.no_overwrite,
        )
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if not args.json_only:
        _print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
