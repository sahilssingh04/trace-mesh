from datetime import datetime, timezone
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy import select,or_,func
import networkx as nx
from ..dependencies import session,access,serial
from ..models import Entity,Edge,Source
from ..analytics import snapshot,projection,analyze,resolution_candidates,colocations,sensitivity
from ..services.links import hidden_links
from ..services.resolution import canonicalize
from ..models import IdentityState
from ..ingest import audit,fetch
router=APIRouter(prefix='/api/cases/{case_id}')


def window(value):
    if not value:return None
    try:
        if len(value)==10:return datetime.fromisoformat(value).date().isoformat()
        t=datetime.fromisoformat(value.replace('Z','+00:00'))
        if t.tzinfo is None:raise ValueError()
        return t.astimezone(timezone.utc).isoformat()
    except ValueError:raise HTTPException(422,'Use YYYY-MM-DD or an ISO timestamp with timezone')


def view(db,case,start,end,pending=False,focus=None):
    start,end=window(start),window(end)
    if start and end and start>end:raise HTTPException(422,'Start must be before end')
    # Date-only upper bound includes the whole day, and date-only lower includes day-precision records.
    if end and len(end)==10:end+='T23:59:59.999999+00:00'
    if focus:
        state=db.get(IdentityState,case);mapping=state.mapping if state else {}
        root=mapping.get(focus,focus);members={root}|{k for k,v in mapping.items() if v==root}
        q=select(Edge).where(Edge.case_id==case,Edge.status.in_(['accepted','pending'] if pending else ['accepted']))
        if start or end:q=q.where(Edge.occurred_at!='')
        if start:q=q.where(Edge.occurred_at>=start)
        if end:q=q.where(Edge.occurred_at<=end)
        first=list(db.scalars(q.where(or_(Edge.source.in_(members),Edge.target.in_(members))).limit(1001)))
        if len(first)>1000:raise HTTPException(422,'Neighborhood too large. Narrow dates.')
        ids=members|{x for e in first for x in (e.source,e.target)}
        roots={mapping.get(i,i) for i in ids};ids|=roots|{k for k,v in mapping.items() if v in roots}
        edges=list(db.scalars(q.where(or_(Edge.source.in_(ids),Edge.target.in_(ids))).order_by(Edge.id).limit(2001)))
        if len(edges)>2000:raise HTTPException(422,'Two-hop neighborhood exceeds 2,000 records. Narrow dates.')
        nodes=list(fetch(db,Entity,case,{x for e in edges for x in (e.source,e.target)}).values())
        if not nodes:
            node=db.get(Entity,(case,focus));nodes=[node] if node else []
        return canonicalize(db,case,nodes,edges)
    try:return canonicalize(db,case,*snapshot(db,case,start,end,pending))
    except ValueError as exc:raise HTTPException(422,str(exc))


@router.get('/graph')
def graph(case_id:str,start:str|None=None,end:str|None=None,pending:bool=True,focus:str|None=None,user=Depends(access),db=Depends(session)):
    nodes,edges=view(db,case_id,start,end,pending,focus)
    # Include standalone entities only when no date/neighborhood filter is active.
    if not start and not end and not focus:
        nodes=list(db.scalars(select(Entity).where(Entity.case_id==case_id).order_by(Entity.id).limit(20001)))
        if len(nodes)>20000:raise HTTPException(422,'Over 20,000 entities. Select a focused neighborhood.')
    nodes,edges=canonicalize(db,case_id,nodes,edges) if not start and not end and not focus else (nodes,edges)
    return {'nodes':[serial(n) for n in nodes],'edges':[serial(e) for e in edges], 'scope':'Selected case, date range and optional two-hop focus'}


@router.get('/analytics')
def analytics(case_id:str,start:str|None=None,end:str|None=None,focus:str|None=None,user=Depends(access),db=Depends(session)):
    nodes,edges=view(db,case_id,start,end,False,focus);r=analyze(nodes,edges)
    r.update(colocations=colocations(nodes,edges),sensitivity=sensitivity(nodes,edges));return r


@router.get('/links')
def links(case_id:str,start:str|None=None,end:str|None=None,focus:str|None=None,user=Depends(access),db=Depends(session)):
    # Pending relationships excluded from topology but suppress duplicate hypotheses.
    nodes,edges=view(db,case_id,start,end,True,focus);return hidden_links(nodes,edges)


@router.get('/path')
def path(case_id:str,source:str,target:str,start:str|None=None,end:str|None=None,focus:str|None=None,user=Depends(access),db=Depends(session)):
    nodes,edges=view(db,case_id,start,end,False,focus);g=projection(nodes,edges)
    try:p=nx.shortest_path(g,source,target)
    except (nx.NetworkXNoPath,nx.NodeNotFound):return {'path':[],'evidence':[]}
    return {'path':p,'evidence':[g[a][b]['evidence'] for a,b in zip(p,p[1:])],'note':'Undirected structural path; not a chronological or causal chain.'}


@router.get('/resolution')
def resolution(case_id:str,user=Depends(access),db=Depends(session)):
    nodes=list(db.scalars(select(Entity).where(Entity.case_id==case_id).order_by(Entity.id).limit(2001)))
    if len(nodes)>2000:raise HTTPException(422,'Identity suggestions support up to 2,000 case entities in this release')
    return resolution_candidates(nodes)


@router.get('/records')
def records(case_id:str,status:str='all',offset:int=Query(0,ge=0),limit:int=Query(100,ge=1,le=500),user=Depends(access),db=Depends(session)):
    q=select(Edge).where(Edge.case_id==case_id)
    if status!='all':q=q.where(Edge.status==status)
    total=db.scalar(select(func.count()).select_from(q.subquery()))
    return {'items':[serial(e) for e in db.scalars(q.order_by(Edge.id).offset(offset).limit(limit))],'total':total}


@router.get('/sources')
def sources(case_id:str,offset:int=Query(0,ge=0),limit:int=Query(100,ge=1,le=500),user=Depends(access),db=Depends(session)):
    return {'items':[{'id':s.id,'title':s.title,'sha256':s.sha256} for s in db.scalars(select(Source).where(Source.case_id==case_id).order_by(Source.id).offset(offset).limit(limit))]}


@router.get('/report')
def report(case_id:str,start:str|None=None,end:str|None=None,focus:str|None=None,user=Depends(access),db=Depends(session)):
    nodes,edges=view(db,case_id,start,end,True,focus);sources=fetch(db,Source,case_id,{e.source_id for e in edges})
    audit(db,case_id,user['name'],'export',{'start':start,'end':end,'focus':focus});db.commit()
    return {'case':case_id,'scope':{'start':start,'end':end,'focus':focus},'entities':[serial(n) for n in nodes],
            'relationships':[serial(e) for e in edges],'sources':[serial(s) for s in sources.values()],
            'hidden_link_hypotheses':hidden_links(nodes,edges),'disclaimer':'Claims and uncalibrated hypotheses, not conclusions of guilt.'}


@router.get('/projection')
def typed_projection(case_id:str,mode:str='directed',start:str|None=None,end:str|None=None,focus:str|None=None,user=Depends(access),db=Depends(session)):
    modes={'directed':None,'communication':{'called'},'ownership':{'owns','uses','member_of'},'location':{'visited'},'transactions':{'transferred'}}
    if mode not in modes:raise HTTPException(422,'Choose directed, communication, ownership, location or transactions')
    nodes,edges=view(db,case_id,start,end,False,focus)
    edges=[e for e in edges if e.polarity=='asserted' and (modes[mode] is None or e.relation in modes[mode])]
    ids={x for e in edges for x in (e.source,e.target)}
    return {'mode':mode,'directed':True,'nodes':[serial(n) for n in nodes if n.id in ids],'edges':[serial(e) for e in edges],'note':'Typed directed records. Parallel evidence edges remain separate.'}
