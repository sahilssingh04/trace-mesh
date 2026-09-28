"""Convert three UTF-8 CSV files to the canonical JSON ingestion schema."""
import argparse
import csv
import json
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--entities',required=True)
p.add_argument('--sources',required=True)
p.add_argument('--edges',required=True)
p.add_argument('--output',default='bundle.json')
a=p.parse_args()
result={}
for key in ('entities','sources','edges'):
    with open(getattr(a,key),encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    if key=='entities':
        for row in rows: row['attrs']=json.loads(row.get('attrs') or '{}')
    if key=='edges':
        for row in rows:
            if not row.get('polarity'): row['polarity']='asserted'
    result[key]=rows
Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('Wrote',a.output,'— API validates it before queueing')
