# -*- coding: utf-8 -*-
# ========================================================
# Main Script for Burs Iran Exchange Signaling System
# Web Application with Interactive Charts
entity_name = "main"
# Author: MohammadReza Saeidi
# ========================================================
# Importing the necessary libraries
# ========================================================
# -Built-in libraries
import sys
import io
import logging
import os
import json
from datetime import datetime, timedelta

# Force UTF-8 encoding for Windows (skip when stdout/stderr are unavailable, e.g. NSSM service)
if sys.platform == 'win32':
    if sys.stdout is not None and hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    if sys.stderr is not None and hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
# -Third-party libraries
import hmac
from urllib.parse import urlparse, urljoin

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import jdatetime
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.utils
# -Custom libraries
from src.data import Data
from src.calculations import Calculations

# Lazy import for pytse_client - will be imported when needed
download_client_types_records = None

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
        os.makedirs('logs', exist_ok=True)
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(lineno)d - %(message)s')
        
        # Console handler with UTF-8 encoding for Windows
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File handler with UTF-8 encoding
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
    with open('config/data_config.json', 'r', encoding='utf-8') as f:
        data_config = json.load(f)
    logger.info("Config files loaded successfully")
except Exception as e:
    logger.error(f"Error loading config file: {e}")
    raise

# ========================================================
# Flask App Setup
# ========================================================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get(
    'FLASK_SECRET_KEY', 'faraz-energy-dev-secret-change-for-production'
)
app.config['JSON_AS_ASCII'] = False  # Allow Persian characters in JSON
app.config['JSONIFY_MIMETYPE'] = 'application/json; charset=utf-8'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['LOGIN_USERNAME'] = os.environ.get('APP_LOGIN_USERNAME', 'admin')
app.config['LOGIN_PASSWORD'] = os.environ.get('APP_LOGIN_PASSWORD', 'admin')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', '0').lower() in (
    '1', 'true', 'yes'
)

# Initialize Data and Calculations classes
data_handler = Data()
calculations_handler = Calculations()

# Cache for client types data (Real Money Flow)
# This prevents downloading all symbols multiple times
client_types_cache = {
    'data': None,
    'timestamp': None,
    'ttl': 3600  # Cache for 1 hour (3600 seconds)
}

# Add UTF-8 encoding to all responses (Windows fix)
@app.after_request
def after_request(response):
    response.headers['Content-Type'] = response.headers.get('Content-Type', 'text/html')
    if 'charset' not in response.headers['Content-Type']:
        response.headers['Content-Type'] += '; charset=utf-8'
    return response


def _is_safe_redirect_url(target):
    """Reject open redirects: only same-host relative URLs."""
    if not target or not isinstance(target, str):
        return False
    target = target.strip()
    if not target.startswith('/') or target.startswith('//'):
        return False
    ref = urlparse(request.host_url)
    test = urlparse(urljoin(request.host_url, target))
    return test.scheme in ('http', 'https') and ref.netloc == test.netloc


@app.before_request
def require_login():
    """Require authentication for all routes except login, static assets, and JSON API responses."""
    if request.endpoint == 'static':
        return
    if request.endpoint == 'login':
        return
    if session.get('logged_in'):
        return

    if request.path.startswith('/calculate_') or \
       request.path.startswith('/summary_watchlist') or \
       request.path == '/get_available_symbols':
        return jsonify({
            'error': 'نیاز به ورود است. لطفاً صفحه را از نو بارگذاری کنید.',
            'login_required': True
        }), 401

    next_path = request.path
    if request.query_string:
        next_path = request.full_path
        if next_path.endswith('?'):
            next_path = next_path[:-1]
    return redirect(url_for('login', next=next_path))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Minimal login page (default user/pass: admin / admin; override via env)."""
    if session.get('logged_in'):
        return redirect(url_for('index'))

    error = None
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        u_exp = app.config['LOGIN_USERNAME']
        p_exp = app.config['LOGIN_PASSWORD']
        if hmac.compare_digest(username, u_exp) and hmac.compare_digest(password, p_exp):
            session.clear()
            session.permanent = True
            session['logged_in'] = True
            nxt = request.args.get('next') or request.form.get('next') or ''
            if nxt and _is_safe_redirect_url(nxt):
                return redirect(nxt)
            return redirect(url_for('index'))
        error = 'نام کاربری یا رمز عبور نادرست است'

    return render_template(
        'login.html',
        error=error,
        next_param=request.args.get('next', '')
    )


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ========================================================
# Helper Functions
# ========================================================
class NumpyEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles numpy types"""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)

RMF_FLOW_CHART_SPECS = (
    ('raw', 'ورود پول حقیقی', 'خام', '#059669', True, 'میلیون تومان'),
    ('per_capita', 'سرانه ورود پول حقیقی', 'سرانه', '#4f46e5', True, 'میلیون تومان'),
    ('normalized', 'ورود پول حقیقی نرمال شده نسبت به کل معاملات', 'نرمال‌شده', '#dc2626', False, 'جمع نسبت روزانه'),
    ('standardized_raw', 'ورود پول حقیقی استاندارد', 'خام استاندارد', '#0f766e', False, 'انحراف معیار (z)'),
)


def _rmf_flow_chart_traces(dates, suite_result, ma_periods, model_key, line_label, base_color, convert_million=False):
    """Build Plotly traces for one RMF flow panel."""
    ma_colors = ['#b45309', '#0369a1', '#a21caf', '#0f766e', '#64748b']
    model = (suite_result or {}).get(model_key, {})
    cumulative = model.get('cumulative', [])
    ma_dict = model.get('ma', {}) or {}
    cum_list = cumulative.tolist() if hasattr(cumulative, 'tolist') else list(cumulative)
    if convert_million:
        cum_list = [float(v) / 10000000.0 if v is not None else None for v in cum_list]

    traces = [
        go.Scatter(
            x=dates,
            y=cum_list,
            mode='lines',
            name=f'{line_label} (تجمعی)',
            line=dict(color=base_color, width=2.5),
        )
    ]
    for idx, period in enumerate(ma_periods):
        if period in ma_dict:
            series = ma_dict[period]
        elif str(period) in ma_dict:
            series = ma_dict[str(period)]
        else:
            series = None
        if series is None:
            continue
        ma_list = series.tolist() if hasattr(series, 'tolist') else list(series)
        if convert_million:
            ma_list = [float(v) / 10000000.0 if v is not None else None for v in ma_list]
        traces.append(
            go.Scatter(
                x=dates,
                y=ma_list,
                mode='lines',
                name=f'{line_label} میانگین {period}',
                line=dict(color=ma_colors[idx % len(ma_colors)], width=1.8, dash='dash'),
            )
        )
    return traces


def create_rmf_price_chart(daily_data, symbol, target_dates):
    """
    Create candlestick price chart aligned to RMF date list.
    """
    try:
        date_to_idx = {}
        for i, ts in enumerate(daily_data['timestamp'].values):
            date_to_idx[convert_timestamp_to_jalali_date(ts)] = i

        dates, open_list, high_list, low_list, close_list = [], [], [], [], []
        for date_str in target_dates:
            idx = date_to_idx.get(str(date_str))
            if idx is None:
                continue
            dates.append(str(date_str))
            open_list.append(float(daily_data['adjopen'].iloc[idx]))
            high_list.append(float(daily_data['adjhigh'].iloc[idx]))
            low_list.append(float(daily_data['adjlow'].iloc[idx]))
            close_list.append(float(daily_data['adjclose'].iloc[idx]))

        if len(dates) < 2:
            return None

        fig = go.Figure(
            data=[
                go.Candlestick(
                    x=dates,
                    open=open_list,
                    high=high_list,
                    low=low_list,
                    close=close_list,
                    name='قیمت',
                    increasing=dict(line=dict(color='#059669'), fillcolor='#10b981'),
                    decreasing=dict(line=dict(color='#dc2626'), fillcolor='#ef4444'),
                )
            ]
        )
        fig.update_layout(
            title=dict(
                text=f'نمودار قیمت {symbol}',
                font=dict(size=17, color='#0f172a', family='Tahoma, Arial'),
                x=0.5,
                xanchor='center',
            ),
            xaxis_title='تاریخ (شمسی)',
            yaxis_title='قیمت (ریال)',
            xaxis_rangeslider_visible=False,
            hovermode='x unified',
            template='plotly_white',
            paper_bgcolor='#f1f5f9',
            plot_bgcolor='#ffffff',
            height=420,
            font=dict(family='Tahoma, Arial', size=11, color='#334155'),
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='right',
                x=1,
                bgcolor='rgba(255, 255, 255, 0.96)',
                bordercolor='#cbd5e1',
                borderwidth=1,
            ),
            margin=dict(t=80, r=40, b=70, l=56),
            xaxis=_category_xaxis_monthly(dates, tickfont=dict(size=9), gridcolor='#e2e8f0', showgrid=True),
            yaxis=dict(showgrid=True, gridcolor='#e2e8f0', zeroline=True, zerolinecolor='#cbd5e1'),
        )
        return json.dumps(fig.to_dict(), cls=NumpyEncoder)
    except Exception as e:
        logger.error(f"Error creating RMF price chart: {e}")
        raise


def create_rmf_flow_charts(dates, suite_result, symbol, ma_periods):
    """
    Create separate Plotly charts for each RMF flow model (frontend toggles visibility).
    Returns dict keyed by model_key -> JSON chart string.
    """
    try:
        ma_periods = [int(p) for p in (ma_periods or []) if str(p).strip()]
        if len(ma_periods) == 0:
            ma_periods = [5, 10, 20]

        charts = {}
        for model_key, title, line_label, base_color, convert_million, y_title in RMF_FLOW_CHART_SPECS:
            traces = _rmf_flow_chart_traces(
                dates, suite_result, ma_periods, model_key, line_label, base_color, convert_million
            )
            fig = go.Figure(data=traces)
            fig.update_layout(
                title=dict(
                    text=f'{title} (تجمعی) — {symbol}',
                    font=dict(size=15, color='#0f172a', family='Tahoma, Arial'),
                    x=0.5,
                    xanchor='center',
                ),
                hovermode='x unified',
                template='plotly_white',
                paper_bgcolor='#f1f5f9',
                plot_bgcolor='#ffffff',
                height=380,
                font=dict(family='Tahoma, Arial', size=11, color='#334155'),
                legend=dict(
                    orientation='v',
                    yanchor='top',
                    y=1,
                    xanchor='left',
                    x=1.02,
                    bgcolor='rgba(255, 255, 255, 0.96)',
                    bordercolor='#cbd5e1',
                    borderwidth=1,
                    font=dict(size=10, color='#334155'),
                ),
                margin=dict(t=72, r=210, b=70, l=56),
                xaxis=_category_xaxis_monthly(dates, tickfont=dict(size=9), gridcolor='#e2e8f0', showgrid=True),
                yaxis=dict(
                    title_text=y_title,
                    showgrid=True,
                    gridcolor='#e2e8f0',
                    zeroline=True,
                    zerolinecolor='#cbd5e1',
                ),
            )
            charts[model_key] = json.dumps(fig.to_dict(), cls=NumpyEncoder)
        return charts
    except Exception as e:
        logger.error(f"Error creating RMF flow charts: {e}")
        raise


def create_rmf_suite_chart(dates, suite_result, symbol, ma_periods):
    """
    Legacy combined 4-panel RMF suite chart (kept for compatibility).
    """
    try:
        ma_periods = [int(p) for p in (ma_periods or []) if str(p).strip()]
        if len(ma_periods) == 0:
            ma_periods = [5, 10, 20]

        subplot_titles = tuple(
            f'{spec[1]} (تجمعی)' for spec in RMF_FLOW_CHART_SPECS
        )

        fig = make_subplots(
            rows=4, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.035,
            row_heights=[0.25, 0.25, 0.25, 0.25],
            subplot_titles=subplot_titles,
        )

        def _legend_cfg(y_ref):
            return dict(
                orientation='v',
                yanchor='top',
                y=y_ref,
                xanchor='left',
                x=1.02,
                bgcolor='rgba(255, 255, 255, 0.96)',
                bordercolor='#cbd5e1',
                borderwidth=1,
                font=dict(size=10, color='#334155'),
            )

        def _add_model(row, model_key, line_label, base_color, legend_key, convert_million=False):
            for trace in _rmf_flow_chart_traces(
                dates, suite_result, ma_periods, model_key, line_label, base_color, convert_million
            ):
                trace.legendgroup = legend_key
                trace.showlegend = True
                if legend_key != 'legend':
                    trace.legend = legend_key
                fig.add_trace(trace, row=row, col=1)

        _add_model(1, 'raw', 'خام', '#059669', 'legend', convert_million=True)
        _add_model(2, 'per_capita', 'سرانه', '#4f46e5', 'legend2', convert_million=True)
        _add_model(3, 'normalized', 'نرمال‌شده', '#dc2626', 'legend3', convert_million=False)
        _add_model(4, 'standardized_raw', 'خام استاندارد', '#0f766e', 'legend4', convert_million=False)

        fig.update_layout(
            title=dict(
                text=f'مجموعه نمودارهای جریان نقد حقیقی — {symbol}',
                font=dict(size=17, color='#0f172a', family='Tahoma, Arial'),
                x=0.5,
                xanchor='center',
            ),
            hovermode='x unified',
            template='plotly_white',
            paper_bgcolor='#f1f5f9',
            plot_bgcolor='#ffffff',
            height=1120,
            font=dict(family='Tahoma, Arial', size=11, color='#334155'),
            legend=_legend_cfg(0.995),
            legend2=_legend_cfg(0.74),
            legend3=_legend_cfg(0.49),
            legend4=_legend_cfg(0.24),
            margin=dict(t=128, r=210, b=70, l=56),
            xaxis=_category_xaxis_monthly(dates, tickfont=dict(size=9), gridcolor='#e2e8f0', showgrid=True),
            xaxis2=_category_xaxis_monthly(dates, tickfont=dict(size=9), gridcolor='#e2e8f0', showgrid=True),
            xaxis3=_category_xaxis_monthly(dates, tickfont=dict(size=9), gridcolor='#e2e8f0', showgrid=True),
            xaxis4=_category_xaxis_monthly(dates, tickfont=dict(size=9), gridcolor='#e2e8f0', showgrid=True),
        )
        for r, spec in enumerate(RMF_FLOW_CHART_SPECS, start=1):
            fig.update_yaxes(
                title_text=spec[5],
                showgrid=True,
                gridcolor='#e2e8f0',
                zeroline=True,
                zerolinecolor='#cbd5e1',
                row=r,
                col=1,
            )

        try:
            fig.for_each_annotation(
                lambda ann: ann.update(font=dict(color='#1e293b', size=11, family='Tahoma, Arial'))
            )
        except Exception:
            pass

        return json.dumps(fig.to_dict(), cls=NumpyEncoder)
    except Exception as e:
        logger.error(f"Error creating RMF suite chart: {e}")
        raise

def convert_timestamp_to_jalali_date(timestamp):
    """
    Convert timestamp to Jalali date string
    Args:
        timestamp: int, Unix timestamp
    Returns:
        str: Jalali date in format YYYY-MM-DD
    """
    try:
        dt = jdatetime.datetime.fromtimestamp(timestamp)
        return dt.strftime('%Y-%m-%d')
    except Exception as e:
        logger.error(f"Error converting timestamp to Jalali date: {e}")
        return str(timestamp)

def get_today_jalali():
    """
    Get today's date in Jalali calendar
    Returns:
        str: Today's date in format YYYY-MM-DD
    """
    return jdatetime.date.today().strftime('%Y-%m-%d')

def calculate_start_date(end_date, lookback_days):
    """
    Calculate start date from end date and lookback days
    Args:
        end_date: str, end date in Jalali format YYYY-MM-DD
        lookback_days: int, number of days to look back
    Returns:
        str: start date in Jalali format YYYY-MM-DD
    """
    try:
        end_dt = jdatetime.datetime.strptime(end_date, '%Y-%m-%d')
        start_dt = end_dt - timedelta(days=lookback_days)
        return start_dt.strftime('%Y-%m-%d')
    except Exception as e:
        logger.error(f"Error calculating start date: {e}")
        raise

def _monthly_category_axis_ticks(dates):
    """
    Build category-axis tickvals/ticktext with one label per Jalali month (YYYY-MM).
    Mirrors Trading Volume and Value tab x-axis behavior.
    """
    month_tick_vals = []
    month_tick_text = []
    last_month_key = None
    for d in dates:
        try:
            month_key = str(d)[:7]
        except Exception:
            month_key = str(d)
        if month_key != last_month_key:
            month_tick_vals.append(d)
            month_tick_text.append(month_key)
            last_month_key = month_key
    return month_tick_vals, month_tick_text


def _category_xaxis_monthly(dates, **extra):
    """Plotly category x-axis dict showing monthly ticks only."""
    tickvals, ticktext = _monthly_category_axis_ticks(dates)
    cfg = dict(
        type='category',
        tickmode='array',
        tickvals=tickvals,
        ticktext=ticktext,
        tickangle=0,
        tickfont=dict(size=10),
    )
    cfg.update(extra)
    return cfg

def _summary_watchlist_files():
    """Return persistent storage file paths for summary watchlist feature."""
    storage_dir = os.path.join('data')
    os.makedirs(storage_dir, exist_ok=True)
    return (
        os.path.join(storage_dir, 'summary_watchlist.json'),
        os.path.join(storage_dir, 'summary_table_cache.json')
    )

def _read_json_file(file_path, default_value):
    """Read JSON file safely with fallback."""
    try:
        if not os.path.exists(file_path):
            return default_value
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not read {file_path}: {e}")
        return default_value

def _write_json_file(file_path, data):
    """Write JSON file safely."""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Could not write {file_path}: {e}")
        raise


def _pending_summary_watchlist_row(symbol):
    """Placeholder row for a watchlist symbol before summary calculations are run."""
    hint = 'محاسبه نشده — «بروزرسانی جدول» را بزنید'
    return {
        'symbol': symbol,
        'pending': True,
        'ma': 'PENDING',
        'ma_detail': hint,
        'divergence': 'PENDING',
        'divergence_detail': hint,
        'beta': 'PENDING',
        'beta_detail': hint,
        'volume': 'PENDING',
        'volume_detail': hint,
        'value': 'PENDING',
        'value_detail': hint,
        'rmf': 'PENDING',
        'rmf_detail': hint,
        'overall': 'PENDING',
        'overall_detail': hint,
    }


def _reconcile_summary_watchlist_table_cache(table_cache, symbols):
    """
    Align cached table rows with the current watchlist order.
    Symbols without a cached row get a pending placeholder row.
    """
    rows_by = {}
    for r in table_cache.get('rows') or []:
        sym = r.get('symbol')
        if sym:
            rows_by[sym] = r
    new_rows = []
    for s in symbols:
        if s in rows_by:
            new_rows.append(rows_by[s])
        else:
            new_rows.append(_pending_summary_watchlist_row(s))
    table_cache['rows'] = new_rows
    return table_cache


def get_recent_divergence_counts(divergence_dict, timestamps, end_timestamp, valid_days=21, lookback_window=None):
    """
    Count bullish/bearish divergences that occurred within a recent validity window.
    This is used for signal generation only (chart rendering remains unchanged).
    Args:
        divergence_dict: dict with divergence lists (bearish, bullish, hidden_*)
        timestamps: sequence of candle timestamps aligned with divergence indices
        end_timestamp: int, end timestamp for the analysis window
        valid_days: int, signal validity window in days (default: 21)
        lookback_window: int or None, divergence lookback window used in detection.
            If provided and timestamp length is larger, divergence indices are
            interpreted relative to the last lookback_window candles.
    Returns:
        dict with recent bullish/bearish counts (regular + hidden + total)
    """
    try:
        threshold_ts = int(end_timestamp - (valid_days * 24 * 60 * 60))
        ts_list = [int(ts) for ts in timestamps]
        index_offset = 0
        if lookback_window is not None:
            try:
                lookback_window = int(lookback_window)
                if lookback_window > 0 and len(ts_list) > lookback_window:
                    index_offset = len(ts_list) - lookback_window
            except Exception:
                index_offset = 0

        def _count_recent(divergence_list):
            count = 0
            for div in divergence_list:
                try:
                    idx2 = int(div['price_indices'][1])
                    ts_idx2 = idx2 + index_offset
                    if 0 <= ts_idx2 < len(ts_list) and ts_list[ts_idx2] >= threshold_ts:
                        count += 1
                except Exception:
                    continue
            return count

        regular_bullish = _count_recent(divergence_dict.get('bullish', []))
        regular_bearish = _count_recent(divergence_dict.get('bearish', []))
        hidden_bullish = _count_recent(divergence_dict.get('hidden_bullish', []))
        hidden_bearish = _count_recent(divergence_dict.get('hidden_bearish', []))

        return {
            'regular_bullish': regular_bullish,
            'regular_bearish': regular_bearish,
            'hidden_bullish': hidden_bullish,
            'hidden_bearish': hidden_bearish,
            'bullish_total': regular_bullish + hidden_bullish,
            'bearish_total': regular_bearish + hidden_bearish
        }
    except Exception as e:
        logger.error(f"Error calculating recent divergence counts: {e}")
        return {
            'regular_bullish': 0,
            'regular_bearish': 0,
            'hidden_bullish': 0,
            'hidden_bearish': 0,
            'bullish_total': 0,
            'bearish_total': 0
        }

def download_single_symbol_client_types(symbol):
    """
    Download client types data for a SINGLE symbol
    This is the CORRECT way that works!
    
    Args:
        symbol: str, symbol name
    Returns:
        pd.DataFrame or None
    """
    try:
        from pytse_client import download_client_types_records
        
        logger.info(f"Downloading client types for single symbol: {symbol}")
        logger.info(f"Symbol type: {type(symbol)}, Symbol repr: {repr(symbol)}")
        
        # Download single symbol (CORRECT METHOD!)
        logger.info(f"Calling download_client_types_records('{symbol}')...")
        data = download_client_types_records(symbol)
        
        logger.info(f"Returned data type: {type(data)}")
        logger.info(f"Data is None: {data is None}")
        
        # Check result
        if not data:
            logger.error(f"No data returned for {symbol} (data is None or False)")
            return None
        
        if not isinstance(data, dict):
            logger.error(f"Expected dict, got {type(data)}")
            return None
        
        logger.info(f"Dict has {len(data)} keys: {list(data.keys())}")
        
        # Symbol should be a key in the dict
        if symbol not in data:
            logger.error(f"Symbol '{symbol}' not found in returned dict")
            logger.error(f"Available keys: {list(data.keys())}")
            
            # Try to find with different encoding or case
            for key in data.keys():
                if key.lower() == symbol.lower():
                    logger.info(f"Found with case difference: '{key}'")
                    df = data[key]
                    if isinstance(df, pd.DataFrame) and not df.empty:
                        logger.info(f"✓ Successfully got {len(df)} rows")
                        return df
            
            return None
        
        # Get DataFrame
        df = data[symbol]
        
        logger.info(f"DataFrame type: {type(df)}")
        
        if not isinstance(df, pd.DataFrame):
            logger.error(f"Expected DataFrame, got {type(df)}")
            return None
        
        if df.empty:
            logger.warning(f"DataFrame for {symbol} is empty")
            return None
        
        logger.info(f"✓ Successfully downloaded {len(df)} rows for {symbol}")
        logger.info(f"DataFrame columns: {list(df.columns)}")
        return df
        
    except Exception as e:
        logger.error(f"Error downloading {symbol}: {e}", exc_info=True)
        return None

def find_symbol_for_pytse(symbol):
    """
    Find the correct symbol identifier for pytse_client
    Tries multiple methods to find the symbol
    Args:
        symbol: str, symbol name (Persian or ticker)
    Returns:
        str: symbol identifier that pytse_client can use
    """
    try:
        from pytse_client import symbols_data
        
        # Method 1: Try to get symbol_id directly
        try:
            if hasattr(symbols_data, 'get_symbol_id'):
                symbol_id = symbols_data.get_symbol_id(symbol)
                logger.info(f"Method 1 success: Found symbol_id={symbol_id} for {symbol}")
                return symbol_id
        except Exception as e:
            logger.debug(f"Method 1 failed: {e}")
        
        # Method 2: Search in all_symbols
        try:
            if hasattr(symbols_data, 'all_symbols'):
                all_syms = symbols_data.all_symbols()
                for sym_info in all_syms:
                    if isinstance(sym_info, dict):
                        # Check if symbol matches any field
                        if (sym_info.get('نماد') == symbol or 
                            sym_info.get('نام') == symbol or
                            sym_info.get('symbol') == symbol or
                            sym_info.get('name') == symbol):
                            found_symbol = sym_info.get('نماد') or sym_info.get('symbol')
                            logger.info(f"Method 2 success: Found {found_symbol} for {symbol}")
                            return found_symbol
        except Exception as e:
            logger.debug(f"Method 2 failed: {e}")
        
        # Method 3: Load symbols_name.json directly
        try:
            import json
            import os
            # Try to find symbols_name.json in pytse_client package
            pytse_path = os.path.dirname(symbols_data.__file__)
            json_path = os.path.join(pytse_path, 'data', 'symbols_name.json')
            
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    symbols_dict = json.load(f)
                
                # Search in the dictionary
                for key, value in symbols_dict.items():
                    if value == symbol or key == symbol:
                        logger.info(f"Method 3 success: Found {key} for {symbol}")
                        return key
        except Exception as e:
            logger.debug(f"Method 3 failed: {e}")
        
        # Method 4: Try common symbol mappings
        symbol_mappings = {
            'اهرم': 'اهرم',
            'شستا': 'شستا',
            'ذوب': 'ذوب',
            'فولاد': 'فولاد',
            'خودرو': 'خودرو',
        }
        
        if symbol in symbol_mappings:
            mapped = symbol_mappings[symbol]
            logger.info(f"Method 4: Using mapped symbol {mapped} for {symbol}")
            return mapped
        
        # If all methods fail, return original symbol
        logger.warning(f"All methods failed, using original symbol: {symbol}")
        return symbol
        
    except Exception as e:
        logger.error(f"Error in find_symbol_for_pytse: {e}")
        return symbol

def create_candlestick_chart_multiple_mas(daily_data, ma_arrays, symbol, price_type, timeframe='daily'):
    """
    Create candlestick chart with multiple moving average overlays
    Args:
        daily_data: pd.DataFrame, candle data
        ma_arrays: dict, {period: np.array} for each MA
        symbol: str, stock symbol
        price_type: str, price type used for MA
        timeframe: str, timeframe (daily/weekly/monthly)
    Returns:
        str: JSON representation of the Plotly figure
    """
    try:
        logger.info(f"Creating candlestick chart with {len(ma_arrays)} MAs")
        
        # Convert timestamps to Jalali dates
        dates = [convert_timestamp_to_jalali_date(ts) for ts in daily_data['timestamp'].values]
        
        # Convert numpy arrays to Python lists to avoid Plotly binary encoding issues
        open_list = daily_data['adjopen'].tolist()
        high_list = daily_data['adjhigh'].tolist()
        low_list = daily_data['adjlow'].tolist()
        close_list = daily_data['adjclose'].tolist()
        
        # Create candlestick trace with Python lists — colors tuned for light plot background
        candlestick = go.Candlestick(
            x=dates,
            open=open_list,
            high=high_list,
            low=low_list,
            close=close_list,
            name='قیمت',
            increasing=dict(line=dict(color='#059669'), fillcolor='#10b981'),
            decreasing=dict(line=dict(color='#dc2626'), fillcolor='#ef4444')
        )
        
        # Create figure data list
        data_traces = [candlestick]
        
        # Define colors for multiple MAs (readable on light background)
        ma_line_colors = ['#0369a1', '#b45309', '#dc2626', '#0f766e', '#7c3aed', '#0d9488']
        
        # Add MA traces
        for idx, (period, ma_array) in enumerate(sorted(ma_arrays.items())):
            # Convert numpy array to list, handle NaN
            ma_list = ma_array.tolist() if hasattr(ma_array, 'tolist') else list(ma_array)
            ma_list = [None if (isinstance(x, float) and np.isnan(x)) else x for x in ma_list]
            
            ma_trace = go.Scatter(
                x=dates,
                y=ma_list,
                mode='lines',
                name=f'MA {period}',
                line=dict(color=ma_line_colors[idx % len(ma_line_colors)], width=2)
            )
            data_traces.append(ma_trace)
        
        # Create figure
        fig = go.Figure(data=data_traces)
        
        # Timeframe label
        timeframe_label = {'daily': 'روزانه', 'weekly': 'هفتگی', 'monthly': 'ماهانه'}.get(timeframe, timeframe)
        
        # Update layout — light theme (same family as volume / other charts)
        fig.update_layout(
            title=dict(
                text=f'نمودار قیمت {symbol} با میانگین‌های متحرک ({timeframe_label})',
                font=dict(size=18, color='#0f172a', family="'Segoe UI', Tahoma, Arial, sans-serif"),
                x=0.5,
                xanchor='center'
            ),
            xaxis_title='تاریخ (شمسی)',
            yaxis_title='قیمت (ریال)',
            xaxis_rangeslider_visible=False,
            hovermode='x unified',
            template='plotly_white',
            paper_bgcolor='#ffffff',
            plot_bgcolor='#fafafa',
            height=600,
            font=dict(family="'Segoe UI', Tahoma, Arial, sans-serif", size=12, color='#334155'),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                bgcolor='rgba(255, 255, 255, 0.92)',
                bordercolor='#e2e8f0',
                borderwidth=1
            ),
            xaxis=_category_xaxis_monthly(
                dates,
                tickfont=dict(size=10, color='#475569'),
                gridcolor='rgba(0, 0, 0, 0.08)',
                zerolinecolor='rgba(0, 0, 0, 0.12)'
            ),
            yaxis=dict(
                tickfont=dict(size=10, color='#475569'),
                gridcolor='rgba(0, 0, 0, 0.08)',
                zerolinecolor='rgba(0, 0, 0, 0.12)'
            )
        )
        
        # Convert to JSON using custom encoder that handles numpy types
        graphJSON = json.dumps(fig.to_dict(), cls=NumpyEncoder)
        logger.info("Candlestick chart with multiple MAs created successfully")
        
        return graphJSON
    except Exception as e:
        logger.error(f"Error creating candlestick chart: {e}")
        raise

def create_candlestick_chart(daily_data, ma_array, symbol, price_type, ma_period):
    """
    Create candlestick chart with moving average overlay (LEGACY - for backwards compatibility)
    Args:
        daily_data: pd.DataFrame, daily candle data
        ma_array: np.array, moving average values
        symbol: str, stock symbol
        price_type: str, price type used for MA
        ma_period: int, moving average period
    Returns:
        str: JSON representation of the Plotly figure
    """
    # Convert to new format and call new function
    ma_arrays = {ma_period: ma_array}
    return create_candlestick_chart_multiple_mas(daily_data, ma_arrays, symbol, price_type)

# ========================================================
# Routes
# ========================================================
@app.route('/')
def index():
    """Main page with tabs"""
    try:
        logger.info("Rendering index page")
        
        # Get available symbols from config
        symbols = data_config.get('focused_symbols', [])
        
        # Get today's date in Jalali
        today = get_today_jalali()
        
        return render_template('index.html', 
                             symbols=symbols,
                             today=today)
    except Exception as e:
        logger.error(f"Error rendering index page: {e}")
        return f"Error: {str(e)}", 500

@app.route('/calculate_divergence', methods=['POST'])
def calculate_divergence():
    """Calculate divergence indicators (RSI, MACD, MFI) and return charts"""
    try:
        logger.info("Received request to calculate divergence")
        
        # Get form data
        symbol = request.form.get('symbol')
        lookback_days = int(request.form.get('lookback_days'))
        end_date = request.form.get('end_date')
        timeframe = request.form.get('timeframe', 'daily')
        
        # Get indicator parameters with defaults
        rsi_period = int(request.form.get('rsi_period', 14))
        rsi_overbought = float(request.form.get('rsi_overbought', 70))
        rsi_oversold = float(request.form.get('rsi_oversold', 30))
        macd_short = int(request.form.get('macd_short', 12))
        macd_long = int(request.form.get('macd_long', 26))
        macd_signal = int(request.form.get('macd_signal', 9))
        mfi_period = int(request.form.get('mfi_period', 14))
        mfi_overbought = float(request.form.get('mfi_overbought', 80))
        mfi_oversold = float(request.form.get('mfi_oversold', 20))
        price_type = request.form.get('price_type', 'close')
        divergence_price_mode = request.form.get('divergence_price_mode', 'high_low')
        try:
            alignment_tol = int(request.form.get('alignment_tol', 3))
        except (TypeError, ValueError):
            return jsonify({'error': 'حداکثر فاصله هم‌ترازی باید یک عدد صحیح باشد'}), 400
        
        logger.info(f"Parameters: symbol={symbol}, lookback={lookback_days}, end_date={end_date}, timeframe={timeframe}")
        logger.info(f"RSI: period={rsi_period}, OB={rsi_overbought}, OS={rsi_oversold}")
        logger.info(f"MACD: short={macd_short}, long={macd_long}, signal={macd_signal}")
        logger.info(f"MFI: period={mfi_period}, OB={mfi_overbought}, OS={mfi_oversold}")
        logger.info(f"Divergence price mode: {divergence_price_mode}")
        logger.info(f"Divergence alignment tolerance: {alignment_tol}")
        
        # Validate inputs
        if not all([symbol, lookback_days, end_date]):
            return jsonify({'error': 'همه فیلدهای اصلی الزامی هستند'}), 400
        
        # Validate date
        try:
            end_dt = jdatetime.datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'فرمت تاریخ نامعتبر است'}), 400
        
        # Validate date is not in future
        today = jdatetime.date.today()
        if end_dt.date() > today:
            return jsonify({'error': 'تاریخ نباید از امروز بزرگتر باشد'}), 400
        
        if alignment_tol < 0 or alignment_tol > 60:
            return jsonify({'error': 'حداکثر فاصله هم‌ترازی باید بین ۰ تا ۶۰ کندل باشد'}), 400
        
        # Calculate start date
        start_date = calculate_start_date(end_date, lookback_days)
        logger.info(f"Calculated start_date: {start_date}")
        
        # Fetch daily candle data
        logger.info("Fetching daily candle data")
        daily_data = data_handler.fetch_daily_candle_data(symbol, start_date, end_date)
        
        if len(daily_data) == 0:
            return jsonify({'error': f'داده‌ای برای {symbol} یافت نشد'}), 404
        
        logger.info(f"Fetched {len(daily_data)} rows")
        
        # Convert to weekly/monthly if requested
        if timeframe == 'weekly':
            daily_data = data_handler.aggregate_to_weekly(daily_data)
            logger.info(f"Converted to weekly data: {len(daily_data)} candles")
        elif timeframe == 'monthly':
            daily_data = data_handler.aggregate_to_monthly(daily_data)
            logger.info(f"Converted to monthly data: {len(daily_data)} candles")
        
        # Check if we have enough data
        min_required = max(macd_long + macd_signal, rsi_period, mfi_period) + 10
        if len(daily_data) < min_required:
            return jsonify({'error': f'داده کافی نیست. حداقل {min_required} روز داده لازم است'}), 400
        
        # Calculate divergence indicators (RSI, MACD, MFI)
        logger.info("Calculating divergence indicators (RSI, MACD, MFI)")
        divergence_result = calculations_handler.calculate_indicator_2(
            candle_data=daily_data,
            rsi_period=rsi_period,
            rsi_overbought=rsi_overbought,
            rsi_oversold=rsi_oversold,
            macd_short=macd_short,
            macd_long=macd_long,
            macd_signal=macd_signal,
            mfi_period=mfi_period,
            mfi_overbought=mfi_overbought,
            mfi_oversold=mfi_oversold,
            lookback=lookback_days,
            price_type=price_type,
            divergence_price_mode=divergence_price_mode,
            alignment_tol=alignment_tol
        )
        
        # Extract results
        rsi_array = divergence_result['rsi_array']
        macd_array = divergence_result['macd_array']
        mfi_array = divergence_result['mfi_array']
        rsi_divergence = divergence_result['rsi_divergence']
        macd_divergence = divergence_result['macd_divergence']
        mfi_divergence = divergence_result['mfi_divergence']
        
        # Convert timestamps to dates
        dates = [convert_timestamp_to_jalali_date(ts) for ts in daily_data['timestamp'].values]
        timestamps = daily_data['timestamp'].values
        end_timestamp = int(np.max(timestamps))

        # Signal validity rule: only divergences in the last 3 weeks (21 days) are valid for signals
        rsi_recent = get_recent_divergence_counts(rsi_divergence, timestamps, end_timestamp, valid_days=21, lookback_window=lookback_days)
        macd_recent = get_recent_divergence_counts(macd_divergence, timestamps, end_timestamp, valid_days=21, lookback_window=lookback_days)
        mfi_recent = get_recent_divergence_counts(mfi_divergence, timestamps, end_timestamp, valid_days=21, lookback_window=lookback_days)
        total_recent_bullish = rsi_recent['bullish_total'] + macd_recent['bullish_total'] + mfi_recent['bullish_total']
        total_recent_bearish = rsi_recent['bearish_total'] + macd_recent['bearish_total'] + mfi_recent['bearish_total']

        if total_recent_bullish == 0 and total_recent_bearish == 0:
            divergence_signal = 'NEUTRAL'
        elif total_recent_bullish > total_recent_bearish:
            divergence_signal = 'POSITIVE'
        elif total_recent_bearish > total_recent_bullish:
            divergence_signal = 'NEGATIVE'
        else:
            divergence_signal = 'NEUTRAL'
        
        # Create RSI chart
        rsi_chart = create_divergence_chart_rsi(
            daily_data=daily_data,
            rsi_array=rsi_array,
            rsi_divergence=rsi_divergence,
            dates=dates,
            symbol=symbol,
            rsi_overbought=rsi_overbought,
            rsi_oversold=rsi_oversold
        )
        
        # Create MACD chart
        macd_chart = create_divergence_chart_macd(
            daily_data=daily_data,
            macd_array=macd_array,
            macd_divergence=macd_divergence,
            dates=dates,
            symbol=symbol
        )
        
        # Create MFI chart
        mfi_chart = create_divergence_chart_mfi(
            daily_data=daily_data,
            mfi_array=mfi_array,
            mfi_divergence=mfi_divergence,
            dates=dates,
            symbol=symbol,
            mfi_overbought=mfi_overbought,
            mfi_oversold=mfi_oversold
        )
        
        # Convert numpy types to Python native types for JSON serialization
        def convert_divergence_to_json(divs, dates_list):
            """Convert divergence list to JSON-serializable format with dates"""
            result = []
            for div in divs:
                idx1 = int(div['price_indices'][0])
                idx2 = int(div['price_indices'][1])
                result.append({
                    'price_indices': (idx1, idx2),
                    'indicator_indices': (int(div['indicator_indices'][0]), int(div['indicator_indices'][1])),
                    'price_values': (float(div['price_values'][0]), float(div['price_values'][1])),
                    'indicator_values': (float(div['indicator_values'][0]), float(div['indicator_values'][1])),
                    'dates': (dates_list[idx1] if idx1 < len(dates_list) else 'N/A', 
                             dates_list[idx2] if idx2 < len(dates_list) else 'N/A')
                })
            return result
        
        # Prepare statistics (regular + hidden divergences)
        stats = {
            'total_candles': int(len(daily_data)),
            'start_date': dates[0],
            'end_date': dates[-1],
            'timeframe': timeframe,
            'divergence_price_mode': divergence_price_mode,
            'alignment_tol': alignment_tol,
            'rsi': {
                'current_value': float(rsi_array[-1]) if not np.isnan(rsi_array[-1]) else None,
                'bearish_count': int(len(rsi_divergence['bearish'])),
                'bullish_count': int(len(rsi_divergence['bullish'])),
                'hidden_bearish_count': int(len(rsi_divergence.get('hidden_bearish', []))),
                'hidden_bullish_count': int(len(rsi_divergence.get('hidden_bullish', []))),
                'divergences': {
                    'bearish': convert_divergence_to_json(rsi_divergence['bearish'], dates),
                    'bullish': convert_divergence_to_json(rsi_divergence['bullish'], dates),
                    'hidden_bearish': convert_divergence_to_json(rsi_divergence.get('hidden_bearish', []), dates),
                    'hidden_bullish': convert_divergence_to_json(rsi_divergence.get('hidden_bullish', []), dates)
                }
            },
            'macd': {
                'current_value': float(macd_array[-1]) if not np.isnan(macd_array[-1]) else None,
                'bearish_count': int(len(macd_divergence['bearish'])),
                'bullish_count': int(len(macd_divergence['bullish'])),
                'hidden_bearish_count': int(len(macd_divergence.get('hidden_bearish', []))),
                'hidden_bullish_count': int(len(macd_divergence.get('hidden_bullish', []))),
                'divergences': {
                    'bearish': convert_divergence_to_json(macd_divergence['bearish'], dates),
                    'bullish': convert_divergence_to_json(macd_divergence['bullish'], dates),
                    'hidden_bearish': convert_divergence_to_json(macd_divergence.get('hidden_bearish', []), dates),
                    'hidden_bullish': convert_divergence_to_json(macd_divergence.get('hidden_bullish', []), dates)
                }
            },
            'mfi': {
                'current_value': float(mfi_array[-1]) if not np.isnan(mfi_array[-1]) else None,
                'bearish_count': int(len(mfi_divergence['bearish'])),
                'bullish_count': int(len(mfi_divergence['bullish'])),
                'hidden_bearish_count': int(len(mfi_divergence.get('hidden_bearish', []))),
                'hidden_bullish_count': int(len(mfi_divergence.get('hidden_bullish', []))),
                'divergences': {
                    'bearish': convert_divergence_to_json(mfi_divergence['bearish'], dates),
                    'bullish': convert_divergence_to_json(mfi_divergence['bullish'], dates),
                    'hidden_bearish': convert_divergence_to_json(mfi_divergence.get('hidden_bearish', []), dates),
                    'hidden_bullish': convert_divergence_to_json(mfi_divergence.get('hidden_bullish', []), dates)
                }
            },
            'signal': divergence_signal,
            'signal_window_days': 21,
            'recent_counts': {
                'total_bullish': total_recent_bullish,
                'total_bearish': total_recent_bearish,
                'rsi': rsi_recent,
                'macd': macd_recent,
                'mfi': mfi_recent
            }
        }
        
        logger.info("Divergence calculation completed successfully")
        
        return jsonify({
            'success': True,
            'rsi_chart': rsi_chart,
            'macd_chart': macd_chart,
            'mfi_chart': mfi_chart,
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Error calculating divergence: {e}", exc_info=True)
        return jsonify({'error': f'خطا در محاسبات: {str(e)}'}), 500

def create_divergence_chart_rsi(daily_data, rsi_array, rsi_divergence, dates, symbol, rsi_overbought, rsi_oversold):
    """Create candlestick chart with RSI and divergence markers"""
    try:
        # Create subplots: candlestick on top, RSI on bottom
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.7, 0.3],
            subplot_titles=(f'نمودار قیمت {symbol}', 'RSI')
        )
        
        # Convert numpy arrays to Python lists to avoid binary encoding
        open_list = daily_data['adjopen'].tolist()
        high_list = daily_data['adjhigh'].tolist()
        low_list = daily_data['adjlow'].tolist()
        close_list = daily_data['adjclose'].tolist()
        rsi_list = [None if (isinstance(x, float) and np.isnan(x)) else x for x in rsi_array.tolist()] if hasattr(rsi_array, 'tolist') else list(rsi_array)
        
        # Candlestick
        fig.add_trace(
            go.Candlestick(
                x=dates,
                open=open_list,
                high=high_list,
                low=low_list,
                close=close_list,
                name='قیمت',
                increasing_line_color='green',
                decreasing_line_color='red'
            ),
            row=1, col=1
        )
        
        # RSI line
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=rsi_list,
                mode='lines',
                name='RSI',
                line=dict(color='blue', width=2)
            ),
            row=2, col=1
        )
        
        # RSI overbought/oversold lines
        fig.add_hline(y=rsi_overbought, line_dash="dash", line_color="red", row=2, col=1, annotation_text=f"اشباع خرید ({rsi_overbought})")
        fig.add_hline(y=rsi_oversold, line_dash="dash", line_color="green", row=2, col=1, annotation_text=f"اشباع فروش ({rsi_oversold})")
        fig.add_hline(y=50, line_dash="dot", line_color="gray", row=2, col=1)
        
        # Mark regular divergences on candlestick chart
        for i, div in enumerate(rsi_divergence.get('bearish', []), 1):
            idx1, idx2 = int(div['price_indices'][0]), int(div['price_indices'][1])
            price_val = float(div['price_values'][1])
            if idx1 < len(dates) and idx2 < len(dates):
                fig.add_annotation(
                    x=dates[idx2], y=price_val,
                    text=f"⚠️ واگرایی نزولی {i}<br>{dates[idx1]} → {dates[idx2]}",
                    showarrow=True, arrowhead=2, arrowcolor="red",
                    bgcolor="rgba(255,0,0,0.1)",
                    row=1, col=1
                )
        
        for i, div in enumerate(rsi_divergence.get('bullish', []), 1):
            idx1, idx2 = int(div['price_indices'][0]), int(div['price_indices'][1])
            price_val = float(div['price_values'][1])
            if idx1 < len(dates) and idx2 < len(dates):
                fig.add_annotation(
                    x=dates[idx2], y=price_val,
                    text=f"✅ واگرایی صعودی {i}<br>{dates[idx1]} → {dates[idx2]}",
                    showarrow=True, arrowhead=2, arrowcolor="green",
                    bgcolor="rgba(0,255,0,0.1)",
                    row=1, col=1
                )
        
        # Mark hidden divergences on candlestick chart (distinct style)
        for i, div in enumerate(rsi_divergence.get('hidden_bearish', []), 1):
            idx1, idx2 = int(div['price_indices'][0]), int(div['price_indices'][1])
            price_val = float(div['price_values'][1])
            if idx1 < len(dates) and idx2 < len(dates):
                fig.add_annotation(
                    x=dates[idx2], y=price_val,
                    text=f"🔶 واگرایی مخفی نزولی {i}<br>{dates[idx1]} → {dates[idx2]}",
                    showarrow=True, arrowhead=2, arrowcolor="darkorange",
                    bgcolor="rgba(255,165,0,0.15)",
                    row=1, col=1
                )
        
        for i, div in enumerate(rsi_divergence.get('hidden_bullish', []), 1):
            idx1, idx2 = int(div['price_indices'][0]), int(div['price_indices'][1])
            price_val = float(div['price_values'][1])
            if idx1 < len(dates) and idx2 < len(dates):
                fig.add_annotation(
                    x=dates[idx2], y=price_val,
                    text=f"🔷 واگرایی مخفی صعودی {i}<br>{dates[idx1]} → {dates[idx2]}",
                    showarrow=True, arrowhead=2, arrowcolor="teal",
                    bgcolor="rgba(0,128,128,0.15)",
                    row=1, col=1
                )
        
        fig.update_layout(
            title=f'تحلیل واگرایی RSI - {symbol}',
            xaxis_rangeslider_visible=False,
            hovermode='x unified',
            template='plotly_white',
            height=700,
            showlegend=True,
            xaxis=_category_xaxis_monthly(dates, tickfont=dict(size=10)),
            xaxis2=_category_xaxis_monthly(dates, tickfont=dict(size=10))
        )
        
        # Convert to JSON using custom encoder
        return json.dumps(fig.to_dict(), cls=NumpyEncoder)
    except Exception as e:
        logger.error(f"Error creating RSI chart: {e}")
        raise

def create_divergence_chart_mfi(daily_data, mfi_array, mfi_divergence, dates, symbol, mfi_overbought, mfi_oversold):
    """Create candlestick chart with MFI and divergence markers"""
    try:
        # Create subplots: candlestick on top, MFI on bottom
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.7, 0.3],
            subplot_titles=(f'نمودار قیمت {symbol}', 'MFI (Money Flow Index)')
        )
        
        # Convert numpy arrays to Python lists to avoid binary encoding
        open_list = daily_data['adjopen'].tolist()
        high_list = daily_data['adjhigh'].tolist()
        low_list = daily_data['adjlow'].tolist()
        close_list = daily_data['adjclose'].tolist()
        mfi_list = [None if (isinstance(x, float) and np.isnan(x)) else x for x in mfi_array.tolist()] if hasattr(mfi_array, 'tolist') else list(mfi_array)
        
        # Candlestick
        fig.add_trace(
            go.Candlestick(
                x=dates,
                open=open_list,
                high=high_list,
                low=low_list,
                close=close_list,
                name='قیمت',
                increasing_line_color='green',
                decreasing_line_color='red'
            ),
            row=1, col=1
        )
        
        # MFI line
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=mfi_list,
                mode='lines',
                name='MFI',
                line=dict(color='purple', width=2)
            ),
            row=2, col=1
        )
        
        # MFI overbought/oversold lines
        fig.add_hline(y=mfi_overbought, line_dash="dash", line_color="red", row=2, col=1, 
                     annotation_text=f"اشباع خرید ({mfi_overbought})")
        fig.add_hline(y=mfi_oversold, line_dash="dash", line_color="green", row=2, col=1, 
                     annotation_text=f"اشباع فروش ({mfi_oversold})")
        fig.add_hline(y=50, line_dash="dot", line_color="gray", row=2, col=1)
        
        # Mark regular divergences on candlestick chart
        for i, div in enumerate(mfi_divergence.get('bearish', []), 1):
            idx1, idx2 = int(div['price_indices'][0]), int(div['price_indices'][1])
            price_val = float(div['price_values'][1])
            if idx1 < len(dates) and idx2 < len(dates):
                fig.add_annotation(
                    x=dates[idx2], y=price_val,
                    text=f"⚠️ واگرایی نزولی {i}<br>{dates[idx1]} → {dates[idx2]}",
                    showarrow=True, arrowhead=2, arrowcolor="red",
                    bgcolor="rgba(255,0,0,0.1)",
                    row=1, col=1
                )
        
        for i, div in enumerate(mfi_divergence.get('bullish', []), 1):
            idx1, idx2 = int(div['price_indices'][0]), int(div['price_indices'][1])
            price_val = float(div['price_values'][1])
            if idx1 < len(dates) and idx2 < len(dates):
                fig.add_annotation(
                    x=dates[idx2], y=price_val,
                    text=f"✅ واگرایی صعودی {i}<br>{dates[idx1]} → {dates[idx2]}",
                    showarrow=True, arrowhead=2, arrowcolor="green",
                    bgcolor="rgba(0,255,0,0.1)",
                    row=1, col=1
                )
        
        # Mark hidden divergences
        for i, div in enumerate(mfi_divergence.get('hidden_bearish', []), 1):
            idx1, idx2 = int(div['price_indices'][0]), int(div['price_indices'][1])
            price_val = float(div['price_values'][1])
            if idx1 < len(dates) and idx2 < len(dates):
                fig.add_annotation(
                    x=dates[idx2], y=price_val,
                    text=f"🔶 واگرایی مخفی نزولی {i}<br>{dates[idx1]} → {dates[idx2]}",
                    showarrow=True, arrowhead=2, arrowcolor="darkorange",
                    bgcolor="rgba(255,165,0,0.15)",
                    row=1, col=1
                )
        
        for i, div in enumerate(mfi_divergence.get('hidden_bullish', []), 1):
            idx1, idx2 = int(div['price_indices'][0]), int(div['price_indices'][1])
            price_val = float(div['price_values'][1])
            if idx1 < len(dates) and idx2 < len(dates):
                fig.add_annotation(
                    x=dates[idx2], y=price_val,
                    text=f"🔷 واگرایی مخفی صعودی {i}<br>{dates[idx1]} → {dates[idx2]}",
                    showarrow=True, arrowhead=2, arrowcolor="teal",
                    bgcolor="rgba(0,128,128,0.15)",
                    row=1, col=1
                )
        
        fig.update_layout(
            title=f'تحلیل واگرایی MFI - {symbol}',
            xaxis_rangeslider_visible=False,
            hovermode='x unified',
            template='plotly_white',
            height=700,
            showlegend=True,
            xaxis=_category_xaxis_monthly(dates, tickfont=dict(size=10)),
            xaxis2=_category_xaxis_monthly(dates, tickfont=dict(size=10))
        )
        
        # Convert to JSON using custom encoder
        return json.dumps(fig.to_dict(), cls=NumpyEncoder)
    except Exception as e:
        logger.error(f"Error creating MFI chart: {e}")
        raise

def create_divergence_chart_macd(daily_data, macd_array, macd_divergence, dates, symbol):
    """Create candlestick chart with MACD and divergence markers"""
    try:
        # Create subplots
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.7, 0.3],
            subplot_titles=(f'نمودار قیمت {symbol}', 'MACD')
        )
        
        # Convert numpy arrays to Python lists to avoid binary encoding
        open_list = daily_data['adjopen'].tolist()
        high_list = daily_data['adjhigh'].tolist()
        low_list = daily_data['adjlow'].tolist()
        close_list = daily_data['adjclose'].tolist()
        macd_list = [None if (isinstance(x, float) and np.isnan(x)) else x for x in macd_array.tolist()] if hasattr(macd_array, 'tolist') else list(macd_array)
        
        # Candlestick
        fig.add_trace(
            go.Candlestick(
                x=dates,
                open=open_list,
                high=high_list,
                low=low_list,
                close=close_list,
                name='قیمت',
                increasing_line_color='green',
                decreasing_line_color='red'
            ),
            row=1, col=1
        )
        
        # MACD line
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=macd_list,
                mode='lines',
                name='MACD',
                line=dict(color='blue', width=2)
            ),
            row=2, col=1
        )
        
        # Zero line for MACD
        fig.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)
        
        # Mark regular divergences
        for i, div in enumerate(macd_divergence.get('bearish', []), 1):
            idx1, idx2 = int(div['price_indices'][0]), int(div['price_indices'][1])
            price_val = float(div['price_values'][1])
            if idx1 < len(dates) and idx2 < len(dates):
                fig.add_annotation(
                    x=dates[idx2], y=price_val,
                    text=f"⚠️ واگرایی نزولی {i}<br>{dates[idx1]} → {dates[idx2]}",
                    showarrow=True, arrowhead=2, arrowcolor="red",
                    bgcolor="rgba(255,0,0,0.1)",
                    row=1, col=1
                )
        
        for i, div in enumerate(macd_divergence.get('bullish', []), 1):
            idx1, idx2 = int(div['price_indices'][0]), int(div['price_indices'][1])
            price_val = float(div['price_values'][1])
            if idx1 < len(dates) and idx2 < len(dates):
                fig.add_annotation(
                    x=dates[idx2], y=price_val,
                    text=f"✅ واگرایی صعودی {i}<br>{dates[idx1]} → {dates[idx2]}",
                    showarrow=True, arrowhead=2, arrowcolor="green",
                    bgcolor="rgba(0,255,0,0.1)",
                    row=1, col=1
                )
        
        # Mark hidden divergences
        for i, div in enumerate(macd_divergence.get('hidden_bearish', []), 1):
            idx1, idx2 = int(div['price_indices'][0]), int(div['price_indices'][1])
            price_val = float(div['price_values'][1])
            if idx1 < len(dates) and idx2 < len(dates):
                fig.add_annotation(
                    x=dates[idx2], y=price_val,
                    text=f"🔶 واگرایی مخفی نزولی {i}<br>{dates[idx1]} → {dates[idx2]}",
                    showarrow=True, arrowhead=2, arrowcolor="darkorange",
                    bgcolor="rgba(255,165,0,0.15)",
                    row=1, col=1
                )
        
        for i, div in enumerate(macd_divergence.get('hidden_bullish', []), 1):
            idx1, idx2 = int(div['price_indices'][0]), int(div['price_indices'][1])
            price_val = float(div['price_values'][1])
            if idx1 < len(dates) and idx2 < len(dates):
                fig.add_annotation(
                    x=dates[idx2], y=price_val,
                    text=f"🔷 واگرایی مخفی صعودی {i}<br>{dates[idx1]} → {dates[idx2]}",
                    showarrow=True, arrowhead=2, arrowcolor="teal",
                    bgcolor="rgba(0,128,128,0.15)",
                    row=1, col=1
                )
        
        fig.update_layout(
            title=f'تحلیل واگرایی MACD - {symbol}',
            xaxis_rangeslider_visible=False,
            hovermode='x unified',
            template='plotly_white',
            height=700,
            showlegend=True,
            xaxis=_category_xaxis_monthly(dates, tickfont=dict(size=10)),
            xaxis2=_category_xaxis_monthly(dates, tickfont=dict(size=10))
        )
        
        # Convert to JSON using custom encoder
        return json.dumps(fig.to_dict(), cls=NumpyEncoder)
    except Exception as e:
        logger.error(f"Error creating MACD chart: {e}")
        raise

@app.route('/calculate_beta', methods=['POST'])
def calculate_beta():
    """Calculate beta coefficient - NO CHART, single value calculation"""
    try:
        logger.info("Received request to calculate beta coefficient")
        
        # Get form data
        symbol = request.form.get('symbol')
        market_symbol = request.form.get('market_symbol', 'شاخص')
        beta_period = int(request.form.get('beta_period', 1100))  # Default ~1100 trading days
        return_period = int(request.form.get('return_period', 30))  # Default 30 days
        threshold = float(request.form.get('threshold', 20.0))  # Default ±20% band on relative Δ ratio
        price_type = request.form.get('price_type', 'close')
        end_date = request.form.get('end_date')
        timeframe = request.form.get('timeframe', 'daily')
        
        logger.info(f"Parameters: symbol={symbol}, market={market_symbol}")
        logger.info(f"Beta period={beta_period}, return_period={return_period}, threshold={threshold}")
        logger.info(f"Price_type={price_type}, end_date={end_date}, timeframe={timeframe}")
        
        # Validate inputs
        if not all([symbol, end_date]):
            return jsonify({'error': 'نماد و تاریخ پایان الزامی هستند'}), 400
        
        # Validate date
        try:
            end_dt = jdatetime.datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'فرمت تاریخ نامعتبر است'}), 400
        
        # Validate date is not in future
        today = jdatetime.date.today()
        if end_dt.date() > today:
            return jsonify({'error': 'تاریخ نباید از امروز بزرگتر باشد'}), 400

        if threshold <= 0:
            return jsonify({'error': 'آستانه باید بزرگتر از صفر باشد'}), 400
        
        # Calculate lookback (need more data than beta_period for calculation)
        lookback_days = max(beta_period + 50, return_period + 50)
        
        # Calculate start date
        start_date = calculate_start_date(end_date, lookback_days)
        logger.info(f"Calculated start_date: {start_date} (lookback: {lookback_days} days)")
        
        # Fetch stock data
        logger.info("Fetching stock candle data")
        stock_data = data_handler.fetch_daily_candle_data(symbol, start_date, end_date)
        
        if len(stock_data) == 0:
            return jsonify({'error': f'داده‌ای برای سهم {symbol} یافت نشد'}), 404
        
        # Fetch market data (using index-specific function)
        logger.info(f"Fetching market index data for {market_symbol}")
        market_data = data_handler.fetch_index_data(market_symbol, start_date, end_date)
        
        if len(market_data) == 0:
            return jsonify({'error': f'داده‌ای برای شاخص {market_symbol} یافت نشد'}), 404
        
        logger.info(f"Fetched {len(stock_data)} stock rows, {len(market_data)} market rows")
        
        # Convert to weekly/monthly if requested
        if timeframe == 'weekly':
            stock_data = data_handler.aggregate_to_weekly(stock_data)
            market_data = data_handler.aggregate_to_weekly(market_data)
            logger.info(f"Converted to weekly: {len(stock_data)} stock, {len(market_data)} market candles")
        elif timeframe == 'monthly':
            stock_data = data_handler.aggregate_to_monthly(stock_data)
            market_data = data_handler.aggregate_to_monthly(market_data)
            logger.info(f"Converted to monthly: {len(stock_data)} stock, {len(market_data)} market candles")
        
        # Trade-to-trade alignment: keep only stock trading dates that also have market data.
        # Returns are calculated after this merge, so both stock and market use the same date windows.
        stock_data['date_str'] = stock_data['timestamp'].apply(convert_timestamp_to_jalali_date)
        market_data['date_str'] = market_data['timestamp'].apply(convert_timestamp_to_jalali_date)
        
        merged_data = pd.merge(
            stock_data, market_data,
            left_on='date_str', right_on='date_str',
            suffixes=('', '_market')
        ).sort_values('timestamp').reset_index(drop=True)
        
        if len(merged_data) < 2:
            return jsonify({'error': f'داده‌های هم‌تراز کافی نیست. فقط {len(merged_data)} روز پیدا شد'}), 400
        
        logger.info(f"Merged data: {len(merged_data)} rows")
        
        # Prepare stock and market candle data
        stock_aligned = merged_data[['timestamp', 'adjfinal', 'adjopen', 'adjhigh', 'adjlow', 'adjclose']].copy()
        market_aligned = merged_data[['timestamp_market', 'adjfinal_market', 'adjopen_market', 
                                      'adjhigh_market', 'adjlow_market', 'adjclose_market']].copy()
        market_aligned.columns = ['timestamp', 'adjfinal', 'adjopen', 'adjhigh', 'adjlow', 'adjclose']
        
        # Calculate beta indicator (NEW: returns single values, not arrays)
        logger.info("Calculating beta coefficient")
        beta_result = calculations_handler.calculate_indicator_3(
            candle_data=stock_aligned,
            market_candle_data=market_aligned,
            beta_period=beta_period,
            return_period=return_period,
            threshold=threshold,
            price_type=price_type
        )
        
        # Extract results (simple values now, not arrays)
        beta_value = beta_result['beta']
        actual_return = beta_result['actual_return']
        expected_return = beta_result['expected_return']
        market_return = beta_result['market_return']
        return_ratio = beta_result['return_ratio']
        return_delta = beta_result['return_delta']
        delta_ratio_pct = beta_result.get('delta_ratio_pct')
        signal = beta_result['signal']
        signal_color = beta_result['signal_color']
        
        # Prepare statistics
        stats = {
            'symbol': symbol,
            'market_symbol': market_symbol,
            'timeframe': timeframe,
            'beta': {
                'value': beta_value,
                'period_used': beta_result['beta_period_used'],
                'interpretation': beta_result['beta_interpretation']
            },
            'returns': {
                'actual': actual_return,
                'expected': expected_return,
                'market': market_return,
                'delta': return_delta,
                'delta_ratio_pct': delta_ratio_pct,
                'ratio': return_ratio,
                'period_used': beta_result['return_period_used'],
                'method': beta_result['return_method']
            },
            'signal': {
                'status': signal,
                'color': signal_color,
                'threshold': threshold
            },
            'dates': {
                'start': merged_data['date_str'].iloc[0],
                'end': merged_data['date_str'].iloc[-1],
                'total_periods': len(merged_data)
            }
        }
        
        logger.info(f"Beta: {beta_value:.4f}, Signal: {signal}")
        logger.info("Beta calculation completed successfully (NO CHART)")
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Error calculating beta: {e}", exc_info=True)
        return jsonify({'error': f'خطا در محاسبات: {str(e)}'}), 500

def create_beta_chart(stock_data, beta_array, actual_return_array, expected_return_array, 
                     return_difference_array, signal_array, dates, symbol, threshold):
    """Create multi-panel chart for beta coefficient analysis"""
    try:
        from plotly.subplots import make_subplots
        
        # Create subplots: candlestick, beta, returns comparison
        fig = make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.4, 0.3, 0.3],
            subplot_titles=(
                f'نمودار قیمت {symbol}',
                'ضریب بتا (Beta Coefficient)',
                'مقایسه بازده واقعی و مورد انتظار'
            )
        )
        
        # Convert numpy arrays to Python lists to avoid binary encoding
        open_list = stock_data['adjopen'].tolist()
        high_list = stock_data['adjhigh'].tolist()
        low_list = stock_data['adjlow'].tolist()
        close_list = stock_data['adjclose'].tolist()
        beta_list = [None if (isinstance(x, float) and np.isnan(x)) else x for x in beta_array.tolist()] if hasattr(beta_array, 'tolist') else list(beta_array)
        actual_return_list = [None if (isinstance(x, float) and np.isnan(x)) else x for x in actual_return_array.tolist()] if hasattr(actual_return_array, 'tolist') else list(actual_return_array)
        expected_return_list = [None if (isinstance(x, float) and np.isnan(x)) else x for x in expected_return_array.tolist()] if hasattr(expected_return_array, 'tolist') else list(expected_return_array)
        
        # Row 1: Candlestick
        fig.add_trace(
            go.Candlestick(
                x=dates,
                open=open_list,
                high=high_list,
                low=low_list,
                close=close_list,
                name='قیمت',
                increasing_line_color='green',
                decreasing_line_color='red'
            ),
            row=1, col=1
        )
        
        # Row 2: Beta coefficient
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=beta_list,
                mode='lines',
                name='ضریب بتا',
                line=dict(color='blue', width=2)
            ),
            row=2, col=1
        )
        
        # Add beta reference lines
        fig.add_hline(y=1.0, line_dash="dash", line_color="gray", row=2, col=1, 
                     annotation_text="β = 1 (هم‌حرکت با بازار)")
        fig.add_hline(y=0, line_dash="dot", line_color="gray", row=2, col=1)
        
        # Row 3: Returns comparison
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=actual_return_list,
                mode='lines',
                name='بازده واقعی',
                line=dict(color='green', width=2)
            ),
            row=3, col=1
        )
        
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=expected_return_list,
                mode='lines',
                name='بازده مورد انتظار',
                line=dict(color='orange', width=2, dash='dash')
            ),
            row=3, col=1
        )
        
        # Add threshold line
        fig.add_hline(y=threshold, line_dash="dash", line_color="red", row=3, col=1,
                     annotation_text=f"آستانه ({threshold}%)")
        
        # Color background for positive signals
        # Convert numpy array result to Python list
        positive_indices = np.where(signal_array == 1)[0].tolist()
        for idx in positive_indices:
            if idx < len(dates):
                fig.add_vrect(
                    x0=dates[idx], x1=dates[min(idx+1, len(dates)-1)],
                    fillcolor="green", opacity=0.1,
                    layer="below", line_width=0,
                    row=3, col=1
                )
        
        fig.update_layout(
            title=f'تحلیل ضریب بتا - {symbol}',
            xaxis_rangeslider_visible=False,
            hovermode='x unified',
            template='plotly_white',
            height=900,
            showlegend=True,
            xaxis=_category_xaxis_monthly(dates, tickfont=dict(size=10)),
            xaxis2=_category_xaxis_monthly(dates, tickfont=dict(size=10)),
            xaxis3=_category_xaxis_monthly(dates, tickfont=dict(size=10))
        )
        
        # Convert to JSON using custom encoder
        return json.dumps(fig.to_dict(), cls=NumpyEncoder)
    except Exception as e:
        logger.error(f"Error creating beta chart: {e}")
        raise

@app.route('/calculate_volume', methods=['POST'])
def calculate_volume():
    """Calculate trading volume/value indicators with multiple MAs and return charts"""
    try:
        logger.info("Received request to calculate trading volume and value")
        
        # Get form data
        symbol = request.form.get('symbol')
        lookback_days = int(request.form.get('lookback_days'))
        volume_ma_periods_str = request.form.get('volume_ma_periods', '30')
        end_date = request.form.get('end_date')
        timeframe = request.form.get('timeframe', 'daily')
        
        # Parse volume MA periods
        try:
            volume_ma_periods = [int(p.strip()) for p in volume_ma_periods_str.split(',') if p.strip()]
        except:
            return jsonify({'error': 'فرمت دوره‌های میانگین حجم نامعتبر است'}), 400
        
        if len(volume_ma_periods) == 0:
            volume_ma_periods = [30]  # Default

        if len(volume_ma_periods) > 3:
            return jsonify({'error': 'حداکثر ۳ دوره میانگین مجاز است'}), 400
        
        logger.info(f"Parameters: symbol={symbol}, lookback_days={lookback_days}, "
                   f"volume_ma_periods={volume_ma_periods}, end_date={end_date}, timeframe={timeframe}")
        
        # Validate inputs
        if not all([symbol, lookback_days, end_date]):
            return jsonify({'error': 'همه فیلدها الزامی هستند'}), 400
        
        # Validate date format
        try:
            end_dt = jdatetime.datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'فرمت تاریخ نامعتبر است. فرمت صحیح: YYYY-MM-DD'}), 400
        
        # Validate date is not in future
        today = jdatetime.date.today()
        if end_dt.date() > today:
            return jsonify({'error': 'تاریخ انتخابی نباید از امروز بزرگتر باشد'}), 400
        
        # Validate lookback_days and volume_ma_periods
        if lookback_days <= 0:
            return jsonify({'error': 'تعداد روزهای بازگشت باید بزرگتر از صفر باشد'}), 400
        
        for period in volume_ma_periods:
            if period <= 0:
                return jsonify({'error': f'دوره میانگین حجم {period} نامعتبر است'}), 400
            if period > lookback_days:
                return jsonify({'error': f'دوره میانگین حجم {period} نباید بزرگتر از تعداد روزهای بازگشت باشد'}), 400
        
        # Calculate start date
        # We need extra data for moving average calculation
        # Fetch (lookback_days + max_volume_ma_period) days to calculate MA properly
        max_volume_ma = max(volume_ma_periods)
        extended_lookback = lookback_days + max_volume_ma
        start_date = calculate_start_date(end_date, extended_lookback)
        logger.info(f"Calculated start_date: {start_date} (fetching {extended_lookback} days for MA calculation)")
        
        # Fetch daily candle data (with extra days for MA calculation)
        logger.info("Fetching daily candle data")
        daily_data = data_handler.fetch_daily_candle_data(symbol, start_date, end_date)
        
        if len(daily_data) == 0:
            return jsonify({'error': f'داده‌ای برای نماد {symbol} در بازه زمانی انتخابی یافت نشد'}), 404
        
        logger.info(f"Fetched {len(daily_data)} rows of daily data")
        
        # Convert to weekly/monthly if requested (BEFORE trimming)
        if timeframe == 'weekly':
            daily_data = data_handler.aggregate_to_weekly(daily_data)
            logger.info(f"Converted to weekly data: {len(daily_data)} candles")
        elif timeframe == 'monthly':
            daily_data = data_handler.aggregate_to_monthly(daily_data)
            logger.info(f"Converted to monthly data: {len(daily_data)} candles")
        
        # Check if we have enough data
        if len(daily_data) < max_volume_ma:
            return jsonify({'error': f'داده کافی نیست. حداقل {max_volume_ma} روز داده لازم است، {len(daily_data)} روز موجود است'}), 400
        
        # Calculate volume indicator with multiple MAs
        logger.info(f"Calculating trading volume indicator with MAs: {volume_ma_periods}")
        logger.info(f"Total data fetched: {len(daily_data)} periods")
        
        volume_result = calculations_handler.calculate_indicator_4_chart(
            candle_data=daily_data,
            volume_ma_periods=volume_ma_periods,
            volume_field="Volume",
            value_field="Value"
        )
        
        # Extract results (all data)
        volumes_all = volume_result['volumes']
        volume_mas_all = volume_result['volume_mas']  # Dict of {period: array}
        values_all = volume_result['values']
        value_mas_all = volume_result['value_mas']  # Dict of {period: array}
        dates_all = volume_result['dates']
        
        logger.info(f"Volume data calculated for {len(volumes_all)} periods")
        
        # Trim to only show the requested lookback period
        # Calculate how many trading days correspond to max_volume_ma
        total_trading_days = len(volumes_all)
        trading_days_ratio = total_trading_days / extended_lookback
        ma_trading_days = int(max_volume_ma * trading_days_ratio)
        
        logger.info(f"Extended lookback: {extended_lookback} calendar days = {total_trading_days} trading days")
        logger.info(f"Max MA period: {max_volume_ma} calendar days ≈ {ma_trading_days} trading days")
        
        # Trim the first ma_trading_days to remove the extra data used for MA calculation
        if total_trading_days > ma_trading_days:
            display_trading_days = total_trading_days - ma_trading_days
            logger.info(f"Trimming first {ma_trading_days} trading days, showing last {display_trading_days} trading days")
            volumes = volumes_all[ma_trading_days:]
            volume_mas = {period: ma_array[ma_trading_days:] for period, ma_array in volume_mas_all.items()}
            values = values_all[ma_trading_days:]
            value_mas = {period: ma_array[ma_trading_days:] for period, ma_array in value_mas_all.items()}
            dates = dates_all[ma_trading_days:]
            logger.info(f"Chart will show: {len(dates)} periods from {dates[0]} to {dates[-1]}")
        else:
            volumes = volumes_all
            volume_mas = volume_mas_all
            values = values_all
            value_mas = value_mas_all
            dates = dates_all
            logger.info(f"Showing all {len(dates)} periods from {dates[0]} to {dates[-1]}")
        
        # Create charts with trimmed data and multiple MAs
        volume_chart_json = create_volume_chart_multiple_mas(
            volumes=volumes,
            volume_mas=volume_mas,
            dates=dates,
            symbol=symbol,
            timeframe=timeframe,
            metric_name='حجم معاملات',
            ma_label_prefix='میانگین حجم'
        )
        value_chart_json = create_volume_chart_multiple_mas(
            volumes=values,
            volume_mas=value_mas,
            dates=dates,
            symbol=symbol,
            timeframe=timeframe,
            metric_name='ارزش معاملات',
            ma_label_prefix='میانگین ارزش'
        )
        
        # Prepare response statistics — equal-weight vote per volume and value
        latest_volume = float(volumes[-1])
        latest_value = float(values[-1])
        volume_ma_values = {period: float(volume_mas[period][-1]) for period in volume_ma_periods}
        value_ma_values = {period: float(value_mas[period][-1]) for period in volume_ma_periods}

        volume_vote = _compute_metric_vote_signal(latest_volume, volume_mas, volume_ma_periods)
        value_vote = _compute_metric_vote_signal(latest_value, value_mas, volume_ma_periods)

        stats = {
            'total_days': len(dates),
            'start_date': dates[0],
            'end_date': dates[-1],
            'timeframe': timeframe,
            'volume': {
                'avg': float(np.mean(volumes)),
                'max': float(np.max(volumes)),
                'min': float(np.min(volumes)),
                **_build_metric_vote_stats(latest_volume, volume_vote, volume_ma_values),
            },
            'value': {
                'avg': float(np.mean(values)),
                'max': float(np.max(values)),
                'min': float(np.min(values)),
                **_build_metric_vote_stats(latest_value, value_vote, value_ma_values),
            },
        }
        
        logger.info("Trading volume/value calculation completed successfully")
        
        return jsonify({
            'success': True,
            'volume_chart': volume_chart_json,
            'value_chart': value_chart_json,
            'chart': volume_chart_json,  # Backwards-compatible legacy field
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Error calculating trading volume/value: {e}", exc_info=True)
        return jsonify({'error': f'خطا در محاسبات: {str(e)}'}), 500

def create_volume_chart_multiple_mas(volumes, volume_mas, dates, symbol, timeframe='daily', metric_name='حجم معاملات', ma_label_prefix='میانگین'):
    """
    Create volume chart with bars for volume and multiple MA lines
    Args:
        volumes: np.array, volume values
        volume_mas: dict, {period: np.array} for each MA
        dates: list, date strings for x-axis
        symbol: str, stock symbol
        timeframe: str, timeframe (daily/weekly/monthly)
    Returns:
        str: JSON representation of the Plotly figure
    """
    try:
        logger.info(f"Creating volume chart with {len(volume_mas)} MAs")
        
        # Convert numpy arrays to Python lists to avoid binary encoding
        volumes_list = [None if (isinstance(x, float) and np.isnan(x)) else x for x in volumes.tolist()] if hasattr(volumes, 'tolist') else list(volumes)
        
        # Create bar chart for volume
        volume_bars = go.Bar(
            x=dates,
            y=volumes_list,
            name=metric_name,
            marker=dict(
                color=volumes_list,
                colorscale='Blues',
                showscale=True,
                colorbar=dict(title=metric_name)
            ),
            text=volumes_list,
            texttemplate='%{text:.2s}',
            textposition='outside',
            hovertemplate=f'تاریخ: %{{x}}<br>{metric_name}: %{{y:,.0f}}<extra></extra>'
        )
        
        # Create figure data list
        data_traces = [volume_bars]
        
        # Define colors for multiple MAs
        ma_colors = ['#ff4757', '#ffd700', '#00d4ff', '#4ecdc4', '#45b7d1']
        
        # Add MA lines
        for idx, (period, ma_array) in enumerate(sorted(volume_mas.items())):
            ma_list = [None if (isinstance(x, float) and np.isnan(x)) else x for x in ma_array.tolist()] if hasattr(ma_array, 'tolist') else list(ma_array)
            
            ma_line = go.Scatter(
                x=dates,
                y=ma_list,
                mode='lines',
                name=f'{ma_label_prefix} {period} روزه',
                line=dict(color=ma_colors[idx % len(ma_colors)], width=3),
                hovertemplate='تاریخ: %{x}<br>میانگین: %{y:,.0f}<extra></extra>'
            )
            data_traces.append(ma_line)
        
        # Create figure
        fig = go.Figure(data=data_traces)
        
        # Timeframe label
        timeframe_label = {'daily': 'روزانه', 'weekly': 'هفتگی', 'monthly': 'ماهانه'}.get(timeframe, timeframe)

        # Update layout
        fig.update_layout(
            title=f'نمودار {metric_name} {symbol} ({timeframe_label})',
            xaxis_title='تاریخ (شمسی)',
            yaxis_title=metric_name,
            hovermode='x unified',
            template='plotly_white',
            height=600,
            font=dict(family="Tahoma, Arial", size=12),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            xaxis=_category_xaxis_monthly(dates, tickfont=dict(size=10)),
            yaxis=dict(
                gridcolor='lightgray',
                showgrid=True
            ),
            bargap=0.2,
            plot_bgcolor='white'
        )
        
        # Convert to JSON using custom encoder
        graphJSON = json.dumps(fig.to_dict(), cls=NumpyEncoder)
        logger.info("Volume chart with multiple MAs created successfully")
        
        return graphJSON
    except Exception as e:
        logger.error(f"Error creating volume chart: {e}")
        raise

def create_volume_chart(volumes, volume_ma, dates, symbol, volume_ma_period):
    """
    Create volume chart (LEGACY - for backwards compatibility)
    """
    volume_mas = {volume_ma_period: volume_ma}
    return create_volume_chart_multiple_mas(volumes, volume_mas, dates, symbol)

def _compute_metric_vote_signal(current_value, ma_series_by_period, periods):
    """
    Equal-weight vote: compare today's metric to each MA period's latest value.
    Majority of POSITIVE vs NEGATIVE votes wins; tie → NEUTRAL.
    """
    per_ma = {}
    positive_count = 0
    negative_count = 0
    neutral_count = 0

    for period in periods:
        series = ma_series_by_period.get(period)
        if series is None or len(series) == 0:
            per_ma[str(period)] = {'signal': 'NO_DATA', 'ma_value': None, 'difference_pct': None}
            continue
        ma_val = float(series[-1]) if not np.isnan(series[-1]) else None
        if ma_val is None:
            per_ma[str(period)] = {'signal': 'NO_DATA', 'ma_value': None, 'difference_pct': None}
            continue
        diff_pct = ((current_value - ma_val) / ma_val) * 100 if ma_val != 0 else 0.0
        if current_value > ma_val:
            sig = 'POSITIVE'
            positive_count += 1
        elif current_value < ma_val:
            sig = 'NEGATIVE'
            negative_count += 1
        else:
            sig = 'NEUTRAL'
            neutral_count += 1
        per_ma[str(period)] = {
            'signal': sig,
            'ma_value': ma_val,
            'difference_pct': diff_pct,
            'status': 'بالاتر' if current_value > ma_val else 'پایین‌تر' if current_value < ma_val else 'برابر',
        }

    total_votes = positive_count + negative_count + neutral_count
    if total_votes == 0:
        overall_signal = 'NO_DATA'
    elif positive_count > negative_count:
        overall_signal = 'POSITIVE'
    elif negative_count > positive_count:
        overall_signal = 'NEGATIVE'
    else:
        overall_signal = 'NEUTRAL'

    return {
        'signal': overall_signal,
        'positive_count': positive_count,
        'negative_count': negative_count,
        'neutral_count': neutral_count,
        'total_votes': total_votes,
        'per_ma': per_ma,
    }


def _compute_ma_vote_signal(current_price, ma_arrays, ma_periods):
    """Equal-weight vote for price vs each moving average period."""
    return _compute_metric_vote_signal(current_price, ma_arrays, ma_periods)


def _metric_vote_status_text(vote):
    """Human-readable vote summary for volume/value/MA stats panels."""
    if not vote or vote.get('total_votes', 0) == 0:
        return 'در دسترس نیست'
    parts = [f"مثبت: {vote['positive_count']}", f"منفی: {vote['negative_count']}"]
    if vote.get('neutral_count', 0) > 0:
        parts.append(f"خنثی: {vote['neutral_count']}")
    return ' | '.join(parts)


def _build_metric_vote_stats(latest, vote, ma_values):
    """Build stats dict for volume or value with equal-weight MA voting."""
    stats = {
        'latest': float(latest),
        'ma_values': ma_values,
        'vote': vote,
        'signal': vote['signal'],
        'positive_count': vote['positive_count'],
        'negative_count': vote['negative_count'],
        'neutral_count': vote['neutral_count'],
        'total_votes': vote['total_votes'],
        'per_ma': vote['per_ma'],
        'latest_status': _metric_vote_status_text(vote),
    }
    if vote['total_votes'] == 0:
        stats['signal'] = 'NO_DATA'
        stats['latest_diff_pct'] = None
    return stats


@app.route('/calculate_ma', methods=['POST'])
def calculate_ma():
    """Calculate multiple moving averages and return chart"""
    try:
        logger.info("Received request to calculate moving average(s)")
        
        # Get form data
        symbol = request.form.get('symbol')
        lookback_days = int(request.form.get('lookback_days'))
        ma_periods_str = request.form.get('ma_periods')  # Comma-separated string like "20,50,200"
        price_type = request.form.get('price_type')
        end_date = request.form.get('end_date')
        timeframe = request.form.get('timeframe', 'daily')  # daily, weekly, monthly
        
        # Parse MA periods
        try:
            ma_periods = [int(p.strip()) for p in ma_periods_str.split(',') if p.strip()]
        except:
            return jsonify({'error': 'فرمت دوره‌های میانگین متحرک نامعتبر است'}), 400
        
        logger.info(f"Parameters: symbol={symbol}, lookback_days={lookback_days}, "
                   f"ma_periods={ma_periods}, price_type={price_type}, end_date={end_date}, timeframe={timeframe}")
        
        # Validate inputs
        if not all([symbol, lookback_days, ma_periods_str, price_type, end_date]):
            return jsonify({'error': 'همه فیلدها الزامی هستند'}), 400
        
        if len(ma_periods) == 0:
            return jsonify({'error': 'حداقل یک دوره میانگین متحرک باید وارد شود'}), 400

        if len(ma_periods) > 3:
            return jsonify({'error': 'حداکثر ۳ دوره میانگین متحرک مجاز است'}), 400
        
        # Validate date format
        try:
            end_dt = jdatetime.datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'فرمت تاریخ نامعتبر است. فرمت صحیح: YYYY-MM-DD'}), 400
        
        # Validate date is not in future
        today = jdatetime.date.today()
        if end_dt.date() > today:
            return jsonify({'error': 'تاریخ انتخابی نباید از امروز بزرگتر باشد'}), 400
        
        # Validate lookback_days and ma_periods
        if lookback_days <= 0:
            return jsonify({'error': 'تعداد روزهای بازگشت باید بزرگتر از صفر باشد'}), 400
        
        for ma_period in ma_periods:
            if ma_period <= 0:
                return jsonify({'error': f'دوره میانگین متحرک {ma_period} نامعتبر است'}), 400
            if ma_period > lookback_days:
                return jsonify({'error': f'دوره میانگین متحرک {ma_period} نباید بزرگتر از تعداد روزهای بازگشت باشد'}), 400
        
        # Calculate start date
        start_date = calculate_start_date(end_date, lookback_days)
        logger.info(f"Calculated start_date: {start_date}")
        
        # Fetch daily candle data
        logger.info("Fetching daily candle data")
        daily_data = data_handler.fetch_daily_candle_data(symbol, start_date, end_date)
        
        if len(daily_data) == 0:
            return jsonify({'error': f'داده‌ای برای نماد {symbol} در بازه زمانی انتخابی یافت نشد'}), 404
        
        logger.info(f"Fetched {len(daily_data)} rows of daily data")
        
        # Convert to weekly/monthly if requested
        if timeframe == 'weekly':
            daily_data = data_handler.aggregate_to_weekly(daily_data)
            logger.info(f"Converted to weekly data: {len(daily_data)} candles")
        elif timeframe == 'monthly':
            daily_data = data_handler.aggregate_to_monthly(daily_data)
            logger.info(f"Converted to monthly data: {len(daily_data)} candles")
        
        # Calculate moving averages
        logger.info("Calculating moving averages")
        ma_arrays = calculations_handler.calculate_indicator_1(
            candle_data=daily_data,
            ma_periods=ma_periods,
            price_type=price_type
        )
        
        logger.info(f"Moving averages calculated for periods: {list(ma_arrays.keys())}")
        
        # Create chart with multiple MAs
        chart_json = create_candlestick_chart_multiple_mas(
            daily_data=daily_data,
            ma_arrays=ma_arrays,
            symbol=symbol,
            price_type=price_type,
            timeframe=timeframe
        )
        
        # Prepare statistics — equal-weight vote across all MA periods
        current_price = float(daily_data['adjclose'].iloc[-1])
        ma_vote = _compute_ma_vote_signal(current_price, ma_arrays, ma_periods)

        stats = {
            'total_candles': len(daily_data),
            'start_date': convert_timestamp_to_jalali_date(daily_data['timestamp'].iloc[0]),
            'end_date': convert_timestamp_to_jalali_date(daily_data['timestamp'].iloc[-1]),
            'current_price': current_price,
            'timeframe': timeframe,
            'ma_values': {},
            'ma_vote': ma_vote,
            'price_vs_ma': None,
        }

        # Add all MA values
        for period, ma_array in ma_arrays.items():
            stats['ma_values'][period] = float(ma_array[-1]) if not np.isnan(ma_array[-1]) else None

        if ma_vote['total_votes'] > 0:
            stats['price_vs_ma'] = {
                'signal': ma_vote['signal'],
                'positive_count': ma_vote['positive_count'],
                'negative_count': ma_vote['negative_count'],
                'neutral_count': ma_vote['neutral_count'],
                'total_votes': ma_vote['total_votes'],
                'per_ma': ma_vote['per_ma'],
            }
        
        logger.info("Moving average calculation completed successfully")
        
        return jsonify({
            'success': True,
            'chart': chart_json,
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Error calculating moving average: {e}", exc_info=True)
        return jsonify({'error': f'خطا در محاسبات: {str(e)}'}), 500

def _summary_ma_periods(val):
    if not val or not str(val).strip():
        return [20, 50, 100]
    try:
        parts = [int(x.strip()) for x in str(val).split(',') if x.strip()]
        return parts if parts else [20, 50, 100]
    except (ValueError, TypeError):
        return [20, 50, 100]


def _summary_safe_int(val, default):
    if val is None or (isinstance(val, str) and not str(val).strip()):
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _summary_safe_float(val, default):
    if val is None or (isinstance(val, str) and not str(val).strip()):
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _summary_safe_str(val, default):
    s = (val or '').strip()
    return s if s else default


def compute_summary_for_symbol(symbol, end_date, timeframe, params):
    """Run all five summary indicators for one symbol; returns a JSON-serializable dict."""
    summary_results = {}

    # ===== INDICATOR 1: Moving Average =====
    try:
        logger.info("Calculating MA for summary...")
        ma_periods = _summary_ma_periods(params.get('summary_ma_periods'))
        lookback_days = _summary_safe_int(params.get('summary_ma_lookback'), 200)
        price_type = _summary_safe_str(params.get('summary_ma_price_type'), 'close')
        
        start_date = calculate_start_date(end_date, lookback_days)
        daily_data = data_handler.fetch_daily_candle_data(symbol, start_date, end_date)
        
        if timeframe == 'weekly':
            daily_data = data_handler.aggregate_to_weekly(daily_data)
        elif timeframe == 'monthly':
            daily_data = data_handler.aggregate_to_monthly(daily_data)
        
        if len(daily_data) > 0:
            ma_arrays = calculations_handler.calculate_indicator_1(daily_data, ma_periods, price_type)
            current_price = float(daily_data['adjclose'].iloc[-1])
            ma_vote = _compute_ma_vote_signal(current_price, ma_arrays, ma_periods)

            summary_results['ma'] = {
                'signal': ma_vote['signal'],
                'current_price': current_price,
                'positive_count': ma_vote['positive_count'],
                'negative_count': ma_vote['negative_count'],
                'neutral_count': ma_vote['neutral_count'],
                'total_votes': ma_vote['total_votes'],
                'per_ma': ma_vote['per_ma'],
                'ma_values': {
                    str(p): ma_vote['per_ma'].get(str(p), {}).get('ma_value')
                    for p in ma_periods
                },
            }
        else:
            summary_results['ma'] = {'signal': 'NO_DATA', 'error': 'داده کافی نیست'}
    except Exception as e:
        logger.error(f"Error in MA summary: {e}")
        summary_results['ma'] = {'signal': 'ERROR', 'error': str(e)}
    
    # ===== INDICATOR 2: Divergence =====
    try:
        logger.info("Calculating Divergence for summary...")
        lookback = _summary_safe_int(params.get('summary_div_lookback'), 60)
        div_rsi_period = _summary_safe_int(params.get('summary_div_rsi_period'), 14)
        div_rsi_overbought = _summary_safe_int(params.get('summary_div_rsi_overbought'), 70)
        div_rsi_oversold = _summary_safe_int(params.get('summary_div_rsi_oversold'), 30)
        div_macd_short = _summary_safe_int(params.get('summary_div_macd_short'), 12)
        div_macd_long = _summary_safe_int(params.get('summary_div_macd_long'), 26)
        div_macd_signal = _summary_safe_int(params.get('summary_div_macd_signal'), 9)
        div_mfi_period = _summary_safe_int(params.get('summary_div_mfi_period'), 14)
        div_mfi_overbought = _summary_safe_int(params.get('summary_div_mfi_overbought'), 80)
        div_mfi_oversold = _summary_safe_int(params.get('summary_div_mfi_oversold'), 20)
        div_price_type = _summary_safe_str(params.get('summary_div_price_type'), 'close')
        div_price_mode = _summary_safe_str(params.get('summary_divergence_price_mode'), 'high_low')
        div_alignment_tol = _summary_safe_int(params.get('summary_div_alignment_tol'), 3)
        if div_alignment_tol < 0 or div_alignment_tol > 60:
            div_alignment_tol = 3
        start_date = calculate_start_date(end_date, lookback + 50)
        daily_data = data_handler.fetch_daily_candle_data(symbol, start_date, end_date)
        
        if timeframe == 'weekly':
            daily_data = data_handler.aggregate_to_weekly(daily_data)
        elif timeframe == 'monthly':
            daily_data = data_handler.aggregate_to_monthly(daily_data)
        
        if len(daily_data) >= 50:
            div_result = calculations_handler.calculate_indicator_2(
                daily_data, rsi_period=div_rsi_period, rsi_overbought=div_rsi_overbought,
                rsi_oversold=div_rsi_oversold, macd_short=div_macd_short, macd_long=div_macd_long,
                macd_signal=div_macd_signal, mfi_period=div_mfi_period,
                mfi_overbought=div_mfi_overbought, mfi_oversold=div_mfi_oversold,
                lookback=lookback, price_type=div_price_type,
                divergence_price_mode=div_price_mode,
                alignment_tol=div_alignment_tol
            )

            timestamps = daily_data['timestamp'].values
            end_timestamp = int(np.max(timestamps))

            rsi_recent = get_recent_divergence_counts(div_result['rsi_divergence'], timestamps, end_timestamp, valid_days=21, lookback_window=lookback)
            macd_recent = get_recent_divergence_counts(div_result['macd_divergence'], timestamps, end_timestamp, valid_days=21, lookback_window=lookback)
            mfi_recent = get_recent_divergence_counts(div_result['mfi_divergence'], timestamps, end_timestamp, valid_days=21, lookback_window=lookback)

            total_bullish = rsi_recent['bullish_total'] + macd_recent['bullish_total'] + mfi_recent['bullish_total']
            total_bearish = rsi_recent['bearish_total'] + macd_recent['bearish_total'] + mfi_recent['bearish_total']

            if total_bullish == 0 and total_bearish == 0:
                divergence_signal = 'NEUTRAL'
            elif total_bullish > total_bearish:
                divergence_signal = 'POSITIVE'
            elif total_bearish > total_bullish:
                divergence_signal = 'NEGATIVE'
            else:
                divergence_signal = 'NEUTRAL'

            summary_results['divergence'] = {
                'signal': divergence_signal,
                'rsi': {'bullish': rsi_recent['bullish_total'], 'bearish': rsi_recent['bearish_total']},
                'macd': {'bullish': macd_recent['bullish_total'], 'bearish': macd_recent['bearish_total']},
                'mfi': {'bullish': mfi_recent['bullish_total'], 'bearish': mfi_recent['bearish_total']},
                'total_bullish': total_bullish,
                'total_bearish': total_bearish,
                'signal_window_days': 21,
                'divergence_price_mode': div_price_mode,
                'alignment_tol': div_alignment_tol
            }
        else:
            summary_results['divergence'] = {'signal': 'NO_DATA', 'error': 'داده کافی نیست'}
    except Exception as e:
        logger.error(f"Error in Divergence summary: {e}")
        summary_results['divergence'] = {'signal': 'ERROR', 'error': str(e)}
    
    # ===== INDICATOR 3: Beta Coefficient =====
    try:
        logger.info("Calculating Beta for summary...")
        beta_period = _summary_safe_int(params.get('summary_beta_period'), 1100)
        return_period = _summary_safe_int(params.get('summary_beta_return_period'), 30)
        beta_threshold = _summary_safe_float(params.get('summary_beta_threshold'), 20.0)
        beta_market_symbol = _summary_safe_str(params.get('summary_beta_market_symbol'), 'شاخص')
        beta_price_type = _summary_safe_str(params.get('summary_beta_price_type'), 'close')
        
        lookback = max(beta_period, return_period) + 50
        start_date = calculate_start_date(end_date, lookback)
        stock_data = data_handler.fetch_daily_candle_data(symbol, start_date, end_date)
        market_data = data_handler.fetch_index_data(beta_market_symbol, start_date, end_date)
        
        if timeframe == 'weekly':
            stock_data = data_handler.aggregate_to_weekly(stock_data)
            market_data = data_handler.aggregate_to_weekly(market_data)
        elif timeframe == 'monthly':
            stock_data = data_handler.aggregate_to_monthly(stock_data)
            market_data = data_handler.aggregate_to_monthly(market_data)
        
        if len(stock_data) > 0 and len(market_data) > 0:
            # Trade-to-trade alignment: calculate stock and market returns over the same date windows.
            stock_data['date_str'] = stock_data['timestamp'].apply(convert_timestamp_to_jalali_date)
            market_data['date_str'] = market_data['timestamp'].apply(convert_timestamp_to_jalali_date)
            
            merged = pd.merge(stock_data, market_data, on='date_str', suffixes=('', '_market'))
            merged = merged.sort_values('timestamp').reset_index(drop=True)
            
            if len(merged) >= 2:
                stock_aligned = merged[['timestamp', 'adjfinal', 'adjopen', 'adjhigh', 'adjlow', 'adjclose']].copy()
                market_aligned = merged[['timestamp_market', 'adjfinal_market', 'adjopen_market',
                                        'adjhigh_market', 'adjlow_market', 'adjclose_market']].copy()
                market_aligned.columns = ['timestamp', 'adjfinal', 'adjopen', 'adjhigh', 'adjlow', 'adjclose']
                
                beta_result = calculations_handler.calculate_indicator_3(
                    stock_aligned, market_aligned, beta_period, return_period,
                    threshold=beta_threshold, price_type=beta_price_type
                )
                
                summary_results['beta'] = {
                    'signal': beta_result['signal'],
                    'beta_value': beta_result['beta'],
                    'return_delta': beta_result['return_delta'],
                    'delta_ratio_pct': beta_result.get('delta_ratio_pct'),
                    'return_ratio': beta_result['return_ratio'],
                    'interpretation': beta_result['beta_interpretation']
                }
            else:
                summary_results['beta'] = {'signal': 'NO_DATA', 'error': 'داده هم‌تراز کافی نیست'}
        else:
            summary_results['beta'] = {'signal': 'NO_DATA', 'error': 'داده کافی نیست'}
    except Exception as e:
        logger.error(f"Error in Beta summary: {e}")
        summary_results['beta'] = {'signal': 'ERROR', 'error': str(e)}
    
    # ===== INDICATOR 4: Volume =====
    try:
        logger.info("Calculating Volume for summary...")
        volume_ma_periods = _summary_ma_periods(params.get('summary_vol_ma_periods'))
        lookback = _summary_safe_int(params.get('summary_vol_lookback'), 200)
        
        start_date = calculate_start_date(end_date, lookback + (volume_ma_periods[0] if volume_ma_periods else 20))
        daily_data = data_handler.fetch_daily_candle_data(symbol, start_date, end_date)
        
        if timeframe == 'weekly':
            daily_data = data_handler.aggregate_to_weekly(daily_data)
        elif timeframe == 'monthly':
            daily_data = data_handler.aggregate_to_monthly(daily_data)
        
        if len(daily_data) > 0:
            vol_result = calculations_handler.calculate_indicator_4_chart(
                daily_data, volume_ma_periods, 'Volume', 'Value'
            )

            latest_volume = float(vol_result['volumes'][-1])
            latest_value = float(vol_result['values'][-1])
            volume_ma_values = {
                period: float(vol_result['volume_mas'][period][-1]) for period in volume_ma_periods
            }
            value_ma_values = {
                period: float(vol_result['value_mas'][period][-1]) for period in volume_ma_periods
            }
            volume_vote = _compute_metric_vote_signal(
                latest_volume, vol_result['volume_mas'], volume_ma_periods
            )
            value_vote = _compute_metric_vote_signal(
                latest_value, vol_result['value_mas'], volume_ma_periods
            )

            summary_results['volume'] = {
                'signal': volume_vote['signal'],
                'current_volume': latest_volume,
                'positive_count': volume_vote['positive_count'],
                'negative_count': volume_vote['negative_count'],
                'neutral_count': volume_vote['neutral_count'],
                'total_votes': volume_vote['total_votes'],
                'per_ma': volume_vote['per_ma'],
                'ma_values': volume_ma_values,
                'status': _metric_vote_status_text(volume_vote),
            }
            summary_results['value'] = {
                'signal': value_vote['signal'],
                'current_value': latest_value,
                'positive_count': value_vote['positive_count'],
                'negative_count': value_vote['negative_count'],
                'neutral_count': value_vote['neutral_count'],
                'total_votes': value_vote['total_votes'],
                'per_ma': value_vote['per_ma'],
                'ma_values': value_ma_values,
                'status': _metric_vote_status_text(value_vote),
            }
        else:
            summary_results['volume'] = {'signal': 'NO_DATA', 'error': 'داده کافی نیست'}
            summary_results['value'] = {'signal': 'NO_DATA', 'error': 'داده کافی نیست'}
    except Exception as e:
        logger.error(f"Error in Volume summary: {e}")
        summary_results['volume'] = {'signal': 'ERROR', 'error': str(e)}
        summary_results['value'] = {'signal': 'ERROR', 'error': str(e)}
    
    # ===== INDICATOR 5: Real Money Flow =====
    try:
        logger.info("Calculating RMF for summary...")
        lookback = _summary_safe_int(params.get('summary_rmf_lookback'), 30)
        power_ma_period = _summary_safe_int(params.get('summary_rmf_power_ma_period'), 20)
        
        start_date_rmf = calculate_start_date(end_date, lookback)
        rmf_data = data_handler.fetch_client_types_data(symbol, start_date_rmf, end_date)
        
        if len(rmf_data) >= 2:
            # Convert numeric client-type columns (summary path must match tab 5 behavior)
            numeric_cols = ['individual_buy_count', 'individual_sell_count',
                           'individual_buy_value', 'individual_sell_value',
                           'individual_buy_vol', 'individual_sell_vol',
                           'corporate_buy_count', 'corporate_sell_count',
                           'corporate_buy_value', 'corporate_sell_value']

            for col in numeric_cols:
                if col in rmf_data.columns:
                    rmf_data[col] = pd.to_numeric(rmf_data[col], errors='coerce')

            rmf_result = calculations_handler.calculate_indicator_5_simple(rmf_data, power_ma_period)
            
            summary_results['rmf'] = {
                'signal': rmf_result['overall_signal'],
                'buyer_power': rmf_result['current']['buyer_power'],
                'weighted_avg': rmf_result['moving_averages']['buyer_power_ma'],
                'ranking': f"Power: {rmf_result['current']['buyer_power']:.2f}",
                'color': rmf_result['overall_color']
            }
        else:
            summary_results['rmf'] = {'signal': 'NO_DATA', 'error': 'داده کافی نیست'}
    except Exception as e:
        logger.error(f"Error in RMF summary: {e}")
        summary_results['rmf'] = {'signal': 'ERROR', 'error': str(e)}
    
    
    signals = []
    for indicator, result in summary_results.items():
        sig = result.get('signal')
        if sig == 'POSITIVE':
            signals.append(1)
        elif sig == 'NEGATIVE':
            signals.append(-1)

    if len(signals) > 0:
        overall_score = sum(signals)
        if overall_score > 0:
            overall_signal = 'POSITIVE'
            overall_color = 'GREEN'
        elif overall_score < 0:
            overall_signal = 'NEGATIVE'
            overall_color = 'RED'
        else:
            overall_signal = 'NEUTRAL'
            overall_color = 'YELLOW'
    else:
        overall_signal = 'NO_DATA'
        overall_color = 'GRAY'

    logger.info(f"Summary calculation completed. Overall: {overall_signal}")

    return {
        'success': True,
        'symbol': symbol,
        'end_date': end_date,
        'timeframe': timeframe,
        'indicators': summary_results,
        'overall': {
            'signal': overall_signal,
            'color': overall_color,
            'positive_count': signals.count(1),
            'negative_count': signals.count(-1),
            'total_count': len(signals),
        },
    }


def _watchlist_row_from_summary(data):
    """Map a successful compute_summary_for_symbol result to a watchlist table row."""
    symbol = data.get('symbol', '')
    indicators = data.get('indicators', {})
    ma_data = indicators.get('ma', {})
    div_data = indicators.get('divergence', {})
    beta_data = indicators.get('beta', {})
    vol_data = indicators.get('volume', {})
    val_data = indicators.get('value', {})
    rmf_data = indicators.get('rmf', {})
    overall_data = data.get('overall', {})
    return {
        'symbol': symbol,
        'ma': ma_data.get('signal', 'NO_DATA'),
        'ma_detail': (
            f"مثبت:{ma_data.get('positive_count', 0)} | منفی:{ma_data.get('negative_count', 0)}"
            if 'positive_count' in ma_data and 'negative_count' in ma_data
            else (
                f"Δ%: {ma_data.get('difference_pct', 0):.2f}"
                if isinstance(ma_data.get('difference_pct'), (int, float))
                else (ma_data.get('error') or 'بدون داده')
            )
        ),
        'divergence': div_data.get('signal', 'NO_DATA'),
        'divergence_detail': f"صعودی:{div_data.get('total_bullish', 0)} | نزولی:{div_data.get('total_bearish', 0)}" if ('total_bullish' in div_data and 'total_bearish' in div_data) else (div_data.get('error') or 'بدون داده'),
        'beta': beta_data.get('signal', 'NO_DATA'),
        'beta_detail': (
            f"نسبت Δ:{beta_data.get('delta_ratio_pct', 0):.1f}% | بتا:{beta_data.get('beta_value', 0):.2f}"
            if isinstance(beta_data.get('delta_ratio_pct'), (int, float))
            and isinstance(beta_data.get('beta_value'), (int, float))
            else (
                f"بتا:{beta_data.get('beta_value', 0):.2f} | Δ%:{beta_data.get('return_delta', 0):.2f}"
                if isinstance(beta_data.get('beta_value'), (int, float))
                and isinstance(beta_data.get('return_delta'), (int, float))
                else (beta_data.get('error') or 'بدون داده')
            )
        ),
        'volume': vol_data.get('signal', 'NO_DATA'),
        'volume_detail': (
            f"مثبت:{vol_data.get('positive_count', 0)} | منفی:{vol_data.get('negative_count', 0)}"
            if 'positive_count' in vol_data and 'negative_count' in vol_data
            else (
                f"Δ%: {vol_data.get('difference_pct', 0):.2f}"
                if isinstance(vol_data.get('difference_pct'), (int, float))
                else (vol_data.get('error') or 'بدون داده')
            )
        ),
        'value': val_data.get('signal', 'NO_DATA'),
        'value_detail': (
            f"مثبت:{val_data.get('positive_count', 0)} | منفی:{val_data.get('negative_count', 0)}"
            if 'positive_count' in val_data and 'negative_count' in val_data
            else (
                f"Δ%: {val_data.get('difference_pct', 0):.2f}"
                if isinstance(val_data.get('difference_pct'), (int, float))
                else (val_data.get('error') or 'بدون داده')
            )
        ),
        'rmf': rmf_data.get('signal', 'NO_DATA'),
        'rmf_detail': f"قدرت:{rmf_data.get('buyer_power', 0):.2f} | میانگین:{rmf_data.get('weighted_avg', 0):.2f}" if isinstance(rmf_data.get('buyer_power'), (int, float)) and isinstance(rmf_data.get('weighted_avg'), (int, float)) else (rmf_data.get('error') or 'بدون داده'),
        'overall': overall_data.get('signal', 'NO_DATA'),
        'overall_detail': f"مثبت:{overall_data.get('positive_count', 0)} | منفی:{overall_data.get('negative_count', 0)}",
    }


def _watchlist_row_error(symbol, detail='خطا در محاسبه'):
    return {
        'symbol': symbol,
        'ma': 'ERROR',
        'ma_detail': detail,
        'divergence': 'ERROR',
        'divergence_detail': detail,
        'beta': 'ERROR',
        'beta_detail': detail,
        'volume': 'ERROR',
        'volume_detail': detail,
        'value': 'ERROR',
        'value_detail': detail,
        'rmf': 'ERROR',
        'rmf_detail': detail,
        'overall': 'ERROR',
        'overall_detail': detail,
    }


@app.route('/calculate_summary', methods=['POST'])
def calculate_summary():
    """Calculate summary of all 5 indicators for a single symbol."""
    try:
        logger.info("Received request for summary dashboard")
        symbol = request.form.get('symbol')
        end_date = request.form.get('end_date', get_today_jalali())
        timeframe = request.form.get('timeframe', 'daily')
        logger.info(f"Summary for: symbol={symbol}, end_date={end_date}, timeframe={timeframe}")
        if not symbol:
            return jsonify({'error': 'نماد الزامی است'}), 400
        try:
            end_dt = jdatetime.datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'فرمت تاریخ نامعتبر است'}), 400
        today = jdatetime.date.today()
        if end_dt.date() > today:
            return jsonify({'error': 'تاریخ نباید از امروز بزرگتر باشد'}), 400
        result = compute_summary_for_symbol(symbol, end_date, timeframe, request.form)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error calculating summary: {e}", exc_info=True)
        return jsonify({'error': f'خطا در محاسبات: {str(e)}'}), 500

@app.route('/summary_watchlist', methods=['GET'])
def get_summary_watchlist():
    """Get persistent summary watchlist symbols and cached table rows."""
    try:
        watchlist_file, table_file = _summary_watchlist_files()
        watchlist_data = _read_json_file(watchlist_file, {'symbols': []})
        table_cache = _read_json_file(table_file, {'rows': [], 'updated_at': None, 'end_date': None, 'timeframe': None})
        return jsonify({
            'success': True,
            'symbols': watchlist_data.get('symbols', []),
            'table': table_cache
        })
    except Exception as e:
        logger.error(f"Error reading summary watchlist: {e}", exc_info=True)
        return jsonify({'error': f'خطا در دریافت واچ‌لیست: {str(e)}'}), 500

@app.route('/summary_watchlist/add', methods=['POST'])
def add_summary_watchlist_symbol():
    """Add a symbol to persistent summary watchlist and reconcile cached table rows."""
    try:
        symbol = (request.form.get('symbol') or '').strip()
        if not symbol:
            return jsonify({'error': 'نماد الزامی است'}), 400

        watchlist_file, table_file = _summary_watchlist_files()
        watchlist_data = _read_json_file(watchlist_file, {'symbols': []})
        symbols = watchlist_data.get('symbols', [])

        if symbol not in symbols:
            symbols.append(symbol)
            watchlist_data['symbols'] = symbols
            _write_json_file(watchlist_file, watchlist_data)

        table_cache = _read_json_file(table_file, {'rows': [], 'updated_at': None, 'end_date': None, 'timeframe': None})
        table_cache = _reconcile_summary_watchlist_table_cache(table_cache, watchlist_data['symbols'])
        _write_json_file(table_file, table_cache)

        return jsonify({
            'success': True,
            'symbols': watchlist_data['symbols'],
            'table': table_cache,
        })
    except Exception as e:
        logger.error(f"Error adding summary watchlist symbol: {e}", exc_info=True)
        return jsonify({'error': f'خطا در افزودن نماد: {str(e)}'}), 500

@app.route('/summary_watchlist/remove', methods=['POST'])
def remove_summary_watchlist_symbol():
    """Remove a symbol from persistent summary watchlist."""
    try:
        symbol = (request.form.get('symbol') or '').strip()
        if not symbol:
            return jsonify({'error': 'نماد الزامی است'}), 400

        watchlist_file, table_file = _summary_watchlist_files()
        watchlist_data = _read_json_file(watchlist_file, {'symbols': []})
        symbols = [s for s in watchlist_data.get('symbols', []) if s != symbol]
        watchlist_data['symbols'] = symbols
        _write_json_file(watchlist_file, watchlist_data)

        # Remove stale row from cached table as well
        table_cache = _read_json_file(table_file, {'rows': [], 'updated_at': None, 'end_date': None, 'timeframe': None})
        rows = [r for r in table_cache.get('rows', []) if r.get('symbol') != symbol]
        table_cache['rows'] = rows
        _write_json_file(table_file, table_cache)

        return jsonify({'success': True, 'symbols': symbols})
    except Exception as e:
        logger.error(f"Error removing summary watchlist symbol: {e}", exc_info=True)
        return jsonify({'error': f'خطا در حذف نماد: {str(e)}'}), 500

@app.route('/calculate_summary_watchlist', methods=['POST'])
def calculate_summary_watchlist():
    """
    Calculate summary dashboard for all symbols in watchlist and return table rows.
    Reuses existing /calculate_summary behavior per symbol to preserve logic.
    """
    try:
        end_date = request.form.get('end_date', get_today_jalali())
        timeframe = request.form.get('timeframe', 'daily')

        # Validate date
        try:
            end_dt = jdatetime.datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'فرمت تاریخ نامعتبر است'}), 400
        today = jdatetime.date.today()
        if end_dt.date() > today:
            return jsonify({'error': 'تاریخ نباید از امروز بزرگتر باشد'}), 400

        watchlist_file, table_file = _summary_watchlist_files()
        watchlist_data = _read_json_file(watchlist_file, {'symbols': []})
        symbols = watchlist_data.get('symbols', [])

        if len(symbols) == 0:
            return jsonify({'error': 'واچ‌لیست خالی است. ابتدا نماد اضافه کنید.'}), 400

        rows = []
        for symbol in symbols:
            try:
                result = compute_summary_for_symbol(symbol, end_date, timeframe, request.form)
                if not result.get('success'):
                    logger.warning('Summary watchlist: compute failed for %s: %s', symbol, result)
                    rows.append(_watchlist_row_error(symbol))
                    continue
                rows.append(_watchlist_row_from_summary(result))
            except Exception as sym_err:
                logger.warning('Summary watchlist: exception for %s: %s', symbol, sym_err, exc_info=True)
                rows.append(_watchlist_row_error(symbol))

        table_cache = {
            'rows': rows,
            'updated_at': jdatetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'end_date': end_date,
            'timeframe': timeframe
        }
        _write_json_file(table_file, table_cache)

        return jsonify({
            'success': True,
            'symbols': symbols,
            'table': table_cache
        })
    except Exception as e:
        logger.error(f"Error calculating summary watchlist: {e}", exc_info=True)
        return jsonify({'error': f'خطا در محاسبه واچ‌لیست: {str(e)}'}), 500

@app.route('/get_available_symbols', methods=['GET'])
def get_available_symbols():
    """Get list of available symbols for Real Money Flow (from config focused_symbols)."""
    try:
        logger.info("Request for available symbols")
        symbols = list(data_config.get('focused_symbols', []))
        logger.info(f"Returning {len(symbols)} symbols from config")
        return jsonify({
            'success': True,
            'count': len(symbols),
            'symbols': sorted(symbols)
        })
    except Exception as e:
        logger.error(f"Error getting available symbols: {e}")
        return jsonify({'error': f'خطا: {str(e)}'}), 500

@app.route('/calculate_real_money_flow', methods=['POST'])
def calculate_real_money_flow():
    """Calculate Real Money Flow indicator with 3 separate signals and return results"""
    try:
        logger.info("Received request to calculate real money flow")
        
        # Get form data
        symbol = request.form.get('symbol')
        lookback_days = int(request.form.get('lookback_days', 30))
        power_ma_period = int(request.form.get('power_ma_period', 20))
        suite_ma_periods_str = request.form.get('suite_ma_periods', '5,10,20')
        end_date = request.form.get('end_date')
        timeframe = request.form.get('timeframe', 'daily')
        
        logger.info(f"Parameters: symbol={symbol}, lookback_days={lookback_days}, "
                   f"power_ma_period={power_ma_period}, end_date={end_date}, timeframe={timeframe}")
        
        # Validate inputs
        if not all([symbol, end_date]):
            return jsonify({'error': 'همه فیلدها الزامی هستند'}), 400
        
        # Validate date format
        try:
            end_dt = jdatetime.datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'فرمت تاریخ نامعتبر است. فرمت صحیح: YYYY-MM-DD'}), 400
        
        # Validate date is not in future
        today = jdatetime.date.today()
        if end_dt.date() > today:
            return jsonify({'error': 'تاریخ انتخابی نباید از امروز بزرگتر باشد'}), 400
        
        # Fetch data from database first, then pytse_client if needed (WITH CACHING!)
        logger.info(f"Fetching Real Money Flow data for {symbol}")
        
        # Calculate date range in Gregorian (pytse_client uses Gregorian dates)
        start_date_jalali = calculate_start_date(end_date, lookback_days)
        
        try:
            # Use data_handler which has database caching!
            rmf_df = data_handler.fetch_client_types_data(symbol, start_date_jalali, end_date)
            
            if rmf_df is None or len(rmf_df) == 0:
                return jsonify({'error': f'داده‌ای برای نماد "{symbol}" یافت نشد. این نماد ممکن است در pytse_client موجود نباشد.'}), 404
            
            logger.info(f"✓ Fetched {len(rmf_df)} rows (from database or API)")
            logger.info(f"Columns: {list(rmf_df.columns)}")
            
            # Ensure date column exists
            if 'date' not in rmf_df.columns:
                rmf_df = rmf_df.reset_index()
                if 'index' in rmf_df.columns:
                    rmf_df = rmf_df.rename(columns={'index': 'date'})
            
        except Exception as e:
            logger.error(f"Error fetching client types data: {e}", exc_info=True)
            return jsonify({'error': f'خطا در دریافت داده‌ها: {str(e)}'}), 500
        
        # Data already has Jalali dates and is filtered
        logger.info(f"Data range: {start_date_jalali} to {end_date}, {len(rmf_df)} rows")
        
        if len(rmf_df) < 2:
            return jsonify({'error': f'داده کافی نیست. {len(rmf_df)} روز یافت شد، حداقل 2 روز لازم است'}), 400
        
        # Convert numeric columns from string to numbers
        logger.info("Converting numeric columns to proper types")
        numeric_cols = ['individual_buy_count', 'individual_sell_count', 
                       'individual_buy_value', 'individual_sell_value',
                       'individual_buy_vol', 'individual_sell_vol',
                       'corporate_buy_count', 'corporate_sell_count',
                       'corporate_buy_value', 'corporate_sell_value']
        
        for col in numeric_cols:
            if col in rmf_df.columns:
                rmf_df[col] = pd.to_numeric(rmf_df[col], errors='coerce')
        
        logger.info("Numeric conversion completed")

        # Parse RMF suite MA periods (up to 3 user-defined periods)
        try:
            suite_ma_periods = [int(p.strip()) for p in suite_ma_periods_str.split(',') if p.strip()]
        except Exception:
            return jsonify({'error': 'فرمت دوره‌های میانگین RMF نامعتبر است'}), 400

        if len(suite_ma_periods) == 0:
            suite_ma_periods = [5, 10, 20]
        if len(suite_ma_periods) > 3:
            return jsonify({'error': 'حداکثر 3 دوره میانگین برای RMF مجاز است'}), 400
        for period in suite_ma_periods:
            if period <= 0:
                return jsonify({'error': f'دوره میانگین {period} نامعتبر است'}), 400
        
        # Calculate Real Money Flow indicator (using SIMPLE calculation method with 3 signals)
        logger.info("Calculating Real Money Flow indicator")
        rmf_result = calculations_handler.calculate_indicator_5_simple(
            rmf_data=rmf_df,
            ma_period=power_ma_period
        )
        
        logger.info("Real Money Flow calculation completed successfully")
        
        # Build latest_day for frontend (matches expected property names)
        cur = rmf_result['current']
        latest_day = {
            'real_buy_value': cur['buy_value'],
            'real_sell_value': cur['sell_value'],
            'real_buy_count': cur['individual_buy_count'],
            'real_sell_count': cur['individual_sell_count'],
            'real_buy_basket': cur['buy_per_capita'],
            'real_sell_basket': cur['sell_per_capita'],
            'buyer_power': cur['buyer_power']
        }
        
        # Expose all 3 MAs for "value vs MA" display in UI
        moving_averages = {
            'buyer_power_ma': rmf_result['moving_averages']['buyer_power_ma'],
            'buy_value_ma': rmf_result['moving_averages']['buy_value_ma'],
            'sell_value_ma': rmf_result['moving_averages']['sell_value_ma']
        }

        # RMF Indicator Suite (Raw/PerCapita/Normalized) - additive for charting
        rmf_suite = calculations_handler.calculate_indicator_5_suite(
            rmf_data=rmf_df,
            ma_periods=suite_ma_periods
        )
        rmf_dates = rmf_df['date'].tolist()
        rmf_flow_charts = create_rmf_flow_charts(
            dates=rmf_dates,
            suite_result=rmf_suite,
            symbol=symbol,
            ma_periods=suite_ma_periods
        )

        rmf_price_chart = None
        try:
            daily_price_data = data_handler.fetch_daily_candle_data(symbol, start_date_jalali, end_date)
            if daily_price_data is not None and len(daily_price_data) > 0:
                rmf_price_chart = create_rmf_price_chart(daily_price_data, symbol, rmf_dates)
        except Exception as price_err:
            logger.warning(f"Could not build RMF price chart for {symbol}: {price_err}")
        
        return jsonify({
            'success': True,
            'current_power': rmf_result['current']['buyer_power'],
            'weighted_avg_power': rmf_result['moving_averages']['buyer_power_ma'],
            'signal': rmf_result['overall_signal'],
            'signal_color': rmf_result['overall_color'],
            'signals': rmf_result['signals'],  # Individual signals for buyer_power, buy_value, sell_value
            'signal_interpretations': rmf_result['signal_interpretations'],  # Text interpretations
            'ranking': 'See signals for details',
            'ranking_class': 'varies',
            'latest_day': latest_day,
            'moving_averages': moving_averages,
            'rmf_price_chart': rmf_price_chart,
            'rmf_flow_charts': rmf_flow_charts,
            'rmf_suite_ma_periods': suite_ma_periods,
            'daily_metrics': rmf_result['daily_data'],
            'statistics': rmf_result['statistics']
        })
        
    except Exception as e:
        logger.error(f"Error calculating real money flow: {e}", exc_info=True)
        return jsonify({'error': f'خطا در محاسبات: {str(e)}'}), 500

# ========================================================
# Run Application
# ========================================================
def _warn_if_default_secrets():
    """Log warnings when production-sensitive defaults are still in use."""
    if app.config['SECRET_KEY'] == 'faraz-energy-dev-secret-change-for-production':
        logger.warning(
            "FLASK_SECRET_KEY is not set — using insecure default. "
            "Set FLASK_SECRET_KEY in the environment before deployment."
        )
    if app.config['LOGIN_USERNAME'] == 'admin' and app.config['LOGIN_PASSWORD'] == 'admin':
        logger.warning(
            "Default login admin/admin is active. "
            "Set APP_LOGIN_USERNAME and APP_LOGIN_PASSWORD for deployment."
        )


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Faraz Energy — Iran Stock Exchange Signaling Web Application'
    )
    parser.add_argument(
        '--production',
        action='store_true',
        help='Run with Waitress WSGI server (use this on the company deployment PC)',
    )
    parser.add_argument(
        '--host',
        default=os.environ.get('APP_HOST', '0.0.0.0'),
        help='Bind address (0.0.0.0 = all LAN interfaces)',
    )
    parser.add_argument(
        '--port',
        type=int,
        default=int(os.environ.get('APP_PORT', '5001')),
        help='TCP port (default 5001)',
    )
    parser.add_argument(
        '--threads',
        type=int,
        default=int(os.environ.get('WAITRESS_THREADS', '8')),
        help='Waitress worker threads (production only)',
    )
    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("Faraz Energy Project - Technical Analysis Web Application")
    logger.info("=" * 80)
    _warn_if_default_secrets()

    if args.production:
        try:
            from waitress import serve
        except ImportError as e:
            logger.error(
                "Waitress is not installed. Run: pip install waitress "
                "(or pip install -r requirements_exact.txt)"
            )
            raise SystemExit(1) from e
        logger.info("Mode: PRODUCTION (Waitress)")
        logger.info("Access from this PC: http://127.0.0.1:%s", args.port)
        logger.info("Access from LAN:     http://<SERVER_IP>:%s", args.port)
        logger.info("Press CTRL+C to quit")
        logger.info("=" * 80)
        serve(app, host=args.host, port=args.port, threads=args.threads)
    else:
        logger.info("Mode: DEVELOPMENT (Flask debug server — not for company deployment)")
        logger.info("For deployment use: python main.py --production")
        logger.info("Access the application at: http://127.0.0.1:%s", args.port)
        logger.info("Press CTRL+C to quit")
        logger.info("=" * 80)
        app.run(debug=True, host=args.host, port=args.port)

