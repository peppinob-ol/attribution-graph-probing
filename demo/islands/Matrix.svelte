<script>
  import { onMount, onDestroy, createEventDispatcher } from 'svelte';
  
  const dispatch = createEventDispatcher();
  
  // State
  let matrix = {};
  let flipMatrix = {};
  let states = [];
  let domainConfig = null;
  let loading = true;
  let error = null;
  let selected = null;
  let hoveredCell = null;
  let sortBy = 'alpha';
  let hideOverlap = false;
  let hideCapitalNotTopLogit = false;
  let colorMode = 'tier';

  // Global variant selector
  let availableVariants = [];
  let selectedVariant = null;
  let variantLoading = false;
  let matrixGeneration = 0;

  $: isUsaStates = domainConfig?.is_usa_states ?? true;
  
  const tierColors = {
    5:    { bg: '#0A4FFF', hover: '#3D7DFF' },
    4:    { bg: '#3D7DFF', hover: '#6B9FFF' },
    3:    { bg: '#AFCBFF', hover: '#C7DAFF' },
    2.5:  { bg: '#FFE8E8', hover: '#FFF0F0' },
    2:    { bg: '#FF7373', hover: '#FF9999' },
    1:    { bg: '#C00000', hover: '#E00000' },
    0:    { bg: '#475569', hover: '#64748b' },
    null: { bg: '#1e293b', hover: '#334155' },
  };

  const flipColors = {
    0:    { bg: '#10b981', hover: '#34d399' },
    1:    { bg: '#34d399', hover: '#6ee7b7' },
    2:    { bg: '#a3e635', hover: '#bef264' },
    3:    { bg: '#facc15', hover: '#fde047' },
    4:    { bg: '#fb923c', hover: '#fdba74' },
    5:    { bg: '#f87171', hover: '#fca5a5' },
    'late': { bg: '#ef4444', hover: '#f87171' },
    null: { bg: '#7f1d1d', hover: '#991b1b' },
    'no_data': { bg: '#1e293b', hover: '#334155' },
  };

  function getFlipStyle(flipPos) {
    if (flipPos === undefined || flipPos === -1) return flipColors['no_data'];
    if (flipPos === null) return flipColors[null];
    if (flipPos <= 5) return flipColors[flipPos] || flipColors[5];
    return flipColors['late'];
  }

  function getFlipLabel(flipPos) {
    if (flipPos === undefined || flipPos === -1) return 'No data';
    if (flipPos === null) return 'Never';
    return `@${flipPos}`;
  }

  function getTierStyle(tier) {
    if (tier === null || tier === undefined) return tierColors[null];
    return tierColors[tier] || tierColors[null];
  }

  function getCellStyle(fromSlug, toSlug) {
    if (colorMode === 'flip') {
      const flipPos = flipMatrix[fromSlug]?.[toSlug];
      const tierVal = matrix[fromSlug]?.[toSlug];
      if (tierVal === undefined || tierVal === null) return flipColors['no_data'];
      if (flipPos === -1) return flipColors['no_data'];
      return getFlipStyle(flipPos);
    }
    return getTierStyle(getTier(fromSlug, toSlug));
  }
  
  function hasNameOverlap(s) {
    if (isUsaStates) {
      const stateLower = (s.state || '').toLowerCase();
      const cityLower = (s.city || '').toLowerCase();
      if (!stateLower || !cityLower) return false;
      if (cityLower.includes(stateLower)) return true;
      return stateLower.split(/\s+/).filter(w => w.length >= 4).some(w => cityLower.includes(w));
    }

    const fields = s.fields || {};
    const conceptFields = domainConfig?.concept_fields || [];
    const answerField = domainConfig?.answer_field || '';
    const primaryField = domainConfig?.primary_field || '';
    const intermediateField = conceptFields.find(f => f !== answerField) || '';
    if (!primaryField || !intermediateField) return false;

    const a = (fields[primaryField] || '').toLowerCase();
    const b = (fields[intermediateField] || '').toLowerCase();
    if (!a || !b) return false;

    if (a.includes(b) || b.includes(a)) return true;
    const aWords = a.split(/\s+/).filter(w => w.length >= 4);
    const bWords = b.split(/\s+/).filter(w => w.length >= 4);
    return aWords.some(w => b.includes(w)) || bWords.some(w => a.includes(w));
  }

  function hasCapitalNotTopLogit(s) {
    if (!isUsaStates) return false;
    return s.capital_is_top_logit === false;
  }
  
  $: sortedStates = [...states].sort((a, b) => {
    if (sortBy === 'alpha') return (a.label || a.state || '').localeCompare(b.label || b.state || '');
    if (sortBy === 'native_prob') return (b.native_prob || 0) - (a.native_prob || 0);
    if (sortBy === 'supernodes') return (b.supernodes || 0) - (a.supernodes || 0);
    if (sortBy === 'src_tier') return (b.src_tier || 0) - (a.src_tier || 0);
    if (sortBy === 'tgt_tier') return (b.tgt_tier || 0) - (a.tgt_tier || 0);
    return 0;
  });
  
  $: visibleStates = sortedStates.filter(s =>
    (!hideOverlap || !hasNameOverlap(s)) &&
    (!hideCapitalNotTopLogit || !hasCapitalNotTopLogit(s))
  );
  
  $: overlapCount = states.filter(s => hasNameOverlap(s)).length;
  $: capitalNotTopLogitCount = states.filter(s => hasCapitalNotTopLogit(s)).length;
  
  $: filteredStats = computeStats(visibleStates, matrix, flipMatrix);
  
  function computeStats(visible, mat, fmat) {
    const slugs = new Set(visible.map(s => s.slug));
    let total = 0, perfect = 0, stateCorrect = 0, suppressed = 0;
    let flipTracked = 0, flipAt01 = 0;
    for (const from of slugs) {
      for (const to of slugs) {
        if (from === to) continue;
        const tier = mat[from]?.[to];
        if (tier == null) continue;
        total++;
        if (tier === 5) perfect++;
        if (tier >= 3) stateCorrect++;
        if (tier >= 2) suppressed++;
        const fp = fmat[from]?.[to];
        if (fp !== undefined && fp !== -1) {
          flipTracked++;
          if (fp !== null && fp <= 1) flipAt01++;
        }
      }
    }
    return {
      total,
      perfectRate: total > 0 ? (perfect / total * 100) : 0,
      stateCorrectRate: total > 0 ? (stateCorrect / total * 100) : 0,
      suppressionRate: total > 0 ? (suppressed / total * 100) : 0,
      flipAt01Rate: flipTracked > 0 ? (flipAt01 / flipTracked * 100) : 0,
      flipTracked,
    };
  }
  
  $: if (typeof document !== 'undefined' && !loading) {
    updateKPIs(filteredStats);
  }
  
  function updateKPIs(stats) {
    const el = (id, val) => {
      const node = document.getElementById(id);
      if (node) node.textContent = val;
    };
    el('kpi-total', String(stats.total));
    el('kpi-perfect', `${stats.perfectRate.toFixed(0)}%`);
    el('kpi-correct', `${stats.stateCorrectRate.toFixed(0)}%`);
    el('kpi-suppress', `${stats.suppressionRate.toFixed(0)}%`);
    if (stats.flipTracked > 0) {
      el('kpi-flip01', `${stats.flipAt01Rate.toFixed(0)}%`);
    }
  }
  
  function selectCell(fromSlug, toSlug) {
    if (fromSlug === toSlug) return;
    selected = { from: fromSlug, to: toSlug };
    document.dispatchEvent(new CustomEvent('cell-selected', {
      detail: { from: fromSlug, to: toSlug },
      bubbles: true,
    }));
  }

  function showStateCard(slug) {
    document.dispatchEvent(new CustomEvent('show-state-card', {
      detail: { slug },
      bubbles: true,
    }));
  }

  function handleKeydown(e) {
    if (!selected) return;
    if (document.querySelector('.state-card-content')) return;

    if (e.key === 'Escape') {
      e.preventDefault();
      selected = null;
      return;
    }

    const { key } = e;
    if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(key)) return;
    e.preventDefault();

    const fromIdx = visibleStates.findIndex(s => s.slug === selected.from);
    const toIdx = visibleStates.findIndex(s => s.slug === selected.to);
    if (fromIdx === -1 || toIdx === -1) return;

    let nf = fromIdx, nt = toIdx;
    const len = visibleStates.length;
    if (key === 'ArrowUp')    nf = Math.max(0, fromIdx - 1);
    if (key === 'ArrowDown')  nf = Math.min(len - 1, fromIdx + 1);
    if (key === 'ArrowLeft')  nt = Math.max(0, toIdx - 1);
    if (key === 'ArrowRight') nt = Math.min(len - 1, toIdx + 1);

    if (nf === nt) {
      if (key === 'ArrowUp')         nf = Math.max(0, nf - 1);
      else if (key === 'ArrowDown')  nf = Math.min(len - 1, nf + 1);
      else if (key === 'ArrowLeft')  nt = Math.max(0, nt - 1);
      else if (key === 'ArrowRight') nt = Math.min(len - 1, nt + 1);
    }

    if (nf !== nt && nf >= 0 && nf < len && nt >= 0 && nt < len) {
      selectCell(visibleStates[nf].slug, visibleStates[nt].slug);
    }
  }

  function handleColorModeChanged(e) {
    colorMode = e.detail?.mode || 'tier';
  }

  function variantLabel(suffix) {
    if (!suffix) return 'Best';
    if (suffix.startsWith('r')) return `Rep ${suffix.slice(1)}`;
    if (suffix.startsWith('add_')) return suffix.slice(4).replace(/_/g, ' + ');
    return suffix.replace(/_/g, ' ');
  }

  async function switchMatrixVariant(varSuffix) {
    selectedVariant = varSuffix;
    variantLoading = true;
    document.dispatchEvent(new CustomEvent('variant-changed', {
      detail: { variant: varSuffix },
      bubbles: true,
    }));
    try {
      const qs = varSuffix ? `?variant=${encodeURIComponent(varSuffix)}` : '';
      const [mRes, fRes] = await Promise.all([
        fetch(`/api/matrix${qs}`),
        fetch(`/api/flip-matrix${qs}`),
      ]);
      if (mRes.ok) matrix = await mRes.json();
      if (fRes.ok) flipMatrix = await fRes.json();
      matrixGeneration++;
    } catch {}
    variantLoading = false;
  }

  onMount(async () => {
    document.addEventListener('keydown', handleKeydown);
    document.addEventListener('color-mode-changed', handleColorModeChanged);
    try {
      const [matrixRes, statesRes, configRes, flipRes, varRes] = await Promise.all([
        fetch('/api/matrix'),
        fetch('/api/states'),
        fetch('/api/config'),
        fetch('/api/flip-matrix'),
        fetch('/api/run-variants'),
      ]);
      
      if (!matrixRes.ok || !statesRes.ok) {
        throw new Error('Failed to load data');
      }
      
      matrix = await matrixRes.json();
      states = await statesRes.json();
      if (configRes.ok) {
        const cfg = await configRes.json();
        domainConfig = cfg.domain || null;
      }
      if (flipRes.ok) {
        flipMatrix = await flipRes.json();
      }
      if (varRes.ok) {
        const vd = await varRes.json();
        availableVariants = vd.variants || [];
      }
      loading = false;
    } catch (e) {
      error = e.message;
      loading = false;
    }
  });

  onDestroy(() => {
    document.removeEventListener('keydown', handleKeydown);
    document.removeEventListener('color-mode-changed', handleColorModeChanged);
  });
  
  function getTier(fromSlug, toSlug) {
    if (fromSlug === toSlug) return null;
    return matrix[fromSlug]?.[toSlug] ?? null;
  }
  
  function isSelected(fromSlug, toSlug) {
    return selected?.from === fromSlug && selected?.to === toSlug;
  }
  
  function isDimmed(fromSlug, toSlug) {
    if (!hoveredCell) return false;
    return hoveredCell.from !== fromSlug && hoveredCell.to !== toSlug;
  }
</script>

<div class="matrix-wrapper">
  <!-- Controls -->
  <div class="flex items-center gap-4 mb-4 flex-wrap">
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
    
    {#if overlapCount > 0 || (isUsaStates && capitalNotTopLogitCount > 0)}
      <span class="text-slate-700 hidden sm:inline">|</span>
      {#if overlapCount > 0}
        <label class="flex items-center gap-2 cursor-pointer select-none">
          <input type="checkbox" bind:checked={hideOverlap} class="accent-cyan-500" />
          <span class="text-xs {hideOverlap ? 'text-cyan-400' : 'text-slate-400'}">
            Hide name overlaps ({overlapCount})
          </span>
        </label>
      {/if}
      {#if isUsaStates && capitalNotTopLogitCount > 0}
        <label class="flex items-center gap-2 cursor-pointer select-none">
          <input type="checkbox" bind:checked={hideCapitalNotTopLogit} class="accent-cyan-500" />
          <span class="text-xs {hideCapitalNotTopLogit ? 'text-cyan-400' : 'text-slate-400'}">
            Hide capital not top logit ({capitalNotTopLogitCount})
          </span>
        </label>
      {/if}
    {/if}
  </div>

  {#if availableVariants.length > 0}
    <div class="flex items-center flex-wrap gap-2 mb-3 text-xs {variantLoading ? 'opacity-50 pointer-events-none' : ''}">
      <span class="text-slate-500">Variant:</span>
      <button
        class="px-2 py-1 rounded transition-colors {selectedVariant === null ? 'bg-indigo-900/50 text-indigo-400 border border-indigo-500/40' : 'bg-slate-800 text-slate-400 hover:bg-slate-700 border border-transparent'}"
        on:click={() => switchMatrixVariant(null)}
      >Best</button>
      {#each availableVariants as v}
        <button
          class="px-2 py-1 rounded transition-colors {selectedVariant === v ? 'bg-indigo-900/50 text-indigo-400 border border-indigo-500/40' : 'bg-slate-800 text-slate-400 hover:bg-slate-700 border border-transparent'}"
          on:click={() => switchMatrixVariant(v)}
        >{variantLabel(v)}</button>
      {/each}
    </div>
  {/if}

  {#if selected}
    <div class="mb-3 text-center text-xs text-slate-600">
      <kbd class="px-1 py-0.5 rounded bg-slate-800 text-slate-500">&#8592;</kbd>
      <kbd class="px-1 py-0.5 rounded bg-slate-800 text-slate-500">&#8594;</kbd>
      <kbd class="px-1 py-0.5 rounded bg-slate-800 text-slate-500">&#8593;</kbd>
      <kbd class="px-1 py-0.5 rounded bg-slate-800 text-slate-500">&#8595;</kbd>
      navigate cells |
      <kbd class="px-1 py-0.5 rounded bg-slate-800 text-slate-500">Esc</kbd> deselect
    </div>
  {/if}

  {#if loading}
    <div class="flex items-center justify-center py-20">
      <div class="text-slate-500 animate-pulse">Loading matrix data...</div>
    </div>
  {:else if error}
    <div class="flex items-center justify-center py-20">
      <div class="text-red-400">Error: {error}</div>
    </div>
  {:else if visibleStates.length === 0}
    <div class="flex items-center justify-center py-20">
      <div class="text-slate-500">No states found</div>
    </div>
  {:else}
    <div class="overflow-x-auto">
      {#key `${colorMode}-${matrixGeneration}`}
      <div class="matrix-grid" style="grid-template-columns: 64px repeat({visibleStates.length}, 16px);">
        <!-- Empty corner cell -->
        <div class="matrix-corner"></div>
        <!-- Column headers -->
        {#each visibleStates as state}
          <div 
            class="matrix-col-header"
            title="{state.label || state.state}{state.city ? ` (${state.city})` : ''}"
          >
            <button
              class="absolute bottom-0 left-1/2 -translate-x-1/2 origin-bottom-left -rotate-45 text-[10px] text-slate-500 hover:text-cyan-400 whitespace-nowrap bg-transparent border-none cursor-pointer p-0 transition-colors"
              on:click|preventDefault|stopPropagation={() => showStateCard(state.slug)}
            >
              {state.abbr}
            </button>
          </div>
        {/each}
        
        <!-- Matrix rows -->
        {#each visibleStates as rowState, rowIndex}
          <!-- Row label -->
          <div 
            class="matrix-row-label"
            title="{rowState.label || rowState.state}{rowState.city ? ` (${rowState.city})` : ''}"
          >
            <button
              class="text-[10px] text-slate-500 hover:text-cyan-400 transition-colors bg-transparent border-none cursor-pointer p-0"
              on:click|preventDefault|stopPropagation={() => showStateCard(rowState.slug)}
            >
              {rowState.abbr}
            </button>
          </div>
          
          <!-- Cells -->
          {#each visibleStates as colState, colIndex}
            {@const tier = getTier(rowState.slug, colState.slug)}
            {@const isIdentity = rowState.slug === colState.slug}
            {@const cs = isIdentity ? { bg: '#0f172a', hover: '#0f172a' } : getCellStyle(rowState.slug, colState.slug)}
            {@const sel = selected?.from === rowState.slug && selected?.to === colState.slug}
            {@const flipPos = flipMatrix[rowState.slug]?.[colState.slug]}
            <button
              class="matrix-cell rounded-sm transition-all duration-100"
              class:opacity-30={isDimmed(rowState.slug, colState.slug)}
              style="--cell-bg: {cs.bg}; --cell-hover: {cs.hover};{sel ? ' transform: scale(1.5); z-index: 20; background-color: var(--cell-hover); box-shadow: 0 0 0 2px #22d3ee;' : ''}"
              disabled={isIdentity || tier === null}
              on:click={() => selectCell(rowState.slug, colState.slug)}
              on:mouseenter={() => hoveredCell = { from: rowState.slug, to: colState.slug }}
              on:mouseleave={() => hoveredCell = null}
              title={isIdentity ? 'Identity' : tier !== null ? `${rowState.abbr} -> ${colState.abbr}: ${colorMode === 'flip' ? getFlipLabel(flipPos) : 'Tier ' + tier}` : 'No data'}
            ></button>
          {/each}
        {/each}
      </div>
      {/key}
    </div>
    
    <!-- Hover info -->
    {#if hoveredCell && hoveredCell.from !== hoveredCell.to}
      {@const fromState = states.find(s => s.slug === hoveredCell.from)}
      {@const toState = states.find(s => s.slug === hoveredCell.to)}
      {@const tier = getTier(hoveredCell.from, hoveredCell.to)}
      {@const flipPos = flipMatrix[hoveredCell.from]?.[hoveredCell.to]}
      <div class="mt-4 p-3 bg-slate-800/50 rounded-lg text-sm">
        <span class="text-slate-400">{fromState?.label || fromState?.state || hoveredCell.from}</span>
        <span class="text-slate-600 mx-2">-></span>
        <span class="text-slate-400">{toState?.label || toState?.state || hoveredCell.to}</span>
        {#if tier !== null}
          {@const badge = getTierStyle(tier)}
          <span class="ml-3 px-2 py-0.5 rounded text-xs font-bold"
                style="background-color: {badge.bg}; color: {[3, 2.5].includes(tier) ? '#1e293b' : '#fff'};">
            T{tier}
          </span>
          {@const flipBadge = getFlipStyle(flipPos)}
          <span class="ml-1 px-2 py-0.5 rounded text-xs font-bold"
                style="background-color: {flipBadge.bg}; color: {[0, 1, 2, 3].includes(flipPos) ? '#1e293b' : '#fff'};">
            {getFlipLabel(flipPos)}
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
  
  .matrix-grid {
    display: inline-grid;
    gap: 0;
  }
  
  .matrix-corner {
    height: 64px;
  }
  
  .matrix-col-header {
    position: relative;
    height: 64px;
  }
  
  .matrix-row-label {
    height: 16px;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    padding-right: 8px;
  }
  
  .matrix-cell {
    width: 16px;
    height: 16px;
    padding: 0;
    margin: 0;
    background-color: var(--cell-bg);
  }
  
  .matrix-cell:not(:disabled):hover {
    transform: scale(1.5);
    z-index: 20;
    background-color: var(--cell-hover);
  }
</style>

