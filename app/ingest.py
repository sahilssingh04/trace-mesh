"""Batch prefetch avoids one SELECT per entity/edge. Each job commits atomically."""
import hashlib
from sqlalchemy import select
from .models import Entity, Source, Edge, Audit, Job
from .schemas import Bundle


def audit(db, case, actor, action, detail):
    db.add(Audit(case_id=case, actor=actor, action=action, detail=detail))


def fetch(db, model, case, ids):
    found={}
    ids=list(ids)
    for start in range(0,len(ids),400):
        found.update({n.id:n for n in db.scalars(select(model).where(model.case_id==case,model.id.in_(ids[start:start+400])))})
    return found


def ingest(db, case, actor, raw):
    bundle=Bundle.model_validate(raw)
    for collection in (bundle.entities,bundle.sources,bundle.edges):
        ids=[x.id for x in collection]
        if len(ids)!=len(set(ids)): raise ValueError('Duplicate IDs within one collection')
    existing=fetch(db,Entity,case,{n.id for n in bundle.entities}|{x for e in bundle.edges for x in (e.source,e.target)})
    for n in bundle.entities:
        values=n.model_dump();old=existing.get(n.id)
        if old and any(getattr(old,k)!=v for k,v in values.items()): raise ValueError(f'Entity ID conflict: {n.id}. Use the entity editor or a new case.')
        if not old:
            old=Entity(case_id=case,**values);db.add(old);existing[n.id]=old
    sources=fetch(db,Source,case,{s.id for s in bundle.sources}|{e.source_id for e in bundle.edges})
    for s in bundle.sources:
        values=s.model_dump();old=sources.get(s.id)
        if old and any(getattr(old,k)!=v for k,v in values.items()): raise ValueError(f'Source ID conflict: {s.id}')
        if not old:
            old=Source(case_id=case,**values,sha256=hashlib.sha256(s.text.encode()).hexdigest());db.add(old);sources[s.id]=old
    old_edges=fetch(db,Edge,case,{e.id for e in bundle.edges})
    for e in bundle.edges:
        if e.source not in existing or e.target not in existing: raise ValueError(f'Unknown endpoint on {e.id}: {e.source} → {e.target}')
        source=sources.get(e.source_id)
        if not source or e.excerpt not in source.text: raise ValueError(f'Excerpt for {e.id} must match text in source {e.source_id}')
        values=e.model_dump(mode='json');values['occurred_at']=e.occurred_at or ''
        old=old_edges.get(e.id)
        if old and any(getattr(old,k)!=v for k,v in values.items()): raise ValueError(f'Edge ID conflict: {e.id}')
        if not old: db.add(Edge(case_id=case,**values))
    audit(db,case,actor,'import',{'entities':len(bundle.entities),'edges':len(bundle.edges)})


def process_one(factory):
    with factory.begin() as db:
        job=db.scalar(select(Job).where(Job.status=='queued').order_by(Job.created_at).with_for_update(skip_locked=True).limit(1))
        if not job: return False
        try:
            with db.begin_nested():
                ingest(db,job.case_id,job.actor,job.payload);db.flush()
            job.status='completed'
            # Successful data is now stored canonically; don't retain a second large JSON copy.
            job.payload={}
        except ValueError as exc:
            job.status='failed';job.error=str(exc)[:2000]
        return True
