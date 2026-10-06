import asyncio
import json
import os
import time
from urllib.parse import urlsplit
from uuid import UUID, NAMESPACE_URL, uuid5

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from open_webui.internal.db import get_async_db_context, get_async_session
from open_webui.models.chats import Chat, ChatForm, Chats
from open_webui.models.folders import FolderForm, Folders
from open_webui.utils.auth import get_verified_user
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, ConfigDict

router = APIRouter()

_sync_lock = asyncio.Lock()

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
    return await _bridge_request('POST', f'/v1/chats/{chat_id}/prompt', user.id, payload.model_dump())


@router.post('/chats/{chat_id}/interrupt')
async def interrupt(chat_id: UUID, payload: BridgePayload, user=Depends(get_verified_user)):
    return await _bridge_request('POST', f'/v1/chats/{chat_id}/interrupt', user.id, payload.model_dump())


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


async def _bridge_json(method: str, path: str, user_id: str, payload: dict | None = None):
    response = await _bridge_request(method, path, user_id, payload)
    value = json.loads(response.body)
    if response.status_code >= 400:
        raise HTTPException(response.status_code, value.get('error', 'Nomadic bridge request failed.'))
    return value


class WorkspaceView(BaseModel):
    project_path: str
    all_sessions: bool = False


@router.post('/view/sync')
async def sync_view(
    payload: WorkspaceView,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    query = httpx.QueryParams({'project_path': payload.project_path, 'all_sessions': str(payload.all_sessions).lower()})
    inventory = await _bridge_json('GET', f'/v1/sessions?{query}', user.id)
    mapping = {}
    # Imports create presentation records only. Tmux sessions and windows are untouched.
    async with _sync_lock:
        folders = await Folders.get_folders_by_user_id(user.id, db=db)
        by_session = {(folder.meta or {}).get('nomadic_session_id'): folder for folder in folders}
        async with get_async_db_context(db) as session_db:
            existing_rows = (await session_db.execute(select(Chat.id, Chat.meta).where(Chat.user_id == user.id))).all()
        by_chat = {((meta or {}).get('nomadic') or {}).get('chat_id'): chat_id for chat_id, meta in existing_rows}
        for session in inventory['sessions'] or []:
            folder = by_session.get(session['id'])
            if folder is None:
                folder = await Folders.insert_new_folder(
                    user.id,
                    FolderForm(name=session['name'], meta={'nomadic_session_id': session['id']}),
                    db=db,
                )
                if folder is None:
                    raise HTTPException(500, 'Could not create the session folder.')
                by_session[session['id']] = folder
            for item in session['chats'] or []:
                chat_id = by_chat.get(item['id']) or str(uuid5(NAMESPACE_URL, f'nomadic:{user.id}:{item["id"]}'))
                mapping[item['id']] = chat_id
                existing = await Chats.get_chat_by_id_and_user_id(chat_id, user.id, db=db)
                if existing is not None:
                    continue
                binding = {
                    'user_id': user.id,
                    'open_webui_chat_id': chat_id,
                    'project_path': payload.project_path,
                    'all_sessions': payload.all_sessions,
                    'session_id': session['id'],
                    'chat_id': item['id'],
                }
                await Chats.insert_new_chat(
                    chat_id,
                    user.id,
                    ChatForm(
                        folder_id=folder.id,
                        chat={
                            'title': item['name'],
                            'models': ['nomadic_codex'],
                            'history': {'messages': {}, 'currentId': None},
                            'messages': [],
                        },
                    ),
                    internal_meta={'nomadic': binding},
                    db=db,
                )
    return {'chats': mapping, 'sessions': len(inventory['sessions'] or [])}


@router.post('/view/{chat_id}')
async def load_view(
    chat_id: UUID,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    chat = await Chats.get_chat_by_id_and_user_id(str(chat_id), user.id, db=db)
    if chat is None:
        raise HTTPException(404, 'Chat not found.')
    binding = (chat.meta or {}).get('nomadic')
    if not binding:
        return {'linked': False}
    await _bridge_json('POST', '/v1/bindings', user.id, binding)
    query = httpx.QueryParams(
        {
            'project_path': binding['project_path'],
            'all_sessions': str(binding.get('all_sessions', False)).lower(),
        }
    )
    snapshot = await _bridge_json('GET', f'/v1/chats/{binding["chat_id"]}/snapshot?{query}', user.id)
    history = chat.chat.get('history') or {}
    message_id = str(uuid5(UUID(str(chat_id)), 'terminal-snapshot'))
    messages = history.get('messages') or {}
    # Refresh our sole snapshot. Preserve authored messages, edits and branch history.
    snapshot_only = len(messages) == 1 and message_id in messages and 'originalContent' not in messages[message_id]
    if not messages or snapshot_only:
        terminal = snapshot['transcript'].replace('```', '` ` `').strip()
        message = {
            'id': message_id,
            'parentId': None,
            'childrenIds': [],
            'role': 'assistant',
            'model': 'nomadic_codex',
            'modelName': 'Nomadic Codex',
            'content': 'Current session transcript\n\n```text\n' + terminal + '\n```',
            'timestamp': int(time.time()),
            'done': True,
        }
        await Chats.update_chat_by_id(
            str(chat_id),
            {'history': {'messages': {message_id: message}, 'currentId': message_id}, 'messages': [message]},
            db=db,
            touch=False,
        )
    return {'linked': True, 'chat_id': binding['chat_id'], 'can_prompt': snapshot['state'] != 'stopped'}
