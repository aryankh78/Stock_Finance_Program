# -*- coding: utf-8 -*-
# ========================================================
# Database Module for Burs Iran Exchange Signaling System
entity_name ="calculations"
# Author: MohammadReza Saeidi
# ========================================================
# Important Notes:
# 1. This module contains functions for calculations.
# ========================================================
# Importing the necessary libraries
# ========================================================
# Importing the necessary libraries
# -Built-in libraries
import logging
import os
import json
import warnings
# -Third-party libraries
import numpy as np
import pandas as pd
import jdatetime
from scipy.signal import argrelextrema
# -Custom libraries
from src.database import Database

# Suppress warnings
warnings.filterwarnings('ignore')
pd.options.mode.chained_assignment = None

# ========================================================
# Logger Setup
# ========================================================
def setup_logging(logger_name):
    """
    Setup logging configuration
    Args:
        logger_name: The name of the logger
    Returns:
        logger: The logger object
    Raises:
        Exception: If the logger is not set up correctly
    """
    try:
        import sys
        os.makedirs('logs', exist_ok=True)
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(lineno)d - %(message)s')
        
        # Console handler with UTF-8
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File handler with UTF-8
        file_handler = logging.FileHandler(f'logs/{logger_name}.log', encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        return logger
    except Exception as e:
        print(f"Error setting up logging: {e}")
        raise

logger = setup_logging(entity_name)
logger.info("Logging setup completed successfully")
# ========================================================
# Config File Loading
# ========================================================
try:
    logger.info("Loading config file")
    with open('config/main_config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    logger.info("Config file loaded successfully")
except Exception as e:
    logger.error(f"Error loading config file: {e}")
    raise
# ========================================================
# Main Class
# ========================================================
class Calculations:
    """
    Calculations class
    This class is designed to calculate the calculations.
    Args:
        None
    Returns:
        None
    """
    def __init__(self):
        logger.info("Initializing Calculations class")
        try:
            self.database = Database()
            logger.info("Database initialized successfully")
            self.database_conn = self.database.connect()
            self.database_cursor = self.database_conn.cursor()
            logger.info("Database connected successfully")
        except Exception as e:
            logger.warning(f"Database connection failed: {e}")
            logger.warning("Database features will not be available")
            self.database = None
            self.database_conn = None
            self.database_cursor = None
        logger.info("Calculations class initialized successfully")

    def calculate_macd(self, candle_data, fast_period, slow_period, signal_period):
        """
        Calculate the MACD indicator
        Args:
            candle_data: np.array, the candle data
            - 0: timestamp(int, seconds since epoch)
            - 1: open price(float)
            - 2: high price(float)
            - 3: low price(float)
            - 4: close price(float)
            - 5: volume(int)
            fast_period: int, the fast period
            slow_period: int, the slow period
            signal_period: int, the signal period
        Returns:
            macd: dict, containing:
                - 'macd_line': np.array, the MACD line
                - 'signal_line': np.array, the signal line
                - 'histogram': np.array, the MACD histogram
        """
        try:
            logger.info("Calculating MACD indicator")
            logger.info(f"Candle data shape: {candle_data.shape}")
            logger.info(f"Fast period: {fast_period}")
            logger.info(f"Slow period: {slow_period}")
            logger.info(f"Signal period: {signal_period}")
            
            # Extract close prices (index 4)
            close_prices = candle_data[:, 4]
            
            # Calculate EMAs
            fast_ema = self._calculate_ema(close_prices, fast_period)
            slow_ema = self._calculate_ema(close_prices, slow_period)
            
            # Calculate MACD line
            macd_line = fast_ema - slow_ema
            
            # Calculate signal line (EMA of MACD line)
            signal_line = self._calculate_ema(macd_line, signal_period)
            
            # Calculate histogram
            histogram = macd_line - signal_line
            
            macd = {
                'macd_line': macd_line,
                'signal_line': signal_line,
                'histogram': histogram
            }
            
            logger.info("MACD indicator calculated successfully")
            return macd
        except Exception as e:
            logger.error(f"Error calculating MACD indicator: {e}")
            raise
    
    def _calculate_ema(self, data, period):
        """
        Calculate Exponential Moving Average
        Args:
            data: np.array, the input data
            period: int, the period for EMA calculation
        Returns:
            ema: np.array, the EMA values
        """
        try:
            # Initialize EMA array with NaN values
            ema = np.full(len(data), np.nan)
            
            # Calculate smoothing factor
            multiplier = 2 / (period + 1)
            
            # First EMA value is SMA (Simple Moving Average)
            if len(data) >= period:
                ema[period - 1] = np.mean(data[:period])
                
                # Calculate subsequent EMA values
                for i in range(period, len(data)):
                    ema[i] = (data[i] - ema[i - 1]) * multiplier + ema[i - 1]
            
            return ema
        except Exception as e:
            logger.error(f"Error calculating EMA: {e}")
            raise

    def _calculate_rsi(self, prices, period=14):
        """
        Calculate RSI (Relative Strength Index) for given prices.
        Args:
            prices: np.array, array of prices
            period: int, RSI period (default: 14)
        Returns:
            rsi: np.array, array of RSI values
        """
        try:
            logger.info(f"Calculating RSI with period {period}")
            deltas = np.diff(prices)
            gain = np.where(deltas > 0, deltas, 0)
            loss = np.where(deltas < 0, -deltas, 0)
            
            avg_gain = np.zeros(len(prices))
            avg_loss = np.zeros(len(prices))
            
            # First average
            avg_gain[period] = np.mean(gain[:period])
            avg_loss[period] = np.mean(loss[:period])
            
            # Smoothed averages
            for i in range(period + 1, len(prices)):
                avg_gain[i] = (avg_gain[i-1] * (period - 1) + gain[i-1]) / period
                avg_loss[i] = (avg_loss[i-1] * (period - 1) + loss[i-1]) / period
            
            rs = np.divide(avg_gain, avg_loss, out=np.zeros_like(avg_gain), where=avg_loss!=0)
            rsi = 100 - (100 / (1 + rs))
            
            logger.info(f"RSI calculated successfully")
            return rsi
        except Exception as e:
            logger.error(f"Error calculating RSI: {e}")
            raise

    def _calculate_mfi(self, candle_data, period=14):
        """
        Calculate MFI (Money Flow Index) for given candle data.
        Args:
            candle_data: pd.DataFrame with columns adjhigh, adjlow, adjclose, Volume
            period: int, MFI period (default: 14)
        Returns:
            mfi: np.array, array of MFI values
        """
        try:
            logger.info(f"Calculating MFI with period {period}")
            
            # Extract required data
            high = candle_data['adjhigh'].to_numpy()
            low = candle_data['adjlow'].to_numpy()
            close = candle_data['adjclose'].to_numpy()
            volume = candle_data['Volume'].to_numpy()
            
            # Calculate typical price
            typical_price = (high + low + close) / 3
            
            # Calculate raw money flow
            raw_money_flow = typical_price * volume
            
            # Calculate positive and negative money flow
            positive_flow = np.zeros(len(typical_price))
            negative_flow = np.zeros(len(typical_price))
            
            for i in range(1, len(typical_price)):
                if typical_price[i] > typical_price[i-1]:
                    positive_flow[i] = raw_money_flow[i]
                elif typical_price[i] < typical_price[i-1]:
                    negative_flow[i] = raw_money_flow[i]
            
            # Calculate MFI
            mfi = np.full(len(typical_price), np.nan)
            
            for i in range(period, len(typical_price)):
                pos_sum = np.sum(positive_flow[i-period+1:i+1])
                neg_sum = np.sum(negative_flow[i-period+1:i+1])
                
                if neg_sum == 0:
                    mfi[i] = 100
                else:
                    money_ratio = pos_sum / neg_sum
                    mfi[i] = 100 - (100 / (1 + money_ratio))
            
            logger.info(f"MFI calculated successfully")
            return mfi
        except Exception as e:
            logger.error(f"Error calculating MFI: {e}")
            raise

    def _detect_peaks_troughs(self, data, order=5):
        """
        Detect peaks (local maxima) and troughs (local minima) in data.
        Args:
            data: np.array, array of values
            order: int, how many points on each side to use for comparison (default: 5)
        Returns:
            tuple: (peak_indices, trough_indices)
        """
        try:
            logger.info(f"Detecting peaks and troughs with order {order}")
            
            # Find local maxima (peaks)
            peak_indices = argrelextrema(data, np.greater, order=order)[0]
            
            # Find local minima (troughs)
            trough_indices = argrelextrema(data, np.less, order=order)[0]
            
            logger.info(f"Found {len(peak_indices)} peaks and {len(trough_indices)} troughs")
            return peak_indices, trough_indices
        except Exception as e:
            logger.error(f"Error detecting peaks and troughs: {e}")
            raise

    def _detect_divergence(self, peak_pivot_data, trough_pivot_data, indicator_data, lookback=60, order=5,
                           alignment_tol=3, peak_value_data=None, trough_value_data=None):
        """
        Detect bullish and bearish divergences between price and indicator.
        Args:
            peak_pivot_data: np.array, series used to locate peak bar indices (swing highs)
            trough_pivot_data: np.array, series used to locate trough bar indices (swing lows)
            indicator_data: np.array, array of indicator values (may contain NaN, e.g. MFI first period)
            lookback: int, number of candles to look back (default: 60)
            order: int, order for peak/trough detection (default: 5)
            alignment_tol: int, max bar offset between matching price/indicator swing points (default: 3)
            peak_value_data: np.array or None, prices compared at peak bars (default: peak_pivot_data).
                For high_low mode use adjhigh at indices found via close pivots.
            trough_value_data: np.array or None, prices compared at trough bars (default: trough_pivot_data).
                For high_low mode use adjlow at indices found via close pivots.
        Returns:
            dict: dictionary with divergence information
        """
        try:
            logger.info(f"Detecting divergences with lookback {lookback}")
            if peak_value_data is None:
                peak_value_data = peak_pivot_data
            if trough_value_data is None:
                trough_value_data = trough_pivot_data

            # Use only the lookback period
            if len(peak_pivot_data) > lookback:
                peak_pivot_window = peak_pivot_data[-lookback:]
                trough_pivot_window = trough_pivot_data[-lookback:]
                peak_value_window = peak_value_data[-lookback:]
                trough_value_window = trough_value_data[-lookback:]
                indicator_window = np.asarray(indicator_data[-lookback:], dtype=float)
            else:
                peak_pivot_window = peak_pivot_data
                trough_pivot_window = trough_pivot_data
                peak_value_window = peak_value_data
                trough_value_window = trough_value_data
                indicator_window = np.asarray(indicator_data, dtype=float)
            
            # Replace NaN/inf in indicator so argrelextrema works (same logic as RSI; MFI has leading NaNs)
            valid_mask = np.isfinite(indicator_window)
            if not np.all(valid_mask):
                valid_vals = indicator_window[valid_mask]
                if len(valid_vals) > 0:
                    fill_val = float(np.median(valid_vals))
                    indicator_window = np.where(valid_mask, indicator_window, fill_val)
                else:
                    indicator_window = np.nan_to_num(indicator_window, nan=50.0, posinf=50.0, neginf=50.0)
            
            # Locate swing bars on pivot series; compare wick prices at those bars when value series differ.
            price_peaks, _ = self._detect_peaks_troughs(peak_pivot_window, order)
            _, price_troughs = self._detect_peaks_troughs(trough_pivot_window, order)
            ind_peaks, ind_troughs = self._detect_peaks_troughs(indicator_window, order)
            
            if alignment_tol < 0 or alignment_tol > 60:
                raise ValueError(f"alignment_tol must be between 0 and 60, got {alignment_tol}")
            logger.info(f"Divergence alignment tolerance: {alignment_tol} bars")
            
            divergences = {
                'bearish': [],       # Regular: Price HH + Indicator LH (reversal down)
                'bullish': [],       # Regular: Price LL + Indicator HL (reversal up)
                'hidden_bearish': [],  # Hidden: Price LH + Indicator HH (continuation down)
                'hidden_bullish': []    # Hidden: Price HL + Indicator LL (continuation up)
            }
            
            # --- Regular Bearish Divergence (at peaks): Price HH + Indicator LH ---
            if len(price_peaks) >= 2 and len(ind_peaks) >= 2:
                for i in range(len(price_peaks) - 1):
                    p_idx1, p_idx2 = price_peaks[i], price_peaks[i + 1]
                    for j in range(len(ind_peaks) - 1):
                        i_idx1, i_idx2 = ind_peaks[j], ind_peaks[j + 1]
                        if abs(p_idx1 - i_idx1) <= alignment_tol and abs(p_idx2 - i_idx2) <= alignment_tol:
                            if peak_value_window[p_idx2] > peak_value_window[p_idx1]:   # Price Higher High
                                if indicator_window[i_idx2] < indicator_window[i_idx1]:  # Indicator Lower High
                                    already = any(d['price_indices'] == (p_idx1, p_idx2) for d in divergences['bearish'])
                                    if not already:
                                        divergences['bearish'].append({
                                            'price_indices': (p_idx1, p_idx2),
                                            'indicator_indices': (i_idx1, i_idx2),
                                            'price_values': (peak_value_window[p_idx1], peak_value_window[p_idx2]),
                                            'indicator_values': (indicator_window[i_idx1], indicator_window[i_idx2])
                                        })
                                        logger.info(f"Bearish divergence detected at indices {p_idx1}, {p_idx2}")
            
            # --- Hidden Bearish Divergence (at peaks): Price LH + Indicator HH ---
            if len(price_peaks) >= 2 and len(ind_peaks) >= 2:
                for i in range(len(price_peaks) - 1):
                    p_idx1, p_idx2 = price_peaks[i], price_peaks[i + 1]
                    for j in range(len(ind_peaks) - 1):
                        i_idx1, i_idx2 = ind_peaks[j], ind_peaks[j + 1]
                        if abs(p_idx1 - i_idx1) <= alignment_tol and abs(p_idx2 - i_idx2) <= alignment_tol:
                            if peak_value_window[p_idx2] < peak_value_window[p_idx1]:   # Price Lower High
                                if indicator_window[i_idx2] > indicator_window[i_idx1]:  # Indicator Higher High
                                    already = any(d['price_indices'] == (p_idx1, p_idx2) for d in divergences['hidden_bearish'])
                                    if not already:
                                        divergences['hidden_bearish'].append({
                                            'price_indices': (p_idx1, p_idx2),
                                            'indicator_indices': (i_idx1, i_idx2),
                                            'price_values': (peak_value_window[p_idx1], peak_value_window[p_idx2]),
                                            'indicator_values': (indicator_window[i_idx1], indicator_window[i_idx2])
                                        })
                                        logger.info(f"Hidden bearish divergence detected at indices {p_idx1}, {p_idx2}")
            
            # --- Regular Bullish Divergence (at troughs): Price LL + Indicator HL ---
            if len(price_troughs) >= 2 and len(ind_troughs) >= 2:
                for i in range(len(price_troughs) - 1):
                    p_idx1, p_idx2 = price_troughs[i], price_troughs[i + 1]
                    for j in range(len(ind_troughs) - 1):
                        i_idx1, i_idx2 = ind_troughs[j], ind_troughs[j + 1]
                        if abs(p_idx1 - i_idx1) <= alignment_tol and abs(p_idx2 - i_idx2) <= alignment_tol:
                            if trough_value_window[p_idx2] < trough_value_window[p_idx1]:   # Price Lower Low
                                if indicator_window[i_idx2] > indicator_window[i_idx1]:  # Indicator Higher Low
                                    already = any(d['price_indices'] == (p_idx1, p_idx2) for d in divergences['bullish'])
                                    if not already:
                                        divergences['bullish'].append({
                                            'price_indices': (p_idx1, p_idx2),
                                            'indicator_indices': (i_idx1, i_idx2),
                                            'price_values': (trough_value_window[p_idx1], trough_value_window[p_idx2]),
                                            'indicator_values': (indicator_window[i_idx1], indicator_window[i_idx2])
                                        })
                                        logger.info(f"Bullish divergence detected at indices {p_idx1}, {p_idx2}")
            
            # --- Hidden Bullish Divergence (at troughs): Price HL + Indicator LL ---
            if len(price_troughs) >= 2 and len(ind_troughs) >= 2:
                for i in range(len(price_troughs) - 1):
                    p_idx1, p_idx2 = price_troughs[i], price_troughs[i + 1]
                    for j in range(len(ind_troughs) - 1):
                        i_idx1, i_idx2 = ind_troughs[j], ind_troughs[j + 1]
                        if abs(p_idx1 - i_idx1) <= alignment_tol and abs(p_idx2 - i_idx2) <= alignment_tol:
                            if trough_value_window[p_idx2] > trough_value_window[p_idx1]:   # Price Higher Low
                                if indicator_window[i_idx2] < indicator_window[i_idx1]:  # Indicator Lower Low
                                    already = any(d['price_indices'] == (p_idx1, p_idx2) for d in divergences['hidden_bullish'])
                                    if not already:
                                        divergences['hidden_bullish'].append({
                                            'price_indices': (p_idx1, p_idx2),
                                            'indicator_indices': (i_idx1, i_idx2),
                                            'price_values': (trough_value_window[p_idx1], trough_value_window[p_idx2]),
                                            'indicator_values': (indicator_window[i_idx1], indicator_window[i_idx2])
                                        })
                                        logger.info(f"Hidden bullish divergence detected at indices {p_idx1}, {p_idx2}")
            
            return divergences
        except Exception as e:
            logger.error(f"Error detecting divergences: {e}")
            raise

    def _calculate_returns(self, prices):
        """
        Calculate row-to-row returns from aligned price data.
        Args:
            prices: np.array, array of prices
        Returns:
            returns: np.array, array of returns (percentage change)
        """
        try:
            logger.info(f"Calculating returns for {len(prices)} prices")
            returns = np.diff(prices) / prices[:-1]
            logger.info(f"Calculated {len(returns)} returns")
            return returns
        except Exception as e:
            logger.error(f"Error calculating returns: {e}")
            raise

    def _interpret_volume_change(self, volume_diff_pct, today_volume, avg_volume):
        """
        Interpret volume change and provide context.
        Args:
            volume_diff_pct: float, percentage difference
            today_volume: float, today's volume
            avg_volume: float, average volume
        Returns:
            str: interpretation string
        """
        try:
            abs_diff = abs(volume_diff_pct)
            
            if volume_diff_pct > 200:
                return "Extremely high volume - potential major news or unusual market interest"
            elif volume_diff_pct > 100:
                return "Very high volume - significant market interest, possible breakout or breakdown"
            elif volume_diff_pct > 50:
                return "High volume - increased market participation and interest"
            elif volume_diff_pct > 20:
                return "Above average volume - moderate increase in trading activity"
            elif volume_diff_pct > 0:
                return "Slightly above average volume - normal market activity"
            elif volume_diff_pct > -20:
                return "Slightly below average volume - normal market activity"
            elif volume_diff_pct > -50:
                return "Below average volume - decreased market interest"
            elif volume_diff_pct > -70:
                return "Low volume - significantly reduced trading activity"
            else:
                return "Very low volume - minimal market interest, potential low liquidity"
        except Exception as e:
            logger.error(f"Error interpreting volume change: {e}")
            raise

    def calculate_indicator_1(self, candle_data, ma_periods, price_type):
        """
        Calculate indicator 1: Multiple Moving Averages for each row of candle data
        Args:
            candle_data: pd.DataFrame, daily candle data with columns:
                - 'timestamp': timestamp values
                - 'adjfinal': adjusted final price
                - 'adjopen': adjusted open price
                - 'adjhigh': adjusted high price
                - 'adjlow': adjusted low price
                - 'adjclose': adjusted close price
            ma_periods: list of int, the moving average periods (e.g., [20, 50, 200])
            price_type: str, the price type ("open", "high", "low", "close")
        Returns:
            dict: dictionary with MA period as key and np.array as value
                Each array contains moving average values for each row
                - For rows before ma_period, the value will be NaN
                - For row at index i (where i >= ma_period-1), returns the moving average
                  of the last ma_period prices up to and including row i
        """
        try:
            logger.info(f"Calculating indicator 1 (Multiple Moving Averages)")
            logger.info(f"Candle data shape: {candle_data.shape}")
            logger.info(f"MA periods: {ma_periods}")
            logger.info(f"Price type: {price_type}")
            
            # Map price_type to the corresponding column name
            price_column_map = {
                'open': 'adjopen',
                'high': 'adjhigh',
                'low': 'adjlow',
                'close': 'adjclose'
            }
            
            # Validate price_type
            if price_type not in price_column_map:
                raise ValueError(f"Invalid price_type '{price_type}'. Must be one of: {list(price_column_map.keys())}")
            
            # Get the column name
            column_name = price_column_map[price_type]
            
            # Validate that the column exists in the dataframe
            if column_name not in candle_data.columns:
                raise ValueError(f"Column '{column_name}' not found in candle_data. Available columns: {list(candle_data.columns)}")
            for required_column in ['adjhigh', 'adjlow']:
                if required_column not in candle_data.columns:
                    raise ValueError(f"Column '{required_column}' not found in candle_data. Available columns: {list(candle_data.columns)}")
            
            # Extract price data
            prices = candle_data[column_name].to_numpy()
            
            # Calculate MA for each period
            ma_arrays = {}
            for ma_period in ma_periods:
                # Initialize moving average array with NaN values
                ma_array = np.full(len(prices), np.nan)
                
                # Calculate simple moving average for each row
                for i in range(ma_period - 1, len(prices)):
                    # Calculate average of last ma_period values up to and including index i
                    ma_array[i] = np.mean(prices[i - ma_period + 1:i + 1])
                
                ma_arrays[ma_period] = ma_array
                logger.info(f"MA-{ma_period} calculated: Non-NaN values: {np.sum(~np.isnan(ma_array))}")
            
            logger.info(f"All moving averages calculated successfully")
            
            return ma_arrays
        except Exception as e:
            logger.error(f"Error calculating indicator 1: {e}")
            raise

    def calculate_indicator_2(self, candle_data,
                             rsi_period=14, rsi_overbought=70, rsi_oversold=30,
                             macd_short=12, macd_long=26, macd_signal=9,
                             mfi_period=14, mfi_overbought=80, mfi_oversold=20,
                             lookback=60, price_type="close", divergence_price_mode="close",
                             alignment_tol=3):
        """
        Calculate indicator 2: Divergence indicator between price and MACD/RSI/MFI.
        Detects bearish and bullish divergences.
        Args:
            candle_data: pd.DataFrame, daily candle data with columns:
                - 'timestamp': timestamp values
                - 'adjfinal': adjusted final price
                - 'adjopen': adjusted open price
                - 'adjhigh': adjusted high price
                - 'adjlow': adjusted low price
                - 'adjclose': adjusted close price
                - 'Volume': trading volume
            rsi_period: int, RSI period (default: 14)
            rsi_overbought: float, RSI overbought level (default: 70)
            rsi_oversold: float, RSI oversold level (default: 30)
            macd_short: int, MACD short period (default: 12)
            macd_long: int, MACD long period (default: 26)
            macd_signal: int, MACD signal period (default: 9)
            mfi_period: int, MFI period (default: 14)
            mfi_overbought: float, MFI overbought level (default: 80)
            mfi_oversold: float, MFI oversold level (default: 20)
            lookback: int, number of candles to look back for divergence detection (default: 60)
            price_type: str, type of price to use ("open", "high", "low", "close") (default: "close")
            divergence_price_mode: str, price logic for divergence pivots:
                - "close": use adjusted close for pivot detection and comparisons
                - "high_low": locate swings on adjusted close; at peak bars compare adjhigh,
                  at trough bars compare adjlow (matches candlestick visual pivots + wick prices)
            alignment_tol: int, max bars between aligned price/indicator swing points (default: 3)
        Returns:
            dict: containing:
                - 'macd_array': np.array, MACD line values for each row
                - 'rsi_array': np.array, RSI values for each row
                - 'mfi_array': np.array, MFI values for each row
                - 'rsi_divergence': dict with 'bearish' and 'bullish' lists
                - 'macd_divergence': dict with 'bearish' and 'bullish' lists
                - 'mfi_divergence': dict with 'bearish' and 'bullish' lists
        """
        try:
            logger.info(f"Calculating indicator 2 (Divergence with RSI/MACD/MFI)")
            logger.info(f"Candle data shape: {candle_data.shape}")
            logger.info(f"RSI settings: period={rsi_period}, overbought={rsi_overbought}, oversold={rsi_oversold}")
            logger.info(f"MACD settings: short={macd_short}, long={macd_long}, signal={macd_signal}")
            logger.info(f"MFI settings: period={mfi_period}, overbought={mfi_overbought}, oversold={mfi_oversold}")
            logger.info(f"Lookback: {lookback}, Price type: {price_type}")
            logger.info(f"Divergence price mode: {divergence_price_mode}")
            logger.info(f"Divergence alignment tolerance: {alignment_tol}")
            if alignment_tol < 0 or alignment_tol > 60:
                raise ValueError(f"alignment_tol must be between 0 and 60, got {alignment_tol}")
            
            # Map price_type to the corresponding column name
            price_column_map = {
                'open': 'adjopen',
                'high': 'adjhigh',
                'low': 'adjlow',
                'close': 'adjclose'
            }
            
            # Validate price_type
            if price_type not in price_column_map:
                raise ValueError(f"Invalid price_type '{price_type}'. Must be one of: {list(price_column_map.keys())}")
            
            # Validate divergence price mode
            valid_divergence_price_modes = ['close', 'high_low']
            if divergence_price_mode not in valid_divergence_price_modes:
                raise ValueError(f"Invalid divergence_price_mode '{divergence_price_mode}'. Must be one of: {valid_divergence_price_modes}")
            
            # Get the column name
            column_name = price_column_map[price_type]
            
            # Validate that the column exists in the dataframe
            if column_name not in candle_data.columns:
                raise ValueError(f"Column '{column_name}' not found in candle_data. Available columns: {list(candle_data.columns)}")
            for required_column in ['adjclose', 'adjhigh', 'adjlow']:
                if required_column not in candle_data.columns:
                    raise ValueError(f"Column '{required_column}' not found in candle_data. Available columns: {list(candle_data.columns)}")
            
            # Check if we have enough data
            min_required = max(macd_long + macd_signal, rsi_period, mfi_period) + 10
            if len(candle_data) < min_required:
                logger.error(f"Not enough data. Need at least {min_required} candles")
                raise ValueError(f"Not enough data. Need at least {min_required} candles, got {len(candle_data)}")
            
            # Extract price data
            prices = candle_data[column_name].to_numpy()
            close_prices = candle_data['adjclose'].to_numpy()
            high_prices = candle_data['adjhigh'].to_numpy()
            low_prices = candle_data['adjlow'].to_numpy()
            if divergence_price_mode == 'high_low':
                peak_pivot = close_prices
                trough_pivot = close_prices
                peak_values = high_prices
                trough_values = low_prices
            else:
                peak_pivot = close_prices
                trough_pivot = close_prices
                peak_values = close_prices
                trough_values = close_prices
            logger.info(f"Price data shape: {prices.shape}")
            logger.info(
                f"Divergence pivots peaks={peak_pivot.shape}, troughs={trough_pivot.shape}; "
                f"values peaks={peak_values.shape}, troughs={trough_values.shape}"
            )
            
            # Calculate RSI
            rsi_values = self._calculate_rsi(prices, rsi_period)
            logger.info(f"RSI calculated, shape: {rsi_values.shape}")
            
            # Calculate MFI
            mfi_values = self._calculate_mfi(candle_data, mfi_period)
            logger.info(f"MFI calculated, shape: {mfi_values.shape}")
            
            # Prepare data for MACD calculation
            # MACD function expects np.array with columns: timestamp, open, high, low, close, volume
            macd_input = np.column_stack([
                candle_data["timestamp"].to_numpy() if "timestamp" in candle_data.columns else np.arange(len(candle_data)),
                candle_data["adjopen"].to_numpy(),
                candle_data["adjhigh"].to_numpy(),
                candle_data["adjlow"].to_numpy(),
                prices,
                np.zeros(len(candle_data))  # Volume not needed for MACD calculation
            ])
            
            # Calculate MACD
            macd_result = self.calculate_macd(
                macd_input,
                macd_short, macd_long, macd_signal
            )
            macd_line = macd_result['macd_line']
            signal_line = macd_result['signal_line']
            histogram = macd_result['histogram']
            logger.info(f"MACD calculated, shape: {macd_line.shape}")
            
            # Detect divergences for RSI
            logger.info("Detecting RSI divergences")
            rsi_divergences = self._detect_divergence(
                peak_pivot, trough_pivot, rsi_values, lookback, order=5, alignment_tol=alignment_tol,
                peak_value_data=peak_values, trough_value_data=trough_values)
            
            # Detect divergences for MACD
            logger.info("Detecting MACD divergences")
            macd_divergences = self._detect_divergence(
                peak_pivot, trough_pivot, macd_line, lookback, order=5, alignment_tol=alignment_tol,
                peak_value_data=peak_values, trough_value_data=trough_values)
            
            # Detect divergences for MFI
            logger.info("Detecting MFI divergences")
            mfi_divergences = self._detect_divergence(
                peak_pivot, trough_pivot, mfi_values, lookback, order=5, alignment_tol=alignment_tol,
                peak_value_data=peak_values, trough_value_data=trough_values)
            
            # Prepare result (regular + hidden divergences)
            result = {
                'macd_array': macd_line,
                'rsi_array': rsi_values,
                'mfi_array': mfi_values,
                'rsi_divergence': {
                    'bearish': rsi_divergences['bearish'],
                    'bullish': rsi_divergences['bullish'],
                    'hidden_bearish': rsi_divergences.get('hidden_bearish', []),
                    'hidden_bullish': rsi_divergences.get('hidden_bullish', [])
                },
                'macd_divergence': {
                    'bearish': macd_divergences['bearish'],
                    'bullish': macd_divergences['bullish'],
                    'hidden_bearish': macd_divergences.get('hidden_bearish', []),
                    'hidden_bullish': macd_divergences.get('hidden_bullish', [])
                },
                'mfi_divergence': {
                    'bearish': mfi_divergences['bearish'],
                    'bullish': mfi_divergences['bullish'],
                    'hidden_bearish': mfi_divergences.get('hidden_bearish', []),
                    'hidden_bullish': mfi_divergences.get('hidden_bullish', [])
                }
            }
            
            logger.info(f"RSI - Regular Bearish: {len(rsi_divergences['bearish'])}, Bullish: {len(rsi_divergences['bullish'])} | "
                       f"Hidden Bearish: {len(rsi_divergences.get('hidden_bearish', []))}, Bullish: {len(rsi_divergences.get('hidden_bullish', []))}")
            logger.info(f"MACD - Regular Bearish: {len(macd_divergences['bearish'])}, Bullish: {len(macd_divergences['bullish'])} | "
                       f"Hidden Bearish: {len(macd_divergences.get('hidden_bearish', []))}, Bullish: {len(macd_divergences.get('hidden_bullish', []))}")
            logger.info(f"MFI - Regular Bearish: {len(mfi_divergences['bearish'])}, Bullish: {len(mfi_divergences['bullish'])} | "
                       f"Hidden Bearish: {len(mfi_divergences.get('hidden_bearish', []))}, Bullish: {len(mfi_divergences.get('hidden_bullish', []))}")
            logger.info(f"Divergence analysis completed successfully")
            
            return result
        except Exception as e:
            logger.error(f"Error calculating indicator 2: {e}")
            raise

    def calculate_indicator_3(self, candle_data, market_candle_data,
                             beta_period=36, return_period=30, threshold=1.0, price_type="close"):
        """
        Calculate indicator 3: Beta Coefficient indicator.
        Measures the stock's volatility relative to the market and compares actual vs expected returns.
        The caller must pass stock and market data already aligned on matching trading dates.
        
        Beta interpretation:
        - β > 1: Stock is more volatile than the market
        - β = 1: Stock moves with the market
        - β < 1: Stock is less volatile than the market
        - β = 0: Stock is uncorrelated with the market
        - β < 0: Stock moves inversely to the market
        
        Process:
        1. Calculate beta using trade-to-trade aligned historical data over beta_period (default 36 months)
        2. Calculate actual stock return over return_period
        3. Calculate expected return based on: expected_return = beta * market_return
        4. Mean reversion signal from relative delta:
           ratio_pct = (Δ / |Re|) × 100  where Δ = Ra − Re
        5. POSITIVE if ratio_pct < -threshold, NEGATIVE if ratio_pct > +threshold,
           else NEUTRAL (threshold is % band on ratio_pct, e.g. 20 means ±20%)
        
        Args:
            candle_data: pd.DataFrame, stock daily candle data with columns:
                - 'timestamp': timestamp values
                - 'adjfinal': adjusted final price
                - 'adjopen': adjusted open price
                - 'adjhigh': adjusted high price
                - 'adjlow': adjusted low price
                - 'adjclose': adjusted close price
            market_candle_data: pd.DataFrame, market index daily candle data with same columns as candle_data
            beta_period: int, period for calculating beta in days (default: 36 for 36 months ~= 750 trading days)
            return_period: int, period for calculating actual returns in days (default: 30)
            threshold: float, symmetric band on relative Δ (%) — neutral if -threshold <= ratio_pct <= +threshold
            price_type: str, type of price to use ("open", "high", "low", "close") (default: "close")
        Returns:
            dict: containing:
                - 'beta': float, the calculated beta coefficient (constant for long-term)
                - 'actual_return': float, actual stock return over return_period
                - 'expected_return': float, expected return based on beta
                - 'market_return': float, market return over return_period
                - 'return_delta': float, actual_return - expected_return (%)
                - 'delta_ratio_pct': float or None, (return_delta / |expected_return|) * 100
                - 'return_ratio': float or None, actual_return / expected_return (legacy)
                - 'signal': str, 'POSITIVE', 'NEGATIVE', or 'NEUTRAL'
                - 'performance_interpretation': str, description of return delta vs threshold
        """
        try:
            logger.info(f"Calculating indicator 3 (Beta Coefficient - Simplified)")
            logger.info(f"Stock candle data shape: {candle_data.shape}")
            logger.info(f"Market candle data shape: {market_candle_data.shape}")
            logger.info(f"Beta period: {beta_period} days (long-term)")
            logger.info(f"Return period: {return_period} days")
            logger.info(f"Threshold: {threshold}")
            logger.info(f"Price type: {price_type}")
            
            # Map price_type to the corresponding column name
            price_column_map = {
                'open': 'adjopen',
                'high': 'adjhigh',
                'low': 'adjlow',
                'close': 'adjclose'
            }
            
            # Validate price_type
            if price_type not in price_column_map:
                raise ValueError(f"Invalid price_type '{price_type}'. Must be one of: {list(price_column_map.keys())}")
            
            # Get the column name
            column_name = price_column_map[price_type]
            
            # Validate that the column exists in both dataframes
            if column_name not in candle_data.columns:
                raise ValueError(f"Column '{column_name}' not found in candle_data. Available columns: {list(candle_data.columns)}")
            if column_name not in market_candle_data.columns:
                raise ValueError(f"Column '{column_name}' not found in market_candle_data. Available columns: {list(market_candle_data.columns)}")
            
            # Check if we have enough data for beta calculation
            min_beta_data = min(beta_period + 1, len(candle_data))
            if len(candle_data) < 2:
                raise ValueError(f"Not enough stock data. Need at least 2 data points, got {len(candle_data)}")
            
            if len(market_candle_data) < min_beta_data:
                logger.warning(f"Not enough market data for full beta period. Using available data: {len(market_candle_data)} days")
            
            # Extract prices
            stock_prices = candle_data[column_name].to_numpy()
            market_prices = market_candle_data[column_name].to_numpy()
            
            logger.info(f"Stock prices shape: {stock_prices.shape}")
            logger.info(f"Market prices shape: {market_prices.shape}")
            
            # Calculate Beta using all available data (up to beta_period)
            beta_calc_period = min(beta_period, len(stock_prices) - 1, len(market_prices) - 1)
            logger.info(f"Using {beta_calc_period} days for beta calculation")
            
            # Get data for beta calculation (use all available data up to beta_period)
            stock_beta_window = stock_prices[-beta_calc_period-1:]
            market_beta_window = market_prices[-beta_calc_period-1:]
            
            # Calculate trade-to-trade returns on already aligned stock/market date windows.
            stock_returns_beta = self._calculate_returns(stock_beta_window)
            market_returns_beta = self._calculate_returns(market_beta_window)
            
            # Calculate Beta
            if len(stock_returns_beta) > 1 and len(market_returns_beta) > 1:
                covariance = np.cov(stock_returns_beta, market_returns_beta)[0, 1]
                market_variance = np.var(market_returns_beta)
                
                if market_variance != 0:
                    beta = covariance / market_variance
                else:
                    beta = 0.0
                    logger.warning("Market variance is zero, setting beta to 0")
            else:
                beta = 0.0
                logger.warning("Not enough data for beta calculation, setting beta to 0")
            
            logger.info(f"Calculated Beta: {beta:.4f}")
            
            # Calculate actual return over return_period
            actual_return_period = min(return_period, len(stock_prices) - 1)
            logger.info(f"Using {actual_return_period} days for return calculation")
            
            actual_return = ((stock_prices[-1] - stock_prices[-actual_return_period-1]) / stock_prices[-actual_return_period-1]) * 100
            
            # Calculate market return over return_period
            market_return = ((market_prices[-1] - market_prices[-actual_return_period-1]) / market_prices[-actual_return_period-1]) * 100
            
            # Calculate expected return based on beta
            expected_return = beta * market_return
            
            # Mean reversion: Δ = Ra - Re (same units as returns, %)
            delta_return = float(actual_return - expected_return)

            # Relative Δ vs |expected return| — used for signaling
            abs_expected = abs(expected_return)
            if abs_expected > 0:
                delta_ratio_pct = float((delta_return / abs_expected) * 100.0)
            else:
                delta_ratio_pct = None
                logger.warning("Expected return is zero; relative delta ratio is undefined")

            # Legacy ratio (actual / expected); optional reference only
            if expected_return != 0:
                return_ratio = float(actual_return / expected_return)
            else:
                return_ratio = None

            # Signal from relative Δ ratio vs symmetric threshold band (%)
            if delta_ratio_pct is None:
                signal = 'NO_DATA'
                signal_color = 'GRAY'
            elif delta_ratio_pct < -threshold:
                signal = 'POSITIVE'
                signal_color = 'GREEN'
            elif delta_ratio_pct > threshold:
                signal = 'NEGATIVE'
                signal_color = 'RED'
            else:
                signal = 'NEUTRAL'
                signal_color = 'YELLOW'
            
            # Interpretation
            if beta > 1.5:
                beta_interpretation = f"High Beta ({beta:.2f}): Stock is significantly more volatile than market"
            elif beta > 1:
                beta_interpretation = f"Above-Market Beta ({beta:.2f}): Stock is more volatile than market"
            elif beta > 0.5:
                beta_interpretation = f"Below-Market Beta ({beta:.2f}): Stock is less volatile than market"
            elif beta > 0:
                beta_interpretation = f"Low Beta ({beta:.2f}): Stock is much less volatile than market"
            elif beta > -0.5:
                beta_interpretation = f"Slightly Negative Beta ({beta:.2f}): Stock moves slightly inverse to market"
            else:
                beta_interpretation = f"Negative Beta ({beta:.2f}): Stock moves inverse to market"
            
            if signal == 'POSITIVE':
                performance_interpretation = (
                    f"Underperformed vs beta expectation "
                    f"(Δ={delta_return:.2f}%, ratio={delta_ratio_pct:.2f}% vs ±{threshold:.2f}% band); "
                    f"mean reversion buy bias"
                )
            elif signal == 'NEGATIVE':
                performance_interpretation = (
                    f"Outperformed vs beta expectation "
                    f"(Δ={delta_return:.2f}%, ratio={delta_ratio_pct:.2f}% vs ±{threshold:.2f}% band); "
                    f"mean reversion sell bias"
                )
            elif signal == 'NO_DATA':
                performance_interpretation = (
                    f"Relative Δ ratio undefined (expected return is zero); Δ={delta_return:.2f}%"
                )
            else:
                ratio_text = f"{delta_ratio_pct:.2f}%" if delta_ratio_pct is not None else "N/A"
                performance_interpretation = (
                    f"Within neutral band (Δ={delta_return:.2f}%, ratio={ratio_text}, ±{threshold:.2f}%)"
                )
            
            logger.info(
                f"Beta: {beta:.4f}, Actual Return: {actual_return:.2f}%, Expected: {expected_return:.2f}%"
            )
            logger.info(
                f"Return Delta: {delta_return:.4f}%, Delta Ratio: "
                f"{delta_ratio_pct if delta_ratio_pct is not None else 'N/A'}%, Signal: {signal}"
            )
            
            # Prepare result dictionary
            result = {
                'beta': float(beta),
                'beta_period_used': beta_calc_period,
                'actual_return': float(actual_return),
                'expected_return': float(expected_return),
                'market_return': float(market_return),
                'return_period_used': actual_return_period,
                'return_method': 'trade_to_trade',
                'return_delta': delta_return,
                'delta_ratio_pct': delta_ratio_pct,
                'return_ratio': return_ratio,
                'signal': signal,
                'signal_color': signal_color,
                'beta_interpretation': beta_interpretation,
                'performance_interpretation': performance_interpretation,
                'threshold': threshold
            }
            
            return result
        except Exception as e:
            logger.error(f"Error calculating indicator 3: {e}")
            raise

    def calculate_indicator_4_chart(self, candle_data, volume_ma_periods, volume_field="Volume", value_field="Value"):
        """
        Calculate indicator 4 for charting: Trading Volume indicator with multiple moving averages.
        Returns daily volumes/values and their moving averages for visualization.
        Args:
            candle_data: pd.DataFrame, daily candle data with columns:
                - 'timestamp': timestamp values
                - 'Volume': volume values (or other volume field name)
                - 'Value': trading value values (or other value field name)
                - (other price fields not used for this indicator)
            volume_ma_periods: list of int, periods for calculating average volume (e.g., [20, 50])
            volume_field: str, field name for volume in dataframe (default: "Volume")
            value_field: str, field name for value in dataframe (default: "Value")
        Returns:
            dict: containing:
                - 'volumes': np.array, daily volume values
                - 'volume_mas': dict with period as key and np.array as value
                - 'values': np.array, daily value values
                - 'value_mas': dict with period as key and np.array as value
                - 'dates': list, date strings for x-axis
                - 'statistics': dict with volume statistics
        """
        try:
            logger.info(f"Calculating indicator 4 (Trading Volume chart with multiple MAs)")
            logger.info(f"Candle data shape: {candle_data.shape}")
            logger.info(f"Volume MA Periods: {volume_ma_periods}")
            logger.info(f"Volume field: {volume_field}")
            logger.info(f"Value field: {value_field}")
            
            # Check if we have enough data
            if len(candle_data) < 2:
                logger.error(f"Not enough data. Need at least 2 data points")
                raise ValueError(f"Not enough data. Need at least 2 data points, got {len(candle_data)}")
            
            # Check if volume field exists
            if volume_field not in candle_data.columns:
                logger.error(f"Volume field '{volume_field}' not found in data")
                available_fields = list(candle_data.columns)
                logger.error(f"Available fields: {available_fields}")
                
                # Provide helpful error message
                error_msg = f"ستون حجم معاملات ('{volume_field}') در داده‌های دریافتی یافت نشد. "
                error_msg += f"ممکن است داده‌های حجم معاملات برای این نماد در دسترس نباشد. "
                error_msg += f"ستون‌های موجود: {available_fields}"
                raise ValueError(error_msg)

            if value_field not in candle_data.columns:
                logger.error(f"Value field '{value_field}' not found in data")
                available_fields = list(candle_data.columns)
                logger.error(f"Available fields: {available_fields}")
                error_msg = f"ستون ارزش معاملات ('{value_field}') در داده‌های دریافتی یافت نشد. "
                error_msg += f"ممکن است داده‌های ارزش معاملات برای این نماد در دسترس نباشد. "
                error_msg += f"ستون‌های موجود: {available_fields}"
                raise ValueError(error_msg)
            
            # Extract volumes
            volumes = candle_data[volume_field].to_numpy()
            values = candle_data[value_field].to_numpy()
            
            # Calculate moving averages for each period
            volume_mas = {}
            value_mas = {}
            for volume_ma_period in volume_ma_periods:
                volume_ma = np.zeros(len(volumes))
                value_ma = np.zeros(len(values))
                
                for i in range(len(volumes)):
                    # Calculate window for moving average
                    window_start = max(0, i - volume_ma_period + 1)
                    # Calculate average of the window
                    volume_ma[i] = np.mean(volumes[window_start:i + 1])
                    value_ma[i] = np.mean(values[window_start:i + 1])
                
                volume_mas[volume_ma_period] = volume_ma
                value_mas[volume_ma_period] = value_ma
                logger.info(f"Volume MA-{volume_ma_period} calculated successfully")
            
            # Convert timestamps to dates
            dates = []
            for ts in candle_data['timestamp'].values:
                try:
                    date_str = jdatetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                    dates.append(date_str)
                except:
                    dates.append(str(ts))
            
            # Prepare result (use first MA period for statistics)
            first_ma_period = volume_ma_periods[0]
            result = {
                'volumes': volumes,
                'volume_mas': volume_mas,
                'values': values,
                'value_mas': value_mas,
                'dates': dates,
                'statistics': {
                    'total_days': len(candle_data),
                    'avg_volume': float(np.mean(volumes)),
                    'max_volume': float(np.max(volumes)),
                    'min_volume': float(np.min(volumes)),
                    'latest_volume': float(volumes[-1]),
                    'latest_volume_ma': float(volume_mas[first_ma_period][-1]),
                    'avg_value': float(np.mean(values)),
                    'max_value': float(np.max(values)),
                    'min_value': float(np.min(values)),
                    'latest_value': float(values[-1]),
                    'latest_value_ma': float(value_mas[first_ma_period][-1])
                }
            }
            
            logger.info(f"Trading Volume chart data prepared successfully")
            logger.info(f"Total days: {result['statistics']['total_days']}")
            logger.info(f"Latest volume: {result['statistics']['latest_volume']}")
            
            return result
        except Exception as e:
            logger.error(f"Error calculating indicator 4 chart: {e}")
            raise

    def calculate_indicator_4(self, symbol, date, 
                             volume_ma_period=30, 
                             volume_field="vol"):
        """
        Calculate indicator 4: Trading Volume indicator.
        Compares today's trading volume with the average volume of recent days.
        Args:
            symbol: str, stock symbol
            date: str, date in format YYYY-MM-DD (today's date)
            volume_ma_period: int, period for calculating average volume (default: 30 days)
            volume_field: str, field name for volume in database (default: "vol")
        Returns:
            dict: containing volume analysis and signal
        """
        try:
            logger.info(f"Calculating indicator 4 (Trading Volume) for {symbol} on {date}")
            logger.info(f"Volume MA Period: {volume_ma_period} days")
            
            # Convert date to timestamp
            timestamp = jdatetime.datetime.strptime(date, "%Y-%m-%d").timestamp()
            timestamp = int(timestamp)
            
            # Get table name
            table_name = f"{symbol}_daily_candles"
            logger.info(f"Table name: {table_name}")
            
            # Fetch data for today and previous period
            # Need volume_ma_period + 1 days (today + previous N days)
            data_lookback = volume_ma_period + 1
            command = f"""
                        SELECT * FROM {table_name}
                        WHERE timestamp <= {timestamp} AND timestamp >= {timestamp - 24*60*60*data_lookback}
                        ORDER BY timestamp ASC
                       """
            logger.info(f"Command: {command}")
            
            try:
                data = pd.read_sql_query(command, self.database_conn)
                logger.info(f"Fetched {len(data)} rows")
            except Exception as e:
                logger.error(f"Error fetching data: {e}")
                return {
                    'error': f'Error fetching data: {str(e)}',
                    'symbol': symbol,
                    'date': date
                }
            
            # Check if we have enough data
            if len(data) < 2:
                logger.error(f"Not enough data. Need at least 2 data points")
                return {
                    'error': 'Not enough data',
                    'required_datapoints': 2,
                    'available_datapoints': len(data),
                    'symbol': symbol
                }
            
            # Add date column
            data["date"] = data["timestamp"].apply(
                lambda x: jdatetime.datetime.fromtimestamp(x).strftime("%Y-%m-%d")
            )
            
            # Check if volume field exists
            if volume_field not in data.columns:
                logger.error(f"Volume field '{volume_field}' not found in data")
                available_fields = list(data.columns)
                logger.error(f"Available fields: {available_fields}")
                return {
                    'error': f"Volume field '{volume_field}' not found",
                    'available_fields': available_fields,
                    'symbol': symbol
                }
            
            # Sort by timestamp to ensure correct order
            data = data.sort_values('timestamp', ascending=True)
            
            # Get today's volume (last row)
            today_volume = float(data[volume_field].iloc[-1])
            today_date = data["date"].iloc[-1]
            logger.info(f"Today's date: {today_date}, Today's volume: {today_volume}")
            
            # Get previous days' volumes (excluding today)
            if len(data) > 1:
                previous_volumes = data[volume_field].iloc[:-1].to_numpy()
            else:
                logger.error("Not enough data to calculate average")
                return {
                    'error': 'Not enough data to calculate average',
                    'symbol': symbol,
                    'date': date
                }
            
            logger.info(f"Number of previous days for average: {len(previous_volumes)}")
            
            # Calculate average volume for previous days
            avg_volume = float(np.mean(previous_volumes))
            logger.info(f"Average volume: {avg_volume}")
            
            # Calculate percentage difference
            if avg_volume == 0:
                logger.error("Average volume is zero, cannot calculate percentage difference")
                return {
                    'error': 'Average volume is zero',
                    'symbol': symbol,
                    'date': date
                }
            
            volume_diff_pct = ((today_volume - avg_volume) / avg_volume) * 100
            logger.info(f"Volume difference: {volume_diff_pct:.2f}%")
            
            # Determine signal
            if today_volume > avg_volume:
                signal = "POSITIVE"
                signal_color = "GREEN"
                description = "Today's volume is above average"
            else:
                signal = "NEGATIVE"
                signal_color = "RED"
                description = "Today's volume is at or below average"
            
            # Determine color intensity based on difference level
            # This can be used for gradient coloring in UI
            abs_diff = abs(volume_diff_pct)
            if abs_diff > 200:
                intensity = "VERY_HIGH"
                intensity_description = "Exceptionally high volume activity"
            elif abs_diff > 100:
                intensity = "HIGH"
                intensity_description = "High volume activity"
            elif abs_diff > 50:
                intensity = "MODERATE"
                intensity_description = "Moderate volume activity"
            elif abs_diff > 20:
                intensity = "SLIGHT"
                intensity_description = "Slight volume activity"
            else:
                intensity = "LOW"
                intensity_description = "Low volume activity"
            
            logger.info(f"Signal: {signal} ({signal_color}), Intensity: {intensity}")
            
            # Calculate volume ratio (today/average)
            volume_ratio = today_volume / avg_volume
            logger.info(f"Volume ratio: {volume_ratio:.2f}x")
            
            # Additional statistics
            min_volume = float(np.min(previous_volumes))
            max_volume = float(np.max(previous_volumes))
            median_volume = float(np.median(previous_volumes))
            std_volume = float(np.std(previous_volumes))
            
            # Calculate percentile ranking of today's volume
            all_volumes = np.append(previous_volumes, today_volume)
            percentile = (np.sum(all_volumes < today_volume) / len(all_volumes)) * 100
            
            logger.info(f"Today's volume percentile: {percentile:.2f}%")
            
            # Prepare result
            result = {
                'symbol': symbol,
                'date': date,
                'settings': {
                    'volume_ma_period': volume_ma_period,
                    'volume_field': volume_field
                },
                'volumes': {
                    'today': round(today_volume, 2),
                    'average': round(avg_volume, 2),
                    'min': round(min_volume, 2),
                    'max': round(max_volume, 2),
                    'median': round(median_volume, 2),
                    'std': round(std_volume, 2)
                },
                'calculation': {
                    'volume_diff_pct': round(volume_diff_pct, 2),
                    'volume_ratio': round(volume_ratio, 2),
                    'percentile': round(percentile, 2)
                },
                'signal': {
                    'status': signal,
                    'color': signal_color,
                    'intensity': intensity,
                    'description': description,
                    'intensity_description': intensity_description
                },
                'interpretation': {
                    'display_text': f"{volume_diff_pct:+.2f}%",
                    'summary': f"Today's volume is {volume_ratio:.2f}x the {volume_ma_period}-day average",
                    'context': self._interpret_volume_change(volume_diff_pct, today_volume, avg_volume)
                },
                'statistics': {
                    'data_points': len(previous_volumes),
                    'period_start': data["date"].iloc[0],
                    'period_end': data["date"].iloc[-2] if len(data) > 1 else data["date"].iloc[0]
                }
            }
            
            logger.info(f"Trading Volume calculation completed: {volume_diff_pct:+.2f}%, Signal={signal}")
            
            return result
        except Exception as e:
            logger.error(f"Error calculating indicator 4: {e}")
            raise

    def calculate_indicator_5_simple(self, rmf_data, ma_period=20):
        """
        Calculate Real Money Flow - SIMPLIFIED VERSION
        
        نمایش‌ها:
        1. ارزش خرید حقیقی + سرانه آن
        2. ارزش فروش حقیقی + سرانه آن  
        3. قدرت خرید = سرانه خرید / سرانه فروش
        
        سیگنال‌دهی بر اساس مقایسه با میانگین:
        - قدرت خرید با میانگین‌هایش
        - خرید حقیقی با میانگین‌هایش
        - فروش حقیقی با میانگین‌هایش
        
        Args:
            rmf_data: pd.DataFrame with columns:
                - date: تاریخ
                - individual_buy_value: ارزش خرید حقیقی
                - individual_sell_value: ارزش فروش حقیقی
                - individual_buy_count: تعداد خریداران حقیقی
                - individual_sell_count: تعداد فروشندگان حقیقی
            ma_period: int, دوره میانگین (default: 20)
        
        Returns:
            dict: نتایج محاسبات
        """
        try:
            logger.info(f"Calculating Real Money Flow (Simplified) - MA period: {ma_period}")
            
            # Check data
            if len(rmf_data) < 2:
                raise ValueError(f"Need at least 2 data points, got {len(rmf_data)}")
            
            # Required columns
            required_cols = ['date', 'individual_buy_count', 'individual_sell_count', 
                           'individual_buy_value', 'individual_sell_value']
            
            for col in required_cols:
                if col not in rmf_data.columns:
                    raise ValueError(f"Column '{col}' not found")
            
            # Sort by date
            df = rmf_data.sort_values('date', ascending=True).reset_index(drop=True)
            
            # محاسبه سرانه‌ها و قدرت خرید
            df['buy_per_capita'] = df['individual_buy_value'] / df['individual_buy_count'].replace(0, np.nan)
            df['sell_per_capita'] = df['individual_sell_value'] / df['individual_sell_count'].replace(0, np.nan)
            df['buyer_power'] = df['buy_per_capita'] / df['sell_per_capita'].replace(0, np.nan)
            
            # Fill NaN with 0
            df = df.fillna(0)
            
            # محاسبه میانگین‌ها برای هر ردیف
            df['buy_value_ma'] = df['individual_buy_value'].rolling(window=ma_period, min_periods=1).mean()
            df['sell_value_ma'] = df['individual_sell_value'].rolling(window=ma_period, min_periods=1).mean()
            df['buyer_power_ma'] = df['buyer_power'].rolling(window=ma_period, min_periods=1).mean()
            
            # مقادیر آخرین روز (امروز)
            last = df.iloc[-1]
            
            # محاسبه سیگنال‌ها (3 سیگنال جداگانه)
            # Signal 1: Buyer Power vs its MA
            signal_buyer_power = 'POSITIVE' if last['buyer_power'] > last['buyer_power_ma'] else 'NEGATIVE'
            
            # Signal 2: Buy Value vs its MA
            signal_buy_value = 'POSITIVE' if last['individual_buy_value'] > last['buy_value_ma'] else 'NEGATIVE'
            
            # Signal 3: Sell Value vs its MA (inverted: higher sell = negative)
            signal_sell_value = 'NEGATIVE' if last['individual_sell_value'] > last['sell_value_ma'] else 'POSITIVE'
            
            signals = {
                'buyer_power': signal_buyer_power,
                'buy_value': signal_buy_value,
                'sell_value': signal_sell_value
            }
            
            # سیگنال کلی (اگر 2 از 3 مثبت باشد → مثبت)
            positive_count = sum(1 for s in signals.values() if s == 'POSITIVE')
            overall_signal = 'POSITIVE' if positive_count >= 2 else 'NEGATIVE'
            overall_color = 'GREEN' if overall_signal == 'POSITIVE' else 'RED'
            
            # تفسیر هر سیگنال
            signal_interpretations = {
                'buyer_power': f"Buyer Power: {last['buyer_power']:.2f} vs MA {last['buyer_power_ma']:.2f} = {signal_buyer_power}",
                'buy_value': f"Buy Value: {last['individual_buy_value']:,.0f} vs MA {last['buy_value_ma']:,.0f} = {signal_buy_value}",
                'sell_value': f"Sell Value: {last['individual_sell_value']:,.0f} vs MA {last['sell_value_ma']:,.0f} = {signal_sell_value}"
            }
            
            # آماده‌سازی نتیجه
            result = {
                'success': True,
                'current': {
                    'date': last['date'],
                    'buy_value': float(last['individual_buy_value']),
                    'sell_value': float(last['individual_sell_value']),
                    'buy_per_capita': float(last['buy_per_capita']),
                    'sell_per_capita': float(last['sell_per_capita']),
                    'buyer_power': float(last['buyer_power']),
                    'individual_buy_count': int(last['individual_buy_count']),
                    'individual_sell_count': int(last['individual_sell_count'])
                },
                'moving_averages': {
                    'buy_value_ma': float(last['buy_value_ma']),
                    'sell_value_ma': float(last['sell_value_ma']),
                    'buyer_power_ma': float(last['buyer_power_ma'])
                },
                'comparisons': {
                    'buy_value_vs_ma': float(last['individual_buy_value'] - last['buy_value_ma']),
                    'sell_value_vs_ma': float(last['individual_sell_value'] - last['sell_value_ma']),
                    'buyer_power_vs_ma': float(last['buyer_power'] - last['buyer_power_ma'])
                },
                'signals': signals,
                'signal_interpretations': signal_interpretations,
                'overall_signal': overall_signal,
                'overall_color': overall_color,
                'statistics': {
                    'total_days': len(df),
                    'ma_period': ma_period,
                    'start_date': df.iloc[0]['date'],
                    'end_date': df.iloc[-1]['date'],
                    'avg_buyer_power': float(df['buyer_power'].mean()),
                    'max_buyer_power': float(df['buyer_power'].max()),
                    'min_buyer_power': float(df['buyer_power'].min())
                },
                'daily_data': df[['date', 'buyer_power', 'buyer_power_ma', 
                                  'individual_buy_value', 'buy_value_ma',
                                  'individual_sell_value', 'sell_value_ma']].to_dict('records')
            }
            
            logger.info(f"Calculation complete - Signal: {overall_signal}")
            return result
            
        except Exception as e:
            logger.error(f"Error in calculate_indicator_5_simple: {e}")
            raise

    def calculate_indicator_5_suite(self, rmf_data, ma_periods=None):
        """
        Real Money Flow Indicator Suite (ADDITIVE - does not replace existing RMF logic)
        
        Models:
        1) Raw Real Money Flow: real_buy_value - real_sell_value
        2) Per Capita Real Money Flow: (real_buy_value/real_buy_count) - (real_sell_value/real_sell_count)
        3) Normalized Real Money Flow: (real_buy_value - real_sell_value) / total_trade_value
        4) Standardized cumulative raw: z-score of cumulative raw over the selected date window
        
        For each model:
        - flow series
        - cumulative series
        - moving averages of cumulative series for configurable periods
        
        Args:
            rmf_data: pd.DataFrame with at least:
                - date
                - individual_buy_value / individual_sell_value
                - individual_buy_count / individual_sell_count
                Optional:
                - corporate_buy_value / corporate_sell_value
                - total_trade_value / Value
            ma_periods: list[int], moving average periods (default: [5, 10, 20])
        
        Returns:
            dict: structured suite output (aligned arrays)
        """
        try:
            logger.info("Calculating Real Money Flow Suite (Raw/PerCapita/Normalized/StandardizedRaw)")
            
            if ma_periods is None:
                ma_periods = [5, 10, 20]
            
            # Validate data
            if rmf_data is None or len(rmf_data) == 0:
                raise ValueError("RMF data is empty")
            
            if 'date' not in rmf_data.columns:
                raise ValueError("Column 'date' not found")
            
            # Sort by date to ensure correct cumulative direction
            df = rmf_data.sort_values('date', ascending=True).reset_index(drop=True).copy()
            
            # Column mapping to preserve current data structures (no interface changes)
            buy_value_col = 'individual_buy_value'
            sell_value_col = 'individual_sell_value'
            buy_count_col = 'individual_buy_count'
            sell_count_col = 'individual_sell_count'
            
            required = [buy_value_col, sell_value_col, buy_count_col, sell_count_col]
            for col in required:
                if col not in df.columns:
                    raise ValueError(f"Column '{col}' not found")
            
            # Ensure numeric types (caller usually converts, but keep suite robust)
            for col in required:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Total traded value (best-effort, without changing data layer)
            if 'total_trade_value' in df.columns:
                total_trade_value = pd.to_numeric(df['total_trade_value'], errors='coerce')
            elif 'Value' in df.columns:
                total_trade_value = pd.to_numeric(df['Value'], errors='coerce')
            else:
                corp_buy = pd.to_numeric(df['corporate_buy_value'], errors='coerce') if 'corporate_buy_value' in df.columns else 0
                corp_sell = pd.to_numeric(df['corporate_sell_value'], errors='coerce') if 'corporate_sell_value' in df.columns else 0
                total_trade_value = df[buy_value_col].fillna(0) + df[sell_value_col].fillna(0) + pd.Series(corp_buy).fillna(0) + pd.Series(corp_sell).fillna(0)
            
            # Fill NaNs after conversion
            buy_value = df[buy_value_col].fillna(0).to_numpy(dtype=float)
            sell_value = df[sell_value_col].fillna(0).to_numpy(dtype=float)
            buy_count = df[buy_count_col].fillna(0).to_numpy(dtype=float)
            sell_count = df[sell_count_col].fillna(0).to_numpy(dtype=float)
            total_trade_value_arr = pd.Series(total_trade_value).fillna(0).to_numpy(dtype=float)
            
            # Helper: MA on cumulative series using the same rolling mean style used elsewhere in project
            def _ma_dict(series_arr, periods):
                s = pd.Series(series_arr, dtype=float)
                out = {}
                for p in periods:
                    try:
                        period = int(p)
                    except Exception:
                        continue
                    if period <= 0:
                        continue
                    out[period] = s.rolling(window=period, min_periods=1).mean().to_numpy(dtype=float)
                return out
            
            # ===========================
            # Model 1: Raw Real Money Flow
            # ===========================
            raw_flow = buy_value - sell_value
            raw_cum = np.cumsum(raw_flow)
            raw_ma = _ma_dict(raw_cum, ma_periods)
            
            # =================================
            # Model 2: Per Capita Real Money Flow
            # =================================
            buy_per_capita = np.divide(buy_value, buy_count, out=np.zeros_like(buy_value, dtype=float), where=buy_count != 0)
            sell_per_capita = np.divide(sell_value, sell_count, out=np.zeros_like(sell_value, dtype=float), where=sell_count != 0)
            per_capita_flow = buy_per_capita - sell_per_capita
            per_capita_cum = np.cumsum(per_capita_flow)
            per_capita_ma = _ma_dict(per_capita_cum, ma_periods)
            
            # ==================================
            # Model 3: Normalized Real Money Flow
            # ==================================
            normalized_flow = np.divide(raw_flow, total_trade_value_arr, out=np.zeros_like(raw_flow, dtype=float), where=total_trade_value_arr != 0)
            normalized_cum = np.cumsum(normalized_flow)
            normalized_ma = _ma_dict(normalized_cum, ma_periods)
            
            # Standardized cumulative raw (z-score over the requested window; mean/std recomputed each run)
            mu_raw_cum = float(np.mean(raw_cum))
            sigma_raw_cum = float(np.std(raw_cum, ddof=0))
            if not np.isfinite(sigma_raw_cum) or sigma_raw_cum == 0.0:
                standardized_raw_cum = np.zeros_like(raw_cum, dtype=float)
            else:
                standardized_raw_cum = (raw_cum - mu_raw_cum) / sigma_raw_cum
            standardized_raw_ma = _ma_dict(standardized_raw_cum, ma_periods)
            
            result = {
                'raw': {
                    'flow': raw_flow,
                    'cumulative': raw_cum,
                    'ma': raw_ma
                },
                'per_capita': {
                    'flow': per_capita_flow,
                    'cumulative': per_capita_cum,
                    'ma': per_capita_ma
                },
                'normalized': {
                    'flow': normalized_flow,
                    'cumulative': normalized_cum,
                    'ma': normalized_ma
                },
                'standardized_raw': {
                    'mean_cumulative_raw': mu_raw_cum,
                    'std_cumulative_raw': sigma_raw_cum,
                    'cumulative': standardized_raw_cum,
                    'ma': standardized_raw_ma
                }
            }
            
            logger.info("Real Money Flow Suite calculated successfully")
            return result
        
        except Exception as e:
            logger.error(f"Error in calculate_indicator_5_suite: {e}")
            raise
    
    def calculate_indicator_5(self, rmf_data, power_ma_period=20):
        """
        Calculate indicator 5: Real Money Flow (جریان نقدینگی حقیقی)
        Analyzes buyer power based on individual (real) investor activity.
        
        Args:
            rmf_data: pd.DataFrame, real money flow data with columns:
                - 'date': date in Jalali format (YYYY-MM-DD)
                - 'individual_buy_count': number of individual buyers
                - 'individual_sell_count': number of individual sellers
                - 'individual_buy_value': total value of individual buys
                - 'individual_sell_value': total value of individual sells
                (other columns not used for this indicator)
            power_ma_period: int, period for calculating weighted average (default: 20 days)
        
        Returns:
            dict: containing:
                - 'daily_metrics': list of dicts with daily calculations
                - 'current_power': float, today's buyer power
                - 'weighted_avg_power': float, weighted average of buyer power
                - 'signal': str, 'POSITIVE' or 'NEGATIVE'
                - 'signal_color': str, 'GREEN' or 'RED'
                - 'ranking': str, classification of buyer power
        """
        try:
            logger.info(f"Calculating indicator 5 (Real Money Flow)")
            logger.info(f"Data shape: {rmf_data.shape}")
            logger.info(f"Power MA Period: {power_ma_period} days")
            
            # Check if we have enough data
            if len(rmf_data) < 2:
                logger.error(f"Not enough data. Need at least 2 data points")
                raise ValueError(f"Not enough data. Need at least 2 data points, got {len(rmf_data)}")
            
            # Required columns
            required_cols = ['date', 'individual_buy_count', 'individual_sell_count', 
                           'individual_buy_value', 'individual_sell_value']
            
            for col in required_cols:
                if col not in rmf_data.columns:
                    raise ValueError(f"Required column '{col}' not found in data")
            
            # Sort by date to ensure correct order
            rmf_data = rmf_data.sort_values('date', ascending=True).reset_index(drop=True)
            
            # Calculate daily metrics
            daily_metrics = []
            buyer_powers = []
            
            for idx, row in rmf_data.iterrows():
                # Real buy basket = Total real buy value / Number of real buyers
                real_buy_basket = row['individual_buy_value'] / row['individual_buy_count'] if row['individual_buy_count'] > 0 else 0
                
                # Real sell basket = Total real sell value / Number of real sellers  
                real_sell_basket = row['individual_sell_value'] / row['individual_sell_count'] if row['individual_sell_count'] > 0 else 0
                
                # Buyer power = Real buy basket / Real sell basket
                buyer_power = real_buy_basket / real_sell_basket if real_sell_basket > 0 else 0
                
                daily_metrics.append({
                    'date': row['date'],
                    'real_buy_value': float(row['individual_buy_value']),
                    'real_sell_value': float(row['individual_sell_value']),
                    'real_buy_count': int(row['individual_buy_count']),
                    'real_sell_count': int(row['individual_sell_count']),
                    'real_buy_basket': float(real_buy_basket),
                    'real_sell_basket': float(real_sell_basket),
                    'buyer_power': float(buyer_power)
                })
                
                buyer_powers.append(buyer_power)
            
            buyer_powers = np.array(buyer_powers)
            
            # Calculate weighted average for the last power_ma_period days
            if len(buyer_powers) >= power_ma_period:
                recent_powers = buyer_powers[-power_ma_period:]
            else:
                recent_powers = buyer_powers
            
            # Calculate weights based on the formula
            weights = []
            for p in recent_powers:
                if p > 1:
                    # Positive weight
                    w = p - 1
                elif p < 1 and p > 0:
                    # Negative weight (normalized)
                    w = -(1/p - 1)
                else:
                    w = 0
                weights.append(w)
            
            weights = np.array(weights)
            
            # Calculate weighted average
            if np.sum(np.abs(weights)) > 0:
                weighted_avg_power = np.average(recent_powers, weights=np.abs(weights))
            else:
                weighted_avg_power = np.mean(recent_powers)
            
            # Current (today's) buyer power
            current_power = buyer_powers[-1]
            
            # Determine signal
            if current_power > weighted_avg_power:
                signal = "POSITIVE"
                signal_color = "GREEN"
            else:
                signal = "NEGATIVE"
                signal_color = "RED"
            
            # Ranking classification
            if current_power >= 3:
                ranking = "قدرت خریدار بالای 3: سبز پررنگ"
                ranking_class = "very_high"
            elif current_power >= 1.5:
                ranking = "قدرت خریدار بین 1.5 تا 3: سبز"
                ranking_class = "high"
            elif current_power >= 1:
                ranking = "قدرت خریدار بین 1 تا 1.5: سبز کم‌رنگ"
                ranking_class = "low"
            else:
                # Less than 1
                if current_power >= 0.67:  # 1/1.5
                    ranking = "قدرت خریدار بین 0.67 تا 1: قرمز کم‌رنگ"
                    ranking_class = "low_negative"
                elif current_power >= 0.33:  # 1/3
                    ranking = "قدرت خریدار بین 0.33 تا 0.67: قرمز"
                    ranking_class = "negative"
                else:
                    ranking = "قدرت خریدار کمتر از 0.33: قرمز پررنگ"
                    ranking_class = "very_negative"
            
            # Calculate individual signals for UI display
            signals = {
                'buyer_power': signal,  # Same as overall signal (primary indicator)
                'buy_value': 'N/A',  # Not calculated in this function
                'sell_value': 'N/A'  # Not calculated in this function
            }
            
            signal_interpretations = {
                'buyer_power': f"Buyer Power: {current_power:.2f} vs Weighted Average: {weighted_avg_power:.2f} = {signal}",
                'buy_value': "Not calculated in standard RMF",
                'sell_value': "Not calculated in standard RMF"
            }
            
            result = {
                'daily_metrics': daily_metrics,
                'current_power': float(current_power),
                'weighted_avg_power': float(weighted_avg_power),
                'signal': signal,
                'signal_color': signal_color,
                'signals': signals,  # Individual signals
                'signal_interpretations': signal_interpretations,  # Text descriptions
                'ranking': ranking,
                'ranking_class': ranking_class,
                'statistics': {
                    'total_days': len(rmf_data),
                    'ma_period_used': min(len(buyer_powers), power_ma_period),
                    'start_date': daily_metrics[0]['date'],
                    'end_date': daily_metrics[-1]['date'],
                    'avg_buyer_power': float(np.mean(buyer_powers)),
                    'max_buyer_power': float(np.max(buyer_powers)),
                    'min_buyer_power': float(np.min(buyer_powers))
                }
            }
            
            logger.info(f"Real Money Flow calculated successfully")
            logger.info(f"Current buyer power: {current_power:.3f}")
            logger.info(f"Weighted average: {weighted_avg_power:.3f}")
            logger.info(f"Signal: {signal}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating indicator 5: {e}")
            raise