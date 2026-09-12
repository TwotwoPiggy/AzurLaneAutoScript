/* eslint-env node */

import {createRequire, builtinModules} from 'module';
import {join} from 'path';
import {fileURLToPath} from 'url';
import vue from '@vitejs/plugin-vue';

const require = createRequire(import.meta.url);
const {chrome} = require('../../electron-vendors.config.json');

const PACKAGE_ROOT = typeof __dirname !== 'undefined' ? __dirname : fileURLToPath(new URL('.', import.meta.url));

/**
 * @type {import('vite').UserConfig}
 * @see https://vitejs.dev/config/
 */
const config = {
  mode: process.env.MODE,
  root: PACKAGE_ROOT,
  resolve: {
    alias: {
      '/@/': join(PACKAGE_ROOT, 'src') + '/',
    },
  },
  plugins: [vue()],
  base: '',
  server: {
    fs: {
      strict: true,
    },
  },
  build: {
    sourcemap: true,
    target: `chrome${chrome}`,
    outDir: 'dist',
    assetsDir: '.',
    terserOptions: {
      ecma: 2020,
      compress: {
        passes: 2,
      },
      safari10: false,
    },
    rollupOptions: {
      external: [
        ...builtinModules,
      ],
    },
    emptyOutDir: true,
    brotliSize: false,
  },
};

export default config;
