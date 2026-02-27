import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

export default defineConfig({
  base: './',
  plugins: [svelte()],
  envPrefix: 'APP_',
  server: {
    proxy: {
      '/v1': {
        target: 'http://localhost:8000/',
      },
    },
  },
})
