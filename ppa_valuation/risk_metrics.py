"""
Risk Metrics
============

Calculate VaR, CVaR, and P&L attribution for PPA portfolios.
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple


def calculate_var(
    returns: np.ndarray,
    confidence_level: float = 0.95
) -> float:
    """
    Calculate Value at Risk (VaR).
    
    VaR: Maximum expected loss at given confidence level.
    
    Args:
        returns: Array of returns or P&L scenarios
        confidence_level: Confidence level (default 0.95)
        
    Returns:
        VaR value (negative = loss)
    """
    percentile = (1 - confidence_level) * 100
    return np.percentile(returns, percentile)


def calculate_cvar(
    returns: np.ndarray,
    confidence_level: float = 0.95
) -> float:
    """
    Calculate Conditional Value at Risk (CVaR / Expected Shortfall).
    
    CVaR: Expected loss given that VaR threshold is breached.
    More conservative than VaR, captures tail risk better.
    
    Args:
        returns: Array of returns or P&L scenarios
        confidence_level: Confidence level (default 0.95)
        
    Returns:
        CVaR value (negative = loss)
    """
    var = calculate_var(returns, confidence_level)
    tail_losses = returns[returns <= var]
    
    if len(tail_losses) > 0:
        return tail_losses.mean()
    else:
        return var


def calculate_downside_risk(
    returns: np.ndarray,
    target_return: float = 0.0
) -> float:
    """
    Calculate downside deviation (semi-variance).
    
    Only penalizes returns below target (e.g., losses).
    
    Args:
        returns: Array of returns
        target_return: Target/threshold return (default 0)
        
    Returns:
        Downside risk (standard deviation of returns below target)
    """
    downside_returns = returns[returns < target_return] - target_return
    
    if len(downside_returns) > 0:
        return np.sqrt(np.mean(downside_returns**2))
    else:
        return 0.0


def pnl_attribution(
    cashflow_df: pd.DataFrame,
    forward_curve,
    hedge_ratio: float = 0.75
) -> Dict[str, float]:
    """
    Decompose P&L into market, volume, shape, and basis components.
    
    Attribution breakdown:
    - Market P&L: Gain/loss from forward curve moves
    - Volume P&L: Impact of actual vs expected generation
    - Shape P&L: Loss from renewable profile vs baseload
    - Basis P&L: Day-ahead vs intraday/imbalance spreads
    - Hedging P&L: Cost of futures hedging strategy
    
    Args:
        cashflow_df: DataFrame with timestamps, volumes, prices, cashflows
        forward_curve: ForwardCurve for expected prices
        hedge_ratio: Proportion of volume hedged with futures
        
    Returns:
        Dict with P&L components
    """
    # Extract data - convert Series to proper types
    timestamps = pd.DatetimeIndex(cashflow_df['timestamp'].values)
    actual_volumes = cashflow_df['volume_mwh'].values
    actual_prices = cashflow_df['forward_price'].values  # Simplified: use forward as proxy
    strike_prices = cashflow_df['strike_price'].values
    
    # Expected volumes (for baseload comparison)
    expected_volume = actual_volumes.mean()
    
    # Get initial forward prices (at contract inception)
    initial_forward_prices = forward_curve.get_prices(timestamps)
    
    # Component 1: Market P&L (forward curve move)
    # Gain from favorable price moves on hedged position
    hedged_volume = expected_volume * hedge_ratio
    market_pnl = hedged_volume * (initial_forward_prices - actual_prices).sum()
    
    # Component 2: Volume P&L (generation deviation from expectation)
    volume_deviation = actual_volumes - expected_volume
    volume_pnl = (volume_deviation * (strike_prices - actual_prices)).sum()
    
    # Component 3: Shape P&L (renewable profile vs baseload)
    # Loss from generating during low-price hours
    baseload_revenue = expected_volume * actual_prices.sum()
    pap_revenue = (actual_volumes * actual_prices).sum()
    shape_pnl = pap_revenue - baseload_revenue
    
    # Component 4: Hedging P&L (bid-ask spreads, roll costs)
    hedging_cost = 0.75 * hedged_volume * len(timestamps)  # EUR/MWh * volume * hours
    hedging_pnl = -hedging_cost
    
    # Component 5: Basis P&L (day-ahead vs real-time)
    # Simplified: assume 2 EUR/MWh average basis
    basis_spread = 2.0
    unhedged_volume = (1 - hedge_ratio) * actual_volumes
    basis_pnl = -(unhedged_volume * basis_spread).sum()
    
    # Total P&L
    total_pnl = market_pnl + volume_pnl + shape_pnl + hedging_pnl + basis_pnl
    
    # Also calculate "intrinsic value" = strike vs market
    intrinsic_value = ((strike_prices - actual_prices) * actual_volumes).sum()
    
    return {
        'total_pnl': total_pnl,
        'market_pnl': market_pnl,
        'volume_pnl': volume_pnl,
        'shape_pnl': shape_pnl,
        'hedging_pnl': hedging_pnl,
        'basis_pnl': basis_pnl,
        'intrinsic_value': intrinsic_value,
        'attribution_check': intrinsic_value - hedging_cost  # Should ≈ total_pnl
    }


def calculate_portfolio_risk(
    ppa_contracts: list,
    correlation_matrix: np.ndarray,
    individual_vars: np.ndarray,
    confidence_level: float = 0.95
) -> Dict[str, float]:
    """
    Calculate portfolio-level risk metrics with correlation.
    
    Accounts for diversification benefits across multiple PPAs.
    
    Args:
        ppa_contracts: List of PPA contract objects
        correlation_matrix: Correlation matrix between PPA P&Ls
        individual_vars: Array of individual VaRs
        confidence_level: Confidence level
        
    Returns:
        Dict with portfolio risk metrics
    """
    n_contracts = len(ppa_contracts)
    
    # Portfolio VaR with correlation
    # Var(Portfolio) = w^T * Corr * w, where w = individual VaRs
    portfolio_variance = individual_vars @ correlation_matrix @ individual_vars
    portfolio_var = np.sqrt(portfolio_variance)
    
    # Standalone VaR (no diversification)
    standalone_var = np.sum(np.abs(individual_vars))
    
    # Diversification benefit
    diversification_benefit = standalone_var - portfolio_var
    diversification_ratio = portfolio_var / standalone_var if standalone_var > 0 else 1.0
    
    return {
        'portfolio_var': portfolio_var,
        'standalone_var': standalone_var,
        'diversification_benefit': diversification_benefit,
        'diversification_ratio': diversification_ratio,
        'n_contracts': n_contracts
    }


def calculate_hedge_effectiveness(
    ppa_cashflows: np.ndarray,
    hedge_cashflows: np.ndarray
) -> Dict[str, float]:
    """
    Calculate effectiveness of hedging strategy.
    
    Metrics:
    - Hedge ratio (beta regression)
    - Variance reduction
    - Correlation
    
    Args:
        ppa_cashflows: Unhedged PPA cashflows
        hedge_cashflows: Hedging instrument cashflows
        
    Returns:
        Dict with hedge effectiveness metrics
    """
    # Calculate correlation
    correlation = np.corrcoef(ppa_cashflows, hedge_cashflows)[0, 1]
    
    # Optimal hedge ratio (OLS beta)
    hedge_ratio = np.cov(ppa_cashflows, hedge_cashflows)[0, 1] / np.var(hedge_cashflows)
    
    # Variance reduction
    var_unhedged = np.var(ppa_cashflows)
    hedged_cashflows = ppa_cashflows + hedge_ratio * hedge_cashflows
    var_hedged = np.var(hedged_cashflows)
    variance_reduction = (var_unhedged - var_hedged) / var_unhedged
    
    # Tracking error
    tracking_error = np.std(hedged_cashflows)
    
    return {
        'correlation': correlation,
        'optimal_hedge_ratio': hedge_ratio,
        'variance_reduction': variance_reduction,
        'var_unhedged': var_unhedged,
        'var_hedged': var_hedged,
        'tracking_error': tracking_error
    }


def stress_test_scenarios(
    ppa_valuation,
    stress_scenarios: Dict[str, Dict]
) -> pd.DataFrame:
    """
    Run stress tests on PPA valuation.
    
    Scenarios might include:
    - Price shocks (+/- 20%)
    - Volume shocks (low wind year)
    - Volatility spikes
    - Negative price frequency
    
    Args:
        ppa_valuation: Base case valuation result
        stress_scenarios: Dict of {name: {param: shock}} scenarios
        
    Returns:
        DataFrame with scenario results
    """
    results = []
    
    # Base case
    results.append({
        'scenario': 'Base Case',
        'npv': ppa_valuation.npv,
        'var_95': ppa_valuation.merchant_tail_var_95,
        'shape_risk': ppa_valuation.shape_risk_premium
    })
    
    # Run stress scenarios
    for scenario_name, shocks in stress_scenarios.items():
        # Apply shocks to valuation (simplified - would re-run full valuation)
        stressed_npv = ppa_valuation.npv
        stressed_var = ppa_valuation.merchant_tail_var_95
        stressed_shape = ppa_valuation.shape_risk_premium
        
        if 'price_shock' in shocks:
            # Price shock impacts merchant exposure
            price_mult = 1 + shocks['price_shock']
            stressed_npv *= price_mult
            stressed_var *= price_mult
        
        if 'volume_shock' in shocks:
            # Volume shock impacts all revenues
            volume_mult = 1 + shocks['volume_shock']
            stressed_npv *= volume_mult
            stressed_var *= volume_mult
        
        if 'shape_risk_mult' in shocks:
            # Increase shape risk penalty
            stressed_shape *= shocks['shape_risk_mult']
            stressed_npv -= (stressed_shape - ppa_valuation.shape_risk_premium)
        
        results.append({
            'scenario': scenario_name,
            'npv': stressed_npv,
            'var_95': stressed_var,
            'shape_risk': stressed_shape
        })
    
    return pd.DataFrame(results)


def calculate_risk_adjusted_return(
    expected_return: float,
    risk_measure: float,
    risk_free_rate: float = 0.03
) -> float:
    """
    Calculate risk-adjusted return (Sharpe-like ratio).
    
    Args:
        expected_return: Expected NPV or return
        risk_measure: Risk metric (std dev, VaR, CVaR)
        risk_free_rate: Risk-free rate for comparison
        
    Returns:
        Risk-adjusted return ratio
    """
    if risk_measure == 0:
        return np.inf if expected_return > 0 else -np.inf
    
    excess_return = expected_return - risk_free_rate
    return excess_return / abs(risk_measure)


def generate_risk_report(
    valuation_result,
    pnl_breakdown: Dict[str, float],
    var_confidence: float = 0.95
) -> str:
    """
    Generate comprehensive risk report for PPA.
    
    Args:
        valuation_result: ValuationResult object
        pnl_breakdown: P&L attribution dict
        var_confidence: Confidence level for VaR
        
    Returns:
        Formatted risk report string
    """
    report = f"""
╔════════════════════════════════════════════════════════════╗
║              PPA RISK ANALYSIS REPORT                      ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  VALUATION SUMMARY                                         ║
║  ═══════════════════                                       ║
║  Net Present Value:        €{valuation_result.npv/1e6:>10.2f}M     ║
║  Expected Revenue:         €{valuation_result.expected_revenue/1e6:>10.2f}M     ║
║                                                            ║
║  RISK METRICS                                              ║
║  ═══════════                                               ║
║  VaR (95%):                €{valuation_result.merchant_tail_var_95/1e6:>10.2f}M     ║
║  CVaR (95%):               €{valuation_result.merchant_tail_cvar_95/1e6:>10.2f}M     ║
║  Shape Risk Premium:       €{valuation_result.shape_risk_premium/1e6:>10.2f}M     ║
║  Hedging Cost:             €{valuation_result.hedging_cost/1e6:>10.2f}M     ║
║                                                            ║
║  P&L ATTRIBUTION                                           ║
║  ════════════════                                          ║
║  Market P&L:               €{pnl_breakdown.get('market_pnl', 0)/1e6:>10.2f}M     ║
║  Volume P&L:               €{pnl_breakdown.get('volume_pnl', 0)/1e6:>10.2f}M     ║
║  Shape P&L:                €{pnl_breakdown.get('shape_pnl', 0)/1e6:>10.2f}M     ║
║  Basis P&L:                €{pnl_breakdown.get('basis_pnl', 0)/1e6:>10.2f}M     ║
║  Hedging P&L:              €{pnl_breakdown.get('hedging_pnl', 0)/1e6:>10.2f}M     ║
║  ────────────────────────────────────────────────────────  ║
║  Total P&L:                €{pnl_breakdown.get('total_pnl', 0)/1e6:>10.2f}M     ║
║                                                            ║
║  RISK BREAKDOWN                                            ║
║  ═══════════════                                           ║
"""
    
    for component, value in valuation_result.risk_breakdown.items():
        report += f"║  {component:30s} €{value/1e6:>10.2f}M     ║\n"
    
    report += """║                                                            ║
╚════════════════════════════════════════════════════════════╝
"""
    
    return report