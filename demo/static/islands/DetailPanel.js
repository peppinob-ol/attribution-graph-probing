/**
 * DetailPanel Island - Vanilla JS implementation
 * Slide-in panel showing swap details and Neuronpedia links
 * Supports annotation mode for editing tiers and notes
 */

class DetailPanelIsland {
  constructor() {
    this.visible = false;
    this.data = null;
    this.fromSlug = null;
    this.toSlug = null;
    this.states = [];
    this.matrix = {};
    this.annotateMode = false;
    this.noteInputActive = false;
    this.saving = false;
    
    // Default colors
    this.defaultTierInfo = {
      5:   { name: 'PERFECT',        color: '#0A4FFF', desc: 'Target capital found in output' },
      4:   { name: 'STATE + CITY',   color: '#3D7DFF', desc: 'Target state city found (not capital)' },
      3:   { name: 'STATE ONLY',     color: '#AFCBFF', desc: 'Target state referred only' },
      2.5: { name: 'WRONG STATE',    color: '#FFE8E8', desc: 'Source suppressed, different state appears' },
      2:   { name: 'SUPPRESSED',     color: '#FF7373', desc: 'Source suppressed, no target content' },
      1:   { name: 'SOURCE PERSISTS', color: '#C00000', desc: 'Source capital still in output' },
    };
    
    // Colorblind-friendly colors
    this.colorblindTierInfo = {
      5:   { name: 'PERFECT',        color: '#0077BB', desc: 'Target capital found in output' },
      4:   { name: 'STATE + CITY',   color: '#33BBEE', desc: 'Target state city found (not capital)' },
      3:   { name: 'STATE ONLY',     color: '#EE7733', desc: 'Target state referred only' },
      2.5: { name: 'WRONG STATE',    color: '#CCBB44', desc: 'Source suppressed, different state appears' },
      2:   { name: 'SUPPRESSED',     color: '#EE3377', desc: 'Source suppressed, no target content' },
      1:   { name: 'SOURCE PERSISTS', color: '#AA3377', desc: 'Source capital still in output' },
    };
    
    this.updateColorMode();
    
    // Listen for colorblind mode changes from Matrix
    document.addEventListener('colorblind-mode-changed', () => {
      this.updateColorMode();
      if (this.visible && this.data) {
        this.renderContent();
      }
    });
    
    this.init();
  }
  
  updateColorMode() {
    const colorblindMode = localStorage.getItem('colorblindMode') === 'true';
    this.tierInfo = colorblindMode ? this.colorblindTierInfo : this.defaultTierInfo;
  }
  
  async init() {
    // Check annotation mode from body data attribute
    this.annotateMode = document.body.dataset.annotateMode === 'true';
    
    // Create panel container
    this.backdrop = document.createElement('div');
    this.backdrop.className = 'fixed inset-0 bg-black/50 z-40';
    this.backdrop.style.display = 'none';
    this.backdrop.onclick = () => this.close();
    
    this.panel = document.createElement('aside');
    this.panel.className = 'detail-panel z-50';
    this.panel.innerHTML = '';
    
    document.body.appendChild(this.backdrop);
    document.body.appendChild(this.panel);
    
    // Listen for cell selection
    document.addEventListener('cell-selected', (e) => this.handleCellSelected(e));
    
    // Keyboard navigation and annotation
    document.addEventListener('keydown', (e) => this.handleKeydown(e));
    
    // Load states and matrix for navigation
    try {
      const [statesRes, matrixRes] = await Promise.all([
        fetch('/api/states'),
        fetch('/api/matrix'),
      ]);
      this.states = await statesRes.json();
      this.matrix = await matrixRes.json();
    } catch (e) {
      console.error('Failed to load navigation data:', e);
    }
  }
  
  handleKeydown(e) {
    if (!this.visible || !this.fromSlug || !this.toSlug) return;
    
    // If note input is active, only handle Escape and Enter
    if (this.noteInputActive) {
      if (e.key === 'Escape') {
        this.cancelNoteInput();
        e.preventDefault();
      }
      // Enter is handled by the input's event listener
      return;
    }
    
    // Annotation mode: handle tier keys 1-5
    if (this.annotateMode && e.key >= '1' && e.key <= '5') {
      e.preventDefault();
      this.setTier(parseInt(e.key));
      return;
    }
    
    // Annotation mode: handle 'w' for Wrong State (tier 2.5)
    if (this.annotateMode && (e.key === 'w' || e.key === 'W')) {
      e.preventDefault();
      this.setTier(2.5);
      return;
    }
    
    // Annotation mode: handle 'n' for notes
    if (this.annotateMode && (e.key === 'n' || e.key === 'N')) {
      e.preventDefault();
      this.openNoteInput();
      return;
    }
    
    // Navigation keys
    const validKeys = ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'];
    if (!validKeys.includes(e.key)) {
      if (e.key === 'Escape') this.close();
      return;
    }
    
    e.preventDefault();
    
    // Get sorted state slugs (same order as matrix)
    const slugs = this.states.map(s => s.slug).sort((a, b) => {
      const stateA = this.states.find(s => s.slug === a)?.state || a;
      const stateB = this.states.find(s => s.slug === b)?.state || b;
      return stateA.localeCompare(stateB);
    });
    
    const fromIdx = slugs.indexOf(this.fromSlug);
    const toIdx = slugs.indexOf(this.toSlug);
    
    if (fromIdx === -1 || toIdx === -1) return;
    
    let newFromIdx = fromIdx;
    let newToIdx = toIdx;
    
    switch (e.key) {
      case 'ArrowUp':
        newFromIdx = Math.max(0, fromIdx - 1);
        break;
      case 'ArrowDown':
        newFromIdx = Math.min(slugs.length - 1, fromIdx + 1);
        break;
      case 'ArrowLeft':
        newToIdx = Math.max(0, toIdx - 1);
        break;
      case 'ArrowRight':
        newToIdx = Math.min(slugs.length - 1, toIdx + 1);
        break;
    }
    
    // Skip identity cells
    if (newFromIdx === newToIdx) {
      if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
        newFromIdx = e.key === 'ArrowUp' ? newFromIdx - 1 : newFromIdx + 1;
      } else {
        newToIdx = e.key === 'ArrowLeft' ? newToIdx - 1 : newToIdx + 1;
      }
    }
    
    // Bounds check
    if (newFromIdx < 0 || newFromIdx >= slugs.length) return;
    if (newToIdx < 0 || newToIdx >= slugs.length) return;
    if (newFromIdx === newToIdx) return;
    
    const newFrom = slugs[newFromIdx];
    const newTo = slugs[newToIdx];
    
    // Check if swap exists
    if (this.matrix[newFrom]?.[newTo] === undefined || this.matrix[newFrom]?.[newTo] === null) {
      return;
    }
    
    // Update matrix selection visually
    document.dispatchEvent(new CustomEvent('cell-selected', {
      detail: { from: newFrom, to: newTo },
      bubbles: true,
    }));
    
    this.loadSwapData(newFrom, newTo);
  }
  
  async setTier(newTier) {
    if (this.saving || !this.fromSlug || !this.toSlug) return;
    
    this.saving = true;
    this.showSavingIndicator();
    
    try {
      const res = await fetch(`/api/annotate/${this.fromSlug}/${this.toSlug}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tier: newTier }),
      });
      
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || 'Failed to save');
      }
      
      const result = await res.json();
      
      // Update local data
      this.data.classification = this.data.classification || {};
      this.data.classification.tier = newTier;
      this.data.classification.manually_edited = true;
      
      // Update matrix cache and cell
      this.matrix[this.fromSlug][this.toSlug] = newTier;
      
      // Dispatch event to update matrix cell and stats
      document.dispatchEvent(new CustomEvent('annotation-saved', {
        detail: {
          from: this.fromSlug,
          to: this.toSlug,
          tier: newTier,
          stats: result.stats,
        },
        bubbles: true,
      }));
      
      // Re-render with updated data
      this.renderContent();
      this.showSaveSuccess('Tier updated');
      
    } catch (e) {
      console.error('Failed to save tier:', e);
      this.showSaveError(e.message);
    } finally {
      this.saving = false;
    }
  }
  
  openNoteInput() {
    this.noteInputActive = true;
    const currentNotes = this.data?.classification?.notes || '';
    
    // Find or create the note input container
    let container = this.panel.querySelector('#note-input-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'note-input-container';
      container.className = 'p-4 bg-amber-900/30 border border-amber-700 rounded-lg mb-4';
      
      // Insert after tier badge
      const tierBadge = this.panel.querySelector('.tier-badge-section');
      if (tierBadge) {
        tierBadge.after(container);
      }
    }
    
    container.innerHTML = `
      <div class="text-xs text-amber-400 uppercase mb-2">Add/Edit Note</div>
      <input 
        type="text" 
        id="note-input"
        class="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded text-white text-sm focus:outline-none focus:border-amber-500"
        placeholder="Type note and press Enter..."
        value="${this.escapeHtml(currentNotes)}"
      />
      <div class="flex gap-2 mt-2">
        <button id="save-note-btn" class="px-3 py-1 bg-amber-600 hover:bg-amber-500 rounded text-xs text-white">
          Save (Enter)
        </button>
        <button id="cancel-note-btn" class="px-3 py-1 bg-slate-700 hover:bg-slate-600 rounded text-xs text-slate-300">
          Cancel (Esc)
        </button>
      </div>
    `;
    
    const input = container.querySelector('#note-input');
    const saveBtn = container.querySelector('#save-note-btn');
    const cancelBtn = container.querySelector('#cancel-note-btn');
    
    input.focus();
    input.select();
    
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        this.saveNote(input.value);
      } else if (e.key === 'Escape') {
        e.preventDefault();
        this.cancelNoteInput();
      }
    });
    
    saveBtn.onclick = () => this.saveNote(input.value);
    cancelBtn.onclick = () => this.cancelNoteInput();
  }
  
  cancelNoteInput() {
    this.noteInputActive = false;
    const container = this.panel.querySelector('#note-input-container');
    if (container) container.remove();
  }
  
  async saveNote(noteText) {
    if (this.saving) return;
    
    this.saving = true;
    
    try {
      const res = await fetch(`/api/annotate/${this.fromSlug}/${this.toSlug}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notes: noteText }),
      });
      
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || 'Failed to save');
      }
      
      const result = await res.json();
      
      // Update local data
      this.data.classification = this.data.classification || {};
      this.data.classification.notes = noteText;
      this.data.classification.manually_edited = true;
      
      // Dispatch event
      document.dispatchEvent(new CustomEvent('annotation-saved', {
        detail: {
          from: this.fromSlug,
          to: this.toSlug,
          notes: noteText,
          stats: result.stats,
        },
        bubbles: true,
      }));
      
      this.noteInputActive = false;
      this.renderContent();
      this.showSaveSuccess('Note saved');
      
    } catch (e) {
      console.error('Failed to save note:', e);
      this.showSaveError(e.message);
    } finally {
      this.saving = false;
    }
  }
  
  showSavingIndicator() {
    const toast = this.createToast('Saving...', 'bg-slate-700');
    setTimeout(() => toast.remove(), 1000);
  }
  
  showSaveSuccess(message) {
    const toast = this.createToast(message, 'bg-emerald-600');
    setTimeout(() => toast.remove(), 2000);
  }
  
  showSaveError(message) {
    const toast = this.createToast(`Error: ${message}`, 'bg-red-600');
    setTimeout(() => toast.remove(), 3000);
  }
  
  createToast(message, bgClass) {
    const toast = document.createElement('div');
    toast.className = `fixed bottom-4 right-4 px-4 py-2 rounded-lg text-white text-sm ${bgClass} z-[100] animate-pulse`;
    toast.textContent = message;
    document.body.appendChild(toast);
    return toast;
  }
  
  async loadSwapData(from, to) {
    this.fromSlug = from;
    this.toSlug = to;
    this.renderLoading();
    
    try {
      const res = await fetch(`/api/swap/${from}/${to}`);
      if (!res.ok) {
        throw new Error('Swap data not found');
      }
      this.data = await res.json();
      this.renderContent();
    } catch (e) {
      this.renderError(e.message);
    }
  }
  
  async handleCellSelected(event) {
    const { from, to } = event.detail;
    
    if (this.fromSlug === from && this.toSlug === to && this.visible) {
      return;
    }
    
    this.show();
    await this.loadSwapData(from, to);
  }
  
  show() {
    this.visible = true;
    this.backdrop.style.display = 'block';
    this.panel.classList.add('visible');
  }
  
  close() {
    this.visible = false;
    this.backdrop.style.display = 'none';
    this.panel.classList.remove('visible');
    this.data = null;
    this.noteInputActive = false;
  }
  
  renderLoading() {
    this.panel.innerHTML = `
      <div class="sticky top-0 bg-slate-900 border-b border-slate-700 p-4">
        <div class="flex items-center justify-between">
          <h2 class="text-lg font-semibold text-white">Swap Details</h2>
          <button class="close-btn w-8 h-8 flex items-center justify-center rounded hover:bg-slate-800 transition-colors text-slate-400 hover:text-white">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        ${this.renderKeyboardHint()}
      </div>
      <div class="p-4">
        <div class="py-20 text-center text-slate-500 animate-pulse">Loading swap data...</div>
      </div>
    `;
    this.attachCloseHandler();
  }
  
  renderKeyboardHint() {
    const baseHints = `
      <span class="px-1.5 py-0.5 bg-slate-800 rounded font-mono">Arrow Keys</span>
      <span>navigate</span>
      <span class="text-slate-600">|</span>
      <span class="px-1.5 py-0.5 bg-slate-800 rounded font-mono">ESC</span>
      <span>close</span>
    `;
    
    const annotateHints = this.annotateMode ? `
      <span class="text-slate-600">|</span>
      <span class="px-1.5 py-0.5 bg-amber-900/50 text-amber-400 rounded font-mono">1-5</span>
      <span class="text-amber-400">tier</span>
      <span class="text-slate-600">|</span>
      <span class="px-1.5 py-0.5 bg-orange-900/50 text-orange-400 rounded font-mono">W</span>
      <span class="text-orange-400">wrong state</span>
      <span class="text-slate-600">|</span>
      <span class="px-1.5 py-0.5 bg-amber-900/50 text-amber-400 rounded font-mono">N</span>
      <span class="text-amber-400">note</span>
    ` : '';
    
    return `
      <div class="mt-2 flex items-center gap-1 text-xs text-slate-500 flex-wrap">
        ${baseHints}
        ${annotateHints}
      </div>
    `;
  }
  
  renderError(message) {
    this.panel.innerHTML = `
      <div class="sticky top-0 bg-slate-900 border-b border-slate-700 p-4">
        <div class="flex items-center justify-between">
          <h2 class="text-lg font-semibold text-white">Swap Details</h2>
          <button class="close-btn w-8 h-8 flex items-center justify-center rounded hover:bg-slate-800 transition-colors text-slate-400 hover:text-white">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        ${this.renderKeyboardHint()}
      </div>
      <div class="p-4">
        <div class="py-20 text-center text-red-400">${message}</div>
      </div>
    `;
    this.attachCloseHandler();
  }
  
  getTier() {
    if (!this.data) return null;
    if (this.data.classification?.tier !== undefined) {
      return this.data.classification.tier;
    }
    const exact = this.data.evaluation?.exact_match || {};
    if (exact.steered_has_to_capital) return 5;
    if (exact.from_suppressed && !exact.steered_has_to_capital) return 2;
    if (!exact.from_suppressed) return 1;
    return 3;
  }
  
  highlightOutput(text, sourceCapital, targetCapital) {
    if (!text) return '';
    let result = this.escapeHtml(text);
    if (targetCapital) {
      result = result.replace(new RegExp(targetCapital, 'gi'), `<span style="color: #34d399; font-weight: bold;">${targetCapital}</span>`);
    }
    if (sourceCapital) {
      result = result.replace(new RegExp(sourceCapital, 'gi'), `<span style="color: #f87171; font-weight: bold;">${sourceCapital}</span>`);
    }
    return result;
  }
  
  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
  
  renderContent() {
    const tier = this.getTier();
    const info = this.tierInfo[tier] || this.tierInfo[0];
    const source = this.data.source || {};
    const target = this.data.target || {};
    const evaluation = this.data.evaluation || {};
    const raw = evaluation.raw || {};
    const firstToken = evaluation.first_token || {};
    const exact = evaluation.exact_match || {};
    const interventions = this.data.interventions || {};
    const classification = this.data.classification || {};
    const isEdited = classification.manually_edited;
    
    // Render tier buttons for annotation mode (including 2.5 for WRONG STATE)
    const allTiers = [1, 2, 2.5, 3, 4, 5];
    const tierButtons = this.annotateMode ? `
      <div class="flex gap-1 mt-3">
        ${allTiers.map(t => {
          const label = t === 2.5 ? 'W' : `T${t}`;
          const isSelected = t === tier;
          return `
            <button 
              class="tier-btn px-2 py-1 rounded text-xs font-bold transition-all ${isSelected ? 'ring-2 ring-white ring-offset-2 ring-offset-slate-900' : 'opacity-60 hover:opacity-100'}"
              style="background: ${this.tierInfo[t]?.color || '#475569'};"
              data-tier="${t}"
              title="${this.tierInfo[t]?.name || 'Unknown'}"
            >${label}</button>
          `;
        }).join('')}
      </div>
    ` : '';
    
    // Edited indicator
    const editedBadge = isEdited ? `
      <span class="ml-2 px-2 py-0.5 bg-amber-900/50 text-amber-400 text-xs rounded">
        EDITED
      </span>
    ` : '';
    
    this.panel.innerHTML = `
      <div class="sticky top-0 bg-slate-900 border-b border-slate-700 p-4">
        <div class="flex items-center justify-between">
          <h2 class="text-lg font-semibold text-white">Swap Details</h2>
          <button class="close-btn w-8 h-8 flex items-center justify-center rounded hover:bg-slate-800 transition-colors text-slate-400 hover:text-white">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        ${this.renderKeyboardHint()}
      </div>
      
      <div class="p-4 text-white">
        <!-- Swap header -->
        <div class="mb-6">
          <div class="flex items-center gap-3 mb-2">
            <div class="text-center">
              <div class="text-2xl font-bold">${source.state || 'Unknown'}</div>
              <div class="text-xs text-slate-500">${source.city || ''}</div>
            </div>
            <div class="text-slate-600 text-2xl">-></div>
            <div class="text-center">
              <div class="text-2xl font-bold">${target.state || 'Unknown'}</div>
              <div class="text-xs text-slate-500">${target.city || ''}</div>
            </div>
          </div>
        </div>
        
        <!-- Tier badge -->
        <div class="tier-badge-section mb-6 p-4 rounded-lg" style="background: rgba(30, 41, 59, 0.5); border: 1px solid rgb(51, 65, 85);">
          <div class="flex items-center gap-3 mb-2">
            <div class="px-3 py-1 rounded text-white font-bold text-sm" style="background: ${info.color};">
              TIER ${tier}
            </div>
            <div class="font-semibold" style="color: ${info.color};">${info.name}</div>
            ${editedBadge}
          </div>
          <p class="text-sm text-slate-400">${info.desc}</p>
          ${classification.notes ? `<p class="text-sm text-amber-400/80 mt-2 italic">"${this.escapeHtml(classification.notes)}"</p>` : ''}
          ${classification.cities_found ? `<p class="text-xs text-slate-600 mt-2">Found: ${Array.isArray(classification.cities_found) ? classification.cities_found.join(', ') : classification.cities_found}</p>` : ''}
          ${tierButtons}
        </div>
        
        <!-- State cards -->
        <div class="grid grid-cols-2 gap-4 mb-6">
          <div class="p-3 rounded-lg" style="background: rgba(30, 41, 59, 0.5); border: 1px solid rgb(51, 65, 85);">
            <div class="text-xs text-slate-500 uppercase mb-2">Source</div>
            <div class="text-sm font-semibold">${source.state}</div>
            <div class="text-xs text-slate-400">Capital: <span style="color: #facc15;">${source.capital}</span></div>
            <div class="text-xs text-slate-400">City: ${source.city}</div>
            ${source.neuronpedia_url ? `<a href="${source.neuronpedia_url}" target="_blank" class="inline-block mt-2 text-xs text-cyan-400 hover:underline">Neuronpedia -></a>` : ''}
          </div>
          <div class="p-3 rounded-lg" style="background: rgba(30, 41, 59, 0.5); border: 1px solid rgb(51, 65, 85);">
            <div class="text-xs text-slate-500 uppercase mb-2">Target</div>
            <div class="text-sm font-semibold">${target.state}</div>
            <div class="text-xs text-slate-400">Capital: <span style="color: #34d399;">${target.capital}</span></div>
            <div class="text-xs text-slate-400">City: ${target.city}</div>
            ${target.neuronpedia_url ? `<a href="${target.neuronpedia_url}" target="_blank" class="inline-block mt-2 text-xs text-cyan-400 hover:underline">Neuronpedia -></a>` : ''}
          </div>
        </div>
        
        <!-- Outputs -->
        <div class="space-y-4 mb-6">
          <div>
            <div class="text-xs text-slate-500 uppercase mb-2">Default Output</div>
            <div class="p-3 rounded text-sm font-mono text-slate-300 overflow-x-auto" style="background: rgb(30, 41, 59);">
              ${this.highlightOutput((raw.default_output || 'N/A').slice(0, 200), source.capital, target.capital)}
            </div>
          </div>
          
          <div class="flex items-center justify-center">
            <div class="px-3 py-1 rounded-full text-cyan-400 text-xs" style="background: rgba(22, 78, 99, 0.3);">
              STEERED
            </div>
          </div>
          
          <div>
            <div class="text-xs text-slate-500 uppercase mb-2">Steered Output</div>
            <div class="p-3 rounded text-sm font-mono text-slate-300 overflow-x-auto" style="background: rgb(30, 41, 59);">
              ${this.highlightOutput((raw.steered_output || 'N/A').slice(0, 200), source.capital, target.capital)}
            </div>
          </div>
        </div>
        
        <!-- First token analysis -->
        <div class="p-4 rounded-lg mb-6" style="background: rgba(30, 41, 59, 0.5); border: 1px solid rgb(51, 65, 85);">
          <div class="text-xs text-slate-500 uppercase mb-3">First Token Analysis</div>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <div class="text-xs text-slate-500">Default</div>
              <div class="text-sm font-mono" style="color: #facc15;">'${firstToken.default || '?'}'</div>
              <div class="text-xs text-slate-600">prob: ${(firstToken.default_prob || 0).toFixed(3)}</div>
            </div>
            <div>
              <div class="text-xs text-slate-500">Steered</div>
              <div class="text-sm font-mono text-cyan-400">'${firstToken.steered || '?'}'</div>
              <div class="text-xs text-slate-600">prob: ${(firstToken.steered_prob || 0).toFixed(3)}</div>
            </div>
          </div>
        </div>
        
        <!-- Status indicators -->
        <div class="p-4 rounded-lg mb-6" style="background: rgba(30, 41, 59, 0.5); border: 1px solid rgb(51, 65, 85);">
          <div class="text-xs text-slate-500 uppercase mb-3">Status</div>
          <div class="space-y-2">
            <div class="flex items-center justify-between text-sm">
              <span class="text-slate-400">Target capital in steered:</span>
              <span style="color: ${exact.steered_has_to_capital ? '#34d399' : '#f87171'};">
                ${exact.steered_has_to_capital ? 'Yes' : 'No'}
              </span>
            </div>
            <div class="flex items-center justify-between text-sm">
              <span class="text-slate-400">Source suppressed:</span>
              <span style="color: ${exact.from_suppressed ? '#34d399' : '#f87171'};">
                ${exact.from_suppressed ? 'Yes' : 'No'}
              </span>
            </div>
          </div>
        </div>
        
        <!-- Interventions -->
        ${interventions.total_count ? `
          <div class="p-4 rounded-lg mb-6" style="background: rgba(30, 41, 59, 0.5); border: 1px solid rgb(51, 65, 85);">
            <div class="text-xs text-slate-500 uppercase mb-3">Interventions</div>
            <div class="grid grid-cols-3 gap-4 text-center">
              <div>
                <div class="text-lg font-bold" style="color: #f87171;">${interventions.ablate_count || 0}</div>
                <div class="text-xs text-slate-500">Ablated</div>
              </div>
              <div>
                <div class="text-lg font-bold" style="color: #34d399;">${interventions.amplify_count || 0}</div>
                <div class="text-xs text-slate-500">Amplified</div>
              </div>
              <div>
                <div class="text-lg font-bold text-slate-400">${interventions.total_count || 0}</div>
                <div class="text-xs text-slate-500">Total</div>
              </div>
            </div>
          </div>
        ` : ''}
        
        <!-- Links -->
        <div class="flex gap-2">
          ${source.neuronpedia_url ? `
            <a href="${source.neuronpedia_url}" target="_blank" class="flex-1 py-2 px-4 rounded bg-slate-800 hover:bg-slate-700 text-center text-sm text-cyan-400 transition-colors">
              Source Subgraph
            </a>
          ` : ''}
          ${target.neuronpedia_url ? `
            <a href="${target.neuronpedia_url}" target="_blank" class="flex-1 py-2 px-4 rounded bg-slate-800 hover:bg-slate-700 text-center text-sm text-cyan-400 transition-colors">
              Target Subgraph
            </a>
          ` : ''}
        </div>
      </div>
    `;
    
    this.attachCloseHandler();
    this.attachTierButtonHandlers();
  }
  
  attachCloseHandler() {
    const closeBtn = this.panel.querySelector('.close-btn');
    if (closeBtn) {
      closeBtn.onclick = () => this.close();
    }
  }
  
  attachTierButtonHandlers() {
    const tierBtns = this.panel.querySelectorAll('.tier-btn');
    tierBtns.forEach(btn => {
      btn.onclick = () => {
        const newTier = parseInt(btn.dataset.tier);
        this.setTier(newTier);
      };
    });
  }
}

// Auto-initialize
document.addEventListener('DOMContentLoaded', () => {
  new DetailPanelIsland();
});

export { DetailPanelIsland };
