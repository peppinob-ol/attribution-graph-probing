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
        """
        Load a SaeLens SAE.

        For the CLT release (mntss-gemma-2-2b-2.5m-clt-as-per-layer), we intentionally
        keep the SAE on CPU so that the huge decoder matrix W_dec never lives on GPU.
        Steering vectors are later moved to the model device in the steering pipeline,
        so this is mathematically identical but GPU-safe.
        """
        if release == "mntss-gemma-2-2b-2.5m-clt-as-per-layer":
            # CPU-backed CLT: load entirely on CPU and keep W_dec off GPU
            loaded_sae = SAE.from_pretrained(
                release=release,
                sae_id=sae_id,
                device="cpu",
            )
            loaded_sae.to("cpu", dtype=DTYPE_MAP[dtype])
        else:
            # Default path: load SAE on the requested device as before
            loaded_sae = SAE.from_pretrained(
                release=release,
                sae_id=sae_id,
                device=device,
            )
            loaded_sae.to(device, dtype=DTYPE_MAP[dtype])

        if loaded_sae.cfg.architecture() in ["temporal"]:
            print("Temporal architecture detected, skipping fold_W_dec_norm")
        else:
            loaded_sae.fold_W_dec_norm()
        loaded_sae.eval()

        return loaded_sae, loaded_sae.cfg.metadata.hook_name
