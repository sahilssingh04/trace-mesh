"""Deterministic synthetic temporal benchmark. NO evidence about real crime accuracy."""
import argparse
import itertools
import json
import random
import time
from pathlib import Path
import networkx as nx


def run(seed):
    rng=random.Random(seed)
    nodes=list(range(50))
    pairs=list(itertools.combinations(nodes,2))
    events=[]
    for day in range(20):
        for a,b in pairs:
            if rng.random() < (.08 if a//10==b//10 else .005):
                events.append((day,a,b))
    # Fixed chronological split. No future edge enters the training graph.
    train={(a,b) for d,a,b in events if d<14}
    future={(a,b) for d,a,b in events if d>=14}
    graph=nx.Graph();graph.add_nodes_from(nodes);graph.add_edges_from(train)
    historical=list(train-future)
    never=[p for p in pairs if p not in train|future]
    positives=sorted(future)
    results={}
    for negative_name, pool in [('never_observed',never),('historical',historical)]:
        negatives=rng.sample(sorted(pool),min(len(pool),len(positives)))
        candidates=positives+negatives
        # Explicitly rank ties by node ID so reproducibility doesn't depend on positive-first order.
        for model in ('common_neighbors','edge_memory'):
            score=lambda p: len(list(nx.common_neighbors(graph,*p))) if model=='common_neighbors' else int(p in train)
            ranked=sorted(candidates,key=lambda p:(-score(p),p))
            k=min(20,len(ranked))
            results[negative_name+'/'+model]={'precision_at_20':sum(p in future for p in ranked[:k])/k,
                'positive_count':len(positives),'negative_count':len(negatives),'k':k,
                'candidate_prevalence':len(positives)/len(candidates)}
    return {'seed':seed,'events':len(events),'train_pairs':len(train),'future_pairs':len(future),
            'new_future_pairs':len(future-train),'results':results}


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',default='artifacts/evaluation.json');a=p.parse_args()
    started=time.perf_counter()
    result={'scope':'Synthetic temporal interaction benchmark; not criminal-risk prediction',
            'split':'days 0–13 train; days 14–19 test; no learned parameters',
            'negative_semantics':'Unobserved within test horizon, not proven nonexistent relationships',
            'runs':[run(s) for s in (7,17,27,37,47)],
            'elapsed_seconds':time.perf_counter()-started,
            'limitations':['Synthetic community generator favors common-neighbor heuristics.',
                          'No GNN trained or evaluated.', 'Candidate sampling affects precision; not full-population precision.',
                          'Thresholds and uncertainty calibration require independent real-domain labels.']}
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2))
    print('Wrote',out)
if __name__=='__main__': main()
