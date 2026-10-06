<script lang="ts">
	import { page } from '$app/stores';
	import Chat from '$lib/components/chat/Chat.svelte';
	import { loadNomadicView } from '$lib/apis/nomadic';
	import { toast } from 'svelte-sonner';
	let prepared = '';
	let preparing = '';
	$: if ($page.params.id && $page.params.id !== preparing) {
		const id = $page.params.id;
		preparing = id;
		prepared = '';
		loadNomadicView(localStorage.token, id)
			.catch((error) => toast.error(error.message))
			.finally(() => {
				if (preparing === id) prepared = id;
			});
	}
</script>

{#if prepared === $page.params.id}
	<Chat chatIdProp={$page.params.id} />
{/if}
