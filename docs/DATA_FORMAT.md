# Accepted data in version 2

Canonical JSON uses `entities`, `sources`, `edges`, as in data/demo.json. IDs are unique within a case. Relationships cite source_id and a verbatim excerpt; endpoints must exist in that case. Replay is idempotent; conflicting content under an existing ID fails atomically.

`occurred_at` accepts null (unknown), YYYY-MM-DD (day precision), or a timezone-aware ISO timestamp. Never supply made-up dates just to pass validation. Date/time fields without timezone in structured/call-log conversion use the UI's explicit offset, default +05:30. Source records preserve original values.

The supplied `demo2.json` structure is supported directly: persons, phones, organizations, vehicles, locations, cases, communications, transactions, organization_links, vehicle_movements, investigation_notes, dataset_info. Extra unrecognized sections produce an error. Entity attributes preserve the original row JSON. Ownership/organization links can remain undated. Cases map to case-mention relationships, not guilt. Narratives are stored as sources only; callers' personal locations and financial amounts are not fabricated into extra edges.

Call-log text must be a delimited file with headers, or JSON/JSONL objects with call columns. Automatic aliases:

| Meaning | Headers |
|---|---|
| Caller | caller, from, from_phone, source, calling_number, a_number |
| Callee | callee, to, to_phone, target, called_number, b_number |
| Timestamp | timestamp, datetime, occurred_at, start_time |
| Date | date, call_date |
| Time | time, call_time |

Custom UI mapping overrides caller/callee/timestamp headers. Numbers remain strings; spaces, parentheses and hyphens are normalized, but country codes are not invented. Phone-to-person ownership must come from additional evidence. Other fields stay in source row JSON. Invalid rows fail conversion with a row number; no silently dropped calls.

TXT prose supports a conservative English subject–verb–object subset. Unsupported/uncertain statements become source-only notes with warnings. It does not resolve pronouns, infer aliases, parse every language, or establish truth. The preview is editable and can be downloaded as JSON. Manual relationship entry covers unsupported cases.

PDF, XLSX, audio and OCR are not supported. Export CSV/UTF-8 text before import. Import creates pending records; the owner confirms/rejects them. Editing a source or endpoints requires a new record, retaining the old evidence and rejecting its relationship.


## V3 extensions

`Transaction` is now an allowed entity kind. The original edge schema and demo2 adapter remain compatible. Attributes remain a maximum of 12 string values; use `phone`, `email`, `record_ref`, `registration`, `aliases` (semicolon/comma/pipe separated), `organization`, and `location` for matching. Phone normalization does not guess country codes. `Location` entities may include `latitude` and `longitude` strings; valid ranges are -90..90 and -180..180. Existing `attrs.original` JSON fields are read for coordinates/identity context.

Canonical graph output adds `members` to entities and `original_source` / `original_target` to edges. These are derived output fields, not accepted input bundle fields. JSON report exports are report documents, not import bundles. Use conversion-preview Download JSON for a re-importable bundle.

Unknown event time is null/blank; date-only retains day precision, exact timestamps require timezone. Recorded-at is system ingestion time and is never substituted for event time. `showcase-v3.json` demonstrates fragmented identities and recorded locations.

Research fixture generation is separate from case imports; it does not send user records to external services.
