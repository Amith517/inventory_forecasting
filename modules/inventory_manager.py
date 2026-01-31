from modules.database import get_connection
from datetime import datetime
from modules.alerts import send_stock_alert_email, record_alert
from modules.forecasting import generate_forecast_for_product, get_latest_forecast
import pandas as pd

def get_all_products():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.product_id, p.name, p.category, p.min_stock, p.early_warning_stock, 
               IFNULL(i.current_stock, 0) as current_stock, i.last_updated
        FROM products p
        LEFT JOIN inventory i ON p.product_id = i.product_id
        ORDER BY p.name
    """)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def set_min_stock(product_id, min_stock, early_warning=None):
    try:
        min_stock = int(min_stock)
    except:
        return False, "min_stock must be numeric."

    if min_stock < 0 or min_stock > 9999:
        return False, "min_stock must be between 0 and 9999."

    if early_warning is not None:
        try:
            early_warning = int(early_warning)
        except:
            return False, "early_warning must be numeric."

        if early_warning < 0 or early_warning > 9999:
            return False, "early_warning must be between 0 and 9999."

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE products 
        SET min_stock = ?, early_warning_stock = ? 
        WHERE product_id = ?
    """, (min_stock, early_warning, product_id))

    conn.commit()
    conn.close()
    return True, "OK"

# -------------------------------------------------------------------------
# UPDATE STOCK — PREVENT NEGATIVE AND LIMIT TO 4 DIGITS
# -------------------------------------------------------------------------
def update_stock(product_id, new_qty):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT current_stock FROM inventory WHERE product_id = ?", (product_id,))
    row = cur.fetchone()

    current_stock = int(row["current_stock"]) if row else 0
    updated_stock = current_stock + int(new_qty)

    # Prevent negative
    if updated_stock < 0:
        conn.close()
        return "NEGATIVE_STOCK_ERROR"

    # Prevent exceeding 4 digits
    if updated_stock > 9999:
        conn.close()
        return "MAX_STOCK_LIMIT"

    # Update/inset stock
    cur.execute("""
        INSERT INTO inventory (product_id, current_stock, last_updated)
        VALUES (?, ?, datetime('now','localtime'))
        ON CONFLICT(product_id)
        DO UPDATE SET current_stock = ?, last_updated = datetime('now','localtime')
    """, (product_id, updated_stock, updated_stock))

    conn.commit()
    conn.close()

    generate_forecast_for_product(product_id)
    check_and_handle_alert(product_id)

    return updated_stock

# -------------------------------------------------------------------------
# RECORD SALE — PREVENT NEGATIVE AND LIMIT TO 4 DIGITS
# -------------------------------------------------------------------------
def adjust_stock_by_sale(product_id, sold_qty, per_unit_price=None):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT current_stock FROM inventory WHERE product_id = ?", (product_id,))
    row = cur.fetchone()

    current_stock = int(row["current_stock"]) if row else 0
    new_stock = current_stock - int(sold_qty)

    # Prevent negative stock
    if new_stock < 0:
        conn.close()
        return "NEGATIVE_STOCK_ERROR"

    # Prevent exceeding 4 digits
    if new_stock > 9999:
        conn.close()
        return "MAX_STOCK_LIMIT"

    # Update stock
    cur.execute("""
        UPDATE inventory
        SET current_stock = ?, last_updated = datetime('now','localtime')
        WHERE product_id = ?
    """, (new_stock, product_id))

    # Record sale
    cur.execute("""
        INSERT INTO sales (product_id, sale_qty, sale_date, per_unit_price)
        VALUES (?, ?, datetime('now','localtime'), ?)
    """, (product_id, sold_qty, per_unit_price))

    conn.commit()
    conn.close()

    generate_forecast_for_product(product_id)
    check_and_handle_alert(product_id)

    return new_stock

# -------------------------------------------------------------------------
# ALERT LOGIC (unchanged)
# -------------------------------------------------------------------------
def get_sales_for_product(product_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT sale_date, sale_qty FROM sales WHERE product_id = ? ORDER BY sale_date",
                (product_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def check_and_handle_alert(product_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.name, p.min_stock, p.early_warning_stock, 
               IFNULL(i.current_stock,0) as current_stock
        FROM products p 
        LEFT JOIN inventory i ON p.product_id = i.product_id 
        WHERE p.product_id = ?
    """, (product_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return

    name = row["name"]
    min_stock = row["min_stock"]
    early = row["early_warning_stock"]
    current = int(row["current_stock"])

    if early is not None and current <= early:
        fc = get_latest_forecast(product_id, limit=14)
        forecast_text = "No forecast available." if fc is None else "\n".join(
            [f"{d.date()} → {round(v,2)}" for d, v in fc.items()]
        )

        send_stock_alert_email(name, current, early, forecast_text)
        record_alert(product_id, "early_warning", f"Early warning: {name} => {current}")

    if min_stock is not None and current <= min_stock:
        record_alert(product_id, "low_stock", f"Critical: {name} => {current}")
