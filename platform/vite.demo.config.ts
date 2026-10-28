import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';

// The platform's 3D view for demo.glyphh.ai's plain pages (src/demo/glyph-view.ts): one ES module, three.js inside,
// served at /voice/3d/glyph-view.js (server/voice.ts).
export default defineConfig({
  // A library build keeps process.env.NODE_ENV for its user to set; this one runs as it is in the browser.
  define: { 'process.env.NODE_ENV': JSON.stringify('production') },
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  build: {
    outDir: 'dist/demo',
    emptyOutDir: true,
    minify: true,
    lib: { entry: 'src/demo/glyph-view.ts', formats: ['es'], fileName: () => 'glyph-view.js' },
  },
});
