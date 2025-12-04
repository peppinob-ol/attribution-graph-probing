/**
 * Matrix Island - Vanilla JS implementation
 * Interactive 50x50 heatmap grid for state swap results
 */

class MatrixIsland {
  constructor(container) {
    this.container = container;
    this.matrix = {};
    this.states = [];
    this.annotated = new Set(); // Track annotated swap keys
    this.selected = null;
    this.hoveredCell = null;
    this.sortBy = 'alpha';
    this.colorblindMode = localStorage.getItem('colorblindMode') === 'true';
    this.stateCardVisible = false;
    this.stateCardData = null;
    
    // Default color palette (blue to red)
    this.defaultColors = {
      5: { bg: '#0A4FFF', hover: '#3D7DFF' },    // PERFECT - deep blue
      4: { bg: '#3D7DFF', hover: '#6B9FFF' },    // STATE+CITY - medium blue
      3: { bg: '#AFCBFF', hover: '#C7DAFF' },    // STATE ONLY - light blue
      2.5: { bg: '#FFE8E8', hover: '#FFF0F0' },  // WRONG STATE - very light red
      2: { bg: '#FF7373', hover: '#FF9999' },    // SUPPRESSED - medium red
      1: { bg: '#C00000', hover: '#E00000' },    // SOURCE PERSISTS - deep red
      0: { bg: '#475569', hover: '#64748b' },
      null: { bg: '#1e293b', hover: '#334155' },
    };
    
    // Colorblind-friendly palette (blue-orange, distinct shapes)
    this.colorblindColors = {
      5: { bg: '#0077BB', hover: '#33A0DD' },    // PERFECT - dark blue
      4: { bg: '#33BBEE', hover: '#66CCFF' },    // STATE+CITY - cyan
      3: { bg: '#EE7733', hover: '#FF9955' },    // STATE ONLY - orange
      2.5: { bg: '#CCBB44', hover: '#DDCC66' },  // WRONG STATE - yellow
      2: { bg: '#EE3377', hover: '#FF5599' },    // SUPPRESSED - magenta
      1: { bg: '#AA3377', hover: '#CC5599' },    // SOURCE PERSISTS - purple
      0: { bg: '#475569', hover: '#64748b' },
      null: { bg: '#1e293b', hover: '#334155' },
    };
    
    this.tierColors = this.colorblindMode ? this.colorblindColors : this.defaultColors;
    
    this.init();
  }
  
  toggleColorblindMode() {
    this.colorblindMode = !this.colorblindMode;
    localStorage.setItem('colorblindMode', this.colorblindMode);
    this.tierColors = this.colorblindMode ? this.colorblindColors : this.defaultColors;
    this.renderMatrix();
    
    // Notify other components (like DetailPanel)
    document.dispatchEvent(new CustomEvent('colorblind-mode-changed', {
      detail: { colorblindMode: this.colorblindMode },
    }));
  }
  
  async init() {
    this.render('<div class="py-20 text-center text-slate-500 animate-pulse">Loading matrix data...</div>');
    
    try {
      const [matrixRes, statesRes, annotatedRes] = await Promise.all([
        fetch('/api/matrix'),
        fetch('/api/states'),
        fetch('/api/annotated'),
      ]);
      
      if (!matrixRes.ok || !statesRes.ok) {
        throw new Error('Failed to load data');
      }
      
      this.matrix = await matrixRes.json();
      this.states = await statesRes.json();
      
      // Load annotated swaps
      if (annotatedRes.ok) {
        const annotatedList = await annotatedRes.json();
        annotatedList.forEach(item => {
          this.annotated.add(`${item.from}:${item.to}`);
        });
      }
      
      this.renderMatrix();
      
      // Listen for external cell selection (from keyboard navigation)
      document.addEventListener('cell-selected', (e) => {
        this.updateSelection(e.detail.from, e.detail.to);
      });
      
      // Listen for annotation saves to update cells and stats
      document.addEventListener('annotation-saved', (e) => {
        this.handleAnnotationSaved(e.detail);
      });
      
      // Listen for state card requests from DetailPanel
      document.addEventListener('show-state-card', (e) => {
        this.showStateCard(e.detail.slug);
      });
      
      // Keyboard navigation for state card
      document.addEventListener('keydown', (e) => {
        if (this.stateCardVisible) {
          if (e.key === 'ArrowLeft') {
            e.preventDefault();
            this.navigateStateCard('prev');
          } else if (e.key === 'ArrowRight') {
            e.preventDefault();
            this.navigateStateCard('next');
          } else if (e.key === 'Escape') {
            e.preventDefault();
            this.closeStateCard();
          }
        }
      });
    } catch (e) {
      this.render(`<div class="py-20 text-center text-red-400">Error: ${e.message}</div>`);
    }
  }
  
  handleAnnotationSaved(detail) {
    const { from, to, tier, stats } = detail;
    
    // Update matrix data
    if (tier !== undefined && this.matrix[from]) {
      this.matrix[from][to] = tier;
    }
    
    // Mark as annotated
    this.annotated.add(`${from}:${to}`);
    
    // Update cell visually
    const cell = this.container.querySelector(`.matrix-cell[data-from="${from}"][data-to="${to}"]`);
    if (cell && tier !== undefined) {
      const colors = this.getTierColor(tier);
      cell.style.backgroundColor = colors.bg;
      cell.dataset.tier = tier;
      cell.title = cell.title.replace(/Tier \d/, `Tier ${tier}`);
      
      // Add edited indicator (small dot)
      if (!cell.querySelector('.edited-indicator')) {
        const dot = document.createElement('span');
        dot.className = 'edited-indicator';
        dot.style.cssText = 'position: absolute; top: 1px; right: 1px; width: 4px; height: 4px; background: #fbbf24; border-radius: 50%;';
        cell.style.position = 'relative';
        cell.appendChild(dot);
      }
    }
    
    // Update stats on page
    if (stats) {
      this.updatePageStats(stats);
    }
  }
  
  updatePageStats(stats) {
    // Update stat cards on the home page
    const aggregate = stats.aggregate || {};
    
    // Find and update stat elements
    const statCards = document.querySelectorAll('.max-w-7xl .grid > div');
    
    statCards.forEach(card => {
      const title = card.querySelector('p')?.textContent?.toLowerCase() || '';
      const valueEl = card.querySelectorAll('p')[1];
      
      if (!valueEl) return;
      
      if (title.includes('total')) {
        valueEl.textContent = stats.total_swaps || 0;
      } else if (title.includes('perfect')) {
        valueEl.textContent = `${Math.round((aggregate.perfect_rate || 0) * 100)}%`;
      } else if (title.includes('state correct')) {
        valueEl.textContent = `${Math.round((aggregate.state_correct_rate || 0) * 100)}%`;
      } else if (title.includes('suppression')) {
        valueEl.textContent = `${Math.round((aggregate.suppression_rate || 0) * 100)}%`;
      }
    });
  }
  
  updateSelection(fromSlug, toSlug) {
    // Update internal state
    this.selected = { from: fromSlug, to: toSlug };
    
    // Update visual selection
    const cells = this.container.querySelectorAll('.matrix-cell');
    cells.forEach(cell => {
      const isSelected = cell.dataset.from === fromSlug && cell.dataset.to === toSlug;
      cell.classList.toggle('selected', isSelected);
      
      if (isSelected) {
        // Scroll cell into view if needed
        cell.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
        
        // Add a persistent highlight for selected cell
        cell.style.transform = 'scale(2)';
        cell.style.zIndex = '20';
        cell.style.boxShadow = '0 0 0 3px rgba(34, 211, 238, 1), 0 0 12px rgba(34, 211, 238, 0.5)';
        cell.style.outline = '2px solid #22d3ee';
        cell.style.outlineOffset = '1px';
      } else {
        // Reset all styles for non-selected cells
        cell.style.transform = '';
        cell.style.zIndex = '';
        cell.style.boxShadow = '';
        cell.style.outline = '';
        cell.style.outlineOffset = '';
      }
    });
    
    // Update hover info
    const hoverInfo = this.container.querySelector('#hover-info');
    if (hoverInfo && fromSlug !== toSlug) {
      const fromState = this.states.find(s => s.slug === fromSlug);
      const toState = this.states.find(s => s.slug === toSlug);
      const tier = this.getTier(fromSlug, toSlug);
      
      if (fromState && toState && hoverInfo) {
        hoverInfo.innerHTML = `
          <span class="text-slate-300 font-medium">${fromState.state}</span>
          <span class="text-slate-500 mx-2">-></span>
          <span class="text-slate-300 font-medium">${toState.state}</span>
          ${tier !== null ? `
            <span class="ml-3 px-2 py-0.5 rounded text-xs font-bold" style="background: ${this.getTierColor(tier).bg}; color: ${this.getTierTextColor(tier)};">
              T${tier === 2.5 ? 'W' : tier}
            </span>
          ` : '<span class="ml-3 text-slate-600">No data</span>'}
        `;
      }
    }
  }
  
  render(html) {
    this.container.innerHTML = html;
  }
  
  getSortedStates() {
    return [...this.states].sort((a, b) => {
      switch (this.sortBy) {
        case 'alpha': return a.state.localeCompare(b.state);
        case 'native_prob': return (b.native_prob || 0) - (a.native_prob || 0);
        case 'supernodes': return (b.supernodes || 0) - (a.supernodes || 0);
        case 'src_tier': return (b.src_tier || 0) - (a.src_tier || 0);
        case 'tgt_tier': return (b.tgt_tier || 0) - (a.tgt_tier || 0);
        default: return 0;
      }
    });
  }
  
  getTier(fromSlug, toSlug) {
    if (fromSlug === toSlug) return null;
    return this.matrix[fromSlug]?.[toSlug] ?? null;
  }
  
  getTierColor(tier) {
    return this.tierColors[tier] || this.tierColors[null];
  }
  
  // Get contrasting text color for tier labels in colorblind mode
  getTierTextColor(tier) {
    // Light backgrounds need dark text, dark backgrounds need light text
    const darkTextTiers = [3, 2.5]; // Light blue, light pink/yellow need dark text
    return darkTextTiers.includes(tier) ? '#1e293b' : '#ffffff';
  }
  
  renderMatrix() {
    const sortedStates = this.getSortedStates();
    
    if (sortedStates.length === 0) {
      this.render('<div class="py-20 text-center text-slate-500">No states found</div>');
      return;
    }
    
    const sortOptions = [
      { value: 'alpha', label: 'A-Z' },
      { value: 'native_prob', label: 'Native Prob' },
      { value: 'supernodes', label: 'Supernodes' },
      { value: 'src_tier', label: 'Source Tier' },
      { value: 'tgt_tier', label: 'Target Tier' },
    ];
    
    let html = `
      <div class="matrix-wrapper">
        <!-- Controls -->
        <div class="flex items-center justify-between gap-4 mb-4">
          <div class="flex items-center gap-4">
            <span class="text-xs text-slate-500">Sort by:</span>
            <div class="flex gap-2" id="sort-buttons">
              ${sortOptions.map(opt => `
                <button
                  class="px-2 py-1 text-xs rounded transition-colors ${this.sortBy === opt.value ? 'bg-cyan-900/50 text-cyan-400' : 'bg-slate-800 text-slate-400 hover:bg-slate-700'}"
                  data-sort="${opt.value}"
                >${opt.label}</button>
              `).join('')}
            </div>
          </div>
          <div class="flex items-center gap-2">
            <button
              id="colorblind-toggle"
              class="px-3 py-1 text-xs rounded transition-colors flex items-center gap-2 ${this.colorblindMode ? 'bg-amber-900/50 text-amber-400' : 'bg-slate-800 text-slate-400 hover:bg-slate-700'}"
              title="Toggle colorblind-friendly palette"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
              </svg>
              ${this.colorblindMode ? 'Colorblind: ON' : 'Colorblind: OFF'}
            </button>
          </div>
        </div>
        
        <!-- Hover info (above matrix) -->
        <div id="hover-info" class="mb-1 px-3 py-2 bg-slate-800/50 rounded-lg text-sm flex items-center" style="min-height: 32px;">
          <span class="text-slate-500 text-xs">Hover over a cell to see details</span>
        </div>
        
        <div class="overflow-x-auto">
          <div class="inline-block">
            <!-- Header row -->
            <div style="display: flex;">
              <div style="width: 64px; height: 64px; flex-shrink: 0;"></div>
              ${sortedStates.map(state => `
                <div style="width: 16px; height: 64px; flex-shrink: 0; position: relative;" title="${state.state} (${state.city})">
                  <button 
                    class="state-label-col"
                    data-slug="${state.slug}"
                    style="position: absolute; bottom: 0; left: 50%; transform: translateX(-50%) rotate(-45deg); transform-origin: bottom left; font-size: 10px; color: #64748b; white-space: nowrap; background: none; border: none; cursor: pointer; padding: 0;"
                  >
                    ${state.abbr}
                  </button>
                </div>
              `).join('')}
            </div>
            
            <!-- Matrix rows -->
            ${sortedStates.map(rowState => `
              <div style="display: flex;">
                <div style="width: 64px; height: 16px; flex-shrink: 0; display: flex; align-items: center; justify-content: flex-end; padding-right: 8px;" title="${rowState.state} (${rowState.city})">
                  <button class="state-label-row hover:text-cyan-400" data-slug="${rowState.slug}" style="font-size: 10px; color: #64748b; background: none; border: none; cursor: pointer; padding: 0;">
                    ${rowState.abbr}
                  </button>
                </div>
                ${sortedStates.map(colState => {
                  const tier = this.getTier(rowState.slug, colState.slug);
                  const isIdentity = rowState.slug === colState.slug;
                  const colors = this.getTierColor(tier);
                  const isSelected = this.selected?.from === rowState.slug && this.selected?.to === colState.slug;
                  const isAnnotated = this.annotated.has(`${rowState.slug}:${colState.slug}`);
                  
                  // Annotated indicator (small yellow dot)
                  const annotatedIndicator = isAnnotated ? 
                    '<span class="edited-indicator" style="position: absolute; top: 1px; right: 1px; width: 4px; height: 4px; background: #fbbf24; border-radius: 50%;"></span>' : '';
                  
                  // Tier label for colorblind mode (show number in cell)
                  const tierLabel = this.colorblindMode && tier !== null && !isIdentity ? 
                    `<span style="font-size: 8px; font-weight: bold; color: ${this.getTierTextColor(tier)}; pointer-events: none;">${tier === 2.5 ? 'W' : tier}</span>` : '';
                  
                  return `
                    <button
                      class="matrix-cell ${isSelected ? 'selected' : ''}"
                      style="width: 16px; height: 16px; flex-shrink: 0; border-radius: 2px; border: none; cursor: ${isIdentity || tier === null ? 'default' : 'pointer'}; background-color: ${isIdentity ? '#0f172a' : colors.bg}; transition: all 100ms ease; position: relative; display: flex; align-items: center; justify-content: center;"
                      data-from="${rowState.slug}"
                      data-to="${colState.slug}"
                      data-tier="${tier}"
                      ${isIdentity || tier === null ? 'disabled' : ''}
                      title="${isIdentity ? 'Identity' : tier !== null ? `${rowState.abbr} -> ${colState.abbr}: Tier ${tier}${isAnnotated ? ' (edited)' : ''}` : 'No data'}"
                    >${tierLabel}${annotatedIndicator}</button>
                  `;
                }).join('')}
              </div>
            `).join('')}
          </div>
        </div>
      </div>
    `;
    
    this.render(html);
    this.attachEventListeners();
  }
  
  attachEventListeners() {
    // Sort buttons
    const sortButtons = this.container.querySelectorAll('#sort-buttons button');
    sortButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        this.sortBy = btn.dataset.sort;
        this.renderMatrix();
      });
    });
    
    // Colorblind toggle
    const colorblindToggle = this.container.querySelector('#colorblind-toggle');
    if (colorblindToggle) {
      colorblindToggle.addEventListener('click', () => {
        this.toggleColorblindMode();
      });
    }
    
    // Matrix cells
    const cells = this.container.querySelectorAll('.matrix-cell');
    const hoverInfo = this.container.querySelector('#hover-info');
    
    cells.forEach(cell => {
      if (cell.disabled) return;
      
      cell.addEventListener('click', () => {
        const from = cell.dataset.from;
        const to = cell.dataset.to;
        
        // Update visual selection
        this.updateSelection(from, to);
        
        // Dispatch event for detail panel
        document.dispatchEvent(new CustomEvent('cell-selected', {
          detail: { from, to },
          bubbles: true,
        }));
      });
      
      cell.addEventListener('mouseenter', () => {
        const from = cell.dataset.from;
        const to = cell.dataset.to;
        const tier = cell.dataset.tier;
        
        const fromState = this.states.find(s => s.slug === from);
        const toState = this.states.find(s => s.slug === to);
        
        if (hoverInfo && fromState && toState) {
          const tierNum = tier === 'null' ? null : parseFloat(tier);
          hoverInfo.innerHTML = `
            <span class="text-slate-300 font-medium">${fromState.state}</span>
            <span class="text-slate-500 mx-2">-></span>
            <span class="text-slate-300 font-medium">${toState.state}</span>
            ${tierNum !== null ? `
              <span class="ml-3 px-2 py-0.5 rounded text-xs font-bold" style="background: ${this.getTierColor(tierNum).bg}; color: ${this.getTierTextColor(tierNum)};">
                T${tierNum === 2.5 ? 'W' : tierNum}
              </span>
            ` : '<span class="ml-3 text-slate-600">No data</span>'}
          `;
        }
        
        // Only apply hover effect if NOT the selected cell
        const isSelected = this.selected?.from === from && this.selected?.to === to;
        if (!isSelected) {
          cell.style.transform = 'scale(1.5)';
          cell.style.zIndex = '10';
        }
      });
      
      cell.addEventListener('mouseleave', () => {
        if (hoverInfo) {
          hoverInfo.innerHTML = '<span class="text-slate-500 text-xs">Hover over a cell to see details</span>';
        }
        
        // Only reset styles if NOT the selected cell
        const from = cell.dataset.from;
        const to = cell.dataset.to;
        const isSelected = this.selected?.from === from && this.selected?.to === to;
        
        if (!isSelected) {
          cell.style.transform = '';
          cell.style.zIndex = '';
        }
      });
    });
    
    // State label click handlers (show state card)
    const stateLabels = this.container.querySelectorAll('.state-label-row, .state-label-col');
    stateLabels.forEach(label => {
      label.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        this.showStateCard(label.dataset.slug);
      });
      
      label.addEventListener('mouseenter', () => {
        label.style.color = '#22d3ee';
      });
      
      label.addEventListener('mouseleave', () => {
        label.style.color = '#64748b';
      });
    });
  }
  
  async showStateCard(slug) {
    // Close any existing card
    this.closeStateCard();
    
    // Create card container
    const card = document.createElement('div');
    card.id = 'state-card';
    card.className = 'fixed inset-0 z-50 flex items-center justify-center';
    card.innerHTML = `
      <div class="state-card-backdrop absolute inset-0 bg-black/60" onclick="this.parentElement.remove()"></div>
      <div class="state-card-content relative bg-slate-900 rounded-xl shadow-2xl border border-slate-700 p-6 max-w-lg w-full mx-4" style="max-height: 90vh; overflow-y: auto;">
        <div class="text-center py-8 text-slate-500 animate-pulse">Loading state profile...</div>
      </div>
    `;
    document.body.appendChild(card);
    this.stateCardVisible = true;
    
    // Fetch profile data
    try {
      const res = await fetch(`/api/state/${slug}/profile`);
      if (!res.ok) throw new Error('Failed to load profile');
      
      this.stateCardData = await res.json();
      this.renderStateCard(card.querySelector('.state-card-content'));
    } catch (e) {
      card.querySelector('.state-card-content').innerHTML = `
        <div class="text-center py-8 text-red-400">Error: ${e.message}</div>
        <button onclick="this.closest('#state-card').remove()" class="mt-4 w-full py-2 bg-slate-800 hover:bg-slate-700 rounded text-sm text-slate-400">Close</button>
      `;
    }
  }
  
  closeStateCard() {
    const existing = document.getElementById('state-card');
    if (existing) existing.remove();
    this.stateCardVisible = false;
    this.stateCardData = null;
  }
  
  renderStateCard(container) {
    const d = this.stateCardData;
    if (!d) return;
    
    // Build stacked feature layer histogram (layer 22 at top, layer 0 at bottom)
    // Blue = state supernode features, Gray = other features
    let histogramHTML = '';
    const layerCounts = d.feature_layers || {};
    const supernodeLayerCounts = d.supernode_layer_counts || {};
    const maxCount = Math.max(...Object.values(layerCounts), 1);
    
    for (let layer = 22; layer >= 0; layer--) {
      const total = layerCounts[layer] || 0;
      const supernode = supernodeLayerCounts[layer] || 0;
      const other = total - supernode;
      
      if (total === 0) continue;
      
      const supernodeWidth = (supernode / maxCount) * 100;
      const otherWidth = (other / maxCount) * 100;
      
      histogramHTML += `
        <div class="flex items-center gap-1 text-xs">
          <div class="w-4 text-slate-500 text-right">${layer}</div>
          <div class="flex-1 h-3 flex rounded overflow-hidden bg-slate-700/50">
            <div style="width: ${supernodeWidth}%; background: #22d3ee;" title="${supernode} state supernode"></div>
            <div style="width: ${otherWidth}%; background: #475569;" title="${other} other"></div>
          </div>
          <div class="w-6 text-slate-500 text-right">${total}</div>
        </div>
      `;
    }
    
    // Overlap warning
    const overlapWarning = d.has_token_overlap ? `
      <div class="mt-3 px-3 py-2 bg-amber-900/30 border border-amber-700/50 rounded text-xs text-amber-400">
        Token overlap: city name contains state name
      </div>
    ` : '';
    
    // Build swap summary tables
    const swapsAsTarget = d.swaps_as_target || [];
    const swapsAsSource = d.swaps_as_source || [];
    
    // Build warning badges with alert icon
    const warnings = [];
    const warnIcon = `<svg class="inline-block w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>`;
    
    if ((d.native_prob || 0) < 0.20 && (d.native_prob || 0) > 0) {
      warnings.push({ text: 'Low native prob', color: '#fbbf24' });
    }
    if ((d.native_prob || 0) > 0.50) {
      warnings.push({ text: 'High native prob', color: '#fbbf24' });
    }
    if ((d.supernodes || 0) > 280) {
      warnings.push({ text: 'High supernode count', color: '#fbbf24' });
    }
    if (d.capital_is_top_logit === false && d.capital_in_logits === true) {
      warnings.push({ text: 'Capital not top logit', color: '#f87171' });
    }
    if (d.capital_in_logits === false) {
      warnings.push({ text: 'Capital absent from logits', color: '#f87171' });
    }
    if (d.has_token_overlap) {
      warnings.push({ text: 'Token overlap (city has state name)', color: '#f87171' });
    }
    
    const warningsHTML = warnings.length > 0 ? `
      <div class="flex flex-wrap gap-1 mt-2 justify-center">
        ${warnings.map(w => `<span class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium" style="background: ${w.color}22; color: ${w.color};">${warnIcon}${w.text}</span>`).join('')}
      </div>
    ` : '';
    
    // Get current state index for navigation
    const sortedStates = this.getSortedStates();
    const currentIndex = sortedStates.findIndex(s => s.slug === d.slug);
    const prevState = currentIndex > 0 ? sortedStates[currentIndex - 1] : null;
    const nextState = currentIndex < sortedStates.length - 1 ? sortedStates[currentIndex + 1] : null;
    
    container.innerHTML = `
      <div class="flex items-center justify-between mb-4">
        <button class="state-nav-btn prev-state w-8 h-8 flex items-center justify-center rounded hover:bg-slate-800 text-slate-400 hover:text-white ${prevState ? '' : 'opacity-30 cursor-not-allowed'}" 
                data-slug="${prevState?.slug || ''}" ${prevState ? '' : 'disabled'} title="${prevState ? prevState.state : 'No previous state'}">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <div class="flex-1 text-center">
          <div class="text-center leading-tight">
            <h2 class="text-xl font-bold text-white mb-0">${d.state}</h2>
            ${d.neuronpedia_url ? `
              <button class="subgraph-btn px-2 py-0 rounded text-xs bg-cyan-900/40 hover:bg-cyan-900/60 text-cyan-400 border border-cyan-700/60 transition-colors"
                      data-slug="${d.slug}" title="View subgraph on Neuronpedia">
                view subgraph&#128279;
              </button>
            ` : ''}
          </div>
          <div class="text-sm text-slate-400">
            <span>Capital: <span class="text-emerald-400">${d.capital || '?'}</span></span>
            <span class="mx-2 text-slate-600">|</span>
            <span>City: ${d.city}</span>
          </div>
          ${warningsHTML}
        </div>
        <button class="state-nav-btn next-state w-8 h-8 flex items-center justify-center rounded hover:bg-slate-800 text-slate-400 hover:text-white ${nextState ? '' : 'opacity-30 cursor-not-allowed'}"
                data-slug="${nextState?.slug || ''}" ${nextState ? '' : 'disabled'} title="${nextState ? nextState.state : 'No next state'}">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
          </svg>
        </button>
        <button onclick="this.closest('#state-card').remove()" class="w-8 h-8 flex items-center justify-center rounded hover:bg-slate-800 text-slate-400 hover:text-white ml-2" title="Close (Esc)">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
      
      <!-- Key metrics -->
      <div class="grid grid-cols-2 gap-3 mb-4">
        <div class="p-3 rounded-lg bg-slate-800/50">
          <div class="text-xs text-slate-500 uppercase mb-1">Native Prob</div>
          <div class="text-lg font-bold ${(d.native_prob || 0) < 0.2 ? 'text-amber-400' : (d.native_prob || 0) > 0.5 ? 'text-emerald-400' : 'text-slate-300'}">
            ${((d.native_prob || 0) * 100).toFixed(1)}%
          </div>
          ${d.logits && d.logits.length > 0 ? `
            <div class="mt-2 pt-2 border-t border-slate-700/50 text-xs leading-relaxed">
              ${d.logits.map((l, i) => `<span class="${l.is_target ? 'text-emerald-400' : 'text-slate-400'}">${l.token}</span> <span class="text-slate-500 tabular-nums">${(l.prob * 100).toFixed(0)}%</span>${i < d.logits.length - 1 ? ' <span class="text-slate-600">|</span> ' : ''}`).join('')}
            </div>
          ` : ''}
        </div>
        <div class="p-3 rounded-lg bg-slate-800/50">
          <div class="text-xs text-slate-500 uppercase mb-1">State Features</div>
          <div class="text-lg font-bold text-cyan-400">${d.supernode_feature_count || 0}</div>
          <div class="text-xs text-slate-600">${d.pinned_nodes || 0} pinned features / ${d.supernodes || 0} supernodes</div>
        </div>
      </div>
      
      <!-- Attack (as target) / Drift (as source) -->
      <div class="grid grid-cols-2 gap-3 mb-4">
        <div class="p-3 rounded-lg bg-slate-800/50 border-l-4" style="border-color: #3D7DFF;" title="Measures how strongly this state features pulls other prompts toward itself when its features are amplified.">
          <div class="text-xs text-slate-500 uppercase mb-1">Attack (as target)</div>
          <div class="flex items-baseline gap-2">
            <div class="text-lg font-bold tabular-nums" style="color: #3D7DFF; min-width: 2.5rem;">${(d.defense_avg || 0).toFixed(2)}</div>
            <div class="text-sm text-emerald-400">${((d.defense_success_rate || 0) * 100).toFixed(0)}% T3+</div>
          </div>
          <div class="text-xs text-slate-500">${d.defense_count || 0} swaps</div>
        </div>
        <div class="p-3 rounded-lg bg-slate-800/50 border-l-4" style="border-color: #f87171;" title="Measures how easily this state prompt gets pulled away from its default identity when targeted by another state.">
          <div class="text-xs text-slate-500 uppercase mb-1">Drift (as source)</div>
          <div class="flex items-baseline gap-2">
            <div class="text-lg font-bold tabular-nums" style="color: #f87171; min-width: 2.5rem;">${(d.attack_avg || 0).toFixed(2)}</div>
            <div class="text-sm text-emerald-400">${((d.attack_success_rate || 0) * 100).toFixed(0)}% T3+</div>
          </div>
          <div class="text-xs text-slate-500">${d.attack_count || 0} swaps</div>
        </div>
      </div>
      
      <!-- Wrong State Rate -->
      ${d.wrong_state_rate !== undefined && d.wrong_state_rate > 0 ? `
        <div class="p-3 rounded-lg bg-slate-800/50 mb-4">
          <div class="flex items-center justify-between">
            <div class="text-xs text-slate-500 uppercase">Wrong State Rate (T2.5)</div>
            <div class="text-sm font-bold" style="color: #FFE8E8;">${(d.wrong_state_rate * 100).toFixed(1)}%</div>
          </div>
        </div>
      ` : ''}
      
      <!-- Feature distribution with legend -->
      ${histogramHTML ? `
        <div class="p-3 rounded-lg bg-slate-800/50 mb-4">
          <div class="flex items-center justify-between mb-2">
            <div class="text-xs text-slate-500 uppercase">Features by Layer</div>
            <div class="flex items-center gap-3 text-xs">
              <span class="flex items-center gap-1">
                <span class="w-2 h-2 rounded" style="background: #22d3ee;"></span>
                <span class="text-slate-500">State (${d.supernode_feature_count || 0})</span>
              </span>
              <span class="flex items-center gap-1">
                <span class="w-2 h-2 rounded" style="background: #475569;"></span>
                <span class="text-slate-500">Other (${(d.total_features || 0) - (d.supernode_feature_count || 0)})</span>
              </span>
            </div>
          </div>
          <div class="space-y-0.5">
            ${histogramHTML}
          </div>
        </div>
      ` : ''}
      
      ${overlapWarning}
      
      <!-- Swap results as target (others attacking this state) -->
      <div class="p-3 rounded-lg bg-slate-800/50 mb-4">
        <div class="swap-section-header flex items-center justify-between cursor-pointer hover:bg-slate-700/30 -mx-3 -mt-3 px-3 pt-3 pb-2 rounded-t-lg transition-colors"
             data-target="swaps-target" data-type="target" data-loaded="false">
          <div class="text-xs text-slate-500 uppercase">Swaps as Target (${swapsAsTarget.length})</div>
          <span class="swap-toggle-label text-xs text-cyan-400">Load Outputs</span>
        </div>
        <div id="swaps-target" class="hidden">
          <div class="swap-list max-h-60 overflow-y-auto space-y-2">
            <div class="text-xs text-slate-500 text-center py-2">Loading...</div>
          </div>
        </div>
      </div>
      
      <!-- Swap results as source (this state defending) -->
      <div class="p-3 rounded-lg bg-slate-800/50 mb-4">
        <div class="swap-section-header flex items-center justify-between cursor-pointer hover:bg-slate-700/30 -mx-3 -mt-3 px-3 pt-3 pb-2 rounded-t-lg transition-colors"
             data-target="swaps-source" data-type="source" data-loaded="false">
          <div class="text-xs text-slate-500 uppercase">Swaps as Source (${swapsAsSource.length})</div>
          <span class="swap-toggle-label text-xs text-cyan-400">Load Outputs</span>
        </div>
        <div id="swaps-source" class="hidden">
          <div class="swap-list max-h-60 overflow-y-auto space-y-2">
            <div class="text-xs text-slate-500 text-center py-2">Loading...</div>
          </div>
        </div>
      </div>
      
      <!-- Neuronpedia Subgraph -->
      ${d.neuronpedia_url ? `
        <div class="mb-4">
          <button class="subgraph-btn w-full py-2 px-4 rounded bg-cyan-900/30 hover:bg-cyan-900/50 text-center text-sm text-cyan-400 hover:text-cyan-300 transition-colors border border-cyan-800/50"
                  data-slug="${d.slug}">
            View Subgraph on Neuronpedia
          </button>
          <div class="text-xs text-slate-600 mt-2 text-center">Embeddings + top logit + features by influence, with supernodes.</div>
        </div>
      ` : ''}
      
      <div class="mt-3 text-center text-xs text-slate-600">
        <kbd class="px-1.5 py-0.5 rounded bg-slate-800 text-slate-500">&#8592;</kbd>
        <kbd class="px-1.5 py-0.5 rounded bg-slate-800 text-slate-500">&#8594;</kbd>
        navigate states |
        <kbd class="px-1.5 py-0.5 rounded bg-slate-800 text-slate-500">Esc</kbd> close
      </div>
    `;
    
    // Attach event handlers for swap tables
    this.attachStateCardHandlers(container);
  }
  
  attachStateCardHandlers(container) {
    // Toggle headers for swap tables - now with lazy loading (entire bar clickable)
    container.querySelectorAll('.swap-section-header').forEach(header => {
      header.addEventListener('click', async () => {
        const targetId = header.dataset.target;
        const type = header.dataset.type;
        const loaded = header.dataset.loaded === 'true';
        const target = container.querySelector(`#${targetId}`);
        const label = header.querySelector('.swap-toggle-label');
        
        if (!target || !label) return;
        
        // If hidden, show it
        if (target.classList.contains('hidden')) {
          target.classList.remove('hidden');
          
          // Load outputs if not already loaded
          if (!loaded) {
            label.textContent = 'Loading...';
            await this.loadSwapOutputs(container, type);
            header.dataset.loaded = 'true';
            label.textContent = 'Hide';
          } else {
            label.textContent = 'Hide';
          }
        } else {
          target.classList.add('hidden');
          label.textContent = loaded ? 'Show' : 'Load Outputs';
        }
      });
    });
    
    // Navigation buttons
    container.querySelectorAll('.state-nav-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const slug = btn.dataset.slug;
        if (slug) {
          this.showStateCard(slug);
        }
      });
    });
    
    // Subgraph button
    container.querySelectorAll('.subgraph-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const slug = btn.dataset.slug;
        if (!slug) return;
        
        const originalText = btn.textContent;
        btn.textContent = 'Loading...';
        btn.disabled = true;
        
        try {
          const res = await fetch(`/api/state/${slug}/subgraph-url?max_features=100`);
          if (!res.ok) throw new Error('Failed to generate subgraph URL');
          
          const data = await res.json();
          if (data.url) {
            window.open(data.url, '_blank');
          } else {
            throw new Error('No URL returned');
          }
        } catch (err) {
          console.error('Subgraph error:', err);
          alert('Could not generate subgraph URL');
        } finally {
          btn.textContent = originalText;
          btn.disabled = false;
        }
      });
    });
  }
  
  getSortedStates() {
    // Return states sorted according to current sort mode
    const sorted = [...this.states];
    if (this.sortBy === 'alpha') {
      sorted.sort((a, b) => a.state.localeCompare(b.state));
    } else if (this.sortBy === 'native_prob') {
      sorted.sort((a, b) => (b.native_prob || 0) - (a.native_prob || 0));
    } else if (this.sortBy === 'supernodes') {
      sorted.sort((a, b) => (b.supernodes || 0) - (a.supernodes || 0));
    }
    return sorted;
  }
  
  navigateStateCard(direction) {
    if (!this.stateCardVisible || !this.stateCardData) return;
    
    const sortedStates = this.getSortedStates();
    const currentIndex = sortedStates.findIndex(s => s.slug === this.stateCardData.slug);
    
    let newIndex;
    if (direction === 'prev') {
      newIndex = currentIndex > 0 ? currentIndex - 1 : sortedStates.length - 1;
    } else {
      newIndex = currentIndex < sortedStates.length - 1 ? currentIndex + 1 : 0;
    }
    
    const newState = sortedStates[newIndex];
    if (newState) {
      this.showStateCard(newState.slug);
    }
  }
  
  async loadSwapOutputs(container, type) {
    const swaps = type === 'target' ? this.stateCardData.swaps_as_target : this.stateCardData.swaps_as_source;
    const listContainer = container.querySelector(`#swaps-${type} .swap-list`);
    
    if (!listContainer || !swaps.length) return;
    
    // Clear placeholder
    listContainer.innerHTML = '<div class="text-xs text-slate-500 text-center py-2 animate-pulse">Fetching steered outputs...</div>';
    
    // Fetch first 10 swap details in parallel
    const batchSize = 10;
    const batch = swaps.slice(0, batchSize);
    
    try {
      const results = await Promise.all(batch.map(async (s) => {
        const from = type === 'target' ? s.from_slug : this.stateCardData.slug;
        const to = type === 'target' ? this.stateCardData.slug : s.to_slug;
        
        try {
          const res = await fetch(`/api/swap/${from}/${to}`);
          if (!res.ok) return { ...s, steered_output: null };
          const data = await res.json();
          return {
            ...s,
            from_slug: from,
            to_slug: to,
            steered_output: data.evaluation?.raw?.steered_output || null,
          };
        } catch {
          return { ...s, steered_output: null };
        }
      }));
      
      // Render results
      listContainer.innerHTML = results.map(s => this.renderSwapOutputRow(s, type)).join('');
      
      // Add "load more" if needed
      if (swaps.length > batchSize) {
        const loadMoreBtn = document.createElement('button');
        loadMoreBtn.className = 'load-more-outputs w-full py-2 text-xs text-cyan-400 hover:text-cyan-300 border-t border-slate-700 mt-2';
        loadMoreBtn.textContent = `Load ${swaps.length - batchSize} more...`;
        loadMoreBtn.dataset.type = type;
        loadMoreBtn.dataset.offset = batchSize;
        loadMoreBtn.addEventListener('click', () => this.loadMoreOutputs(container, type, batchSize, loadMoreBtn));
        listContainer.appendChild(loadMoreBtn);
      }
      
      // Attach click handlers
      this.attachSwapRowHandlers(listContainer);
      
    } catch (e) {
      listContainer.innerHTML = `<div class="text-xs text-red-400 text-center py-2">Error loading outputs: ${e.message}</div>`;
    }
  }
  
  async loadMoreOutputs(container, type, offset, btn) {
    const swaps = type === 'target' ? this.stateCardData.swaps_as_target : this.stateCardData.swaps_as_source;
    const listContainer = container.querySelector(`#swaps-${type} .swap-list`);
    const batchSize = 10;
    const batch = swaps.slice(offset, offset + batchSize);
    
    btn.textContent = 'Loading...';
    btn.disabled = true;
    
    try {
      const results = await Promise.all(batch.map(async (s) => {
        const from = type === 'target' ? s.from_slug : this.stateCardData.slug;
        const to = type === 'target' ? this.stateCardData.slug : s.to_slug;
        
        try {
          const res = await fetch(`/api/swap/${from}/${to}`);
          if (!res.ok) return { ...s, steered_output: null };
          const data = await res.json();
          return {
            ...s,
            from_slug: from,
            to_slug: to,
            steered_output: data.evaluation?.raw?.steered_output || null,
          };
        } catch {
          return { ...s, steered_output: null };
        }
      }));
      
      // Remove load more button and add results
      btn.remove();
      
      const fragment = document.createDocumentFragment();
      results.forEach(s => {
        const div = document.createElement('div');
        div.innerHTML = this.renderSwapOutputRow(s, type);
        fragment.appendChild(div.firstElementChild);
      });
      listContainer.appendChild(fragment);
      
      // Add new "load more" if needed
      const newOffset = offset + batchSize;
      if (swaps.length > newOffset) {
        const loadMoreBtn = document.createElement('button');
        loadMoreBtn.className = 'load-more-outputs w-full py-2 text-xs text-cyan-400 hover:text-cyan-300 border-t border-slate-700 mt-2';
        loadMoreBtn.textContent = `Load ${swaps.length - newOffset} more...`;
        loadMoreBtn.dataset.type = type;
        loadMoreBtn.dataset.offset = newOffset;
        loadMoreBtn.addEventListener('click', () => this.loadMoreOutputs(container, type, newOffset, loadMoreBtn));
        listContainer.appendChild(loadMoreBtn);
      }
      
      // Attach click handlers to new rows
      this.attachSwapRowHandlers(listContainer);
      
    } catch (e) {
      btn.textContent = 'Error - retry';
      btn.disabled = false;
    }
  }
  
  renderSwapOutputRow(s, type) {
    const tierColor = this.getTierColor(s.tier);
    const tierLabel = s.tier === 2.5 ? 'W' : s.tier;
    const stateName = type === 'target' ? s.from_state : s.to_state;
    const arrow = type === 'target' ? '<- ' : '-> ';
    
    // Truncate steered output
    let output = s.steered_output || 'N/A';
    if (output.length > 120) output = output.slice(0, 120) + '...';
    
    return `
      <div class="swap-output-row rounded bg-slate-800/30 hover:bg-slate-700/50 transition-colors cursor-pointer"
           data-from="${s.from_slug}" data-to="${s.to_slug}">
        <div class="flex items-center gap-2 px-2 py-1 border-b border-slate-700/50">
          <span class="text-xs text-slate-500">${arrow}</span>
          <span class="text-xs text-slate-300 font-medium">${stateName}</span>
          <span class="px-1.5 py-0.5 rounded text-white text-xs font-bold" style="background: ${tierColor.bg};">
            T${tierLabel}
          </span>
        </div>
        <div class="px-2 py-1.5 text-xs font-mono text-slate-500 leading-relaxed" style="word-break: break-all;">
          ${this.escapeHtml(output)}
        </div>
      </div>
    `;
  }
  
  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
  
  attachSwapRowHandlers(container) {
    container.querySelectorAll('.swap-output-row').forEach(row => {
      if (row.dataset.handlerAttached) return;
      row.dataset.handlerAttached = 'true';
      
      row.addEventListener('click', () => {
        const from = row.dataset.from;
        const to = row.dataset.to;
        
        this.closeStateCard();
        document.dispatchEvent(new CustomEvent('cell-selected', {
          detail: { from, to },
          bubbles: true,
        }));
        this.updateSelection(from, to);
      });
    });
  }
}

// Auto-initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  const container = document.getElementById('matrix-container');
  if (container) {
    new MatrixIsland(container);
  }
});

export { MatrixIsland };

