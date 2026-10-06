import { redirect } from '@sveltejs/kit';
import { base } from '$app/paths';
import { browser } from '$app/environment';

export const load = () => {
	if (browser && window.parent !== window) return {};
	redirect(307, `${base}/workspace/nomadic`);
};
