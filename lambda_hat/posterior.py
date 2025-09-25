# llc/posterior.py
"""Posterior construction utilities for tempered local posteriors"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable
import jax
import jax.numpy as jnp
from jax import grad, jit

if TYPE_CHECKING:
    # Update TYPE_CHECKING imports
    from .config import PosteriorConfig


# Updated signature to take PosteriorConfig and n_data explicitly
def compute_beta_gamma(
    cfg: PosteriorConfig, d: int, n_data: int
) -> tuple[float, float]:
    """Compute beta and gamma from config and dimension"""
    n_eff = max(3, int(n_data))
    beta = cfg.beta0 / jnp.log(n_eff) if cfg.beta_mode == "1_over_log_n" else cfg.beta0
    gamma = (d / (cfg.prior_radius**2)) if (cfg.prior_radius is not None) else cfg.gamma
    return float(beta), float(gamma)


# Unified function for HMC/MCLMC log density (replaces make_logpost_and_score and make_logdensity_for_mclmc)
def make_logpost(
    loss_full: Callable, params0, n: int, beta: float, gamma: float
) -> Callable:
    """Create the log posterior function: log P(w) = -n*beta*L_n(w) - gamma/2*||w-w0||^2.

    This is used by HMC and MCLMC.
    """
    # Flatten params0 for prior computation
    leaves, _ = jax.tree_util.tree_flatten(params0)
    theta0 = jnp.concatenate([leaf.flatten() for leaf in leaves])

    # Ensure scalars match theta dtype
    beta = jnp.asarray(beta, dtype=theta0.dtype)
    gamma = jnp.asarray(gamma, dtype=theta0.dtype)
    n = jnp.asarray(n, dtype=theta0.dtype)

    @jit
    def logpost(params):
        # Flatten params for prior computation
        leaves, _ = jax.tree_util.tree_flatten(params)
        theta = jnp.concatenate([leaf.flatten() for leaf in leaves])

        Ln = loss_full(params)
        # Prior term: -gamma/2 * ||w-w0||^2
        lp = -0.5 * gamma * jnp.sum((theta - theta0) ** 2)
        # Likelihood term: -n * beta * L_n(w)
        return lp - n * beta * Ln

    return logpost


# New function for SGLD adaptation
def make_grad_loss_minibatch(loss_minibatch: Callable) -> Callable:
    """Create a function that computes the gradient of the minibatch loss.
    This is used for SGLD preconditioning, which should only adapt to the loss landscape.
    """

    @jit
    def grad_loss_fn(params, minibatch):
        Xb, Yb = minibatch
        # Compute gradient of loss w.r.t. params: ∇ L_b(w)
        g_Lb = grad(lambda p: loss_minibatch(p, Xb, Yb))(params)
        return g_Lb

    return grad_loss_fn
