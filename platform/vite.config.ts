import { fileURLToPath, URL } from 'node:url';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  build: { outDir: 'dist/client', emptyOutDir: true },
  css: { modules: { localsConvention: 'camelCaseOnly' } },
  test: {
    globals: true,
    projects: [
      {
        extends: true,
        test: { name: 'server', environment: 'node', include: ['server/**/*.test.ts'] },
      },
      {
        extends: true,
        test: {
          name: 'ui',
          environment: 'jsdom',
          include: ['src/**/*.test.tsx', 'src/**/*.test.ts'],
          setupFiles: ['src/test/setup.ts'],
          css: { modules: { classNameStrategy: 'non-scoped' } },
        },
      },
    ],
  },
});
