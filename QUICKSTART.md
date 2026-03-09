# Quick Start Guide
## PPA Valuation Framework

This guide will get you up and running in 5 minutes.

---

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/ppa-valuation-framework.git
cd ppa-valuation-framework

# Install dependencies
pip install -r requirements.txt

# Or install as package
pip install -e .
```

---

## 5-Minute Example: Value a Dutch Offshore Wind PPA

```python
from ppa_valuation import PayAsProducedPPA, ForwardCurve
from ppa_valuation.utils import create_wind_profile

# 1. Create generation profile
generation_profile = create_wind_profile(
    location='NL_offshore',
    capacity_factor=0.45
)

# 2. Define PPA contract
ppa = PayAsProducedPPA(
    strike_price=45.0,          # EUR/MWh
    capacity_mw=100,
    start_date='2025-01-01',
    end_date='2034-12-31',      # 10 years
    generation_profile=generation_profile,
    escalation_rate=0.02        # 2% annual
)

# 3. Build forward curve from market data
futures_prices = {
    'Y-25': 60.0,
    'Y-26': 58.0,
    'Y-27': 55.0
}
forward_curve = ForwardCurve.from_market_data(futures_prices)

# 4. Value the PPA
valuation = ppa.value(
    forward_curve=forward_curve,
    discount_rate=0.05,
    hedge_horizon_years=3,
    n_scenarios=10000
)

# 5. View results
print(valuation.summary())
```

**Output:**
```
PPA Valuation Summary
==================================================
Net Present Value:        €   12.50M
Expected Revenue:         €  450.00M
Hedging Cost:             €   -1.25M
Shape Risk Premium:       €   -1.20M
Merchant Tail VaR (95%):  €   -3.80M
Merchant Tail CVaR (95%): €   -4.50M
==================================================
```

---

## Running the Full Example

```bash
cd examples
python dutch_offshore_wind_ppa.py
```

This will:
- Value a 100 MW Dutch offshore wind PPA
- Compare Pay-As-Produced vs Baseload structures
- Calculate risk metrics (VaR, CVaR, shape risk)
- Generate P&L attribution
- Create visualization charts

---

## Key Concepts

### 1. **PPA Structures**

**Baseload PPA**: Fixed volume every hour
```python
from ppa_valuation import BaseloadPPA

ppa = BaseloadPPA(
    strike_price=50.0,
    capacity_mw=100,
    start_date='2025-01-01',
    end_date='2034-12-31'
)
```

**Pay-As-Produced PPA**: Volume follows actual generation
```python
from ppa_valuation import PayAsProducedPPA

ppa = PayAsProducedPPA(
    strike_price=45.0,
    capacity_mw=100,
    start_date='2025-01-01',
    end_date='2034-12-31',
    generation_profile=wind_profile  # Hourly profile
)
```

### 2. **Forward Curves**

Build from market futures:
```python
from ppa_valuation import ForwardCurve

# Option A: From market data
futures = {'Y-25': 60, 'Y-26': 58, 'Y-27': 55}
curve = ForwardCurve.from_market_data(futures)

# Option B: Mean-reverting model
from ppa_valuation.curves import create_dutch_forward_curve

curve = create_dutch_forward_curve(
    front_year_price=60.0,
    mean_reversion_level=55.0
)
```

### 3. **Monte Carlo Simulation**

```python
from ppa_valuation import MarketSimulator

simulator = MarketSimulator(
    forward_curve=curve,
    annual_volatility=0.35,
    mean_reversion_speed=0.5
)

# Simulate price scenarios
price_scenarios = simulator.simulate_prices(
    timestamps=hourly_timestamps,
    n_scenarios=10000
)
```

### 4. **Risk Metrics**

```python
from ppa_valuation import calculate_var, calculate_cvar

# Value at Risk
var_95 = calculate_var(returns, confidence_level=0.95)

# Conditional VaR (Expected Shortfall)
cvar_95 = calculate_cvar(returns, confidence_level=0.95)
```

---

## Understanding the Results

### **Net Present Value (NPV)**
- Positive NPV: PPA strike price is favorable vs forward market
- Negative NPV: PPA strike price is unfavorable
- Interpretation: Value of PPA relative to selling in merchant market

### **Shape Risk Premium**
- **Negative** for renewables: Generation anti-correlates with prices
- Renewables generate more during low-price hours (merit order effect)
- Baseload PPAs have zero shape risk

### **Merchant Tail Risk**
- **VaR (95%)**: Maximum expected loss with 95% confidence
- **CVaR (95%)**: Average loss in worst 5% of scenarios
- Captures risk beyond liquid hedge horizon (typically 3-5 years)

### **Hedging Cost**
- Bid-ask spreads on futures contracts
- Roll costs (quarterly/monthly)
- Higher for PAP PPAs due to shape risk

---

## Common Use Cases

### 1. **Compare PPA Structures**
```python
baseload = BaseloadPPA(...)
pap = PayAsProducedPPA(...)

baseload_val = baseload.value(forward_curve)
pap_val = pap.value(forward_curve)

print(f"Shape risk penalty: €{pap_val.shape_risk_premium/1e6:.2f}M")
```

### 2. **Optimize Hedge Ratio**
```python
from ppa_valuation.risk_metrics import calculate_hedge_effectiveness

# Test different hedge ratios
for ratio in [0.5, 0.75, 0.9]:
    hedged_pnl = ppa_cashflows + ratio * futures_cashflows
    var = calculate_var(hedged_pnl)
    print(f"Hedge Ratio {ratio:.0%}: VaR = €{var/1e6:.2f}M")
```

### 3. **Stress Test**
```python
from ppa_valuation.risk_metrics import stress_test_scenarios

scenarios = {
    'Price Shock +20%': {'price_shock': 0.20},
    'Price Shock -20%': {'price_shock': -0.20},
    'Low Wind Year': {'volume_shock': -0.15},
    'Shape Risk 2x': {'shape_risk_mult': 2.0}
}

results = stress_test_scenarios(ppa_valuation, scenarios)
print(results)
```

### 4. **P&L Attribution**
```python
from ppa_valuation import pnl_attribution

breakdown = pnl_attribution(
    cashflow_df=valuation.cashflow_profile,
    forward_curve=forward_curve,
    hedge_ratio=0.75
)

# See contribution from market, volume, shape, hedging, basis
for component, value in breakdown.items():
    print(f"{component}: €{value/1e6:.2f}M")
```

---

## Generation Profiles

### **Wind**
```python
from ppa_valuation.utils import create_wind_profile

# Offshore (higher capacity factor)
offshore_profile = create_wind_profile('NL_offshore')  # CF ~45%

# Onshore (lower capacity factor)
onshore_profile = create_wind_profile('NL_onshore')   # CF ~25%
```

### **Solar**
```python
from ppa_valuation.utils import create_solar_profile

solar_profile = create_solar_profile('NL')  # CF ~11%
```

### **Custom Profile**
```python
import numpy as np

# Create your own hourly profile (8760 hours)
custom_profile = np.array([...])  # Values between 0 and 1
```

---

## Next Steps

1. **Run the example**: `python examples/dutch_offshore_wind_ppa.py`
2. **Read the full docs**: Check the main README.md
3. **Explore notebooks**: See `notebooks/` for detailed walkthroughs
4. **Customize for your needs**: Modify contract parameters, profiles, curves

---

## Getting Help

- **Issues**: Open a GitHub issue
- **Questions**: Contact [your.email@example.com]
- **Documentation**: See README.md for comprehensive guide

---

## Key Files

```
ppa-valuation-framework/
├── ppa_valuation/          # Core library
│   ├── contracts.py        # PPA contract classes
│   ├── curves.py           # Forward curve models
│   ├── simulation.py       # Monte Carlo simulation
│   ├── risk_metrics.py     # VaR, CVaR, P&L attribution
│   └── utils.py            # Generation profiles, helpers
├── examples/
│   └── dutch_offshore_wind_ppa.py  # Complete example
├── tests/
│   └── test_ppa_valuation.py       # Unit tests
└── README.md               # Full documentation
```

---

**Happy valuing!** 🌊⚡
