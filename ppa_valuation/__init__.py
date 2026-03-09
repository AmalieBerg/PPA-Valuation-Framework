"""
PPA Valuation Framework
========================

A quantitative framework for pricing and risk management of renewable energy 
Power Purchase Agreements (PPAs).

Core modules:
- contracts: PPA contract definitions and valuation
- curves: Forward curve construction and management
- simulation: Monte Carlo price and volume scenario generation
- volatility: GARCH and other volatility models
- hedging: Optimal hedge ratio calculation
- risk_metrics: VaR, CVaR, and P&L attribution
"""

__version__ = "0.1.0"
__author__ = "Your Name"

from .contracts import PPAContract, BaseloadPPA, PayAsProducedPPA
from .curves import ForwardCurve
from .simulation import MarketSimulator
from .risk_metrics import calculate_var, calculate_cvar, pnl_attribution

__all__ = [
    'PPAContract',
    'BaseloadPPA', 
    'PayAsProducedPPA',
    'ForwardCurve',
    'MarketSimulator',
    'calculate_var',
    'calculate_cvar',
    'pnl_attribution'
]
