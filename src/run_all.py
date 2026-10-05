"""
Run the whole pipeline in order.

Usage:
    python -m src.run_all              # everything, including a fresh download
    python -m src.run_all --no-ingest  # reuse the existing snapshot
    python -m src.run_all --from model # resume from a step
"""

import argparse
import subprocess
import sys

STEPS = ["ingest", "validate", "model", "analysis", "charts"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-ingest", action="store_true", help="reuse the existing snapshot")
    parser.add_argument("--from", dest="start", choices=STEPS, default=STEPS[0])
    args = parser.parse_args()

    steps = STEPS[STEPS.index(args.start):]
    if args.no_ingest and "ingest" in steps:
        steps.remove("ingest")
    # Each step runs in its own process. In one process, matplotlib's font DLL
    # failed to load after duckdb and scipy had loaded theirs (Windows).
    for step in steps:
        print(f"\n=== {step} ===", flush=True)
        subprocess.run([sys.executable, "-m", f"src.{step}"], check=True)


if __name__ == "__main__":
    main()
