#!/usr/bin/env python3
"""
Build a surfdata-like NetCDF by mapping fields from:
 - Combined percentages: NA_surfdata_nalcms2daymet_pft_landunit_temp.nc
 - PFT breakdown: /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymetELM_PFTs/ELM_PFT_output/pft_total_count_percentage.nc
 - Template surfdata: Surfdata.Daymet_NA.1km.2d_VegMapLandUnit.c251202.nc (for coords/aux vars)

Mappings:
 - lake_percentage        -> PCT_LAKE(y, x)
 - glacier_percentage     -> PCT_GLACIER(y, x)
 - urban_percentage       -> PCT_URBAN(numurbl=3, y, x) [stored in index 0; others 0]
 - pft_percentage         -> PCT_NATVEG(y, x)
 - pft0..16_percentage    -> PCT_NAT_PFT(natpft=17, y, x)
 - Preserve from template: LONGXY, LATIXY, gridID, AREA, natpft (index var), y/x coords

Output variables are float32 with zlib compression level 5.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import List

import numpy as np
import xarray as xr


def open_ds(path: str) -> xr.Dataset:
    errors: List[str] = []
    for eng in ("netcdf4", "h5netcdf", "scipy", None):
        try:
            ds = xr.open_dataset(path, engine=eng)
            _ = list(ds.dims)
            return ds
        except Exception as exc:
            errors.append(f"{eng}: {exc}")
    raise RuntimeError(f"Failed to open {path}:\n" + "\n".join(errors))


def main() -> None:
    ap = argparse.ArgumentParser(description="Build surfdata from combined and PFT breakdown files.")
    ap.add_argument("--template", required=True, help="Template surfdata file (for coords and aux vars)")
    ap.add_argument("--combined", required=True, help="Combined percentages file (NA_surfdata_nalcms2daymet_pft_landunit_temp.nc)")
    ap.add_argument("--pft-breakdown", required=True, help="PFT total count percentage file with pft0..16_percentage variables")
    ap.add_argument("--out", required=True, help="Output surfdata file path")
    ap.add_argument("--counts", default=None, help="Optional counts file (e.g., combined_pft_urban_lake_glacier_total_count.nc) to carry pft/urban/lake/glacier/total counts")
    ap.add_argument("--with-date-stamp", action="store_true", help="Append date stamp like cYYMMDD to output filename")
    ap.add_argument("--stamp-format", default="c%y%m%d", help="strftime format for stamp (default: c%%y%%m%%d)")
    args = ap.parse_args()

    tmpl = open_ds(args.template)
    cmb = open_ds(args.combined)
    pft = open_ds(args.pft_breakdown)

    # Accept either (y,x) or (lat,lon) in the template; target dims are (y,x)
    if not (("y" in tmpl.dims and "x" in tmpl.dims) or ("lat" in tmpl.dims and "lon" in tmpl.dims)):
        raise SystemExit(f"Template must provide y/x or lat/lon dims; found {list(tmpl.dims)}")
    src_ydim = "y" if "y" in tmpl.dims else "lat"
    src_xdim = "x" if "x" in tmpl.dims else "lon"
    ydim, xdim = "y", "x"
    ysize = int(tmpl.sizes[src_ydim]); xsize = int(tmpl.sizes[src_xdim])

    # Pull/align needed fields from combined
    need2d = {
        "lake_percentage": None,
        "glacier_percentage": None,
        "urban_percentage": None,
        "pft_percentage": None,
    }
    # Build 1D target coords based on template, renamed to y/x
    ycoord = tmpl[src_ydim].rename({src_ydim: ydim})
    xcoord = tmpl[src_xdim].rename({src_xdim: xdim})

    for k in list(need2d.keys()):
        if k not in cmb.data_vars:
            raise SystemExit(f"{k} missing in {args.combined}")
        v = cmb[k]
        # drop leading singleton dims e.g., 'file'
        v = v.squeeze(drop=True)
        # Rename last two dims to target y/x names if needed
        if len(v.dims) >= 2:
            ren = {}
            if v.dims[-2] != ydim: ren[v.dims[-2]] = ydim
            if v.dims[-1] != xdim: ren[v.dims[-1]] = xdim
            if ren:
                v = v.rename(ren)
        # align to template grid coords (name and size)
        v, _ = xr.align(v, ycoord, join="override")
        v, _ = xr.align(v, xcoord, join="override")
        need2d[k] = v

    # Build PCT_URBAN with numurbl=3
    numurbl = 3
    urban3 = xr.zeros_like(need2d["urban_percentage"]).expand_dims({"numurbl": numurbl})
    urban3 = urban3.astype(np.float32)
    urban3[0, :, :] = need2d["urban_percentage"].astype(np.float32)
    # PCT_LAKE / PCT_GLACIER / PCT_NATVEG
    pct_lake = need2d["lake_percentage"].astype(np.float32)
    pct_glac = need2d["glacier_percentage"].astype(np.float32)
    pct_natveg = need2d["pft_percentage"].astype(np.float32)

    # Build PCT_NAT_PFT, supporting either:
    # 1) a single variable PCT_NAT_PFT(natpft,*,*) or
    # 2) per-PFT variables pft0..16_percentage
    if "PCT_NAT_PFT" in pft.data_vars:
        v = pft["PCT_NAT_PFT"].squeeze(drop=True)
        # Rename spatial dims to y/x if needed and ensure order (natpft,y,x)
        ren = {}
        if "lat" in v.dims: ren["lat"] = ydim
        if "lon" in v.dims: ren["lon"] = xdim
        v = v.rename(ren)
        # If dims are out of order, transpose
        wanted = [d for d in ("natpft", ydim, xdim) if d in v.dims]
        v = v.transpose(*wanted)
        pct_natpft = v.astype(np.float32)
    else:
        pft_names = [f"pft{i}_percentage" for i in range(17)]
        pft_slices: List[xr.DataArray] = []
        for n in pft_names:
            if n in pft.data_vars:
                v = pft[n].squeeze(drop=True)
                v = v.astype(np.float32)
                # align with template spatial dims
                try:
                    v, _ = xr.align(v, tmpl[src_ydim], join="override")
                    v, _ = xr.align(v, tmpl[src_xdim], join="override")
                except Exception:
                    pass
                # rename last two dims to y/x if needed
                if len(v.dims) >= 2:
                    ren2 = {}
                    if v.dims[-2] != ydim: ren2[v.dims[-2]] = ydim
                    if v.dims[-1] != xdim: ren2[v.dims[-1]] = xdim
                    if ren2:
                        v = v.rename(ren2)
            else:
                # Create a zero field for the missing PFT
                v = xr.DataArray(
                    np.zeros((ysize, xsize), dtype=np.float32),
                    coords={ydim: ycoord, xdim: xcoord},
                    dims=(ydim, xdim),
                    name=n,
                )
            pft_slices.append(v)
        pct_natpft = xr.concat(pft_slices, dim="natpft")

    # Optional temperature field (AvgTempColdMonth) from combined file
    temp_da = None
    if "AvgTempColdMonth" in cmb.data_vars:
        v = cmb["AvgTempColdMonth"].squeeze(drop=True)
        # Rename spatial dims to y/x if needed
        if len(v.dims) >= 2:
            ren_t = {}
            if v.dims[-2] != ydim:
                ren_t[v.dims[-2]] = ydim
            if v.dims[-1] != xdim:
                ren_t[v.dims[-1]] = xdim
            if ren_t:
                v = v.rename(ren_t)
        # Align to template grid coords (name and size)
        try:
            v, _ = xr.align(v, ycoord, join="override")
            v, _ = xr.align(v, xcoord, join="override")
        except Exception:
            pass
        temp_da = v.astype(np.float32)

    # Build output dataset starting from template
    # Carry through coordinates and selected aux variables
    keep_vars = {}
    for name in ("LONGXY", "LATIXY", "gridID", "AREA"):
        if name in tmpl.data_vars:
            keep_vars[name] = tmpl[name].rename({src_ydim: ydim, src_xdim: xdim})
    # Keep natpft index variable if present
    if "natpft" in tmpl.variables:
        keep_vars["natpft"] = tmpl["natpft"]
    # y/x coords
    coords = {}
    coords[ydim] = ycoord
    coords[xdim] = xcoord
    out = xr.Dataset(data_vars=keep_vars, coords=coords)

    # Assign new percentages with proper dims
    # Ensure dims names match template (ydim, xdim)
    def ensure_dims(da: xr.DataArray) -> xr.DataArray:
        dims = list(da.dims)
        # rename spatial dims to template names if needed
        ren = {}
        if len(dims) >= 2:
            if dims[-2] != ydim: ren[dims[-2]] = ydim
            if dims[-1] != xdim: ren[dims[-1]] = xdim
        if ren:
            da = da.rename(ren)
        return da

    out["PCT_LAKE"] = ensure_dims(pct_lake)
    out["PCT_GLACIER"] = ensure_dims(pct_glac)
    out["PCT_NATVEG"] = ensure_dims(pct_natveg)
    out["PCT_URBAN"] = ensure_dims(urban3)
    out["PCT_NAT_PFT"] = ensure_dims(pct_natpft)
    if temp_da is not None:
        out["AvgTempColdMonth"] = ensure_dims(temp_da)

    # Bring original per-PFT counts from the PFT breakdown file if present
    for i in range(17):
        vn = f"pft{i}_count"
        if vn in pft.data_vars:
            v = pft[vn].squeeze(drop=True)
            try:
                v, _ = xr.align(v, tmpl[src_ydim], join="override")
                v, _ = xr.align(v, tmpl[src_xdim], join="override")
            except Exception:
                pass
            v = ensure_dims(v).astype(np.int16, copy=False)
            out[vn] = v

    # Optionally attach aggregate count variables for tracking
    if args.counts:
        cnt = open_ds(args.counts)
        for name in ("pft_total_count", "urban_count", "lake_count", "glacier_count", "total_count"):
            if name in cnt.data_vars:
                v = cnt[name].squeeze(drop=True)
                # Align to template and ensure dims
                try:
                    v, _ = xr.align(v, tmpl[src_ydim], join="override")
                    v, _ = xr.align(v, tmpl[src_xdim], join="override")
                except Exception:
                    pass
                v = ensure_dims(v).astype(np.int16, copy=False)
                out[name] = v

    # Set attributes
    out["PCT_LAKE"].attrs.update(long_name="percent lake", units="unitless")
    out["PCT_GLACIER"].attrs.update(long_name="percent glacier", units="unitless")
    out["PCT_URBAN"].attrs.update(long_name="percent urban for each density type", units="unitless")
    out["PCT_NATVEG"].attrs.update(long_name="total percent natural vegetation landunit", units="unitless")
    out["PCT_NAT_PFT"].attrs.update(long_name="percent plant functional type on the natural veg landunit (% of landunit)", units="unitless")
    if "AvgTempColdMonth" in out.data_vars:
        out["AvgTempColdMonth"].attrs.update(
            long_name="Average temperature of coldest month",
            units="C",
        )
    # Add descriptive attrs for count variables
    if "pft_total_count" in out.data_vars:
        out["pft_total_count"].attrs.update(
            long_name="Total natural vegetation PFT pixel count per gridcell",
            units="count",
            description="Sum of pft0_count..pft16_count; -1 indicates ocean/non-land.",
        )
    for i in range(17):
        vn = f"pft{i}_count"
        if vn in out.data_vars:
            out[vn].attrs.update(
                long_name=f"PFT {i} pixel count per gridcell (30 m tally)",
                units="count",
                description="Original per-PFT counts used to compute pft_total_count; -1 indicates ocean/non-land.",
            )
    for name, ln in [
        ("urban_count", "Urban pixel count per gridcell"),
        ("lake_count", "Lake pixel count per gridcell"),
        ("glacier_count", "Glacier pixel count per gridcell"),
        ("total_count", "Total pixel count per gridcell (PFT + Urban + Lake + Glacier)"),
    ]:
        if name in out.data_vars:
            out[name].attrs.update(
                long_name=ln,
                units="count",
                description="-1 indicates ocean/non-land.",
            )

    # Compression encoding
    enc = {}
    for k, v in out.data_vars.items():
        if np.issubdtype(v.dtype, np.floating):
            enc[k] = {"zlib": True, "complevel": 5, "dtype": "float32"}
        elif np.issubdtype(v.dtype, np.integer):
            enc[k] = {"zlib": True, "complevel": 5, "dtype": "int16"}
        else:
            enc[k] = {"zlib": True, "complevel": 5}

    # Possibly add date stamp to filename before extension
    out_path = args.out
    if args.with_date_stamp:
        import datetime as _dt
        stamp = _dt.datetime.now().strftime(args.stamp_format)
        base, ext = os.path.splitext(out_path)
        out_path = f"{base}.{stamp}{ext or '.nc'}"

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    out.to_netcdf(out_path, encoding=enc)
    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()

