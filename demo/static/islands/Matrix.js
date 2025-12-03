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
      
      if (fromState && toState) {
        hoverInfo.style.display = 'block';
        hoverInfo.innerHTML = `
          <span class="text-slate-400">${fromState.state}</span>
          <span class="text-slate-600 mx-2">-></span>
          <span class="text-slate-400">${toState.state}</span>
          ${tier !== null ? `
            <span class="ml-3 px-2 py-0.5 rounded text-xs font-bold" style="background: ${this.getTierColor(tier).bg}20; color: ${this.getTierColor(tier).bg};">
              T${tier}
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
        
        <div class="overflow-x-auto">
          <div class="inline-block">
            <!-- Header row -->
            <div style="display: flex;">
              <div style="width: 64px; height: 64px; flex-shrink: 0;"></div>
              ${sortedStates.map(state => `
                <div style="width: 16px; height: 64px; flex-shrink: 0; position: relative;" title="${state.state} (${state.city})">
                  <span style="position: absolute; bottom: 0; left: 50%; transform: translateX(-50%) rotate(-45deg); transform-origin: bottom left; font-size: 10px; color: #64748b; white-space: nowrap;">
                    ${state.abbr}
                  </span>
                </div>
              `).join('')}
            </div>
            
            <!-- Matrix rows -->
            ${sortedStates.map(rowState => `
              <div style="display: flex;">
                <div style="width: 64px; height: 16px; flex-shrink: 0; display: flex; align-items: center; justify-content: flex-end; padding-right: 8px;" title="${rowState.state} (${rowState.city})">
                  <a href="/state/${rowState.slug}" style="font-size: 10px; color: #64748b; text-decoration: none;" class="hover:text-cyan-400">
                    ${rowState.abbr}
                  </a>
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
                  
                  return `
                    <button
                      class="matrix-cell ${isSelected ? 'selected' : ''}"
                      style="width: 16px; height: 16px; flex-shrink: 0; border-radius: 2px; border: none; cursor: ${isIdentity || tier === null ? 'default' : 'pointer'}; background-color: ${isIdentity ? '#0f172a' : colors.bg}; transition: all 100ms ease; position: relative;"
                      data-from="${rowState.slug}"
                      data-to="${colState.slug}"
                      data-tier="${tier}"
                      ${isIdentity || tier === null ? 'disabled' : ''}
                      title="${isIdentity ? 'Identity' : tier !== null ? `${rowState.abbr} -> ${colState.abbr}: Tier ${tier}${isAnnotated ? ' (edited)' : ''}` : 'No data'}"
                    >${annotatedIndicator}</button>
                  `;
                }).join('')}
              </div>
            `).join('')}
          </div>
        </div>
        
        <!-- Hover info -->
        <div id="hover-info" class="mt-4 p-3 bg-slate-800/50 rounded-lg text-sm" style="display: none;">
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
          hoverInfo.style.display = 'block';
          hoverInfo.innerHTML = `
            <span class="text-slate-400">${fromState.state}</span>
            <span class="text-slate-600 mx-2">-></span>
            <span class="text-slate-400">${toState.state}</span>
            ${tier !== 'null' ? `
              <span class="ml-3 px-2 py-0.5 rounded text-xs font-bold" style="background: ${this.getTierColor(parseInt(tier)).bg}20; color: ${this.getTierColor(parseInt(tier)).bg};">
                T${tier}
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
          hoverInfo.style.display = 'none';
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

