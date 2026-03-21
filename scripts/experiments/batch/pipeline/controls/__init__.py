"""
Control intervention builders for swap experiments.

Each control mode implements InterventionBuilder and produces the same
features-payload shape consumed by batch_steering_ct.py.
"""
from .factory import create_intervention_builder

__all__ = ["create_intervention_builder"]
