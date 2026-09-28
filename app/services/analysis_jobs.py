"""Durable bounded analytics, claimed transactionally by the existing worker."""
from sqlalchemy import select
from fastapi import HTTPException
from ..models import AnalysisJob
from ..ingest import audit

def process_analysis(factory):
    from ..routes.intelligence import compute_saved,identities
    with factory.begin() as db:
        job=db.scalar(select(AnalysisJob).where(AnalysisJob.status=='queued').order_by(AnalysisJob.created_at).limit(1).with_for_update(skip_locked=True))
        if job is None:return False
        try:
            with db.begin_nested():
                user={'name':job.actor}
                result=compute_saved(db,job.case_id,**job.scope,user=user) if job.operation=='links' else identities(job.case_id,user=user,db=db)
                job.result=result;job.status='completed';db.flush()
        except (ValueError,HTTPException) as exc:
            job.status='failed';job.error=str(getattr(exc,'detail',exc))
        audit(db,job.case_id,job.actor,'analysis_job_'+job.status,{'id':job.id,'operation':job.operation})
    return True
