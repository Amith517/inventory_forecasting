import streamlit as st
from modules.database import init_db, get_connection
from modules.inventory_manager import get_all_products, set_min_stock, update_stock, adjust_stock_by_sale
from modules.forecasting import generate_forecast_for_product
import pandas as pd
import os
import load_products_from_csv

# ---------------- UI SETTINGS ----------------
st.set_page_config(layout="wide", page_title="Inventory Forecasting & Management")

st.title("Inventory Forecasting & Management")

# -----------------------------------------------------
# AUTO IMPORT CSV ON FIRST RUN
# -----------------------------------------------------
try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(1) as cnt FROM products")
    cnt = cur.fetchone()["cnt"]
    conn.close()

    if cnt == 0:
        csv_path = os.path.join("data", "products.csv")
        if os.path.exists(csv_path):
            load_products_from_csv.load_products()

except Exception as e:
    print("Auto import failed:", e)

# -----------------------------------------------------
# SIDEBAR MENU
# -----------------------------------------------------
menu = st.sidebar.selectbox("Menu", ["Home", "Products", "Update Stock", "Record Sale"])

# -----------------------------------------------------
# HOME PAGE
# -----------------------------------------------------
if menu == "Home":
    st.header("Overview")

    products = get_all_products()
    df = pd.DataFrame(products)

    if not df.empty:
        st.dataframe(df)
    else:
        st.info("No products found. Please upload products.csv inside the /data folder.")

# -----------------------------------------------------
# PRODUCTS PAGE
# -----------------------------------------------------
if menu == "Products":
    st.header("Products List")

    products = get_all_products()
    df = pd.DataFrame(products)

    if not df.empty:
        st.dataframe(df)
    else:
        st.info("No products available.")

    st.subheader("Set minimum stock")
    col1, col2 = st.columns([2, 1])

    product_map = {p['name']: p['product_id'] for p in products}

    if product_map:
        selected = col1.selectbox("Select product", [""] + list(product_map.keys()))
        min_qty = col2.number_input("Min stock", min_value=0, step=1, value=0)
        ew = col2.number_input("Early warning stock", min_value=0, step=1, value=0)

        if st.button("Save min stock"):
            if not selected:
                st.warning("Select a product.")
            else:
                # UI validation
                if min_qty > 9999 or ew > 9999:
                    st.error("Min stock and Early warning stock cannot exceed 4 digits (max 9999).")
                else:
                    pid = product_map[selected]
                    ok, msg = set_min_stock(pid, int(min_qty), int(ew))
                    if ok:
                        st.success("Saved successfully.")
                    else:
                        st.error(f"Failed: {msg}")
    else:
        st.info("No products available.")

# -----------------------------------------------------
# UPDATE STOCK PAGE
# -----------------------------------------------------
if menu == "Update Stock":
    st.header("Update Stock")

    products = get_all_products()
    product_map = {p['name']: p['product_id'] for p in products}

    selected = st.selectbox("Select product", [""] + list(product_map.keys()))

    if selected:
        pid = product_map[selected]
        current = next((p['current_stock'] for p in products if p['product_id'] == pid), 0)
        new_qty = st.number_input("Quantity to add/remove (delta)", min_value=-100000, value=0)

        if st.button("Update stock"):
            result = update_stock(pid, int(new_qty))

            if result == "NEGATIVE_STOCK_ERROR":
                st.error("Stock cannot go below zero!")

            elif result == "MAX_STOCK_LIMIT":
                st.error("Stock cannot exceed 4 digits (max 9999)!")

            else:
                st.success("Stock updated successfully.")

# -----------------------------------------------------
# RECORD SALE PAGE
# -----------------------------------------------------
if menu == "Record Sale":
    st.header("Record a Sale")

    products = get_all_products()
    product_map = {p['name']: p['product_id'] for p in products}

    selected = st.selectbox("Select product", [""] + list(product_map.keys()))
    qty = st.number_input("Quantity sold", min_value=1, value=1)

    if st.button("Record Sale"):
        if selected:
            pid = product_map[selected]
            current = next((p['current_stock'] for p in products if p['product_id'] == pid), 0)

            if qty > current:
                st.error(f"Cannot record sale. Current stock is only {current}.")
            else:
                res = adjust_stock_by_sale(pid, int(qty))

                if res == "NEGATIVE_STOCK_ERROR":
                    st.error("Sale would cause negative stock!")

                elif res == "MAX_STOCK_LIMIT":
                    st.error("Stock cannot exceed 4 digits (max 9999)!")

                else:
                    st.success(f"Sale recorded. New stock: {res}")
        else:
            st.warning("Select a product.")
