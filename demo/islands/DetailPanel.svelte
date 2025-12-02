<script>
  import { onMount } from 'svelte';
  
  // State
  let visible = false;
  let loading = false;
  let error = null;
  let data = null;
  let fromSlug = null;
  let toSlug = null;
  
  // Tier display info
  const tierInfo = {
    5: { name: 'PERFECT', color: 'bg-emerald-500', textColor: 'text-emerald-400', desc: 'Target capital found in output' },
    4: { name: 'STATE + CITY', color: 'bg-lime-500', textColor: 'text-lime-400', desc: 'Target state city found (not capital)' },
    3: { name: 'STATE ONLY', color: 'bg-yellow-500', textColor: 'text-yellow-400', desc: 'Target state mentioned only' },
    2: { name: 'SUPPRESSED', color: 'bg-orange-400', textColor: 'text-orange-400', desc: 'Source suppressed, no target content' },
    1: { name: 'SOURCE PERSISTS', color: 'bg-red-500', textColor: 'text-red-400', desc: 'Source capital still in output' },
    0: { name: 'WRONG STATE', color: 'bg-slate-600', textColor: 'text-slate-400', desc: 'Unrelated state in output' },
  };
  
  // Listen for cell selection events
  onMount(() => {
    document.addEventListener('cell-selected', handleCellSelected);
    return () => {
      document.removeEventListener('cell-selected', handleCellSelected);
    };
  });
  
  async function handleCellSelected(event) {
    const { from, to } = event.detail;
    fromSlug = from;
    toSlug = to;
    visible = true;
    loading = true;
    error = null;
    data = null;
    
    try {
      const res = await fetch(`/api/swap/${from}/${to}`);
      if (!res.ok) {
        throw new Error('Swap data not found');
      }
      data = await res.json();
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }
  
  function close() {
    visible = false;
    data = null;
    fromSlug = null;
    toSlug = null;
  }
  
  // Get tier from classification
  function getTier() {
    if (!data) return null;
    // Try classification first
    if (data.classification?.tier !== undefined) {
      return data.classification.tier;
    }
    // Fallback to evaluation
    const exact = data.evaluation?.exact_match || {};
    if (exact.steered_has_to_capital) return 5;
    if (exact.from_suppressed && !exact.steered_has_to_capital) return 2;
    if (!exact.from_suppressed) return 1;
    return 3;
  }
  
  // Highlight capitals in output
  function highlightOutput(text, sourceCapital, targetCapital) {
    if (!text) return '';
    let result = text;
    if (targetCapital) {
      result = result.replace(new RegExp(targetCapital, 'gi'), `<span class="text-emerald-400 font-bold">${targetCapital}</span>`);
    }
    if (sourceCapital) {
      result = result.replace(new RegExp(sourceCapital, 'gi'), `<span class="text-red-400 font-bold">${sourceCapital}</span>`);
    }
    return result;
  }
</script>

<!-- Backdrop -->
{#if visible}
  <div 
    class="fixed inset-0 bg-black/50 z-40"
    on:click={close}
    on:keydown={(e) => e.key === 'Escape' && close()}
    role="button"
    tabindex="0"
  ></div>
{/if}

<!-- Panel -->
<aside 
  class="detail-panel z-50 {visible ? 'visible' : ''}"
  class:animate-slide-in={visible}
>
  {#if visible}
    <!-- Header -->
    <div class="sticky top-0 bg-slate-900 border-b border-slate-700 p-4 flex items-center justify-between">
      <h2 class="text-lg font-semibold">Swap Details</h2>
      <button 
        class="w-8 h-8 flex items-center justify-center rounded hover:bg-slate-800 transition-colors text-slate-400 hover:text-white"
        on:click={close}
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
    
    <!-- Content -->
    <div class="p-4">
      {#if loading}
        <div class="py-20 text-center text-slate-500 animate-pulse">
          Loading swap data...
        </div>
      {:else if error}
        <div class="py-20 text-center text-red-400">
          {error}
        </div>
      {:else if data}
        {@const tier = getTier()}
        {@const info = tierInfo[tier] || tierInfo[0]}
        {@const source = data.source || {}}
        {@const target = data.target || {}}
        {@const evaluation = data.evaluation || {}}
        {@const raw = evaluation.raw || {}}
        {@const firstToken = evaluation.first_token || {}}
        {@const exact = evaluation.exact_match || {}}
        
        <!-- Swap header -->
        <div class="mb-6">
          <div class="flex items-center gap-3 mb-2">
            <div class="text-center">
              <div class="text-2xl font-bold">{source.state || 'Unknown'}</div>
              <div class="text-xs text-slate-500">{source.city || ''}</div>
            </div>
            <div class="text-slate-600 text-2xl">-></div>
            <div class="text-center">
              <div class="text-2xl font-bold">{target.state || 'Unknown'}</div>
              <div class="text-xs text-slate-500">{target.city || ''}</div>
            </div>
          </div>
        </div>
        
        <!-- Tier badge -->
        <div class="mb-6 p-4 rounded-lg bg-slate-800/50 border border-slate-700">
          <div class="flex items-center gap-3 mb-2">
            <div class="px-3 py-1 rounded {info.color} text-white font-bold text-sm">
              TIER {tier}
            </div>
            <div class="{info.textColor} font-semibold">{info.name}</div>
          </div>
          <p class="text-sm text-slate-400">{info.desc}</p>
          {#if data.classification?.notes}
            <p class="text-sm text-slate-500 mt-2">{data.classification.notes}</p>
          {/if}
          {#if data.classification?.cities_found}
            <p class="text-xs text-slate-600 mt-2">
              Found: {Array.isArray(data.classification.cities_found) ? data.classification.cities_found.join(', ') : data.classification.cities_found}
            </p>
          {/if}
        </div>
        
        <!-- State cards -->
        <div class="grid grid-cols-2 gap-4 mb-6">
          <!-- Source -->
          <div class="p-3 rounded-lg bg-slate-800/50 border border-slate-700">
            <div class="text-xs text-slate-500 uppercase mb-2">Source</div>
            <div class="text-sm font-semibold">{source.state}</div>
            <div class="text-xs text-slate-400">Capital: <span class="text-yellow-400">{source.capital}</span></div>
            <div class="text-xs text-slate-400">City: {source.city}</div>
            {#if source.neuronpedia_url}
              <a 
                href={source.neuronpedia_url} 
                target="_blank"
                class="inline-block mt-2 text-xs text-cyan-400 hover:underline"
              >
                Neuronpedia ->
              </a>
            {/if}
          </div>
          
          <!-- Target -->
          <div class="p-3 rounded-lg bg-slate-800/50 border border-slate-700">
            <div class="text-xs text-slate-500 uppercase mb-2">Target</div>
            <div class="text-sm font-semibold">{target.state}</div>
            <div class="text-xs text-slate-400">Capital: <span class="text-emerald-400">{target.capital}</span></div>
            <div class="text-xs text-slate-400">City: {target.city}</div>
            {#if target.neuronpedia_url}
              <a 
                href={target.neuronpedia_url} 
                target="_blank"
                class="inline-block mt-2 text-xs text-cyan-400 hover:underline"
              >
                Neuronpedia ->
              </a>
            {/if}
          </div>
        </div>
        
        <!-- Outputs -->
        <div class="space-y-4 mb-6">
          <div>
            <div class="text-xs text-slate-500 uppercase mb-2">Default Output</div>
            <div class="p-3 rounded bg-slate-800 text-sm font-mono text-slate-300 overflow-x-auto">
              {@html highlightOutput(raw.default_output?.slice(0, 200) || 'N/A', source.capital, target.capital)}
            </div>
          </div>
          
          <div class="flex items-center justify-center">
            <div class="px-3 py-1 rounded-full bg-cyan-900/30 text-cyan-400 text-xs">
              STEERED
            </div>
          </div>
          
          <div>
            <div class="text-xs text-slate-500 uppercase mb-2">Steered Output</div>
            <div class="p-3 rounded bg-slate-800 text-sm font-mono text-slate-300 overflow-x-auto">
              {@html highlightOutput(raw.steered_output?.slice(0, 200) || 'N/A', source.capital, target.capital)}
            </div>
          </div>
        </div>
        
        <!-- First token analysis -->
        <div class="p-4 rounded-lg bg-slate-800/50 border border-slate-700 mb-6">
          <div class="text-xs text-slate-500 uppercase mb-3">First Token Analysis</div>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <div class="text-xs text-slate-500">Default</div>
              <div class="text-sm font-mono text-yellow-400">'{firstToken.default || '?'}'</div>
              <div class="text-xs text-slate-600">prob: {(firstToken.default_prob || 0).toFixed(3)}</div>
            </div>
            <div>
              <div class="text-xs text-slate-500">Steered</div>
              <div class="text-sm font-mono text-cyan-400">'{firstToken.steered || '?'}'</div>
              <div class="text-xs text-slate-600">prob: {(firstToken.steered_prob || 0).toFixed(3)}</div>
            </div>
          </div>
        </div>
        
        <!-- Status indicators -->
        <div class="p-4 rounded-lg bg-slate-800/50 border border-slate-700 mb-6">
          <div class="text-xs text-slate-500 uppercase mb-3">Status</div>
          <div class="space-y-2">
            <div class="flex items-center justify-between text-sm">
              <span class="text-slate-400">Target capital in steered:</span>
              <span class={exact.steered_has_to_capital ? 'text-emerald-400' : 'text-red-400'}>
                {exact.steered_has_to_capital ? 'Yes' : 'No'}
              </span>
            </div>
            <div class="flex items-center justify-between text-sm">
              <span class="text-slate-400">Source suppressed:</span>
              <span class={exact.from_suppressed ? 'text-emerald-400' : 'text-red-400'}>
                {exact.from_suppressed ? 'Yes' : 'No'}
              </span>
            </div>
          </div>
        </div>
        
        <!-- Intervention stats -->
        {#if data.interventions}
          <div class="p-4 rounded-lg bg-slate-800/50 border border-slate-700">
            <div class="text-xs text-slate-500 uppercase mb-3">Interventions</div>
            <div class="grid grid-cols-3 gap-4 text-center">
              <div>
                <div class="text-lg font-bold text-red-400">{data.interventions.ablate_count || 0}</div>
                <div class="text-xs text-slate-500">Ablated</div>
              </div>
              <div>
                <div class="text-lg font-bold text-emerald-400">{data.interventions.amplify_count || 0}</div>
                <div class="text-xs text-slate-500">Amplified</div>
              </div>
              <div>
                <div class="text-lg font-bold text-slate-400">{data.interventions.total_count || 0}</div>
                <div class="text-xs text-slate-500">Total</div>
              </div>
            </div>
          </div>
        {/if}
        
        <!-- Links -->
        <div class="mt-6 flex gap-2">
          {#if source.neuronpedia_url}
            <a 
              href={source.neuronpedia_url}
              target="_blank"
              class="flex-1 py-2 px-4 rounded bg-slate-800 hover:bg-slate-700 text-center text-sm text-cyan-400 transition-colors"
            >
              Source Subgraph
            </a>
          {/if}
          {#if target.neuronpedia_url}
            <a 
              href={target.neuronpedia_url}
              target="_blank"
              class="flex-1 py-2 px-4 rounded bg-slate-800 hover:bg-slate-700 text-center text-sm text-cyan-400 transition-colors"
            >
              Target Subgraph
            </a>
          {/if}
        </div>
      {/if}
    </div>
  {/if}
</aside>

<style>
  .detail-panel {
    position: fixed;
    right: 0;
    top: 0;
    height: 100%;
    width: 450px;
    background-color: rgb(15 23 42);
    border-left: 1px solid rgb(51 65 85);
    box-shadow: 0 25px 50px -12px rgb(0 0 0 / 0.25);
    overflow-y: auto;
    transform: translateX(100%);
    transition: transform 300ms ease;
  }
  
  .detail-panel.visible {
    transform: translateX(0);
  }
  
  @media (max-width: 500px) {
    .detail-panel {
      width: 100%;
    }
  }
</style>

