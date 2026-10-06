import assert from 'node:assert/strict';
import fs from 'node:fs';
import { normalizeOpenWebUIBasePath } from './open-webui-base-path.mjs';

assert.equal(normalizeOpenWebUIBasePath(''), '');
assert.equal(normalizeOpenWebUIBasePath('/'), '');
assert.equal(normalizeOpenWebUIBasePath(' /web '), '/web');
for (const invalid of ['web', '/web/', '/web?x=1', '/web#x', '/a/../b', '/a/./b'])
	assert.throws(() => normalizeOpenWebUIBasePath(invalid));

const read = (path) => fs.readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
assert.match(read('src/lib/constants.ts'), /import \{ base \} from '\$app\/paths'/);
assert.match(read('src/lib/constants.ts'), /WEBUI_BASE_URL = base/);
assert.match(read('svelte.config.js'), /paths: \{ base: openWebUIBasePath \}/);
assert.match(read('svelte.config.js'), /fallback: 'index\.html'/);
for (const route of ['/api', '/ws', '/oauth', '/openai', '/ollama'])
	assert.ok(read('vite.config.ts').includes(`backendRoute('${route}')`));
assert.match(read('vite.config.ts'), /rewrite: stripBasePath/);
const layout = read('src/routes/+layout.svelte');
assert.ok(layout.includes('io(undefined, {'), 'Socket.IO must connect to the default namespace');
assert.ok(
	layout.includes('path: `${WEBUI_BASE_URL}/ws/socket.io`'),
	'Socket.IO transport must keep its base path'
);
const chat = read('src/lib/components/chat/Chat.svelte');
for (const id of ['res.chat_id', '_chatId']) {
	assert.ok(
		chat.includes('`${WEBUI_BASE_URL}/c/${' + id + '}`'),
		'new chats must keep the configured base path'
	);
}
assert.ok(
	!/replaceState\(window\.history\.state, '', `\/(?:c\/|`)/.test(chat),
	'chat navigation must keep its base path'
);
assert.match(read('src/lib/utils/index.ts'), /pdfWorkerUrl/);
const preview = read('src/lib/components/chat/FileNav/FilePreview.svelte');
for (const viewer of ['PdfPagesPreview', 'DocxPreview', 'isMarkdown'])
	assert.ok(preview.includes(viewer));
const dockerfile = read('Dockerfile');
assert.match(dockerfile, /ARG OPEN_WEBUI_BASE_PATH=\/web/);
assert.match(dockerfile, /OPEN_WEBUI_BASE_PATH=\$\{OPEN_WEBUI_BASE_PATH\}/);
assert.match(read('.github/workflows/docker.yaml'), /OPEN_WEBUI_BASE_PATH=\/web/);
console.log(
	'Open WebUI /web API, WebSocket, OAuth, workers, previews, and nested-route contracts: ok'
);
