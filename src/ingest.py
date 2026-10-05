"""
Step 2. Pull one immutable snapshot of both sources and write a manifest.

Outputs:
  data/raw/pbp_<season>__<snapshot_date>.parquet    fourth downs only, kept columns
  data/raw/nfl4th_go_boost__<snapshot_date>.rds     nfl4th probabilities, as published
  data/raw/snapshot__<snapshot_date>.manifest.json  what was pulled, when, and hashes

Play-by-play is filtered to down == 4 on the way in. The full files are large
and every later step uses fourth downs only; the manifest records the
unfiltered row counts so the filter is auditable.

The .rds is saved byte-for-byte as published, so its hash can be checked
against the release.
"""

import hashlib
import io
import json
from datetime import datetime, timezone

import pandas as pd
import requests

from . import config


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def release_assets(repo: str, tag: str) -> dict:
    """Map asset name -> release metadata (url, size, updated_at)."""
    r = requests.get(config.GITHUB_API.format(repo=repo, tag=tag), timeout=60)
    r.raise_for_status()
    return {a["name"]: a for a in r.json()["assets"]}


def download(url: str) -> bytes:
    r = requests.get(url, timeout=300)
    r.raise_for_status()
    return r.content


def main() -> None:
    snapshot_date = datetime.now(timezone.utc).date().isoformat()
    manifest = {
        "snapshot_date": snapshot_date,
        "pulled_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seasons": config.SEASONS,
        "files": [],
    }

    # --- nfl4th probabilities ------------------------------------------------
    assets = release_assets(config.NFL4TH_REPO, config.NFL4TH_TAG)
    a = assets[config.NFL4TH_ASSET]
    path = config.RAW_DIR / f"nfl4th_go_boost__{snapshot_date}.rds"
    print(f"Pulling {a['name']}  (release updated {a['updated_at']})")
    path.write_bytes(download(a["browser_download_url"]))
    manifest["files"].append({
        "file": path.name,
        "source": a["browser_download_url"],
        "release_asset_updated_at": a["updated_at"],
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "filter": None,
    })

    # --- play-by-play, one season at a time ---------------------------------
    assets = release_assets(config.PBP_REPO, config.PBP_TAG)
    for season in config.SEASONS:
        a = assets[config.PBP_ASSET.format(season=season)]
        print(f"Pulling {a['name']}  (release updated {a['updated_at']})")
        full = pd.read_parquet(io.BytesIO(download(a["browser_download_url"])))
        missing = sorted(set(config.PBP_COLUMNS) - set(full.columns))
        if missing:
            raise KeyError(f"{a['name']} is missing expected columns: {missing}")

        fourth = full.loc[full["down"] == 4, config.PBP_COLUMNS]
        path = config.RAW_DIR / f"pbp_{season}__{snapshot_date}.parquet"
        fourth.to_parquet(path, index=False)
        manifest["files"].append({
            "file": path.name,
            "source": a["browser_download_url"],
            "release_asset_updated_at": a["updated_at"],
            "rows_unfiltered": int(len(full)),
            "rows_written": int(len(fourth)),
            "filter": "down == 4",
            "columns": config.PBP_COLUMNS,
            "sha256": sha256(path),
        })
        print(f"  {len(full):,} plays -> {len(fourth):,} fourth downs")

    out = config.RAW_DIR / f"snapshot__{snapshot_date}.manifest.json"
    out.write_text(json.dumps(manifest, indent=2))
    print(f"\nManifest: {out}")


if __name__ == "__main__":
    main()
