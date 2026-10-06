<script lang="ts">
	import { page } from '$app/stores';
	import Chat from '$lib/components/chat/Chat.svelte';
	import { loadNomadicView } from '$lib/apis/nomadic';
	import { toast } from 'svelte-sonner';
	let prepared = '';
	let canPrompt = true;
	let preparing = '';
	$: if ($page.params.id && $page.params.id !== preparing) {
		const id = $page.params.id;
		preparing = id;
		prepared = '';
		canPrompt = true;
		loadNomadicView(localStorage.token, id)
			.then((result) => {
				if (preparing === id) canPrompt = result.can_prompt !== false;
			})
			.catch((error) => toast.error(error.message))
			.finally(() => {
				if (preparing === id) prepared = id;
			});
	}
</script>

{#if prepared === $page.params.id}
	<Chat chatIdProp={$page.params.id} nomadicCanPrompt={canPrompt} />
{/if}
