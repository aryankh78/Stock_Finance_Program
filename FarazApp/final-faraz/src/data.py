# -*- coding: utf-8 -*-
# ========================================================
# Database Module for Burs Iran Exchange Signaling System
entity_name ="data"
# Author: MohammadReza Saeidi
# ========================================================
# Important Notes:
# 1. This module contains functions to manage data operations.
# 2. These operations include fetching data, preprocessing data, storing data and retrieving data.
# ========================================================
# Importing the necessary libraries
# ========================================================
# Importing the necessary libraries
# -Built-in libraries
import logging
import os
import json
# -Third-party libraries
import numpy as np
import pandas as pd
import finpy_tse as fpy
import jdatetime
import shutil
# -Custom libraries
from src.database import Database

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
class Data:
    """
    Data class
    This class is designed to manage data operations.
    Args:
        None
    Returns:
        None
    """
    def __init__(self):
        logger.info("Initializing Data class")
        self.db = Database()
        self.conn = None
        logger.info("Data class initialized successfully")
    
    def make_candle_data(self, oneday_microtransactions_data, time_frame):
        """
        Make candle data from microtransactions data
        Args:
            oneday_microtransactions_data: np.array, the microtransactions data of one day.
            Must be sorted by timestamp ascending.
            The day starts from 09:00:00 and ends at 13:00:00.
            - 0: timestamp(int, seconds since epoch)
            - 1: price(float)
            - 2: volume(int)
            time_frame: int, the time frame in seconds
        Returns:
            candle_data: np.array, the candle data
            - 0: timestamp(int, seconds since epoch)
            - 1: open price(float)
            - 2: high price(float)
            - 3: low price(float)
            - 4: close price(float)
            - 5: volume(int)
        """
        data= oneday_microtransactions_data.copy()
        try:
            logger.info("Making candle data from microtransactions data")
            logger.info(f"Microtransactions data shape: {data.shape}")
            logger.info(f"Time frame: {time_frame}")
            if data.shape[0]==0:
                logger.warning("Microtransactions data is empty! returning empty array")
                return np.array([])
            first_transaction_timestamp= data[0,0]
            logger.info("calculating date")
            date= (first_transaction_timestamp//60*60*24)*60*60*24
            logger.info("Loading data config file")
            with open('config/data_config.json', 'r', encoding='utf-8') as f:
                data_config = json.load(f)
            opening_timestamp_day= data_config['opening_timestamp_day']
            closing_timestamp_day= data_config['closing_timestamp_day']
            logger.info("Data config file loaded successfully")
            logger.info("Calculating start and end timestamps")
            start_timestamp= date+opening_timestamp_day
            end_timestamp= date+closing_timestamp_day
            logger.info("Calculating mid variable timestamp")
            mid_variable_timestamp= start_timestamp+time_frame
            logger.info("Calculating timestamps list")
            timestamps_list=[]
            while mid_variable_timestamp<=end_timestamp:
                timestamps_list.append([start_timestamp, mid_variable_timestamp])
                start_timestamp= mid_variable_timestamp
                mid_variable_timestamp= start_timestamp+time_frame
            logger.info("Calculating timestamps list completed")
            logger.info("Calculating candle data")
            candle_data= np.array([])
            for limits in timestamps_list:
                start_timestamp= limits[0]
                end_timestamp= limits[1]
                candle_data= data[data[:,0]>=start_timestamp and data[:,0]<=end_timestamp]
                open_price= candle_data[0,1]
                high_price= np.max(candle_data[:,1])
                low_price= np.min(candle_data[:,1])
                close_price= candle_data[-1,1]
                volume= np.sum(candle_data[:,2])
                candle_data= np.append(candle_data, np.array([start_timestamp, open_price, high_price, low_price, close_price, volume]))
            return candle_data
        except Exception as e:
            logger.error(f"Error making candle data: {e}")
            raise

    def fetch_microtransactions_data(self, symbol, start_date, end_date):
        """
        Fetch microtransactions data from the database
        Args:
            symbol: str, the symbol name
            date: str, the date in format YYYY-MM-DD
        Returns:
            microtransactions_data: pd.DataFrame, the microtransactions data fetched from Iran Stock Exchange API
            - "timestamp": int, the timestamp of the transaction
            - "price": float, the price of the transaction
            - "volume": int, the volume of the transaction
        """
        try:
            logger.info("Fetching microtransactions data from Iran Stock Exchange API")
            logger.info(f"Symbol: {symbol}")
            logger.info(f"Start date: {start_date}")
            logger.info(f"End date: {end_date}")
            microtransactions_data= fpy.Get_IntradayTrades_History(
                                                                stock=symbol,
                                                                start_date=start_date,
                                                                end_date=end_date,
                                                                jalali_date=True,
                                                                combined_datatime=True,
                                                                show_progress=False)
            if len(microtransactions_data)==0:
                logger.warning("No microtransactions data found! returning empty dataframe")
                return pd.DataFrame(columns=['timestamp', 'price', 'volume'])
            microtransactions_data['timestamp']= microtransactions_data.index.values
            microtransactions_data['timestamp']= microtransactions_data['timestamp'].apply(lambda x: int(jdatetime.datetime.strptime(x, '%Y-%m-%d %H:%M:%S').timestamp()))
            microtransactions_data= microtransactions_data[['timestamp', 'price', 'volume']].reset_index(drop=True)
            if start_date==end_date:
                logger.info("Start date and end date are the same! returning microtransactions data for the same day")
                return microtransactions_data
            else:
                logger.info("Start date and end date are different! returning microtransactions data for the different days as a list of dataframes")
                results= []
                start_date_timestamp= int(jdatetime.datetime.strptime(start_date, '%Y-%m-%d').timestamp())
                end_date_timestamp= int(jdatetime.datetime.strptime(end_date, '%Y-%m-%d').timestamp())
                mid_variable_timestamp= start_date_timestamp+60*60*24
                while mid_variable_timestamp<=end_date_timestamp:
                    microtransactions_data_for_day= microtransactions_data[(microtransactions_data['timestamp']>=start_date_timestamp)&(microtransactions_data['timestamp']<mid_variable_timestamp)]
                    microtransactions_data_for_day= microtransactions_data_for_day.reset_index(drop=True)
                    results.append(microtransactions_data_for_day)
                    start_date_timestamp= mid_variable_timestamp
                    mid_variable_timestamp= start_date_timestamp+60*60*24
                return results
        except Exception as e:
            logger.error(f"Error fetching microtransactions data: {e}")
            raise
    
    def _download_data_from_api(self, symbol, start_date, end_date):
        """
        Download daily data from Iran Stock Exchange API
        Args:
            symbol: str, the symbol name
            start_date: str, the start date in format YYYY-MM-DD
            end_date: str, the end date in format YYYY-MM-DD
        Returns:
            daily_data: pd.DataFrame, the daily data
        """
        try:
            logger.info(f"Downloading data from API for {symbol} from {start_date} to {end_date}")
            daily_data = fpy.Get_Price_History(
                stock=symbol,
                start_date=start_date,
                end_date=end_date,
                ignore_date=False,
                adjust_price=True,
                show_weekday=False,
                double_date=False)
            
            if daily_data is None or len(daily_data) == 0:
                logger.warning("No daily data found from API")
                return pd.DataFrame(columns=['timestamp', 'adjfinal', 'adjopen', 'adjhigh', 'adjlow', 'adjclose', 'Volume', 'Value'])
            
            daily_data['timestamp'] = daily_data.index.values
            daily_data['timestamp'] = daily_data['timestamp'].apply(
                lambda x: int(jdatetime.datetime.strptime(x, '%Y-%m-%d').timestamp()))
            daily_data.rename(columns={
                'Adj Final': 'adjfinal',
                'Adj Open': 'adjopen',
                'Adj High': 'adjhigh',
                'Adj Low': 'adjlow',
                'Adj Close': 'adjclose'
            }, inplace=True)
            
            if 'Volume' not in daily_data.columns:
                logger.warning("Volume column not found in API response")
                daily_data['Volume'] = 0
            if 'Value' not in daily_data.columns:
                logger.warning("Value column not found in API response")
                daily_data['Value'] = 0
            daily_data = daily_data[['timestamp', 'adjfinal', 'adjopen', 'adjhigh', 'adjlow', 'adjclose', 'Volume', 'Value']].reset_index(drop=True)
            
            logger.info(f"Downloaded {len(daily_data)} rows from API")
            return daily_data
        except Exception as e:
            logger.error(f"Error downloading data from API: {e}")
            return pd.DataFrame(columns=['timestamp', 'adjfinal', 'adjopen', 'adjhigh', 'adjlow', 'adjclose', 'Volume', 'Value'])
    
    def _create_daily_candles_table(self, symbol):
        """Create table for daily candles if it doesn't exist"""
        try:
            table_name = f"{symbol}_daily_candles"
            logger.info(f"Creating table {table_name} if not exists")
            
            if self.conn is None:
                self.conn = self.db.connect()
            
            cursor = self.conn.cursor()
            create_table_query = f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    timestamp BIGINT PRIMARY KEY,
                    adjfinal DOUBLE PRECISION,
                    adjopen DOUBLE PRECISION,
                    adjhigh DOUBLE PRECISION,
                    adjlow DOUBLE PRECISION,
                    adjclose DOUBLE PRECISION,
                    volume BIGINT,
                    value BIGINT
                )
            """
            cursor.execute(create_table_query)
            # Ensure older tables also have the value column.
            cursor.execute(f'ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS value BIGINT')
            self.conn.commit()
            cursor.close()
            logger.info(f"Table {table_name} created/verified successfully")
        except Exception as e:
            logger.error(f"Error creating table: {e}")
            raise
    
    def _save_to_database(self, symbol, data):
        """Save candle data to database"""
        try:
            if len(data) == 0:
                logger.warning("No data to save to database")
                return
            
            table_name = f"{symbol}_daily_candles"
            logger.info(f"Saving {len(data)} rows to {table_name}")
            
            # Ensure table exists
            self._create_daily_candles_table(symbol)
            
            if self.conn is None:
                self.conn = self.db.connect()
            
            cursor = self.conn.cursor()
            
            # Insert data using ON CONFLICT to handle duplicates
            for _, row in data.iterrows():
                insert_query = f"""
                    INSERT INTO {table_name} (timestamp, adjfinal, adjopen, adjhigh, adjlow, adjclose, volume, value)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (timestamp) DO UPDATE SET
                        adjfinal = EXCLUDED.adjfinal,
                        adjopen = EXCLUDED.adjopen,
                        adjhigh = EXCLUDED.adjhigh,
                        adjlow = EXCLUDED.adjlow,
                        adjclose = EXCLUDED.adjclose,
                        volume = EXCLUDED.volume,
                        value = EXCLUDED.value
                """
                cursor.execute(insert_query, (
                    int(row['timestamp']),
                    float(row['adjfinal']),
                    float(row['adjopen']),
                    float(row['adjhigh']),
                    float(row['adjlow']),
                    float(row['adjclose']),
                    int(row['Volume']) if 'Volume' in row else 0,
                    int(row['Value']) if 'Value' in row else 0
                ))
            
            self.conn.commit()
            cursor.close()
            logger.info(f"Successfully saved {len(data)} rows to database")
        except Exception as e:
            logger.error(f"Error saving to database: {e}")
            if self.conn:
                self.conn.rollback()
    
    def _fetch_from_database(self, symbol, start_date, end_date):
        """Fetch data from database"""
        try:
            table_name = f"{symbol}_daily_candles"
            start_ts = int(jdatetime.datetime.strptime(start_date, '%Y-%m-%d').timestamp())
            end_ts = int(jdatetime.datetime.strptime(end_date, '%Y-%m-%d').timestamp())
            
            logger.info(f"Fetching from database table {table_name}")

            # Use a short-lived connection per call to avoid shared-connection blocking between requests.
            conn = self.db.connect()
            try:
                # Check if table exists
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_schema = 'public' AND table_name = %s
                    )
                """, (table_name,))
                table_exists = cursor.fetchone()[0]
                cursor.close()

                if not table_exists:
                    logger.info(f"Table {table_name} does not exist")
                    return pd.DataFrame(columns=['timestamp', 'adjfinal', 'adjopen', 'adjhigh', 'adjlow', 'adjclose', 'Volume', 'Value'])

                # Ensure schema compatibility for legacy tables created before Value support.
                cursor = conn.cursor()
                cursor.execute(f'ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS value BIGINT')
                conn.commit()
                cursor.close()

                # Fetch data
                query = f"""
                    SELECT timestamp, adjfinal, adjopen, adjhigh, adjlow, adjclose, volume AS "Volume", COALESCE(value, 0) AS "Value"
                    FROM {table_name}
                    WHERE timestamp >= %s AND timestamp <= %s
                    ORDER BY timestamp ASC
                """
                data = pd.read_sql_query(query, conn, params=(start_ts, end_ts))
            finally:
                conn.close()
            logger.info(f"Fetched {len(data)} rows from database")
            return data
        except Exception as e:
            logger.error(f"Error fetching from database: {e}")
            return pd.DataFrame(columns=['timestamp', 'adjfinal', 'adjopen', 'adjhigh', 'adjlow', 'adjclose', 'Volume', 'Value'])

    def _has_missing_value_data(self, df):
        """Return True when Value has missing or non-positive entries."""
        try:
            if df is None or len(df) == 0 or 'Value' not in df.columns:
                return True
            value_series = pd.to_numeric(df['Value'], errors='coerce')
            missing_count = int(value_series.isna().sum())
            non_positive_count = int((value_series.fillna(0) <= 0).sum())
            return (missing_count > 0) or (non_positive_count > 0)
        except Exception:
            return True

    def backfill_missing_value_data(self, symbol, start_date=None, end_date=None):
        """
        Backfill Value column for existing rows using API data and DB upsert.
        If date range is not provided, it auto-detects from missing-value rows.
        """
        try:
            table_name = f"{symbol}_daily_candles"
            logger.info(f"Starting Value backfill for {symbol}")
            conn = self.db.connect()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_schema = 'public' AND table_name = %s
                    )
                """, (table_name,))
                exists = cursor.fetchone()[0]
                if not exists:
                    cursor.close()
                    logger.info(f"Backfill skipped: table {table_name} does not exist")
                    return {'symbol': symbol, 'updated_rows': 0, 'reason': 'table_missing'}

                cursor.execute(f'ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS value BIGINT')
                conn.commit()

                if start_date is None or end_date is None:
                    cursor.execute(f"""
                        SELECT MIN(timestamp), MAX(timestamp)
                        FROM {table_name}
                        WHERE COALESCE(value, 0) <= 0
                    """)
                    min_ts, max_ts = cursor.fetchone()
                    if min_ts is None or max_ts is None:
                        cursor.close()
                        logger.info(f"Backfill skipped: no missing Value rows for {symbol}")
                        return {'symbol': symbol, 'updated_rows': 0, 'reason': 'no_missing_values'}
                    start_date = jdatetime.datetime.fromtimestamp(min_ts).strftime('%Y-%m-%d')
                    end_date = jdatetime.datetime.fromtimestamp(max_ts).strftime('%Y-%m-%d')
                cursor.close()
            finally:
                conn.close()

            api_data = self._download_data_from_api(symbol, start_date, end_date)
            if len(api_data) == 0:
                logger.warning(f"Backfill API returned no rows for {symbol}")
                return {'symbol': symbol, 'updated_rows': 0, 'reason': 'api_empty'}

            self._save_to_database(symbol, api_data)

            verify_df = self._fetch_from_database(symbol, start_date, end_date)
            value_series = pd.to_numeric(verify_df['Value'], errors='coerce') if 'Value' in verify_df.columns else pd.Series([], dtype='float64')
            positive_count = int((value_series.fillna(0) > 0).sum()) if len(value_series) > 0 else 0
            logger.info(f"Backfill completed for {symbol}: positive Value rows in range={positive_count}")
            return {'symbol': symbol, 'updated_rows': positive_count, 'reason': 'ok', 'start_date': start_date, 'end_date': end_date}
        except Exception as e:
            logger.error(f"Error in Value backfill for {symbol}: {e}")
            return {'symbol': symbol, 'updated_rows': 0, 'reason': f'error: {e}'}
    
    def fetch_daily_candle_data(self, symbol, start_date, end_date, allow_value_refresh=True):
        """
        Fetch daily data - checks database first, downloads from API if needed
        Args:
            symbol: str, the symbol name
            start_date: str, the start date in format YYYY-MM-DD
            end_date: str, the end date in format YYYY-MM-DD
        Returns:
            daily_data: pd.DataFrame, the daily data
            - "timestamp": int, the timestamp of the day
            - "adjfinal": float, the final price of the day
            - "adjopen": float, the open price of the day
            - "adjhigh": float, the high price of the day
            - "adjlow": float, the low price of the day
            - "adjclose": float, the close price of the day
            - "Volume": int, the trading volume of the day
            - "Value": int, the trading value of the day
        """
        try:
            logger.info(f"Fetching daily candle data for {symbol} from {start_date} to {end_date}")
            
            # Step 1: Try to fetch from database
            db_data = self._fetch_from_database(symbol, start_date, end_date)
            
            # Step 2: Check if we have all the data we need
            if len(db_data) > 0:
                logger.info(f"Found {len(db_data)} rows in database")
                # We have some data, check if it covers the full range
                start_ts = int(jdatetime.datetime.strptime(start_date, '%Y-%m-%d').timestamp())
                end_ts = int(jdatetime.datetime.strptime(end_date, '%Y-%m-%d').timestamp())
                
                db_start_ts = db_data['timestamp'].min()
                db_end_ts = db_data['timestamp'].max()
                
                # If database data covers the requested range, return it
                if db_start_ts <= start_ts and db_end_ts >= end_ts:
                    # If Value is missing in covered range, refresh from API only once per request.
                    if self._has_missing_value_data(db_data):
                        if allow_value_refresh:
                            logger.info("Database range covered but Value is missing, refreshing once from API")
                            refresh_data = self._download_data_from_api(symbol, start_date, end_date)
                            if len(refresh_data) > 0:
                                self._save_to_database(symbol, refresh_data)
                                refreshed_db_data = self._fetch_from_database(symbol, start_date, end_date)
                                logger.info(f"Returning refreshed DB data ({len(refreshed_db_data)} rows)")
                                return refreshed_db_data
                            logger.warning("One-time Value refresh returned no API data, returning DB data as-is")
                            return db_data
                        logger.info("Value refresh already attempted once, returning DB data as-is")
                        return db_data
                    logger.info("Database data covers requested range, returning from database")
                    return db_data
                else:
                    logger.info("Database data doesn't cover full range, will download from API")
            else:
                logger.info("No data in database, will download from API")
            
            # Step 3: Download from API
            api_data = self._download_data_from_api(symbol, start_date, end_date)
            
            if len(api_data) == 0:
                logger.warning("No data available from API")
                return db_data  # Return whatever we have from database
            
            # Step 4: Save to database
            self._save_to_database(symbol, api_data)
            
            # Step 5: Return the API data
            logger.info(f"Returning {len(api_data)} rows from API")
            return api_data
            
        except Exception as e:
            logger.error(f"Error fetching daily candle data: {e}")
            raise
    
    def _download_index_data_from_api(self, index_name, start_date, end_date):
        """Download index data from API"""
        try:
            logger.info(f"Downloading index data for {index_name} from API")
            
            # Map index names to finpy-tse functions
            if index_name in ['شاخص کل', 'شاخص']:
                index_data = fpy.Get_CWI_History(
                    start_date=start_date,
                    end_date=end_date,
                    ignore_date=False,
                    just_adj_close=False,
                    show_weekday=False,
                    double_date=False
                )
            elif index_name == 'شاخص کل هم وزن':
                index_data = fpy.Get_EWI_History(
                    start_date=start_date,
                    end_date=end_date,
                    ignore_date=False,
                    just_adj_close=False,
                    show_weekday=False,
                    double_date=False
                )
            else:
                # For other indices, try to use Get_Price_History
                logger.warning(f"Index {index_name} not recognized, trying Get_Price_History")
                index_data = fpy.Get_Price_History(
                    stock=index_name,
                    start_date=start_date,
                    end_date=end_date,
                    ignore_date=False,
                    adjust_price=True,
                    show_weekday=False,
                    double_date=False
                )
            
            if index_data is None or len(index_data) == 0:
                logger.warning(f"No index data found for {index_name}")
                return pd.DataFrame(columns=['timestamp', 'adjfinal', 'adjopen', 'adjhigh', 'adjlow', 'adjclose'])
            
            # Process the data
            index_data['timestamp'] = index_data.index.values
            index_data['timestamp'] = index_data['timestamp'].apply(
                lambda x: int(jdatetime.datetime.strptime(x, '%Y-%m-%d').timestamp())
            )
            
            # Rename columns to match expected format
            rename_map = {
                'Adj Final': 'adjfinal', 'Adj Open': 'adjopen', 
                'Adj High': 'adjhigh', 'Adj Low': 'adjlow', 'Adj Close': 'adjclose',
                'Final': 'adjfinal', 'Open': 'adjopen', 'High': 'adjhigh',
                'Low': 'adjlow', 'Close': 'adjclose',
                'close': 'adjclose', 'open': 'adjopen',
                'high': 'adjhigh', 'low': 'adjlow'
            }
            index_data.rename(columns=rename_map, inplace=True)
            
            # Find primary price column
            price_col = None
            if 'adjclose' in index_data.columns:
                if hasattr(index_data['adjclose'], 'shape') and len(index_data['adjclose'].shape) > 1:
                    price_col = index_data['adjclose'].iloc[:, 0]
                else:
                    price_col = index_data['adjclose']
            elif 'adjfinal' in index_data.columns:
                price_col = index_data['adjfinal']
            
            if price_col is None:
                logger.error(f"No suitable price column found in index data")
                return pd.DataFrame(columns=['timestamp', 'adjfinal', 'adjopen', 'adjhigh', 'adjlow', 'adjclose'])
            
            # Create clean DataFrame
            clean_data = pd.DataFrame()
            clean_data['timestamp'] = index_data['timestamp']
            
            for col in ['adjfinal', 'adjopen', 'adjhigh', 'adjlow', 'adjclose']:
                if col in index_data.columns:
                    col_data = index_data[col]
                    clean_data[col] = col_data.iloc[:, 0] if isinstance(col_data, pd.DataFrame) else col_data
                else:
                    clean_data[col] = price_col if isinstance(price_col, pd.Series) else price_col.iloc[:, 0]
            
            logger.info(f"Downloaded {len(clean_data)} rows of index data")
            return clean_data
        except Exception as e:
            logger.error(f"Error downloading index data from API: {e}")
            return pd.DataFrame(columns=['timestamp', 'adjfinal', 'adjopen', 'adjhigh', 'adjlow', 'adjclose'])
    
    def _save_index_to_database(self, index_name, data):
        """Save index data to database"""
        try:
            if len(data) == 0:
                logger.warning("No index data to save to database")
                return
            
            # Use a safe table name (remove spaces and special chars)
            safe_index_name = index_name.replace(' ', '_').replace('ی', 'ي').replace('ک', 'ك')
            table_name = f"index_{safe_index_name}_daily"
            logger.info(f"Saving {len(data)} rows of index data to {table_name}")
            
            # Create table if not exists
            if self.conn is None:
                self.conn = self.db.connect()
            
            cursor = self.conn.cursor()
            create_table_query = f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    timestamp BIGINT PRIMARY KEY,
                    adjfinal DOUBLE PRECISION,
                    adjopen DOUBLE PRECISION,
                    adjhigh DOUBLE PRECISION,
                    adjlow DOUBLE PRECISION,
                    adjclose DOUBLE PRECISION
                )
            """
            cursor.execute(create_table_query)
            self.conn.commit()
            
            # Insert data
            for _, row in data.iterrows():
                insert_query = f"""
                    INSERT INTO {table_name} (timestamp, adjfinal, adjopen, adjhigh, adjlow, adjclose)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (timestamp) DO UPDATE SET
                        adjfinal = EXCLUDED.adjfinal,
                        adjopen = EXCLUDED.adjopen,
                        adjhigh = EXCLUDED.adjhigh,
                        adjlow = EXCLUDED.adjlow,
                        adjclose = EXCLUDED.adjclose
                """
                cursor.execute(insert_query, (
                    int(row['timestamp']),
                    float(row['adjfinal']),
                    float(row['adjopen']),
                    float(row['adjhigh']),
                    float(row['adjlow']),
                    float(row['adjclose'])
                ))
            
            self.conn.commit()
            cursor.close()
            logger.info(f"Successfully saved {len(data)} rows of index data")
        except Exception as e:
            logger.error(f"Error saving index data to database: {e}")
            if self.conn:
                self.conn.rollback()
    
    def _fetch_index_from_database(self, index_name, start_date, end_date):
        """Fetch index data from database"""
        try:
            safe_index_name = index_name.replace(' ', '_').replace('ی', 'ي').replace('ک', 'ك')
            table_name = f"index_{safe_index_name}_daily"
            start_ts = int(jdatetime.datetime.strptime(start_date, '%Y-%m-%d').timestamp())
            end_ts = int(jdatetime.datetime.strptime(end_date, '%Y-%m-%d').timestamp())
            
            logger.info(f"Fetching index data from database table {table_name}")
            
            conn = self.db.connect()
            try:
                # Check if table exists
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_schema = 'public' AND table_name = %s
                    )
                """, (table_name,))
                table_exists = cursor.fetchone()[0]
                cursor.close()

                if not table_exists:
                    logger.info(f"Table {table_name} does not exist")
                    return pd.DataFrame(columns=['timestamp', 'adjfinal', 'adjopen', 'adjhigh', 'adjlow', 'adjclose'])

                # Fetch data
                query = f"""
                    SELECT timestamp, adjfinal, adjopen, adjhigh, adjlow, adjclose
                    FROM {table_name}
                    WHERE timestamp >= %s AND timestamp <= %s
                    ORDER BY timestamp ASC
                """
                data = pd.read_sql_query(query, conn, params=(start_ts, end_ts))
            finally:
                conn.close()
            logger.info(f"Fetched {len(data)} rows of index data from database")
            return data
        except Exception as e:
            logger.error(f"Error fetching index data from database: {e}")
            return pd.DataFrame(columns=['timestamp', 'adjfinal', 'adjopen', 'adjhigh', 'adjlow', 'adjclose'])
    
    def fetch_index_data(self, index_name, start_date, end_date):
        """
        Fetch market index data - checks database first, downloads from API if needed
        Args:
            index_name: str, the index name (e.g., 'شاخص کل', 'شاخص کل هم وزن', etc.)
            start_date: str, the start date in format YYYY-MM-DD
            end_date: str, the end date in format YYYY-MM-DD
        Returns:
            index_data: pd.DataFrame, the index data with columns:
            - "timestamp": int, the timestamp of the day
            - "adjfinal": float, the final value of the index
            - "adjopen": float, the open value of the index
            - "adjhigh": float, the high value of the index
            - "adjlow": float, the low value of the index
            - "adjclose": float, the close value of the index
        """
        try:
            logger.info(f"Fetching index data for {index_name} from {start_date} to {end_date}")
            
            # Step 1: Try database first
            db_data = self._fetch_index_from_database(index_name, start_date, end_date)
            
            # Step 2: Check if we have complete data
            if len(db_data) > 0:
                logger.info(f"Found {len(db_data)} rows of index data in database")
                start_ts = int(jdatetime.datetime.strptime(start_date, '%Y-%m-%d').timestamp())
                end_ts = int(jdatetime.datetime.strptime(end_date, '%Y-%m-%d').timestamp())
                
                db_start_ts = db_data['timestamp'].min()
                db_end_ts = db_data['timestamp'].max()
                
                if db_start_ts <= start_ts and db_end_ts >= end_ts:
                    logger.info("Database data covers requested range, returning from database")
                    return db_data
                else:
                    logger.info("Database data doesn't cover full range, will download from API")
            else:
                logger.info("No index data in database, will download from API")
            
            # Step 3: Download from API
            api_data = self._download_index_data_from_api(index_name, start_date, end_date)
            
            if len(api_data) == 0:
                logger.warning("No index data available from API")
                return db_data
            
            # Step 4: Save to database
            self._save_index_to_database(index_name, api_data)
            
            # Step 5: Return the API data
            logger.info(f"Returning {len(api_data)} rows of index data from API")
            return api_data
            
        except Exception as e:
            logger.error(f"Error fetching index data: {e}")
            raise

    def _create_client_types_table(self, symbol):
        """Create table for client types (Real Money Flow) if it doesn't exist"""
        try:
            table_name = f"{symbol}_client_types"
            logger.info(f"Creating table {table_name} if not exists")
            
            if self.conn is None:
                self.conn = self.db.connect()
            
            cursor = self.conn.cursor()
            create_table_query = f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    date TEXT PRIMARY KEY,
                    individual_buy_count BIGINT,
                    individual_sell_count BIGINT,
                    individual_buy_value BIGINT,
                    individual_sell_value BIGINT,
                    individual_buy_vol BIGINT,
                    individual_sell_vol BIGINT,
                    individual_ownership_change DOUBLE PRECISION,
                    corporate_buy_count BIGINT,
                    corporate_sell_count BIGINT,
                    corporate_buy_value BIGINT,
                    corporate_sell_value BIGINT
                )
            """
            cursor.execute(create_table_query)
            self.conn.commit()
            cursor.close()
            logger.info(f"Table {table_name} created/verified successfully")
        except Exception as e:
            logger.error(f"Error creating table: {e}")
            raise
    
    def _save_client_types_to_database(self, symbol, data):
        """Save client types data to database"""
        try:
            if len(data) == 0:
                logger.warning("No client types data to save")
                return
            
            table_name = f"{symbol}_client_types"
            logger.info(f"Saving {len(data)} rows to {table_name}")
            
            # Ensure table exists
            self._create_client_types_table(symbol)
            
            if self.conn is None:
                self.conn = self.db.connect()
            
            cursor = self.conn.cursor()
            
            # Insert data using ON CONFLICT
            saved_count = 0
            skipped_count = 0
            
            for _, row in data.iterrows():
                # Validate date before inserting
                date_str = str(row.get('date', row.name))
                
                # Skip invalid dates
                try:
                    jdatetime.datetime.strptime(date_str, '%Y-%m-%d')
                except:
                    logger.debug(f"Skipping invalid date: {date_str}")
                    skipped_count += 1
                    continue
                
                insert_query = f"""
                    INSERT INTO {table_name} (
                        date, individual_buy_count, individual_sell_count,
                        individual_buy_value, individual_sell_value,
                        individual_buy_vol, individual_sell_vol,
                        individual_ownership_change,
                        corporate_buy_count, corporate_sell_count,
                        corporate_buy_value, corporate_sell_value
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (date) DO UPDATE SET
                        individual_buy_count = EXCLUDED.individual_buy_count,
                        individual_sell_count = EXCLUDED.individual_sell_count,
                        individual_buy_value = EXCLUDED.individual_buy_value,
                        individual_sell_value = EXCLUDED.individual_sell_value,
                        individual_buy_vol = EXCLUDED.individual_buy_vol,
                        individual_sell_vol = EXCLUDED.individual_sell_vol,
                        individual_ownership_change = EXCLUDED.individual_ownership_change,
                        corporate_buy_count = EXCLUDED.corporate_buy_count,
                        corporate_sell_count = EXCLUDED.corporate_sell_count,
                        corporate_buy_value = EXCLUDED.corporate_buy_value,
                        corporate_sell_value = EXCLUDED.corporate_sell_value
                """
                
                # Prepare values with default 0 for missing columns
                values = (
                    date_str,
                    int(row.get('individual_buy_count', 0)) if pd.notna(row.get('individual_buy_count', 0)) else 0,
                    int(row.get('individual_sell_count', 0)) if pd.notna(row.get('individual_sell_count', 0)) else 0,
                    int(row.get('individual_buy_value', 0)) if pd.notna(row.get('individual_buy_value', 0)) else 0,
                    int(row.get('individual_sell_value', 0)) if pd.notna(row.get('individual_sell_value', 0)) else 0,
                    int(row.get('individual_buy_vol', 0)) if pd.notna(row.get('individual_buy_vol', 0)) else 0,
                    int(row.get('individual_sell_vol', 0)) if pd.notna(row.get('individual_sell_vol', 0)) else 0,
                    float(row.get('individual_ownership_change', 0)) if pd.notna(row.get('individual_ownership_change', 0)) else 0,
                    int(row.get('corporate_buy_count', 0)) if pd.notna(row.get('corporate_buy_count', 0)) else 0,
                    int(row.get('corporate_sell_count', 0)) if pd.notna(row.get('corporate_sell_count', 0)) else 0,
                    int(row.get('corporate_buy_value', 0)) if pd.notna(row.get('corporate_buy_value', 0)) else 0,
                    int(row.get('corporate_sell_value', 0)) if pd.notna(row.get('corporate_sell_value', 0)) else 0
                )
                
                try:
                    cursor.execute(insert_query, values)
                    saved_count += 1
                except Exception as e:
                    error_text = str(e)
                    # Avoid noisy per-row debug spam for aborted transaction state.
                    if 'current transaction is aborted' not in error_text.lower():
                        logger.debug(f"Skipping row with date {date_str}: {e}")
                    # Clear failed statement state so next rows can continue safely.
                    if self.conn:
                        self.conn.rollback()
                    skipped_count += 1
                    continue
            
            self.conn.commit()
            cursor.close()
            
            if skipped_count > 0:
                logger.info(f"Saved {saved_count} rows, skipped {skipped_count} invalid rows")
            else:
                logger.info(f"Successfully saved {saved_count} rows to database")
        except Exception as e:
            logger.error(f"Error saving client types to database: {e}")
            if self.conn:
                self.conn.rollback()
    
    def _fetch_client_types_from_database(self, symbol, start_date, end_date):
        """Fetch client types data from database"""
        try:
            table_name = f"{symbol}_client_types"
            logger.info(f"Fetching client types from database table {table_name}")

            conn = self.db.connect()
            try:
                # Check if table exists
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_schema = 'public' AND table_name = %s
                    )
                """, (table_name,))
                table_exists = cursor.fetchone()[0]
                cursor.close()

                if not table_exists:
                    logger.info(f"Table {table_name} does not exist")
                    return pd.DataFrame()

                # Fetch data
                query = f"""
                    SELECT * FROM {table_name}
                    WHERE date >= %s AND date <= %s
                    ORDER BY date ASC
                """
                data = pd.read_sql_query(query, conn, params=(start_date, end_date))
            finally:
                conn.close()
            logger.info(f"Fetched {len(data)} rows from database")
            return data
        except Exception as e:
            logger.error(f"Error fetching client types from database: {e}")
            return pd.DataFrame()
    
    def fetch_client_types_data(self, symbol, start_date, end_date):
        """
        Fetch client types (Real Money Flow) data - checks database first, downloads if needed
        Args:
            symbol: str, symbol name
            start_date: str, start date in Jalali format YYYY-MM-DD
            end_date: str, end date in Jalali format YYYY-MM-DD
        Returns:
            pd.DataFrame with client types data
        """
        try:
            logger.info(f"Fetching client types data for {symbol} from {start_date} to {end_date}")
            
            # Step 1: Try database first
            db_data = self._fetch_client_types_from_database(symbol, start_date, end_date)
            
            # Calculate date range coverage
            from datetime import datetime
            import jdatetime
            
            start_dt = jdatetime.datetime.strptime(start_date, '%Y-%m-%d').date()
            end_dt = jdatetime.datetime.strptime(end_date, '%Y-%m-%d').date()
            days_needed = (end_dt - start_dt).days + 1
            
            # Check if database has enough recent data and that it is up-to-date
            if len(db_data) > 0:
                logger.info(f"Found {len(db_data)} rows in database")
                
                # Check that the latest date in DB is at least the requested end_date (data not stale)
                date_col = db_data['date']
                db_max_val = date_col.max()
                if hasattr(db_max_val, 'strftime'):
                    db_max_date_str = db_max_val.strftime('%Y-%m-%d')
                else:
                    db_max_date_str = str(db_max_val).strip()[:10]
                try:
                    db_max_dt = jdatetime.datetime.strptime(db_max_date_str, '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    db_max_dt = None
                # Require data to be up-to-date: latest DB date must be within 3 days of requested end (weekends/holidays)
                if db_max_dt is None or (end_dt - db_max_dt).days > 3:
                    if db_max_dt is None:
                        logger.info("Could not parse latest date in database, will download from API")
                    else:
                        logger.info(
                            f"Database data is stale (latest: {db_max_date_str}, requested end: {end_date}), will download from API"
                        )
                elif len(db_data) >= days_needed * 0.5:  # At least 50% coverage
                    logger.info("Database data is sufficient, returning from database")
                    return db_data
                else:
                    logger.info("Database data is incomplete, will download from API")
            else:
                logger.info("No data in database, will download from API")
            
            # Step 2: Download from pytse_client
            logger.info(f"Downloading client types from pytse_client for {symbol}")
            
            from pytse_client import download_client_types_records
            
            data_dict = download_client_types_records(symbol)
            
            if not data_dict or symbol not in data_dict:
                logger.error(f"Could not download data for {symbol}")
                return db_data  # Return whatever we have from database
            
            api_data = data_dict[symbol]
            
            if api_data is None or len(api_data) == 0:
                logger.warning("No data from API")
                return db_data
            
            logger.info(f"Downloaded {len(api_data)} rows from pytse_client")
            
            # Step 3: Ensure date column exists
            if 'date' not in api_data.columns:
                api_data = api_data.reset_index()
                if 'index' in api_data.columns:
                    api_data = api_data.rename(columns={'index': 'date'})
            
            # Step 4: Convert Gregorian dates to Jalali for database storage
            logger.info("Converting dates from Gregorian to Jalali for database")
            from datetime import datetime as dt_datetime
            
            jalali_dates = []
            valid_indices = []
            
            for idx, date_val in enumerate(api_data['date']):
                try:
                    if isinstance(date_val, (pd.Timestamp, dt_datetime)):
                        greg_date = date_val
                    else:
                        greg_date = dt_datetime.strptime(str(date_val), '%Y-%m-%d')
                    
                    jalali_date = jdatetime.date.fromgregorian(date=greg_date.date())
                    jalali_str = jalali_date.strftime('%Y-%m-%d')
                    
                    # Validate by trying to parse it back
                    try:
                        jdatetime.datetime.strptime(jalali_str, '%Y-%m-%d')
                        jalali_dates.append(jalali_str)
                        valid_indices.append(idx)
                    except:
                        logger.warning(f"Invalid Jalali date: {jalali_str}, skipping")
                        
                except Exception as e:
                    logger.warning(f"Could not convert date {date_val}: {e}")
            
            # Keep only valid rows
            if len(valid_indices) < len(api_data):
                logger.info(f"Keeping {len(valid_indices)} valid dates out of {len(api_data)}")
                api_data = api_data.iloc[valid_indices].copy()
            
            api_data['date'] = jalali_dates
            
            # Step 5: Save to database
            self._save_client_types_to_database(symbol, api_data)
            
            # Step 6: Filter to requested date range so return matches DB behavior
            if 'date' in api_data.columns and len(api_data) > 0:
                mask = (api_data['date'] >= start_date) & (api_data['date'] <= end_date)
                api_data = api_data.loc[mask].copy()
                logger.info(f"Returning {len(api_data)} rows from API (filtered to {start_date}..{end_date})")
            else:
                logger.info(f"Returning {len(api_data)} rows from API")
            return api_data
            
        except Exception as e:
            logger.error(f"Error fetching client types data: {e}")
            raise
    
    def aggregate_to_weekly(self, daily_data):
        """
        Aggregate daily candle data to weekly timeframe based on Persian calendar.
        Week starts on Saturday (شنبه) and ends on Friday (جمعه).
        Thursday and Friday are weekend.
        
        Args:
            daily_data: pd.DataFrame with daily candle data
        Returns:
            pd.DataFrame with weekly candle data
        """
        try:
            logger.info(f"Aggregating {len(daily_data)} daily candles to weekly timeframe")
            
            if len(daily_data) == 0:
                return pd.DataFrame(columns=['timestamp', 'adjfinal', 'adjopen', 'adjhigh', 'adjlow', 'adjclose', 'Volume', 'Value'])
            
            # Convert timestamps to dates
            daily_data['date'] = daily_data['timestamp'].apply(
                lambda x: jdatetime.datetime.fromtimestamp(x).date()
            )
            
            # Find week start (Saturday) for each date
            def get_week_start(date):
                # Get day of week (0=Saturday, 6=Friday in jdatetime)
                weekday = date.togregorian().weekday()  # Monday=0, Sunday=6
                # Convert to Persian week (Saturday=0, Friday=6)
                persian_weekday = (weekday + 2) % 7
                # Calculate days back to Saturday
                days_back = persian_weekday
                week_start = date - jdatetime.timedelta(days=days_back)
                return week_start
            
            daily_data['week_start'] = daily_data['date'].apply(get_week_start)
            
            # Group by week and aggregate
            weekly_data = []
            for week_start, group in daily_data.groupby('week_start'):
                # Sort by date to ensure correct order
                group = group.sort_values('timestamp')
                
                weekly_candle = {
                    'timestamp': int(jdatetime.datetime.combine(week_start, jdatetime.time()).timestamp()),
                    'adjopen': group.iloc[0]['adjopen'],
                    'adjhigh': group['adjhigh'].max(),
                    'adjlow': group['adjlow'].min(),
                    'adjclose': group.iloc[-1]['adjclose'],
                    'adjfinal': group.iloc[-1]['adjfinal'],
                    'Volume': group['Volume'].sum(),
                    'Value': group['Value'].sum() if 'Value' in group.columns else 0
                }
                weekly_data.append(weekly_candle)
            
            result = pd.DataFrame(weekly_data)
            logger.info(f"Created {len(result)} weekly candles")
            return result
            
        except Exception as e:
            logger.error(f"Error aggregating to weekly: {e}")
            raise
    
    def aggregate_to_monthly(self, daily_data):
        """
        Aggregate daily candle data to monthly timeframe based on Persian calendar.
        
        Args:
            daily_data: pd.DataFrame with daily candle data
        Returns:
            pd.DataFrame with monthly candle data
        """
        try:
            logger.info(f"Aggregating {len(daily_data)} daily candles to monthly timeframe")
            
            if len(daily_data) == 0:
                return pd.DataFrame(columns=['timestamp', 'adjfinal', 'adjopen', 'adjhigh', 'adjlow', 'adjclose', 'Volume', 'Value'])
            
            # Convert timestamps to dates
            daily_data['date'] = daily_data['timestamp'].apply(
                lambda x: jdatetime.datetime.fromtimestamp(x).date()
            )
            
            # Get year-month for grouping
            daily_data['year_month'] = daily_data['date'].apply(
                lambda x: (x.year, x.month)
            )
            
            # Group by month and aggregate
            monthly_data = []
            for (year, month), group in daily_data.groupby('year_month'):
                # Sort by date to ensure correct order
                group = group.sort_values('timestamp')
                
                # First day of month
                month_start = jdatetime.date(year, month, 1)
                
                monthly_candle = {
                    'timestamp': int(jdatetime.datetime.combine(month_start, jdatetime.time()).timestamp()),
                    'adjopen': group.iloc[0]['adjopen'],
                    'adjhigh': group['adjhigh'].max(),
                    'adjlow': group['adjlow'].min(),
                    'adjclose': group.iloc[-1]['adjclose'],
                    'adjfinal': group.iloc[-1]['adjfinal'],
                    'Volume': group['Volume'].sum(),
                    'Value': group['Value'].sum() if 'Value' in group.columns else 0
                }
                monthly_data.append(monthly_candle)
            
            result = pd.DataFrame(monthly_data)
            logger.info(f"Created {len(result)} monthly candles")
            return result
            
        except Exception as e:
            logger.error(f"Error aggregating to monthly: {e}")
            raise
    
    def fetch_market_watch_data(self):
        """
        Fetch market watch data from the database
        Args:
            None
        Returns:
            market_watch_data: pd.DataFrame, the market watch data fetched from Iran Stock Exchange API
        """
        try:
            logger.info("Fetching market watch data from Iran Stock Exchange API")
            fpy.Get_MarketWatch(save_excel=True, save_path=f"{config['necessary_directories']['watchlists_temp_path']}")
            watchlist_folder_fils= os.listdir(f"{config['necessary_directories']['watchlists_download_path']}")
            watchlist_folder_fils= [i for i in watchlist_folder_fils if i.endswith(".xlsx")]
            watchlist_folder_fils.sort()
            if len(watchlist_folder_fils)==0:
                logger.warning("No watchlist file found")
                last_watchlist_file_number=0
            else:
                last_watchlist_file_number= int(watchlist_folder_fils[-1].split(".")[0].split("-")[-1])
            new_watchlist_file_number= last_watchlist_file_number+1
            temp_folder_file_list= os.listdir(f"{config['necessary_directories']['watchlists_temp_path']}")
            temp_folder_file_list=[i for i in temp_folder_file_list if i.endswith(".xlsx")]
            temp_folder_file_list=[i for i in temp_folder_file_list if i.startswith("MarketWatch")]
            if len(temp_folder_file_list)==0:
                logger.warning("No temp folder file found! returning empty dataframe")
                new_watchlist= pd.DataFrame(columns=["symbol","open","high","low","close","final"])
                new_watchlist.to_csv(f"{config['necessary_directories']['watchlists_download_path']}/{new_watchlist_file_number}.csv", index=False)
                return new_watchlist
            new_watchlist_file_name= temp_folder_file_list[-1]
            new_watchlist_file_path= f"{config['necessary_directories']['watchlists_temp_path']}/{new_watchlist_file_name}"
            new_watchlist= pd.read_excel(new_watchlist_file_path)
            new_watchlist.rename(columns={"Ticker":"symbol"}, inplace=True)
            new_watchlist.rename(columns={"Open":"open"}, inplace=True)
            new_watchlist.rename(columns={"High":"high"}, inplace=True)
            new_watchlist.rename(columns={"Low":"low"}, inplace=True)
            new_watchlist.rename(columns={"Close":"close"}, inplace=True)
            new_watchlist.rename(columns={"Final":"final"}, inplace=True)
            new_watchlist= new_watchlist[["symbol","open","high","low","close","final"]].reset_index(drop=True)
            with open("config/data_config.json", "r", encoding='utf-8') as f:
                focused_symbols= json.load(f)["focused_symbols"]
            new_watchlist= new_watchlist[new_watchlist["symbol"].isin(focused_symbols)].reset_index(drop=True)
            new_watchlist.to_csv(f"{config['necessary_directories']['watchlists_download_path']}/{new_watchlist_file_number}.csv", index=False)
            shutil.rmtree(f"{config['necessary_directories']['watchlists_temp_path']}")
            os.makedirs(f"{config['necessary_directories']['watchlists_temp_path']}", exist_ok=True)
            return new_watchlist
        except Exception as e:
            logger.error(f"Error fetching market watch data: {e}")
            raise
            
