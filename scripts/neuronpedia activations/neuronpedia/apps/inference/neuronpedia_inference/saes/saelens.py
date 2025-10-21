from typing import Any

import torch
from sae_lens.saes.sae import SAE

from neuronpedia_inference.saes.base import BaseSAE

DTYPE_MAP = {
    "float16": torch.float16,
    "float32": torch.float32,
    "bfloat16": torch.bfloat16,
}


class SaeLensSAE(BaseSAE):
    @staticmethod
    def load(release: str, sae_id: str, device: str, dtype: str) -> tuple[Any, str]:
        loaded_sae = SAE.from_pretrained(
            release=release,
            sae_id=sae_id,
            device=device,
        )
        loaded_sae.to(device, dtype=DTYPE_MAP[dtype])
        loaded_sae.fold_W_dec_norm()
        loaded_sae.eval()

        return loaded_sae, loaded_sae.cfg.metadata.hook_name
