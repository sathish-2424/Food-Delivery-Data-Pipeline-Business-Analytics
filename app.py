from pathlib import Path

import pandas as pd
import streamlit as st


DATA_DIR = Path(__file__).resolve().parent / "Dataset"
REQUIRED = {
    "orders": {"order_id", "user_id", "restaurant_id", "order_timestamp", "order_status", "delivery_city", "delivery_time_mins", "subtotal", "delivery_fee", "total_amount"},
    "users": {"user_id", "membership_tier"},
    "payments": {"order_id", "payment_method", "payment_status"},
    "restaurants": {"restaurant_id", "restaurant_name", "city"},
}

st.set_page_config(page_title="Food Delivery | Analytics", page_icon=":material/analytics:", layout="wide")
st.markdown("""
<style>
  html, body, [class*="css"] { font-family: system-ui, sans-serif; }
  .stApp { background: #f8fafc; }
  h1, h2, h3 { color: #1e3a8a; }
  [data-testid="stMetric"] { background: white; border: 1px solid #dbeafe; padding: 16px 18px; border-radius: 12px; }
  [data-testid="stMetricLabel"] { color: #475569; }
  [data-testid="stMetricValue"] { color: #1e40af; font-family: 'Fira Code', monospace; }
  div[data-testid="stDataFrame"] { border: 1px solid #dbeafe; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=60)
def load_data():
    frames = {}
    for name, required in REQUIRED.items():
        path = DATA_DIR / f"{name}.csv"
        if not path.is_file():
            raise FileNotFoundError(f"Required file not found: {path.name}")
        frame = pd.read_csv(path)
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"{path.name} is missing columns: {', '.join(sorted(missing))}")
        frames[name] = frame

    orders = frames["orders"]
    for col in ("subtotal", "delivery_fee", "total_amount", "delivery_time_mins"):
        orders[col] = pd.to_numeric(orders[col], errors="coerce")
    orders["order_timestamp"] = pd.to_datetime(orders["order_timestamp"], errors="coerce")
    orders = orders.dropna(subset=["order_timestamp"])
    orders["order_date"] = orders["order_timestamp"].dt.date

    users = frames["users"][["user_id", "membership_tier"]].drop_duplicates("user_id")
    restaurants = frames["restaurants"][["restaurant_id", "restaurant_name", "city"]].drop_duplicates("restaurant_id")
    payments = frames["payments"].copy()
    payments["payment_method"] = payments["payment_method"].fillna("Unknown")
    orders = orders.merge(users, on="user_id", how="left").merge(restaurants, on="restaurant_id", how="left")
    orders["membership_tier"] = orders["membership_tier"].fillna("Unknown")
    orders["restaurant_name"] = orders["restaurant_name"].fillna("Unknown")
    orders["payment_method"] = orders["order_id"].map(payments.drop_duplicates("order_id").set_index("order_id")["payment_method"]).fillna("Unknown")
    return orders, payments


st.sidebar.title("Food Delivery")
st.sidebar.caption("CSV-backed analytics · refreshes every 60 seconds")
if st.sidebar.button("Refresh CSV data", use_container_width=True):
    load_data.clear()

try:
    orders, payments = load_data()
except (FileNotFoundError, ValueError, pd.errors.ParserError) as exc:
    st.error(f"Could not load dashboard data: {exc}")
    st.stop()

st.title("Food Delivery Analytics")
st.caption("Delivered revenue, restaurant operations, and payment health")

min_date, max_date = orders["order_date"].min(), orders["order_date"].max()
date_range = st.sidebar.date_input("Order date", value=(min_date, max_date), min_value=min_date, max_value=max_date)
cities = sorted(orders["delivery_city"].dropna().unique().tolist())
tiers = sorted(orders["membership_tier"].dropna().unique().tolist())
methods = sorted(payments["payment_method"].dropna().unique().tolist())
selected_cities = st.sidebar.multiselect("Delivery city", cities, default=cities)
selected_tiers = st.sidebar.multiselect("Membership tier", tiers, default=tiers)
selected_methods = st.sidebar.multiselect("Payment method", methods, default=methods)

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date = end_date = date_range
filtered = orders[
    orders["order_date"].between(start_date, end_date)
    & orders["delivery_city"].isin(selected_cities)
    & orders["membership_tier"].isin(selected_tiers)
    & orders["payment_method"].isin(selected_methods)
].copy()
delivered = filtered[filtered["order_status"].eq("Delivered")]

gmv = delivered["total_amount"].sum()
aov = delivered["subtotal"].mean()
avg_delivery = delivered["delivery_time_mins"].mean()
success_ids = set(filtered["order_id"])
visible_payments = payments[
    payments["order_id"].isin(success_ids) & payments["payment_method"].isin(selected_methods)
]
failure_pct = 100 * visible_payments["payment_status"].eq("Failed").mean() if len(visible_payments) else 0

metrics = st.columns(4)
metrics[0].metric("Delivered GMV", f"₹{gmv:,.2f}", help="Sum of total_amount for delivered orders in the selected filters.")
metrics[1].metric("Delivered orders", f"{len(delivered):,}")
metrics[2].metric("Average basket", f"₹{aov:,.2f}" if pd.notna(aov) else "—", help="Average subtotal for delivered orders.")
metrics[3].metric("Payment failure rate", f"{failure_pct:.2f}%", help="Failed payment attempts divided by visible payment attempts.")

left, right = st.columns((1.5, 1))
with left:
    st.subheader("Delivered GMV over time")
    daily = delivered.groupby("order_date", as_index=True)["total_amount"].sum().rename("Delivered GMV (₹)")
    st.line_chart(daily, y_label="₹", use_container_width=True)
with right:
    st.subheader("GMV by city")
    city_gmv = delivered.groupby("delivery_city")["total_amount"].sum().sort_values(ascending=False)
    st.bar_chart(city_gmv, y_label="Delivered GMV (₹)", use_container_width=True)

left, right = st.columns(2)
with left:
    st.subheader("Payment reliability")
    if visible_payments.empty:
        st.info("No payment attempts match these filters.")
    else:
        payment_summary = visible_payments.groupby("payment_method").agg(
            attempts=("payment_status", "size"),
            failures=("payment_status", lambda values: values.eq("Failed").sum()),
        )
        payment_summary["Failure rate (%)"] = (100 * payment_summary["failures"] / payment_summary["attempts"]).round(2)
        st.bar_chart(payment_summary["Failure rate (%)"], y_label="Failure rate (%)", use_container_width=True)
        st.dataframe(payment_summary.reset_index(), hide_index=True, use_container_width=True)
with right:
    st.subheader("Membership & delivery fees")
    if delivered.empty:
        st.info("No delivered orders match these filters.")
    else:
        membership = delivered.groupby("membership_tier").agg(
            delivered_orders=("order_id", "count"),
            average_basket_inr=("subtotal", "mean"),
            free_delivery_share_pct=("delivery_fee", lambda values: 100 * values.eq(0).mean()),
        ).round(2).reset_index()
        st.dataframe(membership, hide_index=True, use_container_width=True)

st.subheader("Restaurant delivery performance")
if delivered.empty:
    st.info("No delivered orders match these filters.")
else:
    sla = delivered.groupby(["restaurant_name", "city"], dropna=False).agg(
        delivered_orders=("order_id", "count"),
        delivered_gmv_inr=("total_amount", "sum"),
        avg_delivery_mins=("delivery_time_mins", "mean"),
    ).round(2).sort_values("delivered_gmv_inr", ascending=False).reset_index()
    sla["restaurant_tier"] = "Tier 3 - Growth Opportunity"
    sla.loc[sla["delivered_orders"] >= 60, "restaurant_tier"] = "Tier 2 - Steady"
    sla.loc[(sla["delivered_orders"] >= 100) & (sla["avg_delivery_mins"] <= 50), "restaurant_tier"] = "Tier 1 - Top Performer"
    st.dataframe(sla, hide_index=True, use_container_width=True)

with st.expander("Order status mix and data notes"):
    status = filtered["order_status"].value_counts().rename_axis("order_status").reset_index(name="orders")
    st.dataframe(status, hide_index=True, use_container_width=True)
    st.caption("Cancelled and failed order statuses are recorded outcomes, not measured checkout abandonment. GMV is the sum of total_amount for delivered orders. Data refreshes from CSV every 60 seconds; use the sidebar button to refresh immediately.")
