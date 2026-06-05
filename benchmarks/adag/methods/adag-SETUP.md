# ADAG submodule (`methods/adag`) — setup & porting

`methods/adag` is a git submodule of **peppinob-ol/circuits** (fork of
`TransluceAI/circuits`), pinned at `2d215d4ba016ba8602b69d71fc0f1ad139a427b7`.

## Init after a fresh checkout
```bash
git submodule update --init benchmarks/adag/methods/adag
```

## Working on the fork
```bash
cd benchmarks/adag/methods/adag
git switch -c adag-port            # porting branch on the fork
# ...edit, commit, push to peppinob-ol/circuits...
cd -                              # then bump the submodule pointer:
git add benchmarks/adag/methods/adag && git commit -m "bump adag submodule"
```

## Porting commits (tracked on the fork)
1. thread `use_chat_format` through `convert_inputs_to_circuits`; fix the non-chat
   path in `circuits/tracing/trace.py:prepare_ci` to append `seed_response`
   (currently dropped) — needed for base models + base-model CLTs.
2. `Subject` config for Llama-3.2-1B (replace hardcoded `llama31_8B_instruct_config`
   in `circuits/analysis/process_circuits.py`).
3. Gemma-2-2B: GeGLU grad-rule (analogue of `RelPGradMLP`/`ShapleyGradMLP`) + 4
   norms/layer + logit softcapping in `stop_nonlinear_grad_for_*`.

## Runtime
Tracing needs no vllm/nnsight. Descriptions use the Anthropic API backend (all 4
roles on Haiku 4.5); set `ANTHROPIC_API_KEY` in `methods/adag/.env` (gitignored).
