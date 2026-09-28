# Evidence Weave 2.0

**A single-owner workspace for records, call logs, evidence and explainable link suggestions.**

This version addresses all seven requested changes. It includes the exact `demo2.json` adapter, a redesigned interface, UI editing, larger imports, simple natural-language entry, call-log conversion and hidden-link hypotheses.

## Start here — Windows

1. Install **Python 3.12** if needed:

   ```cmd
   winget install --exact --id Python.Python.3.12
   ```

2. Close/reopen Command Prompt. Check `py -3.12 --version`.
3. Extract the ZIP into a new folder. Double-click **start-demo.bat**.
4. Open **http://127.0.0.1:8000**.
5. Open `secrets/users.json` in Notepad. Copy the long random JSON key (without quotes) and paste it into the login box.
6. You are the **one workspace owner**, with full access. There are no viewer, analyst or reviewer accounts.

The launcher checks your Python version instead of silently choosing a newer incompatible interpreter. PostgreSQL's driver is no longer part of the local SQLite installation. Keep the API and worker windows open.

If `.venv` uses the wrong Python, close the project, rename `.venv` to `.venv-backup`, and rerun the launcher. You do not need to delete your database.

### macOS / Linux

Install Python 3.12, then run `bash start-demo.sh` in the project folder. The launcher creates a virtual environment and starts the API and one worker.

### Manual start

From the project folder, using Python 3.12:

```cmd
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python scripts\bootstrap.py
.venv\Scripts\python scripts\seed_demo.py
.venv\Scripts\python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

In another Command Prompt in the same folder:

```cmd
.venv\Scripts\python -m app.worker
```

Linux equivalents use `python3.12` to create the environment and `.venv/bin/python` afterwards.

## Upgrading your existing project

**Close the API and worker windows first.** Back up the old project folder, particularly `workbench.db` and `secrets/`.

Safest route:

1. Extract this release into a **new folder**.
2. Copy your old `workbench.db` and entire `secrets` folder into the new folder if you want your old records. Do not copy `.venv`.
3. Run the new launcher. The database tables remain compatible; no old records are dropped.
4. Bootstrap keeps the former reviewer/admin key as the one owner key. Other old keys stop working. A `users.v1-backup.json` credential backup is created locally.
5. Select an existing case, create a new one, or use the new four-person starter case.

If you use PostgreSQL, do not copy SQLite files. Keep DATABASE_URL pointed at the existing authorized database and run bootstrap against that database. Test the upgrade on a backup before using sensitive records.

## A clearer starter example

The case **“Start here · four fictional people”** has four people and four recorded calls:

- Asha → Neel
- Ravi → Neel
- Asha → Mira
- Ravi → Mira

There is no recorded Asha ↔ Ravi relationship. **Hidden links** suggests it because they share two intermediaries. Click its card to see the supporting records. This is a hypothesis, not a discovered fact. A second structural candidate may also appear.

The starter case is seeded once. Relaunching never overwrites your changes.

## Test your demo2.json

Your file is about 12 KB. Its problem in v1 was **schema mismatch**, not a word limit: it uses `persons`, `phones`, `communications`, etc., instead of the old canonical `entities/sources/edges` structure.

1. Click **New case** and name it “Demo 2 test”. This keeps it separate from the starter data.
2. Open **Add data → Upload records**.
3. Choose your `demo2.json` (also included in `data/`). Keep “Detect automatically”.
4. Check the **UTC offset**, default `+05:30`. This is used for timestamps that have no timezone.
5. Click **Preview file**. Expected result: **35 entities, 47 sources, 49 relationships**.
6. Read the warnings, then click **Import into this case**.
7. Wait for Import activity to say **completed**. If it stays queued, start the worker.
8. Open **Records & sources → Confirm pending page**. Give a review reason. There are fewer than 100 records, so one page covers this dataset.
9. Open **Hidden links**. Suggestions now use the confirmed relationships. Original notes are available under Sources.

Ownership/organization links without dates remain **undated**. Date-only records retain day precision. Calls connect phone identifiers. They do not automatically prove which person made the call. Amounts, durations and narrative notes remain in original sources.

## Three ways to add data

### A. Natural-language notes

Open **Add data → Write a note**. For example:

```text
Asha called Ravi on 2026-01-10.
Ravi met Neel on 2026-01-11.
Asha visited Central Market.
Neel works for Eastern Logistics.
```

Click **Preview note**, inspect the draft, then import it. Dates are optional; missing dates remain unknown unless you explicitly supply a default event time.

The offline parser supports one explicit relationship per sentence: `called`, `met`, `owns`, `uses`, `visited`, `works for`, `transferred to`. It is **not general language understanding**. Negation, uncertainty, pronouns and compound statements are retained as source-only notes with warnings. For example, “Asha reportedly met Ravi” is not promoted to an asserted edge.

Names reuse deterministic IDs within a case. Two different people with the same name need separate IDs: use manual entry or edit the JSON preview. Person/phone type inference is basic; manual entry lets you select exact types.

### B. Call logs / text files

Upload `.csv`, `.tsv`, `.txt`, `.jsonl`, or a JSON array of call-log rows. A text file with columns must use comma, tab, pipe or semicolon separators and a header row.

```csv
caller,callee,timestamp,duration_seconds
+919000000001,+919000000003,2026-01-10T10:00:00+05:30,120
+919000000002,+919000000003,2026-01-10T10:15:00+05:30,85
```

Common caller/callee/date/time headers are recognized. Expand **Map custom call-log columns** for other column names. All original columns, including durations, remain in source JSON text. The interface offers **Download converted JSON**.

A random unstructured TXT call log may need its columns arranged first. There is no universal parser for every telecom vendor, PDF scan or Excel workbook. Unsupported input produces a specific error rather than silently dropping rows.

### C. Manual relationship entry

Open **Add data → Add a relationship manually**. Select existing entities or type new names, choose entity types and relation, enter a date if known, select asserted/denied/uncertain, and paste the supporting source text. Preview and import.

You can edit names/attributes by clicking a node. Click a relationship to confirm, reject or correct its relation/date/polarity. Edits are audited; source text remains immutable. To correct endpoints or replace source evidence, add a new relationship and reject the old one with a reason.

## Hidden links and confidence

Purple dashed graph lines and **Hidden links** cards are hypotheses. Solid source-backed relationships remain separate.

- Candidate pairs: same-type Person/Phone nodes with shared intermediaries and no direct active record in this window.
- Evidence: accepted/asserted records only; case co-mentions are excluded.
- Signals: Adamic–Adar (downweights popular hubs) and Jaccard similarity.
- Score: a documented 0–100 heuristic ranking rule capped at 90.
- Explanation: supporting paths, intermediary IDs and original evidence IDs.

**The displayed confidence is uncalibrated. It is not an actual probability, proof of association or guilt score.** A scientifically valid probability requires representative labelled data and calibration, which are not available here.

If the page is empty: confirm pending records, remove overly narrow dates/focus, or add connected data. The system does not invent a link when there is no supported candidate.

## Limits, clearly stated

There is no generic “word limit”. Defaults:

| Operation | Limit / behavior |
|---|---|
| HTTP request | 25 MB, configurable with MAX_UPLOAD_MB; JSON escaping/envelope counts toward the limit |
| Canonical bundle | Up to 50,000 entities, 50,000 sources and 50,000 relationships, subject to request size |
| Source text | Up to 2 million characters per source; request limit still applies |
| Graph analysis window | Up to 20,000 relationship records; narrow dates or focus on one entity beyond this |
| Focused graph | Up to 2,000 two-hop edge records, with a 1,000-edge first-hop guard |
| Browser drawing | First 120 nodes, up to 600 unique observed pairs, up to 15 suggested links; visible warning when node-limited |
| Records / sources | Paginated browsing; bulk confirmation operates on the current records page |
| Link generation | At most 100,000 two-hop pair expansions; truncation reported |

These limits are resource budgets, **not tested capacity guarantees**. An upload can be larger than one sensible graph view. The raw records remain in the database and can be explored through pages or filtered neighborhoods.

## Backend organization

| Location | Responsibility |
|---|---|
| `app/main.py` | App assembly and validation errors |
| `app/dependencies.py` | One owner key, database sessions, case lookup |
| `app/config.py`, `middleware.py` | Resource limits and request-body guard |
| `app/routes/workspace.py` | Cases, entities, edits, review and audit |
| `app/routes/imports.py` | Conversion previews, imports, jobs and retry |
| `app/routes/graph.py` | Scoped graph, paths, pagination, exports and analytics |
| `app/services/conversion.py` | Canonical JSON, demo2, call-log and text adapters |
| `app/services/links.py` | Explained hidden-link ranking |
| `app/ingest.py`, `worker.py` | Batched lookup, atomic imports, background workers |
| `app/models.py`, `schemas.py` | Persistence and validation |
| `app/static/` | Responsive dashboard with local assets |

See `docs/SCALING.md` for what is implemented and what remains. PostgreSQL is supported through `requirements-postgres.txt` and Docker Compose. Start with `python scripts/configure_docker.py`, then `docker compose up --build -d`, then `docker compose exec api python scripts/seed_demo.py`. Run `docker compose up -d --scale worker=3` only with PostgreSQL, never SQLite.

## Verification

```cmd
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest -q
```

Actual results and limitations are under `verification/`. Tests include your exact demo2 dataset, larger imports, conversion, record edits, link explanations and preservation of unknown dates. This remains a prototype: no real-world detection accuracy, calibrated confidence or national-scale throughput is claimed.

## Common fixes

- **Queued forever:** keep the worker running against the same database and folder.
- **Hidden links empty:** confirm imported claims on Records; remove date filters to include undated ownership links.
- **Entity ID conflict:** import a separate dataset into a new case or edit existing entities in the UI.
- **Unexpected conversion:** inspect warnings and advanced JSON; use manual entry for unsupported language.
- **Case graph too large:** use date filters or Focus entity ID; browse records through pagination.
- **Wrong Python:** the launcher now stops with installation instructions rather than proceeding into package errors.

The default app is local and uses no paid AI API. Original research review is retained as historical background in `docs/RESEARCH_REVIEW.md`; current behavior is documented here and in the v2 documents.
