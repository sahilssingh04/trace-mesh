# V3 changes

Preserved V2: imports and conversion formats, demo2 adapter, full-access owner, immutable original sources, import queue/replay, evidence editing/review, audits, pagination, conservative prose handling, manual entry and existing regression tests.

Added:
- Unicode and identifier normalization, multiple blocking keys, modular identity features, review categories and conflict penalties.
- Human merge/distinct decisions, stale fingerprint/revision checks, canonical graph relinking and reverse-order merge undo.
- Versioned, persisted hidden-link snapshots with typed paths, directions, temporal/context/source signals, contradiction penalties and separate lead reviews.
- Directed typed projection API; Transaction entity type.
- Local Cytoscape 3.30.4 with arrows, parallel edges, pan/zoom/drag, type/relation display filters, keyboard selection, neighborhood/component expansion and collapse.
- Dark interface, property fields instead of raw entity JSON editor, richer evidence and lead inspectors.
- Case brief, date slider, event precision list, offline coordinate map and escaped printable HTML report.
- Durable analytical jobs integrated into the existing worker.
- Fictional fragmented-identity showcase and seed protection.
- Adversarial resolution evaluation, temporal classical baselines and actual optional GraphSAGE experiment.
- Backend lifecycle/security regression and real Chromium end-to-end checks.

Known incomplete parts of the larger brief: arbitrary group splitting, street-map tiles and animated travel paths, field-trained models, multilingual/general-purpose extraction, distributed analytics, production migrations and full operational/load validation. See security/scaling/research documents.

## Investigator workflow UI refinement

- Restored the V2 light, restrained visual language while retaining V3 backend and investigation capabilities.
- Reduced the primary navigation to the four-step workflow: Resolve identities → Network → Explainable leads → Evidence.
- Moved secondary workspace functions under a collapsible More workspace menu.
- Simplified the network graph presentation: restrained labels, cleaner relationship lines, clear hypothesis styling, and less visual noise.
- Redesigned identity review cards to foreground the comparison evidence and merge/distinct actions.
- Redesigned potential-link cards to foreground the explanation and evidence/path counts, with technical scoring details collapsed.
- Redesigned the network inspector's potential-link view around "Why this connection?" and human review actions.
- Added a concise case brief flow linking the four investigation stages.
