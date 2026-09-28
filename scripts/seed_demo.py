"""Only seeds a NEW starter case. Existing cases and user edits are never overwritten."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select
from app.models import Base,Case,Edge,Review,database
from app.ingest import ingest
engine,factory=database();Base.metadata.create_all(engine)
with factory.begin() as db:
    if db.get(Case,'GUIDE'):
        print('Starter case already exists; preserving all changes.')
    else:
        db.add(Case(id='GUIDE',title='Start here · four fictional people'));db.flush()
        ingest(db,'GUIDE','demo-fixture',json.loads(Path('data/demo.json').read_text()))
        for e in db.scalars(select(Edge).where(Edge.case_id=='GUIDE')):
            e.status='accepted';e.revision=1
            db.add(Review(case_id='GUIDE',edge_id=e.id,actor='demo-fixture',decision='accepted',reason='Fictional starter example'))
        print('Starter case ready. Open Hidden links for Asha ↔ Ravi.')

with factory.begin() as db:
    if not db.get(Case,'SHOWCASE'):
        db.add(Case(id='SHOWCASE',title='V3 showcase · fictional fragmented records'));db.flush()
        ingest(db,'SHOWCASE','demo-fixture',json.loads(Path('data/showcase-v3.json').read_text()))
        for e in db.scalars(select(Edge).where(Edge.case_id=='SHOWCASE')):
            e.status='accepted';e.revision=1
            db.add(Review(case_id='SHOWCASE',edge_id=e.id,actor='demo-fixture',decision='accepted',reason='Fictional V3 demonstration fixture'))
        print('V3 showcase ready: compare Asha identities, merge, and inspect explained leads.')
