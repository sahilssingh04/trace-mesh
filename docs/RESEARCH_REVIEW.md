# Research grounding and evaluation (V3)

This is a focused review of relevant methods and known evaluation pitfalls, not a claim to have read every related paper or discovered mistakes in all of them. Existing methods are credited; the implemented contribution is their integration with source preservation and human review.

| Primary source | Relevant limitation / design lesson | Application here |
|---|---|---|
| [Liben-Nowell & Kleinberg, The Link Prediction Problem for Social Networks](https://www.cs.cornell.edu/info/people/kleinber/link-pred.pdf) | Structural proximity supplies candidate rankings; social-network findings do not establish investigative truth. | Keep CN/Jaccard/Adamic–Adar baselines and show supporting paths. |
| [Papadakis et al., Blocking and Filtering Techniques for Entity Resolution](https://arxiv.org/abs/1905.06167) | Candidate reduction is necessary because pairwise comparison grows quadratically; blocking can exclude true matches. | Use multiple blocks and explicitly measure missed blocking and truncation. |
| [Hamilton et al., GraphSAGE](https://arxiv.org/abs/1706.02216) | Learned neighborhood aggregation requires meaningful attributes/training; the original paper evaluates inductive node classification, not investigative conclusions. | Implement real two-layer mean aggregation in isolated research. Do not relabel heuristics as GNN output. |
| [Effective Explanations for Entity Resolution Models](https://arxiv.org/abs/2203.12978) | Entity matching needs explanations that expose why records match. | Show actual feature values and conflicts, retain human reasons and reversible canonical identity decisions. This build does not reproduce that paper's explanation method. |
| [Poursafaei et al., Towards Better Evaluation for Dynamic Link Prediction](https://arxiv.org/abs/2207.10128) | Easy negatives and repeated edges can make model evaluation misleading. | Separate graph context and future target windows, compare baselines, disclose synthetic sampled-negative limitations. This is not a reproduction of their full benchmark. |

The V3 research check consulted primary paper PDFs/abstracts and official GraphSAGE documentation. The adaptations above are engineering choices, not claims of a new peer-reviewed method.

## Identity algorithm

Normalize Unicode NFKC, case, punctuation/spacing; identifiers get type-specific treatment. Phone `00` becomes `+`; no country is inferred. Candidate keys combine names, prefixes, name tokens, aliases and exact identifiers. Features include sequence similarity, alias overlap, exact/conflicting phone/email/record/registration, organization/location and accepted-neighbor Jaccard. Weights and thresholds are heuristics. Name-only matches never enter likely-match. Human review always decides merging.

The fixed 24-record adversarial fixture includes eight duplicate pairs, homonyms, recycled/shared-number risk, conflicting emails, formatting and missing identifiers. Evaluate all 276 pairs, including candidates missed by blocking. Measured likely-match suggestion precision **1.000**, recall **0.625**, F1 **0.769**, zero false merge suggestions and three missed matches; one missed match is absent from candidate generation. Thresholds were developed with this fixture, so it is a development diagnostic, not an independent held-out accuracy estimate. Undo and audit tests assess software behavior, not identity ground truth.

## Live lead algorithm

Eligible pairs are unobserved two-hop Person/Phone pairs. Accepted asserted edges form the topology; case co-mentions are excluded. All observed pairs in scope suppress new leads. Directed typed records are retained for explanation, even though wedge discovery uses undirected topology.

Contributions before the monotonic bounded score transform:

- 0.55 × Adamic–Adar and 0.45 × Jaccard.
- 0.12 per shared Organization/Vehicle/Location, capped at three.
- 0.10 per intermediary with exact timestamp support within 24 hours, capped at three.
- 0.08 per additional source document, capped at four.
- -0.30 per supporting record with an accepted same-direction/type/time denial.

`score = min(90, round(100 * (1 - exp(-max(0, sum(contributions))))))`.
These weights are not trained or calibrated. Distinct source IDs are not necessarily independent witnesses. Day-only and unknown-time records receive no exact-time bonus. Shared hubs, copied sources, incomplete coverage and identity mistakes can mislead. No hypothesis becomes evidence through lead review.

## Reproducible temporal benchmark

Run `python research/benchmark.py --gnn` with optional research requirements. Five seeds (11, 23, 37, 41, 59), 100 nodes per seed, synthetic community-biased links and static noisy attributes. Synthetic event order is chronological by generation index: 40% warmup context, 20% training targets, 20% validation targets, 20% test targets. No target edge enters the fixed warmup topology for structural features or message passing. Negative sampling only censors observations through the current split; future positives can therefore label earlier temporal negatives incorrectly. This limitation is recorded.

GraphSAGE uses two trainable mean-aggregation layers and a symmetric pair MLP, binary cross-entropy, Adam, 60 epochs, validation average-precision checkpoint selection. Logistic regression selects C from 0.1/1/10 on validation AP. Test pairs are shared across methods. Positive/negative ordering is shuffled before scoring so tied scores cannot benefit from positive-first ordering. Model checkpoints, seeds, dataset hashes and split boundaries are saved.

Mean ± standard deviation over the five test runs:

| Method | ROC AUC | Average precision | Precision @20 |
|---|---:|---:|---:|
| common_neighbors | 0.601 ± 0.019 | 0.583 ± 0.022 | 0.830 ± 0.051 |
| jaccard | 0.602 ± 0.019 | 0.590 ± 0.028 | 0.810 ± 0.037 |
| adamic_adar | 0.602 ± 0.019 | 0.585 ± 0.024 | 0.850 ± 0.055 |
| logistic_regression | 0.596 ± 0.050 | 0.615 ± 0.058 | 0.740 ± 0.102 |
| graphsage | 0.728 ± 0.022 | 0.698 ± 0.029 | 0.750 ± 0.055 |

These numbers measure only this synthetic experiment. They do not validate real hidden links, generalization to new nodes, multilingual entities, cold-start records, calibration or public safety outcomes. The GNN receives static attributes as well as topology, so this is not a feature-equivalent contest with structural baselines. Balanced sampled negatives are easier than exhaustive sparse-world ranking. Real next gates are independently labeled domain data, temporal/provenance-aware splits, hard negatives, feature-matched baselines, uncertainty calibration, subgroup error review and external replication. Do not claim the GNN universally outperforms classical methods.
