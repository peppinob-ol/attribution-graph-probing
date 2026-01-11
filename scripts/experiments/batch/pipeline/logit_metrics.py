"""
Fine-grained logit metrics for swap evaluation.

Captures exact logit/probability/rank for specific tokens of interest
across multiple generation positions, enabling:
- Continuous metrics instead of discrete tier classification
- Effect trajectory analysis (when does target become prominent?)
- Specificity verification via control token stability

Usage:
    # During generation
    tracker = LogitTrajectoryTracker(tokenizer, target="Atlanta", source="Austin")
    for step in range(max_tokens):
        logits = model.forward(...)
        tracker.record_step(logits, step)
    
    # Get results
    metrics = tracker.get_metrics()
    metrics_dict = metrics.to_dict()
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import torch


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class TokenLogitInfo:
    """Logit information for a single token at a single position."""
    token: str              # The token string (e.g., " Austin")
    token_id: int           # Tokenizer ID
    logit: float            # Raw logit value
    prob: float             # Softmax probability
    rank: int               # Rank in vocabulary (1 = highest)
    
    @property
    def log_prob(self) -> float:
        """Log probability."""
        return math.log(self.prob) if self.prob > 0 else float('-inf')
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "token": self.token,
            "token_id": self.token_id,
            "logit": round(self.logit, 4),
            "prob": round(self.prob, 6),
            "rank": self.rank,
            "log_prob": round(self.log_prob, 4),
        }


@dataclass
class TokenTrajectory:
    """Track a specific token's logit/prob/rank across generation steps."""
    token: str
    token_id: int
    # One entry per generation step
    positions: List[int] = field(default_factory=list)
    logits: List[float] = field(default_factory=list)
    probs: List[float] = field(default_factory=list)
    ranks: List[int] = field(default_factory=list)
    
    @property
    def first_top1_position(self) -> Optional[int]:
        """Position where token first becomes rank 1."""
        for i, r in enumerate(self.ranks):
            if r == 1:
                return self.positions[i] if i < len(self.positions) else i
        return None
    
    @property
    def first_top5_position(self) -> Optional[int]:
        """Position where token first enters top 5."""
        for i, r in enumerate(self.ranks):
            if r <= 5:
                return self.positions[i] if i < len(self.positions) else i
        return None
    
    @property
    def first_top10_position(self) -> Optional[int]:
        """Position where token first enters top 10."""
        for i, r in enumerate(self.ranks):
            if r <= 10:
                return self.positions[i] if i < len(self.positions) else i
        return None
    
    @property
    def max_prob(self) -> float:
        """Maximum probability achieved."""
        return max(self.probs) if self.probs else 0.0
    
    @property
    def max_prob_position(self) -> Optional[int]:
        """Position of maximum probability."""
        if not self.probs:
            return None
        idx = self.probs.index(max(self.probs))
        return self.positions[idx] if idx < len(self.positions) else idx
    
    @property
    def min_rank(self) -> Optional[int]:
        """Best (lowest) rank achieved."""
        return min(self.ranks) if self.ranks else None
    
    @property
    def rank_improvement(self) -> int:
        """Total rank improvement from start to best."""
        if len(self.ranks) < 1:
            return 0
        return self.ranks[0] - min(self.ranks)
    
    @property
    def final_rank(self) -> Optional[int]:
        """Rank at final position."""
        return self.ranks[-1] if self.ranks else None
    
    @property
    def final_prob(self) -> Optional[float]:
        """Probability at final position."""
        return self.probs[-1] if self.probs else None
    
    def add_step(self, position: int, logit: float, prob: float, rank: int) -> None:
        """Add a step to the trajectory."""
        self.positions.append(position)
        self.logits.append(logit)
        self.probs.append(prob)
        self.ranks.append(rank)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "token": self.token,
            "token_id": self.token_id,
            "trajectory": {
                "positions": self.positions,
                "logits": [round(l, 4) for l in self.logits],
                "probs": [round(p, 6) for p in self.probs],
                "ranks": self.ranks,
            },
            "summary": {
                "first_top1_position": self.first_top1_position,
                "first_top5_position": self.first_top5_position,
                "first_top10_position": self.first_top10_position,
                "max_prob": round(self.max_prob, 6),
                "max_prob_position": self.max_prob_position,
                "min_rank": self.min_rank,
                "rank_improvement": self.rank_improvement,
                "final_rank": self.final_rank,
                "final_prob": round(self.final_prob, 6) if self.final_prob else None,
            }
        }


@dataclass
class MultiPositionLogitMetrics:
    """
    Logit metrics across multiple generation positions.
    
    Tracks target, source, and control tokens throughout the
    entire generation, not just at position 0.
    """
    # Token trajectories
    target_trajectory: Optional[TokenTrajectory] = None
    source_trajectory: Optional[TokenTrajectory] = None
    control_trajectories: Dict[str, TokenTrajectory] = field(default_factory=dict)
    
    # What was actually generated at each position
    generated_tokens: List[str] = field(default_factory=list)
    generated_token_ids: List[int] = field(default_factory=list)
    
    # Metadata
    target_token_str: str = ""
    source_token_str: str = ""
    control_tokens: List[str] = field(default_factory=list)
    n_positions: int = 0
    
    @property
    def target_appears_at(self) -> Optional[int]:
        """Position where target token was actually generated (if ever)."""
        if not self.target_trajectory:
            return None
        target_id = self.target_trajectory.token_id
        for i, tid in enumerate(self.generated_token_ids):
            if tid == target_id:
                return i
        return None
    
    @property
    def source_appears_at(self) -> Optional[int]:
        """Position where source token was actually generated (if ever)."""
        if not self.source_trajectory:
            return None
        source_id = self.source_trajectory.token_id
        for i, tid in enumerate(self.generated_token_ids):
            if tid == source_id:
                return i
        return None
    
    @property
    def flip_position(self) -> Optional[int]:
        """First position where target outranks source."""
        if not self.target_trajectory or not self.source_trajectory:
            return None
        
        target_ranks = self.target_trajectory.ranks
        source_ranks = self.source_trajectory.ranks
        
        for i in range(min(len(target_ranks), len(source_ranks))):
            if target_ranks[i] < source_ranks[i]:
                return self.target_trajectory.positions[i] if i < len(self.target_trajectory.positions) else i
        return None
    
    @property
    def gap_trajectory(self) -> List[float]:
        """Target-source logit gap at each position."""
        if not self.target_trajectory or not self.source_trajectory:
            return []
        
        target_logits = self.target_trajectory.logits
        source_logits = self.source_trajectory.logits
        
        gaps = []
        for i in range(min(len(target_logits), len(source_logits))):
            gap = target_logits[i] - source_logits[i]
            gaps.append(gap)
        return gaps
    
    @property
    def initial_gap(self) -> Optional[float]:
        """Target-source gap at position 0."""
        gaps = self.gap_trajectory
        return gaps[0] if gaps else None
    
    @property
    def best_gap(self) -> Optional[float]:
        """Best (highest) target-source gap achieved."""
        gaps = self.gap_trajectory
        return max(gaps) if gaps else None
    
    @property
    def final_gap(self) -> Optional[float]:
        """Target-source gap at final position."""
        gaps = self.gap_trajectory
        return gaps[-1] if gaps else None
    
    @property
    def gap_closure(self) -> Optional[float]:
        """Improvement in gap from initial to best."""
        initial = self.initial_gap
        best = self.best_gap
        if initial is not None and best is not None:
            return best - initial
        return None
    
    @property
    def control_stability_mean(self) -> Optional[float]:
        """Mean logit change for controls (position 0 to final)."""
        if not self.control_trajectories:
            return None
        
        deltas = []
        for traj in self.control_trajectories.values():
            if len(traj.logits) >= 2:
                delta = abs(traj.logits[-1] - traj.logits[0])
                deltas.append(delta)
        
        return sum(deltas) / len(deltas) if deltas else None
    
    @property
    def control_stability_max(self) -> Optional[float]:
        """Max logit change for any control token."""
        if not self.control_trajectories:
            return None
        
        max_delta = 0.0
        for traj in self.control_trajectories.values():
            if len(traj.logits) >= 2:
                # Max change at any position vs position 0
                for logit in traj.logits[1:]:
                    delta = abs(logit - traj.logits[0])
                    max_delta = max(max_delta, delta)
        
        return max_delta if max_delta > 0 else None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tokens": {
                "target": self.target_token_str,
                "source": self.source_token_str,
                "controls": self.control_tokens,
            },
            "n_positions": self.n_positions,
            "generated_tokens": self.generated_tokens,
            "trajectories": {
                "target": self.target_trajectory.to_dict() if self.target_trajectory else None,
                "source": self.source_trajectory.to_dict() if self.source_trajectory else None,
                "controls": {
                    k: v.to_dict() for k, v in self.control_trajectories.items()
                },
            },
            "summary": {
                "target_appears_at": self.target_appears_at,
                "source_appears_at": self.source_appears_at,
                "flip_position": self.flip_position,
                "initial_gap": round(self.initial_gap, 4) if self.initial_gap is not None else None,
                "best_gap": round(self.best_gap, 4) if self.best_gap is not None else None,
                "final_gap": round(self.final_gap, 4) if self.final_gap is not None else None,
                "gap_closure": round(self.gap_closure, 4) if self.gap_closure is not None else None,
                "gap_trajectory": [round(g, 4) for g in self.gap_trajectory],
                "control_stability_mean": round(self.control_stability_mean, 4) if self.control_stability_mean is not None else None,
                "control_stability_max": round(self.control_stability_max, 4) if self.control_stability_max is not None else None,
            },
        }


# =============================================================================
# Trajectory Tracker (used during generation)
# =============================================================================


class LogitTrajectoryTracker:
    """
    Tracks logits for specific tokens during generation.
    
    Usage:
        tracker = LogitTrajectoryTracker(
            tokenizer=model.tokenizer,
            target_token="Atlanta",
            source_token="Austin",
            control_tokens=[" the", " is"],
        )
        
        for step, logits in enumerate(generation_logits):
            generated_id = tracker.record_step(logits, step)
            # generated_id is the token that was actually sampled
        
        metrics = tracker.get_metrics()
    """
    
    DEFAULT_CONTROL_TOKENS = [" the", " is", " a", " of"]
    
    def __init__(
        self,
        tokenizer,
        target_token: str,
        source_token: str,
        control_tokens: Optional[List[str]] = None,
    ):
        self.tokenizer = tokenizer
        self.target_token_str = target_token
        self.source_token_str = source_token
        self.control_tokens = control_tokens or self.DEFAULT_CONTROL_TOKENS
        
        # Resolve token IDs
        self.target_id, self.target_resolved = self._resolve_token(target_token)
        self.source_id, self.source_resolved = self._resolve_token(source_token)
        self.control_ids: Dict[str, Tuple[int, str]] = {}
        for ctrl in self.control_tokens:
            tid, resolved = self._resolve_token(ctrl)
            if tid is not None:
                self.control_ids[ctrl] = (tid, resolved)
        
        # Initialize trajectories
        self.target_trajectory = TokenTrajectory(
            token=self.target_resolved or target_token,
            token_id=self.target_id or -1,
        )
        self.source_trajectory = TokenTrajectory(
            token=self.source_resolved or source_token,
            token_id=self.source_id or -1,
        )
        self.control_trajectories: Dict[str, TokenTrajectory] = {
            ctrl: TokenTrajectory(token=resolved, token_id=tid)
            for ctrl, (tid, resolved) in self.control_ids.items()
        }
        
        # Track generated tokens
        self.generated_tokens: List[str] = []
        self.generated_token_ids: List[int] = []
    
    def _resolve_token(self, token_str: str) -> Tuple[Optional[int], Optional[str]]:
        """
        Resolve a token string to its ID.
        
        Tries multiple variants (with/without space) and returns the
        single-token version if available.
        """
        variants = [
            f" {token_str}",  # With leading space (common for word tokens)
            token_str,
            token_str.strip(),
            token_str.lower(),
            f" {token_str.lower()}",
        ]
        
        for variant in variants:
            try:
                encoded = self.tokenizer.encode(variant, add_special_tokens=False)
                if len(encoded) == 1:
                    return encoded[0], variant
            except Exception:
                continue
        
        # Fallback: use first token of the encoded sequence
        try:
            encoded = self.tokenizer.encode(f" {token_str}", add_special_tokens=False)
            if encoded:
                first_token = self.tokenizer.decode([encoded[0]])
                return encoded[0], first_token
        except Exception:
            pass
        
        return None, None
    
    def record_step(
        self,
        logits: torch.Tensor,
        step: int,
        sampled_token_id: Optional[int] = None,
    ) -> None:
        """
        Record logit information for this generation step.
        
        Args:
            logits: Model logits for next token [vocab_size] or [batch, vocab_size]
            step: Current generation step (0-indexed)
            sampled_token_id: The token that was actually sampled (if known)
        """
        # Ensure logits are 1D
        if logits.dim() > 1:
            logits = logits.squeeze()
        if logits.dim() > 1:
            logits = logits[-1]  # Take last position if still multi-dim
        
        # Compute probabilities and ranks
        probs = torch.softmax(logits, dim=-1)
        
        # Record target
        if self.target_id is not None:
            logit_val = logits[self.target_id].item()
            prob_val = probs[self.target_id].item()
            rank_val = self._compute_rank(probs, self.target_id)
            self.target_trajectory.add_step(step, logit_val, prob_val, rank_val)
        
        # Record source
        if self.source_id is not None:
            logit_val = logits[self.source_id].item()
            prob_val = probs[self.source_id].item()
            rank_val = self._compute_rank(probs, self.source_id)
            self.source_trajectory.add_step(step, logit_val, prob_val, rank_val)
        
        # Record controls
        for ctrl, traj in self.control_trajectories.items():
            tid = traj.token_id
            if tid >= 0:
                logit_val = logits[tid].item()
                prob_val = probs[tid].item()
                rank_val = self._compute_rank(probs, tid)
                traj.add_step(step, logit_val, prob_val, rank_val)
        
        # Record sampled token if provided
        if sampled_token_id is not None:
            self.generated_token_ids.append(sampled_token_id)
            self.generated_tokens.append(self.tokenizer.decode([sampled_token_id]))
    
    def _compute_rank(self, probs: torch.Tensor, token_id: int) -> int:
        """Compute rank of token (1 = highest probability)."""
        token_prob = probs[token_id]
        # Count how many tokens have strictly higher probability
        rank = (probs > token_prob).sum().item() + 1
        return int(rank)
    
    def get_metrics(self) -> MultiPositionLogitMetrics:
        """Get the complete metrics object."""
        return MultiPositionLogitMetrics(
            target_trajectory=self.target_trajectory if self.target_id else None,
            source_trajectory=self.source_trajectory if self.source_id else None,
            control_trajectories=self.control_trajectories,
            generated_tokens=self.generated_tokens,
            generated_token_ids=self.generated_token_ids,
            target_token_str=self.target_token_str,
            source_token_str=self.source_token_str,
            control_tokens=self.control_tokens,
            n_positions=len(self.generated_tokens),
        )


# =============================================================================
# Single-position metrics (for backward compatibility / simpler cases)
# =============================================================================


@dataclass
class SinglePositionLogitMetrics:
    """
    Logit metrics at a single position (e.g., first generated token).
    
    Simpler alternative to full trajectory when only one position matters.
    """
    target_baseline: Optional[TokenLogitInfo] = None
    target_steered: Optional[TokenLogitInfo] = None
    source_baseline: Optional[TokenLogitInfo] = None
    source_steered: Optional[TokenLogitInfo] = None
    controls_baseline: Dict[str, TokenLogitInfo] = field(default_factory=dict)
    controls_steered: Dict[str, TokenLogitInfo] = field(default_factory=dict)
    
    target_token_str: str = ""
    source_token_str: str = ""
    control_tokens: List[str] = field(default_factory=list)
    
    @property
    def target_logit_delta(self) -> Optional[float]:
        """Change in target logit."""
        if self.target_baseline and self.target_steered:
            return self.target_steered.logit - self.target_baseline.logit
        return None
    
    @property
    def source_logit_delta(self) -> Optional[float]:
        """Change in source logit."""
        if self.source_baseline and self.source_steered:
            return self.source_steered.logit - self.source_baseline.logit
        return None
    
    @property
    def gap_baseline(self) -> Optional[float]:
        """Target-source gap at baseline."""
        if self.target_baseline and self.source_baseline:
            return self.target_baseline.logit - self.source_baseline.logit
        return None
    
    @property
    def gap_steered(self) -> Optional[float]:
        """Target-source gap after steering."""
        if self.target_steered and self.source_steered:
            return self.target_steered.logit - self.source_steered.logit
        return None
    
    @property
    def gap_closure(self) -> Optional[float]:
        """Improvement in gap."""
        g_baseline = self.gap_baseline
        g_steered = self.gap_steered
        if g_baseline is not None and g_steered is not None:
            return g_steered - g_baseline
        return None
    
    @property
    def flip_achieved(self) -> bool:
        """Did target become higher than source?"""
        if self.target_steered and self.source_steered:
            return self.target_steered.logit > self.source_steered.logit
        return False
    
    @property
    def target_rank_improvement(self) -> Optional[int]:
        """Positions target climbed."""
        if self.target_baseline and self.target_steered:
            return self.target_baseline.rank - self.target_steered.rank
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tokens": {
                "target": self.target_token_str,
                "source": self.source_token_str,
                "controls": self.control_tokens,
            },
            "baseline": {
                "target": self.target_baseline.to_dict() if self.target_baseline else None,
                "source": self.source_baseline.to_dict() if self.source_baseline else None,
                "controls": {k: v.to_dict() for k, v in self.controls_baseline.items()},
            },
            "steered": {
                "target": self.target_steered.to_dict() if self.target_steered else None,
                "source": self.source_steered.to_dict() if self.source_steered else None,
                "controls": {k: v.to_dict() for k, v in self.controls_steered.items()},
            },
            "deltas": {
                "target_logit_delta": round(self.target_logit_delta, 4) if self.target_logit_delta else None,
                "source_logit_delta": round(self.source_logit_delta, 4) if self.source_logit_delta else None,
                "gap_baseline": round(self.gap_baseline, 4) if self.gap_baseline else None,
                "gap_steered": round(self.gap_steered, 4) if self.gap_steered else None,
                "gap_closure": round(self.gap_closure, 4) if self.gap_closure else None,
                "flip_achieved": self.flip_achieved,
                "target_rank_improvement": self.target_rank_improvement,
            },
        }


def get_token_logit_info(
    logits: torch.Tensor,
    tokenizer,
    token_str: str,
    position: int = -1,
) -> Optional[TokenLogitInfo]:
    """
    Get detailed logit info for a specific token at a specific position.
    
    Args:
        logits: Model logits [batch, seq_len, vocab_size] or [seq_len, vocab_size]
        tokenizer: Tokenizer for encoding
        token_str: Token string to look up (e.g., "Austin")
        position: Sequence position to query (default: -1 = last)
    
    Returns:
        TokenLogitInfo or None if token not found
    """
    # Resolve token ID
    variants = [f" {token_str}", token_str, token_str.strip()]
    token_id = None
    actual_token_str = None
    
    for variant in variants:
        try:
            encoded = tokenizer.encode(variant, add_special_tokens=False)
            if len(encoded) == 1:
                token_id = encoded[0]
                actual_token_str = variant
                break
        except Exception:
            continue
    
    if token_id is None:
        # Multi-token - use first token as approximation
        try:
            encoded = tokenizer.encode(f" {token_str}", add_special_tokens=False)
            if encoded:
                token_id = encoded[0]
                actual_token_str = tokenizer.decode([token_id])
        except Exception:
            return None
    
    if token_id is None:
        return None
    
    # Get logits at position
    squeezed = logits.squeeze()
    if squeezed.dim() > 1:
        pos_logits = squeezed[position]
    else:
        pos_logits = squeezed
    
    # Get the specific token's logit
    token_logit = pos_logits[token_id].item()
    
    # Compute probability
    probs = torch.softmax(pos_logits, dim=-1)
    token_prob = probs[token_id].item()
    
    # Compute rank
    rank = (probs > token_prob).sum().item() + 1
    
    return TokenLogitInfo(
        token=actual_token_str,
        token_id=token_id,
        logit=token_logit,
        prob=token_prob,
        rank=int(rank),
    )





