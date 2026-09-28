# Scaling: implemented work and next gates

Version 3 improves organization and bounded data handling; it does not claim high-scale deployment has already been proven.

Implemented: modular routes/services; one authoritative SQL store; PostgreSQL-compatible persistence; durable import workers with transactional job claiming; chunked prefetch instead of per-row reads; replay protection; configurable body/graph budgets; paginated records and sources; two-hop focused views; sampled betweenness; capped candidate expansion; cleared completed-job payloads; fixed graph drawing budgets.

Large ingestion and large visualization are different problems. A 25 MB upload is not a reason to draw every relationship at once. The API asks for a date window or focus ID rather than returning an arbitrary truncated analysis. The frontend discloses its display limit.

Remaining bottlenecks: JSON parsing and conversion still materialize request bodies and drafts in memory; job payloads are stored in the database until processing completes; small graph analytics runs in API thread workers; large lead/identity requests can use durable analytical jobs; no distributed cache or external broker, object-storage ingestion stream, adaptive query planner, DB row-level security or production migration system. Endpoint lookups are indexed but some global counts and case-wide analytics can still be costly. Resource caps do not constitute throughput measurements.

For real large-scale use: move raw uploads to object storage with streaming parser jobs; partition event tables by case/time; add durable analytical jobs and snapshot caching keyed by case revision/window; add request/job quotas and dead-letter handling; add SSO, backup/restore and operational monitoring. If graph traversal remains a bottleneck, add a Neo4j read model using a transactional outbox and reconciliation, not independent dual writes.

Before any scale claim: measure end-to-end p50/p95/p99, throughput, failure rate, memory, queue delay and SQL lock waits with representative sizes and 1/10/50 concurrent clients; test worker crashes, retries and restore. Run PostgreSQL multi-worker integration tests. The local tests and benchmark in this package are not substitutes for those gates.

Configuration: MAX_UPLOAD_MB defaults to 25; MAX_GRAPH_EDGES defaults to 20000. Apply the same environment to API replicas. Do not raise limits without measuring memory and latency. SQLite is local development, one worker. Docker uses PostgreSQL and can scale worker processes. Docker execution must be verified on your machine.


## V3 measured/bounded behavior

- Client rendering: up to 500 nodes, 2,000 source-backed edges, 50 lead overlays. Counts disclose the limit; UI type/relation filters only affect rendering, while date/focus affect backend scope.
- Case graph: configured `MAX_GRAPH_EDGES` defaults to 20,000. Focus: 1,000 first-hop records and 2,000 two-hop records; excess returns an explicit error.
- Identity fingerprint: at most 20,000 entities and 20,000 records. Candidate blocks cap 200 IDs, 50,000 candidate pairs, 200 returned candidates. Truncation is disclosed. This can miss true matches; it is not lossless search.
- Leads: at most 100,000 wedge visits, 5,000 candidate pairs, 50 returned leads. Scores remain structural-window dependent.
- Background analytical jobs: durable result JSON in SQL, same transaction as completion, fair alternation with imports, best-effort five queued jobs per case. Unexpected worker exceptions retry after rollback. Completed results accumulate; retention/archival remains an operations task.
- Reports: bounded selected graph, latest 500 saved lead snapshots and latest 1,000 rows per history category, with explicit truncation text. Sources in the selected graph are included; standalone source-only notes are available through the Sources UI and are not included in this graph report.

The included research uses 100 nodes per seed and dense adjacency tensors. It is not a scalable GNN trainer. The checked import benchmark is an isolated local SQL operation, not end-to-end concurrent API throughput. Browser tests use real Chromium with requests fulfilled by FastAPI TestClient, not live TCP or remote browsers.
