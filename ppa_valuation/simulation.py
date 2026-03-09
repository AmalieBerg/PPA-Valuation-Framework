"""
Market Simulation
=================

Monte Carlo simulation for power prices and renewable generation volumes.
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional
from scipy.stats import norm


class MarketSimulator:
    """
    Monte Carlo simulator for power prices and renewable generation.
    
    Supports:
    - Geometric Brownian Motion with mean reversion
    - Jump diffusion for extreme events
    - GARCH volatility (time-varying)
    - Correlated price-volume scenarios
    """
    
    def __init__(
        self,
        forward_curve,
        volatility_model: str = 'constant',
        annual_volatility: float = 0.35,
        mean_reversion_speed: float = 0.5,
        jump_intensity: float = 2.0,  # jumps per year
        jump_size_mean: float = 0.0,
        jump_size_std: float = 0.15,
        seed: Optional[int] = None
    ):
        """
        Initialize market simulator.
        
        Args:
            forward_curve: ForwardCurve object for drift term
            volatility_model: 'constant', 'garch', or 'heston'
            annual_volatility: Annualized volatility (e.g., 0.35 = 35%)
            mean_reversion_speed: Speed of reversion to forward curve
            jump_intensity: Expected number of jumps per year
            jump_size_mean: Mean jump size (log-returns)
            jump_size_std: Jump size volatility
            seed: Random seed for reproducibility
        """
        self.forward_curve = forward_curve
        self.volatility_model = volatility_model
        self.annual_volatility = annual_volatility
        self.mean_reversion_speed = mean_reversion_speed
        self.jump_intensity = jump_intensity
        self.jump_size_mean = jump_size_mean
        self.jump_size_std = jump_size_std
        
        if seed is not None:
            np.random.seed(seed)
    
    def simulate_prices(
        self,
        timestamps: pd.DatetimeIndex,
        n_scenarios: int = 10000,
        include_jumps: bool = True
    ) -> np.ndarray:
        """
        Simulate price scenarios using mean-reverting GBM with jumps.
        
        Args:
            timestamps: Hourly timestamps to simulate
            n_scenarios: Number of Monte Carlo paths
            include_jumps: Include jump-diffusion component
            
        Returns:
            Array of shape (n_scenarios, n_timesteps) with prices
        """
        n_steps = len(timestamps)
        dt = 1/8760  # Hourly timestep in years
        
        # Get forward prices as drift term
        forward_prices = self.forward_curve.get_prices(timestamps)
        
        # Initialize price paths
        prices = np.zeros((n_scenarios, n_steps))
        prices[:, 0] = forward_prices[0]  # Start at forward price
        
        # Generate random shocks
        dW = np.random.normal(0, np.sqrt(dt), (n_scenarios, n_steps-1))
        
        # Generate jump component if requested
        if include_jumps:
            jump_prob = self.jump_intensity * dt
            jumps = np.random.binomial(1, jump_prob, (n_scenarios, n_steps-1))
            jump_sizes = np.random.normal(
                self.jump_size_mean,
                self.jump_size_std,
                (n_scenarios, n_steps-1)
            )
            jump_component = jumps * jump_sizes
        else:
            jump_component = 0
        
        # Simulate paths with mean reversion
        for t in range(1, n_steps):
            # Mean reversion toward forward curve
            drift = self.mean_reversion_speed * (
                np.log(forward_prices[t]) - np.log(prices[:, t-1])
            )
            
            # Volatility component
            if self.volatility_model == 'constant':
                vol = self.annual_volatility
            else:
                # Simplified GARCH: higher vol in extremes
                vol = self.annual_volatility * (
                    1 + 0.3 * np.abs(np.log(prices[:, t-1] / forward_prices[t-1]))
                )
            
            # Update prices (log-normal to ensure positivity)
            log_return = drift * dt + vol * dW[:, t-1] + jump_component[:, t-1]
            prices[:, t] = prices[:, t-1] * np.exp(log_return)
            
            # Floor prices at zero (handle negative price scenarios separately if needed)
            prices[:, t] = np.maximum(prices[:, t], 0.01)
        
        return prices
    
    def simulate_volumes(
        self,
        timestamps: pd.DatetimeIndex,
        base_volumes: np.ndarray,
        volume_uncertainty: float = 0.10,
        n_scenarios: int = 10000
    ) -> np.ndarray:
        """
        Simulate renewable generation volume scenarios.
        
        Args:
            timestamps: Hourly timestamps
            base_volumes: Expected generation profile (MWh)
            volume_uncertainty: Forecast error (std/mean)
            n_scenarios: Number of scenarios
            
        Returns:
            Array of shape (n_scenarios, n_timesteps) with volumes
        """
        n_steps = len(timestamps)
        
        # Model volumes as lognormal (ensures non-negativity)
        # with auto-correlation (weather persistence)
        volumes = np.zeros((n_scenarios, n_steps))
        
        # Auto-correlation for weather persistence
        phi = 0.95  # High persistence (24-hour weather correlation)
        
        for scenario in range(n_scenarios):
            epsilon = np.random.normal(0, 1, n_steps)
            innovations = np.zeros(n_steps)
            innovations[0] = epsilon[0]
            
            # AR(1) process for innovations
            for t in range(1, n_steps):
                innovations[t] = phi * innovations[t-1] + np.sqrt(1 - phi**2) * epsilon[t]
            
            # Transform to lognormal volumes
            log_sigma = volume_uncertainty
            volumes[scenario] = base_volumes * np.exp(
                -0.5 * log_sigma**2 + log_sigma * innovations
            )
        
        return volumes
    
    def simulate_prices_and_volumes(
        self,
        timestamps: pd.DatetimeIndex,
        base_volumes: np.ndarray,
        volume_uncertainty: float = 0.10,
        correlation: float = -0.3,
        n_scenarios: int = 10000
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Simulate correlated price and volume scenarios.
        
        Key insight: High renewable generation → low prices (merit order effect)
        
        Args:
            timestamps: Hourly timestamps
            base_volumes: Expected generation profile
            volume_uncertainty: Volume forecast error
            correlation: Price-volume correlation (typically negative)
            n_scenarios: Number of scenarios
            
        Returns:
            Tuple of (price_scenarios, volume_scenarios)
        """
        n_steps = len(timestamps)
        dt = 1/8760
        
        # Generate correlated random shocks
        Z1 = np.random.normal(0, 1, (n_scenarios, n_steps-1))
        Z2 = np.random.normal(0, 1, (n_scenarios, n_steps-1))
        
        # Correlated shocks using Cholesky decomposition
        price_shocks = Z1
        volume_shocks = correlation * Z1 + np.sqrt(1 - correlation**2) * Z2
        
        # Simulate prices
        forward_prices = self.forward_curve.get_prices(timestamps)
        prices = np.zeros((n_scenarios, n_steps))
        prices[:, 0] = forward_prices[0]
        
        for t in range(1, n_steps):
            drift = self.mean_reversion_speed * (
                np.log(forward_prices[t]) - np.log(prices[:, t-1])
            )
            vol = self.annual_volatility
            log_return = drift * dt + vol * np.sqrt(dt) * price_shocks[:, t-1]
            prices[:, t] = prices[:, t-1] * np.exp(log_return)
            prices[:, t] = np.maximum(prices[:, t], 0.01)
        
        # Simulate correlated volumes
        volumes = np.zeros((n_scenarios, n_steps))
        phi = 0.95  # Weather persistence
        
        for scenario in range(n_scenarios):
            innovations = np.zeros(n_steps)
            innovations[0] = volume_shocks[scenario, 0]
            
            for t in range(1, n_steps):
                innovations[t] = (
                    phi * innovations[t-1] + 
                    np.sqrt(1 - phi**2) * volume_shocks[scenario, t-1]
                )
            
            log_sigma = volume_uncertainty
            volumes[scenario] = base_volumes * np.exp(
                -0.5 * log_sigma**2 + log_sigma * innovations
            )
        
        return prices, volumes
    
    def simulate_negative_price_scenarios(
        self,
        timestamps: pd.DatetimeIndex,
        base_prices: np.ndarray,
        negative_prob: float = 0.05,
        n_scenarios: int = 10000
    ) -> np.ndarray:
        """
        Simulate scenarios including negative prices (Germany/Netherlands).
        
        Negative prices occur during:
        - High renewable generation + low demand
        - Grid congestion
        - Must-run generation (nuclear/lignite) + renewables oversupply
        
        Args:
            timestamps: Hourly timestamps
            base_prices: Forward price expectations
            negative_prob: Probability of negative prices per hour
            n_scenarios: Number of scenarios
            
        Returns:
            Price scenarios including negatives
        """
        n_steps = len(timestamps)
        
        # First simulate normal prices
        prices = self.simulate_prices(timestamps, n_scenarios, include_jumps=True)
        
        # Identify hours with high negative price probability
        # (typically: sunny/windy midday hours in Q2-Q3)
        hours = timestamps.hour
        quarters = timestamps.quarter
        
        # Higher probability during midday (10-15) in Q2-Q3
        hour_factor = np.where((hours >= 10) & (hours <= 15), 2.0, 1.0)
        quarter_factor = np.where((quarters == 2) | (quarters == 3), 1.5, 1.0)
        adjusted_prob = negative_prob * hour_factor * quarter_factor
        
        # Generate negative price events
        for t in range(n_steps):
            negative_events = np.random.random(n_scenarios) < adjusted_prob[t]
            n_negative = negative_events.sum()
            
            if n_negative > 0:
                # Negative prices: uniform between -50 and 0 EUR/MWh
                negative_prices = np.random.uniform(-50, 0, n_negative)
                prices[negative_events, t] = negative_prices
        
        return prices


def create_market_simulator(
    forward_curve,
    market_regime: str = 'normal'
) -> MarketSimulator:
    """
    Create market simulator with preset parameters for different regimes.
    
    Args:
        forward_curve: ForwardCurve object
        market_regime: 'normal', 'high_vol', or 'crisis'
        
    Returns:
        MarketSimulator instance
    """
    regimes = {
        'normal': {
            'annual_volatility': 0.35,
            'mean_reversion_speed': 0.5,
            'jump_intensity': 2.0,
            'jump_size_std': 0.15
        },
        'high_vol': {
            'annual_volatility': 0.55,
            'mean_reversion_speed': 0.3,
            'jump_intensity': 5.0,
            'jump_size_std': 0.25
        },
        'crisis': {
            'annual_volatility': 0.85,
            'mean_reversion_speed': 0.2,
            'jump_intensity': 10.0,
            'jump_size_std': 0.40
        }
    }
    
    if market_regime not in regimes:
        raise ValueError(f"Unknown regime: {market_regime}. Choose from {list(regimes.keys())}")
    
    params = regimes[market_regime]
    
    return MarketSimulator(
        forward_curve=forward_curve,
        **params
    )
