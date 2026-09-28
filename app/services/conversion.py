"""Deterministic adapters with explicit omissions. Never silently turn prose into facts."""
import csv
import io
import json
import re
import hashlib
from datetime import datetime, timezone
from ..schemas import Bundle


def ident(value, prefix):
    return prefix+'-'+hashlib.sha256(value.encode()).hexdigest()[:20]


class Builder:
    def __init__(self, title):
        self.title=title;self.nodes={};self.sources=[];self.source_ids=set();self.edges=[];self.warnings=[]
    def node(self,label,kind='Person',id=None,attrs=None):
        id=id or ident(kind+':'+label.casefold().strip(),'n')
        value={'id':id,'label':label,'kind':kind,'attrs':attrs or {}}
        if id in self.nodes and self.nodes[id]!=value: raise ValueError(f'Conflicting entity ID {id}')
        self.nodes[id]=value;return id
    def source(self,text):
        id=ident(text,'s')
        if id not in self.source_ids:
            self.sources.append({'id':id,'title':self.title,'text':text});self.source_ids.add(id)
        return id
    def edge(self,a,b,r,text,t=None,polarity='asserted'):
        s=self.source(text)
        key=json.dumps([a,b,r,s,t,polarity,len(self.edges)])
        self.edges.append({'id':ident(key,'e'),'source':a,'target':b,'relation':r,'source_id':s,
                           'excerpt':text[:10000],'occurred_at':t,'polarity':polarity})
    def result(self,fmt):
        bundle=Bundle.model_validate({'entities':list(self.nodes.values()),'sources':self.sources,'edges':self.edges}).model_dump(mode='json')
        return {'format':fmt,'bundle':bundle,'warnings':self.warnings[:100], 'warning_count':len(self.warnings),
                'counts':{k:len(v) for k,v in bundle.items()},'note':'Preview only. Import creates pending claims. Unknown event times stay unknown.'}


def event_time(row,offset):
    date=str(row.get('date') or '').strip();time=str(row.get('time') or '').strip()
    value=str(row.get('timestamp') or row.get('occurred_at') or '').strip()
    if not value:
        if not date: return None
        if not time: return date
        value=date+'T'+time
    d=datetime.fromisoformat(value.replace('Z','+00:00'))
    if d.tzinfo is None: d=datetime.fromisoformat(value+offset)
    return d.astimezone(timezone.utc).isoformat()


def structured(data,title,offset):
    b=Builder(title)
    specs=[('persons','person_id','name','Person'),('phones','phone_id','number','Phone'),
           ('organizations','organization_id','name','Organization'),('vehicles','vehicle_id','registration','Vehicle'),
           ('locations','location_id','name','Location'),('cases','case_id','case_type','Case')]
    for key,idkey,labelkey,kind in specs:
        for row in data.get(key,[]):
            b.node(str(row[labelkey]),kind,str(row[idkey]),{'original':json.dumps(row,ensure_ascii=False)})
    for key in ('phones','vehicles'):
        for row in data.get(key,[]):
            if row.get('owner_person_id'):
                b.edge(row['owner_person_id'],row['phone_id' if key=='phones' else 'vehicle_id'],'owns',json.dumps(row,ensure_ascii=False))
    for row in data.get('organization_links',[]):
        b.edge(row['person_id'],row['organization_id'],'owns' if row.get('relationship')=='owner' else 'member_of',json.dumps(row,ensure_ascii=False))
    for row in data.get('cases',[]):
        for person in row.get('persons',[]): b.edge(person,row['case_id'],'mentioned_in',json.dumps(row,ensure_ascii=False),row.get('date'))
    for key,a,c,r in [('communications','from_phone','to_phone','called'),('transactions','from_person','to_person','transferred'),('vehicle_movements','vehicle_id','location_id','visited')]:
        for row in data.get(key,[]): b.edge(row[a],row[c],r,json.dumps(row,ensure_ascii=False),event_time(row,offset))
    for row in data.get('investigation_notes',[]): b.source(json.dumps(row,ensure_ascii=False))
    if data.get('dataset_info'): b.source(json.dumps(data['dataset_info'],ensure_ascii=False))
    b.warnings += [f'Naive date/time fields use the selected UTC offset {offset}. Date-only records keep day precision.',
                   'Ownership and organization links without dates remain undated. Time-filtered analysis excludes undated records.',
                   'Narrative notes retained as sources, not converted into asserted relationships. Case mentions do not imply wrongdoing.',
                   'Caller location IDs and transaction metadata are retained in source records; no personal co-location is inferred.']
    known={x[0] for x in specs}|{'organization_links','communications','transactions','vehicle_movements','investigation_notes','dataset_info'}
    if set(data)-known: raise ValueError('Unrecognized top-level sections: '+', '.join(sorted(set(data)-known)))
    return b.result('structured investigation JSON')


ALIASES={'caller':['caller','from','from_phone','source','calling_number','a_number'],
         'callee':['callee','to','to_phone','target','called_number','b_number'],
         'timestamp':['timestamp','datetime','occurred_at','start_time'], 'date':['date','call_date'], 'time':['time','call_time']}


def calls(text,title,offset,mapping):
    b=Builder(title)
    try: dialect=csv.Sniffer().sniff(text[:8192],delimiters=',;\t|')
    except csv.Error: dialect=csv.excel
    reader=csv.DictReader(io.StringIO(text),dialect=dialect)
    headers=reader.fieldnames or []
    lookup={h.strip().lower():h for h in headers}
    columns={key:mapping.get(key) or next((lookup[a] for a in names if a in lookup),None) for key,names in ALIASES.items()}
    if not columns['caller'] or not columns['callee']:
        raise ValueError('Call-log columns not recognized. Map caller and callee columns. Found: '+', '.join(headers))
    def phone(value):
        raw=str(value or '').strip()
        if not raw: raise ValueError('Empty caller/callee')
        normalized=re.sub(r'[\s()-]','',raw)
        if not re.fullmatch(r'\+?\d{5,18}',normalized): raise ValueError('Phone identifier must contain 5–18 digits; map caller/callee number columns')
        return b.node(normalized,'Phone')
    for i,row in enumerate(reader,2):
        if i>50001: raise ValueError('Call log exceeds 50,000 rows. Split into files.')
        if None in row: raise ValueError(f'Row {i}: too many columns; check delimiter/quoting')
        try:
            a,c=phone(row[columns['caller']]),phone(row[columns['callee']])
            stamp=event_time({k:row.get(v,'') for k,v in columns.items() if v and k in ('timestamp','date','time')},offset)
            b.edge(a,c,'called',json.dumps(row,ensure_ascii=False),stamp)
        except (ValueError,KeyError) as exc: raise ValueError(f'Call-log row {i}: {exc}')
    if not b.edges: raise ValueError('No call rows found')
    b.warnings.append(f'Calls connect phone identifiers, not proven owners. Naive times use {offset}; original duration and other columns remain in source text.')
    return b.result('delimited call log')


def prose(text,title,default):
    b=Builder(title)
    relations={'called':'called','met':'met','owns':'owns','uses':'uses','visited':'visited','works for':'member_of','transferred to':'transferred'}
    pattern=re.compile(r'^(?P<a>.+?)\s+(?P<r>transferred to|works for|called|met|owns|uses|visited)\s+(?P<b>.+?)(?:\s+on\s+(?P<t>\d{4}-\d{2}-\d{2}(?:T\S+)?))?\.?$',re.I)
    # One relation per sentence/line; unsupported sentences are retained and listed.
    chunks=[s.strip() for s in re.split(r'\n+|(?<=[.!?])\s+(?=[A-Z])',text) if s.strip()]
    for i,line in enumerate(chunks,1):
        m=pattern.fullmatch(line)
        if not m or re.search(r'\b(not|never|denied|reportedly|possibly|allegedly|maybe|might|may|and|or|he|she|they)\b',line,re.I):
            b.source(line);b.warnings.append(f'Line {i}: retained as source only. Use one explicit subject–relation–object statement; resolve negation, aliases or uncertainty manually.');continue
        a,c=m['a'].strip(' "'),m['b'].strip(' ."');r=relations[m['r'].lower()]
        kind=lambda label:'Phone' if re.fullmatch(r'\+?\d{5,18}',label) else 'Person'
        target_kind='Location' if r=='visited' else 'Organization' if r=='member_of' else kind(c)
        stamp=m['t'] or (default.isoformat() if default else None)
        b.edge(b.node(a,kind(a)),b.node(c,target_kind),r,line,stamp)
    if default: b.warnings.append('Missing event dates used your explicitly selected default timestamp. Confirm before importing.')
    b.warnings.append('English pattern parser, not general language understanding. Same normalized label reuses an ID; homonyms need separate IDs in preview/manual entry.')
    return b.result('natural-language draft')


def convert(item):
    text=item.text.lstrip('\ufeff').strip();fmt=item.format
    if fmt=='auto':
        fmt='json' if text.startswith(('{','[')) else 'csv' if any(c in text.splitlines()[0] for c in (',','\t','|',';')) else 'text'
    if fmt=='json':
        try: data=json.loads(text)
        except json.JSONDecodeError as exc: raise ValueError(f'Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}')
        if isinstance(data,dict) and ('entities' in data or 'edges' in data):
            result=Bundle.model_validate(data).model_dump(mode='json')
            return {'format':'canonical JSON','bundle':result,'counts':{k:len(v) for k,v in result.items()},'warnings':[],'warning_count':0}
        if isinstance(data,dict) and 'persons' in data: return structured(data,item.title,item.timezone_offset)
        if isinstance(data,list) and all(isinstance(r,dict) for r in data):
            stream=io.StringIO();keys=list(dict.fromkeys(k for row in data for k in row));writer=csv.DictWriter(stream,fieldnames=keys);writer.writeheader();writer.writerows(data)
            return calls(stream.getvalue(),item.title,item.timezone_offset,item.column_map)
        raise ValueError('Unsupported JSON structure. Use a canonical bundle, investigation JSON with persons, or an array of call-log rows.')
    if fmt=='jsonl':
        rows=[]
        for i,line in enumerate(text.splitlines(),1):
            if line.strip():
                try: rows.append(json.loads(line))
                except json.JSONDecodeError: raise ValueError(f'Invalid JSON on line {i}')
        return convert(item.model_copy(update={'format':'json','text':json.dumps(rows)}))
    if fmt=='csv': return calls(text,item.title,item.timezone_offset,item.column_map)
    return prose(text,item.title,item.default_time)
