"""Local HTTP boundary for every route. Not isolation from the same OS user."""
import ipaddress
import os
import re
import secrets

from fastapi import Request
from starlette.responses import JSONResponse

CSRF_TOKEN = secrets.token_urlsafe(32)
# Native supervisor may provide app.state.api_token in memory. Never sent by /session.
API_TOKEN = secrets.token_urlsafe(32)
MAX_BODY_BYTES = 150_000
SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')


def local_host(value):
    match = re.fullmatch(r'(localhost|127\.0\.0\.1|\[::1\])(?::([0-9]{1,5}))?', value, re.I)
    return bool(match and (match[2] is None or 1 <= int(match[2]) <= 65535))


def allowed_origins():
    configured = os.getenv('ORCH_ALLOWED_ORIGINS')
    return {value.strip() for value in configured.split(',') if value.strip()} if configured else {
        'http://127.0.0.1:5173', 'http://localhost:5173',
        'http://127.0.0.1:8765', 'http://localhost:8765',
    }


def _matches(value, expected):
    return (isinstance(expected, str) and bool(expected) and expected.isascii()
            and bool(value) and len(value) <= 512 and value.isascii()
            and secrets.compare_digest(value, expected))


def _reject(detail, status=403):
    return JSONResponse({'detail': detail}, status_code=status)


async def _protect(request: Request, call_next):
    try:
        peer_is_local = request.client is not None and ipaddress.ip_address(request.client.host).is_loopback
    except ValueError:
        peer_is_local = False
    if not peer_is_local:
        return _reject('Esta API aceita operações somente pela interface local.')
    hosts = request.headers.getlist('host')
    if len(hosts) != 1 or not local_host(hosts[0]):
        return _reject('Host não autorizado. Use a API em localhost.')
    origins = request.headers.getlist('origin')
    if (len(origins) > 1 or request.headers.get('sec-fetch-site') == 'cross-site'
            or (origins and origins[0] not in allowed_origins())):
        return _reject('Origin não autorizado.')
    origin = origins[0] if origins else None
    # Only the browser bootstrap and liveness check are token-free reads.
    bootstrap = request.scope['path'] in ('/session', '/health') and request.method in ('GET', 'HEAD')
    native = False
    if not bootstrap:
        authorizations = request.headers.getlist('authorization')
        csrf_values = request.headers.getlist('x-orchestrator-csrf')
        if len(authorizations) > 1 or len(csrf_values) > 1:
            return _reject('Sessão inválida. Atualize a página e tente novamente.')
        if authorizations:
            scheme, separator, token = authorizations[0].partition(' ')
            expected = getattr(request.app.state, 'api_token', API_TOKEN)
            native = bool(separator and scheme.lower() == 'bearer' and _matches(token, expected))
            if not native:
                return _reject('Sessão inválida. Atualize a página e tente novamente.')
        elif not _matches(csrf_values[0] if csrf_values else '', CSRF_TOKEN):
            return _reject('Sessão inválida. Atualize a página e tente novamente.')
    if request.method not in SAFE_METHODS:
        if not native and (not origin or origin not in allowed_origins()):
            return _reject('Origin obrigatório para operações de escrita.')
        if request.headers.get('content-type', '').split(';')[0].strip() != 'application/json':
            return _reject('Use application/json.', 415)
    # Bound actual bytes, including GET bodies and chunked requests; never trust Content-Length.
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_BODY_BYTES:
            return _reject('Solicitação excede 150 kB.', 413)
    request._body = bytes(body)
    return await call_next(request)


async def protect_routes(request: Request, call_next):
    response = await _protect(request, call_next)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Cross-Origin-Resource-Policy'] = 'same-origin'
    return response


# Compatibility import for existing callers; policy now covers every route.
protect_project_routes = protect_routes
