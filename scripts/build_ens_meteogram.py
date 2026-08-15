#!/usr/bin/env python3
"""
Download ECMWF ENS global GRIB cache (2t) and overwrite latest file.

Output:
    data/ecmwf/global/ecmwf_ens_global_latest.grib

Usage:
    python scripts/build_ens_meteogram.py
    python scripts/build_ens_meteogram.py --fast-test
    python scripts/build_ens_meteogram.py --out /ruta/ecmwf_ens_global_latest.grib
"""

from __future__ import annotations

import argparse
import logging
import shutil
import tempfile
import time
from pathlib import Path

from ecmwf.opendata import Client

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_GLOBAL_OUT = REPO_ROOT / "data" / "ecmwf" / "global" / "ecmwf_ens_global_latest.grib"

# Producción
STEPS = list(range(6, 361, 6))  # 6..360 cada 6h
NUMBERS = list(range(1, 51))    # 50 perturbados (pf)

# Prueba rápida
FAST_TEST_STEPS = [6, 12]
FAST_TEST_NUMBERS = [1, 2]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("ens_global_download")


def download_global_ens(global_out: Path, fast_test: bool = False) -> None:
    t0 = time.perf_counter()

    steps = FAST_TEST_STEPS if fast_test else STEPS
    numbers = FAST_TEST_NUMBERS if fast_test else NUMBERS
    mode = "FAST_TEST" if fast_test else "FULL"

    log.info("Mode: %s | steps=%s | members=%s", mode, steps, numbers)
    log.info("Downloading ENS global (2t)...")

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".grib", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        client = Client(source="ecmwf")
        client.retrieve(
            stream="enfo",
            type="pf",
            param=["2t","tp"],
            step=steps,
            number=numbers,
            target=str(tmp_path),
        )

        log.info("Downloaded GRIB temp file → %s", tmp_path)

        global_out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(tmp_path, global_out)
        log.info("Global GRIB overwritten → %s", global_out)

    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

    elapsed = time.perf_counter() - t0
    log.info("Download completed.")
    log.info("Total runtime: %.1f s (%.2f min)", elapsed, elapsed / 60.0)
    print(f"[build_ens_meteogram] Tiempo total: {elapsed:.1f} s ({elapsed/60.0:.2f} min)")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Download ECMWF ENS global GRIB cache only.")
    p.add_argument("--out", type=Path, default=DEFAULT_GLOBAL_OUT, help="Path to overwritten global ENS GRIB")
    p.add_argument("--fast-test", action="store_true", help="Quick test mode (few steps/members)")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    download_global_ens(global_out=args.out, fast_test=args.fast_test)
