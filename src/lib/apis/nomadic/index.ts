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
		throw new Error(error?.detail ?? `Nomadic request failed (${response.status}).`);
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
