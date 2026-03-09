"""
Dutch Offshore Wind PPA Valuation Example
==========================================

Comprehensive analysis of a 100 MW offshore wind PPA in the Netherlands.

This example demonstrates:
1. PPA contract setup (Pay-As-Produced structure)
2. Forward curve construction from market data
3. Monte Carlo simulation for merchant tail risk
4. Risk metrics calculation (VaR, CVaR, shape risk)
5. Comparison with baseload alternative
6. Hedging strategy analysis
"""

import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Add parent directory to path
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from ppa_valuation import (
    PayAsProducedPPA,
    BaseloadPPA,
    ForwardCurve,
    MarketSimulator,
    calculate_var,
    calculate_cvar,
    pnl_attribution
)
from ppa_valuation.utils import create_wind_profile, format_currency
from ppa_valuation.risk_metrics import generate_risk_report

# Set style
sns.set_style('whitegrid')
plt.rcParams['figure.figsize'] = (12, 6)


def main():
    """Run Dutch offshore wind PPA valuation."""
    
    print("="*70)
    print("DUTCH OFFSHORE WIND PPA VALUATION")
    print("="*70)
    print()
    
    # =========================================================================
    # 1. CONTRACT SPECIFICATIONS
    # =========================================================================
    print("1. Contract Specifications")
    print("-" * 70)
    
    capacity_mw = 100
    strike_price = 45.0  # EUR/MWh
    start_date = '2025-01-01'
    end_date = '2034-12-31'  # 10-year term
    escalation_rate = 0.02  # 2% annual escalation
    
    print(f"Capacity:              {capacity_mw} MW")
    print(f"Strike Price:          €{strike_price}/MWh (escalating {escalation_rate*100}% p.a.)")
    print(f"Contract Period:       {start_date} to {end_date} (10 years)")
    print(f"Location:              Dutch offshore wind")
    print(f"Expected Capacity Factor: 45%")
    print()
    
    # =========================================================================
    # 2. GENERATION PROFILE
    # =========================================================================
    print("2. Generation Profile")
    print("-" * 70)
    
    # Create realistic offshore wind profile for Netherlands
    generation_profile = create_wind_profile(
        location='NL_offshore',
        year_hours=8760,
        capacity_factor=0.45
    )
    
    annual_generation_mwh = generation_profile.sum() * capacity_mw
    load_factor = generation_profile.mean()
    
    print(f"Annual Generation:     {annual_generation_mwh:,.0f} MWh")
    print(f"Load Factor:           {load_factor:.1%}")
    print(f"Max Hourly Output:     {generation_profile.max()*capacity_mw:.1f} MW")
    print(f"Min Hourly Output:     {generation_profile.min()*capacity_mw:.1f} MW")
    print()
    
    # Plot generation profile
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # Weekly profile
    week_hours = generation_profile[:168]
    axes[0, 0].plot(week_hours, linewidth=1.5)
    axes[0, 0].set_title('Generation Profile - First Week')
    axes[0, 0].set_xlabel('Hour')
    axes[0, 0].set_ylabel('Capacity Factor')
    axes[0, 0].grid(True, alpha=0.3)
    
    # Monthly average
    monthly_avg = [generation_profile[i*730:(i+1)*730].mean() for i in range(12)]
    axes[0, 1].bar(range(1, 13), monthly_avg, color='steelblue')
    axes[0, 1].set_title('Average Capacity Factor by Month')
    axes[0, 1].set_xlabel('Month')
    axes[0, 1].set_ylabel('Capacity Factor')
    axes[0, 1].set_xticks(range(1, 13))
    axes[0, 1].grid(True, alpha=0.3, axis='y')
    
    # Hourly distribution
    axes[1, 0].hist(generation_profile, bins=50, color='steelblue', edgecolor='black', alpha=0.7)
    axes[1, 0].set_title('Distribution of Hourly Capacity Factors')
    axes[1, 0].set_xlabel('Capacity Factor')
    axes[1, 0].set_ylabel('Frequency')
    axes[1, 0].grid(True, alpha=0.3, axis='y')
    
    # Duration curve
    sorted_gen = np.sort(generation_profile)[::-1]
    axes[1, 1].plot(sorted_gen, linewidth=1.5)
    axes[1, 1].set_title('Generation Duration Curve')
    axes[1, 1].set_xlabel('Hours')
    axes[1, 1].set_ylabel('Capacity Factor')
    axes[1, 1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('nl_wind_generation_profile.png', dpi=150, bbox_inches='tight')
    print("Saved: nl_wind_generation_profile.png")
    print()
    
    # =========================================================================
    # 3. FORWARD CURVE CONSTRUCTION
    # =========================================================================
    print("3. Forward Curve Construction")
    print("-" * 70)
    
    # Market futures prices (illustrative - based on ICE Endex)
    futures_prices = {
        'Y-25': 60.0,   # Calendar 2025
        'Y-26': 58.0,   # Calendar 2026
        'Y-27': 55.0,   # Calendar 2027
        'Y-28': 54.0,
        'Y-29': 53.0,
        'Y-30': 52.5,
    }
    
    print("Market Futures Prices (EUR/MWh):")
    for contract, price in futures_prices.items():
        print(f"  {contract}: €{price}")
    print()
    
    # Build forward curve
    forward_curve = ForwardCurve.from_market_data(
        futures_prices=futures_prices,
        reference_date='2024-12-01'
    )
    
    # Display average prices by year
    print("Forward Curve - Annual Average Prices:")
    for year in range(2025, 2031):
        year_start = f'{year}-01-01'
        year_end = f'{year}-12-31'
        avg_price = forward_curve.get_average_price(year_start, year_end)
        print(f"  {year}: €{avg_price:.2f}/MWh")
    print()
    
    # =========================================================================
    # 4. PAY-AS-PRODUCED PPA VALUATION
    # =========================================================================
    print("4. Pay-As-Produced PPA Valuation")
    print("-" * 70)
    
    # Create PAP PPA contract
    pap_ppa = PayAsProducedPPA(
        strike_price=strike_price,
        capacity_mw=capacity_mw,
        start_date=start_date,
        end_date=end_date,
        generation_profile=generation_profile,
        escalation_rate=escalation_rate,
        volume_uncertainty=0.10  # 10% forecast error
    )
    
    # Create market simulator for tail risk
    simulator = MarketSimulator(
        forward_curve=forward_curve,
        volatility_model='constant',
        annual_volatility=0.35,
        mean_reversion_speed=0.5,
        seed=42
    )
    
    # Value the PPA
    print("Valuing PAP PPA with Monte Carlo simulation...")
    pap_valuation = pap_ppa.value(
        forward_curve=forward_curve,
        market_simulator=simulator,
        discount_rate=0.05,
        hedge_horizon_years=3,
        n_scenarios=100
    )
    
    print(pap_valuation.summary())
    
    # =========================================================================
    # 5. BASELOAD PPA COMPARISON
    # =========================================================================
    print("5. Baseload PPA Comparison")
    print("-" * 70)
    
    # Create equivalent baseload PPA
    baseload_ppa = BaseloadPPA(
        strike_price=strike_price,
        capacity_mw=capacity_mw * load_factor,  # Equivalent average capacity
        start_date=start_date,
        end_date=end_date,
        escalation_rate=escalation_rate,
        load_factor=1.0
    )
    
    print("Valuing equivalent Baseload PPA...")
    baseload_valuation = baseload_ppa.value(
        forward_curve=forward_curve,
        market_simulator=simulator,
        discount_rate=0.05,
        hedge_horizon_years=3,
        n_scenarios=300
    )
    
    print(baseload_valuation.summary())
    
    # Comparison table
    print("Comparison: Pay-As-Produced vs Baseload")
    print("-" * 70)
    comparison = pd.DataFrame({
        'Metric': [
            'NPV',
            'Expected Revenue',
            'Shape Risk',
            'Merchant Tail VaR',
            'Merchant Tail CVaR',
            'Hedging Cost'
        ],
        'PAP PPA': [
            format_currency(pap_valuation.npv),
            format_currency(pap_valuation.expected_revenue),
            format_currency(pap_valuation.shape_risk_premium),
            format_currency(pap_valuation.merchant_tail_var_95),
            format_currency(pap_valuation.merchant_tail_cvar_95),
            format_currency(pap_valuation.hedging_cost)
        ],
        'Baseload PPA': [
            format_currency(baseload_valuation.npv),
            format_currency(baseload_valuation.expected_revenue),
            format_currency(baseload_valuation.shape_risk_premium),
            format_currency(baseload_valuation.merchant_tail_var_95),
            format_currency(baseload_valuation.merchant_tail_cvar_95),
            format_currency(baseload_valuation.hedging_cost)
        ]
    })
    print(comparison.to_string(index=False))
    print()
    
    print("KEY INSIGHT:")
    shape_risk_diff = pap_valuation.shape_risk_premium - baseload_valuation.shape_risk_premium
    print(f"Shape risk penalty for PAP vs Baseload: {format_currency(shape_risk_diff)}")
    print("→ Wind generates more during low-price hours (merit order effect)")
    print()
    
    # =========================================================================
    # 6. P&L ATTRIBUTION ANALYSIS
    # =========================================================================
    print("6. P&L Attribution Analysis")
    print("-" * 70)
    
    pnl_breakdown = pnl_attribution(
        cashflow_df=pap_valuation.cashflow_profile,
        forward_curve=forward_curve,
        hedge_ratio=0.75
    )
    
    print("P&L Components:")
    for component, value in pnl_breakdown.items():
        if component != 'attribution_check':
            print(f"  {component:20s}: {format_currency(value)}")
    print()
    
    # Plot P&L attribution
    components = ['market_pnl', 'volume_pnl', 'shape_pnl', 'hedging_pnl', 'basis_pnl']
    values = [pnl_breakdown[c] / 1e6 for c in components]
    labels = ['Market', 'Volume', 'Shape', 'Hedging', 'Basis']
    colors = ['green' if v > 0 else 'red' for v in values]
    
    plt.figure(figsize=(10, 6))
    bars = plt.bar(labels, values, color=colors, alpha=0.7, edgecolor='black')
    plt.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
    plt.title('P&L Attribution - PAP PPA', fontsize=14, fontweight='bold')
    plt.ylabel('P&L (EUR Million)', fontsize=12)
    plt.xlabel('Component', fontsize=12)
    plt.grid(True, alpha=0.3, axis='y')
    
    # Add value labels on bars
    for bar, value in zip(bars, values):
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                f'€{value:.1f}M',
                ha='center', va='bottom' if value > 0 else 'top',
                fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig('pnl_attribution.png', dpi=150, bbox_inches='tight')
    print("Saved: pnl_attribution.png")
    print()
    
    # =========================================================================
    # 7. CASHFLOW PROFILE ANALYSIS
    # =========================================================================
    print("7. Cashflow Profile Analysis")
    print("-" * 70)
    
    # Aggregate cashflows by year
    cashflow_df = pap_valuation.cashflow_profile.copy()
    cashflow_df['year'] = cashflow_df['timestamp'].dt.year
    
    annual_cf = cashflow_df.groupby('year').agg({
        'volume_mwh': 'sum',
        'cashflow': 'sum',
        'discounted_cf': 'sum'
    }).reset_index()
    
    print("Annual Cashflow Summary:")
    print(annual_cf.to_string(index=False))
    print()
    
    # Plot annual cashflows
    fig, ax = plt.subplots(figsize=(12, 6))
    
    x = annual_cf['year']
    y1 = annual_cf['cashflow'] / 1e6
    y2 = annual_cf['discounted_cf'] / 1e6
    
    ax.bar(x - 0.2, y1, 0.4, label='Undiscounted', color='steelblue', alpha=0.7)
    ax.bar(x + 0.2, y2, 0.4, label='Discounted (5%)', color='darkblue', alpha=0.7)
    
    ax.set_xlabel('Year', fontsize=12)
    ax.set_ylabel('Cashflow (EUR Million)', fontsize=12)
    ax.set_title('Annual Cashflow Profile - PAP PPA', fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig('cashflow_profile.png', dpi=150, bbox_inches='tight')
    print("Saved: cashflow_profile.png")
    print()
    
    # =========================================================================
    # 8. RISK REPORT
    # =========================================================================
    print("8. Comprehensive Risk Report")
    print("-" * 70)
    
    risk_report = generate_risk_report(
        valuation_result=pap_valuation,
        pnl_breakdown=pnl_breakdown,
        var_confidence=0.95
    )
    
    print(risk_report)
    
    # =========================================================================
    # 9. KEY INSIGHTS & RECOMMENDATIONS
    # =========================================================================
    print("9. Key Insights & Recommendations")
    print("=" * 70)
    print()
    
    print("VALUATION SUMMARY:")
    print(f"• PPA Fair Value: {format_currency(pap_valuation.npv)}")
    print(f"• Equivalent to strike premium of €{pap_valuation.npv/(annual_generation_mwh*10):.2f}/MWh")
    print()
    
    print("RISK ASSESSMENT:")
    print(f"• Shape Risk: {format_currency(pap_valuation.shape_risk_premium)}")
    print("  → Wind generation anti-correlates with prices (merit order effect)")
    print(f"• Merchant Tail VaR (95%): {format_currency(pap_valuation.merchant_tail_var_95)}")
    print("  → Maximum expected loss beyond hedge horizon with 95% confidence")
    print()
    
    print("HEDGING STRATEGY:")
    hedge_years = 3
    hedged_volume = annual_generation_mwh * hedge_years * 0.75
    print(f"• Recommended hedge: 75% of expected generation for Years 1-{hedge_years}")
    print(f"• Hedged Volume: {hedged_volume:,.0f} MWh")
    print(f"• Merchant Exposure: {annual_generation_mwh * (10-hedge_years):,.0f} MWh (Years {hedge_years+1}-10)")
    print()
    
    print("COMMERCIAL CONSIDERATIONS:")
    print(f"• Strike Price ({strike_price} EUR/MWh) vs Long-term Price ({forward_curve.get_average_price(start_date, end_date):.1f} EUR/MWh)")
    if strike_price < forward_curve.get_average_price(start_date, end_date):
        print("  → Strike below market: Generator hedges against low prices")
    else:
        print("  → Strike above market: Offtaker hedges against high prices")
    print()
    
    print("PORTFOLIO MANAGEMENT IMPLICATIONS:")
    print("• Shape risk requires dynamic hedging (not simple baseload futures)")
    print("• Consider options strategies for merchant tail (collars, put floors)")
    print("• Monitor correlation between generation forecast and market prices")
    print("• Regular P&L attribution to identify hedge effectiveness")
    print()
    
    print("=" * 70)
    print("Analysis complete. Generated files:")
    print("  • nl_wind_generation_profile.png")
    print("  • pnl_attribution.png")
    print("  • cashflow_profile.png")
    print("=" * 70)


if __name__ == '__main__':
    main()
