<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { page } from '$app/stores';
	import {
		getNomadicBinding,
		interruptNomadicChat,
		nomadicEventsUrl,
		promptNomadicChat,
		type NomadicBinding
	} from '$lib/apis/nomadic';

	let binding: NomadicBinding | null = null;
	let transcript = '';
	let state = 'connecting';
	let message = '';
	let error = '';
	let sending = false;
	let controller: AbortController | null = null;
	let transcriptElement: HTMLPreElement;

	const followTranscript = async () => {
		await Promise.resolve();
		if (transcriptElement) transcriptElement.scrollTop = transcriptElement.scrollHeight;
	};

	const connect = async () => {
		if (!binding) return;
		controller?.abort();
		controller = new AbortController();
		try {
			const response = await fetch(nomadicEventsUrl(binding.chat_id, binding.project_path), {
				headers: { authorization: `Bearer ${localStorage.token}`, Accept: 'text/event-stream' },
				signal: controller.signal
			});
			if (!response.ok || !response.body) throw new Error(`Transcript stream failed (${response.status}).`);
			const reader = response.body.getReader();
			const decoder = new TextDecoder();
			let buffer = '';
			while (true) {
				const { value, done } = await reader.read();
				if (done) break;
				buffer += decoder.decode(value, { stream: true });
				const events = buffer.split('\n\n');
				buffer = events.pop() ?? '';
				for (const event of events) {
					const data = event
						.split('\n')
						.filter((line) => line.startsWith('data:'))
						.map((line) => line.slice(5).trimStart())
						.join('\n');
					if (!data) continue;
					try {
						const update = JSON.parse(data);
						transcript = update.transcript ?? transcript;
						state = update.state ?? state;
						followTranscript();
					} catch {
						error = data;
					}
				}
			}
		} catch (cause) {
			if (!controller?.signal.aborted) {
				error = cause instanceof Error ? cause.message : 'Transcript stream disconnected.';
			}
		}
	};

	const send = async () => {
		const text = message.trim();
		if (!binding || !text || sending) return;
		sending = true;
		error = '';
		try {
			await promptNomadicChat(localStorage.token, binding.chat_id, binding.project_path, text);
			message = '';
		} catch (cause) {
			error = cause instanceof Error ? cause.message : 'Message could not be sent.';
		} finally {
			sending = false;
		}
	};

	const interrupt = async () => {
		if (!binding) return;
		try {
			await interruptNomadicChat(localStorage.token, binding.chat_id, binding.project_path);
		} catch (cause) {
			error = cause instanceof Error ? cause.message : 'Session could not be interrupted.';
		}
	};

	onMount(async () => {
		try {
			const openWebUIChatId = $page.params.id;
			if (!openWebUIChatId) throw new Error('Chat identity is missing.');
			binding = await getNomadicBinding(localStorage.token, openWebUIChatId);
			await connect();
		} catch (cause) {
			error = cause instanceof Error ? cause.message : 'This Nomadic chat could not be restored.';
		}
	});

	onDestroy(() => controller?.abort());
</script>

<svelte:head><title>Nomadic Chat</title></svelte:head>

<div class="mx-auto flex h-[calc(100dvh-4rem)] w-full max-w-5xl flex-col px-2 pb-3 sm:px-5">
	<header class="flex items-center justify-between border-b border-gray-100 py-3 dark:border-gray-850">
		<div>
			<h1 class="text-sm font-semibold text-gray-900 dark:text-gray-100">Codex session</h1>
			<p class="text-xs text-gray-500">{state}</p>
		</div>
		<button
			class="rounded-lg border border-gray-200 px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
			on:click={interrupt}>Stop</button
		>
	</header>

	{#if error}<div class="mt-3 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-200" role="alert">{error}</div>{/if}

	<pre
		bind:this={transcriptElement}
		class="min-h-0 flex-1 overflow-auto whitespace-pre-wrap break-words px-2 py-5 font-sans text-[15px] leading-7 text-gray-800 dark:text-gray-200"
		>{transcript || 'Connecting to the Codex session…'}</pre
	>

	<form class="rounded-3xl border border-gray-200 bg-white p-2 shadow-sm dark:border-gray-700 dark:bg-gray-900" on:submit|preventDefault={send}>
		<textarea
			bind:value={message}
			rows="2"
			placeholder="Message Codex…"
			class="max-h-44 w-full resize-none bg-transparent px-3 py-2 text-sm outline-none placeholder:text-gray-400"
			on:keydown={(event) => {
				if (event.key === 'Enter' && !event.shiftKey) {
					event.preventDefault();
					send();
				}
			}}
		></textarea>
		<div class="flex justify-end">
			<button
				type="submit"
				disabled={sending || !message.trim() || !binding}
				class="rounded-full bg-gray-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40 dark:bg-gray-100 dark:text-gray-900"
				>{sending ? 'Sending…' : 'Send'}</button
			>
		</div>
	</form>
</div>
