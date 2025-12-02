<script>
  import { onMount, createEventDispatcher } from 'svelte';
  
  const dispatch = createEventDispatcher();
  
  // State
  let matrix = {};
  let states = [];
  let loading = true;
  let error = null;
  let selected = null;
  let hoveredCell = null;
  let sortBy = 'alpha'; // alpha, native_prob, supernodes, src_tier, tgt_tier
  
  // Tier colors
  const tierColors = {
    5: 'bg-emerald-500 hover:bg-emerald-400',
    4: 'bg-lime-500 hover:bg-lime-400',
    3: 'bg-yellow-500 hover:bg-yellow-400',
    2: 'bg-orange-400 hover:bg-orange-300',
    1: 'bg-red-500 hover:bg-red-400',
    0: 'bg-slate-600 hover:bg-slate-500',
    null: 'bg-slate-800',
  };
  
  // Sorted states
  $: sortedStates = [...states].sort((a, b) => {
    if (sortBy === 'alpha') return a.state.localeCompare(b.state);
    if (sortBy === 'native_prob') return (b.native_prob || 0) - (a.native_prob || 0);
    if (sortBy === 'supernodes') return (b.supernodes || 0) - (a.supernodes || 0);
    if (sortBy === 'src_tier') return (b.src_tier || 0) - (a.src_tier || 0);
    if (sortBy === 'tgt_tier') return (b.tgt_tier || 0) - (a.tgt_tier || 0);
    return 0;
  });
  
  // Load data on mount
  onMount(async () => {
    try {
      const [matrixRes, statesRes] = await Promise.all([
        fetch('/api/matrix'),
        fetch('/api/states'),
      ]);
      
      if (!matrixRes.ok || !statesRes.ok) {
        throw new Error('Failed to load data');
      }
      
      matrix = await matrixRes.json();
      states = await statesRes.json();
      loading = false;
    } catch (e) {
      error = e.message;
      loading = false;
    }
  });
  
  // Handle cell click
  function selectCell(fromSlug, toSlug) {
    if (fromSlug === toSlug) return; // Skip identity
    
    selected = { from: fromSlug, to: toSlug };
    
    // Dispatch event for detail panel
    const event = new CustomEvent('cell-selected', {
      detail: { from: fromSlug, to: toSlug },
      bubbles: true,
    });
    document.dispatchEvent(event);
  }
  
  // Get tier for a cell
  function getTier(fromSlug, toSlug) {
    if (fromSlug === toSlug) return null;
    return matrix[fromSlug]?.[toSlug] ?? null;
  }
  
  // Get color class for tier
  function getTierColor(tier) {
    if (tier === null || tier === undefined) return 'bg-slate-800';
    return tierColors[tier] || 'bg-slate-700';
  }
  
  // Check if cell is selected
  function isSelected(fromSlug, toSlug) {
    return selected?.from === fromSlug && selected?.to === toSlug;
  }
  
  // Check if row/col should be dimmed
  function isDimmed(fromSlug, toSlug) {
    if (!hoveredCell) return false;
    return hoveredCell.from !== fromSlug && hoveredCell.to !== toSlug;
  }
</script>

<div class="matrix-wrapper">
  <!-- Sort controls -->
  <div class="flex items-center gap-4 mb-4">
    <span class="text-xs text-slate-500">Sort by:</span>
    <div class="flex gap-2">
      {#each [
        { value: 'alpha', label: 'A-Z' },
        { value: 'native_prob', label: 'Native Prob' },
        { value: 'supernodes', label: 'Supernodes' },
        { value: 'src_tier', label: 'Source Tier' },
        { value: 'tgt_tier', label: 'Target Tier' },
      ] as option}
        <button
          class="px-2 py-1 text-xs rounded transition-colors {sortBy === option.value ? 'bg-cyan-900/50 text-cyan-400' : 'bg-slate-800 text-slate-400 hover:bg-slate-700'}"
          on:click={() => sortBy = option.value}
        >
          {option.label}
        </button>
      {/each}
    </div>
  </div>
  
  {#if loading}
    <div class="flex items-center justify-center py-20">
      <div class="text-slate-500 animate-pulse">Loading matrix data...</div>
    </div>
  {:else if error}
    <div class="flex items-center justify-center py-20">
      <div class="text-red-400">Error: {error}</div>
    </div>
  {:else if sortedStates.length === 0}
    <div class="flex items-center justify-center py-20">
      <div class="text-slate-500">No states found</div>
    </div>
  {:else}
    <div class="overflow-x-auto">
      <!-- Matrix container -->
      <div class="inline-block">
        <!-- Header row with column labels -->
        <div class="flex">
          <!-- Empty corner cell -->
          <div class="w-16 h-16 flex-shrink-0"></div>
          <!-- Column headers -->
          {#each sortedStates as state}
            <div 
              class="w-4 h-16 flex-shrink-0 relative group"
              title="{state.state} ({state.city})"
            >
              <span class="absolute bottom-0 left-1/2 -translate-x-1/2 origin-bottom-left -rotate-45 text-[10px] text-slate-500 whitespace-nowrap">
                {state.abbr}
              </span>
            </div>
          {/each}
        </div>
        
        <!-- Matrix rows -->
        {#each sortedStates as rowState, rowIndex}
          <div class="flex">
            <!-- Row label -->
            <div 
              class="w-16 h-4 flex-shrink-0 flex items-center justify-end pr-2"
              title="{rowState.state} ({rowState.city})"
            >
              <a 
                href="/state/{rowState.slug}" 
                class="text-[10px] text-slate-500 hover:text-cyan-400 transition-colors"
              >
                {rowState.abbr}
              </a>
            </div>
            
            <!-- Cells -->
            {#each sortedStates as colState, colIndex}
              {@const tier = getTier(rowState.slug, colState.slug)}
              {@const isIdentity = rowState.slug === colState.slug}
              <button
                class="w-4 h-4 flex-shrink-0 rounded-sm transition-all duration-100 {isIdentity ? 'bg-slate-900' : getTierColor(tier)} {isSelected(rowState.slug, colState.slug) ? 'ring-2 ring-cyan-400 z-10' : ''} {isDimmed(rowState.slug, colState.slug) ? 'opacity-30' : ''}"
                disabled={isIdentity || tier === null}
                on:click={() => selectCell(rowState.slug, colState.slug)}
                on:mouseenter={() => hoveredCell = { from: rowState.slug, to: colState.slug }}
                on:mouseleave={() => hoveredCell = null}
                title={isIdentity ? 'Identity' : tier !== null ? `${rowState.abbr} -> ${colState.abbr}: Tier ${tier}` : 'No data'}
              ></button>
            {/each}
          </div>
        {/each}
      </div>
    </div>
    
    <!-- Hover info -->
    {#if hoveredCell && hoveredCell.from !== hoveredCell.to}
      {@const fromState = states.find(s => s.slug === hoveredCell.from)}
      {@const toState = states.find(s => s.slug === hoveredCell.to)}
      {@const tier = getTier(hoveredCell.from, hoveredCell.to)}
      <div class="mt-4 p-3 bg-slate-800/50 rounded-lg text-sm">
        <span class="text-slate-400">{fromState?.state || hoveredCell.from}</span>
        <span class="text-slate-600 mx-2">-></span>
        <span class="text-slate-400">{toState?.state || hoveredCell.to}</span>
        {#if tier !== null}
          <span class="ml-3 px-2 py-0.5 rounded text-xs font-bold tier-{tier} tier-{tier}-text">
            T{tier}
          </span>
        {:else}
          <span class="ml-3 text-slate-600">No data</span>
        {/if}
      </div>
    {/if}
  {/if}
</div>

<style>
  .matrix-wrapper {
    user-select: none;
  }
  
  button:not(:disabled):hover {
    transform: scale(1.5);
    z-index: 10;
  }
</style>

