from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Synthetic failing run.")
    parser.add_argument("--input", default="data/missing.csv", help="Missing input path")
    args = parser.parse_args()

    print("Starting failing task")
    print("Loading configuration")
    print(f"Opening input file: {args.input}")

    sys.stderr.write("Traceback (most recent call last):\n")
    sys.stderr.write('  File "fail.py", line 16, in main\n')
    sys.stderr.write(f"FileNotFoundError: required input '{args.input}' was not found\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
