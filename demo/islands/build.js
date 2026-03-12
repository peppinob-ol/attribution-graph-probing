/**
 * Build script for Svelte islands
 * Compiles init.js (which imports all Svelte components) to a single bundle
 */
import * as esbuild from 'esbuild';
import sveltePlugin from 'esbuild-svelte';

const isWatch = process.argv.includes('--watch');

console.log('Building Svelte islands...');

const buildOptions = {
  entryPoints: ['./init.js'],
  bundle: true,
  outfile: '../static/islands/islands.js',
  format: 'esm',
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

