#!/usr/bin/env python3
"""Fail-closed structural audit for the two manuscript PDFs and bibliography.

The reference ledger records preparation-time primary-source checks.  This
script validates ledger coverage and manuscript structure; it does not access
the network or substitute for scientific review.
"""
from __future__ import annotations

if not __debug__:
    raise RuntimeError("Paper audit must not run with Python -O")

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAPER = ROOT / "paper"
OUT = ROOT / "artifact" / "results" / "audits"


def balanced(text: str, start: int) -> tuple[str, int]:
    depth = 1
    i = start
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i], i + 1
        i += 1
    raise ValueError("unbalanced bibliography field")


def entries(text: str) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for match in re.finditer(r"@(\w+)\s*\{\s*([^,]+),", text):
        body, _ = balanced(text, match.end())
        values: dict[str, str] = {}
        pos = 0
        while True:
            field = re.search(r"(\w+)\s*=\s*\{", body[pos:])
            if not field:
                break
            start = pos + field.end()
            value, end = balanced(body, start)
            values[field.group(1).lower()] = value
            pos = end
        key = match.group(2).strip()
        if key in out:
            raise ValueError(f"duplicate bibliography key {key}")
        out[key] = {"type": match.group(1).lower(), **values}
    return out


def cited_keys(tex: str) -> tuple[set[str], dict[str, list[str]]]:
    used: set[str] = set()
    locations: dict[str, list[str]] = {}
    section = "Front matter"
    for line_no, line in enumerate(tex.splitlines(), 1):
        section_match = re.search(r"\\section\{([^}]+)\}", line)
        if section_match:
            section = section_match.group(1)
        for citation in re.finditer(r"\\cite\w*\{([^}]+)\}", line):
            for raw_key in citation.group(1).split(","):
                key = raw_key.strip()
                used.add(key)
                locations.setdefault(key, []).append(f"{section} (main.tex:{line_no})")
    return used, locations


def find_heading_page(document, heading: str) -> list[int]:
    return [index + 1 for index, page in enumerate(document) if heading in page.get_text()]


def assert_clean_log(path: Path) -> None:
    text = path.read_text(errors="replace")
    if "Overfull \\hbox" in text or "Overfull \\vbox" in text:
        raise AssertionError(f"overfull box in {path.name}")
    if re.search(r"Citation .* undefined|Reference .* undefined|There were undefined", text):
        raise AssertionError(f"unresolved reference in {path.name}")


def main() -> None:
    import fitz

    bib = entries((PAPER / "references.bib").read_text())
    tex = (PAPER / "main.tex").read_text()
    used, locations = cited_keys(tex)
    if len(bib) != 73 or set(bib) != used:
        raise AssertionError((len(bib), sorted(set(bib) - used), sorted(used - set(bib))))

    ledger_rows = list(csv.DictReader((PAPER / "reference-audit.csv").open(newline="")))
    ledger = {row["key"]: row for row in ledger_rows}
    if len(ledger_rows) != len(ledger) or set(ledger) != set(bib):
        raise AssertionError("reference ledger does not cover each bibliography key exactly once")
    required = ("title", "primary_anchor", "review_depth", "primary_check_date", "manuscript_usage")
    for key, row in ledger.items():
        if any(not row.get(field, "").strip() for field in required):
            raise AssertionError(f"incomplete reference ledger row: {key}")
        if key not in locations:
            raise AssertionError(f"uncited ledger row: {key}")

    pdf_paths = {
        "anonymous": PAPER / "hydrakeep-anonymous.pdf",
        "authored": PAPER / "hydrakeep-authored.pdf",
    }
    pdf_summary: dict[str, dict[str, object]] = {}
    forbidden = (
        "Haoyi Zhang",
        "Huaijin Ran",
        "Xunzhu Tang",
        "hyeliozhang@gmail.com",
        "huaijin003@e.ntu.edu.sg",
        "xunzhu.tang@uni.lu",
        "realdanieltang@gmail.com",
    )
    for kind, path in pdf_paths.items():
        document = fitz.open(path)
        if len(document) != 12:
            raise AssertionError(f"{kind} PDF has {len(document)} pages")
        references = find_heading_page(document, "References")
        appendix = find_heading_page(document, "Transaction Rules and Reproduction Details")
        if references != [9] or appendix != [11]:
            raise AssertionError(f"{kind}: references={references}, appendix={appendix}")
        page8_text = document[7].get_text()
        if "Conclusion" not in page8_text or len(page8_text.split()) < 650:
            raise AssertionError(f"{kind}: page 8 is not a substantive completed main page")
        full_text = "\n".join(page.get_text() for page in document)
        if kind == "anonymous":
            metadata = " ".join(str(value or "") for value in document.metadata.values())
            if any(token.lower() in (full_text + metadata).lower() for token in forbidden):
                raise AssertionError("anonymous PDF contains identifying author material")
            if document.metadata.get("author"):
                raise AssertionError("anonymous PDF has author metadata")
        else:
            if not all(name in full_text for name in forbidden[:3]):
                raise AssertionError("authored PDF is missing an author name")
            if not all(email in full_text for email in forbidden[3:]):
                raise AssertionError("authored PDF is missing an author email")
        pdf_summary[kind] = {
            "pages": len(document),
            "main_text_pages": 8,
            "reference_start_page": references[0],
            "appendix_start_page": appendix[0],
            "page_8_words": len(page8_text.split()),
        }

    tests_candidates = [
        ROOT / "artifact" / "results" / "tests.log",
        ROOT / "artifact" / "results" / "transactions" / "tests.log",
    ]
    test_log_path = next((path for path in tests_candidates if path.exists()), None)
    if test_log_path is None:
        raise RuntimeError("run the test suite before auditing")
    test_log = test_log_path.read_text(errors="replace")
    match = re.search(r"Ran (\d+) tests", test_log)
    if not match or "\nOK" not in test_log:
        raise AssertionError("test log is incomplete")
    tests = int(match.group(1))
    if tests != 119 or f"{tests} passing tests" not in tex:
        raise AssertionError("test count differs between evidence and manuscript")

    assert_clean_log(PAPER / "main.log")
    assert_clean_log(PAPER / "authored.log")
    if len(re.findall(r"\\bibitem", (PAPER / "main.bbl").read_text())) != len(bib):
        raise AssertionError("compiled bibliography count differs from references.bib")

    source = tex.split("\\begin{document}", 1)[0]
    if "\\documentclass[sigconf,anonymous,review]{acmart}" not in source:
        raise AssertionError("anonymous ACM class options changed")
    if "\\title{HydraKeep: Preserving Early Form Input across Web Hydration}" not in source:
        raise AssertionError("unexpected manuscript title")

    for key, row in ledger.items():
        row["manuscript_usage"] = "; ".join(dict.fromkeys(locations[key]))
    with (PAPER / "reference-audit.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ledger_rows[0].keys())
        writer.writeheader()
        writer.writerows(ledger[key] for key in bib)

    summary = {
        "manuscripts": pdf_summary,
        "bibliography_entries": len(bib),
        "research_publications": sum(value["type"] != "misc" for value in bib.values()),
        "specification_documentation_source_entries": sum(value["type"] == "misc" for value in bib.values()),
        "all_bibliography_entries_cited": set(bib) == used,
        "reference_ledger_rows": len(ledger_rows),
        "passing_tests_reported": tests,
        "unresolved_citations_or_references": False,
        "overfull_boxes": False,
        "publisher_class_options": "sigconf,anonymous,review",
        "anonymous_author_leak": False,
        "quantitative_inputs": "validated phase-grid, native-integration, transaction, typed-transaction, model, and witness records",
        "scope": "structural, citation-coverage, build-log, anonymity, and PDF-boundary checks; not acceptance prediction",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "paper.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
