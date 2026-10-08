#!/usr/bin/env python3
"""Run the heterogeneous typed-control matrix in process-isolated shards.

Each shard contains one configuration and one repetition (four schedule cells).
A shard is accepted only after its raw rows and metadata pass structural checks.
The combined file is written atomically after every expected shard is valid.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import pathlib
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "fixtures/typed-transactions/cases.json").read_text())
OUT = ROOT / "results/typed-transactions"
SHARDS = OUT / "shards"
EXPECTED_CELLS = {("pre", ("t1", "t2")), ("pre", ("t2", "t1")),
                  ("post", ("t1", "t2")), ("post", ("t2", "t1"))}


def load_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
    return rows


def validate_shard(case: dict[str, Any], rep: int, path: pathlib.Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    meta_path = path.with_suffix(".meta.json")
    rendered_path = path.with_suffix(".rendered.json")
    for required in (path, meta_path, rendered_path):
        if not required.is_file():
            raise RuntimeError(f"missing shard output: {required}")
    rows = load_jsonl(path)
    if len(rows) != 4:
        raise RuntimeError(f"{path}: expected 4 rows, found {len(rows)}")
    cells: set[tuple[str, tuple[str, str]]] = set()
    run_ids: set[str] = set()
    for row in rows:
        if row.get("case") != case["id"] or row.get("rep") != rep:
            raise RuntimeError(f"{path}: case/repetition mismatch")
        if row.get("framework") != case["framework"] or row.get("pattern") != case["pattern"]:
            raise RuntimeError(f"{path}: configuration metadata mismatch")
        cell = (row.get("gap"), tuple(row.get("dispatch_order", [])))
        if cell not in EXPECTED_CELLS or cell in cells:
            raise RuntimeError(f"{path}: unexpected or duplicate schedule cell {cell}")
        cells.add(cell)
        run_id = row.get("run")
        if not isinstance(run_id, str) or run_id in run_ids:
            raise RuntimeError(f"{path}: missing or duplicate run id")
        run_ids.add(run_id)
        if row.get("error") or row.get("page_errors") or row.get("oracle", {}).get("status") == "inconclusive":
            raise RuntimeError(f"{path}: incomplete browser row {run_id}")
        if row.get("oracle") != row.get("reference"):
            raise RuntimeError(f"{path}: monitor/specification disagreement in {run_id}")
        if len(row.get("server_records", [])) != 2:
            raise RuntimeError(f"{path}: {run_id} does not contain two receiver records")
    if cells != EXPECTED_CELLS:
        raise RuntimeError(f"{path}: incomplete schedule grid")
    meta = json.loads(meta_path.read_text())
    if meta.get("runs") != 4 or meta.get("receipt_count") != 8 or meta.get("cases") != 1:
        raise RuntimeError(f"{meta_path}: inconsistent shard counts")
    rendered = json.loads(rendered_path.read_text())
    if set(rendered) != {case["id"]}:
        raise RuntimeError(f"{rendered_path}: wrong prerendered configuration")
    return rows, meta


def terminate_group(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)


def run_shard(case: dict[str, Any], rep: int, timeout: float, retries: int) -> pathlib.Path:
    SHARDS.mkdir(parents=True, exist_ok=True)
    stem = f"{case['id']}-r{rep}"
    rel = pathlib.Path("results/typed-transactions/shards") / f"{stem}.jsonl"
    target = ROOT / rel
    log = SHARDS / f"{stem}.log"
    command = [sys.executable, "scripts/run_typed_transactions.py", "--case", case["id"],
               "--repeats", "1", "--rep-offset", str(rep), "--output", str(rel)]
    failures: list[str] = []
    for attempt in range(1, retries + 2):
        for suffix in (".jsonl", ".meta.json", ".rendered.json"):
            candidate = target.with_suffix(suffix)
            if candidate.exists():
                candidate.unlink()
        started = time.monotonic()
        with log.open("a") as stream:
            stream.write(f"\n=== attempt {attempt} ===\n")
            stream.flush()
            process = subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                       text=True, start_new_session=True)
            try:
                code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                terminate_group(process)
                code = -signal.SIGKILL
            stream.write(f"exit={code} elapsed={time.monotonic()-started:.3f}s\n")
        if code == 0:
            try:
                validate_shard(case, rep, target)
                return target
            except Exception as exc:  # validation is part of the retry boundary
                failures.append(f"attempt {attempt}: {exc}")
        else:
            failures.append(f"attempt {attempt}: exit {code}")
    raise RuntimeError(f"shard {stem} failed: " + "; ".join(failures))


def atomic_write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=90.0,
                        help="wall-clock limit for one four-cell shard")
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--reuse", action="store_true",
                        help="validate and combine existing shards without launching browsers")
    args = parser.parse_args()
    if args.repeats < 1 or args.retries < 0 or args.timeout <= 0:
        raise SystemExit("repeats and timeout must be positive; retries must be nonnegative")

    started = time.monotonic()
    all_rows: list[dict[str, Any]] = []
    all_meta: list[dict[str, Any]] = []
    rendered: dict[str, str] = {}
    shard_paths: list[pathlib.Path] = []
    for case in CASES:
        for rep in range(args.repeats):
            path = SHARDS / f"{case['id']}-r{rep}.jsonl"
            if not args.reuse:
                path = run_shard(case, rep, args.timeout, args.retries)
            rows, meta = validate_shard(case, rep, path)
            all_rows.extend(rows)
            all_meta.append(meta)
            rendered.update(json.loads(path.with_suffix(".rendered.json").read_text()))
            shard_paths.append(path)
            print(f"accepted {case['id']} repetition {rep}", flush=True)

    expected = len(CASES) * args.repeats * 4
    if len(all_rows) != expected:
        raise RuntimeError(f"combined row count {len(all_rows)} != {expected}")
    all_rows.sort(key=lambda row: (row["case"], row["rep"], row["gap"], tuple(row["dispatch_order"])))
    run_ids = [row["run"] for row in all_rows]
    if len(run_ids) != len(set(run_ids)):
        raise RuntimeError("duplicate run identifiers across shards")
    combined = "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in all_rows)
    atomic_write(OUT / "runs.jsonl", combined)
    atomic_write(OUT / "runs.rendered.json", json.dumps(rendered, indent=2) + "\n")
    browser_versions = sorted({str(meta.get("browser")) for meta in all_meta})
    counts = collections.Counter(row["oracle"]["status"] for row in all_rows)
    meta = {
        "runs": len(all_rows),
        "cases": len(CASES),
        "repeats": args.repeats,
        "browser_versions": browser_versions,
        "counts": dict(sorted(counts.items())),
        "receipt_count": sum(len(row["server_records"]) for row in all_rows),
        "shards": len(shard_paths),
        "measured_shard_wall_seconds": round(sum(float(item.get("wall_seconds", 0)) for item in all_meta), 3),
        "orchestrator_wall_seconds": round(time.monotonic() - started, 3),
        "scope": "text, checkbox, single-select; paired React/Vue authored workflows; actual loopback receipts",
    }
    atomic_write(OUT / "runs.meta.json", json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
