<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { v4 as uuidv4 } from 'uuid';
	import { createNewChat, deleteChatById } from '$lib/apis/chats';
	import {
		createNomadicChat,
		getNomadicSessions,
		renameNomadicSession,
		reorderNomadicSessions,
		resumeNomadicChat,
		type NomadicChat,
		type NomadicSession
	} from '$lib/apis/nomadic';

	let projectPath = '';
	let sessions: NomadicSession[] = [];
	let loading = false;
	let action = '';
	let error = '';
	let chatName = 'New chat';
	let resumeId = '';
	let targetSessionId = '';
	let draggingSessionId = '';
	let holdTimer: ReturnType<typeof setTimeout> | null = null;
	let pointerStart = { x: 0, y: 0 };

	const load = async () => {
		const path = projectPath.trim();
		if (!path) return;
		loading = true;
		error = '';
		try {
			const result = await getNomadicSessions(localStorage.token, path);
			sessions = [...(result.sessions ?? [])].sort((a, b) => a.order - b.order);
			if (!sessions.some((session) => session.id === targetSessionId)) {
				targetSessionId = sessions[0]?.id ?? '';
			}
			localStorage.setItem('nomadic.workspace.projectPath', path);
		} catch (cause) {
			sessions = [];
			error = cause instanceof Error ? cause.message : 'Nomadic workspace could not be loaded.';
		} finally {
			loading = false;
		}
	};

	const makeNativeChat = async (mode: 'create' | 'resume') => {
		const name = chatName.trim();
		if (!name || !targetSessionId || !projectPath.trim()) return;
		if (mode === 'resume' && !resumeId.trim()) {
			error = 'Enter the Codex conversation UUID to resume.';
			return;
		}

		action = mode;
		error = '';
		let nativeChatId = '';
		try {
			const draftId = uuidv4();
			const saved = await createNewChat(
				localStorage.token,
				{
					id: draftId,
					title: name,
					models: [],
					params: {},
					history: { messages: {}, currentId: null },
					messages: [],
					tags: [],
					timestamp: Date.now()
				},
				null
			);
			nativeChatId = saved.id;
			const payload = {
				open_webui_chat_id: nativeChatId,
				project_path: projectPath.trim(),
				session_id: targetSessionId,
				name,
				...(mode === 'resume' ? { resume_id: resumeId.trim() } : {}),
				idempotency_key: uuidv4()
			};
			const binding =
				mode === 'resume'
					? await resumeNomadicChat(localStorage.token, payload)
					: await createNomadicChat(localStorage.token, payload);
			localStorage.setItem(`nomadic.workspace.chat.${binding.chat_id}`, nativeChatId);
			await goto(`/c/${nativeChatId}`);
		} catch (cause) {
			if (nativeChatId) await deleteChatById(localStorage.token, nativeChatId).catch(() => null);
			error = cause instanceof Error ? cause.message : `Could not ${mode} the chat.`;
		} finally {
			action = '';
		}
	};

	const renameSession = async (session: NomadicSession) => {
		const name = window.prompt('Session name', session.name)?.trim();
		if (!name || name === session.name) return;
		action = `rename:${session.id}`;
		error = '';
		try {
			await renameNomadicSession(localStorage.token, session.id, projectPath.trim(), name);
			await load();
		} catch (cause) {
			error = cause instanceof Error ? cause.message : 'Could not rename the session.';
		} finally {
			action = '';
		}
	};

	const openChat = async (chat: NomadicChat) => {
		const nativeChatId = localStorage.getItem(`nomadic.workspace.chat.${chat.id}`);
		if (nativeChatId) await goto(`/c/${nativeChatId}`);
		else error = 'This chat has no Open WebUI binding on this browser yet.';
	};

	const clearHold = () => {
		if (holdTimer) clearTimeout(holdTimer);
		holdTimer = null;
	};

	const pointerDown = (event: PointerEvent, sessionId: string) => {
		clearHold();
		pointerStart = { x: event.clientX, y: event.clientY };
		holdTimer = setTimeout(() => {
			draggingSessionId = sessionId;
			(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
		}, 350);
	};

	const pointerMove = (event: PointerEvent) => {
		if (
			!draggingSessionId &&
			Math.hypot(event.clientX - pointerStart.x, event.clientY - pointerStart.y) > 8
		) {
			clearHold();
		}
		if (draggingSessionId) event.preventDefault();
	};

	const pointerUp = async (event: PointerEvent) => {
		clearHold();
		if (!draggingSessionId) return;
		const sourceId = draggingSessionId;
		draggingSessionId = '';
		const target = document
			.elementFromPoint(event.clientX, event.clientY)
			?.closest<HTMLElement>('[data-session-id]')?.dataset.sessionId;
		if (!target || target === sourceId) return;

		const reordered = [...sessions];
		const from = reordered.findIndex((session) => session.id === sourceId);
		const to = reordered.findIndex((session) => session.id === target);
		if (from < 0 || to < 0) return;
		const [moved] = reordered.splice(from, 1);
		reordered.splice(to, 0, moved);
		sessions = reordered;
		action = 'reorder';
		error = '';
		try {
			await reorderNomadicSessions(
				localStorage.token,
				projectPath.trim(),
				reordered.map((session) => session.id)
			);
			await load();
		} catch (cause) {
			error = cause instanceof Error ? cause.message : 'Could not save the session order.';
			await load();
		} finally {
			action = '';
		}
	};

	onMount(() => {
		projectPath = localStorage.getItem('nomadic.workspace.projectPath') ?? '';
		if (projectPath) load();
	});
</script>

<svelte:head><title>Nomadic Workspace</title></svelte:head>

<div class="mx-auto flex w-full max-w-6xl flex-col gap-5 px-1 py-4 sm:px-3">
	<header>
		<p class="text-xs font-medium uppercase tracking-[0.14em] text-gray-500 dark:text-gray-400">
			Coding workspace
		</p>
		<h1 class="text-2xl font-semibold text-gray-900 dark:text-gray-50">Nomadic</h1>
		<p class="mt-1 max-w-2xl text-sm leading-6 text-gray-600 dark:text-gray-300">
			Manage Codex sessions here. Bound conversations open in the native Open WebUI chat.
		</p>
	</header>

	<form class="flex flex-col gap-2 sm:flex-row" on:submit|preventDefault={load}>
		<label class="sr-only" for="nomadic-project-path">Absolute project path</label>
		<input
			id="nomadic-project-path"
			class="min-w-0 flex-1 rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900"
			bind:value={projectPath}
			placeholder="/absolute/path/to/project"
			autocomplete="off"
			spellcheck="false"
		/>
		<button
			type="submit"
			disabled={loading || !projectPath.trim()}
			class="rounded-xl bg-gray-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-gray-100 dark:text-gray-900"
			>{loading ? 'Loading…' : 'Load project'}</button
		>
	</form>

	{#if error}<div
			class="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/30 dark:text-red-200"
			role="alert"
		>
			{error}
		</div>{/if}

	{#if sessions.length > 0}
		<section
			class="grid gap-3 rounded-2xl border border-gray-200 p-4 dark:border-gray-800 sm:grid-cols-2 lg:grid-cols-4"
		>
			<div class="sm:col-span-2 lg:col-span-1">
				<label class="mb-1 block text-xs text-gray-500" for="nomadic-chat-name">Chat name</label>
				<input
					id="nomadic-chat-name"
					class="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900"
					bind:value={chatName}
				/>
			</div>
			<div>
				<label class="mb-1 block text-xs text-gray-500" for="nomadic-session">Session</label>
				<select
					id="nomadic-session"
					class="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900"
					bind:value={targetSessionId}
					>{#each sessions as session}<option value={session.id}>{session.name}</option
						>{/each}</select
				>
			</div>
			<div>
				<label class="mb-1 block text-xs text-gray-500" for="nomadic-resume-id"
					>Codex UUID to resume</label
				>
				<input
					id="nomadic-resume-id"
					class="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900"
					bind:value={resumeId}
					placeholder="Optional for new chat"
				/>
			</div>
			<div class="flex items-end gap-2">
				<button
					class="flex-1 rounded-lg bg-gray-900 px-3 py-2 text-sm text-white disabled:opacity-50 dark:bg-gray-100 dark:text-gray-900"
					disabled={!!action || !chatName.trim()}
					on:click={() => makeNativeChat('create')}
					>{action === 'create' ? 'Creating…' : 'New chat'}</button
				>
				<button
					class="flex-1 rounded-lg border border-gray-200 px-3 py-2 text-sm disabled:opacity-50 dark:border-gray-700"
					disabled={!!action || !chatName.trim() || !resumeId.trim()}
					on:click={() => makeNativeChat('resume')}
					>{action === 'resume' ? 'Resuming…' : 'Resume'}</button
				>
			</div>
		</section>

		<p class="text-xs text-gray-500 dark:text-gray-400">
			Hold the grip, then drag onto another card to reorder sessions.
		</p>
		<div class="grid gap-3 md:grid-cols-2">
			{#each sessions as session (session.id)}
				<section
					data-session-id={session.id}
					class="overflow-hidden rounded-2xl border bg-white transition dark:bg-gray-950 {draggingSessionId ===
					session.id
						? 'border-blue-500 opacity-70'
						: 'border-gray-200 dark:border-gray-800'}"
				>
					<div
						class="flex items-center gap-2 border-b border-gray-100 px-4 py-3 dark:border-gray-800"
					>
						<button
							aria-label={`Hold and drag ${session.name}`}
							class="cursor-grab touch-none select-none px-1 text-lg text-gray-400 active:cursor-grabbing"
							on:pointerdown={(event) => pointerDown(event, session.id)}
							on:pointermove={pointerMove}
							on:pointerup={pointerUp}
							on:pointercancel={() => {
								clearHold();
								draggingSessionId = '';
							}}>⠿</button
						>
						<div class="min-w-0 flex-1">
							<h2 class="truncate text-sm font-semibold">{session.name}</h2>
							<p class="text-xs text-gray-500">
								{session.chats.length}
								{session.chats.length === 1 ? 'chat' : 'chats'}
							</p>
						</div>
						<button
							disabled={!!action}
							class="rounded-lg px-2 py-1 text-xs hover:bg-gray-100 disabled:opacity-50 dark:hover:bg-gray-800"
							on:click={() => renameSession(session)}
							>{action === `rename:${session.id}` ? 'Saving…' : 'Rename'}</button
						>
					</div>
					<div class="divide-y divide-gray-100 dark:divide-gray-800">
						{#each session.chats as chat (chat.id)}
							<button
								class="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-gray-900"
								on:click={() => openChat(chat)}
							>
								<span
									class="size-2 shrink-0 rounded-full {chat.state === 'working'
										? 'bg-amber-500'
										: 'bg-emerald-500'}"
								></span>
								<span class="min-w-0 flex-1"
									><span class="block truncate text-sm">{chat.name}</span><span
										class="block text-xs capitalize text-gray-500">{chat.state}</span
									></span
								>
								<span class="text-gray-400">›</span>
							</button>
						{/each}
					</div>
				</section>
			{/each}
		</div>
	{:else if !loading && projectPath.trim() && !error}
		<div
			class="rounded-2xl border border-dashed border-gray-200 px-5 py-10 text-center dark:border-gray-700"
		>
			<p class="text-sm font-medium">No managed sessions found</p>
			<p class="mt-1 text-sm text-gray-500">
				Create the first managed session with the Nomadic CLI, then reload this project.
			</p>
		</div>
	{:else if !projectPath.trim()}
		<div
			class="rounded-2xl border border-dashed border-gray-200 px-5 py-10 text-center dark:border-gray-700"
		>
			<p class="text-sm font-medium">Choose a project</p>
			<p class="mt-1 text-sm text-gray-500">
				Enter the absolute path configured on the Nomadic host.
			</p>
		</div>
	{/if}
</div>
