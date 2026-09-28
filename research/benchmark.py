"""Reproducible synthetic temporal link benchmark; not field validation.
Run: python research/benchmark.py [--gnn]
Requires requirements-research.txt for --gnn; never loaded by the application.
"""
import argparse,json,math,time,hashlib
from pathlib import Path
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score,roc_auc_score,precision_recall_fscore_support
import networkx as nx

def metrics(y,score):
    y=np.array(y);score=np.array(score);k=min(20,len(score));order=np.argsort(-score,kind='stable')
    return {'roc_auc':float(roc_auc_score(y,score)),'average_precision':float(average_precision_score(y,score)),'precision_at_20':float(y[order[:k]].mean()),'positives':int(sum(y)),'negatives':int(len(y)-sum(y))}

def fixture(seed,n=100):
    rng=np.random.default_rng(seed);group=np.arange(n)%5
    # Static noisy attributes exist before the observation window; hidden group is not an input label.
    x=(np.eye(5)[group]+rng.normal(0,.7,(n,5))).astype('float32')
    pairs=[]
    for a in range(n):
        for b in range(a+1,n):
            if rng.random()<(.35 if group[a]==group[b] else .015):pairs.append((a,b))
    rng.shuffle(pairs)
    return x,pairs

def split_data(seed):
    x,events=fixture(seed);n=len(x);l=len(events);bounds=[int(l*f) for f in [.4,.6,.8]]
    warm=events[:bounds[0]];parts=[events[bounds[0]:bounds[1]],events[bounds[1]:bounds[2]],events[bounds[2]:]]
    g=nx.Graph();g.add_nodes_from(range(n));g.add_edges_from(warm)
    rng=np.random.default_rng(seed+1000);seen=set(warm);datasets=[]
    for positives in parts:
        # Only observations available up to this split's end censor negative examples.
        # Future positives may appear among earlier negatives: an explicit temporal-label limitation.
        seen.update(positives);pool=[(a,b) for a in range(n) for b in range(a+1,n) if (a,b) not in seen]
        neg=[pool[i] for i in rng.choice(len(pool),len(positives),replace=False)]
        pairs=positives+neg;y=np.array([1]*len(positives)+[0]*len(neg))
        order=rng.permutation(len(pairs));datasets.append(([pairs[i] for i in order],y[order]))
    return x,g,datasets,events,bounds

def features(g,pairs):
    result=[]
    for a,b in pairs:
        na,nb=set(g[a]),set(g[b]);common=na&nb
        result.append([len(common),len(common)/max(1,len(na|nb)),sum(1/math.log(g.degree(c)) for c in common if g.degree(c)>1),g.degree(a),g.degree(b)])
    return np.asarray(result,dtype='float32')

def gnn_scores(x,g,datasets,seed):
    import torch
    from torch import nn
    torch.manual_seed(seed);torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    X=torch.from_numpy(x);adj=torch.zeros((len(x),len(x)))
    for a,b in g.edges:adj[a,b]=adj[b,a]=1
    adj=adj/adj.sum(1,keepdim=True).clamp(min=1)
    class SAGE(nn.Module):
        def __init__(self):
            super().__init__();self.first=nn.Linear(10,24);self.second=nn.Linear(48,16);self.head=nn.Sequential(nn.Linear(32,16),nn.ReLU(),nn.Linear(16,1))
        def forward(self,pairs):
            h=torch.relu(self.first(torch.cat((X,adj@X),1)))
            h=self.second(torch.cat((h,adj@h),1));a,b=pairs[:,0],pairs[:,1]
            return self.head(torch.cat((h[a]*h[b],torch.abs(h[a]-h[b])),1)).squeeze(1)
    model=SAGE();opt=torch.optim.Adam(model.parameters(),lr=.01,weight_decay=.001)
    tensors=[(torch.tensor(p,dtype=torch.long),torch.tensor(y,dtype=torch.float32)) for p,y in datasets]
    best=-1;checkpoint=None;epoch_chosen=0
    for epoch in range(60):
        model.train();opt.zero_grad();loss=nn.functional.binary_cross_entropy_with_logits(model(tensors[0][0]),tensors[0][1]);loss.backward();opt.step()
        model.eval()
        with torch.no_grad():val=model(tensors[1][0]).sigmoid().numpy()
        ap=average_precision_score(datasets[1][1],val)
        if ap>best:best=ap;checkpoint={k:v.detach().clone() for k,v in model.state_dict().items()};epoch_chosen=epoch+1
    model.load_state_dict(checkpoint);model.eval()
    with torch.no_grad():scores=model(tensors[2][0]).sigmoid().numpy()
    out=Path(__file__).resolve().parents[1]/'verification'/'research';out.mkdir(exist_ok=True)
    torch.save({'state_dict':checkpoint,'seed':seed,'epoch':epoch_chosen,'architecture':'two mean GraphSAGE layers + symmetric pair MLP','input_features':5},out/f'graphsage-seed-{seed}.pt')
    return scores,epoch_chosen

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--gnn',action='store_true',help='Enable isolated real PyTorch research pipeline');args=parser.parse_args()
    rows=[];started=time.perf_counter()
    for seed in [11,23,37,41,59]:
        x,g,sets,events,bounds=split_data(seed);f=[features(g,p) for p,y in sets];y=sets[2][1]
        # Warmup graph is fixed: no train-target, validation or test edge enters message passing or structural features.
        assert not set(g.edges)&set(events[bounds[0]:])
        scores={name:f[2][:,i] for i,name in enumerate(['common_neighbors','jaccard','adamic_adar'])}
        best=None;best_ap=-1
        for C in [.1,1,10]:
            model=LogisticRegression(C=C,random_state=seed,max_iter=1000).fit(f[0],sets[0][1]);ap=average_precision_score(sets[1][1],model.predict_proba(f[1])[:,1])
            if ap>best_ap:best=model;best_ap=ap
        scores['logistic_regression']=best.predict_proba(f[2])[:,1]
        epoch=None
        if args.gnn:scores['graphsage'],epoch=gnn_scores(x,g,sets,seed)
        rows.append({'seed':seed,'context_edges':g.number_of_edges(),'ordered_event_count':len(events),'split_boundaries':bounds,'dataset_sha256':hashlib.sha256(json.dumps(events).encode()).hexdigest(),'selected_gnn_epoch':epoch,'metrics':{k:metrics(y,v) for k,v in scores.items()}})
    names=list(rows[0]['metrics']);summary={name:{metric:{'mean':float(np.mean([r['metrics'][name][metric] for r in rows])),'std':float(np.std([r['metrics'][name][metric] for r in rows]))} for metric in ['roc_auc','average_precision','precision_at_20']} for name in names}
    output={'dataset':'synthetic temporal community links; 100 nodes; static noisy attributes','protocol':'40% warmup graph, 20% train targets, 20% validation, 20% test. All methods share fixed warmup topology and same sampled test pairs. Negative sampling uses only observations through current split. No claims of inductive held-out-node evaluation.','limitations':['Synthetic communities are not investigative evidence.','Balanced sampled negatives inflate usefulness relative to sparse real networks.','Chronological index is simulated, not field timestamps.','Future observations may relabel earlier temporal negatives.','GNN has static attributes in addition to structure; comparison is not feature-equivalent.','No calibrated confidence or field accuracy claim.'],'gnn_enabled':args.gnn,'runtime_seconds':time.perf_counter()-started,'runs':rows,'summary':summary}
    dest=Path(__file__).resolve().parents[1]/'verification'/'research-benchmark.json';dest.write_text(json.dumps(output,indent=2));print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
