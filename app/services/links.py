"""Explainable missing-link candidates; ranking scores are NOT calibrated probabilities."""
from collections import defaultdict
from itertools import combinations
from math import log, exp
from datetime import datetime
from ..analytics import projection


def hidden_links(nodes,edges,limit=50):
    # Case co-mentions are not a basis for a predicted social link.
    usable=[e for e in edges if e.relation!='mentioned_in']
    g=projection(nodes,usable);by_id={n.id:n for n in nodes}
    observed={frozenset((e.source,e.target)) for e in edges}
    candidates=defaultdict(set);budget=0;truncated=False
    for middle in sorted(g):
        neighbors=sorted(g[middle])
        for a,b in combinations(neighbors,2):
            budget+=1
            if budget>100000: truncated=True;break
            if by_id[a].kind!=by_id[b].kind or by_id[a].kind not in ('Person','Phone'): continue
            if frozenset((a,b)) in observed: continue
            if (a,b) not in candidates and len(candidates)>=5000:truncated=True;break
            candidates[(a,b)].add(middle)
        if truncated: break
    output=[]
    edge_by={e.id:e for e in edges}
    denied={(e.source,e.target,e.relation,e.occurred_at) for e in edges if e.status=='accepted' and e.polarity=='denied' and e.occurred_at}
    for (a,b),shared in candidates.items():
        aa=sum(1/log(g.degree(c)) for c in shared if g.degree(c)>1)
        jaccard=len(shared)/len(set(g[a])|set(g[b]))
        paths=[{'via':m,'evidence':g[a][m]['evidence']+g[b][m]['evidence']} for m in sorted(shared)]
        evidence_ids=sorted({eid for p in paths for eid in p['evidence']})
        support=[edge_by[eid] for eid in evidence_ids]
        source_ids=sorted({e.source_id for e in support})
        temporal=0
        for p in paths:
            left=[e for e in support if e.id in p['evidence'] and a in (e.source,e.target) and len(e.occurred_at)>10]
            right=[e for e in support if e.id in p['evidence'] and b in (e.source,e.target) and len(e.occurred_at)>10]
            if any(abs((datetime.fromisoformat(x.occurred_at)-datetime.fromisoformat(y.occurred_at)).total_seconds())<=86400 for x in left for y in right):temporal+=1
            p['typed_path']=[by_id[a].kind,by_id[p['via']].kind,by_id[b].kind]
            p['directions']=[{'id':i,'source':edge_by[i].source,'target':edge_by[i].target,'relation':edge_by[i].relation} for i in p['evidence']]
        context=sum(by_id[m].kind in ('Organization','Vehicle','Location') for m in shared)
        contradictions=sum((e.source,e.target,e.relation,e.occurred_at) in denied for e in support)
        signals={'adamic_adar':round(.55*aa,4),'jaccard':round(.45*jaccard,4),'typed_context':round(.12*min(context,3),4),'temporal_proximity':round(.10*min(temporal,3),4),'source_diversity':round(.08*min(max(0,len(source_ids)-1),4),4),'contradiction_penalty':round(-.30*contradictions,4)}
        score=round(min(90,100*(1-exp(-max(0,sum(signals.values()))))))
        output.append({'source':a,'target':b,'source_label':by_id[a].label,'target_label':by_id[b].label,
                       'score':score,'score_label':'Lead score / 100 — uncalibrated', 'signals':signals, 'evidence_ids':evidence_ids, 'source_ids':source_ids,
                       'common_neighbors':len(shared),'adamic_adar':round(aa,4),'jaccard':round(jaccard,4),
                       'paths':paths,'status':'hypothesis',
                       'explanation':f'{len(shared)} shared intermediary node(s). Hubs contribute less. No direct record in selected window.',
                       'caveat':'Not a probability, proven connection or guilt score. Shared services and incomplete records can create false positives.'})
    output.sort(key=lambda p:(-p['score'],p['source'],p['target']))
    return {'items':output[:limit],'candidate_count':len(output),'truncated':truncated,
            'method':'same-type 2-hop candidates; mentioned_in excluded; accepted asserted edges only',
            'formula':'min(90, round(100*(1-exp(-max(0,sum(signal contributions))))))',
            'empty_reason':'No unobserved two-hop Person/Phone pairs. Confirm pending data, widen dates, or add connected records.' if not output else None}
