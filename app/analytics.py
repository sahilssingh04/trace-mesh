"""Bounded graph views, explicit projections and explainable structural signals."""
from collections import defaultdict
from difflib import SequenceMatcher
import math
import networkx as nx
from sqlalchemy import select
from .models import Entity, Edge

from .config import MAX_GRAPH_EDGES
MAX_EDGES = MAX_GRAPH_EDGES


def snapshot(db, case, start=None, end=None, include_pending=False):
    q = select(Edge).where(Edge.case_id == case)
    q = q.where(Edge.status.in_(['accepted', 'pending']) if include_pending else Edge.status == 'accepted')
    if start or end: q = q.where(Edge.occurred_at != '')
    if start:
        q = q.where(Edge.occurred_at >= start)
    if end:
        q = q.where(Edge.occurred_at <= end)
    edges = list(db.scalars(q.order_by(Edge.occurred_at, Edge.id).limit(MAX_EDGES + 1)))
    if len(edges) > MAX_EDGES:
        raise ValueError(f'Window exceeds {MAX_EDGES:,} relationships. Narrow the dates or choose an entity neighborhood.')
    ids = set(x for e in edges for x in (e.source, e.target))
    nodes = list(db.scalars(select(Entity).where(Entity.case_id == case, Entity.id.in_(ids)))) if ids else []
    return nodes, edges


def projection(nodes, edges):
    g = nx.Graph()
    g.add_nodes_from(n.id for n in nodes)
    for e in edges:
        if e.status == 'accepted' and e.polarity == 'asserted' and e.source != e.target:
            if not g.has_edge(e.source, e.target):
                g.add_edge(e.source, e.target, evidence=[])
            g[e.source][e.target]['evidence'].append(e.id)
    return g


def analyze(nodes, edges):
    g = projection(nodes, edges)
    if not nodes:
        return {'centrality': [], 'communities': [], 'conflicts': [], 'bursts': [], 'note': 'No relationships in this window.'}
    between = nx.betweenness_centrality(g, k=min(64, len(g)), seed=42)
    communities = list(nx.community.louvain_communities(g, seed=42)) if g.number_of_edges() else [{n} for n in g]
    conflicts = defaultdict(list)
    days = defaultdict(lambda: defaultdict(list))
    for e in edges:
        conflicts[(e.source, e.target, e.relation, e.occurred_at)].append(e)
        if e.status == 'accepted' and e.polarity == 'asserted' and e.relation == 'called' and e.occurred_at:
            days[(e.source, e.target)][e.occurred_at[:10]].append(e.id)
    # Minimum baseline prevents division by zero and dramatic scores for no-history pairs.
    bursts = []
    for pair, counts in days.items():
        ordered = sorted(counts)
        if len(ordered) < 4:
            continue
        baseline = sum(len(counts[d]) for d in ordered[:-1]) / len(ordered[:-1])
        current = len(counts[ordered[-1]])
        if baseline >= 2 and current >= max(6, 3 * baseline):
            bursts.append({'source': pair[0], 'target': pair[1], 'day': ordered[-1],
                           'count': current, 'baseline_observed_day_mean': baseline,
                           'ratio': current / baseline, 'evidence': counts[ordered[-1]],
                           'caveat': 'Only observed days; missing coverage can create apparent bursts.'})
    return {
        'centrality': [{'id': n, 'degree': g.degree(n), 'betweenness': round(between[n], 5)}
                       for n in sorted(g, key=lambda n: (-between[n], n))[:50]],
        'communities': [sorted(c) for c in communities],
        'conflicts': [{'evidence': [e.id for e in es], 'reason': 'Asserted and denied records at the same event time'}
                      for es in conflicts.values() if es[0].occurred_at and {'asserted', 'denied'} <= {e.polarity for e in es}],
        'bursts': bursts,
        'note': 'Undirected, unweighted projection of accepted asserted records. Parallel records collapse. '
                'Centrality and communities describe this selected window, not culpability. Seed 42; betweenness samples up to 64 nodes.'}


def resolution_candidates(nodes):
    buckets = defaultdict(list)
    for n in nodes:
        # Blocking reduces comparisons, but can miss aliases with different surname initials.
        key = n.label.casefold().split()[-1][:1] if n.label.strip() else ''
        buckets[(n.kind, key)].append(n)
    out, comparisons = [], 0
    for group in buckets.values():
        for i, a in enumerate(group):
            for b in group[i+1:]:
                comparisons += 1
                if comparisons > 20000:
                    return {'candidates': out[:100], 'truncated': True, 'comparisons': comparisons-1}
                similarity = SequenceMatcher(None, a.label.casefold(), b.label.casefold()).ratio()
                same = [k for k in ('phone', 'email', 'record_ref') if a.attrs.get(k) and a.attrs.get(k) == b.attrs.get(k)]
                if similarity >= .65 or same:
                    out.append({'left': a.id, 'right': b.id, 'name_similarity': round(similarity, 3),
                                'matching_fields': same, 'requires_review': True,
                                'reason': 'Candidate only. Shared identifiers may be recycled or shared; no automatic merge.'})
    return {'candidates': sorted(out, key=lambda x: (-len(x['matching_fields']), -x['name_similarity']))[:100],
            'truncated': len(out) > 100, 'comparisons': comparisons}


def colocations(nodes, edges, minutes=15):
    """Same recorded location and event-time proximity, not precise GPS inference."""
    from datetime import datetime
    groups = defaultdict(list)
    for e in edges:
        if e.status == 'accepted' and e.polarity == 'asserted' and e.relation == 'visited' and len(e.occurred_at) > 10:
            groups[e.target].append(e)
    out = []
    for location, events in groups.items():
        events.sort(key=lambda e: e.occurred_at)
        for i, a in enumerate(events):
            for b in events[i+1:]:
                gap = (datetime.fromisoformat(b.occurred_at)-datetime.fromisoformat(a.occurred_at)).total_seconds()/60
                if gap > minutes:
                    break
                if a.source != b.source:
                    out.append({'left': a.source, 'right': b.source, 'location': location,
                                'minutes_apart': gap, 'evidence': [a.id, b.id],
                                'caveat': 'Shared location is not evidence of a meeting; location precision is unknown.'})
                if len(out) >= 100:
                    return {'pairs': out, 'truncated': True}
    return {'pairs': out, 'truncated': False}


def sensitivity(nodes, edges):
    """Sensitivity under random missing links, not a confidence interval."""
    import random
    g = projection(nodes, edges)
    ranking = lambda x: set(sorted(x, key=lambda n: (-x.degree(n), n))[:min(5, len(x))])
    reference = ranking(g)
    samples = []
    for seed in range(10):
        rng = random.Random(seed)
        altered = g.copy()
        altered.remove_edges_from(rng.sample(list(g.edges), int(g.number_of_edges()*.2)))
        samples.append(len(reference & ranking(altered))/len(reference) if reference else 1.0)
    return {'removed_edge_fraction': .2, 'seeds': list(range(10)),
            'top5_degree_overlap': samples, 'mean_overlap': sum(samples)/len(samples),
            'caveat': 'Uniform edge removal only. Real missingness is rarely random. Not confidence in any person or claim.'}
