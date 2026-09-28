import json
from pathlib import Path
from sqlalchemy import select
from app.models import Edge,Entity,Hypothesis,IdentityState
from app.services.resolution import normalize,features,candidates
from types import SimpleNamespace
from test_workbench import system,h,load,accept,demo

def duplicate(c):
    r=c.post('/api/cases/A/entities',headers=h(),json={'id':'alias','label':'ASHA (demo)','kind':'Person','attrs':{'phone':'+91 9000000001'}})
    assert r.status_code==201

def action(c,source='alias',target='guide-asha'):
    d=c.get('/api/cases/A/identities',headers=h()).json()
    return {'source':source,'target':target,'decision':'merge','reason':'Confirmed original identifiers','fingerprint':d['fingerprint'],'expected_revision':d['revision']}

def test_resolution_merge_undo_preserves_source(system):
    c,f=system;load(c,f);accept(c);duplicate(c)
    body=action(c);r=c.post('/api/cases/A/identities/review',headers=h(),json=body);assert r.status_code==200,r.text
    assert c.post('/api/cases/A/identities/review',headers=h(),json=body).status_code==409
    g=c.get('/api/cases/A/graph',headers=h()).json();n=next(n for n in g['nodes'] if n['id']=='guide-asha');assert 'alias' in n['members']
    with f() as db:assert db.get(Entity,('A','alias')) and db.get(Edge,('A','guide-e1')).source=='guide-asha'
    u=c.post('/api/cases/A/identities/'+str(r.json()['id'])+'/undo',headers=h(),json={'expected_revision':1,'reason':'Recheck duplicate identity'});assert u.status_code==200,u.text
    assert len(c.get('/api/cases/A/graph',headers=h()).json()['nodes'])==5

def test_identity_fingerprint_stale_and_case_boundary(system):
    c,f=system;load(c,f);duplicate(c);body=action(c)
    c.post('/api/cases/A/entities',headers=h(),json={'id':'new','label':'New','kind':'Phone'})
    assert c.post('/api/cases/A/identities/review',headers=h(),json=body).status_code==409
    body=action(c);body['target']='not-in-case'
    assert c.post('/api/cases/A/identities/review',headers=h(),json=body).status_code==404
    assert c.get('/api/cases/other/identities',headers=h()).status_code==404

def test_merge_relinks_and_safe_order(system):
    c,f=system;load(c,f);accept(c)
    body=action(c,'guide-asha','guide-ravi');r=c.post('/api/cases/A/identities/review',headers=h(),json=body);assert r.status_code==200
    g=c.get('/api/cases/A/graph',headers=h()).json();e=next(e for e in g['edges'] if e['id']=='guide-e1');assert e['source']=='guide-ravi' and e['original_source']=='guide-asha'
    r2=c.post('/api/cases/A/identities/review',headers=h(),json=action(c,'guide-ravi','guide-neel'));assert r2.status_code==200,r2.text
    assert c.post('/api/cases/A/identities/'+str(r.json()['id'])+'/undo',headers=h(),json={'expected_revision':2,'reason':'Unsafe undo should fail'}).status_code==409

def test_hypothesis_snapshot_review_never_creates_edge(system):
    c,f=system;load(c,f);accept(c)
    d=c.post('/api/cases/A/hypotheses/compute',headers=h(),json={});assert d.status_code==200,d.text
    item=d.json()['items'][0];assert item['signals'] and item['source_ids'] and item['paths'][0]['directions']
    r=c.post('/api/cases/A/hypotheses/'+item['id']+'/review',headers=h(),json={'decision':'worth_following','expected_revision':0,'reason':'Worth seeking additional records'});assert r.status_code==200
    assert c.post('/api/cases/A/hypotheses/'+item['id']+'/review',headers=h(),json={'decision':'dismissed','expected_revision':0,'reason':'Stale review'}).status_code==409
    again=c.post('/api/cases/A/hypotheses/compute',headers=h(),json={}).json();assert next(x for x in again['items'] if x['id']==item['id'])['status']=='worth_following'
    assert c.get('/api/cases/A/records',headers=h()).json()['total']==4

def test_time_geo_and_report_escape(system):
    c,f=system;d=demo();d['entities'].append({'id':'place','label':'<script>alert(1)</script>','kind':'Location','attrs':{'latitude':'19.1','longitude':'72.9'}})
    d['edges'][0].update(target='place',relation='visited',occurred_at=None)
    d['sources'][0]['text']+='<script>bad()</script>';load(c,f,d)
    t=c.get('/api/cases/A/timeline',headers=h()).json();assert t['unknown_count']==1 and t['events'][-1]['precision']=='unknown'
    g=c.get('/api/cases/A/geo',headers=h()).json();assert g['points'][0]['latitude']==19.1 and len(g['points'][0]['records'])==1
    report=c.get('/api/cases/A/report.html',headers=h());assert report.status_code==200
    assert '<script>' not in report.text and '&lt;script&gt;' in report.text
    assert c.get('/api/cases/A/brief',headers=h()).json()['counts']['records']==4

def test_normalization_homonyms_and_conflicts():
    n=lambda id,label,attrs={}:SimpleNamespace(id=id,label=label,kind='Person',attrs=attrs)
    assert normalize('  ＡＳＨＡ—Rao ')==normalize('asha rao')
    assert normalize('0091 (90000) 00001','phone')=='+919000000001'
    assert features(n('1','Asha'),n('2','Asha'))['category']=='review'
    assert features(n('1','Asha',{'phone':'123456'}),n('2','Asha',{'phone':'654321'}))['category']=='likely_distinct'
    a=n('1','Asha Rao',{'email':'asha@example.test'});b=n('2','ASHA RAO',{'email':'ASHA@example.test'})
    assert features(a,b)['category']=='likely_match'
    assert candidates([a,b],[])['compared_pairs']==1

def test_invalid_types_paths_and_rejected_exclusion(system):
    c,f=system;d=demo();d['entities'][0]['kind']='Criminal';assert c.post('/api/cases/A/imports',headers=h(),json=d).status_code==422
    d=demo();d['sources'][0]['id']='../../secret';assert c.post('/api/cases/A/imports',headers=h(),json=d).status_code==422
    load(c,f);accept(c)
    rows=c.get('/api/cases/A/records',headers=h()).json()['items']
    c.post('/api/cases/A/review-batch',headers=h(),json={'edges':[{'id':e['id'],'revision':e['revision']} for e in rows],'decision':'rejected','reason':'Reject synthetic test data'})
    assert not c.post('/api/cases/A/hypotheses/compute',headers=h(),json={}).json()['items']

def test_background_analysis_and_projection(system):
    from app.services.analysis_jobs import process_analysis
    c,f=system;load(c,f);accept(c)
    r=c.post('/api/cases/A/analysis-jobs',headers=h(),json={'operation':'links'});assert r.status_code==202
    assert process_analysis(f)
    result=c.get('/api/cases/A/analysis-jobs/'+r.json()['id'],headers=h()).json()
    assert result['status']=='completed' and result['result']['items'][0]['id']
    p=c.get('/api/cases/A/projection?mode=communication',headers=h()).json()
    assert p['directed'] and len(p['edges'])==4
    assert not c.get('/api/cases/A/projection?mode=ownership',headers=h()).json()['edges']
    r=c.post('/api/cases/A/analysis-jobs',headers=h(),json={'operation':'identities'});assert process_analysis(f)
    assert c.get('/api/cases/A/analysis-jobs/'+r.json()['id'],headers=h()).json()['status']=='completed'

def test_analysis_crash_rolls_back(system,monkeypatch):
    from app.services.analysis_jobs import process_analysis
    from app.routes import intelligence
    import pytest
    c,f=system;load(c,f);accept(c)
    r=c.post('/api/cases/A/analysis-jobs',headers=h(),json={'operation':'links'})
    original=intelligence.compute_saved
    def crash(*args,**kwargs):raise RuntimeError('simulated worker interruption')
    monkeypatch.setattr(intelligence,'compute_saved',crash)
    with pytest.raises(RuntimeError):process_analysis(f)
    assert c.get('/api/cases/A/analysis-jobs/'+r.json()['id'],headers=h()).json()['status']=='queued'
    monkeypatch.setattr(intelligence,'compute_saved',original);assert process_analysis(f)
