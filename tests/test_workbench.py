import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from app.main import create_app
from app.models import Case,Edge,Entity,Job
from app.ingest import process_one
from app.schemas import ConvertIn
from app.services.conversion import convert

KEY='r'*32
@pytest.fixture
def system(tmp_path):
    app=create_app('sqlite:///'+str(tmp_path/'test.db'),{KEY:{'role':'owner'},'v'*32:{'role':'viewer'}})
    with TestClient(app) as c:
        with app.state.factory.begin() as db:db.add(Case(id='A',title='A'))
        yield c,app.state.factory

def h(key=KEY):return {'Authorization':'Bearer '+key}
def demo():return json.loads(Path('data/demo.json').read_text())
def load(c,f,bundle=None):
    r=c.post('/api/cases/A/imports',headers=h(),json=bundle or demo());assert r.status_code==202,r.text
    assert process_one(f)
    with f() as db:
        j=db.get(Job,r.json()['id']);assert j.status=='completed',j.error
    return r.json()
def accept(c):
    rows=c.get('/api/cases/A/records?limit=500',headers=h()).json()['items']
    r=c.post('/api/cases/A/review-batch',headers=h(),json={'edges':[{'id':e['id'],'revision':e['revision']} for e in rows], 'decision':'accepted','reason':'Checked source records'})
    assert r.status_code==200,r.text

def test_one_owner_full_access(system):
    c,f=system
    assert c.get('/api/cases').status_code==401
    assert c.get('/api/cases',headers=h('v'*32)).status_code==401
    created=c.post('/api/cases',headers=h(),json={'title':'Second dataset'})
    assert created.status_code==201
    assert c.get('/api/cases/'+created.json()['id']+'/graph',headers=h()).status_code==200

def test_demo2_exact_input(system):
    c,f=system
    p=c.post('/api/cases/A/convert',headers=h(),json={'text':Path('data/demo2.json').read_text(),'format':'auto'})
    assert p.status_code==200,p.text
    r=p.json();assert r['counts']=={'entities':35,'sources':47,'edges':49}
    assert any(e['occurred_at'] is None for e in r['bundle']['edges'])
    load(c,f,r['bundle']);accept(c)
    links=c.get('/api/cases/A/links',headers=h()).json()
    assert links['items']
    assert all(0<=x['score']<=90 for x in links['items'])

def test_preview_does_not_persist(system):
    c,f=system
    r=c.post('/api/cases/A/convert',headers=h(),json={'text':'Asha called Ravi on 2026-01-10.','format':'text'})
    assert r.status_code==200
    assert len(r.json()['bundle']['edges'])==1
    with f() as db:assert db.scalar(select(func.count()).select_from(Entity))==0

def test_text_uncertain_and_undated():
    r=convert(ConvertIn(text=Path('data/notes.txt').read_text(),format='text'))
    assert len(r['bundle']['edges'])==5
    assert r['bundle']['edges'][-1]['occurred_at'] is None
    assert len(r['bundle']['sources'])==6
    assert any('source only' in w for w in r['warnings'])

def test_call_log_custom_mapping_and_timezone():
    r=convert(ConvertIn(text='A_NUM|B_NUM|WHEN|duration\n9000000001|9000000002|2026-01-01T10:00:00|60',format='csv',column_map={'caller':'A_NUM','callee':'B_NUM','timestamp':'WHEN'}))
    assert r['bundle']['edges'][0]['occurred_at']=='2026-01-01T04:30:00+00:00'
    assert 'duration' in r['bundle']['sources'][0]['text']
    with pytest.raises(ValueError,match='row 2'):
        convert(ConvertIn(text='caller,callee,date\nabc,123456,2026-01-01',format='csv'))

def test_import_replay_and_atomic_failure(system):
    c,f=system;r=load(c,f)
    assert c.post('/api/cases/A/imports',headers=h(),json=demo()).json()['id']==r['id']
    d=demo();d['entities'].append({'id':'new','label':'New','kind':'Person','attrs':{}});d['edges'][0]['excerpt']='fabricated'
    j=c.post('/api/cases/A/imports',headers=h(),json=d).json();process_one(f)
    with f() as db:
        assert db.get(Job,j['id']).status=='failed'
        assert db.get(Entity,('A','new')) is None

def test_hidden_links_explanation_and_pending(system):
    c,f=system;load(c,f)
    assert c.get('/api/cases/A/links',headers=h()).json()['items']==[]
    accept(c)
    result=c.get('/api/cases/A/links',headers=h()).json()
    candidate=next(x for x in result['items'] if {x['source'],x['target']}=={'guide-asha','guide-ravi'})
    assert candidate['common_neighbors']==2 and len(candidate['paths'])==2
    assert all(p['evidence'] for p in candidate['paths'])
    assert 'uncalibrated' in candidate['score_label']

def test_review_conflict_and_edit_history(system):
    c,f=system;load(c,f)
    body={'decision':'accepted','reason':'Original source checked','expected_revision':0}
    assert c.post('/api/cases/A/edges/guide-e1/review',headers=h(),json=body).status_code==200
    assert c.post('/api/cases/A/edges/guide-e1/review',headers=h(),json=body).status_code==409
    r=c.patch('/api/cases/A/edges/guide-e1',headers=h(),json={'relation':'met','occurred_at':None,'polarity':'uncertain','expected_revision':1,'reason':'Correcting interpretation'})
    assert r.status_code==200,r.text
    with f() as db:
        e=db.get(Edge,('A','guide-e1'));assert e.status=='pending' and e.occurred_at==''
    logs=c.get('/api/cases/A/audit',headers=h()).json();assert any(a['action']=='edit_relationship' for a in logs)

def test_node_edit_and_stale_guard(system):
    c,f=system;load(c,f)
    body={'label':'New label','attrs':{'note':'test'},'expected_label':'Asha (demo)','expected_attrs':{}}
    assert c.patch('/api/cases/A/entities/guide-asha',headers=h(),json=body).status_code==200
    assert c.patch('/api/cases/A/entities/guide-asha',headers=h(),json=body).status_code==409

def test_unknown_dates_do_not_enter_filtered_graph(system):
    c,f=system;d=demo();d['edges'][0]['occurred_at']=None;load(c,f,d)
    g=c.get('/api/cases/A/graph?start=2026-01-01&end=2026-01-31',headers=h()).json()
    assert len(g['edges'])==3

def test_over_old_source_limit_and_large_text(system):
    c,f=system
    d=demo();d['sources'] += [{'id':f'extra-{i}','title':'Record','text':'A'*20000} for i in range(110)]
    # >2MB and >100 sources: rejected by v1, accepted by v2.
    load(c,f,d)
    assert c.get('/api/cases/A/sources?limit=500',headers=h()).status_code==200

def test_readable_validation_and_size_limit(system,monkeypatch):
    import app.middleware as middleware
    c,f=system
    r=c.post('/api/cases/A/imports',headers=h(),json={'persons':[]})
    assert r.status_code==422 and r.json()['errors'][0]['field']=='body.persons'
    monkeypatch.setattr(middleware,'MAX_UPLOAD_BYTES',100)
    r=c.post('/api/cases/A/imports',headers=h(),content='x'*101)
    assert r.status_code==413 and 'MB' in r.json()['detail']

def test_jsonl_and_csv():
    r=convert(ConvertIn(text=Path('data/call_logs.csv').read_text(),format='auto'))
    assert r['counts']['edges']==4
    r=convert(ConvertIn(text='{"caller":"9000000001","callee":"9000000002"}\n',format='jsonl'))
    assert r['bundle']['edges'][0]['occurred_at'] is None

def test_graph_capacity_explicit(system,monkeypatch):
    import app.analytics as analytics
    c,f=system;load(c,f);monkeypatch.setattr(analytics,'MAX_EDGES',2)
    assert c.get('/api/cases/A/graph',headers=h()).status_code==422
    assert c.get('/api/cases/A/graph?focus=guide-asha',headers=h()).status_code==200

def test_standalone_entity_and_records_pagination(system):
    c,f=system
    c.post('/api/cases/A/entities',headers=h(),json={'id':'alone','label':'Alone','kind':'Person'})
    assert len(c.get('/api/cases/A/graph',headers=h()).json()['nodes'])==1
    load(c,f)
    result=c.get('/api/cases/A/records?limit=2&offset=2',headers=h()).json()
    assert result['total']==4 and len(result['items'])==2
