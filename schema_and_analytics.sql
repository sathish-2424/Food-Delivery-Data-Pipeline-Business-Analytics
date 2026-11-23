-- ============================================================================
-- End-to-End Food Delivery Data Pipeline Schema (Zomato / Uber Eats Model)
-- Normalized 3NF Relational Schema for MySQL / PostgreSQL / Snowflake
-- ============================================================================

CREATE DATABASE IF NOT EXISTS food_delivery_dw;
USE food_delivery_dw;

CREATE TABLE categories (
    category_id INT PRIMARY KEY,
    category_name VARCHAR(50) NOT NULL
);

CREATE TABLE restaurants (
    restaurant_id INT PRIMARY KEY,
    restaurant_name VARCHAR(100) NOT NULL,
    city VARCHAR(50) NOT NULL,
    cuisine_type VARCHAR(50),
    rating DECIMAL(2,1),
    avg_prep_time_mins INT
);

CREATE TABLE items (
    item_id INT PRIMARY KEY,
    restaurant_id INT NOT NULL,
    item_name VARCHAR(100) NOT NULL,
    category_id INT NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (restaurant_id) REFERENCES restaurants(restaurant_id),
    FOREIGN KEY (category_id) REFERENCES categories(category_id)
);

CREATE TABLE users (
    user_id INT PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(20),
    city VARCHAR(50),
    signup_date DATE,
    membership_tier VARCHAR(20)
);

CREATE TABLE orders (
    order_id INT PRIMARY KEY,
    user_id INT NOT NULL,
    restaurant_id INT NOT NULL,
    order_timestamp DATETIME NOT NULL,
    order_status VARCHAR(20) NOT NULL,
    delivery_city VARCHAR(50),
    delivery_time_mins INT,
    subtotal DECIMAL(10,2),
    delivery_fee DECIMAL(10,2),
    discount_amount DECIMAL(10,2),
    total_amount DECIMAL(10,2),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (restaurant_id) REFERENCES restaurants(restaurant_id)
);

CREATE TABLE order_items (
    order_item_id INT PRIMARY KEY,
    order_id INT NOT NULL,
    item_id INT NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    unit_price DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (item_id) REFERENCES items(item_id)
);

CREATE TABLE payments (
    payment_id INT PRIMARY KEY,
    order_id INT NOT NULL,
    payment_method VARCHAR(30) NOT NULL,
    payment_status VARCHAR(20) NOT NULL,
    paid_amount DECIMAL(10,2),
    paid_at DATETIME,
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);

-- ============================================================================
-- SAMPLE BUSINESS ANALYTICS QUERIES (DATA MART / KPI LAYER)
-- ============================================================================

-- 1. Most Popular Restaurants & SLA Rating (Uber Eats Interview Case Study)
SELECT 
    r.restaurant_name,
    r.city,
    COUNT(o.order_id) AS total_delivered_orders,
    ROUND(SUM(o.total_amount), 2) AS gross_revenue_inr,
    ROUND(AVG(o.delivery_time_mins), 1) AS avg_delivery_mins,
    CASE 
        WHEN COUNT(o.order_id) >= 100 AND AVG(o.delivery_time_mins) <= 50 THEN 'Tier 1 - Top Performer'
        WHEN COUNT(o.order_id) >= 60 THEN 'Tier 2 - Steady'
        ELSE 'Tier 3 - Growth Opportunity'
    END AS restaurant_tier
FROM orders o
JOIN restaurants r ON o.restaurant_id = r.restaurant_id
WHERE o.order_status = 'Delivered'
GROUP BY r.restaurant_id, r.restaurant_name, r.city
ORDER BY gross_revenue_inr DESC;

-- 2. Revenue & Order Share by Dietary Category
SELECT 
    c.category_name,
    SUM(oi.quantity) AS total_units_sold,
    ROUND(SUM(oi.quantity * oi.unit_price), 2) AS category_revenue_inr
FROM order_items oi
JOIN items i ON oi.item_id = i.item_id
JOIN categories c ON i.category_id = c.category_id
JOIN orders o ON oi.order_id = o.order_id
WHERE o.order_status = 'Delivered'
GROUP BY c.category_name
ORDER BY category_revenue_inr DESC;

-- 3. Payment Method Failure Rate Analysis (Actionable Product Insight)
SELECT 
    payment_method,
    COUNT(*) AS total_attempts,
    SUM(CASE WHEN payment_status = 'Failed' THEN 1 ELSE 0 END) AS failed_txns,
    ROUND(100.0 * SUM(CASE WHEN payment_status = 'Failed' THEN 1 ELSE 0 END) / COUNT(*), 2) AS failure_rate_pct
FROM payments
GROUP BY payment_method
ORDER BY failure_rate_pct DESC;

-- ============================================================================
-- MATERIALIZED DATA MARTS (MySQL 8+)
-- Re-run these statements to refresh the marts after a new ingestion.
-- ============================================================================

DROP TABLE IF EXISTS mart_city_gmv;
CREATE TABLE mart_city_gmv AS
SELECT delivery_city AS city,
       COUNT(*) AS delivered_orders,
       ROUND(SUM(total_amount), 2) AS delivered_gmv_inr,
       ROUND(AVG(total_amount), 2) AS average_order_value_inr
FROM orders
WHERE order_status = 'Delivered'
GROUP BY delivery_city;

DROP TABLE IF EXISTS mart_restaurant_sla_tiers;
CREATE TABLE mart_restaurant_sla_tiers AS
SELECT r.restaurant_id, r.restaurant_name, r.city,
       COUNT(*) AS delivered_orders,
       ROUND(SUM(o.total_amount), 2) AS delivered_gmv_inr,
       ROUND(AVG(o.delivery_time_mins), 1) AS avg_delivery_mins,
       CASE
         WHEN COUNT(*) >= 100 AND AVG(o.delivery_time_mins) <= 50 THEN 'Tier 1 - Top Performer'
         WHEN COUNT(*) >= 60 THEN 'Tier 2 - Steady'
         ELSE 'Tier 3 - Growth Opportunity'
       END AS restaurant_tier
FROM orders o
JOIN restaurants r ON r.restaurant_id = o.restaurant_id
WHERE o.order_status = 'Delivered'
GROUP BY r.restaurant_id, r.restaurant_name, r.city;

DROP TABLE IF EXISTS mart_payment_failure_rates;
CREATE TABLE mart_payment_failure_rates AS
SELECT payment_method,
       COUNT(*) AS total_attempts,
       SUM(payment_status = 'Failed') AS failed_txns,
       ROUND(100.0 * SUM(payment_status = 'Failed') / COUNT(*), 2) AS failure_rate_pct
FROM payments
GROUP BY payment_method;
