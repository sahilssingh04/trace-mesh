"""A small, fictional network with an intentionally missing direct connection."""
import json
from pathlib import Path
nodes=[{'id':i,'label':n,'kind':'Person','attrs':{}} for i,n in [('guide-asha','Asha (demo)'),('guide-ravi','Ravi (demo)'),('guide-neel','Neel (demo)'),('guide-mira','Mira (demo)')]]
edges=[];sources=[]
for i,(a,b) in enumerate([('asha','neel'),('ravi','neel'),('asha','mira'),('ravi','mira')],1):
    text=f'FICTIONAL DEMO: {a.title()} called {b.title()} on 2026-01-{i:02d}.'
    sources.append({'id':f'guide-s{i}','title':f'Demo call record {i}','text':text})
    edges.append({'id':f'guide-e{i}','source':'guide-'+a,'target':'guide-'+b,'relation':'called',
        'source_id':f'guide-s{i}','excerpt':text,'occurred_at':f'2026-01-{i:02d}','polarity':'asserted'})
Path('data/demo.json').write_text(json.dumps({'entities':nodes,'sources':sources,'edges':edges},indent=2))
