"""Human-reviewed intelligence, separate from source-backed claims."""
import hashlib,json,uuid
from html import escape
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Query
from fastapi.responses import HTMLResponse
from pydantic import Field
from sqlalchemy import select,update,func
from sqlalchemy.exc import IntegrityError
from ..models import IdentityState,IdentityDecision,Hypothesis,AnalysisJob,Entity,Edge,Audit,Source,Case,Review,now
from ..dependencies import access,session,serial
from ..schemas import Strict
from ..ingest import audit,fetch
from ..services.resolution import fingerprint,candidates,features,canonicalize,attributes
from ..services.links import hidden_links
router=APIRouter(prefix='/api/cases/{case_id}')

def identity_snapshot(db,case):
    try:return fingerprint(db,case)
    except ValueError as e:raise HTTPException(422,str(e))

@router.get('/identities')
def identities(case_id:str,user=Depends(access),db=Depends(session)):
    fp,nodes,edges=identity_snapshot(db,case_id);state=db.get(IdentityState,case_id)
    result=candidates(nodes,edges,state.mapping if state else {})
    result.update(fingerprint=fp,revision=state.revision if state else 0,mapping=state.mapping if state else {},history=[serial(d) for d in db.scalars(select(IdentityDecision).where(IdentityDecision.case_id==case_id).order_by(IdentityDecision.id.desc()).limit(100))])
    previous={}
    for d in result['history']:
        pair=tuple(sorted((d['source'],d['target'])))
        previous.setdefault(pair,d)
    for item in result['items']:
        prior=previous.get(tuple(sorted((item['source'],item['target']))))
        item['previous_decision']=prior['decision'] if prior else None
    return result

class IdentityAction(Strict):
    source:str=Field(min_length=1,max_length=80)
    target:str=Field(min_length=1,max_length=80)
    decision:Literal['merge','distinct']
    reason:str=Field(min_length=5,max_length=2000)
    fingerprint:str=Field(min_length=64,max_length=64)
    expected_revision:int=Field(ge=0)

class Undo(Strict):
    expected_revision:int=Field(ge=0)
    reason:str=Field(min_length=5,max_length=2000)


def lock_identity(db,case,revision):
    state=db.get(IdentityState,case)
    if state is None:
        try:
            with db.begin_nested():db.add(IdentityState(case_id=case,revision=0,mapping={}));db.flush()
        except IntegrityError:pass
    changed=db.execute(update(IdentityState).where(IdentityState.case_id==case,IdentityState.revision==revision).values(revision=revision+1))
    if changed.rowcount!=1:raise HTTPException(409,'Identity state changed. Reload and review again.')
    return db.get(IdentityState,case,populate_existing=True)

@router.post('/identities/review')
def identity_review(case_id:str,body:IdentityAction,user=Depends(access),db=Depends(session)):
    state=lock_identity(db,case_id,body.expected_revision)
    fp,nodes,edges=identity_snapshot(db,case_id)
    if fp!=body.fingerprint:raise HTTPException(409,'Case evidence changed. Reload identity candidates.')
    by={n.id:n for n in nodes};a,b=by.get(body.source),by.get(body.target)
    if not a or not b:raise HTTPException(404,'Entity not found in this case')
    mapping=dict(state.mapping)
    if a.kind!=b.kind or a.id==b.id:raise HTTPException(422,'Choose two different entities of the same type')
    left,right=mapping.get(a.id,a.id),mapping.get(b.id,b.id)
    if left==right:raise HTTPException(409,'Already in the same canonical group')
    f=features(a,b)
    decision=IdentityDecision(case_id=case_id,source=a.id,target=b.id,decision=body.decision,reason=body.reason,actor=user['name'],before=mapping,features=f)
    db.add(decision)
    if body.decision=='merge':
        # Target is canonical. Rewrite only the derived identity map, never source edges.
        updated={k:(right if v==left else v) for k,v in mapping.items()}
        updated[left]=right;state.mapping=updated
    audit(db,case_id,user['name'],'identity_'+body.decision,{'source':a.id,'target':b.id,'reason':body.reason,'features':f,'revision':state.revision})
    db.commit();return {'id':decision.id,'revision':state.revision,'mapping':state.mapping}

@router.post('/identities/{decision_id}/undo')
def undo(case_id:str,decision_id:int,body:Undo,user=Depends(access),db=Depends(session)):
    state=lock_identity(db,case_id,body.expected_revision)
    last=db.scalar(select(IdentityDecision).where(IdentityDecision.case_id==case_id,IdentityDecision.decision=='merge',IdentityDecision.active==1).order_by(IdentityDecision.id.desc()).limit(1))
    if not last or last.id!=decision_id:raise HTTPException(409,'Undo the latest active merge first; dependent merges must be reversed in order.')
    state.mapping=dict(last.before);last.active=0
    audit(db,case_id,user['name'],'identity_unmerge',{'decision_id':last.id,'reason':body.reason,'revision':state.revision});db.commit()
    return {'revision':state.revision,'mapping':state.mapping}


def scoped(db,case,start,end,focus):
    from .graph import view
    return view(db,case,start,end,True,focus)

def compute_saved(db,case_id,start,end,focus,user):
    nodes,edges=scoped(db,case_id,start,end,focus);result=hidden_links(nodes,edges)
    graph_hash=hashlib.sha256(json.dumps({'nodes':[serial(n) for n in nodes],'edges':[serial(e) for e in edges]},sort_keys=True).encode()).hexdigest()
    for h in result['items']:
        h.update(algorithm='links-3.0',graph_fingerprint=graph_hash,scope={'start':start,'end':end,'focus':focus})
        hid=hashlib.sha256(json.dumps(h,sort_keys=True).encode()).hexdigest()
        old=db.get(Hypothesis,hid)
        if not old:
            try:
                with db.begin_nested():db.add(Hypothesis(id=hid,case_id=case_id,snapshot=h));db.flush()
            except IntegrityError:pass
            old=db.get(Hypothesis,hid)
        h.update(id=hid,status=old.status,revision=old.revision,created_at=old.created_at)
    audit(db,case_id,user['name'],'compute_hypotheses',{'graph_fingerprint':graph_hash,'count':len(result['items']),'scope':{'start':start,'end':end,'focus':focus}})
    return result

@router.post('/hypotheses/compute')
def compute(case_id:str,start:str|None=None,end:str|None=None,focus:str|None=None,user=Depends(access),db=Depends(session)):
    result=compute_saved(db,case_id,start,end,focus,user)
    db.commit();return result

class LeadReview(Undo):
    decision:Literal['unreviewed','worth_following','dismissed','needs_evidence']

@router.post('/hypotheses/{hypothesis_id}/review')
def review_lead(case_id:str,hypothesis_id:str,body:LeadReview,user=Depends(access),db=Depends(session)):
    changed=db.execute(update(Hypothesis).where(Hypothesis.id==hypothesis_id,Hypothesis.case_id==case_id,Hypothesis.revision==body.expected_revision).values(status=body.decision,revision=body.expected_revision+1))
    if changed.rowcount!=1:raise HTTPException(409,'Lead changed or no longer exists. Reload it.')
    audit(db,case_id,user['name'],'review_hypothesis',{'id':hypothesis_id,'decision':body.decision,'reason':body.reason,'revision':body.expected_revision+1});db.commit()
    return {'status':body.decision,'revision':body.expected_revision+1}

@router.get('/hypotheses')
def history(case_id:str,offset:int=Query(0,ge=0),user=Depends(access),db=Depends(session)):
    return {'items':[serial(h) for h in db.scalars(select(Hypothesis).where(Hypothesis.case_id==case_id).order_by(Hypothesis.created_at.desc()).offset(offset).limit(100))]}

@router.get('/timeline')
def timeline(case_id:str,start:str|None=None,end:str|None=None,focus:str|None=None,user=Depends(access),db=Depends(session)):
    nodes,edges=scoped(db,case_id,start,end,focus)
    events=[{**serial(e),'precision':'unknown' if not e.occurred_at else 'day' if len(e.occurred_at)==10 else 'timestamp'} for e in edges]
    return {'events':sorted(events,key=lambda e:(not bool(e['occurred_at']),e['occurred_at'],e['id'])),'unknown_count':sum(not e.occurred_at for e in edges),'note':'Unknown times stay separate; day-only records do not establish precise co-location.'}

@router.get('/geo')
def geo(case_id:str,start:str|None=None,end:str|None=None,focus:str|None=None,user=Depends(access),db=Depends(session)):
    nodes,edges=scoped(db,case_id,start,end,focus);points=[]
    for n in nodes:
        if n.kind!='Location':continue
        a=attributes(n)
        try:lat=float(a.get('latitude',a.get('lat')));lon=float(a.get('longitude',a.get('lon',a.get('lng'))))
        except (ValueError,TypeError):continue
        if not (-90<=lat<=90 and -180<=lon<=180):continue
        visits=[serial(e) for e in edges if e.target==n.id and e.relation=='visited']
        points.append({'id':n.id,'label':n.label,'latitude':lat,'longitude':lon,'records':visits})
    return {'points':points,'note':'Coordinates identify recorded locations, not live tracking. Close timestamps do not establish a meeting.'}

@router.get('/brief')
def brief(case_id:str,user=Depends(access),db=Depends(session)):
    counts={name:db.scalar(select(func.count()).select_from(model).where(model.case_id==case_id)) for name,model in [('entities',Entity),('records',Edge),('sources',Source),('saved_leads',Hypothesis)]}
    counts['pending']=db.scalar(select(func.count()).select_from(Edge).where(Edge.case_id==case_id,Edge.status=='pending'))
    return {'case':serial(db.get(Case,case_id)),'counts':counts,'leads':[serial(h) for h in db.scalars(select(Hypothesis).where(Hypothesis.case_id==case_id,Hypothesis.status!='dismissed').order_by(Hypothesis.created_at.desc()).limit(5))],'identity_merges':db.scalar(select(func.count()).select_from(IdentityDecision).where(IdentityDecision.case_id==case_id,IdentityDecision.decision=='merge',IdentityDecision.active==1))}

@router.get('/report.html',response_class=HTMLResponse)
def report_html(case_id:str,start:str|None=None,end:str|None=None,focus:str|None=None,user=Depends(access),db=Depends(session)):
    nodes,edges=scoped(db,case_id,start,end,focus);sources=fetch(db,Source,case_id,{e.source_id for e in edges});title=db.get(Case,case_id).title
    esc=lambda x:escape(str(x),quote=True)
    def table(head,rows):
        return '<table><thead><tr>'+''.join('<th>'+esc(x)+'</th>' for x in head)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table>'
    html='<!doctype html><html lang="en"><meta charset="utf-8"><title>'+esc(title)+' — Evidence Weave</title><style>body{font:14px system-ui;margin:40px;color:#162438}h1{font-size:32px}h2{margin-top:36px}table{border-collapse:collapse;width:100%;font-size:12px}td,th{border:1px solid #ccd4df;padding:8px;text-align:left;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere}.notice{padding:16px;background:#edf3f6}@media print{thead{display:table-header-group}tr{break-inside:avoid}}</style><h1>'+esc(title)+'</h1><p>Evidence Weave 3.0 · '+esc(now())+'</p><p>Scope: '+esc({'start':start,'end':end,'focus':focus})+'</p><p class="notice">Investigator decision support. Source-backed claims and algorithmic hypotheses are distinct. Scores are uncalibrated priorities, never probabilities or conclusions of guilt.</p>'
    html+='<h2>Case view</h2><p>'+str(len(nodes))+' canonical entities · '+str(len(edges))+' selected claims</p>'
    html+=table(['Entity','Type','Original members'],[(n.label,n.kind,', '.join(n.members)) for n in nodes])
    html+='<h2>Claims and provenance</h2>'+table(['ID','Direction / relation','Status / polarity','Event time','Original endpoints','Source / excerpt'],[(e.id,e.source+' → '+e.target+' / '+e.relation,e.status+' / '+e.polarity,e.occurred_at or 'Unknown',e.original_source+' → '+e.original_target,e.source_id+' / '+e.excerpt) for e in edges])
    html+='<h2>Computed leads in this view</h2>'+table(['Pair','Lead score','Signals','Evidence IDs'],[(h['source_label']+' ↔ '+h['target_label'],h['score'],json.dumps(h['signals']),', '.join(h['evidence_ids'])) for h in hidden_links(nodes,edges)['items']])
    saved=list(db.scalars(select(Hypothesis).where(Hypothesis.case_id==case_id).order_by(Hypothesis.created_at.desc()).limit(501)))
    html+='<h2>Saved lead reviews (case history, latest 500)</h2>'+table(['Pair','Status','Snapshot time','Algorithm'],[(h.snapshot['source_label']+' ↔ '+h.snapshot['target_label'],h.status,h.created_at,h.snapshot['algorithm']) for h in saved[:500]])
    if len(saved)>500:html+='<p>History truncated to latest 500 snapshots.</p>'
    for name,model in [('Identity decisions',IdentityDecision),('Evidence reviews',Review),('Audit trail',Audit)]:
        rows=list(db.scalars(select(model).where(model.case_id==case_id).order_by(model.id.desc()).limit(1001)))
        html+='<h2>'+name+' (case history, latest 1,000)</h2>'+table(['History'],[(json.dumps(serial(x),ensure_ascii=False),) for x in rows[:1000]])
        if len(rows)>1000:html+='<p>History truncated to latest 1,000 entries.</p>'
    html+='<h2>Original sources</h2>'
    for s in sources.values():html+='<h3>'+esc(s.title)+'</h3><p>'+esc(s.id)+' · SHA-256 '+esc(s.sha256)+'</p><pre>'+esc(s.text)+'</pre>'
    html+='<h2>Method and limitations</h2><p>links-3.0 uses accepted asserted two-hop paths, degree-discounted shared neighbors, typed intermediaries, source diversity and time proximity. Shared hubs and incomplete data can mislead. Dates are not inferred. Entity merges are human decisions; original source endpoints remain intact. Selected graph views are bounded; synthetic benchmarks are not field validation. GNN research is isolated from this score.</p></html>'
    audit(db,case_id,user['name'],'export_html',{'start':start,'end':end,'focus':focus});db.commit()
    return HTMLResponse(html,headers={'Content-Disposition':'attachment; filename="evidence-weave-report.html"'})


class AnalysisRequest(Strict):
    operation:Literal['links','identities']
    start:str|None=None
    end:str|None=None
    focus:str|None=Field(default=None,max_length=80)

@router.post('/analysis-jobs',status_code=202)
def enqueue_analysis(case_id:str,body:AnalysisRequest,user=Depends(access),db=Depends(session)):
    from .graph import window
    start,end=window(body.start),window(body.end)
    if start and end and start>end:raise HTTPException(422,'Start must be before end')
    queued=db.scalar(select(func.count()).select_from(AnalysisJob).where(AnalysisJob.case_id==case_id,AnalysisJob.status=='queued'))
    if queued>=5:raise HTTPException(429,'Five analyses already queued. Wait for the worker.')
    job=AnalysisJob(id=str(uuid.uuid4()),case_id=case_id,actor=user['name'],operation=body.operation,scope={'start':start,'end':end,'focus':body.focus})
    db.add(job);audit(db,case_id,user['name'],'queue_analysis',{'id':job.id,'operation':body.operation});db.commit()
    return {'id':job.id,'status':job.status}

@router.get('/analysis-jobs/{job_id}')
def analysis_job(case_id:str,job_id:str,user=Depends(access),db=Depends(session)):
    job=db.get(AnalysisJob,job_id)
    if not job or job.case_id!=case_id:raise HTTPException(404,'Analysis job not found')
    return serial(job)
