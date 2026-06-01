# =============================================================================
# BUILT-UP SURFACE EXTRACTION — TANZANIA (incl. Zanzibar & Pemba)
# Definition : Gross building footprint area (m²) per 100m pixel
#              bounded by wall perimeter — matching 1:10K topographic specs
# Source     : GHSL GHS-BUILT-S P2023A (JRC, European Commission)
# Resolution : 100m | CRS: EPSG:4326
# Epochs     : 2010 (baseline ~2014), 2015, 2020
#
# OUTPUTS:
#   (A) Separate raster per epoch
#   (B) Multi-band stack (all epochs in one .tif)
#   (C) Built-up change rasters between consecutive epochs
#
# Run in terminal: python tz_builtup_extraction.py
# =============================================================================

import ee
import geemap
import geopandas as gpd
import numpy as np
import os
import requests
import zipfile
from pathlib import Path

# ------------------------------------------------------------------------------
# 0. AUTHENTICATE & INITIALIZE GEE
# ------------------------------------------------------------------------------
try:
    ee.Initialize(project="ee-ebanella736")  # replace with your GEE project ID
except Exception:
    ee.Authenticate()
    ee.Initialize(project="ee-ebanella736")  # replace with your GEE project ID

print("GEE initialized successfully")

# ------------------------------------------------------------------------------
# 1. CONFIGURATION
# ------------------------------------------------------------------------------
CONFIG = {
    "country"    : "Tanzania",
    "iso3"       : "TZA",
    "resolution" : 100,           # metres
    "crs"        : "EPSG:4326",
    "output_dir" : "outputs/tz_builtup",
    "gee_folder" : "GEE_TZ_BuiltUp",
}

# GHSL epochs: 2010 = baseline (~2014), 2015, 2020 = most recent
EPOCHS = [2010, 2015, 2020]

# Create output directories
for folder in ["separate", "change", "stack"]:
    Path(f"{CONFIG['output_dir']}/{folder}").mkdir(parents=True, exist_ok=True)

print("=" * 65)
print("  Built-up Surface Extraction — Tanzania + Zanzibar + Pemba")
print("=" * 65)
print(f"Definition : m² of gross building footprint per 100m pixel")
print(f"Source     : GHSL GHS-BUILT-S P2023A")
print(f"Epochs     : {', '.join(map(str, EPOCHS))}")
print(f"Resolution : {CONFIG['resolution']}m | CRS: {CONFIG['crs']}\n")

# ------------------------------------------------------------------------------
# 2. TANZANIA BOUNDARY (MAINLAND + ZANZIBAR + PEMBA)
# ------------------------------------------------------------------------------
print("===== Loading Tanzania Boundary =====")

# Load Tanzania boundary from GEE (includes Zanzibar & Pemba automatically)
tz_national = (
    ee.FeatureCollection("FAO/GAUL/2015/level0")
    .filter(ee.Filter.eq("ADM0_NAME", "United Republic of Tanzania"))
)

# Verify geometry loaded
tz_info = tz_national.getInfo()
print(f"Tanzania boundary loaded: {len(tz_info['features'])} feature(s)")

# Area of interest for all GEE operations
aoi = tz_national.geometry()

# Also load region-level for island confirmation
tz_regions = (
    ee.FeatureCollection("FAO/GAUL/2015/level1")
    .filter(ee.Filter.eq("ADM0_NAME", "United Republic of Tanzania"))
)

region_names = tz_regions.aggregate_array("ADM1_NAME").getInfo()
islands = [r for r in region_names if any(
    x in r.lower() for x in ["zanzibar", "pemba"]
)]
print(f"Island regions confirmed: {', '.join(islands)}\n")

# ------------------------------------------------------------------------------
# 3. HELPER FUNCTIONS
# ------------------------------------------------------------------------------

def export_and_download(image, description, folder=CONFIG["gee_folder"],
                        scale=CONFIG["resolution"], region=None, crs=CONFIG["crs"]):
    """Export EE image to Google Drive and download locally."""

    local_path = f"{CONFIG['output_dir']}/separate/{description}.tif"

    # Skip if already downloaded
    if os.path.exists(local_path):
        print(f"    Already exists, skipping: {description}.tif")
        return local_path

    if region is None:
        region = aoi

    task = ee.batch.Export.image.toDrive(
        image          = image,
        description    = description,
        folder         = folder,
        scale          = scale,
        region         = region,
        crs            = crs,
        maxPixels      = 1e13,
        fileFormat     = "GeoTIFF",
        formatOptions  = {"cloudOptimized": True}
    )
    task.start()
    print(f"    GEE task started: {description}")

    # Monitor task
    import time
    while task.active():
        status = task.status()["state"]
        print(f"    Status: {status}", end="\r")
        time.sleep(10)

    final_status = task.status()["state"]
    if final_status == "COMPLETED":
        print(f"\n    Task completed: {description}")
    else:
        raise RuntimeError(f"Task failed: {description} | State: {final_status}")

    # Download from Google Drive using geemap
    geemap.download_ee_image(
        image       = image,
        filename    = local_path,
        scale       = scale,
        region      = region,
        crs         = crs,
        max_tile_size = 3
    )
    print(f"    Downloaded: {description}.tif")
    return local_path


def get_raster_stats(path):
    """Print basic stats for a raster file."""
    import rasterio
    with rasterio.open(path) as src:
        data = src.read(1)
        valid = data[data != src.nodata] if src.nodata else data[~np.isnan(data)]
        valid = valid[valid >= 0]
        print(f"    Min: {valid.min():.1f} m²  |  "
              f"Max: {valid.max():.1f} m²  |  "
              f"Mean: {valid.mean():.1f} m²  |  "
              f"Built pixels: {(valid > 0).sum():,}")
        if valid.max() > 10000:
            n_exceed = (valid > 10000).sum()
            print(f"    [!] WARNING: {n_exceed:,} pixels exceed 10,000 m² "
                  f"(full pixel area) — check for artefacts")


# ------------------------------------------------------------------------------
# 4. EXTRACT BUILT-UP SURFACE PER EPOCH — OUTPUT (A): SEPARATE RASTERS
# ------------------------------------------------------------------------------
print("===== Extracting Built-up Surface per Epoch =====")
print("Band : built_surface")
print("Unit : m² of gross building footprint area per 100m pixel\n")

epoch_paths = {}

for epoch in EPOCHS:
    print(f"  Extracting epoch: {epoch}")

    # GHS-BUILT-S: built_surface band = m² of building footprint per pixel
    builtup = (
        ee.ImageCollection("JRC/GHSL/P2023A/GHS_BUILT_S")
        .filter(ee.Filter.eq("system:index", str(epoch)))
        .first()
        .select("built_surface")
        .clip(aoi)
    )

    # Clamp negative values (area cannot be negative)
    builtup = builtup.max(ee.Image(0))

    description = f"builtup_ghsl_{epoch}_100m"

    try:
        path = export_and_download(builtup, description)
        epoch_paths[epoch] = path
        get_raster_stats(path)
        print()
    except Exception as e:
        print(f"    ERROR for epoch {epoch}: {e}\n")

print(f"Separate rasters saved to: {CONFIG['output_dir']}/separate/")
print(f"Epochs extracted: {len(epoch_paths)} of {len(EPOCHS)}\n")

# ------------------------------------------------------------------------------
# 5. BUILD MULTI-BAND STACK — OUTPUT (B)
# ------------------------------------------------------------------------------
print("===== Building Multi-band Stack =====")

import rasterio
from rasterio.enums import Resampling

stack_path = f"{CONFIG['output_dir']}/stack/tz_builtup_stack_2010_2015_2020_100m.tif"

if len(epoch_paths) > 0:
    # Read all epoch rasters
    raster_data = {}
    profile     = None

    for epoch, path in epoch_paths.items():
        with rasterio.open(path) as src:
            raster_data[epoch] = src.read(1)
            if profile is None:
                profile = src.profile.copy()

    # Update profile for multi-band output
    profile.update(
        count   = len(epoch_paths),
        dtype   = "float32",
        compress = "lzw"
    )

    with rasterio.open(stack_path, "w", **profile) as dst:
        for i, (epoch, data) in enumerate(raster_data.items(), start=1):
            dst.write(data.astype("float32"), i)
            dst.set_band_description(i, f"builtup_m2_{epoch}")

    print(f"Multi-band stack saved : {os.path.basename(stack_path)}")
    print(f"Bands                  : {len(epoch_paths)}")
    print(f"Band names             : {' | '.join([f'builtup_m2_{e}' for e in epoch_paths])}")

    with rasterio.open(stack_path) as src:
        print(f"Dimensions             : {src.height} rows x {src.width} cols\n")

# ------------------------------------------------------------------------------
# 6. BUILT-UP CHANGE RASTERS — OUTPUT (C)
# ------------------------------------------------------------------------------
print("===== Computing Built-up Change Rasters =====")
print("Change = later epoch minus earlier epoch")
print("Positive values = new built-up | Negative = demolished\n")

sorted_epochs = sorted(epoch_paths.keys())

# Consecutive pairs: 2010->2015, 2015->2020
epoch_pairs = list(zip(sorted_epochs[:-1], sorted_epochs[1:]))

# Add full period pair: 2010->2020
if sorted_epochs[0] != sorted_epochs[-1]:
    epoch_pairs.append((sorted_epochs[0], sorted_epochs[-1]))

for from_epoch, to_epoch in epoch_pairs:
    if from_epoch not in epoch_paths or to_epoch not in epoch_paths:
        print(f"  Skipping {from_epoch}->{to_epoch}: missing raster")
        continue

    print(f"  Change {from_epoch} -> {to_epoch}:")

    with rasterio.open(epoch_paths[from_epoch]) as src_from:
        data_from = src_from.read(1).astype("float32")
        profile   = src_from.profile.copy()

    with rasterio.open(epoch_paths[to_epoch]) as src_to:
        data_to = src_to.read(1).astype("float32")

    # Compute change
    change = data_to - data_from

    # Mask nodata
    nodata_mask = np.isnan(data_from) | np.isnan(data_to)
    change[nodata_mask] = np.nan

    # Stats
    valid      = change[~np.isnan(change)]
    gained_px  = (valid > 0).sum()
    lost_px    = (valid < 0).sum()
    gained_km2 = round(valid[valid > 0].sum() / 1e6, 2)
    lost_km2   = round(abs(valid[valid < 0].sum()) / 1e6, 2)

    print(f"    Gained (new built-up) : {gained_px:,} pixels | {gained_km2} km²")
    print(f"    Lost   (demolished)   : {lost_px:,} pixels | {lost_km2} km²")
    print(f"    No change             : {(valid == 0).sum():,} pixels")

    # Save change raster
    change_path = (f"{CONFIG['output_dir']}/change/"
                   f"tz_builtup_change_{from_epoch}_to_{to_epoch}_100m.tif")
    profile.update(dtype="float32", compress="lzw", count=1)

    with rasterio.open(change_path, "w", **profile) as dst:
        dst.write(change, 1)
        dst.set_band_description(
            1, f"builtup_change_{from_epoch}_to_{to_epoch}"
        )

    print(f"    Saved: {os.path.basename(change_path)}\n")

# ------------------------------------------------------------------------------
# 7. FINAL SUMMARY
# ------------------------------------------------------------------------------
print("=" * 65)
print("  BUILT-UP SURFACE EXTRACTION COMPLETE — TANZANIA")
print("=" * 65)
print("Definition : Gross building footprint (m²) per 100m pixel")
print("Coverage   : Mainland Tanzania + Zanzibar + Pemba")
print("Epochs     : 2010 (baseline ~2014), 2015, 2020\n")
print("Output structure:")
print("  outputs/tz_builtup/")
print("  ├── separate/")
print("  │   ├── builtup_ghsl_2010_100m.tif")
print("  │   ├── builtup_ghsl_2015_100m.tif")
print("  │   └── builtup_ghsl_2020_100m.tif")
print("  ├── change/")
print("  │   ├── tz_builtup_change_2010_to_2015_100m.tif")
print("  │   ├── tz_builtup_change_2015_to_2020_100m.tif")
print("  │   └── tz_builtup_change_2010_to_2020_100m.tif")
print("  └── stack/")
print("      └── tz_builtup_stack_2010_2015_2020_100m.tif")
print("=" * 65)