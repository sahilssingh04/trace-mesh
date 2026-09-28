# Requested changes and implementation

1. **One full-access user:** one owner key; UI case creation, entity editing, relationship correction and bulk confirmation. Old role tokens disabled during bootstrap migration.
2. **Import failure:** exact demo2.json schema adapter added; readable errors; request budget raised to 25 MB and row/source budgets raised. The user's 12 KB file failed v1 schema, not size.
3. **UI:** new responsive sidebar layout, lighter design, force-positioned graph, node dragging, zoom, evidence inspector, cards and guided input. No frontend build/CDN required.
4. **Backend:** separated configuration/dependencies, routers and services; batched database lookups; paginated records; focused graph queries; resource budgets. High-scale production remains a validation task.
5. **Hidden links:** actual candidate generation, supporting paths, graph overlays and 0–100 uncalibrated confidence ranking. No automatic conversion of hypotheses into facts.
6. **Natural language:** offline conservative draft parser, source-only handling for unsupported language, manual entry and editable preview. Smaller starter example.
7. **Text/call logs:** delimiter/header detection, custom column mapping, CSV/TSV/TXT/JSONL/row-array JSON conversion, original column retention, downloaded canonical JSON.

Additional fixes: Python 3.12 launcher checks; SQLAlchemy updated; PostgreSQL driver removed from local requirements; separate postgres requirements; unknown/day-precision times preserved; starter seeding no longer overwrites user edits.
