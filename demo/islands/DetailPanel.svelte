<script>
  import { onMount } from 'svelte';
  
  // ===========================================
  // FEATURE FLAGS - flip to false to disable
  // ===========================================
  const SHOW_TRAJECTORY_FEATURES = true;
  
  // State
  let visible = false;
  let loading = false;
  let error = null;
  let data = null;
  let fromSlug = null;
  let toSlug = null;
  let selectedVariant = null;
  
  // Cached subgraph URLs (slug -> url) to avoid repeated API calls
  let subgraphUrlCache = {};
  let sourceSubgraphUrl = null;
  let targetSubgraphUrl = null;

  // Swap features (ablated/amplified per layer)
  let features = null;
  let featuresExpanded = false;
  let contrastGroupExpanded = false;
  let topkExpanded = false;
  let trajectoryExpanded = false;

  // Global variant from the matrix selector (persists across cell selections)
  let globalVariant = null;

  // Variant & control derived data from backend
  $: variants = data?._variants || [];
  $: derived = data?._derived || {};
  $: loadedVariant = data?._loaded_variant || null;
  $: controlMode = derived?.control_mode || null;
  $: fieldsUsed = derived?.fields_used || null;
  $: hasContrastMetrics = derived?.vs_max != null || derived?.rank_in_group != null || derived?.vs_topk != null;
  $: hasPos0Metrics = derived?.vs_max_pos0 != null || derived?.rank_in_group_pos0 != null;
  $: hasTrajMetrics = derived?.initial_gap != null || derived?.best_gap != null || derived?.gap_closure != null;
  
  let domainConfig = null;
  $: isUsaStates = domainConfig?.is_usa_states ?? true;
  $: answerLabel = domainConfig?.answer_field || 'capital';

  const tierInfo = {
    5: { name: 'PERFECT', color: 'bg-emerald-500', textColor: 'text-emerald-400', desc: 'Target answer found in output' },
    4: { name: 'PARTIAL + ANSWER', color: 'bg-lime-500', textColor: 'text-lime-400', desc: 'Target partial match found (not exact answer)' },
    3: { name: 'PARTIAL', color: 'bg-yellow-500', textColor: 'text-yellow-400', desc: 'Target concept mentioned only' },
    2: { name: 'SUPPRESSED', color: 'bg-orange-400', textColor: 'text-orange-400', desc: 'Source suppressed, no target content' },
    1: { name: 'SOURCE PERSISTS', color: 'bg-red-500', textColor: 'text-red-400', desc: 'Source answer still in output' },
    0: { name: 'WRONG ANSWER', color: 'bg-slate-600', textColor: 'text-slate-400', desc: 'Unrelated answer in output' },
  };

  const regimeInfo = {
    A: { label: 'Clean Redirection', color: 'text-emerald-400', bgColor: 'bg-emerald-500/20', borderColor: 'border-emerald-500/30' },
    B: { label: 'Both Boosted', color: 'text-blue-400', bgColor: 'bg-blue-500/20', borderColor: 'border-blue-500/30' },
    C: { label: 'Differential Disruption', color: 'text-yellow-400', bgColor: 'bg-yellow-500/20', borderColor: 'border-yellow-500/30' },
    D: { label: 'Generic Disruption', color: 'text-red-400', bgColor: 'bg-red-500/20', borderColor: 'border-red-500/30' },
    E: { label: 'Pure Suppression', color: 'text-slate-400', bgColor: 'bg-slate-500/20', borderColor: 'border-slate-500/30' },
  };

  function getRegimeInfo() {
    const regime = derived?.regime;
    if (!regime || !regimeInfo[regime]) return null;
    const info = regimeInfo[regime];
    return { regime, ...info };
  }
  
  function handleEscape(event) {
    if (visible && event.key === 'Escape') {
      close();
    }
  }

  function handleVariantChanged(event) {
    globalVariant = event.detail?.variant || null;
  }

  onMount(async () => {
    document.addEventListener('cell-selected', handleCellSelected);
    document.addEventListener('keydown', handleEscape);
    document.addEventListener('variant-changed', handleVariantChanged);
    try {
      const res = await fetch('/api/config');
      if (res.ok) {
        const cfg = await res.json();
        domainConfig = cfg.domain || null;
      }
    } catch {}
    return () => {
      document.removeEventListener('cell-selected', handleCellSelected);
      document.removeEventListener('keydown', handleEscape);
      document.removeEventListener('variant-changed', handleVariantChanged);
    };
  });
  
  async function handleCellSelected(event) {
    const { from, to } = event.detail;
    fromSlug = from;
    toSlug = to;
    selectedVariant = globalVariant;
    visible = true;
    loading = true;
    error = null;
    data = null;
    features = null;
    featuresExpanded = false;
    contrastGroupExpanded = false;
    topkExpanded = false;
    trajectoryExpanded = false;
    sourceSubgraphUrl = null;
    targetSubgraphUrl = null;
    
    const qs = globalVariant ? `?variant=${encodeURIComponent(globalVariant)}` : '';
    try {
      const res = await fetch(`/api/swap/${from}/${to}${qs}`);
      if (!res.ok) {
        throw new Error('Swap data not found');
      }
      data = await res.json();
      
      Promise.all([
        fetchSubgraphUrl(from),
        fetchSubgraphUrl(to),
        fetch(`/api/swap/${from}/${to}/features${qs}`).then(r => r.ok ? r.json() : null).catch(() => null),
      ]).then(([srcUrl, tgtUrl, feat]) => {
        sourceSubgraphUrl = srcUrl;
        targetSubgraphUrl = tgtUrl;
        if (feat && !feat.error) features = feat;
      });
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  async function switchVariant(variantSuffix) {
    if (!fromSlug || !toSlug) return;
    selectedVariant = variantSuffix;
    loading = true;
    error = null;
    features = null;
    featuresExpanded = false;
    trajectoryExpanded = false;
    try {
      const qs = variantSuffix ? `?variant=${encodeURIComponent(variantSuffix)}` : '';
      const res = await fetch(`/api/swap/${fromSlug}/${toSlug}${qs}`);
      if (!res.ok) throw new Error('Variant not found');
      data = await res.json();
      fetch(`/api/swap/${fromSlug}/${toSlug}/features${qs}`)
        .then(r => r.ok ? r.json() : null)
        .then(feat => { if (feat && !feat.error) features = feat; })
        .catch(() => {});
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  function variantLabel(suffix) {
    if (!suffix) return 'Best';
    if (suffix.startsWith('r')) return `Replicate ${suffix.slice(1)}`;
    if (suffix.startsWith('add_')) return suffix.slice(4).replace(/_/g, ' + ');
    return suffix.replace(/_/g, ' ');
  }

  const controlModeLabels = {
    labeled: 'Labeled',
    random_feature_matched: 'Random Control',
    additivity: 'Field Additivity',
  };
  
  async function fetchSubgraphUrl(slug) {
    if (!slug) return null;
    if (subgraphUrlCache[slug]) return subgraphUrlCache[slug];
    try {
      const res = await fetch(`/api/state/${slug}/subgraph-url?max_features=100`);
      if (!res.ok) return null;
      const d = await res.json();
      if (d.url) {
        subgraphUrlCache[slug] = d.url;
        return d.url;
      }
    } catch {}
    return null;
  }
  
  function close() {
    visible = false;
    data = null;
    features = null;
    featuresExpanded = false;
    topkExpanded = false;
    trajectoryExpanded = false;
    fromSlug = null;
    toSlug = null;
    selectedVariant = null;
    sourceSubgraphUrl = null;
    targetSubgraphUrl = null;
  }

  function openConceptPanel(slug) {
    if (!slug) return;
    close();
    document.dispatchEvent(new CustomEvent('show-state-card', {
      detail: { slug },
      bubbles: true,
    }));
  }
  
  // Get tier from classification
  function getTier() {
    if (!data) return null;
    if (data.classification?.tier !== undefined) {
      return data.classification.tier;
    }
    const exact = data.evaluation?.exact_match || {};
    const evaluation = data.evaluation || {};
    const toAnswer = evaluation.to_answer || '';
    const steeredOut = evaluation.raw?.steered_output || '';

    let hit = exact.steered_has_to_capital || exact.steered_has_to_answer;

    if (!hit && toAnswer && steeredOut) {
      const norm = s => s.replace(/\./g, '').replace(/-/g, ' ').toLowerCase();
      if (norm(toAnswer) && norm(steeredOut).includes(norm(toAnswer))) {
        hit = true;
      }
    }

    if (!hit) {
      const steeredFirst = (evaluation.first_token?.steered || '').trim();
      if (steeredFirst.length >= 2 && toAnswer) {
        if (toAnswer.replace(/\./g, '').toLowerCase().includes(steeredFirst.toLowerCase())) {
          hit = true;
        }
      }
    }

    if (!hit && toAnswer && steeredOut) {
      const blacklist = new Set((domainConfig?.tier_word_blacklist || []).map(w => w.toLowerCase()));
      for (const word of toAnswer.replace(/\./g, '').split(/\s+/)) {
        if (word.length >= 3 && !blacklist.has(word.toLowerCase()) && new RegExp('\\b' + word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b', 'i').test(steeredOut)) {
          hit = true;
          break;
        }
      }
    }

    if (hit) return 5;
    if (!exact.from_suppressed) return 1;
    return 2;
  }
  
  function getAnswerValue(entity) {
    if (!entity) return '';
    if (answerLabel && entity[answerLabel]) return entity[answerLabel];
    return entity.capital || entity.answer || '';
  }

  function highlightOutput(text, sourceAnswer, targetAnswer) {
    if (!text) return '';
    let result = text;
    if (targetAnswer) {
      const escaped = targetAnswer.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      result = result.replace(new RegExp(escaped, 'gi'), `<span class="text-emerald-400 font-bold">${targetAnswer}</span>`);
    }
    if (sourceAnswer) {
      const escaped = sourceAnswer.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      result = result.replace(new RegExp(escaped, 'gi'), `<span class="text-red-400 font-bold">${sourceAnswer}</span>`);
    }
    return result;
  }
  
  // ===========================================
  // TRAJECTORY HELPERS
  // ===========================================
  
  // Get trajectory summary safely
  function getTrajectory() {
    if (!data?.evaluation?.logit_trajectory) return null;
    return data.evaluation.logit_trajectory;
  }
  
  // Get trajectory summary metrics
  function getTrajectorySummary() {
    const traj = getTrajectory();
    if (!traj?.summary) return null;
    return traj.summary;
  }
  
  // Get baseline comparison at position 0
  function getPosition0Comparison() {
    return data?.evaluation?.position_0_comparison || null;
  }
  
  // Generate SVG sparkline path for gap trajectory
  function generateSparklinePath(gapTrajectory, width = 120, height = 44) {
    if (!gapTrajectory || gapTrajectory.length < 2) return null;
    
    const padding = 4;
    const w = width - padding * 2;
    const h = height - padding * 2;
    
    // Find min/max for scaling
    const min = Math.min(...gapTrajectory, 0); // include 0 for reference
    const max = Math.max(...gapTrajectory, 0);
    const range = max - min || 1;
    
    // Generate points
    const points = gapTrajectory.map((val, i) => {
      const x = padding + (i / (gapTrajectory.length - 1)) * w;
      const y = padding + h - ((val - min) / range) * h;
      return { x, y, val };
    });
    
    // Create path
    const pathD = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
    
    // Zero line position
    const zeroY = padding + h - ((0 - min) / range) * h;
    
    // Find flip position (first point where val > 0)
    const flipIdx = gapTrajectory.findIndex(v => v > 0);
    const flipPoint = flipIdx >= 0 ? points[flipIdx] : null;
    
    return { pathD, zeroY, points, flipPoint, width, height, padding };
  }
  
  // Format number for display
  function formatNum(val, decimals = 1) {
    if (val === null || val === undefined || isNaN(val)) return 'N/A';
    return val.toFixed(decimals);
  }
  
  function formatTokenLabel(token, fallback) {
    return (token || fallback || '').trim() || fallback;
  }
  
  // Get flip status info
  function getFlipStatus() {
    const summary = getTrajectorySummary();
    const pos0 = getPosition0Comparison();
    
    if (!summary) return null;
    
    const flipPos = summary.flip_position;
    const flipAt0 = pos0?.flip_at_0 ?? (flipPos === 0);
    
    if (flipPos === null || flipPos === undefined) {
      return {
        achieved: false,
        position: null,
        label: 'NO FLIP',
        badgeLabel: 'NO FLIP',
        color: 'text-red-400',
        bgColor: 'bg-red-500/20',
        description: 'The target token never outranks the source token during the tracked generation steps.'
      };
    } else if (flipPos === 0) {
      return {
        achieved: true,
        position: 0,
        label: 'FLIP @ 0 POS',
        badgeLabel: 'FLIP @ 0 POS',
        color: 'text-emerald-400',
        bgColor: 'bg-emerald-500/20',
        description: 'The target token already outranks the source token at generation position 0.'
      };
    } else {
      return {
        achieved: true,
        position: flipPos,
        label: `FLIP @ ${flipPos} POS`,
        badgeLabel: `FLIP @ ${flipPos} POS`,
        color: 'text-yellow-400',
        bgColor: 'bg-yellow-500/20',
        description: `The target token first outranks the source token at generation position ${flipPos}.`
      };
    }
  }
  
  // Get gap closure quality
  function getGapClosureQuality(gapClosure) {
    if (gapClosure === null || gapClosure === undefined) return { label: 'N/A', color: 'text-slate-500' };
    if (gapClosure >= 10) return { label: 'strong', color: 'text-emerald-400' };
    if (gapClosure >= 5) return { label: 'good', color: 'text-lime-400' };
    if (gapClosure > 0) return { label: 'weak', color: 'text-yellow-400' };
    if (gapClosure === 0) return { label: 'neutral', color: 'text-slate-400' };
    return { label: 'negative', color: 'text-red-400' };
  }
  
  // Get specificity quality (lower is better)
  function getSpecificityQuality(stability) {
    if (stability === null || stability === undefined) return { label: 'N/A', color: 'text-slate-500' };
    if (stability < 5) return { label: 'high', color: 'text-emerald-400' };
    if (stability < 10) return { label: 'medium', color: 'text-yellow-400' };
    return { label: 'low', color: 'text-orange-400' };
  }
  
  function getRankDeltaInfo(delta) {
    if (delta === null || delta === undefined) {
      return { text: '(+0)', color: 'text-yellow-400' };
    }
    if (delta > 0) return { text: `(+${delta})`, color: 'text-emerald-400' };
    if (delta < 0) return { text: `(${delta})`, color: 'text-red-400' };
    return { text: '(+0)', color: 'text-yellow-400' };
  }
  
  function getFirstTop5Label(position) {
    if (position === null || position === undefined) return 'never';
    return `position ${position}`;
  }

  function getFeatureLayerRows(feat) {
    if (!feat?.layer_counts) return [];
    const abl = feat.layer_counts.ablated || {};
    const amp = feat.layer_counts.amplified || {};
    const allLayers = new Set([...Object.keys(abl), ...Object.keys(amp)]);
    let maxCount = 1;
    const rows = [];
    for (const l of allLayers) {
      const a = abl[l] || 0;
      const m = amp[l] || 0;
      const total = a + m;
      if (total > maxCount) maxCount = total;
      rows.push({ layer: Number(l), ablated: a, amplified: m, total });
    }
    rows.sort((a, b) => b.layer - a.layer);
    for (const r of rows) {
      r.ablWidth = (r.ablated / maxCount) * 100;
      r.ampWidth = (r.amplified / maxCount) * 100;
    }
    return rows;
  }
</script>

<!-- Backdrop -->
{#if visible}
  <div 
    class="fixed inset-0 bg-black/50 z-40 pointer-events-none"
    aria-hidden="true"
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
        
        {@const sourceAnswer = getAnswerValue(source)}
        {@const targetAnswer = getAnswerValue(target)}
        {@const entityFields = domainConfig?.entity_fields || []}
        
        <!-- Swap header -->
        <div class="mb-6">
          <div class="flex items-center gap-3 mb-2">
            <div class="text-center">
              <div class="text-2xl font-bold">{source.label || source.state || source[domainConfig?.primary_field] || 'Unknown'}</div>
              <div class="text-xs text-slate-500">{source.city || source[domainConfig?.primary_field] || ''}</div>
            </div>
            <div class="text-slate-600 text-2xl">-></div>
            <div class="text-center">
              <div class="text-2xl font-bold">{target.label || target.state || target[domainConfig?.primary_field] || 'Unknown'}</div>
              <div class="text-xs text-slate-500">{target.city || target[domainConfig?.primary_field] || ''}</div>
            </div>
          </div>
        </div>
        
        <!-- Outcome Summary: Tier + Regime + Flip + Primary Metrics (merged) -->
        {@const flipStatus = SHOW_TRAJECTORY_FEATURES ? getFlipStatus() : null}
        {@const regimeStatus = getRegimeInfo()}
        <div class="mb-4 p-3 rounded-lg bg-slate-800/50 border border-slate-700">
          <!-- Badges row -->
          <div class="flex items-center gap-2 mb-2 flex-wrap">
            <div class="px-2.5 py-0.5 rounded {info.color} text-white font-bold text-sm">
              T{tier}
            </div>
            <div class="{info.textColor} font-semibold text-sm">{info.name}</div>
            {#if flipStatus}
              <div
                class="px-2 py-0.5 rounded {flipStatus.bgColor} {flipStatus.color} font-mono text-xs border border-current/30"
                title={flipStatus.description}
              >
                {flipStatus.badgeLabel}
              </div>
            {/if}
          </div>
          <!-- Regime display: badge + label on first row, logit direction on second -->
          {#if regimeStatus}
            {@const tgtDir = derived.target_logit_delta > 0 ? 'UP' : derived.target_logit_delta < -1 ? 'DOWN' : 'FLAT'}
            {@const srcDir = derived.source_logit_delta < -1 ? 'DOWN' : derived.source_logit_delta > 0 ? 'UP' : 'FLAT'}
            {@const tgtColor = tgtDir === 'UP' ? 'text-emerald-400' : tgtDir === 'DOWN' ? 'text-red-400' : 'text-slate-400'}
            {@const srcColor = srcDir === 'UP' ? 'text-emerald-400' : srcDir === 'DOWN' ? 'text-red-400' : 'text-slate-400'}
            <div
              class="mb-2 cursor-help"
              title="Regime {regimeStatus.regime}: {regimeStatus.label}&#10;&#10;A  Tgt UP   Src DOWN  flip=yes  Clean redirection&#10;B  Tgt UP   Src UP    flip=--   Both boosted&#10;C  Tgt DOWN  Src DOWN  flip=yes  Differential disruption&#10;D  Tgt DOWN  Src DOWN  flip=no   Generic disruption&#10;E  Tgt FLAT  Src DOWN  flip=yes  Pure suppression"
            >
              <div class="flex items-center gap-2 text-xs">
                <span class="px-1.5 py-0.5 rounded {regimeStatus.bgColor} {regimeStatus.color} font-bold border {regimeStatus.borderColor}">{regimeStatus.regime}</span>
                <span class="{regimeStatus.color} font-medium">{regimeStatus.label}</span>
              </div>
              <div class="flex items-center gap-4 text-xs mt-1 ml-7">
                <span class="text-slate-500">Target <span class="{tgtColor} font-mono font-bold">{tgtDir}</span></span>
                <span class="text-slate-500">Source <span class="{srcColor} font-mono font-bold">{srcDir}</span></span>
              </div>
            </div>
          {/if}
          {#if data.classification?.notes}
            <p class="text-xs text-slate-500 mb-1">{data.classification.notes}</p>
          {/if}
          <!-- Primary metrics: dual-row table (pos0 / best) when contrast data exists, inline fallback otherwise -->
          {#if hasContrastMetrics}
            <div class="pt-2 border-t border-slate-700/50">
              <table class="w-full text-xs">
                <thead>
                  <tr>
                    <th class="text-left text-[10px] text-slate-600 uppercase font-normal pb-1 w-14"></th>
                    {#if hasPos0Metrics}
                      <th class="text-right text-[10px] text-slate-500 uppercase font-normal pb-1 pr-2"
                          title="Value at generation position 0 -- the direct causal effect before autoregressive feedback.">pos0</th>
                    {/if}
                    <th class="text-right text-[10px] text-slate-500 uppercase font-normal pb-1"
                        title="Best value across the full generation trajectory (typically 11 positions).">{hasPos0Metrics ? 'best' : ''}</th>
                  </tr>
                </thead>
                <tbody>
                  {#if derived.vs_max != null}
                    <tr title="Target logit minus max other dataset answer. Positive = target beats all alternatives.">
                      <td class="text-slate-500 uppercase py-0.5">vsMax</td>
                      {#if hasPos0Metrics}
                        <td class="text-right font-mono font-bold pr-2 {derived.vs_max_pos0 != null ? (derived.vs_max_pos0 > 0 ? 'text-emerald-400/80' : derived.vs_max_pos0 > -2 ? 'text-yellow-400/80' : 'text-red-400/80') : 'text-slate-600'}">
                          {derived.vs_max_pos0 != null ? (derived.vs_max_pos0 > 0 ? '+' : '') + formatNum(derived.vs_max_pos0) : '--'}
                        </td>
                      {/if}
                      <td class="text-right font-mono font-bold {derived.vs_max > 0 ? 'text-emerald-400' : derived.vs_max > -2 ? 'text-yellow-400' : 'text-red-400'}">
                        {derived.vs_max > 0 ? '+' : ''}{formatNum(derived.vs_max)}
                      </td>
                    </tr>
                  {/if}
                  {#if derived.rank_in_group != null}
                    <tr title="Rank of target among all {derived.contrast_n ?? '?'} dataset answer tokens (1 = top).">
                      <td class="text-slate-500 uppercase py-0.5">RkGrp</td>
                      {#if hasPos0Metrics}
                        <td class="text-right font-mono font-bold pr-2 {derived.rank_in_group_pos0 != null ? (derived.rank_in_group_pos0 === 1 ? 'text-emerald-400/80' : derived.rank_in_group_pos0 <= 3 ? 'text-yellow-400/80' : 'text-red-400/80') : 'text-slate-600'}">
                          {derived.rank_in_group_pos0 != null ? derived.rank_in_group_pos0 : '--'}
                        </td>
                      {/if}
                      <td class="text-right font-mono font-bold {derived.rank_in_group === 1 ? 'text-emerald-400' : derived.rank_in_group <= 3 ? 'text-yellow-400' : 'text-red-400'}">
                        {derived.rank_in_group}
                      </td>
                    </tr>
                  {/if}
                  {#if derived.vs_topk != null}
                    <tr title="Target logit minus mean top-{derived.contrast_topk_k ?? 3} other dataset answers.">
                      <td class="text-slate-500 uppercase py-0.5">vsTopK</td>
                      {#if hasPos0Metrics}
                        <td class="text-right font-mono font-bold pr-2 {derived.vs_topk_pos0 != null ? (derived.vs_topk_pos0 > 0 ? 'text-emerald-400/80' : derived.vs_topk_pos0 > -2 ? 'text-yellow-400/80' : 'text-red-400/80') : 'text-slate-600'}">
                          {derived.vs_topk_pos0 != null ? (derived.vs_topk_pos0 > 0 ? '+' : '') + formatNum(derived.vs_topk_pos0) : '--'}
                        </td>
                      {/if}
                      <td class="text-right font-mono font-bold {derived.vs_topk > 0 ? 'text-emerald-400' : derived.vs_topk > -2 ? 'text-yellow-400' : 'text-red-400'}">
                        {derived.vs_topk > 0 ? '+' : ''}{formatNum(derived.vs_topk)}
                      </td>
                    </tr>
                  {/if}
                </tbody>
              </table>
            </div>
          {:else if hasTrajMetrics}
            <div class="flex items-center gap-3 pt-2 border-t border-slate-700/50 flex-wrap">
              {#if derived.initial_gap != null}
                <div class="flex items-baseline gap-1" title="Target logit minus source logit at generation position 0.">
                  <span class="text-[10px] text-slate-500 uppercase">Gap0</span>
                  <span class="text-sm font-mono font-bold {derived.initial_gap > 0 ? 'text-emerald-400' : derived.initial_gap < 0 ? 'text-red-400' : 'text-slate-400'}">{derived.initial_gap > 0 ? '+' : ''}{formatNum(derived.initial_gap)}</span>
                </div>
              {/if}
              {#if derived.best_gap != null}
                <div class="flex items-baseline gap-1" title="Maximum target-minus-source margin across all generation positions.">
                  <span class="text-[10px] text-slate-500 uppercase">BestGap</span>
                  <span class="text-sm font-mono font-bold {derived.best_gap > 0 ? 'text-emerald-400' : derived.best_gap < 0 ? 'text-red-400' : 'text-slate-400'}">{derived.best_gap > 0 ? '+' : ''}{formatNum(derived.best_gap)}</span>
                </div>
              {/if}
              {#if derived.gap_closure != null}
                <div class="flex items-baseline gap-1" title="Best gap minus initial gap. Positive = target gained advantage.">
                  <span class="text-[10px] text-slate-500 uppercase">Closure</span>
                  <span class="text-sm font-mono font-bold {derived.gap_closure > 0 ? 'text-emerald-400' : derived.gap_closure < 0 ? 'text-red-400' : 'text-slate-400'}">{derived.gap_closure > 0 ? '+' : ''}{formatNum(derived.gap_closure)}</span>
                </div>
              {/if}
            </div>
          {/if}
          <!-- Contrast group members (collapsible) -->
          {#if derived.contrast_members && derived.contrast_members.length > 0}
            <div class="mt-2 pt-1">
              <button
                class="text-xs text-slate-500 hover:text-slate-300 transition-colors w-full text-left"
                on:click={() => contrastGroupExpanded = !contrastGroupExpanded}
              >
                {contrastGroupExpanded ? 'Hide' : 'Show'} competing answers ({derived.contrast_n})
              </button>
              {#if contrastGroupExpanded}
                <div class="mt-2 flex flex-wrap gap-1">
                  {#each derived.contrast_members as member}
                    <span
                      class="px-1.5 py-0.5 rounded text-xs font-mono {member.token.trim() === (data?.target?.answer || data?.evaluation?.to_answer || '').trim() ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-slate-700/50 text-slate-400'}"
                      title="token_id: {member.token_id}"
                    >{member.token.trim()}</span>
                  {/each}
                </div>
                <div class="text-xs text-slate-600 mt-1">Target must outrank these to achieve RkGrp = 1</div>
              {/if}
            </div>
          {/if}
        </div>
        
        <!-- Entity cards -->
        <div class="grid grid-cols-2 gap-4 mb-6">
          {#each [['Source', source, 'text-yellow-400', sourceSubgraphUrl, fromSlug], ['Target', target, 'text-emerald-400', targetSubgraphUrl, toSlug]] as [role, entity, answerColor, subgraphUrl, entitySlug]}
            <div
              class="p-3 rounded-lg bg-slate-800/50 border border-slate-700 transition-colors cursor-pointer hover:bg-slate-800/80 hover:border-slate-600 focus:outline-none focus:ring-2 focus:ring-cyan-500/70"
              role="button"
              tabindex="0"
              aria-label={`Open concept panel for ${entity.label || entity.state || entity[domainConfig?.primary_field] || entity.slug || role}`}
              on:click={() => openConceptPanel(entity.slug || entitySlug)}
              on:keydown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  openConceptPanel(entity.slug || entitySlug);
                }
              }}
            >
              <div class="text-xs text-slate-500 uppercase mb-2">{role}</div>
              <div class="text-sm font-semibold">{entity.label || entity.state || entity[domainConfig?.primary_field] || entity.slug || ''}</div>
              {#each entityFields.filter(f => f !== (domainConfig?.primary_field || '') && entity[f]) as field}
                <div class="text-xs text-slate-400">
                  <span class="capitalize">{field}:</span>
                  <span class={field === answerLabel ? answerColor : ''}>{entity[field]}</span>
                </div>
              {/each}
              {#if !entityFields.length && entity.capital}
                <div class="text-xs text-slate-400">Capital: <span class={answerColor}>{entity.capital}</span></div>
              {/if}
              {#if entity.error_node_influence_pct != null}
                <div
                  class="mt-2 text-xs"
                  title="Percentage of graph influence attributed to CLT reconstruction-error nodes. Higher values mean more of the computation is invisible to the pipeline."
                >
                  <span class="text-slate-500">Error Influence</span>
                  <span class="font-mono ml-1 {entity.error_node_influence_pct > 50 ? 'text-amber-400' : entity.error_node_influence_pct > 30 ? 'text-slate-300' : 'text-emerald-400'}">
                    {entity.error_node_influence_pct.toFixed(1)}%
                  </span>
                </div>
              {/if}
              {#if subgraphUrl || entity.neuronpedia_url}
                <a href={subgraphUrl || entity.neuronpedia_url} target="_blank"
                   class="inline-block mt-2 text-xs text-cyan-400 hover:underline"
                   on:click|stopPropagation>
                  Neuronpedia ->
                </a>
              {/if}
            </div>
          {/each}
        </div>

        <!-- Control + Variant selector -->
        {#if (controlMode && controlMode !== 'labeled') || variants.length > 0}
          <div class="mb-4 p-3 rounded-lg bg-indigo-500/10 border border-indigo-500/30">
            {#if controlMode && controlMode !== 'labeled'}
              <div class="flex items-center gap-2 flex-wrap {variants.length > 0 ? 'mb-2' : ''}">
                <span class="px-2 py-0.5 rounded text-xs font-bold bg-indigo-500/30 text-indigo-300">
                  {controlModeLabels[controlMode] || controlMode}
                </span>
                {#if fieldsUsed && fieldsUsed.length > 0}
                  <span class="text-xs text-slate-400">Fields: {fieldsUsed.join(', ')}</span>
                {/if}
                {#if derived.replicate_id != null}
                  <span class="text-xs text-slate-500">Replicate #{derived.replicate_id}</span>
                {/if}
              </div>
            {/if}
            {#if variants.length > 0}
              <div class="flex flex-wrap gap-1.5">
                <button
                  class="px-2 py-1 text-xs rounded transition-colors {!selectedVariant ? 'bg-cyan-900/50 text-cyan-400 border border-cyan-500/40' : 'bg-slate-700 text-slate-400 hover:bg-slate-600 border border-transparent'}"
                  on:click={() => switchVariant(null)}
                >Best</button>
                {#each variants as v}
                  <button
                    class="px-2 py-1 text-xs rounded transition-colors {selectedVariant === v.variant_suffix ? 'bg-cyan-900/50 text-cyan-400 border border-cyan-500/40' : 'bg-slate-700 text-slate-400 hover:bg-slate-600 border border-transparent'}"
                    on:click={() => switchVariant(v.variant_suffix)}
                    title="Tier {v.tier ?? '?'} | Flip {v.flip_position ?? 'N/A'}"
                  >{variantLabel(v.variant_suffix)}</button>
                {/each}
              </div>
            {/if}
          </div>
        {/if}

        <!-- Outputs -->
        <div class="space-y-4 mb-6">
          <div>
            <div class="text-xs text-slate-500 uppercase mb-2">Default Output</div>
            <div class="p-3 rounded bg-slate-800 text-sm font-mono text-slate-300 overflow-x-auto">
              {@html highlightOutput(raw.default_output?.slice(0, 200) || 'N/A', sourceAnswer, targetAnswer)}
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
              {@html highlightOutput(raw.steered_output?.slice(0, 200) || 'N/A', sourceAnswer, targetAnswer)}
            </div>
          </div>
        </div>
        
        <!-- First token analysis -->
        {@const defaultTopk = raw.default_topk || []}
        {@const steeredTopk = raw.steered_topk || []}
        {@const hasTopk = defaultTopk.length > 0 || steeredTopk.length > 0}
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

          {#if hasTopk}
            <button
              class="w-full flex items-center justify-between mt-3 pt-2 border-t border-slate-700/50 hover:bg-slate-700/20 rounded px-1 py-1 transition-colors text-left"
              on:click={() => topkExpanded = !topkExpanded}
            >
              <span class="text-xs text-slate-500">Top {Math.max(defaultTopk.length, steeredTopk.length)} tokens</span>
              <svg class="w-4 h-4 text-slate-500 transition-transform {topkExpanded ? 'rotate-180' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {#if topkExpanded}
              <div class="grid grid-cols-2 gap-4 mt-2">
                <div class="space-y-1">
                  {#each defaultTopk as tok, i}
                    <div class="flex items-baseline gap-1.5">
                      <span class="text-xs text-slate-600 w-3 text-right shrink-0">{i + 1}.</span>
                      <span class="text-xs font-mono text-yellow-400 truncate" title={tok.token}>'{tok.token}'</span>
                      <span class="text-xs text-slate-600 ml-auto shrink-0">{(tok.prob || 0).toFixed(3)}</span>
                    </div>
                  {/each}
                </div>
                <div class="space-y-1">
                  {#each steeredTopk as tok, i}
                    <div class="flex items-baseline gap-1.5">
                      <span class="text-xs text-slate-600 w-3 text-right shrink-0">{i + 1}.</span>
                      <span class="text-xs font-mono text-cyan-400 truncate" title={tok.token}>'{tok.token}'</span>
                      <span class="text-xs text-slate-600 ml-auto shrink-0">{(tok.prob || 0).toFixed(3)}</span>
                    </div>
                  {/each}
                </div>
              </div>
            {/if}
          {/if}
        </div>
        
        <!-- Trajectory section -->
        {#if SHOW_TRAJECTORY_FEATURES}
          {@const trajSummary = getTrajectorySummary()}
          {@const trajectory = getTrajectory()}

          {#if trajSummary}
            <div class="p-4 rounded-lg bg-slate-800/50 border border-slate-700 mb-6">
              <!-- Always-visible: target rank + initial/best gap summary -->
              <div class="flex items-start justify-between gap-3 mb-2">
                <div class="text-xs text-slate-500 uppercase">Trajectory</div>
                <div
                  class="w-5 h-5 rounded-full border border-slate-600 text-slate-400 flex items-center justify-center text-[11px] cursor-help shrink-0"
                  title="Trajectory metrics compare the target token against the source token across generation positions. Positive gap = target logit ahead of source."
                >?</div>
              </div>

              <!-- Compact always-visible summary row -->
              <div class="grid grid-cols-2 gap-2 mb-2">
                <div class="p-2 rounded bg-slate-900/30" title="Target logit minus source logit at position 0.">
                  <div class="text-xs text-slate-500 mb-0.5">Initial Gap</div>
                  <div class="text-sm font-mono {trajSummary.initial_gap > 0 ? 'text-emerald-400' : trajSummary.initial_gap < 0 ? 'text-red-400' : 'text-slate-400'}">
                    {trajSummary.initial_gap > 0 ? '+' : ''}{formatNum(trajSummary.initial_gap)}
                  </div>
                </div>
                <div class="p-2 rounded bg-slate-900/30" title="Maximum target-minus-source margin across all positions.">
                  <div class="text-xs text-slate-500 mb-0.5">Best Gap</div>
                  <div class="text-sm font-mono {trajSummary.best_gap > 0 ? 'text-emerald-400' : trajSummary.best_gap < 0 ? 'text-red-400' : 'text-slate-400'}">
                    {trajSummary.best_gap > 0 ? '+' : ''}{formatNum(trajSummary.best_gap)}
                  </div>
                </div>
              </div>

              <!-- Target rank (always visible) -->
              {#if trajectory?.trajectories?.target?.summary}
                {@const targetSum = trajectory.trajectories.target.summary}
                {@const targetBestRank = targetSum.min_rank}
                {@const unsteeredRank = evaluation.baseline_logits?.target?.rank}
                {@const rankDeltaVsUnsteered = (unsteeredRank != null && targetBestRank != null) ? unsteeredRank - targetBestRank : null}
                {@const rankDelta = getRankDeltaInfo(rankDeltaVsUnsteered)}
                <div class="flex items-center justify-between text-sm mb-1" title="Best position the target token reaches in the trajectory.">
                  <span class="text-slate-500">Best target rank:</span>
                  <span class="font-mono">
                    <span class="text-slate-400">#{targetBestRank ?? '?'}</span>
                    <span class="{rankDelta.color} ml-2">{rankDelta.text}</span>
                  </span>
                </div>
                <div class="flex items-center justify-between text-sm" title="Earliest position where target enters model's top-5.">
                  <span class="text-slate-500">First top-5:</span>
                  <span class="font-mono text-cyan-400">{getFirstTop5Label(targetSum.first_top5_position)}</span>
                </div>
              {/if}

              <!-- Collapsible: Sparkline + Gap Closure + Specificity -->
              <div class="mt-3 pt-2 border-t border-slate-700/50">
                <button
                  class="w-full flex items-center justify-between hover:bg-slate-700/20 rounded px-1 py-1 transition-colors text-left"
                  on:click={() => trajectoryExpanded = !trajectoryExpanded}
                >
                  <span class="text-xs text-slate-500">Gap trajectory & details</span>
                  <svg class="w-4 h-4 text-slate-500 transition-transform {trajectoryExpanded ? 'rotate-180' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                  </svg>
                </button>

                {#if trajectoryExpanded}
                  <!-- Sparkline -->
                  {#if trajSummary.gap_trajectory?.length > 1}
                    {@const spark = generateSparklinePath(trajSummary.gap_trajectory)}
                    {#if spark}
                      <div class="mt-3 p-3 rounded bg-slate-900/50">
                        <div class="flex items-center justify-between mb-2">
                          <span class="text-xs text-slate-500">Gap Trajectory</span>
                        </div>
                        <div class="flex justify-between items-center mb-1">
                          <span class="text-[11px] font-medium text-sky-200">
                            {formatTokenLabel(trajectory?.tokens?.target, 'Target')} (Target)
                          </span>
                          <span></span>
                        </div>
                        <svg class="w-full h-20" viewBox="0 0 {spark.width} {spark.height}" aria-label="Gap trajectory chart">
                          <line x1="{spark.padding}" y1="{spark.zeroY}" x2="{spark.width - spark.padding}" y2="{spark.zeroY}" stroke="rgb(100 116 139)" stroke-width="1" stroke-dasharray="2,2" />
                          <path d="{spark.pathD}" fill="none" stroke="rgb(56 189 248)" stroke-width="1.1" stroke-linecap="round" stroke-linejoin="round" />
                          {#if spark.flipPoint}
                            <circle cx="{spark.flipPoint.x}" cy="{spark.flipPoint.y}" r="1.8" fill="rgb(56 189 248)" stroke="rgb(224 242 254)" stroke-width="0.8" />
                          {/if}
                        </svg>
                        <div class="flex justify-between items-center text-xs text-slate-600 mt-1">
                          <div class="flex flex-col items-start gap-1">
                            <span class="text-slate-100">pos 0</span>
                            <span class="text-[11px] text-slate-400">{formatTokenLabel(trajectory?.tokens?.source, 'Source')} (Source)</span>
                          </div>
                          <span>pos {trajSummary.gap_trajectory.length - 1}</span>
                        </div>
                      </div>
                    {/if}
                  {/if}

                  <!-- Gap Closure + Specificity -->
                  <div class="grid grid-cols-2 gap-3 mt-3">
                    <div class="p-2 rounded bg-slate-900/30" title="Best gap minus initial gap. Positive = target gained advantage after pos 0.">
                      <div class="text-xs text-slate-500 mb-1">Gap Closure</div>
                      <div class="flex items-baseline gap-2">
                        <span class="text-sm font-mono {trajSummary.gap_closure > 0 ? 'text-emerald-400' : trajSummary.gap_closure < 0 ? 'text-red-400' : 'text-slate-400'}">
                          {trajSummary.gap_closure > 0 ? '+' : ''}{formatNum(trajSummary.gap_closure)}
                        </span>
                        <span class="text-xs {getGapClosureQuality(trajSummary.gap_closure).color}">
                          {getGapClosureQuality(trajSummary.gap_closure).label}
                        </span>
                      </div>
                    </div>
                    <div class="p-2 rounded bg-slate-900/30" title="Control token drift during intervention. Lower is better.">
                      <div class="text-xs text-slate-500 mb-1">Specificity</div>
                      <div class="flex items-baseline gap-2">
                        <span class="text-sm font-mono text-slate-300">{formatNum(trajSummary.control_stability_mean)}</span>
                        <span class="text-xs {getSpecificityQuality(trajSummary.control_stability_mean).color}">
                          {getSpecificityQuality(trajSummary.control_stability_mean).label}
                        </span>
                      </div>
                    </div>
                  </div>
                {/if}
              </div>
            </div>
          {/if}
        {/if}
        
        <!-- Status indicators -->
        <div class="p-4 rounded-lg bg-slate-800/50 border border-slate-700 mb-6">
          <div class="text-xs text-slate-500 uppercase mb-3">Status</div>
          <div class="space-y-2">
            <div class="flex items-center justify-between text-sm">
              <span class="text-slate-400">Target {answerLabel} in steered:</span>
              {#if exact.steered_has_to_capital || exact.steered_has_to_answer}
                <span class="text-emerald-400">Yes</span>
              {:else}
                <span class="text-red-400">No</span>
              {/if}
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
          {@const ablCount = features?.summary?.ablate_count ?? data.interventions.ablate_count ?? 0}
          {@const ampCount = features?.summary?.amplify_count ?? data.interventions.amplify_count ?? 0}
          {@const totCount = features?.summary?.total_count ?? data.interventions.total_count ?? 0}
          {@const layerRows = features ? getFeatureLayerRows(features) : []}
          <div class="p-4 rounded-lg bg-slate-800/50 border border-slate-700">
            <div class="flex items-center justify-between mb-3">
              <div class="text-xs text-slate-500 uppercase">Interventions</div>
              <div class="flex gap-4 text-xs">
                <span><span class="font-bold text-red-400">{ablCount}</span> <span class="text-slate-500">ablated</span></span>
                <span><span class="font-bold text-emerald-400">{ampCount}</span> <span class="text-slate-500">amplified</span></span>
                <span><span class="font-bold text-slate-400">{totCount}</span> <span class="text-slate-500">total</span></span>
              </div>
            </div>

            <!-- Features by Layer chart -->
            {#if layerRows.length > 0}
              <div class="mb-3">
                <div class="text-xs text-slate-500 uppercase mb-2">Features by Layer</div>
                <div class="space-y-0.5">
                  {#each layerRows as row}
                    <div class="flex items-center gap-1 text-xs">
                      <div class="w-5 text-slate-500 text-right font-mono">{row.layer}</div>
                      <div class="flex-1 h-3 flex rounded overflow-hidden bg-slate-700/50">
                        <div style="width: {row.ablWidth}%; background: #f87171;" title="{row.ablated} ablated"></div>
                        <div style="width: {row.ampWidth}%; background: #4ade80;" title="{row.amplified} amplified"></div>
                      </div>
                      <div class="w-5 text-slate-500 text-right">{row.total}</div>
                    </div>
                  {/each}
                </div>
                <div class="flex items-center gap-4 mt-2 text-xs">
                  <span class="flex items-center gap-1">
                    <span class="w-2.5 h-2.5 rounded" style="background: #f87171;"></span>
                    <span class="text-slate-500">Ablated (source)</span>
                  </span>
                  <span class="flex items-center gap-1">
                    <span class="w-2.5 h-2.5 rounded" style="background: #4ade80;"></span>
                    <span class="text-slate-500">Amplified (target)</span>
                  </span>
                </div>
              </div>
            {/if}

            <!-- Expandable feature links -->
            {#if features && totCount > 0}
              <button
                class="w-full flex items-center justify-between py-2 px-1 hover:bg-slate-700/30 rounded transition-colors text-left"
                on:click={() => featuresExpanded = !featuresExpanded}
              >
                <span class="text-xs text-slate-400">View {totCount} feature links</span>
                <svg class="w-4 h-4 text-slate-500 transition-transform {featuresExpanded ? 'rotate-180' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {#if featuresExpanded}
                <div class="mt-2 space-y-4">
                  <!-- Ablated features -->
                  {#if features.ablated?.length > 0}
                    <div>
                      <div class="text-xs text-slate-500 uppercase mb-1.5">Ablated ({features.ablated.length})</div>
                      <div class="space-y-0.5">
                        {#each features.ablated as feat}
                          <a
                            href={feat.neuronpedia_url}
                            target="_blank"
                            class="flex items-center gap-2 py-1 px-2 rounded hover:bg-slate-700/40 transition-colors group"
                          >
                            <span class="text-xs text-slate-300 font-mono shrink-0">L{feat.layer} #{feat.index}</span>
                            {#if feat.supernode_name}
                              <span class="text-xs text-slate-500 truncate">{feat.supernode_name}</span>
                            {/if}
                            <span class="text-xs text-cyan-400 opacity-60 group-hover:opacity-100 ml-auto shrink-0">-></span>
                          </a>
                        {/each}
                      </div>
                    </div>
                  {/if}

                  <!-- Amplified features -->
                  {#if features.amplified?.length > 0}
                    <div>
                      <div class="text-xs text-slate-500 uppercase mb-1.5">Amplified ({features.amplified.length})</div>
                      <div class="space-y-0.5">
                        {#each features.amplified as feat}
                          <a
                            href={feat.neuronpedia_url}
                            target="_blank"
                            class="flex items-center gap-2 py-1 px-2 rounded hover:bg-slate-700/40 transition-colors group"
                          >
                            <span class="text-xs text-slate-300 font-mono shrink-0">L{feat.layer} #{feat.index}</span>
                            {#if feat.supernode_name}
                              <span class="text-xs text-slate-500 truncate">{feat.supernode_name}</span>
                            {/if}
                            <span class="text-xs text-cyan-400 opacity-60 group-hover:opacity-100 ml-auto shrink-0">-></span>
                          </a>
                        {/each}
                      </div>
                    </div>
                  {/if}
                </div>
              {/if}
            {/if}
          </div>
        {/if}

        <!-- Source / Target groupings -->
        {#if features && (features.source_groupings?.length > 0 || features.target_groupings?.length > 0)}
          <div class="p-4 rounded-lg bg-slate-800/50 border border-slate-700 mt-4">
            <div class="text-xs text-slate-500 uppercase mb-3">Groupings</div>
            <div class="grid grid-cols-2 gap-4">

              <!-- Source groupings -->
              {#if features.source_groupings?.length > 0}
                {@const srcAblated = features.source_groupings.filter(g => g.ablated)}
                {@const srcNotAblated = features.source_groupings.filter(g => !g.ablated)}
                <div>
                  <div class="text-xs text-slate-400 font-semibold mb-2">Source</div>
                  {#if srcAblated.length > 0}
                    <div class="mb-2">
                      <div class="text-xs text-red-400/70 uppercase mb-1">Ablated ({srcAblated.length})</div>
                      <div class="space-y-0.5">
                        {#each srcAblated as g}
                          <div class="text-xs text-slate-300 px-1 py-0.5 rounded bg-red-500/10 border border-red-500/20 truncate" title={`${g.name} (${g.feature_count ?? 0})`}>
                            {g.name} ({g.feature_count ?? 0})
                          </div>
                        {/each}
                      </div>
                    </div>
                  {/if}
                  {#if srcNotAblated.length > 0}
                    <div>
                      <div class="text-xs text-slate-500 uppercase mb-1">Not ablated ({srcNotAblated.length})</div>
                      <div class="space-y-0.5">
                        {#each srcNotAblated as g}
                          <div class="text-xs text-slate-500 px-1 py-0.5 rounded bg-slate-700/30 truncate" title={`${g.name} (${g.feature_count ?? 0})`}>
                            {g.name} ({g.feature_count ?? 0})
                          </div>
                        {/each}
                      </div>
                    </div>
                  {/if}
                </div>
              {/if}

              <!-- Target groupings -->
              {#if features.target_groupings?.length > 0}
                {@const tgtAmplified = features.target_groupings.filter(g => g.amplified)}
                {@const tgtNotAmplified = features.target_groupings.filter(g => !g.amplified)}
                <div>
                  <div class="text-xs text-slate-400 font-semibold mb-2">Target</div>
                  {#if tgtAmplified.length > 0}
                    <div class="mb-2">
                      <div class="text-xs text-emerald-400/70 uppercase mb-1">Amplified ({tgtAmplified.length})</div>
                      <div class="space-y-0.5">
                        {#each tgtAmplified as g}
                          <div class="text-xs text-slate-300 px-1 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20 truncate" title={`${g.name} (${g.feature_count ?? 0})`}>
                            {g.name} ({g.feature_count ?? 0})
                          </div>
                        {/each}
                      </div>
                    </div>
                  {/if}
                  {#if tgtNotAmplified.length > 0}
                    <div>
                      <div class="text-xs text-slate-500 uppercase mb-1">Not amplified ({tgtNotAmplified.length})</div>
                      <div class="space-y-0.5">
                        {#each tgtNotAmplified as g}
                          <div class="text-xs text-slate-500 px-1 py-0.5 rounded bg-slate-700/30 truncate" title={`${g.name} (${g.feature_count ?? 0})`}>
                            {g.name} ({g.feature_count ?? 0})
                          </div>
                        {/each}
                      </div>
                    </div>
                  {/if}
                </div>
              {/if}

            </div>
          </div>
        {/if}

        <!-- Links -->
        <div class="mt-6 flex gap-2">
          {#if sourceSubgraphUrl || source.neuronpedia_url}
            <a 
              href={sourceSubgraphUrl || source.neuronpedia_url}
              target="_blank"
              class="flex-1 py-2 px-4 rounded bg-slate-800 hover:bg-slate-700 text-center text-sm text-cyan-400 transition-colors"
            >
              Source Subgraph
            </a>
          {/if}
          {#if targetSubgraphUrl || target.neuronpedia_url}
            <a 
              href={targetSubgraphUrl || target.neuronpedia_url}
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

