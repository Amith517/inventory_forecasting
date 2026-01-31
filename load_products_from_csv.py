# load_products_from_csv.py
import sqlite3
import pandas as pd
import os
from modules.database import get_connection

CSV_PATH = os.path.join("data", "products.csv")

def load_products():
    if not os.path.exists(CSV_PATH):
        print(f"CSV not found at {CSV_PATH}")
        return 0

    # Read CSV, set header normalization
    df = pd.read_csv(CSV_PATH)
    df.columns = [c.strip().lower() for c in df.columns]

    name_col = None
    for c in df.columns:
        if "product" in c and "name" in c:
            name_col = c
            break
    stock_col = None
    for c in df.columns:
        if "total" in c and "quantity" in c:
            stock_col = c
            break
    # fallback heuristics
    if stock_col is None:
        for c in df.columns:
            if "stock" in c or "quantity" in c:
                stock_col = c
                break

    category_col = next((c for c in df.columns if "category" in c), None)
    price_col = next((c for c in df.columns if "listprice" in c or "list_price" in c or "price" in c), None)

    if name_col is None or stock_col is None:
        print("Required columns not found in CSV. Found columns:", df.columns.tolist())
        return 0

    conn = get_connection()
    cur = conn.cursor()

    inserted = 0
    for _, row in df.iterrows():
        name = str(row[name_col]).strip()
        if not name:
            continue
        try:
            stock = int(float(row.get(stock_col, 0)))
        except Exception:
            stock = 0
        category = str(row.get(category_col, "")).strip() if category_col else ""
        try:
            price = float(row.get(price_col, 0)) if price_col else 0.0
        except Exception:
            price = 0.0

        cur.execute("SELECT product_id FROM products WHERE name = ?", (name,))
        res = cur.fetchone()
        if res:
            pid = res["product_id"]
            cur.execute("SELECT product_id FROM inventory WHERE product_id = ?", (pid,))
            if cur.fetchone():
                cur.execute("UPDATE inventory SET current_stock = ?, last_updated = datetime('now') WHERE product_id = ?", (stock, pid))
            else:
                cur.execute("INSERT INTO inventory (product_id, current_stock, last_updated) VALUES (?, ?, datetime('now'))", (pid, stock))
            print(f"Updated existing: {name} (stock={stock})")
        else:
            cur.execute("INSERT INTO products (name, category, min_stock, early_warning_stock, price) VALUES (?, ?, NULL, NULL, ?)", (name, category, price))
            pid = cur.lastrowid
            cur.execute("INSERT INTO inventory (product_id, current_stock, last_updated) VALUES (?, ?, datetime('now'))", (pid, stock))
            print(f"Inserted: {name} (stock={stock})")
            inserted += 1

    conn.commit()
    conn.close()
    print(f"Done. Inserted {inserted} new products (existing updated).")
    return inserted

if __name__ == "__main__":
    load_products()
