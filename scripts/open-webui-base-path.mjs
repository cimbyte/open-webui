export function normalizeOpenWebUIBasePath(value = '') {
	const trimmed = value.trim();
	if (!trimmed || trimmed === '/') return '';
	if (!trimmed.startsWith('/') || trimmed.endsWith('/') || trimmed.includes('?') || trimmed.includes('#')) throw new Error('OPEN_WEBUI_BASE_PATH must be empty or an absolute path without a trailing slash, query, or fragment');
	if (trimmed.split('/').some((segment) => segment === '.' || segment === '..')) throw new Error('OPEN_WEBUI_BASE_PATH cannot contain dot segments');
	return trimmed;
}
export const openWebUIBasePath = normalizeOpenWebUIBasePath(process.env.OPEN_WEBUI_BASE_PATH ?? '');
