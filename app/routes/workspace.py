import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update, func
from ..dependencies import session, owner, access, serial
from ..models import Case, Entity, Edge, Source, Audit, Review
from ..schemas import CaseIn, NodeIn, NodeEdit, EdgeEdit, ReviewIn, BatchReview
from ..ingest import audit
router = APIRouter(prefix='/api')


@router.get('/cases')
def cases(user=Depends(owner), db=Depends(session)):
    return {'user':user['name'], 'cases':[serial(c) for c in db.scalars(select(Case).order_by(Case.id))]}


@router.post('/cases', status_code=201)
def create_case(item:CaseIn, user=Depends(owner), db=Depends(session)):
    c=Case(id='case-'+uuid.uuid4().hex[:12],title=item.title)
    db.add(c); audit(db,c.id,user['name'],'create_case',{'title':c.title});db.commit()
    return serial(c)


@router.get('/cases/{case_id}/entities')
def entities(case_id:str, q:str='', offset:int=Query(0,ge=0), limit:int=Query(100,ge=1,le=500),user=Depends(access),db=Depends(session)):
    query=select(Entity).where(Entity.case_id==case_id)
    if q: query=query.where(Entity.label.ilike('%'+q+'%'))
    total=db.scalar(select(func.count()).select_from(query.subquery()))
    return {'items':[serial(n) for n in db.scalars(query.order_by(Entity.id).offset(offset).limit(limit))], 'total':total}


@router.post('/cases/{case_id}/entities',status_code=201)
def add_entity(case_id:str,item:NodeIn,user=Depends(access),db=Depends(session)):
    if db.get(Entity,(case_id,item.id)): raise HTTPException(409,'ID already exists')
    n=Entity(case_id=case_id,**item.model_dump());db.add(n)
    audit(db,case_id,user['name'],'create_entity',item.model_dump());db.commit();return serial(n)


@router.patch('/cases/{case_id}/entities/{entity_id}')
def edit_entity(case_id:str,entity_id:str,item:NodeEdit,user=Depends(access),db=Depends(session)):
    n=db.scalar(select(Entity).where(Entity.case_id==case_id,Entity.id==entity_id).with_for_update())
    if not n: raise HTTPException(404,'Entity not found')
    if n.label!=item.expected_label or n.attrs!=item.expected_attrs: raise HTTPException(409,'Entity changed. Refresh before saving.')
    before=serial(n);n.label=item.label;n.attrs=item.attrs
    audit(db,case_id,user['name'],'edit_entity',{'before':before,'after':serial(n)});db.commit();return serial(n)


def apply_review(db,case_id,edge_id,decision,revision,reason,user):
    r=db.execute(update(Edge).where(Edge.case_id==case_id,Edge.id==edge_id,Edge.revision==revision)
                 .values(status=decision,revision=Edge.revision+1))
    if r.rowcount!=1: raise HTTPException(409,f'Relationship {edge_id} changed. Refresh and try again.')
    db.add(Review(case_id=case_id,edge_id=edge_id,actor=user['name'],decision=decision,reason=reason))
    audit(db,case_id,user['name'],'review',{'edge':edge_id,'decision':decision,'reason':reason})


@router.post('/cases/{case_id}/edges/{edge_id}/review')
def review(case_id:str,edge_id:str,item:ReviewIn,user=Depends(access),db=Depends(session)):
    apply_review(db,case_id,edge_id,item.decision,item.expected_revision,item.reason,user);db.commit()
    return {'status':item.decision,'revision':item.expected_revision+1}


@router.post('/cases/{case_id}/review-batch')
def batch_review(case_id:str,item:BatchReview,user=Depends(access),db=Depends(session)):
    for edge in item.edges:
        if not isinstance(edge.get('id'),str) or not isinstance(edge.get('revision'),int):
            raise HTTPException(422,'Each edge needs id and integer revision')
        apply_review(db,case_id,edge['id'],item.decision,edge['revision'],item.reason,user)
    db.commit();return {'updated':len(item.edges)}


@router.patch('/cases/{case_id}/edges/{edge_id}')
def edit_edge(case_id:str,edge_id:str,item:EdgeEdit,user=Depends(access),db=Depends(session)):
    e=db.get(Edge,(case_id,edge_id))
    if not e: raise HTTPException(404,'Relationship not found')
    before=serial(e)
    values={'relation':item.relation,'occurred_at':item.occurred_at or '','polarity':item.polarity,'status':'pending'}
    r=db.execute(update(Edge).where(Edge.case_id==case_id,Edge.id==edge_id,Edge.revision==item.expected_revision).values(**values,revision=Edge.revision+1))
    if r.rowcount!=1: raise HTTPException(409,'Relationship changed; refresh first')
    audit(db,case_id,user['name'],'edit_relationship',{'before':before,'changes':values,'reason':item.reason})
    db.commit();return {'revision':item.expected_revision+1, 'status':'pending'}


@router.get('/cases/{case_id}/sources/{source_id}')
def source(case_id:str,source_id:str,user=Depends(access),db=Depends(session)):
    s=db.get(Source,(case_id,source_id))
    if not s: raise HTTPException(404,'Source not found')
    audit(db,case_id,user['name'],'view_source',{'id':source_id});db.commit();return serial(s)


@router.get('/cases/{case_id}/audit')
def logs(case_id:str,after:int=Query(0,ge=0),user=Depends(access),db=Depends(session)):
    return [serial(a) for a in db.scalars(select(Audit).where(Audit.case_id==case_id,Audit.id>after).order_by(Audit.id).limit(200))]
