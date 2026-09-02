import os
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from open_webui.utils.auth import get_verified_user
from pydantic import BaseModel, ConfigDict

router = APIRouter()

_BRIDGE_TIMEOUT = httpx.Timeout(15.0, connect=5.0)


class BridgePayload(BaseModel):
    model_config = ConfigDict(extra='allow')


def _bridge_config() -> tuple[str, str]:
    base_url = os.getenv('NOMADIC_BRIDGE_URL', '').strip().rstrip('/')
    token = os.getenv('NOMADIC_BRIDGE_TOKEN', '').strip()
    parsed = urlsplit(base_url)
    if (
        parsed.scheme not in {'http', 'https'}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or len(token) < 32
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Nomadic workspace is not configured.',
        )
    return base_url, token


async def _bridge_request(method: str, path: str, user_id: str, payload: dict | None = None) -> Response:
    base_url, token = _bridge_config()
    headers = {
        'Authorization': f'Bearer {token}',
        'X-User-Id': user_id,
        'Accept': 'application/json',
    }
    try:
        async with httpx.AsyncClient(timeout=_BRIDGE_TIMEOUT, follow_redirects=False, trust_env=False) as client:
            bridge_response = await client.request(
                method,
                f'{base_url}{path}',
                headers=headers,
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail='Nomadic bridge is unavailable.',
        ) from exc

    content_type = bridge_response.headers.get('content-type', 'application/json').split(';', 1)[0]
    if content_type != 'application/json':
        content_type = 'text/plain'
    return Response(
        content=bridge_response.content,
        status_code=bridge_response.status_code,
        media_type=content_type,
        headers={'Cache-Control': 'no-store'},
    )


@router.get('/sessions')
async def sessions(
    project_path: str = Query(min_length=1, max_length=4096),
    user=Depends(get_verified_user),
):
    query = httpx.QueryParams({'project_path': project_path})
    return await _bridge_request('GET', f'/v1/sessions?{query}', user.id)


@router.post('/chats/create')
async def create_chat(payload: BridgePayload, user=Depends(get_verified_user)):
    body = payload.model_dump()
    body['user_id'] = user.id
    return await _bridge_request('POST', '/v1/chats/create', user.id, body)


@router.post('/chats/resume')
async def resume_chat(payload: BridgePayload, user=Depends(get_verified_user)):
    body = payload.model_dump()
    body['user_id'] = user.id
    return await _bridge_request('POST', '/v1/chats/resume', user.id, body)


@router.post('/sessions/{session_id}/rename')
async def rename_session(
    session_id: UUID,
    payload: BridgePayload,
    user=Depends(get_verified_user),
):
    return await _bridge_request(
        'POST',
        f'/v1/sessions/{session_id}/rename',
        user.id,
        payload.model_dump(),
    )


@router.post('/sessions/reorder')
async def reorder_sessions(payload: BridgePayload, user=Depends(get_verified_user)):
    return await _bridge_request('POST', '/v1/sessions/reorder', user.id, payload.model_dump())


@router.get('/bindings/{chat_id}')
async def binding(chat_id: UUID, user=Depends(get_verified_user)):
    return await _bridge_request('GET', f'/v1/bindings/{chat_id}', user.id)


@router.post('/chats/{chat_id}/prompt')
async def prompt(chat_id: UUID, payload: BridgePayload, user=Depends(get_verified_user)):
    return await _bridge_request(
        'POST', f'/v1/chats/{chat_id}/prompt', user.id, payload.model_dump()
    )


@router.post('/chats/{chat_id}/interrupt')
async def interrupt(chat_id: UUID, payload: BridgePayload, user=Depends(get_verified_user)):
    return await _bridge_request(
        'POST', f'/v1/chats/{chat_id}/interrupt', user.id, payload.model_dump()
    )


@router.get('/chats/{chat_id}/events')
async def events(
    chat_id: UUID,
    project_path: str = Query(min_length=1, max_length=4096),
    after: int = Query(default=0, ge=0),
    user=Depends(get_verified_user),
):
    base_url, token = _bridge_config()
    query = httpx.QueryParams({'project_path': project_path, 'after': str(after)})
    headers = {
        'Authorization': f'Bearer {token}',
        'X-User-Id': user.id,
        'Accept': 'text/event-stream',
    }

    async def stream():
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(None, connect=5.0), follow_redirects=False, trust_env=False
            ) as client:
                async with client.stream(
                    'GET', f'{base_url}/v1/chats/{chat_id}/events?{query}', headers=headers
                ) as bridge_response:
                    if bridge_response.status_code != status.HTTP_200_OK:
                        body = await bridge_response.aread()
                        yield b'event: error\ndata: ' + body.replace(b'\n', b' ') + b'\n\n'
                        return
                    async for chunk in bridge_response.aiter_bytes():
                        yield chunk
        except httpx.HTTPError:
            yield b'event: error\ndata: Nomadic bridge is unavailable.\n\n'

    return StreamingResponse(
        stream(),
        media_type='text/event-stream',
        headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'},
    )
