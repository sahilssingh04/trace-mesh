# Evidence Weave 3.0

A local, single-owner investigation workspace. Import records, review evidence, resolve duplicate identities, and examine explainable leads. Every owner action has full access. This is a tested demonstration and research build, not a production or guilt-prediction system.

## Run on Windows (simple steps)

1. Install Python **3.12**, if it is missing. In Command Prompt run:

   ```cmd
   winget install --exact --id Python.Python.3.12
   ```

2. Close and reopen Command Prompt. Check:

   ```cmd
   py -3.12 --version
   ```

3. Extract this ZIP. Open the `investigation-workbench` folder. Double-click **start-demo.bat**, or run:

   ```cmd
   start-demo.bat
   ```

4. Keep both the server and worker windows open. Visit **http://127.0.0.1:8000**.
5. Open `secrets/users.json`. Copy the long key before the first colon and paste it into the login box. Do not share that file.
6. Select **V3 showcase · fictional fragmented records** in the case menu. Follow `docs/SIH_DEMO.md`.

There is no frontend build, paid API, or model download required for the application. Cytoscape is bundled locally. The optional research model is separate.

### If setup fails

- `No suitable Python runtime found`: install 3.12 using step 1, reopen your terminal, then retry.
- Old `.venv` uses Python 3.14: close project windows, rename `.venv` to `.venv-backup`, and rerun the launcher. Never delete your database to fix a Python environment.
- The old `typing.Union` / SQLAlchemy error: use the tested Python 3.12 launcher and updated requirements.
- `psycopg-binary==3.2.9` unavailable: the default SQLite install no longer requires PostgreSQL packages. Optional PostgreSQL uses `requirements-postgres.txt` with 3.2.13.
- Import or analysis stays queued: keep the worker window running. Start it manually with `.venv\Scripts\python -m app.worker` if needed.
- File too large: defaults are 25 MiB request bytes, 24 million conversion-input characters and 2 million characters per source. JSON escaping also consumes request bytes. Split large files into batches; this is not a word limit.
- Port 8000 busy: close the older project server first.

## Run on Linux or macOS

Install Python 3.12, then from this folder run:

```bash
bash start-demo.sh
```

## Upgrade an existing V2 workspace

Stop the old server and worker. Back up `workbench.db` and `secrets/`. Extract V3 into a new folder and copy those files into it. Start V3. Startup adds `identity_state`, `identity_decisions`, `hypotheses`, and `analysis_jobs`; existing source records and reviews are preserved. Do not copy the old virtual environment. The seed script only creates missing demo cases. Test on the backup copy before using important records. There is no general database migration framework yet.

## Feed your own dataset

1. Click **New case** and give it a name.
2. Open **Add data**.
3. Upload JSON, CSV, TSV, TXT or JSONL, or type short statements in **Write a note**.
4. Click **Preview**. Check names, direction, dates, and warnings. Download converted JSON if useful.
5. Click **Import into this case** and wait for the worker.
6. Open **Records & sources**. Review and confirm the relevant claims. Only accepted, asserted claims support leads.
7. Open **Resolve identities**. Check the original identifiers before merging. The right-hand identity becomes canonical.
8. Explore **Hidden links**, **Timeline & places**, and **Case brief**. Record a reason when reviewing a lead.
9. Use **Print report** to download an HTML document. Open it in a browser and print/save as PDF.

The exact supplied `demo2.json` remains supported: 35 entities, 47 sources and 49 relationships. Delimited call logs in `.txt` are detected. Custom headers can be mapped in the upload panel. Natural language is conservative: uncertain, complex and ambiguous statements remain source-only notes. Manual relationship entry handles those cases without inventing facts.

## What the scores mean

Identity scores prioritize potential duplicates; a name match alone cannot become a likely match. Merging requires your reason. Undo merges in reverse order to avoid breaking dependent identity groups. All original entities, endpoints and sources remain available.

A **lead score** ranks missing connections from accepted evidence. It is not calibrated probability. Its inspector lists paths, original directions, record IDs and signed signal contributions. Reviewing a lead never creates an observed relationship. Saved snapshots retain their scope and algorithm version; older snapshots may refer to older entity names or decisions.

## What is in the folders?

| Path | Purpose |
|---|---|
| `app/main.py` | Starts the API and serves the interface |
| `app/models.py` | Evidence, review, identity, hypothesis and job tables |
| `app/routes/` | Case, import, graph and intelligence API endpoints |
| `app/services/` | File conversion, identity matching, link scoring and analytical worker logic |
| `app/static/` | Local interface, styles and bundled graph library |
| `scripts/` | Setup, demo seeding and verification tools |
| `data/` | Fictional examples and call-log templates |
| `research/benchmark.py` | Real optional GraphSAGE and baseline evaluation |
| `tests/` | Regression, lifecycle and security checks |
| `verification/` | Test logs, browser screenshot, synthetic metrics and sample report |
| `docs/` | Architecture, demo guide, research, security and scaling notes |

## Tests and optional research

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python scripts/evaluate_resolution.py
```

Real browser verification requires a browser download:

```bash
python -m pip install playwright==1.51.0
python -m playwright install chromium --only-shell
python scripts/browser_smoke.py
```

Optional CPU research (not needed to run the application):

```bash
python -m pip install torch==2.7.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-research.txt
python research/benchmark.py --gnn
```

Without `--gnn`, only the classical baselines run (NumPy and scikit-learn still required). Five seeded model checkpoints and exact measured results are included under `verification/`. Do not load model files from untrusted sources. See `docs/RESEARCH_REVIEW.md` for protocol and limitations.

## Practical limits

The API supports bounded case views, not unlimited graphs. The client displays at most 500 entities / 2,000 evidence records, and explicitly reports the difference. Identity review caps at 20,000 records/entities, 50,000 candidate comparisons and 200 displayed candidates. Larger UI analyses queue through the worker. Geographic display is an offline longitude/latitude plot, not a street map or live tracker. The model benchmark is synthetic, not field validation. PostgreSQL multi-worker behavior and Windows execution were not tested in this Linux environment; the Windows launcher is supplied and inspected. See `docs/SCALING.md` before deployment.
