/**
 * Island initializer - mounts Svelte components to their containers
 */
import Matrix from './Matrix.svelte';
import DetailPanel from './DetailPanel.svelte';
import StateCard from './StateCard.svelte';

function mount() {
  const matrixContainer = document.getElementById('matrix-container');
  if (matrixContainer) {
    matrixContainer.innerHTML = '';
    new Matrix({ target: matrixContainer });
  }

  const detailContainer = document.getElementById('detail-panel');
  if (detailContainer) {
    new DetailPanel({ target: detailContainer });
  }

  const stateCardContainer = document.getElementById('state-card-mount');
  if (stateCardContainer) {
    new StateCard({ target: stateCardContainer });
  }
}

// Mount when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', mount);
} else {
  mount();
}


