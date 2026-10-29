import argparse
import csv
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

HEADER = ["recorded_at", "patient_id", "systolic", "diastolic", "heart_rate"]
LIMITS = {"systolic": (50, 300), "diastolic": (30, 200), "heart_rate": (20, 250)}


def data_file() -> Path:
    return Path(os.environ.get("DATA_DIR", "data")) / "readings.csv"


def read_rows(path: Path) -> list:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def add_row(path: Path, patient_id: str, systolic: int, diastolic: int, heart_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        if is_new:
            writer.writerow(HEADER)
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        writer.writerow([stamp, patient_id, systolic, diastolic, heart_rate])


def check_values(patient_id: str, values: dict) -> None:
    if not patient_id.strip():
        raise ValueError("patient_id must not be empty")
    for name, number in values.items():
        low, high = LIMITS[name]
        if not low <= number <= high:
            raise ValueError(f"{name} must be between {low} and {high} (got {number})")


def show(path: Path) -> int:
    rows = read_rows(path)
    print(f"File: {path}")
    for row in rows:
        print(f"  {row['recorded_at']}  {row['patient_id']}  BP {row['systolic']}/{row['diastolic']}  HR {row['heart_rate']}")
    print(f"Readings in file: {len(rows)}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Add a vitals reading to readings.csv, or show what is saved.")
    parser.add_argument("patient_id", nargs="?")
    parser.add_argument("systolic", nargs="?", type=int)
    parser.add_argument("diastolic", nargs="?", type=int)
    parser.add_argument("heart_rate", nargs="?", type=int)
    parser.add_argument("--show", action="store_true", help="print the saved readings instead of adding one")
    args = parser.parse_args(argv)

    path = data_file()

    if args.show:
        try:
            return show(path)
        except OSError as error:
            print(f"Problem with {path.parent}: {error.strerror or error}", file=sys.stderr)
            return 1

    values = {"systolic": args.systolic, "diastolic": args.diastolic, "heart_rate": args.heart_rate}
    if args.patient_id is None or None in values.values():
        parser.error("patient_id, systolic, diastolic and heart_rate are needed unless you use --show")

    try:
        check_values(args.patient_id, values)
    except ValueError as error:
        print(f"Not saved: {error}", file=sys.stderr)
        return 2

    try:
        add_row(path, args.patient_id.strip(), **values)
        count = len(read_rows(path))
    except OSError as error:
        print(f"Problem with {path.parent}: {error.strerror or error}", file=sys.stderr)
        return 1

    print(f"Saved reading for {args.patient_id.strip()}")
    print(f"File: {path}")
    print(f"Readings in file: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
