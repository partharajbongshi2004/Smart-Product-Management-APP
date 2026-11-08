import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect("inventory.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            min_stock_level INTEGER NOT NULL
        )
    """)
    conn.commit()
    return conn

conn = init_db()

# --- APP CONFIGURATION ---
st.set_page_config(page_title="Inventory Management System", layout="wide", page_icon="📦")
st.title("📦 Smart Inventory & Stock Management")

# --- HELPER FUNCTIONS ---
def get_data():
    return pd.read_sql_query("SELECT * FROM inventory", conn)

def add_item(name, cat, qty, price, min_stock):
    try:
        with conn:
            conn.execute(
                "INSERT INTO inventory (item_name, category, quantity, price, min_stock_level) VALUES (?, ?, ?, ?, ?)",
                (name, cat, qty, price, min_stock)
            )
        return True
    except sqlite3.IntegrityError:
        return False

def update_stock_level(item_id, new_qty):
    with conn:
        conn.execute("UPDATE inventory SET quantity = ? WHERE id = ?", (new_qty, item_id))

def delete_item(item_id):
    with conn:
        conn.execute("DELETE FROM inventory WHERE id = ?", (item_id,))

# --- SIDEBAR: ADD / MANAGE ITEMS ---
st.sidebar.header("Add New Product")
new_name = st.sidebar.text_input("Item Name")
new_cat = st.sidebar.selectbox("Category", ["Electronics", "Apparel", "Food & Beverage", "Office Supplies", "Other"])
new_qty = st.sidebar.number_input("Initial Stock", min_value=0, step=1, value=10)
new_price = st.sidebar.number_input("Unit Price ($)", min_value=0.0, step=0.01, value=1.0)
new_min = st.sidebar.number_input("Minimum Stock Alert Level", min_value=0, step=1, value=5)

if st.sidebar.button("Add Item to Inventory"):
    if new_name:
        success = add_item(new_name, new_cat, new_qty, new_price, new_min)
        if success:
            st.sidebar.success(f"Added {new_name} successfully!")
            st.rerun()
        else:
            st.sidebar.error("Item name already exists.")
    else:
        st.sidebar.warning("Please provide an item name.")

# --- MAIN DASHBOARD ---
df = get_data()

# 1. KPI Metric Badges
st.subheader("Key Performance Metrics")
if not df.empty:
    total_items = df['quantity'].sum()
    total_value = (df['quantity'] * df['price']).sum()
    low_stock_count = df[df['quantity'] <= df['min_stock_level']].shape[0]
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Items in Stock", f"{total_items:,}")
    col2.metric("Total Inventory Value", f"${total_value:,.2f}")
    col3.metric("Low Stock Alerts", f"{low_stock_count}", delta=f"-{low_stock_count}" if low_stock_count > 0 else "0", delta_color="inverse")
else:
    st.info("Your inventory is currently empty. Add products in the sidebar to begin.")

st.divider()

# 2. Interactive Inventory Editor & Stock Alerts
if not df.empty:
    st.subheader("Current Stock Inventory")
    
    # Highlight low stock
    df['Status'] = df.apply(lambda row: "⚠️ Low Stock" if row['quantity'] <= row['min_stock_level'] else "✅ Healthy", axis=1)
    
    # Display inline interactive editor mimicking GitHub template behaviors
    edited_df = st.data_editor(
        df[['id', 'item_name', 'category', 'quantity', 'price', 'min_stock_level', 'Status']],
        column_config={
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "item_name": "Item Name",
            "category": "Category",
            "quantity": st.column_config.NumberColumn("Stock Qty", min_value=0, step=1),
            "price": st.column_config.NumberColumn("Price ($)", format="$%.2f"),
            "Status": st.column_config.TextColumn("Status", disabled=True)
        },
        disabled=["id", "item_name", "category", "Status"],
        hide_index=True,
        use_container_width=True
    )
    
    # Save bulk edits back to DB dynamically
    if st.button("Save Changes"):
        for index, row in edited_df.iterrows():
            orig_row = df.iloc[index]
            if row['quantity'] != orig_row['quantity'] or row['price'] != orig_row['price'] or row['min_stock_level'] != orig_row['min_stock_level']:
                with conn:
                    conn.execute(
                        "UPDATE inventory SET quantity = ?, price = ?, min_stock_level = ? WHERE id = ?",
                        (int(row['quantity']), float(row['price']), int(row['min_stock_level']), int(row['id']))
                    )
        st.success("Inventory changes committed to database!")
        st.rerun()

    st.divider()

    # 3. Analytics Charts
    st.subheader("Inventory Metrics Visualized")
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        fig_qty = px.bar(df, x='item_name', y='quantity', color='category', title="Stock Levels per Product", labels={'item_name': 'Product', 'quantity': 'Quantity'})
        st.plotly_chart(fig_qty, use_container_width=True)
        
    with chart_col2:
        df['total_value'] = df['quantity'] * df['price']
        fig_val = px.pie(df, values='total_value', names='category', title="Inventory Capital Value Distribution by Category")
        st.plotly_chart(fig_val, use_container_width=True)

    st.divider()

    # 4. Danger Zone: Item Removal
    st.subheader("🗑️ Delete Items")
    del_col1, del_col2 = st.columns([1, 3])
    with del_col1:
        item_to_delete = st.selectbox("Select item to remove:", df['item_name'].tolist())
    with del_col2:
        st.write("") # Alignment helper
        st.write("") 
        if st.button("Permanently Remove Product", type="primary"):
            target_id = df[df['item_name'] == item_to_delete]['id'].values[0]
            delete_item(target_id)
            st.error(f"Removed {item_to_delete} from the database.")
            st.rerun()
