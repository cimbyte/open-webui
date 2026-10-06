<script lang="ts">
	let loaded = false;
</script>

<svelte:head><title>Nomadic Workspace</title></svelte:head>

<div class="relative h-full min-h-[32rem] w-full overflow-hidden rounded-xl">
	{#if !loaded}
		<p class="absolute inset-x-0 top-6 text-center text-sm text-gray-500" role="status">
			Opening Nomadic…
		</p>
	{/if}
	<iframe
		title="Nomadic projects and chats"
		src="/web/chats"
		class="h-full min-h-[32rem] w-full border-0"
		on:load={() => (loaded = true)}
	></iframe>
</div>
