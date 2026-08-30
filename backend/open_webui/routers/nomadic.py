import os
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
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
