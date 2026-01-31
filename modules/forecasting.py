import warnings
from datetime import timedelta
import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX
from prophet import Prophet
from pmdarima import auto_arima
from modules.database import get_connection
from modules.preprocessing import get_daily_sales_series

warnings.filterwarnings("ignore")

# -----------------------------------------------------------
# Train SARIMA Model
# -----------------------------------------------------------
def train_sarima(series, seasonal_period=7):
    if series.empty or len(series) < 10:
        return None
    try:
        arima_model = auto_arima(series, seasonal=True, m=seasonal_period,
                                 trace=False, error_action='ignore', suppress_warnings=True)
        order = arima_model.order
        seasonal_order = arima_model.seasonal_order
    except Exception:
        order = (1, 1, 1)
        seasonal_order = (0, 1, 1, seasonal_period)

    model = SARIMAX(series, order=order, seasonal_order=seasonal_order,
                    enforce_stationarity=False, enforce_invertibility=False)
    fitted = model.fit(disp=False)
    return fitted


# -----------------------------------------------------------
# SARIMA Forecast
# -----------------------------------------------------------
def forecast_sarima(fitted_model, steps):
    if fitted_model is None:
        return None
    pred = fitted_model.get_forecast(steps=steps)
    forecast = pred.predicted_mean
    return pd.Series(forecast.values)


# -----------------------------------------------------------
# Train Prophet Model
# -----------------------------------------------------------
def train_prophet(series):
    if series.empty or len(series) < 6:
        return None

    df = series.reset_index()
    df.columns = ['ds', 'y']

    m = Prophet(
        daily_seasonality=True,
        yearly_seasonality=True,
        weekly_seasonality=True
    )
    m.fit(df)
    return m


# -----------------------------------------------------------
# Prophet Forecast
# -----------------------------------------------------------
def forecast_prophet(model, periods):
    future = model.make_future_dataframe(periods=periods)
    fcst = model.predict(future)
    fc = fcst[['ds', 'yhat']].set_index('ds')['yhat'][-periods:]
    return pd.Series(fc.values)


# -----------------------------------------------------------
# SAVE forecast to DB
# -----------------------------------------------------------
def save_forecast_to_db(product_id, forecast_series, model_name='hybrid'):
    if forecast_series is None or len(forecast_series) == 0:
        return

    conn = get_connection()
    cur = conn.cursor()

    # remove old forecasts
    cur.execute("DELETE FROM forecast_results WHERE product_id = ?", (product_id,))

    # write new forecasts
    start_date = pd.Timestamp.today().normalize() + pd.Timedelta(days=1)
    dates = pd.date_range(start_date, periods=len(forecast_series), freq='D')

    for dt, qty in zip(dates, forecast_series):
        cur.execute("""
            INSERT INTO forecast_results (product_id, forecast_date, forecast_qty, model)
            VALUES (?, ?, ?, ?)
        """, (product_id, dt.isoformat(), float(qty), model_name))

    conn.commit()
    conn.close()


# -----------------------------------------------------------
# HYBRID FORECAST = (SARIMA + Prophet) / 2
# -----------------------------------------------------------
def generate_forecast_for_product(product_id, days=14):
    series = get_daily_sales_series(product_id)

    # No sales history → return zero forecast
    if series.empty:
        fallback = pd.Series([0.0] * days)
        save_forecast_to_db(product_id, fallback, model_name='none')
        return fallback

    # ---- Train SARIMA ----
    sarima_model = train_sarima(series)
    sarima_fc = forecast_sarima(sarima_model, days) if sarima_model else None

    # ---- Train Prophet ----
    prophet_model = train_prophet(series)
    prophet_fc = forecast_prophet(prophet_model, days) if prophet_model else None

    # ---- Handle fallback cases ----
    if sarima_fc is None and prophet_fc is None:
        avg = series.mean()
        fallback = pd.Series([avg] * days)
        save_forecast_to_db(product_id, fallback, 'avg_fallback')
        return fallback

    if sarima_fc is None:
        save_forecast_to_db(product_id, prophet_fc, 'prophet_only')
        return prophet_fc

    if prophet_fc is None:
        save_forecast_to_db(product_id, sarima_fc, 'sarima_only')
        return sarima_fc

    # ⭐ FINAL HYBRID FORECAST ⭐
    hybrid = (sarima_fc + prophet_fc) / 2
    save_forecast_to_db(product_id, hybrid, model_name="hybrid")

    return hybrid


# -----------------------------------------------------------
# Fetch Latest Forecast (Used in Alerts)
# -----------------------------------------------------------
def get_latest_forecast(product_id, limit=14):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT forecast_date, forecast_qty 
        FROM forecast_results 
        WHERE product_id = ?
        ORDER BY forecast_date 
        LIMIT ?
    """, (product_id, limit))
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return None

    dates = [pd.to_datetime(r["forecast_date"]) for r in rows]
    values = [float(r["forecast_qty"]) for r in rows]

    return pd.Series(values, index=dates)
