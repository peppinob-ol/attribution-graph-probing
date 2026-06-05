# methods/adag — ADAG (Transluce) as a git submodule

This directory becomes a git submodule of our fork **peppinob-ol/circuits**
(fork of `TransluceAI/circuits`), pinned for reproducibility.

Upstream commit used in the smoke phase: `2d215d4ba016ba8602b69d71fc0f1ad139a427b7`

## Setup (after `gh auth login`)
```bash
gh repo fork TransluceAI/circuits --fork-name circuits --clone=false
git submodule add https://github.com/peppinob-ol/circuits methods/adag
git -C methods/adag checkout 2d215d4ba016ba8602b69d71fc0f1ad139a427b7
git -C methods/adag switch -c adag-baseline-port   # porting branch
```

## Porting commits (tracked on the fork)
1. thread `use_chat_format` through `convert_inputs_to_circuits`; fix the non-chat
   path in `circuits/tracing/trace.py:prepare_ci` to append `seed_response`
   (currently dropped) — needed for base models + base-model CLTs.
2. `Subject` config for Llama-3.2-1B (`llama32_1B`) replacing the hardcoded
   `llama31_8B_instruct_config` in `circuits/analysis/process_circuits.py`.
3. Gemma-2-2B support: GeGLU grad-rule (analogue of `RelPGradMLP`/`ShapleyGradMLP`)
   + 4-norm/layer + logit softcapping in `stop_nonlinear_grad_for_*`.

## Runtime note
Tracing needs NO vllm / NO nnsight. Descriptions use the Anthropic API backend
(`circuits/descriptions/api_backend.py`, all 4 roles on Haiku) — no vllm. Set
`ANTHROPIC_API_KEY` in `methods/adag/.env` (gitignored).
