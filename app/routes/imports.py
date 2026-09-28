import hashlib
import json
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from ..dependencies import session, access, serial
from ..models import Job
from ..schemas import Bundle, ConvertIn, TextIn
from ..ingest import audit
from ..services.conversion import convert
from ..extraction import extract
router=APIRouter(prefix='/api/cases/{case_id}')


@router.post('/convert')
def preview(case_id:str,item:ConvertIn,user=Depends(access),db=Depends(session)):
    try: result=convert(item)
    except ValidationError as exc:
        raise HTTPException(422,{'message':'Data format needs correction','errors':[{'field':'.'.join(map(str,e['loc'])),'message':e['msg']} for e in exc.errors()[:20]]})
    except (ValueError,KeyError,TypeError) as exc: raise HTTPException(422,str(exc))
    audit(db,case_id,user['name'],'conversion_preview',{'format':result['format'],'counts':result['counts']});db.commit()
    return result


@router.post('/imports',status_code=202)
def submit(case_id:str,bundle:Bundle,user=Depends(access),db=Depends(session)):
    raw=bundle.model_dump(mode='json');digest=hashlib.sha256(json.dumps(raw,sort_keys=True).encode()).hexdigest()
    old=db.scalar(select(Job).where(Job.case_id==case_id,Job.digest==digest))
    if old: return {'id':old.id,'status':old.status,'replayed':True,'error':old.error}
    job=Job(id=uuid.uuid4().hex,case_id=case_id,actor=user['name'],digest=digest,payload=raw)
    db.add(job);audit(db,case_id,user['name'],'submit_import',{'job':job.id})
    try: db.commit()
    except IntegrityError:
        db.rollback();old=db.scalar(select(Job).where(Job.case_id==case_id,Job.digest==digest))
        if not old: raise
        return {'id':old.id,'status':old.status,'replayed':True}
    return {'id':job.id,'status':job.status,'replayed':False}


@router.get('/jobs')
def jobs(case_id:str,user=Depends(access),db=Depends(session)):
    return [{k:v for k,v in serial(j).items() if k!='payload'} for j in db.scalars(select(Job).where(Job.case_id==case_id).order_by(Job.created_at.desc()).limit(50))]


@router.post('/jobs/{job_id}/retry')
def retry(case_id:str,job_id:str,user=Depends(access),db=Depends(session)):
    j=db.scalar(select(Job).where(Job.case_id==case_id,Job.id==job_id).with_for_update())
    if not j or j.status!='failed': raise HTTPException(409,'Only failed jobs can be retried')
    j.status='queued';j.error=None;audit(db,case_id,user['name'],'retry_import',{'job':job_id});db.commit()
    return {'status':'queued'}


@router.post('/extract')
def extraction(case_id:str,item:TextIn,user=Depends(access)):
    try:return extract(item.text,item.mode)
    except (ImportError,ValueError,OSError):raise HTTPException(503,'Optional local model unavailable. Use natural-language draft entry instead.')
