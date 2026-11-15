-- Clean analysis table for delivered orders (PRD section 5 definitions).
--
-- Run with: uv run scripts/build_analysis_table.py
--
-- Each block starts with "-- STAGE: <object>" and must be a single statement.
-- The builder checks count(*) = count(distinct order_id) after every stage.
--
-- Grain decisions:
--   * Population: order_status = 'delivered' and a non-null delivered date.
--   * order_items is aggregated to one row per order before the join: the
--     highest price + freight item wins, ties broken by lowest order_item_id.
--     This keeps category and seller from the same item. Multi-item orders
--     would otherwise fan out (110,189 item rows over 96,470 orders).
--   * order_reviews is aggregated to one row per order before the join: the
--     latest review by review_answer_timestamp wins, ties broken by creation
--     date then review_id. 525 of the 96,470 delivered orders have more than
--     one review.
--   * category_en is the English translation; two untranslated categories fall
--     back to their Portuguese names. NULL means the product has no category.
--   * delay_days and delivery_time_days are whole calendar days. is_late is
--     delay_days > 0, so a delivery on the estimated day is on time.

-- STAGE: qc_delivered_orders
create or replace temp view qc_delivered_orders as
select
    order_id,
    customer_id,
    order_purchase_timestamp,
    order_delivered_customer_date,
    order_estimated_delivery_date
from orders
where order_status = 'delivered'
  and order_delivered_customer_date is not null;

-- STAGE: qc_with_customers
create or replace temp view qc_with_customers as
select
    o.*,
    c.customer_unique_id,
    c.customer_state
from qc_delivered_orders o
left join customers c using (customer_id);

-- STAGE: qc_with_items
create or replace temp view qc_with_items as
with item_details as (
    select
        i.order_id,
        i.order_item_id,
        i.seller_id,
        coalesce(
            t.product_category_name_english,
            p.product_category_name
        ) as category_en,
        i.price + i.freight_value as item_value
    from order_items i
    left join products p using (product_id)
    left join product_category_name_translation t using (product_category_name)
),
ranked as (
    select
        *,
        row_number() over (
            partition by order_id
            order by item_value desc, order_item_id
        ) as item_rank
    from item_details
)
select
    o.*,
    r.category_en,
    r.seller_id
from qc_with_customers o
left join ranked r
    on r.order_id = o.order_id
   and r.item_rank = 1;

-- STAGE: qc_with_reviews
create or replace temp view qc_with_reviews as
with ranked_reviews as (
    select
        order_id,
        review_score,
        row_number() over (
            partition by order_id
            order by review_answer_timestamp desc, review_creation_date desc, review_id
        ) as review_rank
    from order_reviews
)
select
    o.*,
    r.review_score
from qc_with_items o
left join ranked_reviews r
    on r.order_id = o.order_id
   and r.review_rank = 1;

-- STAGE: analysis_orders
create or replace table analysis_orders as
select
    order_id,
    customer_unique_id,
    customer_state,
    date_diff(
        'day',
        order_estimated_delivery_date::date,
        order_delivered_customer_date::date
    ) as delay_days,
    date_diff(
        'day',
        order_purchase_timestamp::date,
        order_delivered_customer_date::date
    ) as delivery_time_days,
    date_diff(
        'day',
        order_estimated_delivery_date::date,
        order_delivered_customer_date::date
    ) > 0 as is_late,
    review_score,
    category_en,
    seller_id
from qc_with_reviews;
