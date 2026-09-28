# A seven-minute demonstration

Everything in the included examples is fictional. Explain that Evidence Weave helps an investigator prioritize follow-up; it makes no accusation.

1. Start `start-demo.bat`, log in, and select **V3 showcase · fictional fragmented records**. Open **Case brief**: 10 original entities and 11 source-backed records. Demo claims are pre-accepted and marked as fictional in sources and review history.
2. Open **Resolve identities**. Compare `Asha Rao` (`asha-a`) and `ASHA RAO` (`asha-b`). Their email matches after normalization. Compare the separate homonym with a conflicting email; do not merge that entity.
3. Merge the matching pair into the right entity. Use reason “Compared fictional email identifiers and original records”. Network count becomes nine. Inspect the canonical entity's original member IDs. Explain that sources were not rewritten.
4. Open **Hidden links**. Inspect the canonical Asha/Ravi candidate. Follow paths via Neel, Mira, the organization and location/vehicle. Explain each signed signal; a shared institution is weaker context, not proof. Open an underlying record and source hash. Choose **needs evidence** or **worth following** with a reason.
5. Open **Timeline & places**. Inspect exact timestamps, day-only events and the separate unknown-time entries. Move the slider and apply it; graph and geography share the same date window. Select a location marker to read supporting visits. Never describe proximity alone as a meeting.
6. Download **Print report**. Open it and print to PDF. It contains selected claims, provenance, score contributions, review history, audit and limitations. Older saved lead snapshots are clearly case history.
7. Return to identity history and **Undo merge**. The original ten entities reappear. Add a new short natural-language note or upload `data/call_logs.csv`, preview it, import it, and confirm evidence before expecting new leads.

## Questions to prepare for

- Why not a guilt score? A graph pattern cannot establish intent or culpability.
- Why human identity review? Homonyms, recycled numbers and missing identifiers create false matches.
- Is the lead score calibrated? No. It is an explained ranking rule with fixed weights.
- Is the GNN real? Yes, in an isolated reproducible synthetic experiment; it is not a field-validated decision engine. Show the actual benchmark output and limitations.
- What scales today? Bounded SQL queries, pagination, import and analytical workers, focus exploration. PostgreSQL concurrency and deployment load still require measurement.
- What is novel here? The integration of provenance, reversible human identity review, typed explanation paths and temporal review. Do not claim a new published algorithm or guaranteed competition outcome.
