<script>
  import { onMount, onDestroy } from 'svelte';

  const ATTACK_COLOR = '#3D7DFF';
  const DRIFT_COLOR  = '#f87171';
  const CYAN         = '#22d3ee';
  const SLATE        = '#475569';

  let domainConfig = null;
  $: isUsaStates = domainConfig?.is_usa_states ?? true;
  $: entityFields = domainConfig?.entity_fields || [];
  $: answerLabel = domainConfig?.answer_field || 'capital';

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

  function tierBg(tier) {
    return (tierColors[tier] || tierColors[null]).bg;
  }
  function tierText(tier) {
    return [3, 2.5].includes(tier) ? '#1e293b' : '#ffffff';
  }
  function tierLabel(tier) {
    return tier === 2.5 ? 'W' : tier;
  }

  let visible = false;
  let loading = false;
  let error = null;
  let data = null;
  let slug = null;
  let states = [];

  let targetSwapsVisible = false;
  let sourceSwapsVisible = false;
  let targetSwapsLoaded = false;
  let sourceSwapsLoaded = false;
  let targetOutputs = [];
  let sourceOutputs = [];
  let targetOutputsLoading = false;
  let sourceOutputsLoading = false;

  function getWarnings(d) {
    const w = [];
    const np = d.native_prob || 0;
    if (np < 0.20 && np > 0) w.push({ text: 'Low native prob', color: '#fbbf24' });
    if (np > 0.50)           w.push({ text: 'High native prob', color: '#fbbf24' });
    if ((d.supernodes || 0) > 280) w.push({ text: 'High supernode count', color: '#fbbf24' });
    if (d.capital_is_top_logit === false && d.capital_in_logits === true)
      w.push({ text: `${answerLabel} not top logit`, color: '#f87171' });
    if (d.capital_in_logits === false)
      w.push({ text: `${answerLabel} absent from logits`, color: '#f87171' });
    if (d.has_token_overlap)
      w.push({ text: 'Token overlap', color: '#f87171' });
    return w;
  }

  function getHistogramRows(d) {
    const layers = d.feature_layers || {};
    const snLayers = d.supernode_layer_counts || {};
    const maxCount = Math.max(...Object.values(layers), 1);
    const rows = [];
    const layerNums = Object.keys(layers).map(Number).sort((a, b) => b - a);
    for (const layer of layerNums) {
      const total = layers[layer] || 0;
      if (total === 0) continue;
      const sn = snLayers[layer] || 0;
      const other = total - sn;
      rows.push({
        layer, total, sn, other,
        snWidth:    (sn / maxCount) * 100,
        otherWidth: (other / maxCount) * 100,
      });
    }
    return rows;
  }

  $: warnings     = data ? getWarnings(data) : [];
  $: histogramRows = data ? getHistogramRows(data) : [];

  $: currentIndex = states.findIndex(s => s.slug === slug);
  $: prevState    = currentIndex > 0 ? states[currentIndex - 1] : null;
  $: nextState    = currentIndex < states.length - 1 ? states[currentIndex + 1] : null;

  async function show(newSlug) {
    slug = newSlug;
    visible = true;
    loading = true;
    error = null;
    data = null;
    resetSwaps();

    try {
      const [profileRes, statesRes] = await Promise.all([
        fetch(`/api/state/${newSlug}/profile`),
        states.length ? Promise.resolve(null) : fetch('/api/states'),
      ]);
      if (!profileRes.ok) throw new Error('Failed to load profile');
      data = await profileRes.json();
      if (statesRes) states = await statesRes.json();
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  function resetSwaps() {
    targetSwapsVisible = false;
    sourceSwapsVisible = false;
    targetSwapsLoaded = false;
    sourceSwapsLoaded = false;
    targetOutputs = [];
    sourceOutputs = [];
  }

  function close() {
    visible = false;
    data = null;
    slug = null;
    resetSwaps();
    if (window.location.hash.startsWith('#state=')) {
      history.pushState('', document.title, window.location.pathname + window.location.search);
    }
  }

  function navigate(direction) {
    if (!visible || !slug) return;
    const idx = states.findIndex(s => s.slug === slug);
    let next;
    if (direction === 'prev') {
      next = idx > 0 ? idx - 1 : states.length - 1;
    } else {
      next = idx < states.length - 1 ? idx + 1 : 0;
    }
    if (states[next]) show(states[next].slug);
  }

  function handleKeydown(e) {
    if (!visible) return;
    if (e.key === 'Escape')     { e.preventDefault(); close(); }
    if (e.key === 'ArrowLeft')  { e.preventDefault(); navigate('prev'); }
    if (e.key === 'ArrowRight') { e.preventDefault(); navigate('next'); }
  }

  async function toggleSwaps(type) {
    if (type === 'target') {
      targetSwapsVisible = !targetSwapsVisible;
      if (targetSwapsVisible && !targetSwapsLoaded) await loadSwapOutputs('target');
    } else {
      sourceSwapsVisible = !sourceSwapsVisible;
      if (sourceSwapsVisible && !sourceSwapsLoaded) await loadSwapOutputs('source');
    }
  }

  async function loadSwapOutputs(type) {
    const swaps = type === 'target' ? data.swaps_as_target : data.swaps_as_source;
    if (!swaps || !swaps.length) return;

    if (type === 'target') targetOutputsLoading = true;
    else sourceOutputsLoading = true;

    const batch = swaps.slice(0, 10);
    try {
      const results = await Promise.all(batch.map(async (s) => {
        const from = type === 'target' ? s.from_slug : data.slug;
        const to   = type === 'target' ? data.slug   : s.to_slug;
        try {
          const res = await fetch(`/api/swap/${from}/${to}`);
          if (!res.ok) return { ...s, from_slug: from, to_slug: to, steered_output: null };
          const d = await res.json();
          return { ...s, from_slug: from, to_slug: to, steered_output: d.evaluation?.raw?.steered_output || null };
        } catch { return { ...s, from_slug: from, to_slug: to, steered_output: null }; }
      }));

      if (type === 'target') { targetOutputs = results; targetSwapsLoaded = true; }
      else                   { sourceOutputs = results; sourceSwapsLoaded = true; }
    } catch (e) {
      console.error('Error loading swap outputs:', e);
    } finally {
      if (type === 'target') targetOutputsLoading = false;
      else sourceOutputsLoading = false;
    }
  }

  function truncate(text, len = 120) {
    if (!text) return 'N/A';
    return text.length > len ? text.slice(0, len) + '...' : text;
  }

  function openSwapDetail(fromSlug, toSlug) {
    close();
    document.dispatchEvent(new CustomEvent('cell-selected', {
      detail: { from: fromSlug, to: toSlug },
      bubbles: true,
    }));
  }

  async function openSubgraph() {
    if (!data?.slug) return;
    try {
      const res = await fetch(`/api/state/${data.slug}/subgraph-url?max_features=100`);
      if (!res.ok) throw new Error('Failed');
      const d = await res.json();
      if (d.url) window.open(d.url, '_blank');
    } catch {
      alert('Could not generate subgraph URL');
    }
  }

  function handleShowStateCard(e) {
    show(e.detail.slug);
  }

  onMount(async () => {
    document.addEventListener('show-state-card', handleShowStateCard);
    document.addEventListener('keydown', handleKeydown);
    try {
      const res = await fetch('/api/config');
      if (res.ok) {
        const cfg = await res.json();
        domainConfig = cfg.domain || null;
      }
    } catch {}
  });

  onDestroy(() => {
    document.removeEventListener('show-state-card', handleShowStateCard);
    document.removeEventListener('keydown', handleKeydown);
  });
</script>

{#if visible}
  <!-- Backdrop -->
  <div
    class="fixed inset-0 z-50 flex items-center justify-center"
    on:click|self={close}
    on:keydown={(e) => e.key === 'Escape' && close()}
    role="button"
    tabindex="0"
  >
    <div class="absolute inset-0 bg-black/60"></div>

    <!-- Card -->
    <div class="state-card-content relative bg-slate-900 rounded-xl shadow-2xl border border-slate-700 p-6 max-w-lg w-full mx-4"
         style="max-height: 90vh; overflow-y: auto;">

      {#if loading}
        <div class="text-center py-8 text-slate-500 animate-pulse">Loading state profile...</div>
      {:else if error}
        <div class="text-center py-8 text-red-400">{error}</div>
        <button class="mt-4 w-full py-2 bg-slate-800 hover:bg-slate-700 rounded text-sm text-slate-400" on:click={close}>Close</button>
      {:else if data}
        <!-- Header: nav + title + close -->
        <div class="flex items-center justify-between mb-4">
          <button
            class="state-nav-btn w-8 h-8 flex items-center justify-center rounded hover:bg-slate-800 text-slate-400 hover:text-white {prevState ? '' : 'opacity-30 cursor-not-allowed'}"
            disabled={!prevState}
            on:click={() => navigate('prev')}
            title={prevState ? prevState.state : 'No previous state'}
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
            </svg>
          </button>

          <div class="flex-1 text-center leading-tight">
            <h2 class="text-xl font-bold text-white mb-0">{data.label || data.state}</h2>
            {#if data.neuronpedia_url}
              <button
                class="subgraph-btn px-2 py-0 rounded text-xs bg-cyan-900/40 hover:bg-cyan-900/60 text-cyan-400 border border-cyan-700/60 transition-colors"
                on:click={openSubgraph}
                title="View subgraph on Neuronpedia"
              >view subgraph</button>
            {/if}
            <div class="text-sm text-slate-400">
              {#if data.fields && Object.keys(data.fields).length > 0}
                {#each Object.entries(data.fields) as [field, value], i}
                  {#if i > 0}<span class="mx-2 text-slate-600">|</span>{/if}
                  <span class="capitalize">{field}: <span class={field === answerLabel ? 'text-emerald-400' : ''}>{value || '?'}</span></span>
                {/each}
              {:else}
                <span>Capital: <span class="text-emerald-400">{data.capital || '?'}</span></span>
                <span class="mx-2 text-slate-600">|</span>
                <span>City: {data.city}</span>
              {/if}
            </div>
            {#if warnings.length > 0}
              <div class="flex flex-wrap gap-1 mt-2 justify-center">
                {#each warnings as w}
                  <span class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium"
                        style="background: {w.color}22; color: {w.color};">
                    <svg class="inline-block w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
                      <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
                    </svg>
                    {w.text}
                  </span>
                {/each}
              </div>
            {/if}
          </div>

          <button
            class="state-nav-btn w-8 h-8 flex items-center justify-center rounded hover:bg-slate-800 text-slate-400 hover:text-white {nextState ? '' : 'opacity-30 cursor-not-allowed'}"
            disabled={!nextState}
            on:click={() => navigate('next')}
            title={nextState ? nextState.state : 'No next state'}
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
            </svg>
          </button>

          <button
            class="w-8 h-8 flex items-center justify-center rounded hover:bg-slate-800 text-slate-400 hover:text-white ml-1"
            on:click={close}
            title="Close (Esc)"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Key metrics -->
        <div class="grid grid-cols-2 gap-3 mb-4">
          <div class="p-3 rounded-lg bg-slate-800/50">
            <div class="text-xs text-slate-500 uppercase mb-1">Native Prob</div>
            <div class="text-lg font-bold {(data.native_prob || 0) < 0.2 ? 'text-amber-400' : (data.native_prob || 0) > 0.5 ? 'text-emerald-400' : 'text-slate-300'}">
              {((data.native_prob || 0) * 100).toFixed(1)}%
            </div>
            {#if data.logits && data.logits.length > 0}
              <div class="mt-2 pt-2 border-t border-slate-700/50 text-xs leading-relaxed">
                {#each data.logits as l, i}
                  <span class="{l.is_target ? 'text-emerald-400' : 'text-slate-400'}">{l.token}</span>
                  <span class="text-slate-500 tabular-nums">{(l.prob * 100).toFixed(0)}%</span>
                  {#if i < data.logits.length - 1}<span class="text-slate-600"> | </span>{/if}
                {/each}
              </div>
            {/if}
          </div>
          <div class="p-3 rounded-lg bg-slate-800/50">
            <div class="text-xs text-slate-500 uppercase mb-1">Concept Features</div>
            <div class="text-lg font-bold text-cyan-400">{data.supernode_feature_count || 0}</div>
            <div class="text-xs text-slate-600">{data.pinned_nodes || 0} pinned features / {data.supernodes || 0} supernodes</div>
          </div>
        </div>

        <!-- Attack / Drift -->
        <div class="grid grid-cols-2 gap-3 mb-4">
          <div class="p-3 rounded-lg bg-slate-800/50 border-l-4" style="border-color: {ATTACK_COLOR};"
               title="Measures how strongly this state features pulls other prompts toward itself when its features are amplified.">
            <div class="text-xs text-slate-500 uppercase mb-1">Attack (as target)</div>
            <div class="flex items-baseline gap-2">
              <div class="text-lg font-bold tabular-nums" style="color: {ATTACK_COLOR}; min-width: 2.5rem;">
                {(data.defense_avg || 0).toFixed(2)}
              </div>
              <div class="text-sm text-emerald-400">{((data.defense_success_rate || 0) * 100).toFixed(0)}% T3+</div>
            </div>
            <div class="text-xs text-slate-500">{data.defense_count || 0} swaps</div>
          </div>
          <div class="p-3 rounded-lg bg-slate-800/50 border-l-4" style="border-color: {DRIFT_COLOR};"
               title="Measures how easily this state prompt gets pulled away from its default identity when targeted by another state.">
            <div class="text-xs text-slate-500 uppercase mb-1">Drift (as source)</div>
            <div class="flex items-baseline gap-2">
              <div class="text-lg font-bold tabular-nums" style="color: {DRIFT_COLOR}; min-width: 2.5rem;">
                {(data.attack_avg || 0).toFixed(2)}
              </div>
              <div class="text-sm text-emerald-400">{((data.attack_success_rate || 0) * 100).toFixed(0)}% T3+</div>
            </div>
            <div class="text-xs text-slate-500">{data.attack_count || 0} swaps</div>
          </div>
        </div>

        <!-- Wrong State Rate -->
        {#if data.wrong_state_rate !== undefined && data.wrong_state_rate > 0}
          <div class="p-3 rounded-lg bg-slate-800/50 mb-4">
            <div class="flex items-center justify-between">
              <div class="text-xs text-slate-500 uppercase">Wrong State Rate (T2.5)</div>
              <div class="text-sm font-bold" style="color: #FFE8E8;">{(data.wrong_state_rate * 100).toFixed(1)}%</div>
            </div>
          </div>
        {/if}

        <!-- Features by Layer histogram -->
        {#if histogramRows.length > 0}
          <div class="p-3 rounded-lg bg-slate-800/50 mb-4">
            <div class="flex items-center justify-between mb-2">
              <div class="text-xs text-slate-500 uppercase">Features by Layer</div>
              <div class="flex items-center gap-3 text-xs">
                <span class="flex items-center gap-1">
                  <span class="w-2 h-2 rounded" style="background: {CYAN};"></span>
                  <span class="text-slate-500">Concept ({data.supernode_feature_count || 0})</span>
                </span>
                <span class="flex items-center gap-1">
                  <span class="w-2 h-2 rounded" style="background: {SLATE};"></span>
                  <span class="text-slate-500">Other ({(data.total_features || 0) - (data.supernode_feature_count || 0)})</span>
                </span>
              </div>
            </div>
            <div class="space-y-0.5">
              {#each histogramRows as row}
                <div class="flex items-center gap-1 text-xs">
                  <div class="w-4 text-slate-500 text-right">{row.layer}</div>
                  <div class="flex-1 h-3 flex rounded overflow-hidden bg-slate-700/50">
                    <div style="width: {row.snWidth}%; background: {CYAN};" title="{row.sn} state supernode"></div>
                    <div style="width: {row.otherWidth}%; background: {SLATE};" title="{row.other} other"></div>
                  </div>
                  <div class="w-6 text-slate-500 text-right">{row.total}</div>
                </div>
              {/each}
            </div>
          </div>
        {/if}

        {#if data.has_token_overlap}
          <div class="mt-3 px-3 py-2 bg-amber-900/30 border border-amber-700/50 rounded text-xs text-amber-400 mb-4">
            Token overlap detected
          </div>
        {/if}

        <!-- Swaps as Target -->
        <div class="p-3 rounded-lg bg-slate-800/50 mb-4">
          <button
            class="swap-section-header flex items-center justify-between cursor-pointer hover:bg-slate-700/30 -mx-3 -mt-3 px-3 pt-3 pb-2 rounded-t-lg transition-colors w-full text-left"
            on:click={() => toggleSwaps('target')}
          >
            <div class="text-xs text-slate-500 uppercase">Swaps as Target ({(data.swaps_as_target || []).length})</div>
            <span class="text-xs text-cyan-400">
              {targetSwapsVisible ? (targetSwapsLoaded ? 'Hide' : 'Loading...') : 'Load Outputs'}
            </span>
          </button>
          {#if targetSwapsVisible}
            <div class="swap-list max-h-60 overflow-y-auto space-y-2 mt-2">
              {#if targetOutputsLoading}
                <div class="text-xs text-slate-500 text-center py-2 animate-pulse">Fetching steered outputs...</div>
              {:else if targetOutputs.length > 0}
                {#each targetOutputs as s}
                  <button
                    class="swap-output-row rounded bg-slate-800/30 hover:bg-slate-700/50 transition-colors cursor-pointer w-full text-left"
                    on:click={() => openSwapDetail(s.from_slug, s.to_slug)}
                  >
                    <div class="flex items-center gap-2 px-2 py-1 border-b border-slate-700/50">
                      <span class="text-xs text-slate-500">&lt;-</span>
                      <span class="text-xs text-slate-300 font-medium">{s.from_state}</span>
                      <span class="px-1.5 py-0.5 rounded text-white text-xs font-bold" style="background: {tierBg(s.tier)}; color: {tierText(s.tier)};">
                        T{tierLabel(s.tier)}
                      </span>
                    </div>
                    <div class="px-2 py-1.5 text-xs font-mono text-slate-500 leading-relaxed" style="word-break: break-all;">
                      {truncate(s.steered_output)}
                    </div>
                  </button>
                {/each}
              {:else}
                <div class="text-xs text-slate-500 text-center py-2">No outputs available</div>
              {/if}
            </div>
          {/if}
        </div>

        <!-- Swaps as Source -->
        <div class="p-3 rounded-lg bg-slate-800/50 mb-4">
          <button
            class="swap-section-header flex items-center justify-between cursor-pointer hover:bg-slate-700/30 -mx-3 -mt-3 px-3 pt-3 pb-2 rounded-t-lg transition-colors w-full text-left"
            on:click={() => toggleSwaps('source')}
          >
            <div class="text-xs text-slate-500 uppercase">Swaps as Source ({(data.swaps_as_source || []).length})</div>
            <span class="text-xs text-cyan-400">
              {sourceSwapsVisible ? (sourceSwapsLoaded ? 'Hide' : 'Loading...') : 'Load Outputs'}
            </span>
          </button>
          {#if sourceSwapsVisible}
            <div class="swap-list max-h-60 overflow-y-auto space-y-2 mt-2">
              {#if sourceOutputsLoading}
                <div class="text-xs text-slate-500 text-center py-2 animate-pulse">Fetching steered outputs...</div>
              {:else if sourceOutputs.length > 0}
                {#each sourceOutputs as s}
                  <button
                    class="swap-output-row rounded bg-slate-800/30 hover:bg-slate-700/50 transition-colors cursor-pointer w-full text-left"
                    on:click={() => openSwapDetail(s.from_slug, s.to_slug)}
                  >
                    <div class="flex items-center gap-2 px-2 py-1 border-b border-slate-700/50">
                      <span class="text-xs text-slate-500">-&gt;</span>
                      <span class="text-xs text-slate-300 font-medium">{s.to_state}</span>
                      <span class="px-1.5 py-0.5 rounded text-white text-xs font-bold" style="background: {tierBg(s.tier)}; color: {tierText(s.tier)};">
                        T{tierLabel(s.tier)}
                      </span>
                    </div>
                    <div class="px-2 py-1.5 text-xs font-mono text-slate-500 leading-relaxed" style="word-break: break-all;">
                      {truncate(s.steered_output)}
                    </div>
                  </button>
                {/each}
              {:else}
                <div class="text-xs text-slate-500 text-center py-2">No outputs available</div>
              {/if}
            </div>
          {/if}
        </div>

        <!-- Neuronpedia Subgraph -->
        {#if data.neuronpedia_url}
          <div class="mb-4">
            <button
              class="w-full py-2 px-4 rounded bg-cyan-900/30 hover:bg-cyan-900/50 text-center text-sm text-cyan-400 hover:text-cyan-300 transition-colors border border-cyan-800/50"
              on:click={openSubgraph}
            >
              View Subgraph on Neuronpedia
            </button>
            <div class="text-xs text-slate-600 mt-2 text-center">Embeddings + top logit + features by influence, with supernodes.</div>
          </div>
        {/if}

        <!-- Footer with keyboard hints -->
        <div class="mt-3 text-center text-xs text-slate-600">
          <kbd class="px-1.5 py-0.5 rounded bg-slate-800 text-slate-500">&#8592;</kbd>
          <kbd class="px-1.5 py-0.5 rounded bg-slate-800 text-slate-500">&#8594;</kbd>
          navigate states |
          <kbd class="px-1.5 py-0.5 rounded bg-slate-800 text-slate-500">Esc</kbd> close
        </div>
      {/if}
    </div>
  </div>
{/if}
