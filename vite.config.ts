import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

import { viteStaticCopy } from 'vite-plugin-static-copy';
import { openWebUIBasePath } from './scripts/open-webui-base-path.mjs';

const backendTarget = process.env.WEBUI_BACKEND_URL || 'http://localhost:8080';
const backendRoute = (path: string) => `${openWebUIBasePath}${path}`;
const stripBasePath = (path: string) => openWebUIBasePath && path.startsWith(openWebUIBasePath) ? path.slice(openWebUIBasePath.length) || '/' : path;

export default defineConfig({
	plugins: [
		sveltekit(),
		viteStaticCopy({
			targets: [
				{
					src: 'node_modules/onnxruntime-web/dist/*.jsep.*',

					dest: 'wasm'
				}
			]
		})
	],
	define: {
		APP_VERSION: JSON.stringify(process.env.npm_package_version),
		APP_BUILD_HASH: JSON.stringify(process.env.APP_BUILD_HASH || 'dev-build')
	},
	build: {
		sourcemap: true
	},
	server: {
		proxy: {
			[backendRoute('/api')]: {
				target: backendTarget,
				changeOrigin: true,
				rewrite: stripBasePath,
				ws: true
			},
			[backendRoute('/ollama')]: {
				target: backendTarget,
				changeOrigin: true, rewrite: stripBasePath
			},
			[backendRoute('/openai')]: {
				target: backendTarget,
				changeOrigin: true, rewrite: stripBasePath
			},
			[backendRoute('/oauth')]: {
				target: backendTarget,
				changeOrigin: true, rewrite: stripBasePath
			},
			[backendRoute('/ws')]: {
				target: backendTarget,
				changeOrigin: true,
				rewrite: stripBasePath,
				ws: true
			}
		}
	},
	worker: {
		format: 'es'
	},
	esbuild: {
		pure: process.env.ENV === 'dev' ? [] : ['console.log', 'console.debug', 'console.error']
	}
});
