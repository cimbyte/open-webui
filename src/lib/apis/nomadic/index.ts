import { WEBUI_API_BASE_URL } from '$lib/constants';

export type NomadicChat = {
	id: string;
	name: string;
	window_id: string;
	codex_session_id?: string;
	state: string;
};

export type NomadicSession = {
	id: string;
	name: string;
	order: number;
	chats: NomadicChat[];
};

export type NomadicSessionsResponse = { sessions: NomadicSession[] };

export type NomadicBinding = {
	user_id: string;
	open_webui_chat_id: string;
	project_path: string;
	session_id: string;
	chat_id: string;
};

export type NomadicCreateChat = {
	open_webui_chat_id: string;
	project_path: string;
	project_name?: string;
	codex_command?: string;
	session_id?: string;
	name: string;
	resume_id?: string;
	idempotency_key: string;
};

const request = async <T>(token: string, path: string, init: RequestInit = {}): Promise<T> => {
	const response = await fetch(`${WEBUI_API_BASE_URL}/nomadic${path}`, {
		...init,
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`,
			...init.headers
		}
	});

	if (!response.ok) {
		const error = await response.json().catch(() => null);
		throw new Error(
			error?.detail ?? error?.error ?? `Nomadic request failed (${response.status}).`
		);
	}
	return response.json();
};

export const getNomadicSessions = (token: string, projectPath: string) =>
	request<NomadicSessionsResponse>(
		token,
		`/sessions?project_path=${encodeURIComponent(projectPath)}`
	);

export const createNomadicChat = (token: string, payload: NomadicCreateChat) =>
	request<NomadicBinding>(token, '/chats/create', {
		method: 'POST',
		body: JSON.stringify(payload)
	});

export const resumeNomadicChat = (token: string, payload: NomadicCreateChat) =>
	request<NomadicBinding>(token, '/chats/resume', {
		method: 'POST',
		body: JSON.stringify(payload)
	});

export const renameNomadicSession = (
	token: string,
	sessionId: string,
	projectPath: string,
	name: string
) =>
	request(token, `/sessions/${encodeURIComponent(sessionId)}/rename`, {
		method: 'POST',
		body: JSON.stringify({
			project_path: projectPath,
			name,
			idempotency_key: crypto.randomUUID()
		})
	});

export const reorderNomadicSessions = (token: string, projectPath: string, sessionIds: string[]) =>
	request(token, '/sessions/reorder', {
		method: 'POST',
		body: JSON.stringify({
			project_path: projectPath,
			session_ids: sessionIds,
			idempotency_key: crypto.randomUUID()
		})
	});

export const getNomadicBinding = (token: string, openWebUIChatId: string) =>
	request<NomadicBinding>(token, `/bindings/${encodeURIComponent(openWebUIChatId)}`);

export const promptNomadicChat = (
	token: string,
	chatId: string,
	projectPath: string,
	text: string
) =>
	request(token, `/chats/${encodeURIComponent(chatId)}/prompt`, {
		method: 'POST',
		body: JSON.stringify({
			project_path: projectPath,
			text,
			idempotency_key: crypto.randomUUID()
		})
	});

export const interruptNomadicChat = (token: string, chatId: string, projectPath: string) =>
	request(token, `/chats/${encodeURIComponent(chatId)}/interrupt`, {
		method: 'POST',
		body: JSON.stringify({
			project_path: projectPath,
			idempotency_key: crypto.randomUUID()
		})
	});

export const nomadicEventsUrl = (chatId: string, projectPath: string, after = 0) =>
	`${WEBUI_API_BASE_URL}/nomadic/chats/${encodeURIComponent(chatId)}/events?project_path=${encodeURIComponent(projectPath)}&after=${after}`;

export const syncNomadicView = (
	token: string,
	workspace: { project_path: string; all_sessions: boolean }
) =>
	request<{ chats: Record<string, string>; sessions: number }>(token, '/view/sync', {
		method: 'POST',
		body: JSON.stringify(workspace)
	});

export const loadNomadicView = (token: string, chatId: string) =>
	request<{ linked: boolean; chat_id?: string; can_prompt?: boolean }>(
		token,
		`/view/${encodeURIComponent(chatId)}`,
		{
			method: 'POST'
		}
	);
