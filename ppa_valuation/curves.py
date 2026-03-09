"""
Forward Curve Construction
===========================

Build and manage forward power price curves from market data.
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional, Union
from datetime import datetime
from scipy.interpolate import interp1d


class ForwardCurve:
    """
    Forward power price curve with seasonal adjustments.
    
    Constructs hourly forward prices from:
    - Yearly/quarterly/monthly futures prices
    - Seasonal factors (day/night, weekday/weekend, quarters)
    - Time-of-day profiles
    """
    
    def __init__(
        self,
        base_curve: pd.Series,
        seasonal_factors: Optional[Dict[str, float]] = None,
        hourly_factors: Optional[np.ndarray] = None
    ):
        """
        Initialize forward curve.
        
        Args:
            base_curve: Time series of base prices (indexed by date)
            seasonal_factors: Dict of seasonal multipliers (Q1, Q2, Q3, Q4)
            hourly_factors: Array of 24 hourly factors (0-23)
        """
        self.base_curve = base_curve.sort_index()
        self.seasonal_factors = seasonal_factors or self._default_seasonal_factors()
        self.hourly_factors = hourly_factors or self._default_hourly_factors()
        
    @staticmethod
    def _default_seasonal_factors() -> Dict[str, float]:
        """Default seasonal factors for European power markets."""
        return {
            'Q1': 1.15,  # Winter: high demand
            'Q2': 0.95,  # Spring: mild, high renewables
            'Q3': 0.90,  # Summer: low demand, high solar
            'Q4': 1.10   # Autumn: rising demand
        }
    
    @staticmethod
    def _default_hourly_factors() -> np.ndarray:
        """
        Default hourly factors for European power markets.
        
        Represents typical daily price shape:
        - Night hours (0-6): Low demand, low prices
        - Morning ramp (7-9): Demand increase
        - Day hours (10-16): Peak demand
        - Evening peak (17-20): Highest demand
        - Late evening (21-23): Demand decline
        """
        factors = np.array([
            0.75, 0.70, 0.68, 0.67, 0.68, 0.72,  # 0-5: Night
            0.85, 1.05, 1.20, 1.25, 1.28, 1.30,  # 6-11: Morning ramp + day
            1.30, 1.28, 1.25, 1.22, 1.20, 1.35,  # 12-17: Day + evening start
            1.40, 1.42, 1.35, 1.15, 0.95, 0.80   # 18-23: Evening peak + decline
        ])
        return factors / factors.mean()  # Normalize to mean = 1.0
    
    @classmethod
    def from_market_data(
        cls,
        futures_prices: Dict[str, float],
        seasonal_factors: Optional[Dict[str, float]] = None,
        hourly_factors: Optional[np.ndarray] = None,
        reference_date: Optional[str] = None
    ) -> 'ForwardCurve':
        """
        Construct forward curve from market futures prices.
        
        Args:
            futures_prices: Dict mapping contract names to prices
                           (e.g., {'Y-25': 60, 'Q1-25': 65, 'M-Jan-25': 70})
            seasonal_factors: Optional seasonal adjustments
            hourly_factors: Optional hourly profiles
            reference_date: Reference date for curve (default: today)
            
        Returns:
            ForwardCurve instance
            
        Example:
            >>> futures = {'Y-25': 60, 'Y-26': 58, 'Y-27': 55}
            >>> curve = ForwardCurve.from_market_data(futures)
        """
        ref_date = pd.to_datetime(reference_date) if reference_date else pd.Timestamp.now()
        
        # Parse futures contracts
        contracts = []
        for contract, price in futures_prices.items():
            parsed = cls._parse_contract(contract, ref_date)
            if parsed:
                contracts.append((*parsed, price))
        
        # Build base curve from contracts
        base_curve = cls._build_base_curve(contracts, ref_date)
        
        return cls(
            base_curve=base_curve,
            seasonal_factors=seasonal_factors,
            hourly_factors=hourly_factors
        )
    
    @staticmethod
    def _parse_contract(
        contract_name: str,
        ref_date: pd.Timestamp
    ) -> Optional[tuple]:
        """
        Parse futures contract name to date range.
        
        Supports formats:
        - Y-25, Y-2025: Calendar year
        - Q1-25, Q1-2025: Quarter
        - M-Jan-25, M-2025-01: Month
        """
        parts = contract_name.upper().replace('_', '-').split('-')
        
        try:
            if parts[0] == 'Y':  # Yearly
                year = int(parts[1]) if len(parts[1]) == 4 else 2000 + int(parts[1])
                start = pd.Timestamp(f'{year}-01-01')
                end = pd.Timestamp(f'{year}-12-31')
                return (start, end, 'Y')
                
            elif parts[0] == 'Q':  # Quarterly
                quarter = int(parts[0][1])
                year = int(parts[1]) if len(parts[1]) == 4 else 2000 + int(parts[1])
                start = pd.Timestamp(f'{year}-01-01') + pd.DateOffset(months=3*(quarter-1))
                end = start + pd.DateOffset(months=3) - pd.Timedelta(days=1)
                return (start, end, 'Q')
                
            elif parts[0] == 'M':  # Monthly
                month = parts[1]
                year = int(parts[2]) if len(parts[2]) == 4 else 2000 + int(parts[2])
                start = pd.Timestamp(f'{year}-{month}-01')
                end = start + pd.offsets.MonthEnd(1)
                return (start, end, 'M')
                
        except (ValueError, IndexError):
            pass
        
        return None
    
    @staticmethod
    def _build_base_curve(
        contracts: list,
        ref_date: pd.Timestamp,
        forward_years: int = 15
    ) -> pd.Series:
        """
        Build daily base curve from futures contracts using interpolation.
        
        Args:
            contracts: List of (start, end, type, price) tuples
            ref_date: Reference date
            forward_years: Number of years to project
            
        Returns:
            Daily base price series
        """
        # Create daily date range
        end_date = ref_date + pd.DateOffset(years=forward_years)
        dates = pd.date_range(start=ref_date, end=end_date, freq='D')
        
        # Initialize prices array
        prices = np.full(len(dates), np.nan)
        
        # Fill prices from contracts (priority: M > Q > Y)
        contracts_sorted = sorted(contracts, key=lambda x: {'M': 0, 'Q': 1, 'Y': 2}[x[2]])
        
        for start, end, contract_type, price in contracts_sorted:
            mask = (dates >= start) & (dates <= end)
            prices[mask] = price
        
        # Interpolate missing values
        known_mask = ~np.isnan(prices)
        if known_mask.sum() > 1:
            interpolator = interp1d(
                np.where(known_mask)[0],
                prices[known_mask],
                kind='linear',
                fill_value='extrapolate'
            )
            unknown_mask = np.isnan(prices)
            prices[unknown_mask] = interpolator(np.where(unknown_mask)[0])
        else:
            # If insufficient data, use flat curve
            prices[:] = contracts[0][3] if contracts else 50.0
        
        return pd.Series(prices, index=dates)
    
    def get_prices(
        self,
        timestamps: Union[pd.DatetimeIndex, pd.Timestamp],
        include_seasonality: bool = True
    ) -> np.ndarray:
        """
        Get forward prices for specific timestamps.
        
        Args:
            timestamps: Single timestamp or array of timestamps
            include_seasonality: Apply seasonal and hourly factors
            
        Returns:
            Array of forward prices in EUR/MWh
        """
        if isinstance(timestamps, pd.Timestamp):
            timestamps = pd.DatetimeIndex([timestamps])
        
        # Get base prices (daily)
        dates = timestamps.normalize()
        base_prices = self.base_curve.reindex(dates, method='nearest').values
        
        if not include_seasonality:
            return base_prices
        
        # Apply seasonal factors
        quarters = timestamps.quarter
        seasonal_multipliers = np.array([
            self.seasonal_factors[f'Q{q}'] for q in quarters
        ])
        
        # Apply hourly factors
        hours = timestamps.hour
        hourly_multipliers = self.hourly_factors[hours]
        
        # Combine adjustments
        prices = base_prices * seasonal_multipliers * hourly_multipliers
        
        return prices
    
    def get_average_price(
        self,
        start_date: Union[str, pd.Timestamp],
        end_date: Union[str, pd.Timestamp],
        profile: Optional[np.ndarray] = None
    ) -> float:
        """
        Calculate volume-weighted average price over a period.
        
        Args:
            start_date: Period start
            end_date: Period end
            profile: Optional generation profile (default: flat)
            
        Returns:
            Average price in EUR/MWh
        """
        timestamps = pd.date_range(
            start=start_date,
            end=end_date,
            freq='h'
        )
        
        prices = self.get_prices(timestamps)
        
        if profile is None:
            return prices.mean()
        else:
            # Ensure profile matches length
            if len(profile) != len(prices):
                profile = np.tile(profile, int(np.ceil(len(prices) / len(profile))))[:len(prices)]
            return np.average(prices, weights=profile)
    
    def shift_curve(self, shift_eur: float) -> 'ForwardCurve':
        """
        Create a shifted forward curve (parallel shift).
        
        Args:
            shift_eur: Shift amount in EUR/MWh
            
        Returns:
            New ForwardCurve with shifted prices
        """
        shifted_base = self.base_curve + shift_eur
        return ForwardCurve(
            base_curve=shifted_base,
            seasonal_factors=self.seasonal_factors,
            hourly_factors=self.hourly_factors
        )
    
    def scale_curve(self, scale_factor: float) -> 'ForwardCurve':
        """
        Create a scaled forward curve (multiplicative).
        
        Args:
            scale_factor: Scaling factor (e.g., 1.1 = +10%)
            
        Returns:
            New ForwardCurve with scaled prices
        """
        scaled_base = self.base_curve * scale_factor
        return ForwardCurve(
            base_curve=scaled_base,
            seasonal_factors=self.seasonal_factors,
            hourly_factors=self.hourly_factors
        )
    
    def plot(self, years: int = 5) -> None:
        """
        Plot the forward curve.
        
        Args:
            years: Number of years to display
        """
        import matplotlib.pyplot as plt
        
        end_date = self.base_curve.index[0] + pd.DateOffset(years=years)
        plot_dates = pd.date_range(
            start=self.base_curve.index[0],
            end=end_date,
            freq='D'
        )
        
        prices = self.base_curve.reindex(plot_dates, method='nearest')
        
        plt.figure(figsize=(12, 6))
        plt.plot(prices.index, prices.values, linewidth=2)
        plt.xlabel('Date')
        plt.ylabel('Price (EUR/MWh)')
        plt.title('Forward Power Price Curve')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()


def create_dutch_forward_curve(
    front_year_price: float = 60.0,
    mean_reversion_level: float = 55.0,
    mean_reversion_speed: float = 0.3
) -> ForwardCurve:
    """
    Create a realistic forward curve for Dutch power market.
    
    Uses mean-reverting model: prices decay toward long-run marginal cost.
    
    Args:
        front_year_price: Price for next calendar year (EUR/MWh)
        mean_reversion_level: Long-run equilibrium price
        mean_reversion_speed: Speed of mean reversion (0-1)
        
    Returns:
        ForwardCurve instance
    """
    years = 15
    daily_steps = years * 365
    
    # Generate mean-reverting price path
    dates = pd.date_range(start='2025-01-01', periods=daily_steps, freq='D')
    prices = np.zeros(daily_steps)
    prices[0] = front_year_price
    
    for t in range(1, daily_steps):
        # Mean reversion: P(t+1) = P(t) + speed * (level - P(t))
        prices[t] = prices[t-1] + mean_reversion_speed/365 * (mean_reversion_level - prices[t-1])
    
    base_curve = pd.Series(prices, index=dates)
    
    # Dutch-specific seasonal factors (mild winters, summer solar penetration)
    seasonal_factors = {
        'Q1': 1.12,  # Winter, but milder than continental
        'Q2': 0.93,  # Spring, high wind + solar
        'Q3': 0.87,  # Summer, very high solar
        'Q4': 1.08   # Autumn
    }
    
    return ForwardCurve(
        base_curve=base_curve,
        seasonal_factors=seasonal_factors
    )
