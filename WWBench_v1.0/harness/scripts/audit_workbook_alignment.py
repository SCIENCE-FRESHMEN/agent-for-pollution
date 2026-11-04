"""Audit an annotated literature workbook against the WWBench question bank.

The workbook is treated as an evidence inventory, not as executable instructions
or as a replacement for the question-bank schema.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd


# DOI suffixes may contain parentheses, e.g. ``10.1016/S0273-1223(97)00502-7``.
# Stop at whitespace and trim separators only after extraction.
DOI_RE = re.compile(r"10\.\d{4,9}/\S+", re.IGNORECASE)


def norm_doi(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip().lower()
    match = DOI_RE.search(text)
    if not match:
        return ""
    return match.group(0).rstrip(".,;:。；，、）]}>")


def doi_set(values: pd.Series) -> set[str]:
    out: set[str] = set()
    for value in values:
        out.update(norm_doi(part) for part in DOI_RE.findall(str(value)))
    return {doi for doi in out if doi}


def doi_counts(values: pd.Series) -> Counter[str]:
    counts: Counter[str] = Counter()
    for value in values:
        if value is None or pd.isna(value):
            continue
        for part in DOI_RE.findall(str(value)):
            doi = norm_doi(part)
            if doi:
                counts[doi] += 1
    return counts


def audit(workbook: Path, questions: Path) -> dict:
    sheets = pd.ExcelFile(workbook).sheet_names
    if len(sheets) < 2:
        raise ValueError(f"expected at least two workbook sheets, got {sheets}")
    full = pd.read_excel(workbook, sheet_name=0)
    stats = pd.read_excel(workbook, sheet_name=1)
    if full.shape[1] < 69:
        raise ValueError("workbook is missing the expected DOI column")

    source_col = full.columns[10]
    main_col = full.columns[0]
    cross_col = full.columns[2]
    salt_col = full.columns[3]
    anammox_col = full.columns[11]
    title_col = full.columns[20]
    abstract_col = full.columns[33]
    doi_col = full.columns[68]

    qdf = pd.read_csv(questions, encoding="utf-8-sig")
    qref_col = "参考文献" if "参考文献" in qdf.columns else qdf.columns[10]
    doi_frequency = doi_counts(full[doi_col])
    workbook_dois = set(doi_frequency)
    question_dois = doi_set(qdf[qref_col])

    exact_doi_cells = {str(value).strip().lower() for value in full[doi_col].dropna() if str(value).strip()}
    return {
        "workbook": str(workbook),
        "sheets": sheets,
        "main_rows": int(len(full)),
        "main_columns": int(full.shape[1]),
        "unique_doi": int(len(doi_frequency)),
        "exact_doi_cells": int(len(exact_doi_cells)),
        "nonempty_doi_cells": int(full[doi_col].notna().sum()),
        "doi_occurrences": int(sum(doi_frequency.values())),
        "duplicate_doi_occurrences": int(sum(max(0, count - 1) for count in doi_frequency.values())),
        "blank_titles": int(full[title_col].isna().sum()),
        "blank_abstracts": int(full[abstract_col].isna().sum()),
        "source_counts": {str(k): int(v) for k, v in full[source_col].value_counts(dropna=False).items()},
        "main_category_counts": {str(k): int(v) for k, v in full[main_col].value_counts(dropna=False).items()},
        "cross_stress_counts": {str(k): int(v) for k, v in full[cross_col].value_counts(dropna=False).items()},
        "salt_marker_counts": {str(k): int(v) for k, v in full[salt_col].value_counts(dropna=False).items()},
        "anammox_flag_nonempty": int(full[anammox_col].notna().sum()),
        "question_count": int(len(qdf)),
        "question_doi_count": int(len(question_dois)),
        "question_workbook_doi_overlap": int(len(question_dois & workbook_dois)),
        "question_doi_missing_from_workbook": sorted(question_dois - workbook_dois),
        "summary_sheet_rows": int(len(stats)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", required=True, type=Path)
    parser.add_argument("--questions", default=Path("data/questions.csv"), type=Path)
    parser.add_argument("--json", dest="json_path", type=Path)
    args = parser.parse_args()
    result = audit(args.workbook, args.questions)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.json_path:
        args.json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
