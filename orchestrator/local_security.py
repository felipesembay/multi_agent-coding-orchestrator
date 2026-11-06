"""Browser write protection. Not authentication against other local processes."""
import os
import ipaddress
import secrets
from urllib.parse import urlsplit

from fastapi import Request
from starlette.responses import JSONResponse

CSRF_TOKEN = secrets.token_urlsafe(32)


def local_host(value):
    try:
        parsed = urlsplit('http://' + value)
        return parsed.hostname in ('localhost', '127.0.0.1', '::1') and not parsed.username and not parsed.password and parsed.path == '' and parsed.query == '' and parsed.fragment == '' and (parsed.port is None or 1 <= parsed.port <= 65535)
    except ValueError:
        return False


def allowed_origins():
    configured = os.getenv('ORCH_ALLOWED_ORIGINS')
    return {value.strip() for value in configured.split(',') if value.strip()} if configured else {
        'http://127.0.0.1:5173', 'http://localhost:5173',
        'http://127.0.0.1:8765', 'http://localhost:8765',
    }


async def protect_project_routes(request: Request, call_next):
    path = request.url.path
    protected = path == '/session' or path == '/project-policy' or path == '/projects' or path.startswith('/projects/')
    if not protected:
        return await call_next(request)
    try:
        peer_is_local = request.client is not None and ipaddress.ip_address(request.client.host).is_loopback
    except ValueError:
        peer_is_local = False
    if not peer_is_local:
        return JSONResponse({'detail': 'Esta API aceita operações de projetos somente pela interface local.'}, status_code=403)
    origin = request.headers.get('origin')
    if not local_host(request.headers.get('host', '')):
        return JSONResponse({'detail': 'Host não autorizado. Use a API em localhost.'}, status_code=403)
    if request.headers.get('sec-fetch-site') == 'cross-site' or (origin is not None and origin not in allowed_origins()):
        return JSONResponse({'detail': 'Origin não autorizado.'}, status_code=403)
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        if not origin or origin not in allowed_origins():
            return JSONResponse({'detail': 'Origin obrigatório para operações de escrita.'}, status_code=403)
        token = request.headers.get('x-orchestrator-csrf', '')
        if not token.isascii() or not secrets.compare_digest(token, CSRF_TOKEN):
            return JSONResponse({'detail': 'Sessão inválida. Atualize a página e tente novamente.'}, status_code=403)
        if request.headers.get('content-type', '').split(';')[0].strip() != 'application/json':
            return JSONResponse({'detail': 'Use application/json.'}, status_code=415)
        # Bound input before Pydantic parses it, including chunked request bodies.
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 150_000:
                return JSONResponse({'detail': 'Solicitação excede 150 kB.'}, status_code=413)
        request._body = bytes(body)
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Cross-Origin-Resource-Policy'] = 'same-origin'
    return response
