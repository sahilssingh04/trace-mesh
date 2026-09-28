"""Bounded, explainable identity resolution. No automatic merging."""
import hashlib,json,re,unicodedata
from difflib import SequenceMatcher
from collections import defaultdict
from itertools import combinations
from types import SimpleNamespace
from sqlalchemy import select
from ..models import Entity,Edge,IdentityState
from ..dependencies import serial
VERSION='resolution-3.0'

def normalize(value,kind='name'):
    s=unicodedata.normalize('NFKC',str(value)).casefold().strip()
    if kind=='phone':
        s=re.sub(r'[^0-9+]','',s)
        return '+'+s[2:] if s.startswith('00') else s
    if kind=='email':return s
    return ' '.join(re.findall(r'\w+',s,flags=re.UNICODE))

def attributes(n):
    a=dict(n.attrs)
    try:a={**json.loads(a.get('original','{}')),**a}
    except (ValueError,TypeError):pass
    return a

def features(a,b,neighbors=None):
    aa,bb=attributes(a),attributes(b);na,nb=normalize(a.label),normalize(b.label)
    name=SequenceMatcher(None,na,nb).ratio()
    if a.kind==b.kind=='Phone':name=float(normalize(a.label,'phone')==normalize(b.label,'phone'))
    if a.kind==b.kind=='Vehicle':name=SequenceMatcher(None,na.replace(' ',''),nb.replace(' ','')).ratio()
    aliases=lambda n,attrs:{normalize(n.label)}|{normalize(v) for v in re.split(r'[;,|]',str(attrs.get('aliases','')))}-{''}
    alias=bool(aliases(a,aa)&aliases(b,bb))
    if alias:name=max(name,.95)
    exact=[];conflicts=[]
    for k in ['phone','email','record_ref','registration']:
        av,bv=aa.get(k),bb.get(k)
        if a.kind==b.kind=='Phone' and k=='phone':av,bv=a.label,b.label
        if a.kind==b.kind=='Vehicle' and k=='registration':av,bv=a.label,b.label
        if av and bv:
            norm=lambda x: normalize(x,k).replace(' ','') if k=='registration' else normalize(x,k)
            (exact if norm(av)==norm(bv) else conflicts).append(k)
    context=[]
    for k in ['organization','location']:
        if aa.get(k) and bb.get(k) and normalize(aa[k])==normalize(bb[k]):context.append(k)
    neighbors=neighbors or {};an,bn=neighbors.get(a.id,set()),neighbors.get(b.id,set())
    overlap=len(an&bn)/max(1,len(an|bn))
    score=max(0,min(100,round(48*name+12*alias+35*bool(exact)+5*len(context)+10*overlap-45*len(conflicts))))
    # Name-only homonyms can never become a likely match.
    category='likely_match' if score>=78 and exact and not conflicts else 'review' if score>=45 else 'likely_distinct'
    return {'name_similarity':round(name,3),'alias_overlap':alias,'exact_identifiers':exact,'conflicting_identifiers':conflicts,'context_matches':context,'neighbor_jaccard':round(overlap,3),'score':score,'category':category}

def fingerprint(db,case):
    nodes=list(db.scalars(select(Entity).where(Entity.case_id==case).order_by(Entity.id).limit(20001)))
    edges=list(db.scalars(select(Edge).where(Edge.case_id==case).order_by(Edge.id).limit(20001)))
    if len(nodes)>20000 or len(edges)>20000:raise ValueError('Identity review supports 20,000 entities and 20,000 records per case. Split the case before resolving identities.')
    state=db.get(IdentityState,case)
    body={'nodes':[serial(n) for n in nodes],'edges':[serial(e) for e in edges],'mapping':state.mapping if state else {}}
    return hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest(),nodes,edges

def candidates(nodes,edges,mapping=None):
    mapping=mapping or {};blocks=defaultdict(set);by={n.id:n for n in nodes};neighbors=defaultdict(set)
    for e in edges:
        if e.status=='accepted' and e.polarity=='asserted':neighbors[e.source].add(e.target);neighbors[e.target].add(e.source)
    for n in nodes:
        a=attributes(n);name=normalize(n.label)
        keys={'name:'+name,'prefix:'+name[:4]}
        keys|={'token:'+t for t in name.split() if len(t)>=3}
        for k in ['phone','email','record_ref','registration']:
            if a.get(k):keys.add(k+':'+normalize(a[k],k).replace(' ',''))
        if n.kind in ('Phone','Vehicle'):keys.add('identifier:'+normalize(n.label,'phone' if n.kind=='Phone' else 'registration').replace(' ',''))
        for alias in re.split(r'[;,|]',str(a.get('aliases',''))):
            if alias.strip():keys.add('name:'+normalize(alias))
        for k in keys:blocks[(n.kind,k)].add(n.id)
    pairs=set();truncated=False
    for key in sorted(blocks):
        ids=sorted(blocks[key]);
        if len(ids)>200:ids=ids[:200];truncated=True
        for a,b in combinations(ids,2):
            if mapping.get(a,a)==mapping.get(b,b):continue
            pairs.add((a,b))
            if len(pairs)>=50000:truncated=True;break
        if len(pairs)>=50000:break
    items=[]
    for a,b in sorted(pairs):
        f=features(by[a],by[b],neighbors)
        items.append({'source':a,'target':b,'source_label':by[a].label,'target_label':by[b].label,**f})
    items.sort(key=lambda x:(-x['score'],x['source'],x['target']))
    return {'items':items[:200],'compared_pairs':len(pairs),'candidate_count':len(items),'truncated':truncated or len(items)>200,'algorithm':VERSION,'note':'Scores rank review priority; not identity probabilities. No country code is guessed for phone numbers.'}

def canonicalize(db,case,nodes,edges):
    state=db.get(IdentityState,case);mapping=state.mapping if state else {}
    ids={mapping.get(n.id,n.id) for n in nodes};by={n.id:n for n in nodes}
    missing=ids-set(by)
    if missing:
        for i in range(0,len(missing),400):
            for n in db.scalars(select(Entity).where(Entity.case_id==case,Entity.id.in_(list(missing)[i:i+400]))):by[n.id]=n
    groups=defaultdict(list)
    for member,root in mapping.items():groups[root].append(member)
    outnodes=[SimpleNamespace(**serial(by[i]),members=sorted(set(groups[i]+[i]))) for i in sorted(ids) if i in by]
    outedges=[]
    for e in edges:
        obj=serial(e);obj.update(source=mapping.get(e.source,e.source),target=mapping.get(e.target,e.target),original_source=getattr(e,"original_source",e.source),original_target=getattr(e,"original_target",e.target))
        outedges.append(SimpleNamespace(**obj))
    return outnodes,outedges
