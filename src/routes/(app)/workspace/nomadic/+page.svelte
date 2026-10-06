<script lang="ts">
	import { onMount } from 'svelte';
	import { base } from '$app/paths';
	import { syncNomadicView } from '$lib/apis/nomadic';

	let view: 'nomadic' | 'openwebui' = 'nomadic';
	let frame: HTMLIFrameElement;
	let source = `${base}/chats`;
	let loaded = false;
	let busy = false;
	let error = '';
	let preferenceKey = '';
	let selectedChat = '';
	let chats: Record<string, string> = {};

	const workspace = async () => {
		const response = await fetch('/gateway/v1/workspace');
		const value = await response.json();
		if (!response.ok) throw new Error(value.error ?? 'Could not load your workspace.');
		return value;
	};

	const rememberSelection = () => {
		try {
			const path = frame?.contentWindow?.location.pathname ?? '';
			const match = path.match(/\/(chats|c)\/([^/]+)$/);
			if (!match) return;
			const id = decodeURIComponent(match[2]);
			const nativeId =
				match[1] === 'chats' ? id : Object.keys(chats).find((key) => chats[key] === id);
			if (nativeId) {
				selectedChat = nativeId;
				if (preferenceKey) localStorage.setItem(`${preferenceKey}.chat`, nativeId);
			}
		} catch {
			/* The frame may be navigating. */
		}
	};

	const switchView = async (next: 'nomadic' | 'openwebui') => {
		if (busy || (next === view && loaded)) return;
		rememberSelection();
		busy = true;
		error = '';
		try {
			if (next === 'openwebui') {
				const context = await workspace();
				const inventory = await syncNomadicView(localStorage.token, context);
				chats = inventory.chats;
				source = chats[selectedChat] ? `${base}/c/${chats[selectedChat]}` : `${base}/`;
			} else {
				source = selectedChat
					? `${base}/chats/${encodeURIComponent(selectedChat)}`
					: `${base}/chats`;
			}
			loaded = false;
			view = next;
			if (preferenceKey) localStorage.setItem(preferenceKey, next);
		} catch (cause) {
			error = cause instanceof Error ? cause.message : 'Could not switch views.';
		} finally {
			busy = false;
		}
	};

	onMount(() => {
		if (window.parent !== window) {
			window.parent.postMessage({ type: 'nomadic-view', view: 'nomadic' }, window.location.origin);
			return;
		}
		let cancelled = false;
		workspace()
			.then((context) => {
				if (cancelled) return;
				preferenceKey = `nomadic.workspace.view.${context.email}`;
				selectedChat = localStorage.getItem(`${preferenceKey}.chat`) ?? '';
				if (localStorage.getItem(preferenceKey) === 'openwebui') void switchView('openwebui');
			})
			.catch(() => {
				/* Nomadic handles sign-in and project selection. */
			});
		const timer = setInterval(rememberSelection, 500);
		const message = (event: MessageEvent) => {
			if (
				event.origin === window.location.origin &&
				event.source === frame?.contentWindow &&
				event.data?.type === 'nomadic-view'
			) {
				void switchView('nomadic');
			}
		};
		window.addEventListener('message', message);
		return () => {
			cancelled = true;
			clearInterval(timer);
			window.removeEventListener('message', message);
		};
	});
</script>

<svelte:head><title>Nomadic / Open WebUI</title></svelte:head>

<div class="flex h-full min-h-0 w-full flex-col">
	<header
		class="flex shrink-0 items-center justify-between gap-2 border-b border-gray-200 px-3 py-2 dark:border-gray-800"
	>
		<span class="text-sm font-semibold">Session view</span>
		<div
			class="flex rounded-lg bg-gray-100 p-1 dark:bg-gray-850"
			role="group"
			aria-label="Session view"
		>
			{#each ['nomadic', 'openwebui'] as option}
				<button
					type="button"
					aria-pressed={view === option}
					disabled={busy}
					class="rounded-md px-3 py-1 text-sm disabled:opacity-50 {view === option
						? 'bg-white font-semibold shadow-sm dark:bg-gray-700'
						: 'text-gray-600 dark:text-gray-300'}"
					on:click={() => switchView(option as 'nomadic' | 'openwebui')}
				>
					{option === 'nomadic' ? 'Nomadic' : 'Open WebUI'}
				</button>
			{/each}
		</div>
	</header>
	{#if error}<p class="shrink-0 px-3 py-2 text-sm text-red-600 dark:text-red-400" role="alert">
			{error}
		</p>{/if}
	<div class="relative min-h-0 flex-1">
		{#if !loaded || busy}
			<p
				class="pointer-events-none absolute inset-x-0 top-4 z-10 text-center text-sm text-gray-500"
				role="status"
			>
				{busy ? 'Opening Open WebUI sessions…' : 'Opening sessions…'}
			</p>
		{/if}
		{#key source}
			<iframe
				bind:this={frame}
				title={view === 'nomadic' ? 'Nomadic workspace' : 'Open WebUI workspace'}
				src={source}
				class="absolute inset-0 h-full w-full border-0"
				on:load={() => (loaded = true)}
			></iframe>
		{/key}
	</div>
</div>
