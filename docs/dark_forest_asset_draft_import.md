# Dark Forest Asset Draft Import

`asset_drafts/dark_forest/accepted/` is the staging area for accepted asset draft ZIP archives.

The project should not require manual PNG placement into `assets/dark_forest/`. Draft archives are imported through a command that reads each archive registry, maps draft ids to logical asset ids, and copies PNG files to the paths defined by `assets_manifest.json`.

## Workflow

```bash
mkdir -p asset_drafts/dark_forest/accepted
cp ~/Downloads/dark_forest_B*.zip asset_drafts/dark_forest/accepted/

./r import-asset-packs asset_drafts/dark_forest/accepted/
./r assets-full
./r
```

The import command writes:

```text
output/visual_map/debug/asset_draft_import_report.json
```

## Mapping rules

Draft package ids can differ from runtime asset ids. For example:

```text
forest_fill_01 -> forest.fill
road_straight_ns_01 -> road.straight_ns
decor_reeds_01 -> decor.reeds_01
```

Explicit mappings live in:

```text
top_down_visualgen/profiles/dark_forest/asset_import_aliases.json
```

The importer also tries simple automatic candidates such as `decor_reeds_01 -> decor.reeds_01`, but production mappings should be explicit when the draft id does not directly match the project id.

## Notes

- The importer does not extract the whole ZIP archive.
- Only PNG files listed in `manifest/asset_registry.json` are copied.
- The command is allowed to overwrite placeholder PNG files under `assets/dark_forest/`.
- Unmapped draft assets are reported and skipped instead of being guessed into random paths.
