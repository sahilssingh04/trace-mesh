"""Application assembly only; routes and services live in separate modules."""
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from .models import Base, database
from .middleware import BodyLimit
from .routes import workspace, imports, graph, intelligence


def create_app(db_url=None, credentials=None):
    engine, factory = database(db_url)
    if credentials is None:
        try: credentials = json.loads(Path(os.getenv('AUTH_FILE', 'secrets/users.json')).read_text())
        except (OSError, ValueError): raise RuntimeError('Run python scripts/bootstrap.py first')
    # One owner. Old deployments choose the reviewer/admin key, never promote all old keys.
    candidates = [(k,v) for k,v in credentials.items() if v.get('role') in ('owner','admin','reviewer')]
    if not candidates: candidates = list(credentials.items())[:1]
    if not candidates or len(candidates[0][0]) < 24: raise RuntimeError('Invalid owner credential')
    @asynccontextmanager
    async def lifespan(app):
        Base.metadata.create_all(engine)
        yield
        engine.dispose()
    app = FastAPI(title='Evidence Weave', version='3.0.0', lifespan=lifespan)
    app.state.factory, app.state.owner_token = factory, candidates[0][0]
    app.add_middleware(BodyLimit)
    @app.exception_handler(RequestValidationError)
    async def validation(request, exc):
        errors = [{'field': '.'.join(map(str,e['loc'])), 'message': e['msg']} for e in exc.errors()[:20]]
        return JSONResponse({'detail':'Some fields need correction.', 'errors':errors}, 422)
    @app.middleware('http')
    async def headers(request: Request, call_next):
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'"
        return response
    for router in (workspace.router, imports.router, graph.router, intelligence.router): app.include_router(router)
    static = Path(__file__).parent / 'static'
    app.mount('/static', StaticFiles(directory=static), name='static')
    @app.get('/')
    def index(): return FileResponse(static/'index.html')
    @app.get('/health')
    def health():
        from sqlalchemy import text
        with engine.connect() as c: c.execute(text('SELECT 1'))
        return {'status':'ok', 'version':'3.0.0'}
    return app
