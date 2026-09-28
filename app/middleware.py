from fastapi.responses import JSONResponse
from .config import MAX_UPLOAD_BYTES


class BodyLimit:
    def __init__(self, app): self.app = app
    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http': return await self.app(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect': return
            chunks.append(message)
            size += len(message.get('body', b''))
            if size > MAX_UPLOAD_BYTES:
                return await JSONResponse({'detail': f'Upload exceeds {MAX_UPLOAD_BYTES // 1048576} MB. Split the file or change MAX_UPLOAD_MB and restart.'}, 413)(scope, receive, send)
            if not message.get('more_body'): break
        async def replay(): return chunks.pop(0) if chunks else await receive()
        await self.app(scope, replay, send)
