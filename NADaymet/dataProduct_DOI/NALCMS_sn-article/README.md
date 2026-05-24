# NALCMS Scientific Data paper — scripts and documentation

Mirror of Python scripts and markdown documentation from the Scientific Data descriptor paper workspace (`NALCMS_sn-article`). Stored in the NA_surfdataGEN repository so figure-generation, comparison, validation, and diagnostic docs version with the surfdata pipeline.

**Source workspace (authoring):** `/Users/7xw/Documents/Work/papers/NALCMS_sn-article`

## Contents

| Path | Purpose |
|------|---------|
| `PaperFigures/scripts/` | Regenerate manuscript figures (MTCO, PFT panel, land-unit RGB, Li/E3SM comparisons, reprojection) |
| `DaymetVeg_LandUnit_DataProduct/comparison/` | External dataset comparison scripts |
| `internal_validation/` | Quantitative closure checks on surfdata and intermediate GeoTIFFs |
| `PaperFigures/*.md`, `DaymetVeg_LandUnit_DataProduct/*.md` | Great Lakes / `na_mask` fix documentation |
| `paper_improvement.md` | Paper revision notes |

Pipeline fix scripts that modify surfdata inputs live one level up in `NADaymet/dataProduct_DOI/` (`extend_na_mask_open_water.py`, `fix_great_lakes_lake_mask.py`, etc.).

## Sync from paper workspace

To refresh this folder from the paper repo (`.py`, `.md`, validation CSVs):

```bash
PAPER=/Users/7xw/Documents/Work/papers/NALCMS_sn-article
DEST=NADaymet/dataProduct_DOI/NALCMS_sn-article

cd "$PAPER" && find . -type f \( -name '*.py' -o -name '*.md' \) ! -path './.git/*' | while read -r f; do
  rel="${f#./}"
  mkdir -p "$DEST/$(dirname "$rel")"
  cp "$f" "$DEST/$rel"
done
```

## Run examples

Figure scripts (from `PaperFigures/scripts/`):

```bash
python3 generate_landtype_rgb.py
python3 generate_li_lulc_comparison.py
```

Internal validation:

```bash
python3 internal_validation/compute_internal_validation.py
```

See `PaperFigures/scripts/README.md` and `internal_validation/README.md` for defaults and options.
