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
  
  // Cached subgraph URLs (slug -> url) to avoid repeated API calls
  let subgraphUrlCache = {};
  let sourceSubgraphUrl = null;
  let targetSubgraphUrl = null;
  
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
  
  function handleEscape(event) {
    if (visible && event.key === 'Escape') {
      close();
    }
  }

  onMount(async () => {
    document.addEventListener('cell-selected', handleCellSelected);
    document.addEventListener('keydown', handleEscape);
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
    sourceSubgraphUrl = null;
    targetSubgraphUrl = null;
    
    try {
      const res = await fetch(`/api/swap/${from}/${to}`);
      if (!res.ok) {
        throw new Error('Swap data not found');
      }
      data = await res.json();
      
      // Resolve subgraph URLs in parallel (non-blocking)
      Promise.all([fetchSubgraphUrl(from), fetchSubgraphUrl(to)])
        .then(([srcUrl, tgtUrl]) => {
          sourceSubgraphUrl = srcUrl;
          targetSubgraphUrl = tgtUrl;
        });
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }
  
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
    fromSlug = null;
    toSlug = null;
    sourceSubgraphUrl = null;
    targetSubgraphUrl = null;
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
        
        <!-- Tier badge + Flip badge -->
        {@const flipStatus = SHOW_TRAJECTORY_FEATURES ? getFlipStatus() : null}
        <div class="mb-6 p-4 rounded-lg bg-slate-800/50 border border-slate-700">
          <div class="flex items-center gap-3 mb-2 flex-wrap">
            <div class="px-3 py-1 rounded {info.color} text-white font-bold text-sm">
              TIER {tier}
            </div>
            <div class="{info.textColor} font-semibold">{info.name}</div>
            
            <!-- Flip badge (new) -->
            {#if flipStatus}
              <div
                class="px-2 py-1 rounded {flipStatus.bgColor} {flipStatus.color} font-mono text-xs border border-current/30"
                title={flipStatus.description}
              >
                {flipStatus.badgeLabel}
              </div>
            {/if}
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
        
        <!-- Entity cards -->
        <div class="grid grid-cols-2 gap-4 mb-6">
          {#each [['Source', source, 'text-yellow-400', sourceSubgraphUrl], ['Target', target, 'text-emerald-400', targetSubgraphUrl]] as [role, entity, answerColor, subgraphUrl]}
            <div class="p-3 rounded-lg bg-slate-800/50 border border-slate-700">
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
              {#if subgraphUrl || entity.neuronpedia_url}
                <a href={subgraphUrl || entity.neuronpedia_url} target="_blank"
                   class="inline-block mt-2 text-xs text-cyan-400 hover:underline">
                  Neuronpedia ->
                </a>
              {/if}
            </div>
          {/each}
        </div>
        
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
        
        <!-- Trajectory Metrics (new) -->
        {#if SHOW_TRAJECTORY_FEATURES}
          {@const trajSummary = getTrajectorySummary()}
          {@const trajectory = getTrajectory()}
          
          {#if trajSummary}
            <div class="p-4 rounded-lg bg-slate-800/50 border border-slate-700 mb-6">
              <div class="flex items-start justify-between gap-3 mb-3">
                <div class="flex items-center gap-2 flex-wrap">
                  <div class="text-xs text-slate-500 uppercase">Trajectory Metrics</div>
                  {#if flipStatus}
                    <div
                      class="px-2 py-1 rounded {flipStatus.bgColor} {flipStatus.color} font-mono text-xs border border-current/30"
                      title={flipStatus.description}
                    >
                      {flipStatus.badgeLabel}
                    </div>
                  {/if}
                </div>
                <div
                  class="w-5 h-5 rounded-full border border-slate-600 text-slate-400 flex items-center justify-center text-[11px] cursor-help shrink-0"
                  title="Trajectory metrics compare the target token against the source token across generation positions. Positive gap means the target logit is ahead of the source logit. Flip position is the first step where the target outranks the source. Initial gap is the step-0 margin, best gap is the strongest margin reached later, gap closure measures extra gain after step 0, and specificity measures how much unrelated control tokens drift during the intervention, where lower is better."
                >
                  ?
                </div>
              </div>
              
              <!-- Sparkline -->
              {#if trajSummary.gap_trajectory?.length > 1}
                {@const spark = generateSparklinePath(trajSummary.gap_trajectory)}
                {#if spark}
                  <div
                    class="mb-4 p-3 rounded bg-slate-900/50"
                    title="Gap trajectory tracks target logit minus source logit across generation positions. Above the dashed zero line, the target token is ahead. Below the dashed line, the source token is ahead."
                  >
                    <div class="flex items-center justify-between mb-2">
                      <span class="text-xs text-slate-500">Gap Trajectory</span>
                    </div>
                    <div class="flex justify-between items-center mb-1">
                      <span class="text-[11px] font-medium text-sky-200">
                        {formatTokenLabel(trajectory?.tokens?.target, 'Target')} (Target)
                      </span>
                      <span></span>
                    </div>
                    <svg 
                      class="w-full h-20"
                      viewBox="0 0 {spark.width} {spark.height}"
                      aria-label="Gap trajectory chart"
                    >
                      <!-- Zero reference line -->
                      <line 
                        x1="{spark.padding}" 
                        y1="{spark.zeroY}" 
                        x2="{spark.width - spark.padding}" 
                        y2="{spark.zeroY}" 
                        stroke="rgb(100 116 139)" 
                        stroke-width="1" 
                        stroke-dasharray="2,2"
                      />
                      
                      <!-- Gap trajectory line -->
                      <path 
                        d="{spark.pathD}" 
                        fill="none" 
                        stroke="rgb(56 189 248)" 
                        stroke-width="1.1"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      />
                      
                      <!-- Flip point marker -->
                      {#if spark.flipPoint}
                        <circle 
                          cx="{spark.flipPoint.x}" 
                          cy="{spark.flipPoint.y}" 
                          r="1.8" 
                          fill="rgb(56 189 248)"
                          stroke="rgb(224 242 254)"
                          stroke-width="0.8"
                        />
                      {/if}
                    </svg>
                    <div class="flex justify-between items-center text-xs text-slate-600 mt-1">
                      <div class="flex flex-col items-start gap-1">
                        <span class="text-slate-100">pos 0</span>
                        <span class="text-[11px] text-slate-400">
                          {formatTokenLabel(trajectory?.tokens?.source, 'Source')} (Source)
                        </span>
                      </div>
                      <span>pos {trajSummary.gap_trajectory.length - 1}</span>
                    </div>
                  </div>
                {/if}
              {/if}
              
              <!-- Metrics grid -->
              <div class="grid grid-cols-2 gap-3">
                <!-- Initial Gap -->
                <div
                  class="p-2 rounded bg-slate-900/30"
                  title="Initial gap is the target logit minus the source logit at generation position 0. Positive means the target starts ahead."
                >
                  <div class="text-xs text-slate-500 mb-1">Initial Gap</div>
                  <div class="text-sm font-mono {trajSummary.initial_gap > 0 ? 'text-emerald-400' : trajSummary.initial_gap < 0 ? 'text-red-400' : 'text-slate-400'}">
                    {trajSummary.initial_gap > 0 ? '+' : ''}{formatNum(trajSummary.initial_gap)}
                  </div>
                </div>
                
                <!-- Best Gap -->
                <div
                  class="p-2 rounded bg-slate-900/30"
                  title="Best gap is the maximum target-minus-source margin reached anywhere in the tracked trajectory."
                >
                  <div class="text-xs text-slate-500 mb-1">Best Gap</div>
                  <div class="text-sm font-mono {trajSummary.best_gap > 0 ? 'text-emerald-400' : trajSummary.best_gap < 0 ? 'text-red-400' : 'text-slate-400'}">
                    {trajSummary.best_gap > 0 ? '+' : ''}{formatNum(trajSummary.best_gap)}
                  </div>
                </div>

                <!-- Gap Closure -->
                <div
                  class="p-2 rounded bg-slate-900/30"
                  title="Gap closure is best gap minus initial gap. Positive means the target gained additional advantage after position 0. Zero means the trajectory never improved beyond its starting margin."
                >
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
                
                <!-- Specificity -->
                <div
                  class="p-2 rounded bg-slate-900/30"
                  title="Specificity measures how much unrelated control tokens drift during the intervention. Lower is better because it means the steering is more selective."
                >
                  <div class="text-xs text-slate-500 mb-1">Specificity</div>
                  <div class="flex items-baseline gap-2">
                    <span class="text-sm font-mono text-slate-300">
                      {formatNum(trajSummary.control_stability_mean)}
                    </span>
                    <span class="text-xs {getSpecificityQuality(trajSummary.control_stability_mean).color}">
                      {getSpecificityQuality(trajSummary.control_stability_mean).label}
                    </span>
                  </div>
                </div>
              </div>
              
              <!-- Target rank improvement (if available) -->
              {#if trajectory?.trajectories?.target?.summary}
                {@const targetSum = trajectory.trajectories.target.summary}
                {@const targetBestRank = targetSum.min_rank}
                {@const rankDelta = getRankDeltaInfo(targetSum.rank_improvement)}
                <div class="mt-3 pt-3 border-t border-slate-700/50">
                  <div
                    class="flex items-center justify-between text-sm"
                    title="Best target rank is the highest position the target token reaches anywhere in the tracked trajectory. The number in parentheses shows the improvement relative to the starting rank at pos 0."
                  >
                    <span class="text-slate-500">Best target rank:</span>
                    <span class="font-mono">
                      <span class="text-slate-400">#{targetBestRank ?? '?'}</span>
                      <span class="{rankDelta.color} ml-2">{rankDelta.text}</span>
                    </span>
                  </div>
                  <div
                    class="flex items-center justify-between text-sm mt-1"
                    title="First top-5 is the earliest generation position where the target token enters the model's top-5 candidates. 'never' means it never reached top-5 during the tracked steps."
                  >
                    <span class="text-slate-500">First top-5:</span>
                    <span class="font-mono text-cyan-400">{getFirstTop5Label(targetSum.first_top5_position)}</span>
                  </div>
                </div>
              {/if}
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

