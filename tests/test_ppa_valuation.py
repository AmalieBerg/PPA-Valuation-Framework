"""
Unit Tests for PPA Valuation Framework
=======================================

Basic tests to ensure core functionality works correctly.
"""

import numpy as np
import pandas as pd
import pytest
from datetime import datetime

import sys
sys.path.insert(0, '..')

from ppa_valuation import (
    BaseloadPPA,
    PayAsProducedPPA,
    ForwardCurve,
    MarketSimulator,
    calculate_var,
    calculate_cvar
)
from ppa_valuation.utils import create_wind_profile


class TestForwardCurve:
    """Test forward curve construction."""
    
    def test_from_market_data(self):
        """Test building curve from futures prices."""
        futures = {'Y-25': 60, 'Y-26': 58, 'Y-27': 55}
        curve = ForwardCurve.from_market_data(futures)
        
        assert curve is not None
        assert len(curve.base_curve) > 0
    
    def test_get_prices(self):
        """Test retrieving prices for timestamps."""
        futures = {'Y-25': 60}
        curve = ForwardCurve.from_market_data(futures)
        
        timestamps = pd.date_range('2025-01-01', periods=24, freq='h')
        prices = curve.get_prices(timestamps)
        
        assert len(prices) == 24
        assert all(prices > 0)
        assert prices.mean() > 0
    
    def test_shift_curve(self):
        """Test parallel shift of curve."""
        futures = {'Y-25': 60}
        curve = ForwardCurve.from_market_data(futures)
        
        shifted = curve.shift_curve(10.0)
        
        # Verify shift
        ts = pd.date_range('2025-01-01', periods=1, freq='h')
        original_price = curve.get_prices(ts, include_seasonality=False)[0]
        shifted_price = shifted.get_prices(ts, include_seasonality=False)[0]
        
        assert abs((shifted_price - original_price) - 10.0) < 0.1


class TestPPAContracts:
    """Test PPA contract classes."""
    
    def test_baseload_ppa_creation(self):
        """Test creating baseload PPA."""
        ppa = BaseloadPPA(
            strike_price=50.0,
            capacity_mw=100,
            start_date='2025-01-01',
            end_date='2027-12-31'
        )
        
        assert ppa.strike_price == 50.0
        assert ppa.capacity_mw == 100
        assert ppa.contract_type == 'baseload'
    
    def test_pap_ppa_creation(self):
        """Test creating pay-as-produced PPA."""
        profile = create_wind_profile('NL_offshore')
        
        ppa = PayAsProducedPPA(
            strike_price=45.0,
            capacity_mw=100,
            start_date='2025-01-01',
            end_date='2027-12-31',
            generation_profile=profile
        )
        
        assert ppa.strike_price == 45.0
        assert ppa.contract_type == 'pay_as_produced'
        assert len(ppa.generation_profile) == 8760
    
    def test_baseload_valuation(self):
        """Test baseload PPA valuation."""
        ppa = BaseloadPPA(
            strike_price=50.0,
            capacity_mw=10,  # Small for fast test
            start_date='2025-01-01',
            end_date='2025-12-31'
        )
        
        futures = {'Y-25': 60}
        curve = ForwardCurve.from_market_data(futures)
        
        valuation = ppa.value(
            forward_curve=curve,
            discount_rate=0.05,
            n_scenarios=100  # Small for fast test
        )
        
        assert valuation.npv is not None
        assert valuation.expected_revenue > 0
        assert hasattr(valuation, 'cashflow_profile')
    
    def test_pap_valuation(self):
        """Test PAP PPA valuation."""
        profile = create_wind_profile('NL_offshore')
        
        ppa = PayAsProducedPPA(
            strike_price=45.0,
            capacity_mw=10,
            start_date='2025-01-01',
            end_date='2025-12-31',
            generation_profile=profile
        )
        
        futures = {'Y-25': 60}
        curve = ForwardCurve.from_market_data(futures)
        
        valuation = ppa.value(
            forward_curve=curve,
            discount_rate=0.05,
            n_scenarios=100
        )
        
        assert valuation.npv is not None
        assert valuation.shape_risk_premium != 0  # PAP should have shape risk


class TestMarketSimulator:
    """Test Monte Carlo simulation."""
    
    def test_simulator_creation(self):
        """Test creating market simulator."""
        futures = {'Y-25': 60}
        curve = ForwardCurve.from_market_data(futures)
        
        simulator = MarketSimulator(
            forward_curve=curve,
            annual_volatility=0.35
        )
        
        assert simulator is not None
        assert simulator.annual_volatility == 0.35
    
    def test_simulate_prices(self):
        """Test price simulation."""
        futures = {'Y-25': 60}
        curve = ForwardCurve.from_market_data(futures)
        
        simulator = MarketSimulator(
            forward_curve=curve,
            seed=42
        )
        
        timestamps = pd.date_range('2025-01-01', periods=100, freq='h')
        prices = simulator.simulate_prices(
            timestamps=timestamps,
            n_scenarios=10
        )
        
        assert prices.shape == (10, 100)
        assert all(prices.flatten() > 0)  # All prices positive
    
    def test_simulate_volumes(self):
        """Test volume simulation."""
        futures = {'Y-25': 60}
        curve = ForwardCurve.from_market_data(futures)
        
        simulator = MarketSimulator(
            forward_curve=curve,
            seed=42
        )
        
        timestamps = pd.date_range('2025-01-01', periods=100, freq='h')
        base_volumes = np.full(100, 50.0)  # 50 MWh base
        
        volumes = simulator.simulate_volumes(
            timestamps=timestamps,
            base_volumes=base_volumes,
            volume_uncertainty=0.1,
            n_scenarios=10
        )
        
        assert volumes.shape == (10, 100)
        assert all(volumes.flatten() >= 0)  # All volumes non-negative


class TestRiskMetrics:
    """Test risk metrics calculations."""
    
    def test_var_calculation(self):
        """Test VaR calculation."""
        returns = np.random.normal(0, 1, 1000)
        var_95 = calculate_var(returns, 0.95)
        
        assert var_95 < 0  # VaR should be negative (loss)
        assert var_95 < np.percentile(returns, 10)
    
    def test_cvar_calculation(self):
        """Test CVaR calculation."""
        returns = np.random.normal(0, 1, 1000)
        cvar_95 = calculate_cvar(returns, 0.95)
        var_95 = calculate_var(returns, 0.95)
        
        assert cvar_95 <= var_95  # CVaR should be worse than VaR
    
    def test_var_ordering(self):
        """Test that CVaR >= VaR (both negative)."""
        returns = np.random.normal(-0.5, 2, 1000)
        
        var_90 = calculate_var(returns, 0.90)
        var_95 = calculate_var(returns, 0.95)
        var_99 = calculate_var(returns, 0.99)
        
        # Higher confidence = more negative VaR (worse loss)
        assert var_99 <= var_95 <= var_90


class TestUtils:
    """Test utility functions."""
    
    def test_wind_profile_creation(self):
        """Test wind generation profile."""
        profile = create_wind_profile('NL_offshore')
        
        assert len(profile) == 8760
        assert all(profile >= 0)
        assert all(profile <= 1)
        assert 0.40 < profile.mean() < 0.50  # Capacity factor check
    
    def test_wind_profile_seasonal(self):
        """Test wind profile has seasonal variation."""
        profile = create_wind_profile('NL_offshore')
        
        # Split into quarters
        q1 = profile[:2190].mean()
        q2 = profile[2190:4380].mean()
        q3 = profile[4380:6570].mean()
        q4 = profile[6570:].mean()
        
        # Q1 and Q4 should have higher capacity factors (winter)
        assert q1 > q3  # Winter > Summer
        assert q4 > q3


def run_tests():
    """Run all tests."""
    pytest.main([__file__, '-v'])


if __name__ == '__main__':
    run_tests()
