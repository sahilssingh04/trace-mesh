"""Fixed adversarial identity fixture; reports missed blocking and ranking errors."""
import json,sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.resolution import candidates
rows=[];truth={}
def pair(tag,left,right,positive):
    for suffix,(label,kind,attrs) in zip(['a','b'],[left,right]):rows.append(SimpleNamespace(id=tag+suffix,label=label,kind=kind,attrs=attrs))
    truth[tuple(sorted([tag+'a',tag+'b']))]=positive
pair('unicode',('ＡＳＨＡ Rao','Person',{'email':'a@example.test'}),('asha rao','Person',{'email':'A@example.test'}),True)
pair('phone',('+91 (90000) 00001','Phone',{}),('00919000000001','Phone',{}),True)
pair('vehicle',('MH-01 AB 1234','Vehicle',{}),('MH01AB1234','Vehicle',{}),True)
pair('homonym',('Ravi Kumar','Person',{'phone':'111111'}),('Ravi Kumar','Person',{'phone':'222222'}),False)
pair('commonname',('Amit Shah','Person',{}),('Amit Shah','Person',{}),False)
pair('typo',('Neel Sharma','Person',{'email':'n@example.test'}),('Neil Sharma','Person',{'email':'n@example.test'}),True)
pair('alias',('Meera Desai','Person',{'aliases':'Mira D','phone':'999999'}),('Mira D','Person',{'phone':'999999'}),True)
pair('weakalias',('Sanjay Patel','Person',{'aliases':'Sam'}),('Sam','Person',{}),True)
pair('missing',('Kiran Rao','Person',{}),('K. Rao','Person',{}),True)
pair('conflict',('Rohan Singh','Person',{'email':'one@example.test'}),('Rohan Singh','Person',{'email':'two@example.test'}),False)
pair('recycled',('Old Owner','Person',{'phone':'777777'}),('New Owner','Person',{'phone':'777777'}),False)
pair('country',('9000000002','Phone',{}),('+919000000002','Phone',{}),True)
result=candidates(rows,[]);by={(x['source'],x['target']):x for x in result['items']}
# All cross-fixture pairs are also distinct: assess full pair universe, including missed blocks.
from itertools import combinations
for a,b in combinations(sorted(n.id for n in rows),2):truth.setdefault((a,b),False)
tp=fp=fn=tn=0;missed_blocking=0;errors=[]
for pair,actual in truth.items():
    pred=by.get(pair,{}).get('category')=='likely_match'
    tp+=pred and actual;fp+=pred and not actual;fn+=not pred and actual;tn+=not pred and not actual
    if actual and pair not in by:missed_blocking+=1
    if pred!=actual:errors.append({'pair':pair,'actual_match':actual,'category':by.get(pair,{}).get('category','not_generated')})
p=tp/max(1,tp+fp);rec=tp/max(1,tp+fn)
out={'fixture':'24 records, 8 duplicate pairs plus all cross-pair negatives; adversarial synthetic only','decision_threshold':'likely_match (still requires human approval)','precision':p,'recall':rec,'f1':2*p*rec/max(1e-9,p+rec),'false_merge_suggestions':fp,'missed_match_suggestions':fn,'missed_by_blocking':missed_blocking,'tp':tp,'fp':fp,'fn':fn,'tn':tn,'errors':errors,'warning':'These are ranking suggestions, not automatic merge outcomes. Tiny fixed fixture is not field validation.'}
Path('verification/resolution-evaluation.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
