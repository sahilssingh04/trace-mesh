"""Reproducible local SQLite import benchmark. Not a deployment/load benchmark."""
import json,sys,tempfile,time,platform
from datetime import datetime,timedelta,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import event
from app.models import Base,Case,database
from app.schemas import ConvertIn
from app.services.conversion import convert
from app.ingest import ingest
start=datetime(2026,1,1,tzinfo=timezone.utc)
text='caller,callee,timestamp,duration_seconds\n'+'\n'.join(f'9000000001,{9000000002+i%100},{(start+timedelta(seconds=i)).isoformat()},60' for i in range(10000))
t=time.perf_counter();result=convert(ConvertIn(text=text,format='csv'));conversion=time.perf_counter()-t
with tempfile.TemporaryDirectory() as tmp:
    engine,factory=database('sqlite:///'+str(Path(tmp)/'bench.db'));Base.metadata.create_all(engine)
    with factory.begin() as db:db.add(Case(id='BENCH',title='Synthetic benchmark'))
    selects=[]
    @event.listens_for(engine,'before_cursor_execute')
    def capture(conn,cursor,statement,parameters,context,executemany):
        if statement.lstrip().upper().startswith('SELECT'):selects.append(1)
    t=time.perf_counter()
    with factory.begin() as db:ingest(db,'BENCH','benchmark',result['bundle'])
    elapsed=time.perf_counter()-t
    engine.dispose()
print(json.dumps({'scope':'Single-process local SQLite conversion + one atomic import; no HTTP/browser/network/concurrency', 'python':platform.python_version(),'input_bytes':len(text.encode()),'counts':result['counts'],'conversion_seconds':conversion,'import_seconds':elapsed,'select_statements':len(selects)},indent=2))
