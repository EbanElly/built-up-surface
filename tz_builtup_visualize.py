# =============================================================================
# VISUALIZATION — TANZANIA BUILT-UP SURFACE
# Visualizes one epoch of the extracted GHSL GHS-BUILT-S raster
# =============================================================================

import rasterio
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from rasterio.plot import show
from pathlib import Path

# ------------------------------------------------------------------------------
# CONFIGURATION — change epoch to 2010, 2015, or 2020
# ------------------------------------------------------------------------------
EPOCH      = 2020
RASTER_PATH = f"outputs/tz_builtup/separate/builtup_ghsl_{EPOCH}_100m.tif"

# ------------------------------------------------------------------------------
# LOAD RASTER
# ------------------------------------------------------------------------------
print(f"Loading built-up surface raster: epoch {EPOCH}")

with rasterio.open(RASTER_PATH) as src:
    data    = src.read(1).astype("float32")
    profile = src.profile
    extent  = [src.bounds.left, src.bounds.right,
               src.bounds.bottom, src.bounds.top]
    nodata  = src.nodata

# Mask nodata and zeros for cleaner display
data_masked = np.where(
    (data == nodata) | (data < 0) if nodata else data < 0,
    np.nan, data
)

# Stats
valid = data_masked[~np.isnan(data_masked)]
print(f"  Min  : {valid.min():.1f} m²")
print(f"  Max  : {valid.max():.1f} m²")
print(f"  Mean : {valid.mean():.1f} m²")
print(f"  Built pixels (>0): {(valid > 0).sum():,}")
print(f"  Total pixels     : {valid.size:,}\n")

# ------------------------------------------------------------------------------
# PLOT
# ------------------------------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(16, 8))
fig.patch.set_facecolor("#1a1a2e")

# --- Panel 1: Full Tanzania map ---
ax1 = axes[0]
ax1.set_facecolor("#0d0d1a")

# Use log scale to better show variation (built-up ranges widely)
data_log = np.where(data_masked > 0, np.log1p(data_masked), np.nan)

im = ax1.imshow(
    data_log,
    cmap   = "YlOrRd",
    extent = extent,
    aspect = "auto",
    interpolation = "nearest"
)

# Colorbar
cbar = plt.colorbar(im, ax=ax1, fraction=0.03, pad=0.04)
cbar.set_label("Built-up Surface (log m²)", color="white", fontsize=10)
cbar.ax.yaxis.set_tick_params(color="white")
plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white")

# Labels
ax1.set_title(f"Tanzania Built-up Surface — {EPOCH}\n(GHSL GHS-BUILT-S | 100m)",
              color="white", fontsize=13, fontweight="bold", pad=12)
ax1.set_xlabel("Longitude", color="white", fontsize=10)
ax1.set_ylabel("Latitude",  color="white", fontsize=10)
ax1.tick_params(colors="white")
for spine in ax1.spines.values():
    spine.set_edgecolor("#444")

# Annotate major cities
cities = {
    "Dar es Salaam" : (39.28, -6.80),
    "Mwanza"        : (32.90, -2.52),
    "Arusha"        : (36.68, -3.37),
    "Dodoma"        : (35.74, -6.17),
    "Zanzibar"      : (39.20, -6.17),
    "Mbeya"         : (33.45, -8.90),
}
for city, (lon, lat) in cities.items():
    ax1.plot(lon, lat, "o", color="#00d4ff", markersize=4, zorder=5)
    ax1.annotate(city, (lon, lat),
                 textcoords="offset points", xytext=(5, 3),
                 fontsize=7, color="#00d4ff", fontweight="bold")

# --- Panel 2: Histogram of built-up values ---
ax2 = axes[1]
ax2.set_facecolor("#0d0d1a")

built_only = valid[valid > 0]  # only pixels with actual built-up area

ax2.hist(
    built_only,
    bins  = 80,
    color = "#e74c3c",
    edgecolor = "#c0392b",
    alpha = 0.85,
    log   = True   # log y-axis because most pixels have low values
)

# Percentile lines
for pct, label, color in [(50, "Median", "#f39c12"),
                           (90, "90th pct", "#2ecc71"),
                           (99, "99th pct", "#00d4ff")]:
    val = np.percentile(built_only, pct)
    ax2.axvline(val, color=color, linestyle="--", linewidth=1.2, label=f"{label}: {val:.0f} m²")

ax2.set_title(f"Distribution of Built-up Values — {EPOCH}\n(pixels > 0 only)",
              color="white", fontsize=13, fontweight="bold", pad=12)
ax2.set_xlabel("Built-up Surface Area (m²)", color="white", fontsize=10)
ax2.set_ylabel("Pixel Count (log scale)",    color="white", fontsize=10)
ax2.tick_params(colors="white")
ax2.legend(facecolor="#1a1a2e", edgecolor="#444", labelcolor="white", fontsize=9)
for spine in ax2.spines.values():
    spine.set_edgecolor("#444")

# Stats box
stats_text = (
    f"Epoch        : {EPOCH}\n"
    f"Total pixels : {valid.size:,}\n"
    f"Built pixels : {(valid > 0).sum():,}\n"
    f"Built area   : {built_only.sum() / 1e6:.1f} km²\n"
    f"Mean (built) : {built_only.mean():.1f} m²\n"
    f"Max          : {built_only.max():.1f} m²"
)
ax2.text(0.97, 0.97, stats_text,
         transform=ax2.transAxes,
         fontsize=8, verticalalignment="top", horizontalalignment="right",
         color="white", family="monospace",
         bbox=dict(boxstyle="round", facecolor="#0d0d1a",
                   edgecolor="#444", alpha=0.9))

plt.suptitle(
    "Tanzania Built-up Surface — GHSL GHS-BUILT-S P2023A",
    color="white", fontsize=15, fontweight="bold", y=1.01
)
plt.tight_layout()

# Save
out_path = f"outputs/tz_builtup/tz_builtup_visualization_{EPOCH}.png"
plt.savefig(out_path, dpi=150, bbox_inches="tight",
            facecolor=fig.get_facecolor())
print(f"Visualization saved: {out_path}")
plt.show()