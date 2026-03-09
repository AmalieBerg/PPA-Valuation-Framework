# PPA Valuation Framework
## Power Purchase Agreement Pricing & Risk Analysis for Renewable Energy

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A quantitative framework for pricing and risk management of renewable energy Power Purchase Agreements (PPAs), with focus on Nordic and Continental European power markets.

---

## Project Motivation

Power Purchase Agreements are critical instruments for financing renewable energy projects, but their valuation requires sophisticated analytics combining:
- **Derivatives pricing theory** (forward curves, optionality, volatility modeling)
- **Energy market fundamentals** (shape risk, imbalance pricing, negative prices)
- **Portfolio optimization** (hedging strategies, merchant tail exposure)

This framework demonstrates production-ready capabilities for quantitative portfolio management in renewable energy markets.

---

## Core Capabilities

### 1. **PPA Structure Pricing**
- **Baseload PPAs**: Fixed volume, flat delivery profile
- **Pay-As-Produced (PAP)**: Volume follows actual generation profile
- **Hybrid structures**: Baseload collar with merchant upside

### 2. **Risk Decomposition**
- **Volume risk**: Generation forecast uncertainty vs contracted volumes
- **Shape risk**: Renewable profile vs market price profile correlation
- **Merchant tail risk**: Exposure to extreme price scenarios beyond hedge horizon
- **Basis risk**: Day-ahead vs intraday/imbalance price spreads

### 3. **Valuation Models**
- **Forward curve modeling**: Bootstrapping from futures, seasonal factors
- **Monte Carlo simulation**: Correlated price & volume scenarios (GBM + jump-diffusion)
- **GARCH volatility**: Time-varying volatility for risk assessment
- **Greeks & sensitivities**: Delta, Vega, correlation sensitivity

### 4. **Portfolio Optimization**
- **Hedging strategy**: Optimal futures hedge ratios considering shape risk
- **P&L attribution**: Decompose realized performance into market/volume/basis components
- **Risk metrics**: VaR, CVaR, downside risk for merchant exposure

---

## Key Features

```python
from ppa_valuation import PPAContract, ForwardCurve, MarketSimulator

# Define PPA contract
ppa = PPAContract(
    contract_type='pay_as_produced',
    strike_price=45.0,  # EUR/MWh
    capacity_mw=100,
    start_date='2025-01-01',
    end_date='2034-12-31',
    generation_profile='wind_offshore_nl'  # Dutch offshore wind profile
)

# Build forward curve from market data
curve = ForwardCurve.from_market_data(
    futures_prices={'Y-25': 60, 'Y-26': 58, 'Y-27': 55},
    seasonal_factors={'Q1': 1.15, 'Q2': 0.95, 'Q3': 0.90, 'Q4': 1.10}
)

# Simulate market scenarios with volatility
simulator = MarketSimulator(
    forward_curve=curve,
    volatility_model='garch',  # Heston-Nandi GARCH for time-varying vol
    n_scenarios=10000
)

# Value the PPA with risk metrics
valuation = ppa.value(
    forward_curve=curve,
    market_simulator=simulator,
    discount_rate=0.05
)

print(f"PPA Fair Value: €{valuation.npv/1e6:.2f}M")
print(f"Merchant Tail VaR (95%): €{valuation.var_95/1e6:.2f}M")
print(f"Shape Risk Premium: €{valuation.shape_risk/1e6:.2f}M")
```

---

## Project Structure

```
ppa-valuation-framework/
├── ppa_valuation/
│   ├── __init__.py
│   ├── contracts.py          # PPA contract definitions
│   ├── curves.py              # Forward curve construction
│   ├── simulation.py          # Monte Carlo price/volume scenarios
│   ├── volatility.py          # GARCH volatility models
│   ├── hedging.py             # Optimal hedge ratio calculations
│   ├── risk_metrics.py        # VaR, CVaR, P&L attribution
│   └── utils.py               # Helper functions
├── data/
│   ├── sample_futures.csv     # Example market data
│   └── generation_profiles/   # Renewable generation profiles
├── notebooks/
│   ├── 01_baseload_vs_pap.ipynb
│   ├── 02_shape_risk_analysis.ipynb
│   ├── 03_merchant_tail_hedging.ipynb
│   └── 04_portfolio_optimization.ipynb
├── tests/
│   └── test_ppa_valuation.py
├── examples/
│   ├── dutch_offshore_wind_ppa.py
│   └── nordic_hydro_ppa.py
├── requirements.txt
├── setup.py
└── README.md
```

---

## Quick Start

### Installation

```bash
git clone https://github.com/yourusername/ppa-valuation-framework.git
cd ppa-valuation-framework
pip install -r requirements.txt
```

### Basic Usage

```python
# Example: Dutch offshore wind PAP PPA valuation
python examples/dutch_offshore_wind_ppa.py
```

### Run Jupyter Notebooks

```bash
jupyter notebook notebooks/
```

---

## Analytical Approach

### 1. Forward Curve Construction
Built from liquid futures markets (ICE Endex for Netherlands, NASDAQ Commodities for Nordics):
- Bootstrap yearly/quarterly/monthly forward prices
- Apply seasonal factors for hourly profile
- Adjust for delivery location basis

### 2. Generation Profile Modeling
Realistic renewable generation profiles based on:
- **Wind**: ERA5 reanalysis data, capacity factors by region
- **Solar**: Global horizontal irradiance, panel efficiency curves
- **Hydro**: Inflow patterns, reservoir constraints (Nordic markets)

### 3. Price-Volume Correlation
Critical for shape risk assessment:
- High wind/solar → low prices (merit order effect)
- Model correlation structure: Gaussian copula with tail dependence
- Negative price scenarios (Germany/Netherlands)

### 4. Merchant Tail Risk
Beyond liquid hedge horizon (typically 3-5 years):
- Mean reversion to long-run marginal cost
- Jump-diffusion for extreme events (capacity outages, fuel price shocks)
- Regulatory scenario analysis (SDE++, CfD schemes)

---

## Technical Foundations

This framework builds on established financial engineering principles:

1. **Derivatives Pricing**: Black-Scholes framework, martingale pricing, risk-neutral valuation
2. **Volatility Modeling**: GARCH family models (Heston-Nandi for closed-form solutions)
3. **Portfolio Theory**: Mean-variance optimization, efficient frontier for hedge ratios
4. **Energy Economics**: Merit order curves, renewable integration effects, market microstructure


---

## Case Study: 100 MW Dutch Offshore Wind PPA

### Contract Specifications
- **Type**: Pay-As-Produced
- **Capacity**: 100 MW
- **Term**: 10 years (2025-2034)
- **Strike**: €45/MWh (escalating 2% annually)
- **Profile**: Dutch offshore wind (capacity factor ~45%)

### Valuation Results (Illustrative)

| Metric | Value |
|--------|-------|
| **NPV (@ 5% discount rate)** | €12.5M |
| **Merchant Tail VaR (95%)** | -€3.8M |
| **Shape Risk Premium** | -€1.2M |
| **Optimal Hedge Ratio (Y1-Y3)** | 75% |
| **Unhedged Merchant Exposure** | €4.5M |

### Risk Decomposition
- **Captured value**: €18.0M (PPA vs merchant expected)
- **Shape risk penalty**: -€1.2M (wind profile vs baseload)
- **Tail risk**: -€3.8M (95% VaR beyond Y3)
- **Hedging cost**: -€0.5M (bid-ask spreads)

---

## Advanced Features

### 1. **GARCH Volatility Surface**
Time-varying volatility for forward contracts:
- Short-term: High volatility (weather, outages)
- Long-term: Mean reversion to fundamentals
- Implementation: Heston-Nandi GARCH(1,1) with closed-form Greeks

### 2. **Negative Price Modeling**
Critical for Netherlands/Germany:
- Shifted lognormal model for price distributions
- Conditional on high renewable penetration scenarios
- Impact on PAP PPA value vs baseload

### 3. **Correlation Structure**
Multi-factor model for price-volume dependencies:
- Price: Mean-reverting GBM + jumps
- Volume: Auto-regressive weather model
- Correlation: Time-varying (higher in extreme scenarios)

### 4. **Regulatory Scenarios**
Sensitivity to policy changes:
- Dutch SDE++ subsidy phase-out impact
- German EEG levy abolishment effects
- EU ETS carbon price pass-through

---

## References & Further Reading

### Academic Literature
- Benth, F.E., Saltyte-Benth, J., & Koekebakker, S. (2008). *Stochastic Modelling of Electricity and Related Markets*
- Burger, M., et al. (2007). "A spot market model for pricing derivatives in electricity markets"
- Weron, R. (2014). "Electricity price forecasting: A review of the state-of-the-art"

### Market Structure
- ACER Market Monitoring Report (European power markets)
- TenneT Transparency Platform (Dutch TSO)
- ENTSO-E Statistical Yearbook (European generation data)

### Industry Practice
- EFET Standard PPA Documentation
- ISDA Energy Derivatives Definitions
- Statkraft Global Environmental Markets publications

---

## Use Cases

### Portfolio Managers
- Value existing PPA book against forward curves
- Assess hedge effectiveness and rebalancing needs
- P&L attribution for performance reporting

### Deal Originators
- Price new PPA structures in competitive tenders
- Quantify shape risk vs baseload alternatives
- Optimize strike price and tenor for bankability

### Risk Managers
- Calculate VaR/CVaR for merchant tail exposure
- Stress test portfolio under regulatory scenarios
- Monitor Greeks and sensitivity to market moves

### Analysts
- Research price-volume correlation dynamics
- Backtest volatility models for hedge ratio optimization
- Scenario analysis for long-term market views

---

## Dependencies

```txt
numpy>=1.21.0
pandas>=1.3.0
scipy>=1.7.0
matplotlib>=3.4.0
seaborn>=0.11.0
statsmodels>=0.13.0
arch>=5.0.0  # GARCH models
scikit-learn>=1.0.0
jupyter>=1.0.0
```

---

## License

MIT License - see LICENSE file for details

---

## Author

**Amalie Berg**
- M.S. Economics (Finance), NHH Norwegian School of Economics
- M.S. Physics (Materials/Energy), University of Oslo
- M.S. Software Engineering (in progress), BI Norwegian Business School

**Thesis**: *Heston-Nandi GARCH Option Pricing in Energy Markets* (Grade A)

---

## Contact

For questions, collaboration, or applications: ab@amalieberg.com


