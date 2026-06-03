from __future__ import annotations

import argparse
import csv
from pathlib import Path


ROWS = [
    {"epoch": 1, "train_loss": 1.20, "val_loss": 1.05, "val_accuracy": 0.61},
    {"epoch": 2, "train_loss": 0.92, "val_loss": 0.84, "val_accuracy": 0.70},
    {"epoch": 3, "train_loss": 0.73, "val_loss": 0.65, "val_accuracy": 0.78},
    {"epoch": 4, "train_loss": 0.58, "val_loss": 0.54, "val_accuracy": 0.83},
    {"epoch": 5, "train_loss": 0.47, "val_loss": 0.46, "val_accuracy": 0.86},
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Synthetic successful training run.")
    parser.add_argument("--output", default="metrics.csv", help="CSV output path")
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("Starting synthetic training run")
    for row in ROWS:
        print(
            f"epoch={row['epoch']} "
            f"train_loss={row['train_loss']:.2f} "
            f"val_loss={row['val_loss']:.2f} "
            f"val_accuracy={row['val_accuracy']:.2f}"
        )

    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["epoch", "train_loss", "val_loss", "val_accuracy"],
        )
        writer.writeheader()
        writer.writerows(ROWS)

    print(f"Wrote metrics to {output_path}")
    print("Best val_accuracy=0.86 at epoch 5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
