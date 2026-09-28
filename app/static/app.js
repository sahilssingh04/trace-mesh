'use strict';
const $=id=>document.getElementById(id), NS='http://www.w3.org/2000/svg';
let token='',caseId='',data={nodes:[],edges:[]},links={items:[]},preview=null,recordOffset=0,records=[],sourceOffset=0,active='network',poller=null,noticeTimer,positions=new Map(),viewState=null;
const relations=['called','met','owns','uses','visited','member_of','transferred','mentioned_in'];
const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
const button=(text,fn,cls)=>{const b=node('button',text,cls);b.onclick=()=>run(fn,b);return b;};
const option=(label,value)=>{const o=node('option',label);o.value=value;return o;};
function say(message){$('notice').textContent=message;$('notice').hidden=false;clearTimeout(noticeTimer);noticeTimer=setTimeout(()=>$('notice').hidden=true,10000);}
async function run(fn,b){if(b)b.disabled=true;$('busy').textContent='Working…';try{return await fn();}catch(e){say(e.message);}finally{if(b)b.disabled=false;$('busy').textContent='';}}
function bind(id,fn){$(id).onclick=()=>run(fn,$(id));}
async function api(path,opts={}){const r=await fetch('/api'+path,{...opts,headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'}});let d;try{d=await r.json();}catch{throw Error('Server returned an unreadable response. Check the server window.');}if(!r.ok){let message=typeof d.detail==='string'?d.detail:JSON.stringify(d.detail);if(d.errors)message+='\n'+d.errors.map(e=>e.field+': '+e.message).join('\n');throw Error(message);}return d;}
const base=()=>'/cases/'+encodeURIComponent(caseId),post=(path,body)=>api(path,{method:'POST',body:JSON.stringify(body)});
function query(){const p=new URLSearchParams();for(const k of ['start','end','focus'])if($(k).value)p.set(k,$(k).value);return p;}
const label=id=>data.nodes.find(n=>n.id===id)?.label||id;
function download(value,name){const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));const a=node('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function modal(title,content){$('modalContent').replaceChildren(node('h2',title),content);$('modal').showModal();}
bind('closeModal',async()=>$('modal').close());
async function loadCases(selected){const d=await api('/cases');$('cases').replaceChildren(...d.cases.map(c=>option(c.title,c.id)));if(selected)$('cases').value=selected;else if(d.cases.some(c=>c.id==='GUIDE'))$('cases').value='GUIDE';caseId=$('cases').value;}
bind('signIn',async()=>{token=$('token').value.trim();await loadCases();$('login').hidden=true;$('workspace').hidden=false;$('token').value='';if(caseId)await refresh();else await newCase();});
bind('signOut',async()=>{token='';clearInterval(poller);location.reload();});
async function newCase(){const title=prompt('Name your new case / dataset');if(!title?.trim())return;const c=await post('/cases',{title:title.trim()});await loadCases(c.id);clearState();await refresh();}
bind('newCase',newCase);
function clearState(){data={nodes:[],edges:[]};links={items:[]};positions.clear();viewState=null;draw(true);$('stats').replaceChildren();preview=null;$('previewPanel').hidden=true;recordOffset=0;sourceOffset=0;clearInterval(poller);poller=null;for(const k of ['start','end','focus','search','kindFilter','relationFilter'])$(k).value='';$('inspector').replaceChildren(node('p','Select a record to inspect.','subtle'));}
$('cases').onchange=()=>run(async()=>{caseId=$('cases').value;clearState();await refresh();});
async function showTab(tab){active=tab;document.querySelectorAll('.tab').forEach(n=>n.hidden=n.id!==tab);document.querySelectorAll('.sidebar button[data-tab]').forEach(n=>n.classList.toggle('active',n.dataset.tab===tab));$('pageTitle').textContent={network:'Network',links:'Explainable leads',input:'Add data',records:'Evidence',insights:'Insights',identity:'Resolve identities',timeline:'Timeline & places',brief:'Case brief'}[tab];if(tab==='links')await loadLinks();if(tab==='records'){await loadRecords();await loadSources(true);}if(tab==='input'){populateEntities();await jobs();}if(tab==='insights')await insights();if(tab==='identity')await loadIdentity();if(tab==='timeline')await loadTimeline();if(tab==='brief')await loadBrief();if(tab==='network'&&cy){cy.resize();}}
document.querySelectorAll('.sidebar button[data-tab]').forEach(b=>b.onclick=()=>run(()=>showTab(b.dataset.tab),b));
bind('emptyAdd',()=>showTab('input'));
async function refresh(){const selectedCase=caseId,p=query();p.set('pending',$('pending').checked);const incoming=await api(base()+'/graph?'+p);if(selectedCase!==caseId)return;data=incoming;$('stats').replaceChildren(...[['Entities',data.nodes.length,'In this view'],['Relationships',data.edges.length,'Source-backed claims'],['Pending',data.edges.filter(e=>e.status==='pending').length,'Ready for your confirmation'],['Accepted',data.edges.filter(e=>e.status==='accepted').length,'Used for link suggestions']].map(([t,v,s])=>{const d=node('div',undefined,'stat');d.append(node('span',t),node('strong',String(v)),node('small',s));return d;}));$('scopeLabel').textContent=data.scope;populateEntities();await loadLinks();draw();if(active==='records')await loadRecords();if(active==='insights')await insights();}
bind('refresh',refresh);bind('refreshLinks',loadLinks);bind('refreshInsights',insights);$('showLinks').onchange=draw;$('search').oninput=draw;
function populateEntities(){for(const id of ['manualFrom','manualTo']){const old=$(id).value;$(id).replaceChildren(option('Select an existing entity',''),...data.nodes.map(n=>option(n.label+' · '+n.id,n.id)));if(data.nodes.some(n=>n.id===old))$(id).value=old;}}
$('manualRelation').replaceChildren(...relations.map(r=>option(r.replaceAll('_',' '),r)));
function svg(tag,attrs){const n=document.createElementNS(NS,tag);for(const[k,v]of Object.entries(attrs))n.setAttribute(k,v);return n;}
let cy=null,graphSelection=null;
function captureGraphState(){
 if(!cy)return;
 viewState={zoom:cy.zoom(),pan:{...cy.pan()}};
 cy.nodes().forEach(n=>{
  const p=n.position();
  if(Number.isFinite(p.x)&&Number.isFinite(p.y))positions.set(n.id(),{x:p.x,y:p.y});
 });
}
function initialGraphPositions(shown,edges){
 const out=new Map(),count=shown.length;
 shown.forEach((n,i)=>{
  const a=(i/Math.max(1,count))*Math.PI*2;
  out.set(n.id,{x:450+220*Math.cos(a),y:280+175*Math.sin(a)});
 });
 if(count>160)return out;
 for(let t=0;t<90;t++){
  const force=new Map(shown.map(n=>[n.id,{x:0,y:0}]));
  for(let i=0;i<count;i++)for(let j=i+1;j<count;j++){
   const a=out.get(shown[i].id),b=out.get(shown[j].id);
   const dx=a.x-b.x,dy=a.y-b.y,d=Math.max(26,Math.hypot(dx,dy));
   const rep=2400/(d*d);
   force.get(shown[i].id).x+=dx/d*rep;force.get(shown[i].id).y+=dy/d*rep;
   force.get(shown[j].id).x-=dx/d*rep;force.get(shown[j].id).y-=dy/d*rep;
  }
  for(const e of edges){
   const a=out.get(e.source),b=out.get(e.target);if(!a||!b)continue;
   const dx=b.x-a.x,dy=b.y-a.y,d=Math.max(1,Math.hypot(dx,dy));
   const attract=(d-125)*0.0025;
   force.get(e.source).x+=dx/d*attract;force.get(e.source).y+=dy/d*attract;
   force.get(e.target).x-=dx/d*attract;force.get(e.target).y-=dy/d*attract;
  }
  for(const n of shown){
   const p=out.get(n.id),f=force.get(n.id);
   p.x=Math.max(55,Math.min(845,p.x+f.x*7+(450-p.x)*0.003));
   p.y=Math.max(45,Math.min(515,p.y+f.y*7+(280-p.y)*0.003));
  }
 }
 return out;
}
function buildGraphPositions(shown,edges,reset){
 if(reset)positions.clear();
 const initial=initialGraphPositions(shown,edges);
 const known=[...shown].filter(n=>positions.has(n.id));
 if(!known.length){for(const [id,p] of initial)positions.set(id,p);return;}
 for(const n of shown){
  if(positions.has(n.id))continue;
  const neighbors=[];
  for(const e of edges){if(e.source===n.id&&positions.has(e.target))neighbors.push(positions.get(e.target));else if(e.target===n.id&&positions.has(e.source))neighbors.push(positions.get(e.source));}
  if(neighbors.length){
   const x=neighbors.reduce((a,p)=>a+p.x,0)/neighbors.length,y=neighbors.reduce((a,p)=>a+p.y,0)/neighbors.length;
   const angle=(n.id.length*37)%360*Math.PI/180;
   positions.set(n.id,{x:x+46*Math.cos(angle),y:y+46*Math.sin(angle)});
  }else positions.set(n.id,initial.get(n.id)||{x:450,y:280});
 }
}
function draw(reset=false){
 const hadPreviousPositions=!reset&&data.nodes.some(n=>positions.has(n.id));
 captureGraphState();
 const shown=data.nodes.filter(n=>!$('kindFilter').value||n.kind===$('kindFilter').value).slice(0,500),ids=new Set(shown.map(n=>n.id));
 const edges=data.edges.filter(e=>ids.has(e.source)&&ids.has(e.target)&&(!$('relationFilter').value||e.relation===$('relationFilter').value)).slice(0,2000);
 $('graphEmpty').hidden=shown.length>0;$('graphLimit').textContent=`Showing ${shown.length} of ${data.nodes.length} entities and ${edges.length} of ${data.edges.length} records. Use type, date or focused queries to narrow the view.`;
 const hypothesisElements=$('showLinks').checked?links.items.filter(h=>ids.has(h.source)&&ids.has(h.target)).slice(0,50).map((h,i)=>({data:{id:'hyp:'+i,source:h.source,target:h.target,label:'Potential relationship',hypothesis:h},classes:'hypothesis'})):[];
 buildGraphPositions(shown,edges,reset);
 const saved={};for(const n of shown){const p=positions.get(n.id);if(p)saved[n.id]={x:p.x,y:p.y};}
 if(cy)cy.destroy();
 cy=cytoscape({container:$('graph'),elements:[...shown.map(n=>({data:{id:n.id,label:n.label,kind:n.kind}})),...edges.map(e=>({data:{id:'edge:'+e.id,source:e.source,target:e.target,label:e.relation,record:e},classes:e.status+' '+e.polarity})),...hypothesisElements],
  style:[
   {selector:'node',style:{'background-color':'#117e79','label':'data(label)','color':'#182b36','font-size':10,'font-weight':500,'text-valign':'bottom','text-margin-y':8,'text-wrap':'ellipsis','text-max-width':'110px','width':27,'height':27,'border-width':2,'border-color':'#ffffff'}},
   {selector:'node[kind != "Person"]',style:{'background-color':'#fffaf1','border-color':'#d39752','shape':'roundrectangle'}},
   {selector:'node[kind = "Location"]',style:{'background-color':'#f5f8ff','border-color':'#6f8fbe','shape':'roundrectangle'}},
   {selector:'node[kind = "Organization"]',style:{'background-color':'#f7f3ff','border-color':'#8f77ba','shape':'roundrectangle'}},
   {selector:'edge',style:{'width':1.35,'line-color':'#8db5b2','target-arrow-color':'#8db5b2','target-arrow-shape':'triangle','curve-style':'bezier','label':'','font-size':9,'font-weight':600,'color':'#52656e','text-rotation':'autorotate','text-background-color':'#ffffff','text-background-opacity':.95,'text-background-padding':3}},
   {selector:'.pending',style:{'line-style':'dashed','opacity':.72}},
   {selector:'.rejected',style:{'line-color':'#ba5359','target-arrow-color':'#ba5359'}},
   {selector:'.denied',style:{'line-color':'#ba5359','target-arrow-color':'#ba5359'}},
   {selector:'.uncertain',style:{'line-color':'#b77e22','target-arrow-color':'#b77e22'}},
   {selector:'.hypothesis',style:{'line-color':'#8865c7','target-arrow-color':'#8865c7','line-style':'dashed','target-arrow-shape':'none','label':'Potential relationship','color':'#6c4da8','font-size':8,'text-background-color':'#ffffff','text-background-opacity':.96}},
   {selector:':selected',style:{'border-width':3,'border-color':'#117e79','line-color':'#117e79','target-arrow-color':'#117e79','label':'data(label)','text-background-opacity':1}},
   {selector:'.dim',style:{'opacity':.14}}
  ],layout:{name:'preset',positions:saved,fit:false,padding:45},minZoom:.2,maxZoom:4,wheelSensitivity:.15});
 const q=$('search').value.toLowerCase();if(q)cy.nodes().filter(n=>!(`${n.data('label')} ${n.id()}`.toLowerCase().includes(q))).addClass('dim');
 cy.on('tap','node',e=>{graphSelection=e.target.id();inspectNode(data.nodes.find(n=>n.id===graphSelection));});
 cy.on('tap','edge',e=>run(()=>e.target.data('hypothesis')?inspectLink(e.target.data('hypothesis')):inspectEdge(e.target.data('record'))));
 $('graphAccess').replaceChildren(...shown.map(n=>button(n.label,async()=>{graphSelection=n.id;inspectNode(n);cy.center(cy.getElementById(n.id));})));
 if(!hadPreviousPositions){cy.fit(undefined,45);captureGraphState();} else if(viewState){cy.zoom(viewState.zoom);cy.pan(viewState.pan);} 
}
bind('resetGraph',async()=>{positions.clear();draw(true);});
function field(title,value,tag='input'){const l=node('label',title),i=node(tag);i.value=value??'';l.append(i);return [l,i];}
function inspectNode(n){const box=$('inspector'),[l,name]=field('Name',n.label);box.replaceChildren(node('h3',n.label),node('small',n.kind+' · '+n.id),l);const attrFields=[];for(const [key,value] of Object.entries(n.attrs)){if(key==='original'){const d=node('details');d.append(node('summary','Original imported fields'));try{for(const [k,v] of Object.entries(JSON.parse(value)))d.append(node('p',k.replaceAll('_',' ')+': '+String(v)));}catch{d.append(node('p',value));}box.append(d);continue;}const [el,input]=field(key.replaceAll('_',' '),value);box.append(el);attrFields.push([key,input]);}const [newKey,k]=field('Add attribute name',''),[newValue,v]=field('Attribute value','');const more=node('details');more.append(node('summary','Add an attribute'),newKey,newValue);box.append(more,button('Save changes',async()=>{const attrs={...n.attrs};for(const [key,input] of attrFields)attrs[key]=input.value;if(k.value.trim())attrs[k.value.trim()]=v.value;await api(base()+'/entities/'+n.id,{method:'PATCH',body:JSON.stringify({label:name.value,attrs,expected_label:n.label,expected_attrs:n.attrs})});await refresh();say('Entity updated.');},'primary'),button('Focus neighborhood',async()=>{$('focus').value=n.id;await refresh();}),button('Use as path start',async()=>$('pathFrom').value=n.id));nodeTools(box,n);}
async function inspectEdge(e){if(active!=='network')await showTab('network');const s=await api(base()+'/sources/'+e.source_id),box=$('inspector');box.replaceChildren(node('h3',label(e.source)+' → '+label(e.target)),node('span',e.status+' · '+e.polarity,'badge '+e.status),node('p',e.relation+' · '+(e.occurred_at||'Unknown event time')),node('div',e.excerpt,'source'));const d=node('details'),sum=node('summary','Original source & hash');d.append(sum,node('div',s.text,'source'),node('small',s.sha256));box.append(d);const [r,reason]=field('Reason for review / correction','','textarea');reason.rows=2;box.append(r);for(const decision of ['accepted','rejected','pending'])box.append(button({accepted:'Confirm',rejected:'Reject',pending:'Set pending'}[decision],async()=>{await post(base()+'/edges/'+e.id+'/review',{decision,reason:reason.value,expected_revision:e.revision});await refresh();box.replaceChildren(node('p','Saved. Select a record to continue.'));},decision==='accepted'?'primary':''));const edit=node('details');edit.append(node('summary','Correct relationship details'));const [rel,ri]=field('Relation',e.relation,'select');ri.replaceChildren(...relations.map(x=>option(x,x)));ri.value=e.relation;const [tm,ti]=field('Event date / ISO timestamp (blank if unknown)',e.occurred_at);const [pol,pi]=field('Statement type',e.polarity,'select');pi.replaceChildren(...['asserted','denied','uncertain'].map(x=>option(x,x)));pi.value=e.polarity;edit.append(rel,tm,pol,button('Save correction',async()=>{await api(base()+'/edges/'+e.id,{method:'PATCH',body:JSON.stringify({relation:ri.value,occurred_at:ti.value||null,polarity:pi.value,expected_revision:e.revision,reason:reason.value})});await refresh();box.replaceChildren(node('p','Correction saved as pending. Original source retained.'));}));box.append(edit);}
async function inspectLink(h){if(active!=='network')await showTab('network');const b=$('inspector');b.replaceChildren(node('p','POTENTIAL RELATIONSHIP','eyebrow'),node('h2',h.source_label+' ↔ '+h.target_label),node('span','HYPOTHESIS · REQUIRES REVIEW','badge hypothesis'),node('p',h.explanation,'subtle'));renderLeadReview(b,h);for(const p of h.paths||[]){b.append(node('p','Supporting path · '+label(p.via),'subtle'));for(const id of p.evidence||[]){const e=data.edges.find(e=>e.id===id);if(e)b.append(button(label(e.source)+' → '+label(e.target)+' · '+e.relation+' · '+(e.occurred_at||'Unknown time'),()=>inspectEdge(e)));}}}
async function loadLinks(){const selectedCase=caseId,result=data.edges.length>=2000?await queuedAnalysis('links'):await post(base()+'/hypotheses/compute?'+query(),{});if(selectedCase!==caseId)return;links=result;$('linkBadge').textContent=links.items.length;const target=$('linksContent');target.replaceChildren();if(!links.items.length)target.append(node('div',links.empty_reason||'No candidates in this window.','panel'));for(const h of links.items){const c=node('article',undefined,'panel link-card');c.append(node('span','POTENTIAL RELATIONSHIP','eyebrow'),node('h3',h.source_label+' ↔ '+h.target_label),node('p',h.explanation));const meta=node('div',undefined,'lead-meta');meta.append(node('span',(h.evidence_ids||[]).length+' evidence records'),node('span',(h.paths||[]).length+' supporting paths'));c.append(meta);const actions=node('div',undefined,'action-row');actions.append(button('Investigate lead →',()=>inspectLink(h)));c.append(actions);const detail=node('details');detail.append(node('summary','Technical details'),node('small','Structural score '+h.score+' / 100 · uncalibrated ranking · AA '+h.adamic_adar+' · Jaccard '+h.jaccard));c.append(detail);target.append(c);}if(links.truncated)target.append(node('p','Candidate budget reached. Narrow the view for more complete results.','warning'));draw();}
bind('findPath',async()=>{const p=query();p.set('source',$('pathFrom').value);p.set('target',$('pathTo').value);const d=await api(base()+'/path?'+p);$('pathResult').replaceChildren(node('p',d.path.length?d.path.map(label).join(' → '):'No accepted path in this view.'));for(const ids of d.evidence)for(const id of ids){const e=data.edges.find(e=>e.id===id);if(e)$('pathResult').append(button('Evidence '+id,()=>inspectEdge(e)));}});
function previewView(result){preview=result.bundle;$('previewPanel').hidden=false;$('previewTitle').textContent=result.format||'Editable draft';$('previewCounts').replaceChildren(...Object.entries(preview).map(([k,v])=>node('strong',v.length+' '+k)));$('previewWarnings').replaceChildren(...(result.warnings||[]).map(w=>node('p',w,'warning')));$('previewRows').replaceChildren(...preview.edges.slice(0,15).map(e=>{const r=node('div',undefined,'row');const name=id=>preview.entities.find(n=>n.id===id)?.label||label(id);r.append(node('div',`${name(e.source)} → ${name(e.target)} · ${e.relation}`),node('small',e.occurred_at||'Unknown event time'));return r;}));if(preview.edges.length>15)$('previewRows').append(node('p',`Preview shows 15 of ${preview.edges.length} relationships. Download JSON to inspect all.`,'subtle'));$('previewJson').value=JSON.stringify(preview,null,2);$('previewPanel').scrollIntoView({behavior:'smooth',block:'start'});}
bind('parseNote',async()=>{const d=await post(base()+'/convert',{text:$('noteText').value,format:'text',title:'Manual note',default_time:$('defaultTime').value?$('defaultTime').value+':00Z':null});previewView(d);});
$('file').onchange=()=>{$('fileName').textContent=$('file').files[0]?.name||'No file selected';};
bind('parseFile',async()=>{const f=$('file').files[0];if(!f)throw Error('Choose a file first');if(f.size>25*1048576)throw Error('File exceeds the default 25 MB limit. Split the input into smaller files.');const mapping={};for(const[k,id]of [['caller','callerColumn'],['callee','calleeColumn'],['timestamp','timeColumn']])if($(id).value)mapping[k]=$(id).value;previewView(await post(base()+'/convert',{text:await f.text(),format:$('format').value,title:f.name,timezone_offset:$('tz').value,column_map:mapping}));});
bind('downloadJson',async()=>{if(preview)download(preview,'converted-records.json');});
bind('applyJson',async()=>{const text=$('previewJson').value;previewView(await post(base()+'/convert',{text,format:'json',title:'Edited draft'}));});
bind('savePreview',async()=>{if(!preview)throw Error('Preview data first');const d=await post(base()+'/imports',preview);say('Import '+d.status+'. New claims need your confirmation.');await jobs();if(d.status==='queued')startPolling();else if(d.status==='completed')await refresh();});
async function jobs(){const d=await api(base()+'/jobs');$('jobs').replaceChildren(...d.map(j=>{const r=node('div',undefined,'row');r.append(node('div',j.id.slice(0,10)+' · '+j.status+(j.error?' — '+j.error:'')),node('small',j.created_at));if(j.status==='failed')r.append(button('Retry',async()=>{await post(base()+'/jobs/'+j.id+'/retry',{});startPolling();await jobs();}));return r;}));if(!d.length)$('jobs').append(node('p','No imports yet.','subtle'));return d;}
function startPolling(){clearInterval(poller);const caseAtStart=caseId;let ticks=0;poller=setInterval(async()=>{try{if(caseId!==caseAtStart){clearInterval(poller);return;}const d=await jobs();ticks++;if(!d.some(j=>j.status==='queued')){clearInterval(poller);await refresh();say('Import processing finished. Open Records to confirm pending claims.');}else if(ticks===15)say('Still queued? Make sure the worker window is running.');if(ticks>90)clearInterval(poller);}catch(e){clearInterval(poller);say(e.message);}},2000);}
bind('manualAdd',async()=>{const entities=[],fresh=(which)=>{const name=$('manual'+which+'Name').value.trim();if(name){const id='n-'+crypto.randomUUID();entities.push({id,label:name,kind:$('manual'+which+'Kind').value,attrs:{}});return id;}const id=$('manual'+which).value;if(!id)throw Error('Select an entity or enter a new name for both ends');return id;};const a=fresh('From'),b=fresh('To'),text=$('manualText').value.trim();if(!text)throw Error('Add supporting source text');const sid='s-'+crypto.randomUUID();previewView({format:'Manual relationship',bundle:{entities,sources:[{id:sid,title:'Manual source',text}],edges:[{id:'e-'+crypto.randomUUID(),source:a,target:b,relation:$('manualRelation').value,source_id:sid,excerpt:text,occurred_at:$('manualDate').value||null,polarity:$('manualPolarity').value}]},warnings:[]});});
async function loadRecords(){const d=await api(base()+'/records?offset='+recordOffset+'&limit=100&status='+$('recordStatus').value);records=d.items;$('recordPage').textContent=` ${d.total?recordOffset+1:0}–${recordOffset+d.items.length} / ${d.total} `;$('prevRecords').disabled=recordOffset===0;$('nextRecords').disabled=recordOffset+100>=d.total;$('recordRows').replaceChildren(...d.items.map(e=>{const r=node('div',undefined,'row'),v=node('div');v.append(node('strong',label(e.source)+' → '+label(e.target)),node('small',e.relation+' · '+(e.occurred_at||'Unknown event time')));r.append(v,node('span',e.status,'badge '+e.status),button('Inspect / edit',()=>inspectEdge(e)));return r;}));if(!d.total)$('recordRows').append(node('p','No records with this status.','subtle'));}
bind('prevRecords',async()=>{recordOffset=Math.max(0,recordOffset-100);await loadRecords();});bind('nextRecords',async()=>{recordOffset+=100;await loadRecords();});$('recordStatus').onchange=()=>run(async()=>{recordOffset=0;await loadRecords();});
bind('acceptVisible',async()=>{const pending=records.filter(e=>e.status==='pending');if(!pending.length)throw Error('No pending claims on this page');const reason=prompt(`Confirm ${pending.length} claims on this page. Enter your review reason (at least 5 characters).`);if(!reason)return;await post(base()+'/review-batch',{edges:pending.map(e=>({id:e.id,revision:e.revision})),decision:'accepted',reason});await refresh();await loadRecords();say('Claims confirmed; hidden links recomputed.');});
async function loadSources(reset){if(reset){sourceOffset=0;$('sourceRows').replaceChildren();}const d=await api(base()+'/sources?offset='+sourceOffset+'&limit=100');for(const s of d.items){const r=node('div',undefined,'row');r.append(node('div',s.title+' · '+s.id.slice(0,12)),button('Read source',async()=>{const full=await api(base()+'/sources/'+s.id);const pre=node('pre',full.text);modal(full.title,pre);}));$('sourceRows').append(r);}sourceOffset+=d.items.length;$('moreSources').disabled=d.items.length<100;}
bind('moreSources',()=>loadSources(false));bind('loadAudit',async()=>{const rows=await api(base()+'/audit');$('auditRows').replaceChildren(...rows.map(a=>{const r=node('div',undefined,'row');r.append(node('div',a.action+' · '+a.actor),node('small',a.created_at),button('Details',async()=>modal(a.action,node('pre',JSON.stringify(a.detail,null,2)))));return r;}));});
async function insights(){const d=await api(base()+'/analytics?'+query());const box=$('insightContent');box.replaceChildren();function card(title,items){const c=node('section',undefined,'panel');c.append(node('h3',title));if(!items.length)c.append(node('p','No patterns in this view.','subtle'));for(const text of items)c.append(node('p',text));box.append(c);}card('Structural position',d.centrality.slice(0,8).map(n=>`${label(n.id)} · degree ${n.degree} · betweenness ${n.betweenness}`));card('Communities',d.communities.map((g,i)=>`Group ${i+1}: ${g.map(label).join(', ')}`));card('Conflicting claims',d.conflicts.map(x=>x.reason+' · '+x.evidence.join(', ')));card('Call bursts',d.bursts.map(x=>`${label(x.source)} → ${label(x.target)}: ${x.count} calls on ${x.day}; ${x.ratio.toFixed(1)}× baseline. ${x.caveat}`));card('Recorded location overlap',(d.colocations?.pairs||[]).map(x=>`${label(x.left)} / ${label(x.right)} at ${label(x.location)} · ${x.minutes_apart} minutes apart. ${x.caveat}`));card('Missing-data sensitivity',[`Average top-five degree overlap after randomly removing 20% of edges: ${Math.round(d.sensitivity.mean_overlap*100)}%.`,d.sensitivity.caveat]);box.append(node('p',d.note,'subtle'));}
bind('export',async()=>download(await api(base()+'/report?'+query()),'evidence-weave-'+caseId+'.json'));

for(const kind of ['Person','Phone','Organization','Vehicle','Location','Event','Case','Transaction'])$('kindFilter').append(option(kind,kind));
for(const rel of relations)$('relationFilter').append(option(rel,rel));
$('kindFilter').onchange=draw;$('relationFilter').onchange=draw;
function nodeTools(box,n){
 box.append(node('p','Original member IDs: '+(n.members||[n.id]).join(', '),'subtle'));
 for(const hops of [1,2])box.append(button('Show '+hops+'-hop neighbors',async()=>{const selected=cy.getElementById(n.id);let group=selected;for(let i=0;i<hops;i++)group=group.union(group.closedNeighborhood());cy.elements().hide();group.show();cy.fit(group,40);}));
 box.append(button('Show connected component',async()=>{const component=cy.elements().components().find(c=>c.has(cy.getElementById(n.id)));if(component){cy.elements().hide();component.show();cy.fit(component,40);}}),button('Collapse to this entity',async()=>{cy.elements().hide();cy.getElementById(n.id).show();}));
 const related=data.edges.filter(e=>e.source===n.id||e.target===n.id);box.append(node('h3','Related records ('+related.length+')'));
 for(const e of related.slice(0,20))box.append(button(e.relation+' · '+(e.occurred_at||'Unknown time'),()=>inspectEdge(e)));
 if(related.length>20)box.append(node('p','First 20 shown. Use Records for all claims.'));
}
function renderLeadReview(box,h){
 box.append(node('h3','Why this connection?'));
 const signals=h.signals||{};const signalList=node('div',undefined,'signal-list');
 const pretty={common_neighbor:'Shared intermediaries',common_neighbors:'Shared intermediaries',typed_context:'Typed relationship context',temporal_proximity:'Temporal proximity',geographic_overlap:'Recorded location overlap',source_diversity:'Evidence diversity',entity_resolution:'Entity-resolution support',conflicting_claims:'Conflicting claims'};
 for(const [name,value] of Object.entries(signals)){const row=node('div',undefined,'signal-row');row.append(node('span',pretty[name]||name.replaceAll('_',' ')),node('strong',(value>=0?'+':'')+value));signalList.append(row);}box.append(signalList);
 const evidence=node('div',undefined,'evidence-summary');evidence.append(node('strong',(h.evidence_ids||[]).length+' evidence records'),node('span',(h.source_ids||[]).length+' source documents'));box.append(evidence);
 box.append(node('small',h.caveat||'Candidate relationship only; review the underlying evidence before acting.','subtle'));
 const inspect=node('div',undefined,'action-row');inspect.append(button('Inspect first entity',async()=>inspectNode(data.nodes.find(n=>n.id===h.source))),button('Inspect second entity',async()=>inspectNode(data.nodes.find(n=>n.id===h.target))));box.append(inspect);
 const review=node('div',undefined,'action-row review-actions');review.append(button('Worth following',async()=>{const reason=prompt('Reason for this lead decision (at least 5 characters)');if(!reason)return;await post(base()+'/hypotheses/'+h.id+'/review',{decision:'worth_following',reason,expected_revision:h.revision});await loadLinks();say('Lead decision saved.');}),button('Needs more evidence',async()=>{const reason=prompt('What evidence is still needed?');if(!reason)return;await post(base()+'/hypotheses/'+h.id+'/review',{decision:'needs_evidence',reason,expected_revision:h.revision});await loadLinks();say('Lead marked for more evidence.');}),button('Dismiss',async()=>{const reason=prompt('Reason for dismissing this lead (at least 5 characters)');if(!reason)return;await post(base()+'/hypotheses/'+h.id+'/review',{decision:'dismissed',reason,expected_revision:h.revision});await loadLinks();say('Lead dismissed.');}));box.append(review);
}
let identityState=null;
async function loadIdentity(){
 const d=data.nodes.length>=1000?await queuedAnalysis('identities'):await api(base()+'/identities');identityState=d;$('identityInfo').replaceChildren(node('p',`${d.compared_pairs} candidate pairs compared · ${d.items.length} shown${d.truncated?' · results bounded':''}. ${d.note}`,'subtle'));
 const box=$('identityContent');box.replaceChildren();
 for(const h of d.items){const card=node('article',undefined,'panel identity-card');
  const heading=node('div',undefined,'identity-heading');heading.append(node('span',h.category.replaceAll('_',' '),'badge'),node('h3',h.source_label+' ↔ '+h.target_label));card.append(heading);
  const pair=node('div',undefined,'identity-pair');pair.append(node('span',h.source),node('span','↔'),node('span',h.target));card.append(pair);
  const facts=node('div',undefined,'identity-facts');
  const nameFact=node('div',undefined,'fact');nameFact.append(node('span','Name similarity'),node('strong',h.name_similarity));facts.append(nameFact);
  const exact=node('div',undefined,'fact');exact.append(node('span','Exact identifiers'),node('strong',h.exact_identifiers.join(', ')||'None'));facts.append(exact);
  const context=node('div',undefined,'fact');context.append(node('span','Context matches'),node('strong',h.context_matches.join(', ')||'None'));facts.append(context);
  const conflict=node('div',undefined,'fact');conflict.append(node('span','Conflicts'),node('strong',h.conflicting_identifiers.join(', ')||'None'));facts.append(conflict);card.append(facts);
  const score=node('div',undefined,'identity-score');score.append(node('span','Match assessment'),node('strong',h.score+' / 100'));card.append(score);
  const actions=node('div',undefined,'action-row');actions.append(button('Merge identities',async()=>{const reason=prompt('Explain the identity decision (at least 5 characters)');if(!reason)return;await post(base()+'/identities/review',{source:h.source,target:h.target,decision:'merge',reason,fingerprint:d.fingerprint,expected_revision:d.revision});await refresh();await loadIdentity();say('Identity merged and graph refreshed.');},'primary'),button('Keep distinct',async()=>{const reason=prompt('Explain why these are distinct (at least 5 characters)');if(!reason)return;await post(base()+'/identities/review',{source:h.source,target:h.target,decision:'distinct',reason,fingerprint:d.fingerprint,expected_revision:d.revision});await loadIdentity();say('Identity pair marked distinct.');}));card.append(actions);box.append(card);}
 if(!d.items.length)box.append(node('p','No candidate duplicates found in the current view.','subtle'));
 $('identityHistory').replaceChildren(...d.history.map(h=>{const row=node('div',undefined,'row');row.append(node('p',`${h.source} → ${h.target} · ${h.decision}${h.active?'':' (undone)'} · ${h.reason}`));if(h.decision==='merge'&&h.active)row.append(button('Undo merge',async()=>{const reason=prompt('Reason for undo');if(!reason)return;await post(base()+'/identities/'+h.id+'/undo',{reason,expected_revision:d.revision});await refresh();await loadIdentity();}));return row;}));
}
bind('refreshIdentity',loadIdentity);
let timelineData=[],timelineCount=100,timelineDays=[];
function timelineRows(){const box=$('timelineRows');box.replaceChildren();for(const e of timelineData.slice(0,timelineCount)){const row=node('div',undefined,'row');row.append(node('div',`${e.occurred_at||'Unknown time'} · ${e.precision}
${label(e.source)} → ${label(e.target)} · ${e.relation}`),button('Evidence',()=>inspectEdge(e)));box.append(row);}$('moreTimeline').hidden=timelineCount>=timelineData.length;}
async function loadTimeline(){const [t,g]=await Promise.all([api(base()+'/timeline?'+query()),api(base()+'/geo?'+query())]);timelineData=t.events;timelineCount=100;timelineRows();timelineDays=[...new Set(t.events.filter(e=>e.occurred_at).map(e=>e.occurred_at.slice(0,10)))];$('timeSlider').max=Math.max(0,timelineDays.length-1);$('timeSlider').value=$('timeSlider').max;$('sliderDay').textContent=timelineDays.at(-1)||'No dated events';drawGeo(g);}
$('timeSlider').oninput=()=>{$('sliderDay').textContent=timelineDays[Number($('timeSlider').value)]||'No dated events';};
bind('applyTime',async()=>{const day=timelineDays[Number($('timeSlider').value)];if(!day)return;$('end').value=day;await refresh();await loadTimeline();say('Network and geographic view now include records through '+day);});
bind('clearTime',async()=>{$('start').value='';$('end').value='';await refresh();await loadTimeline();});
bind('moreTimeline',async()=>{timelineCount+=100;timelineRows();});bind('refreshTimeline',loadTimeline);
function drawGeo(result){const root=$('geoMap');root.replaceChildren();$('geoDetails').replaceChildren(node('p',result.note,'subtle'));const pts=result.points;if(!pts.length){$('geoDetails').append(node('p','No valid location coordinates in this view. Add latitude and longitude attributes to Location entities.'));return;}
 const xs=pts.map(p=>p.longitude),ys=pts.map(p=>p.latitude),xmin=Math.min(...xs)-.005,xmax=Math.max(...xs)+.005,ymin=Math.min(...ys)-.005,ymax=Math.max(...ys)+.005;
 const x=v=>45+(v-xmin)/(xmax-xmin)*500,y=v=>360-(v-ymin)/(ymax-ymin)*310;
 for(let i=0;i<=4;i++){const xv=xmin+(xmax-xmin)*i/4,yv=ymin+(ymax-ymin)*i/4;root.append(svg('line',{x1:x(xv),x2:x(xv),y1:30,y2:360,class:'geo-grid'}),svg('line',{x1:45,x2:545,y1:y(yv),y2:y(yv),class:'geo-grid'}));const tx=svg('text',{x:x(xv),y:390,'text-anchor':'middle'});tx.textContent=xv.toFixed(3)+'°';const ty=svg('text',{x:4,y:y(yv)});ty.textContent=yv.toFixed(3)+'°';root.append(tx,ty);}
 for(const p of pts){const c=svg('circle',{cx:x(p.longitude),cy:y(p.latitude),r:8,tabindex:0,role:'button','aria-label':p.label});const txt=svg('text',{x:x(p.longitude)+12,y:y(p.latitude)-10});txt.textContent=p.label;const select=()=>{$('geoDetails').replaceChildren(node('h3',p.label),node('p',`${p.latitude}, ${p.longitude}`),node('small',result.note),...p.records.map(e=>button((e.occurred_at||'Unknown time')+' · '+label(e.source),()=>inspectEdge(e))));};c.onclick=select;c.onkeydown=e=>{if(e.key==='Enter')select();};root.append(c,txt);}
}
async function loadBrief(){const d=await api(base()+'/brief'),b=$('briefContent');b.replaceChildren(node('p','CASE OVERVIEW','eyebrow'),node('h2',d.case.title),node('p','A focused path through identity review, network exploration, explainable leads and source evidence.','subtle'));const stats=node('div',undefined,'stats');for(const [k,v] of Object.entries(d.counts)){const card=node('div',undefined,'stat');card.append(node('span',k.replaceAll('_',' ')),node('strong',v));stats.append(card);}b.append(stats);const next=node('section',undefined,'panel workflow-card');next.append(node('p','INVESTIGATION FLOW','eyebrow'),node('h3','Resolve → Explore → Explain → Verify'),node('p','Start by consolidating possible duplicate identities. Then follow the resulting network, inspect a potential relationship, and finish with the underlying source record.','subtle'));const actions=node('div',undefined,'action-row');actions.append(button('1  Resolve identities',()=>showTab('identity')),button('2  Open network',()=>showTab('network')),button('3  Review leads',()=>showTab('links')),button('4  Open evidence',()=>showTab('records')));next.append(actions);b.append(next);const leads=node('section',undefined,'panel');leads.append(node('h3','Recent saved leads'));for(const h of d.leads){const a=button(`${h.snapshot.source_label} ↔ ${h.snapshot.target_label} · ${h.status} · ${h.created_at.slice(0,10)}`,async()=>{const scope=h.snapshot.scope;for(const k of ['start','end','focus'])$(k).value=scope[k]||'';await refresh();await inspectLink({...h.snapshot,id:h.id,revision:h.revision,status:h.status});});leads.append(a);}b.append(leads,node('div',undefined,'action-row'));const toolsBox=b.lastChild;toolsBox.append(button('Timeline & places',()=>showTab('timeline')),button('Add data',()=>showTab('input')),button('Insights',()=>showTab('insights')));}
bind('refreshBrief',loadBrief);
bind('htmlReport',async()=>{const r=await fetch('/api'+base()+'/report.html?'+query(),{headers:{Authorization:'Bearer '+token}});if(!r.ok)throw Error('Report could not be generated. Narrow the view and try again.');const url=URL.createObjectURL(await r.blob()),a=node('a');a.href=url;a.download='evidence-weave-report.html';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});

async function queuedAnalysis(operation){const originalCase=caseId,body={operation};for(const [k,v] of query())body[k]=v;const job=await post(base()+'/analysis-jobs',body);for(let i=0;i<120;i++){await new Promise(resolve=>setTimeout(resolve,1000));if(caseId!==originalCase)throw Error('Case changed; analysis continues in the worker.');const result=await api(base()+'/analysis-jobs/'+job.id);if(result.status==='completed')return result.result;if(result.status==='failed')throw Error(result.error);$('busy').textContent='Analysis queued · keep the worker running';}throw Error('Analysis is still queued. Check the worker window and recompute later.');}
