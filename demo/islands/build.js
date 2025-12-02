/**
 * Build script for Svelte islands
 * Compiles .svelte files to JS modules in ../static/islands/
 */
import * as esbuild from 'esbuild';
import sveltePlugin from 'esbuild-svelte';
import { readdirSync } from 'fs';
import { join, basename } from 'path';

const isWatch = process.argv.includes('--watch');

// Find all .svelte files
const svelteFiles = readdirSync('.')
  .filter(f => f.endsWith('.svelte'))
  .map(f => `./${f}`);

console.log('Building Svelte islands:', svelteFiles);

const buildOptions = {
  entryPoints: svelteFiles,
  bundle: true,
  outdir: '../static/islands',
  format: 'esm',
  splitting: true,
  minify: !isWatch,
  sourcemap: isWatch,
  plugins: [
    sveltePlugin({
      compilerOptions: {
        css: 'injected',
      },
    }),
  ],
  logLevel: 'info',
};

if (isWatch) {
  const ctx = await esbuild.context(buildOptions);
  await ctx.watch();
  console.log('Watching for changes...');
} else {
  await esbuild.build(buildOptions);
  console.log('Build complete!');
}

