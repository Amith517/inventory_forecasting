# modules/database.py
import sqlite3
from pathlib import Path

DB_PATH = Path("inventory.db")

def get_connection():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cur = conn.cursor()

    # products: product master (no current stock)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS products (
        product_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        category TEXT,
        min_stock INTEGER,
        early_warning_stock INTEGER,
        price REAL
    );
    """)

    # inventory: current stock per product
    cur.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        product_id INTEGER PRIMARY KEY,
        current_stock INTEGER DEFAULT 0,
        last_updated TEXT,
        FOREIGN KEY(product_id) REFERENCES products(product_id)
    );
    """)

    # sales: store every sale event (useful for forecasting)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        sale_qty INTEGER,
        sale_date TEXT,
        per_unit_price REAL,
        FOREIGN KEY(product_id) REFERENCES products(product_id)
    );
    """)

    # forecast_results: store forecasts for products
    cur.execute("""
    CREATE TABLE IF NOT EXISTS forecast_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        forecast_date TEXT,
        forecast_qty REAL,
        model TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(product_id) REFERENCES products(product_id)
    );
    """)

    # alerts: store sent alerts
    cur.execute("""
    CREATE TABLE IF NOT EXISTS alerts (
        alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        alert_type TEXT,
        message TEXT,
        sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(product_id) REFERENCES products(product_id)
    );
    """)

    conn.commit()
    conn.close()

# ensure DB created on import
init_db()
