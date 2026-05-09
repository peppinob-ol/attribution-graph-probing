"""
Research helper: geometry of the answer space at the seed prompt (Gemma-2-2b).

Computes:
1) Mean pairwise cosine similarity of last-layer hidden states at the final
   prompt position (one vector per entity prompt).
2) Per-prompt distribution over candidate answers using teacher-forced full-string
   log-probabilities (sum of log P(token | prompt, prior answer tokens)), then
   softmax over candidates; reports entropy, normalized entropy, top-1 mass,
   and top1-top2 margin.
3) Same restricted metrics using only the first subtoken of each answer and
   the true one-step logits at the seed (for comparison to embedding-only work).

Run from repo root:
  .venv/bin/python -m scripts.utils.seed_answer_geometry
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_ID = "google/gemma-2-2b"
DATASETS_ROOT = Path(__file__).resolve().parent / "datasets"


@dataclass
class GroupStats:
    name: str
    n_prompts: int
    n_candidates: int
    mean_pairwise_cos_last_hidden: float
    mean_entropy_full_seq: float
    mean_norm_entropy_full_seq: float
    mean_top1_full_seq: float
    mean_margin_full_seq: float
    mean_entropy_first_tok: float
    mean_norm_entropy_first_tok: float
    mean_top1_first_tok: float
    mean_margin_first_tok: float


def mean_pairwise_cosine(E: torch.Tensor) -> float:
    """E: (n, d) float."""
    n = E.shape[0]
    if n < 2:
        return float("nan")
    E = E / (E.norm(dim=1, keepdim=True) + 1e-12)
    g = E @ E.T
    tri = torch.triu_indices(n, n, offset=1)
    return g[tri[0], tri[1]].mean().item()


def first_subtoken_ids(tokenizer: Any, texts: list[str]) -> list[int]:
    out: list[int] = []
    for t in texts:
        s = " " + t.strip()
        ids = tokenizer.encode(s, add_special_tokens=False)
        if not ids:
            raise ValueError(f"empty tokenization: {t!r}")
        out.append(ids[0])
    return out


def continuation_ids(tokenizer: Any, text: str) -> list[int]:
    s = " " + text.strip()
    ids = tokenizer.encode(s, add_special_tokens=False)
    if not ids:
        raise ValueError(f"empty continuation: {text!r}")
    return ids


@torch.no_grad()
def teacher_forced_sequence_logprob(
    model: Any,
    device: torch.device,
    prompt_ids: list[int],
    continuation_ids_list: list[int],
) -> float:
    """
    Sum of log probs of continuation tokens given prompt (teacher forcing).
    """
    ids = list(prompt_ids)
    total = 0.0
    inp = torch.tensor([ids], device=device, dtype=torch.long)
    out = model(inp, use_cache=True)
    past = out.past_key_values
    logits = out.logits[0, -1].float()
    logp = F.log_softmax(logits, dim=-1)

    first = continuation_ids_list[0]
    total += logp[first].item()
    cur = torch.tensor([[first]], device=device, dtype=torch.long)

    for j in range(1, len(continuation_ids_list)):
        out = model(cur, past_key_values=past, use_cache=True)
        past = out.past_key_values
        logits = out.logits[0, -1].float()
        logp = F.log_softmax(logits, dim=-1)
        nxt = continuation_ids_list[j]
        total += logp[nxt].item()
        cur = torch.tensor([[nxt]], device=device, dtype=torch.long)

    return total


def restricted_stats_from_scores(scores: torch.Tensor) -> dict[str, float]:
    """scores: (K,) higher is better; treat as log unnormalized."""
    p = F.softmax(scores.float(), dim=0)
    k = p.shape[0]
    ent = -(p * (p.clamp_min(1e-12).log())).sum().item()
    max_ent = math.log(k)
    top2 = torch.topk(p, k=min(2, k))
    margin = (
        (top2.values[0] - top2.values[1]).item()
        if k > 1
        else float(top2.values[0].item())
    )
    return {
        "entropy": ent,
        "norm_entropy": ent / max_ent if max_ent > 0 else 0.0,
        "top1": float(p.max().item()),
        "margin": margin,
    }


def analyze_group(
    name: str,
    prompts: list[str],
    candidates: list[str],
    model: Any,
    tokenizer: Any,
    device: torch.device,
) -> GroupStats:
    k = len(candidates)
    cont_ids_all = [continuation_ids(tokenizer, c) for c in candidates]
    first_ids = [row[0] for row in cont_ids_all]

    toks = tokenizer(
        prompts,
        return_tensors="pt",
        padding=True,
        add_special_tokens=True,
    ).to(device)
    mask = toks.attention_mask
    with torch.no_grad():
        out = model(
            **toks,
            output_hidden_states=True,
            use_cache=False,
        )
    last_idx = mask.sum(dim=1) - 1
    h_last = out.hidden_states[-1]
    rows = []
    for b in range(len(prompts)):
        li = int(last_idx[b].item())
        rows.append(h_last[b, li].float())
    H = torch.stack(rows, dim=0)
    cos_h = mean_pairwise_cosine(H)

    mean_e_full: list[float] = []
    mean_ne_full: list[float] = []
    mean_t1_full: list[float] = []
    mean_m_full: list[float] = []
    mean_e1: list[float] = []
    mean_ne1: list[float] = []
    mean_t1_1: list[float] = []
    mean_m1: list[float] = []

    logits0 = out.logits.float()

    for b in range(len(prompts)):
        li = int(last_idx[b].item())
        logit_row = logits0[b, li]
        sub1 = logit_row[torch.tensor(first_ids, device=device)]
        s1 = restricted_stats_from_scores(sub1)
        mean_e1.append(s1["entropy"])
        mean_ne1.append(s1["norm_entropy"])
        mean_t1_1.append(s1["top1"])
        mean_m1.append(s1["margin"])

        prompt_len = int(mask[b].sum().item())
        prompt_ids = toks.input_ids[b, :prompt_len].tolist()
        scores = []
        for c_ids in cont_ids_all:
            lp = teacher_forced_sequence_logprob(
                model, device, prompt_ids, c_ids
            )
            scores.append(lp)
        s_full = restricted_stats_from_scores(torch.tensor(scores, device=device))
        mean_e_full.append(s_full["entropy"])
        mean_ne_full.append(s_full["norm_entropy"])
        mean_t1_full.append(s_full["top1"])
        mean_m_full.append(s_full["margin"])

    return GroupStats(
        name=name,
        n_prompts=len(prompts),
        n_candidates=k,
        mean_pairwise_cos_last_hidden=cos_h,
        mean_entropy_full_seq=float(sum(mean_e_full) / len(mean_e_full)),
        mean_norm_entropy_full_seq=float(sum(mean_ne_full) / len(mean_ne_full)),
        mean_top1_full_seq=float(sum(mean_t1_full) / len(mean_t1_full)),
        mean_margin_full_seq=float(sum(mean_m_full) / len(mean_m_full)),
        mean_entropy_first_tok=float(sum(mean_e1) / len(mean_e1)),
        mean_norm_entropy_first_tok=float(sum(mean_ne1) / len(mean_ne1)),
        mean_top1_first_tok=float(sum(mean_t1_1) / len(mean_t1_1)),
        mean_margin_first_tok=float(sum(mean_m1) / len(mean_m1)),
    )


def main() -> list[GroupStats]:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    dtype = torch.float16 if device.type == "cuda" else torch.float32
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        torch_dtype=dtype,
        device_map=str(device),
    )
    model.eval()

    books = json.loads((DATASETS_ROOT / "book_characters_authors.json").read_text())
    usa_path = (
        Path(__file__).resolve().parents[2]
        / "output"
        / "usa_states_batch"
        / "_swaps"
        / "runs"
        / "highm_usa_m100"
        / "config_resolved.json"
    )
    if not usa_path.exists():
        raise FileNotFoundError(f"Missing USA config: {usa_path}")
    cfg = json.loads(usa_path.read_text())

    tpl_usa = "The capital of the state containing {city} is"
    prompts_usa = [tpl_usa.replace("{city}", e["city"]) for e in cfg["_entities"]]
    capitals = [e["capital"] for e in cfg["_entities"]]

    tpl_book = books["seed_prompt_template"]
    prompts_book = [tpl_book.replace("{character}", e["character"]) for e in books["entities"]]
    authors = sorted({e["author"] for e in books["entities"]})

    stats: list[GroupStats] = []
    stats.append(
        analyze_group(
            "usa_states (answers=capitals, highm_usa_m100 entities)",
            prompts_usa,
            capitals,
            model,
            tokenizer,
            device,
        )
    )
    stats.append(
        analyze_group(
            "book_characters_authors (answers=authors)",
            prompts_book,
            authors,
            model,
            tokenizer,
            device,
        )
    )

    print("device:", device)
    for s in stats:
        print()
        print(s.name)
        print(
            f"  last_hidden pairwise cos (across entity prompts): {s.mean_pairwise_cos_last_hidden:.4f}"
        )
        print(
            "  full-sequence logprob softmax over candidates (mean over prompts):"
        )
        print(
            f"    norm_entropy={s.mean_norm_entropy_full_seq:.4f}  top1={s.mean_top1_full_seq:.4f}  margin={s.mean_margin_full_seq:.4f}"
        )
        print(
            "  first-subtoken only @ seed logits (mean over prompts):"
        )
        print(
            f"    norm_entropy={s.mean_norm_entropy_first_tok:.4f}  top1={s.mean_top1_first_tok:.4f}  margin={s.mean_margin_first_tok:.4f}"
        )

    return stats


if __name__ == "__main__":
    main()
