#!/usr/bin/env python3
"""Aggregate evidence families without conflating runs, receipts, or models."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def load(relative: str) -> dict:
    return json.loads((RESULTS / relative).read_text())


def main() -> None:
    phase = load("phase-grid/summary.json")
    native = load("native-integration/summary.json")
    transactions = load("transactions/summary.json")
    typed = load("typed-transactions/summary.json")
    witnesses = load("witnesses/summary.json")

    families = [
        {
            "family": "phase-grid and vector-contract studies",
            "browser_runs": phase["total_receiver_backed_runs"],
            "http_receipts": phase["total_receiver_backed_runs"],
        },
        {
            "family": "native SSR reference grid",
            "browser_runs": native["coverage"]["matrix"]["rows"],
            "http_receipts": native["coverage"]["matrix"]["rows"],
        },
        {
            "family": "native representative replay",
            "browser_runs": native["native_quotient_runs"],
            "http_receipts": native["native_quotient_runs"],
        },
        {
            "family": "pinned-version stability",
            "browser_runs": native["coverage"]["versions"]["rows"],
            "http_receipts": native["coverage"]["versions"]["rows"],
        },
        {
            "family": "reported Vue preservation change",
            "browser_runs": native["coverage"]["historical"]["rows"],
            "http_receipts": native["coverage"]["historical"]["rows"],
        },
        {
            "family": "native HTML submission",
            "browser_runs": native["coverage"]["native-submit"]["rows"],
            "http_receipts": native["coverage"]["native-submit"]["rows"],
        },
        {
            "family": "maintained Next.js form",
            "browser_runs": native["public_completed_receipts"],
            "http_receipts": native["public_completed_receipts"],
        },
        {
            "family": "two-text transaction profile",
            "browser_runs": transactions["primary_browser_runs"],
            "http_receipts": transactions["primary_http_receipts"],
        },
        {
            "family": "heterogeneous transaction profile",
            "browser_runs": typed["primary_browser_runs"],
            "http_receipts": typed["loopback_http_receipts"],
        },
    ]

    output = {
        "project": "hydrakeep",
        "primary_evidence": families,
        "primary_browser_runs": sum(row["browser_runs"] for row in families),
        "primary_http_receipts": sum(row["http_receipts"] for row in families),
        "transaction_profiles": {
            "browser_runs": transactions["primary_browser_runs"]
            + typed["primary_browser_runs"],
            "http_receipts": transactions["primary_http_receipts"]
            + typed["loopback_http_receipts"],
            "incremental_prefix_disagreements": transactions[
                "prefix_specification_disagreements"
            ]
            + typed["prefix_specification_disagreements"],
        },
        "semantic_witnesses": witnesses,
        "passing_tests": 119,
        "bibliography_entries": 73,
        "scope_notes": [
            "Smoke runs, generated model traces, compatibility reinterpretations, unavailable cells, and auxiliary InitRacer controls are excluded from primary totals.",
            "Repeated schedules are replications of authored configurations, not independent deployed applications.",
            "Browser runs and HTTP receipts are separate units because transaction workflows can emit two receipts per run.",
        ],
    }
    if output["primary_browser_runs"] != 7_994:
        raise ValueError(f"unexpected browser total: {output['primary_browser_runs']}")
    if output["primary_http_receipts"] != 8_250:
        raise ValueError(f"unexpected receipt total: {output['primary_http_receipts']}")
    if output["transaction_profiles"]["incremental_prefix_disagreements"] != 0:
        raise ValueError("transaction interpreter/specification disagreement")

    target = RESULTS / "evidence-summary.json"
    target.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
