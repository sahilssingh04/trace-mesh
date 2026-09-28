import json
import os
import secrets
from pathlib import Path
p=Path('.env')
if not p.exists():
    uid=os.getuid() if hasattr(os,'getuid') else 10001
    gid=os.getgid() if hasattr(os,'getgid') else 10001
    p.write_text(f'DB_PASSWORD={secrets.token_hex(24)}\nLOCAL_UID={uid}\nLOCAL_GID={gid}\n')
    p.chmod(0o600)
d=Path('secrets');d.mkdir(exist_ok=True)
p=d/'users.json'
if not p.exists():
    p.write_text(json.dumps({secrets.token_urlsafe(32):{'name':'Demo Reviewer','role':'reviewer','cases':['DEMO']}},indent=2))
    p.chmod(0o600)
print('Docker configuration ready. Run docker compose up --build -d')
