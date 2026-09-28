# V3 verification

Executed with Python 3.12.14 on Linux. See environment-v3.json for exact packages.

- `python -m pytest -q`: **24 passed**, one third-party AnyIO/Starlette deprecation warning. Includes all 15 V2 tests and 9 V3 lifecycle/security/worker tests.
- `python scripts/browser_smoke.py`: **passed** in actual Chromium 134 / Playwright 1.51. FastAPI TestClient fulfills browser HTTP requests; this is not a live TCP deployment test. Owner login, demo2 upload/conversion, download, import worker, bulk confirmation, conservative prose, graph, inspectors, identity merge/undo, lead review, timeline, geo selection, HTML download, mobile width, and zero page errors.
- `python -m compileall -q app scripts research`: passed.
- `python scripts/benchmark_import.py`: 10,000 fictional rows, 101 entities, 10,000 sources and edges, 51 SELECTs; conversion 0.220 seconds, atomic SQLite import 0.964 seconds on this run. Not an API/concurrency benchmark.
- `python scripts/evaluate_resolution.py`: suggestion precision 1.000, recall 0.625, F1 0.769 on a fixed development fixture. Three missed matches, including one blocking miss. No automatic merges.
- `python research/benchmark.py --gnn`: five seeded actual CPU GraphSAGE training/evaluation runs with classical baselines. JSON results, dataset hashes, split boundaries and checkpoints included. Synthetic data only.

`dashboard-v3.png` was visually inspected. `showcase-report.html` is an actual downloaded fictional report from the browser flow. Older V2-named or unsuffixed legacy benchmark files are retained as historical artifacts; use the V3 files and research-benchmark.json for current results.

Not executed: Windows launcher on Windows, Docker/PostgreSQL multi-worker integration, sustained live-network load, independent security testing or real investigative accuracy validation. These remain deployment gates, not implied successes.
