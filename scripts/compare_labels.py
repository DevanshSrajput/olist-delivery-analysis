"""Compare human and model labels and write agreement outputs.

The two files use different taxonomies, so this script reports two views:

1. Literal comparison: exact strings, plus a case-insensitive check. This does
   not change any labels, but it is not a meaningful model-accuracy measure
   because most labels have no exact counterpart in the other file.
2. Crosswalk comparison: a documented in-memory mapping from the 8 human labels
   to the 6 PRD labels. The source CSVs are never modified; the mapped label is
   written as a separate column.

Outputs are written to outputs/.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import os
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HUMAN_PATH = PROJECT_ROOT / "labels_human.csv"
DEFAULT_MODEL_PATH = PROJECT_ROOT / "labels_model.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs"

MODEL_LABELS = (
    "Late or never arrived",
    "Wrong item",
    "Damaged or defective",
    "Poor quality or not as described",
    "Seller or customer service",
    "Other",
)

# Documented one-way crosswalk from the human 8-label scheme to the PRD
# taxonomy. Out of Stock / Cancelled is ambiguous; the alternate sensitivity
# check maps it to Other.
CROSSWALK = {
    "Delivery Issue / Not Received": "Late or never arrived",
    "Missing Item": "Wrong item",
    "Defective / Broken": "Damaged or defective",
    "Wrong Item": "Wrong item",
    "Poor Quality / Fake": "Poor quality or not as described",
    "Out of Stock / Cancelled": "Seller or customer service",
    "Customer Service Issue": "Seller or customer service",
    "Positive Feedback": "Other",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--human",
        type=Path,
        default=DEFAULT_HUMAN_PATH,
        help=f"human labels CSV (default: {DEFAULT_HUMAN_PATH})",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=DEFAULT_MODEL_PATH,
        help=f"model labels CSV (default: {DEFAULT_MODEL_PATH})",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"directory for CSV outputs (default: {DEFAULT_OUTPUT_DIR})",
    )
    return parser.parse_args(argv)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_label(label: str) -> str:
    """Case/punctuation normalization only; no semantic mapping."""
    return label.strip().rstrip(".").casefold()


def read_csv(path: Path, required: set[str]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        missing = required - fieldnames
        if missing:
            raise ValueError(
                f"{path} is missing columns {sorted(missing)}; "
                f"found {reader.fieldnames}"
            )
        return list(reader)


def cohen_kappa(pairs: list[tuple[str, str]], labels: list[str]) -> float:
    n = len(pairs)
    if n == 0:
        raise ValueError("cannot compute kappa on zero rows")
    observed = sum(1 for human, model in pairs if human == model) / n
    human_counts = Counter(human for human, _ in pairs)
    model_counts = Counter(model for _, model in pairs)
    expected = sum(
        (human_counts[label] / n) * (model_counts[label] / n)
        for label in labels
    )
    if math.isclose(expected, 1.0):
        raise ValueError("expected agreement is 1.0; kappa is undefined")
    return (observed - expected) / (1.0 - expected)


def build_matrix(
    pairs: list[tuple[str, str]],
    row_labels: list[str],
    column_labels: list[str],
) -> dict[tuple[str, str], int]:
    counts = Counter(pairs)
    return {
        (row, column): counts.get((row, column), 0)
        for row in row_labels
        for column in column_labels
    }


def write_csv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    os.replace(temporary, path)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not args.human.is_file():
        print(f"Human labels not found: {args.human}", file=sys.stderr)
        return 1
    if not args.model.is_file():
        print(f"Model labels not found: {args.model}", file=sys.stderr)
        return 1

    human_hash_before = sha256_file(args.human)
    model_hash_before = sha256_file(args.model)

    try:
        human_rows = read_csv(args.human, {"review_id", "comment", "label"})
        model_rows = read_csv(
            args.model, {"review_id", "comment", "label", "confidence"}
        )
    except ValueError as error:
        print(f"Input error: {error}", file=sys.stderr)
        return 1

    human_by_id = {row["review_id"]: row for row in human_rows}
    model_by_id = {row["review_id"]: row for row in model_rows}

    if len(human_by_id) != len(human_rows):
        print("Duplicate review_id in the human labels", file=sys.stderr)
        return 1
    if len(model_by_id) != len(model_rows):
        print("Duplicate review_id in the model labels", file=sys.stderr)
        return 1
    if set(human_by_id) != set(model_by_id):
        print("The two files do not contain the same review_ids", file=sys.stderr)
        return 1

    for review_id, human_row in human_by_id.items():
        model_row = model_by_id[review_id]
        if human_row["comment"] != model_row["comment"]:
            print(f"Comment mismatch for {review_id}", file=sys.stderr)
            return 1
        if model_row["label"] not in MODEL_LABELS:
            print(
                f"Unknown model label for {review_id}: {model_row['label']!r}",
                file=sys.stderr,
            )
            return 1
        if human_row["label"] not in CROSSWALK:
            print(
                f"No crosswalk for human label {human_row['label']!r} "
                f"(review {review_id})",
                file=sys.stderr,
            )
            return 1

    review_ids = sorted(human_by_id)
    human_raw = [human_by_id[review_id]["label"] for review_id in review_ids]
    model_labels = [model_by_id[review_id]["label"] for review_id in review_ids]
    human_normalized = [normalize_label(label) for label in human_raw]
    model_normalized = [normalize_label(label) for label in model_labels]
    human_mapped = [CROSSWALK[label] for label in human_raw]

    raw_exact_pairs = list(zip(human_raw, model_labels))
    raw_normalized_pairs = list(zip(human_normalized, model_normalized))
    mapped_pairs = list(zip(human_mapped, model_labels))

    raw_exact_labels = sorted(set(human_raw) | set(model_labels))
    raw_normalized_labels = sorted(set(human_normalized) | set(model_normalized))

    comparisons = [
        {
            "name": "raw_case_sensitive",
            "pairs": raw_exact_pairs,
            "labels": raw_exact_labels,
            "note": "No exact matches; Wrong Item vs Wrong item is a case difference.",
        },
        {
            "name": "raw_case_insensitive",
            "pairs": raw_normalized_pairs,
            "labels": raw_normalized_labels,
            "note": (
                "Only Wrong Item/Wrong item overlaps; not a valid measure of "
                "model accuracy because the label sets differ."
            ),
        },
        {
            "name": "mapped_crosswalk",
            "pairs": mapped_pairs,
            "labels": list(MODEL_LABELS),
            "note": (
                "In-memory crosswalk; source labels unchanged. "
                "Out of Stock/Cancelled mapped to Seller or customer service."
            ),
        },
    ]

    summary_rows: list[list[object]] = []
    for comparison in comparisons:
        pairs = comparison["pairs"]
        matches = sum(1 for human, model in pairs if human == model)
        n = len(pairs)
        accuracy = matches / n
        kappa = cohen_kappa(pairs, comparison["labels"])
        summary_rows.append(
            [
                comparison["name"],
                n,
                matches,
                f"{accuracy:.4f}",
                f"{kappa:.4f}",
                n - matches,
                comparison["note"],
            ]
        )

    # Sensitivity: the ambiguous Out of Stock / Cancelled label could map to
    # Other instead of Seller or customer service.
    alternate_crosswalk = dict(CROSSWALK)
    alternate_crosswalk["Out of Stock / Cancelled"] = "Other"
    alternate_pairs = [
        (alternate_crosswalk[human_by_id[review_id]["label"]],
         model_by_id[review_id]["label"])
        for review_id in review_ids
    ]
    alternate_matches = sum(1 for human, model in alternate_pairs if human == model)
    alternate_kappa = cohen_kappa(alternate_pairs, list(MODEL_LABELS))
    summary_rows.append(
        [
            "mapped_crosswalk_alt_stock_other",
            len(alternate_pairs),
            alternate_matches,
            f"{alternate_matches / len(alternate_pairs):.4f}",
            f"{alternate_kappa:.4f}",
            len(alternate_pairs) - alternate_matches,
            "Sensitivity only: Out of Stock/Cancelled mapped to Other.",
        ]
    )

    write_csv(
        args.out_dir / "q5_agreement_summary.csv",
        [
            "comparison",
            "n",
            "matches",
            "accuracy",
            "cohens_kappa",
            "disagreements",
            "note",
        ],
        summary_rows,
    )

    raw_human_labels = sorted(set(human_raw))
    raw_matrix = build_matrix(raw_exact_pairs, raw_human_labels, list(MODEL_LABELS))
    raw_matrix_rows = [
        [human_label]
        + [raw_matrix[(human_label, model_label)] for model_label in MODEL_LABELS]
        + [sum(raw_matrix[(human_label, model_label)] for model_label in MODEL_LABELS)]
        for human_label in raw_human_labels
    ]
    write_csv(
        args.out_dir / "q5_confusion_matrix_raw.csv",
        ["human_label", *MODEL_LABELS, "total"],
        raw_matrix_rows,
    )

    mapped_matrix = build_matrix(mapped_pairs, list(MODEL_LABELS), list(MODEL_LABELS))
    mapped_matrix_rows = [
        [human_label]
        + [mapped_matrix[(human_label, model_label)] for model_label in MODEL_LABELS]
        + [sum(mapped_matrix[(human_label, model_label)] for model_label in MODEL_LABELS)]
        for human_label in MODEL_LABELS
    ]
    write_csv(
        args.out_dir / "q5_confusion_matrix_mapped.csv",
        ["human_label_mapped", *MODEL_LABELS, "total"],
        mapped_matrix_rows,
    )

    write_csv(
        args.out_dir / "q5_label_crosswalk.csv",
        ["human_label", "model_label", "note"],
        [
            [
                human_label,
                target,
                (
                    "Ambiguous; sensitivity maps this to Other."
                    if human_label == "Out of Stock / Cancelled"
                    else "Low-score reviews with positive text; no positive label in the model taxonomy."
                    if human_label == "Positive Feedback"
                    else ""
                ),
            ]
            for human_label, target in CROSSWALK.items()
        ],
    )

    raw_disagreement_rows = []
    for review_id, human_label, human_norm, model_label, model_norm in zip(
        review_ids, human_raw, human_normalized, model_labels, model_normalized
    ):
        if human_norm != model_norm:
            raw_disagreement_rows.append(
                [
                    review_id,
                    human_by_id[review_id]["comment"],
                    human_label,
                    human_norm,
                    model_label,
                    model_norm,
                    model_by_id[review_id]["confidence"],
                ]
            )
    write_csv(
        args.out_dir / "q5_disagreements_raw.csv",
        [
            "review_id",
            "comment",
            "human_label",
            "human_label_normalized",
            "model_label",
            "model_label_normalized",
            "model_confidence",
        ],
        raw_disagreement_rows,
    )

    mapped_disagreement_rows = []
    for review_id, human_label, target, model_label in zip(
        review_ids, human_raw, human_mapped, model_labels
    ):
        if target != model_label:
            mapped_disagreement_rows.append(
                [
                    review_id,
                    human_by_id[review_id]["comment"],
                    human_label,
                    target,
                    model_label,
                    model_by_id[review_id]["confidence"],
                ]
            )
    mapped_disagreement_rows.sort(key=lambda row: (row[3], row[4], row[0]))
    write_csv(
        args.out_dir / "q5_disagreements_mapped.csv",
        [
            "review_id",
            "comment",
            "human_label",
            "human_label_mapped",
            "model_label",
            "model_confidence",
        ],
        mapped_disagreement_rows,
    )

    human_hash_after = sha256_file(args.human)
    model_hash_after = sha256_file(args.model)
    if human_hash_before != human_hash_after or model_hash_before != model_hash_after:
        print("Input labels changed during the run", file=sys.stderr)
        return 1

    print("Inputs")
    print(f"  human: {args.human} ({len(human_rows)} rows, {len(set(human_raw))} labels)")
    print(f"  model: {args.model} ({len(model_rows)} rows, {len(set(model_labels))} labels)")
    print("  same review_ids and comments: yes")
    print(f"  human sha256: {human_hash_before}")
    print(f"  model sha256: {model_hash_before}")
    print()

    print("Agreement summary")
    print(
        f"  {'comparison':<38}{'n':>4}{'match':>7}{'accuracy':>10}"
        f"{'kappa':>9}{'diff':>6}"
    )
    for row in summary_rows:
        print(
            f"  {row[0]:<38}{row[1]:>4}{row[2]:>7}{row[3]:>10}"
            f"{row[4]:>9}{row[5]:>6}"
        )
    print()

    print("Mapped confusion matrix (rows = mapped human, columns = model)")
    model_header = "".join(f"{label[:12]:>14}" for label in MODEL_LABELS)
    print(f"  {'human':<38}{model_header}{'total':>7}")
    for human_label, row in zip(MODEL_LABELS, mapped_matrix_rows):
        counts = "".join(f"{value:>14}" for value in row[1:])
        print(f"  {human_label:<38}{counts[:-14]}{row[-1]:>7}")
    print()

    print(f"Mapped disagreements ({len(mapped_disagreement_rows)})")
    for index, row in enumerate(mapped_disagreement_rows, start=1):
        review_id, comment, human_label, target, model_label, confidence = row
        print(
            f"  {index:>2}. {review_id[:8]}  "
            f"{human_label!r} -> {target!r}  |  model={model_label!r} "
            f"(confidence={confidence})"
        )
        print(f"      {comment!r}")
    print()

    print("Wrote")
    for name in (
        "q5_agreement_summary.csv",
        "q5_confusion_matrix_raw.csv",
        "q5_confusion_matrix_mapped.csv",
        "q5_label_crosswalk.csv",
        "q5_disagreements_raw.csv",
        "q5_disagreements_mapped.csv",
    ):
        print(f"  {args.out_dir / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
