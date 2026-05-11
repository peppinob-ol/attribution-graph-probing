/**
 * Island initializer - mounts Svelte components to their containers
 */
import Matrix from './Matrix.svelte';
import DetailPanel from './DetailPanel.svelte';
import StateCard from './StateCard.svelte';

function mount() {
  const matrixContainer = document.getElementById('matrix-container');
  if (matrixContainer) {
    const ds = matrixContainer.dataset || {};
    const props = {
      defaultBestMode: ds.defaultBestMode === 'true',
      domainFields: {
        input: ds.domainInput || '',
        intermediate: ds.domainIntermediate || '',
        answer: ds.domainAnswer || '',
      },
    };
    matrixContainer.innerHTML = '';
    new Matrix({ target: matrixContainer, props });
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


