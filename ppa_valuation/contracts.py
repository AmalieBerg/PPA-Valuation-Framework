"""
PPA Contract Models
===================

Defines different PPA contract structures and their valuation methods.
"""

import numpy as np
import pandas as pd
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class ValuationResult:
    """Container for PPA valuation results and risk metrics."""
    npv: float
    expected_revenue: float
    hedging_cost: float
    shape_risk_premium: float
    merchant_tail_var_95: float
    merchant_tail_cvar_95: float
    cashflow_profile: pd.DataFrame
    risk_breakdown: Dict[str, float]
    
    def summary(self) -> str:
        """Return formatted summary of valuation results."""
        return f"""
PPA Valuation Summary
{'='*50}
Net Present Value:        €{self.npv/1e6:>10.2f}M
Expected Revenue:         €{self.expected_revenue/1e6:>10.2f}M
Hedging Cost:             €{self.hedging_cost/1e6:>10.2f}M
Shape Risk Premium:       €{self.shape_risk_premium/1e6:>10.2f}M
Merchant Tail VaR (95%):  €{self.merchant_tail_var_95/1e6:>10.2f}M
Merchant Tail CVaR (95%): €{self.merchant_tail_cvar_95/1e6:>10.2f}M
{'='*50}
"""


class PPAContract:
    """
    Base class for Power Purchase Agreement contracts.
    
    Attributes:
        contract_type: Type of PPA ('baseload', 'pay_as_produced', 'hybrid')
        strike_price: Fixed price in EUR/MWh
        capacity_mw: Contracted capacity in MW
        start_date: Contract start date
        end_date: Contract end date
        escalation_rate: Annual price escalation (default 0.02 = 2%)
        generation_profile: Hourly generation profile (for PAP contracts)
    """
    
    def __init__(
        self,
        contract_type: str,
        strike_price: float,
        capacity_mw: float,
        start_date: str,
        end_date: str,
        escalation_rate: float = 0.02,
        generation_profile: Optional[np.ndarray] = None,
        location: str = 'NL',
        technology: str = 'wind_offshore'
    ):
        self.contract_type = contract_type.lower()
        self.strike_price = strike_price
        self.capacity_mw = capacity_mw
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date)
        self.escalation_rate = escalation_rate
        self.generation_profile = generation_profile
        self.location = location
        self.technology = technology
        
        # Validate inputs
        self._validate()
        
    def _validate(self):
        """Validate contract parameters."""
        if self.contract_type not in ['baseload', 'pay_as_produced', 'hybrid']:
            raise ValueError(f"Unknown contract type: {self.contract_type}")
        
        if self.strike_price <= 0:
            raise ValueError("Strike price must be positive")
            
        if self.capacity_mw <= 0:
            raise ValueError("Capacity must be positive")
            
        if self.start_date >= self.end_date:
            raise ValueError("End date must be after start date")
    
    def get_contract_hours(self) -> int:
        """Calculate total contract hours."""
        years = (self.end_date - self.start_date).days / 365.25
        return int(years * 8760)
    
    def get_strike_prices(self, hourly_timestamps: pd.DatetimeIndex) -> np.ndarray:
        """
        Calculate strike prices with escalation over contract period.
        
        Args:
            hourly_timestamps: Timestamps for which to calculate strikes
            
        Returns:
            Array of escalated strike prices
        """
        years_from_start = (hourly_timestamps - self.start_date).days / 365.25
        escalation_factor = (1 + self.escalation_rate) ** years_from_start
        return self.strike_price * escalation_factor
    
    def value(
        self,
        forward_curve,
        market_simulator=None,
        discount_rate: float = 0.05,
        hedge_horizon_years: int = 3,
        n_scenarios: int = 10000
    ) -> ValuationResult:
        """
        Value the PPA contract using forward curve and optional MC simulation.
        
        Args:
            forward_curve: ForwardCurve object with price expectations
            market_simulator: MarketSimulator for stochastic scenarios
            discount_rate: Annual discount rate for NPV calculation
            hedge_horizon_years: Years of liquid hedging availability
            n_scenarios: Number of Monte Carlo scenarios
            
        Returns:
            ValuationResult with NPV and risk metrics
        """
        raise NotImplementedError("Subclasses must implement value() method")


class BaseloadPPA(PPAContract):
    """
    Baseload PPA: Fixed volume delivered every hour.
    
    Simpler risk profile than PAP:
    - No volume risk (fixed delivery)
    - No shape risk (flat profile)
    - Only merchant tail risk beyond hedge horizon
    """
    
    def __init__(
        self,
        strike_price: float,
        capacity_mw: float,
        start_date: str,
        end_date: str,
        escalation_rate: float = 0.02,
        load_factor: float = 1.0,  # Baseload = 100% load factor
        **kwargs
    ):
        super().__init__(
            contract_type='baseload',
            strike_price=strike_price,
            capacity_mw=capacity_mw,
            start_date=start_date,
            end_date=end_date,
            escalation_rate=escalation_rate,
            **kwargs
        )
        self.load_factor = load_factor
    
    def value(
        self,
        forward_curve,
        market_simulator=None,
        discount_rate: float = 0.05,
        hedge_horizon_years: int = 3,
        n_scenarios: int = 10000
    ) -> ValuationResult:
        """Value baseload PPA."""
        
        # Generate hourly timestamps
        hours = pd.date_range(
            start=self.start_date,
            end=self.end_date,
            freq='h'
        )
        
        # Get forward prices and strike prices
        forward_prices = forward_curve.get_prices(hours)
        strike_prices = self.get_strike_prices(hours)
        
        # Baseload volume (constant every hour)
        volumes_mwh = np.full(len(hours), self.capacity_mw * self.load_factor)
        
        # Calculate cashflows: receive strike, pay market
        # Positive NPV = PPA better than merchant
        ppa_revenue = strike_prices * volumes_mwh
        market_cost = forward_prices * volumes_mwh
        cashflows = np.array(ppa_revenue - market_cost)
        
        # Discount cashflows
        years_from_now = np.array((hours - pd.Timestamp.now()).total_seconds() / (365.25 * 24 * 3600))
        discount_factors = np.exp(-discount_rate * years_from_now)
        discounted_cf = cashflows * discount_factors
        
        npv = float(np.sum(discounted_cf))
        expected_revenue = float(np.sum(ppa_revenue))
        
        # Split hedged vs merchant tail periods
        hedge_end = self.start_date + pd.DateOffset(years=hedge_horizon_years)
        hedged_mask = hours < hedge_end
        
        # Hedging cost (bid-ask spread, approximately 0.5 EUR/MWh)
        hedging_cost = 0.5 * volumes_mwh[hedged_mask].sum()
        
        # Merchant tail risk (simplified - would use MC simulation in production)
        merchant_cashflows = cashflows[~hedged_mask]
        if market_simulator is not None:
            # Use MC simulation for tail risk
            merchant_tail_var_95, merchant_tail_cvar_95 = self._simulate_merchant_tail(
                hours[~hedged_mask],
                volumes_mwh[~hedged_mask],
                strike_prices[~hedged_mask],
                market_simulator,
                discount_rate,
                n_scenarios
            )
        else:
            # Simplified estimate: -1 standard deviation
            merchant_tail_var_95 = -np.std(merchant_cashflows) * np.sqrt(len(merchant_cashflows))
            merchant_tail_cvar_95 = merchant_tail_var_95 * 1.2
        
        # Shape risk premium = 0 for baseload
        shape_risk_premium = 0.0
        
        # Create cashflow profile
        cashflow_df = pd.DataFrame({
            'timestamp': hours,
            'volume_mwh': volumes_mwh,
            'strike_price': strike_prices,
            'forward_price': forward_prices,
            'cashflow': cashflows,
            'discounted_cf': discounted_cf,
            'hedged': hedged_mask
        })
        
        risk_breakdown = {
            'hedged_value': discounted_cf[hedged_mask].sum(),
            'merchant_value': discounted_cf[~hedged_mask].sum(),
            'hedging_cost': -hedging_cost,
            'shape_risk': 0.0
        }
        
        return ValuationResult(
            npv=npv,
            expected_revenue=expected_revenue,
            hedging_cost=hedging_cost,
            shape_risk_premium=shape_risk_premium,
            merchant_tail_var_95=merchant_tail_var_95,
            merchant_tail_cvar_95=merchant_tail_cvar_95,
            cashflow_profile=cashflow_df,
            risk_breakdown=risk_breakdown
        )
    
    def _simulate_merchant_tail(
        self,
        timestamps: pd.DatetimeIndex,
        volumes: np.ndarray,
        strikes: np.ndarray,
        simulator,
        discount_rate: float,
        n_scenarios: int
    ) -> Tuple[float, float]:
        """Simulate merchant tail risk using Monte Carlo."""
        
        # Generate price scenarios
        price_scenarios = simulator.simulate_prices(
            timestamps=timestamps,
            n_scenarios=n_scenarios
        )
        
        # Calculate P&L for each scenario
        scenario_pnls = []
        for scenario_prices in price_scenarios:
            cashflows = np.array((strikes - scenario_prices) * volumes)
            years = np.array((timestamps - pd.Timestamp.now()).total_seconds() / (365.25 * 24 * 3600))
            discount_factors = np.exp(-discount_rate * years)
            pnl = float(np.sum(cashflows * discount_factors))
            scenario_pnls.append(pnl)
        
        scenario_pnls = np.array(scenario_pnls)
        
        # Calculate VaR and CVaR (5th percentile for 95% confidence)
        var_95 = np.percentile(scenario_pnls, 5)
        cvar_95 = scenario_pnls[scenario_pnls <= var_95].mean()
        
        return var_95, cvar_95


class PayAsProducedPPA(PPAContract):
    """
    Pay-As-Produced PPA: Volume follows actual generation profile.
    
    Complex risk profile:
    - Volume risk: Generation forecast uncertainty
    - Shape risk: Renewable profile vs market price correlation
    - Merchant tail risk beyond hedge horizon
    - Negative price exposure (wind/solar produce during low price hours)
    """
    
    def __init__(
        self,
        strike_price: float,
        capacity_mw: float,
        start_date: str,
        end_date: str,
        generation_profile: np.ndarray,
        escalation_rate: float = 0.02,
        volume_uncertainty: float = 0.10,  # 10% forecast error
        **kwargs
    ):
        super().__init__(
            contract_type='pay_as_produced',
            strike_price=strike_price,
            capacity_mw=capacity_mw,
            start_date=start_date,
            end_date=end_date,
            escalation_rate=escalation_rate,
            generation_profile=generation_profile,
            **kwargs
        )
        self.volume_uncertainty = volume_uncertainty
        
    def value(
        self,
        forward_curve,
        market_simulator=None,
        discount_rate: float = 0.05,
        hedge_horizon_years: int = 3,
        n_scenarios: int = 10000
    ) -> ValuationResult:
        """Value pay-as-produced PPA with shape risk premium."""
        
        # Generate hourly timestamps
        hours = pd.date_range(
            start=self.start_date,
            end=self.end_date,
            freq='h'
        )
        
        # Ensure generation profile matches contract length
        if len(self.generation_profile) != len(hours):
            # Tile profile to match contract length
            n_repeats = int(np.ceil(len(hours) / len(self.generation_profile)))
            tiled_profile = np.tile(self.generation_profile, n_repeats)
            volumes_mwh = tiled_profile[:len(hours)] * self.capacity_mw
        else:
            volumes_mwh = self.generation_profile * self.capacity_mw
        
        # Get forward prices and strike prices
        forward_prices = forward_curve.get_prices(hours)
        strike_prices = self.get_strike_prices(hours)
        
        # Calculate baseload equivalent for shape risk comparison
        avg_volume = volumes_mwh.mean()
        
        # PPA cashflows
        ppa_revenue = strike_prices * volumes_mwh
        market_cost = forward_prices * volumes_mwh
        cashflows = np.array(ppa_revenue - market_cost)
        
        # Discount cashflows
        years_from_now = np.array((hours - pd.Timestamp.now()).total_seconds() / (365.25 * 24 * 3600))
        discount_factors = np.exp(-discount_rate * years_from_now)
        discounted_cf = cashflows * discount_factors
        
        npv = float(np.sum(discounted_cf))
        expected_revenue = float(np.sum(ppa_revenue))
        
        # Split hedged vs merchant tail periods
        hedge_end = self.start_date + pd.DateOffset(years=hedge_horizon_years)
        hedged_mask = hours < hedge_end
        
        # Hedging cost (higher for PAP due to shape risk)
        hedging_cost = 0.75 * volumes_mwh[hedged_mask].sum()  # 0.75 EUR/MWh
        
        # Shape risk premium: loss from renewable profile vs baseload
        # Renewable generation anti-correlates with prices (merit order effect)
        shape_risk_premium = self._calculate_shape_risk(
            volumes_mwh[hedged_mask],
            forward_prices[hedged_mask],
            avg_volume
        )
        
        # Merchant tail risk with volume uncertainty
        merchant_cashflows = cashflows[~hedged_mask]
        if market_simulator is not None:
            merchant_tail_var_95, merchant_tail_cvar_95 = self._simulate_merchant_tail_pap(
                hours[~hedged_mask],
                volumes_mwh[~hedged_mask],
                strike_prices[~hedged_mask],
                market_simulator,
                discount_rate,
                n_scenarios
            )
        else:
            # Simplified estimate with volume uncertainty
            std_with_volume_risk = np.std(merchant_cashflows) * (1 + self.volume_uncertainty)
            merchant_tail_var_95 = -std_with_volume_risk * np.sqrt(len(merchant_cashflows))
            merchant_tail_cvar_95 = merchant_tail_var_95 * 1.3
        
        # Create cashflow profile
        cashflow_df = pd.DataFrame({
            'timestamp': hours,
            'volume_mwh': volumes_mwh,
            'strike_price': strike_prices,
            'forward_price': forward_prices,
            'cashflow': cashflows,
            'discounted_cf': discounted_cf,
            'hedged': hedged_mask
        })
        
        risk_breakdown = {
            'hedged_value': discounted_cf[hedged_mask].sum(),
            'merchant_value': discounted_cf[~hedged_mask].sum(),
            'hedging_cost': -hedging_cost,
            'shape_risk': shape_risk_premium
        }
        
        return ValuationResult(
            npv=npv,
            expected_revenue=expected_revenue,
            hedging_cost=hedging_cost,
            shape_risk_premium=shape_risk_premium,
            merchant_tail_var_95=merchant_tail_var_95,
            merchant_tail_cvar_95=merchant_tail_cvar_95,
            cashflow_profile=cashflow_df,
            risk_breakdown=risk_breakdown
        )
    
    def _calculate_shape_risk(
        self,
        volumes: np.ndarray,
        prices: np.ndarray,
        avg_volume: float
    ) -> float:
        """
        Calculate shape risk premium from renewable profile.
        
        Shape risk = value loss from correlation between generation and low prices.
        Renewable assets generate more during low-price hours (merit order effect).
        """
        
        # Value of PAP profile
        pap_value = (volumes * prices).sum()
        
        # Value of equivalent baseload
        baseload_value = avg_volume * prices.sum()
        
        # Shape risk premium (typically negative for renewables)
        shape_risk = pap_value - baseload_value
        
        return shape_risk
    
    def _simulate_merchant_tail_pap(
        self,
        timestamps: pd.DatetimeIndex,
        volumes: np.ndarray,
        strikes: np.ndarray,
        simulator,
        discount_rate: float,
        n_scenarios: int
    ) -> Tuple[float, float]:
        """Simulate merchant tail risk with price-volume correlation."""
        
        # Generate correlated price and volume scenarios
        price_scenarios, volume_scenarios = simulator.simulate_prices_and_volumes(
            timestamps=timestamps,
            base_volumes=volumes,
            volume_uncertainty=self.volume_uncertainty,
            correlation=-0.3,  # Negative correlation: high generation → low prices
            n_scenarios=n_scenarios
        )
        
        # Calculate P&L for each scenario
        scenario_pnls = []
        for price_path, volume_path in zip(price_scenarios, volume_scenarios):
            cashflows = np.array((strikes - price_path) * volume_path)
            years = np.array((timestamps - pd.Timestamp.now()).total_seconds() / (365.25 * 24 * 3600))
            discount_factors = np.exp(-discount_rate * years)
            pnl = float(np.sum(cashflows * discount_factors))
            scenario_pnls.append(pnl)
        
        scenario_pnls = np.array(scenario_pnls)
        
        # Calculate VaR and CVaR
        var_95 = np.percentile(scenario_pnls, 5)
        cvar_95 = scenario_pnls[scenario_pnls <= var_95].mean()
        
        return var_95, cvar_95


def create_ppa(
    contract_type: str,
    strike_price: float,
    capacity_mw: float,
    start_date: str,
    end_date: str,
    **kwargs
) -> PPAContract:
    """
    Factory function to create appropriate PPA contract type.
    
    Args:
        contract_type: 'baseload' or 'pay_as_produced'
        strike_price: Fixed price in EUR/MWh
        capacity_mw: Contracted capacity
        start_date: Contract start date
        end_date: Contract end date
        **kwargs: Additional parameters specific to contract type
        
    Returns:
        PPAContract instance
    """
    if contract_type.lower() == 'baseload':
        return BaseloadPPA(
            strike_price=strike_price,
            capacity_mw=capacity_mw,
            start_date=start_date,
            end_date=end_date,
            **kwargs
        )
    elif contract_type.lower() == 'pay_as_produced':
        if 'generation_profile' not in kwargs:
            raise ValueError("Pay-as-produced PPA requires 'generation_profile' parameter")
        return PayAsProducedPPA(
            strike_price=strike_price,
            capacity_mw=capacity_mw,
            start_date=start_date,
            end_date=end_date,
            **kwargs
        )
    else:
        raise ValueError(f"Unknown contract type: {contract_type}")