"""
Utilities
=========

Helper functions and data for PPA valuation.
"""

import numpy as np
import pandas as pd
from typing import Optional


def create_wind_profile(
    location: str = 'NL_offshore',
    year_hours: int = 8760,
    capacity_factor: Optional[float] = None
) -> np.ndarray:
    """
    Generate realistic wind generation profile.
    
    Args:
        location: 'NL_offshore', 'NL_onshore', 'NO_offshore', etc.
        year_hours: Number of hours in profile
        capacity_factor: Override default capacity factor
        
    Returns:
        Hourly generation profile (0-1, fraction of capacity)
    """
    # Default capacity factors by location
    cf_defaults = {
        'NL_offshore': 0.45,
        'NL_onshore': 0.25,
        'NO_offshore': 0.50,
        'NO_onshore': 0.30,
        'DE_offshore': 0.43,
        'DE_onshore': 0.22
    }
    
    cf = capacity_factor if capacity_factor is not None else cf_defaults.get(location, 0.35)
    
    # Generate base profile with seasonal and diurnal patterns
    hours = np.arange(year_hours)
    
    # Seasonal pattern: higher in winter (Q1, Q4)
    day_of_year = (hours / 24) % 365
    seasonal = 1.0 + 0.3 * np.cos(2 * np.pi * (day_of_year - 15) / 365)
    
    # Diurnal pattern: slight variation (less pronounced than solar)
    hour_of_day = hours % 24
    diurnal = 1.0 + 0.1 * np.cos(2 * np.pi * (hour_of_day - 14) / 24)
    
    # Random weather variations (autocorrelated)
    np.random.seed(42)
    weather = np.random.normal(0, 0.3, year_hours)
    # Apply autocorrelation (weather persistence)
    for i in range(1, year_hours):
        weather[i] = 0.9 * weather[i-1] + 0.1 * weather[i]
    
    # Combine patterns
    profile = cf * seasonal * diurnal * (1 + weather)
    
    # Clip to [0, 1] and ensure non-negative
    profile = np.clip(profile, 0, 1)
    
    # Adjust to match target capacity factor
    profile = profile * (cf / profile.mean())
    
    return profile


def create_solar_profile(
    location: str = 'NL',
    year_hours: int = 8760,
    capacity_factor: Optional[float] = None
) -> np.ndarray:
    """
    Generate realistic solar PV generation profile.
    
    Args:
        location: 'NL', 'NO', 'DE', etc.
        year_hours: Number of hours in profile
        capacity_factor: Override default capacity factor
        
    Returns:
        Hourly generation profile (0-1, fraction of capacity)
    """
    # Default capacity factors by location
    cf_defaults = {
        'NL': 0.11,
        'NO': 0.10,
        'DE': 0.12,
        'ES': 0.18,
        'IT': 0.16
    }
    
    cf = capacity_factor if capacity_factor is not None else cf_defaults.get(location, 0.12)
    
    hours = np.arange(year_hours)
    
    # Seasonal pattern: peak in summer (Q2-Q3)
    day_of_year = (hours / 24) % 365
    seasonal = 1.0 + 0.8 * np.cos(2 * np.pi * (day_of_year - 172) / 365)  # Peak at summer solstice
    
    # Strong diurnal pattern: only generate during day
    hour_of_day = hours % 24
    # Solar curve: zero at night, peak at midday
    diurnal = np.maximum(0, np.cos(2 * np.pi * (hour_of_day - 12) / 24))
    diurnal = diurnal ** 2  # Sharper peak
    
    # Cloud/weather variations
    np.random.seed(43)
    weather = np.random.normal(0, 0.2, year_hours)
    for i in range(1, year_hours):
        weather[i] = 0.7 * weather[i-1] + 0.3 * weather[i]
    
    # Combine patterns
    profile = cf * seasonal * diurnal * (1 + weather)
    
    # Clip and normalize
    profile = np.clip(profile, 0, 1)
    profile = profile * (cf / (profile.mean() + 1e-6))
    
    return profile


def create_hydro_profile(
    location: str = 'NO',
    year_hours: int = 8760,
    capacity_factor: Optional[float] = None,
    reservoir_type: str = 'seasonal'
) -> np.ndarray:
    """
    Generate hydro generation profile (Nordic markets).
    
    Args:
        location: 'NO', 'SE', etc.
        year_hours: Number of hours
        capacity_factor: Override default
        reservoir_type: 'run_of_river' or 'seasonal'
        
    Returns:
        Hourly generation profile
    """
    cf = capacity_factor if capacity_factor is not None else 0.45
    
    hours = np.arange(year_hours)
    day_of_year = (hours / 24) % 365
    
    if reservoir_type == 'run_of_river':
        # Follow natural inflow pattern
        seasonal = 1.0 + 0.5 * np.cos(2 * np.pi * (day_of_year - 150) / 365)  # Peak in spring
    else:  # seasonal storage
        # Optimized dispatch: higher in winter (high prices)
        seasonal = 1.0 + 0.4 * np.cos(2 * np.pi * (day_of_year - 15) / 365)
    
    # Price-responsive dispatch (higher during peak hours)
    hour_of_day = hours % 24
    hourly = 1.0 + 0.2 * (
        (hour_of_day >= 7) & (hour_of_day <= 9) |
        (hour_of_day >= 17) & (hour_of_day <= 20)
    ).astype(float)
    
    profile = cf * seasonal * hourly
    profile = np.clip(profile, 0, 1)
    profile = profile * (cf / profile.mean())
    
    return profile


def load_entso_e_data(
    country_code: str = 'NL',
    year: int = 2024,
    data_type: str = 'generation'
) -> pd.DataFrame:
    """
    Placeholder for loading ENTSO-E data.
    
    In production, would use ENTSO-E API to get actual generation/price data.
    
    Args:
        country_code: ISO country code
        year: Year of data
        data_type: 'generation', 'prices', or 'load'
        
    Returns:
        DataFrame with timestamp and values
    """
    # This is a placeholder - in production would call ENTSO-E API
    timestamps = pd.date_range(
        start=f'{year}-01-01',
        end=f'{year}-12-31 23:00:00',
        freq='h'
    )
    
    # Generate synthetic data for demonstration
    if data_type == 'generation':
        if country_code == 'NL':
            profile = create_wind_profile('NL_offshore', len(timestamps))
        else:
            profile = create_wind_profile('NO_offshore', len(timestamps))
        
        df = pd.DataFrame({
            'timestamp': timestamps,
            'generation_mw': profile * 1000  # Example 1000 MW capacity
        })
    
    elif data_type == 'prices':
        # Synthetic price data
        base_price = 60.0
        seasonal = 1.0 + 0.2 * np.cos(2 * np.pi * (timestamps.dayofyear - 15) / 365)
        hourly_factors = np.array([0.75, 0.70, 0.68, 0.67, 0.68, 0.72,
                                   0.85, 1.05, 1.20, 1.25, 1.28, 1.30,
                                   1.30, 1.28, 1.25, 1.22, 1.20, 1.35,
                                   1.40, 1.42, 1.35, 1.15, 0.95, 0.80])
        hourly = hourly_factors[timestamps.hour]
        noise = np.random.normal(1.0, 0.15, len(timestamps))
        
        prices = base_price * seasonal * hourly * noise
        
        df = pd.DataFrame({
            'timestamp': timestamps,
            'price_eur_mwh': prices
        })
    
    else:  # load
        # Synthetic load data
        seasonal = 1.0 + 0.3 * np.cos(2 * np.pi * (timestamps.dayofyear - 15) / 365)
        is_weekend = (timestamps.dayofweek >= 5).astype(float)
        hourly_factors = np.array([0.70, 0.65, 0.63, 0.62, 0.65, 0.75,
                                   0.90, 1.15, 1.25, 1.20, 1.15, 1.10,
                                   1.05, 1.00, 0.98, 1.00, 1.10, 1.30,
                                   1.35, 1.30, 1.20, 1.05, 0.90, 0.75])
        hourly = hourly_factors[timestamps.hour]
        weekend_factor = 1.0 - 0.15 * is_weekend
        
        load = 15000 * seasonal * hourly * weekend_factor  # Example base load
        
        df = pd.DataFrame({
            'timestamp': timestamps,
            'load_mw': load
        })
    
    return df


def calculate_strike_from_lcoe(
    capacity_mw: float,
    capex_eur_per_kw: float,
    opex_eur_per_kw_year: float,
    capacity_factor: float,
    lifetime_years: int = 25,
    wacc: float = 0.06
) -> float:
    """
    Calculate PPA strike price from project LCOE.
    
    Used to reverse-engineer fair PPA prices from project economics.
    
    Args:
        capacity_mw: Project capacity
        capex_eur_per_kw: Capital expenditure
        opex_eur_per_kw_year: Annual operating costs
        capacity_factor: Expected capacity factor
        lifetime_years: Project lifetime
        wacc: Weighted average cost of capital
        
    Returns:
        LCOE in EUR/MWh (fair PPA strike)
    """
    capacity_kw = capacity_mw * 1000
    
    # Annual generation
    annual_mwh = capacity_mw * 8760 * capacity_factor
    
    # Present value of OPEX
    opex_annual = opex_eur_per_kw_year * capacity_kw
    pv_opex = sum(opex_annual / (1 + wacc)**t for t in range(1, lifetime_years + 1))
    
    # Total cost
    total_cost = capex_eur_per_kw * capacity_kw + pv_opex
    
    # Present value of generation
    pv_generation = sum(annual_mwh / (1 + wacc)**t for t in range(1, lifetime_years + 1))
    
    # LCOE
    lcoe = total_cost / pv_generation
    
    return lcoe


def format_currency(value: float, millions: bool = True) -> str:
    """Format currency values for display."""
    if millions:
        return f"€{value/1e6:.2f}M"
    else:
        return f"€{value:,.0f}"


def calculate_ppa_tenor_value(
    strike_price: float,
    capacity_mw: float,
    generation_profile: np.ndarray,
    forward_curve,
    max_tenor_years: int = 15
) -> pd.DataFrame:
    """
    Calculate PPA value for different tenors (contract lengths).
    
    Helps optimize contract duration.
    
    Args:
        strike_price: PPA strike
        capacity_mw: Capacity
        generation_profile: Hourly profile
        forward_curve: Price curve
        max_tenor_years: Maximum tenor to analyze
        
    Returns:
        DataFrame with tenor analysis
    """
    results = []
    
    for tenor in range(5, max_tenor_years + 1):
        # Calculate NPV for this tenor
        hours = pd.date_range(
            start='2025-01-01',
            periods=tenor * 8760,
            freq='h'
        )
        
        profile_tiled = np.tile(generation_profile, tenor)[:len(hours)]
        volumes = profile_tiled * capacity_mw
        
        forward_prices = forward_curve.get_prices(hours)
        strikes = np.full(len(hours), strike_price)
        
        cashflows = (strikes - forward_prices) * volumes
        years_from_now = (hours - pd.Timestamp.now()).days / 365.25
        discount_factors = np.exp(-0.05 * years_from_now)
        
        npv = (cashflows * discount_factors).sum()
        annual_value = npv / tenor
        
        results.append({
            'tenor_years': tenor,
            'npv': npv,
            'annual_value': annual_value,
            'total_mwh': volumes.sum()
        })
    
    return pd.DataFrame(results)
