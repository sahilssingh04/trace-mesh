"""Run from repository root. Creates random local credentials, never overwrites them."""
import json
import os
import secrets
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.models import Base, Case, database

p = Path(os.getenv('AUTH_FILE', 'secrets/users.json'))
p.parent.mkdir(parents=True, exist_ok=True)
if not p.exists():
    users = {secrets.token_urlsafe(32): {'name': 'Workspace owner', 'role': 'owner'}}
    p.write_text(json.dumps(users, indent=2));p.chmod(0o600)
    print('Created one workspace owner key in secrets/users.json.')
else:
    users=json.loads(p.read_text())
    chosen=next((k for k,v in users.items() if v.get('role') in ('owner','admin','reviewer')),next(iter(users)))
    if len(users)!=1 or users[chosen].get('role')!='owner':
        backup=p.with_name('users.v1-backup.json')
        if not backup.exists(): backup.write_text(p.read_text());backup.chmod(0o600)
        p.write_text(json.dumps({chosen:{'name':'Workspace owner','role':'owner'}},indent=2));p.chmod(0o600)
        print('Migrated to one owner key. Old viewer/analyst keys are disabled.')
    else: print('Keeping existing owner key.')
engine, factory = database()
Base.metadata.create_all(engine)
print('Database ready. Run scripts/seed_demo.py or create a case through the UI.')
