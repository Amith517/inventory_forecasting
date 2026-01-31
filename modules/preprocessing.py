# modules/preprocessing.py
import pandas as pd
from modules.database import get_connection

def get_daily_sales_series(product_id):
    """
    Returns a pandas Series (indexed by date) of daily sold quantities for given product_id.
    Aggregates the sales table.
    """
    conn = get_connection()
    df = pd.read_sql_query("SELECT sale_date, sale_qty FROM sales WHERE product_id = ?", conn, params=(product_id,))
    conn.close()
    if df.empty:
        return pd.Series(dtype=float)
    df['sale_date'] = pd.to_datetime(df['sale_date']).dt.date
    daily = df.groupby('sale_date')['sale_qty'].sum().sort_index()
    series = daily.astype(float)
    series.index = pd.to_datetime(series.index)
    return series
