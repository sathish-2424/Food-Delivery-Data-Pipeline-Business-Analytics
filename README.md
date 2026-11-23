# Food Delivery Analytics Pipeline

A small MySQL 8+ pipeline for loading the supplied food delivery CSVs, then building three queryable data marts for BI tools.

## Business readout

The supplied orders contain **₹5,10,080.10 delivered GMV across 1,054 delivered orders** (GMV uses `orders.total_amount`; cancelled and failed orders are excluded).

- Gold orders had a ₹450.69 average subtotal and received a zero delivery fee on 78.3% of delivered orders. Standard orders averaged ₹480.14 subtotal and none had a zero delivery fee. Gold's average basket was ₹29.45 lower, so test a modest free-delivery minimum near the current Gold basket and compare order frequency and contribution margin before changing the benefit. This is an association in this sample, not evidence that membership caused basket size.
- Wallet had the highest observed payment failure rate: 5/79 attempts (6.33%). UPI had 27/620 failures (4.35%) and the largest failure count. Prioritize Wallet checkout diagnostics while monitoring its small sample; treat payment failure as a checkout friction proxy, not a measured abandonment rate.
- 93 orders were Cancelled and 53 Failed, out of 1,200 total. These are recorded order outcomes, not unobserved checkout drop-offs.

## Run it

1. Create a MySQL 8 database and schema by running `schema_and_analytics.sql` in a MySQL client. The script creates `food_delivery_dw` and all seven normalized tables.
2. Install the one connector dependency: `python -m pip install -r requirements.txt`.
3. Set `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, and optionally `MYSQL_DATABASE` (defaults: localhost, 3306, root, empty password, `food_delivery_dw`).
4. Run `python ingest.py` from this directory. Use `python ingest.py --batch-size 250` to change batch size. The loader inserts dimensions before facts, commits table-by-table, converts blank CSV cells to SQL NULL, and uses primary-key upserts so reruns refresh existing rows.
5. Re-run the three `CREATE TABLE AS SELECT` statements at the end of `schema_and_analytics.sql` to refresh `mart_city_gmv`, `mart_restaurant_sla_tiers`, and `mart_payment_failure_rates`.
6. Connect Power BI, Tableau, or Streamlit to those three mart tables. For example, start with `SELECT * FROM mart_city_gmv ORDER BY delivered_gmv_inr DESC;`.

[Open the live dashboard](https://food-delivery-data-pipeline-business-analytics.streamlit.app/)

The source also retains the original analytics SELECT queries. To reload from scratch, drop/recreate the database schema before loading; rerunning the loader itself is safe for existing primary keys. The loader expects the CSV headers and MySQL schema in this folder to match.
