import hmac
from fastapi import Request, Depends, HTTPException
from .models import Case


def session(request: Request):
    with request.app.state.factory() as db:
        yield db


def owner(request: Request):
    token = request.headers.get('authorization', '').removeprefix('Bearer ')
    if not hmac.compare_digest(token, request.app.state.owner_token):
        raise HTTPException(401, 'Enter the workspace access key from secrets/users.json')
    return {'name': 'Workspace owner'}


def access(case_id: str, user=Depends(owner), db=Depends(session)):
    if not db.get(Case, case_id):
        raise HTTPException(404, 'Case not found')
    return user


def serial(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns} if hasattr(obj, '__table__') else vars(obj)
