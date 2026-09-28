"""Measures bounded in-memory graph analytics, not end-to-end deployment throughput."""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from types import SimpleNamespace as N
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import networkx as nx
from app.analytics import analyze, sensitivity
p=argparse.ArgumentParser();p.add_argument('--nodes',type=int,default=1000);p.add_argument('--edges',type=int,default=4000);a=p.parse_args()
if not 2<=a.nodes<=2000 or not 1<=a.edges<=5000 or a.edges>a.nodes*(a.nodes-1)//2:
    p.error('Choose 2–2000 nodes and 1–5000 possible edges')
g=nx.gnm_random_graph(a.nodes,a.edges,seed=42)
nodes=[N(id=str(n)) for n in g]
edges=[N(id=str(i),source=str(u),target=str(v),status='accepted',polarity='asserted',relation='met',occurred_at='2026-01-01T00:00:00+00:00') for i,(u,v) in enumerate(g.edges)]
times=[]
for _ in range(5):
    t=time.perf_counter();analyze(nodes,edges);sensitivity(nodes,edges);times.append(time.perf_counter()-t)
print(json.dumps({'scope':'In-memory analytics only; not database/API/load test','nodes':a.nodes,'edges':a.edges,'runs_seconds':times,'median_seconds':statistics.median(times)},indent=2))
