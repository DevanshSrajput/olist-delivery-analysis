-- Quality checks for the Olist dataset (PRD section 7).
--
-- Run with: uv run scripts/run_quality_checks.py
--
-- Each block starts with "-- CHECK: <name>" and must be a single SELECT.
-- A block that returns a "status" column is a gate: "FAIL" makes the runner
-- exit with code 1. Other blocks are informational.
--
-- Join checks are done at order grain. order_items, order_payments and
-- order_reviews are aggregated per order first, because joining them raw
-- multiplies rows for multi-item orders and orders with multiple reviews.

-- CHECK: row counts per table
-- PRD 7: row counts per table after load.
select table_name, row_count
from (
    select 1 as ord, 'customers' as table_name, count(*) as row_count from customers
    union all
    select 2, 'geolocation', count(*) from geolocation
    union all
    select 3, 'order_items', count(*) from order_items
    union all
    select 4, 'order_payments', count(*) from order_payments
    union all
    select 5, 'order_reviews', count(*) from order_reviews
    union all
    select 6, 'orders', count(*) from orders
    union all
    select 7, 'products', count(*) from products
    union all
    select 8, 'sellers', count(*) from sellers
    union all
    select 9, 'product_category_name_translation', count(*) from product_category_name_translation
) counts
order by ord;

-- CHECK: duplicate order rows after joins
-- PRD 7: the joined orders table must have one row per order_id after every join.
-- A non-zero duplicate_rows means a join fanned out.
with items as (
    select order_id
    from order_items
    group by order_id
),
payments as (
    select order_id
    from order_payments
    group by order_id
),
reviews as (
    select order_id
    from order_reviews
    group by order_id
),
joined as (
    select 1 as ord, 'orders (base)' as join_step,
           count(*) as joined_rows, count(distinct order_id) as distinct_order_ids
    from orders
    union all
    select 2, 'orders + customers',
           count(*), count(distinct o.order_id)
    from orders o
    left join customers c using (customer_id)
    union all
    select 3, 'orders + customers + order_items',
           count(*), count(distinct o.order_id)
    from orders o
    left join customers c using (customer_id)
    left join items i using (order_id)
    union all
    select 4, 'orders + customers + order_items + order_payments',
           count(*), count(distinct o.order_id)
    from orders o
    left join customers c using (customer_id)
    left join items i using (order_id)
    left join payments p using (order_id)
    union all
    select 5, 'orders + customers + order_items + order_payments + order_reviews',
           count(*), count(distinct o.order_id)
    from orders o
    left join customers c using (customer_id)
    left join items i using (order_id)
    left join payments p using (order_id)
    left join reviews r using (order_id)
)
select join_step,
       joined_rows,
       distinct_order_ids,
       joined_rows - distinct_order_ids as duplicate_rows,
       case when joined_rows = distinct_order_ids then 'ok' else 'FAIL' end as status
from joined
order by ord;

-- CHECK: raw child-table fan-out (informational)
-- Joining child tables directly to orders multiplies rows by design; the
-- order-grain check above is the one that has to pass. This block records the
-- raw multiplication so it is not mistaken for corruption.
select 'order_items' as child_table,
       count(*) as raw_joined_rows,
       count(distinct o.order_id) as distinct_order_ids,
       round(count(*) * 1.0 / nullif(count(distinct o.order_id), 0), 2) as rows_per_order
from orders o
join order_items i using (order_id)
union all
select 'order_payments',
       count(*), count(distinct o.order_id),
       round(count(*) * 1.0 / nullif(count(distinct o.order_id), 0), 2)
from orders o
join order_payments p using (order_id)
union all
select 'order_reviews',
       count(*), count(distinct o.order_id),
       round(count(*) * 1.0 / nullif(count(distinct o.order_id), 0), 2)
from orders o
join order_reviews r using (order_id)
order by child_table;

-- CHECK: duplicate keys in join dimensions
-- A duplicate on the join key fans rows out even when the child table has one
-- row per order. These keys should all be unique.
select 'orders.order_id' as key_name,
       count(*) - count(distinct order_id) as duplicate_rows,
       case when count(*) = count(distinct order_id) then 'ok' else 'FAIL' end as status
from orders
union all
select 'customers.customer_id',
       count(*) - count(distinct customer_id),
       case when count(*) = count(distinct customer_id) then 'ok' else 'FAIL' end
from customers
union all
select 'products.product_id',
       count(*) - count(distinct product_id),
       case when count(*) = count(distinct product_id) then 'ok' else 'FAIL' end
from products
union all
select 'sellers.seller_id',
       count(*) - count(distinct seller_id),
       case when count(*) = count(distinct seller_id) then 'ok' else 'FAIL' end
from sellers
union all
select 'product_category_name_translation.product_category_name',
       count(*) - count(distinct product_category_name),
       case when count(*) = count(distinct product_category_name) then 'ok' else 'FAIL' end
from product_category_name_translation
order by key_name;

-- CHECK: null rates on key date columns
-- PRD 7: null rates on key date columns. A null delivered date is expected for
-- orders that were not delivered; the analysis population filters those out.
select 'orders' as table_name, 'order_purchase_timestamp' as column_name,
       count(*) as total_rows,
       count(*) - count(order_purchase_timestamp) as null_rows,
       round(100.0 * (count(*) - count(order_purchase_timestamp)) / nullif(count(*), 0), 2) as null_pct
from orders
union all
select 'orders', 'order_approved_at',
       count(*), count(*) - count(order_approved_at),
       round(100.0 * (count(*) - count(order_approved_at)) / nullif(count(*), 0), 2)
from orders
union all
select 'orders', 'order_delivered_carrier_date',
       count(*), count(*) - count(order_delivered_carrier_date),
       round(100.0 * (count(*) - count(order_delivered_carrier_date)) / nullif(count(*), 0), 2)
from orders
union all
select 'orders', 'order_delivered_customer_date',
       count(*), count(*) - count(order_delivered_customer_date),
       round(100.0 * (count(*) - count(order_delivered_customer_date)) / nullif(count(*), 0), 2)
from orders
union all
select 'orders', 'order_estimated_delivery_date',
       count(*), count(*) - count(order_estimated_delivery_date),
       round(100.0 * (count(*) - count(order_estimated_delivery_date)) / nullif(count(*), 0), 2)
from orders
union all
select 'order_items', 'shipping_limit_date',
       count(*), count(*) - count(shipping_limit_date),
       round(100.0 * (count(*) - count(shipping_limit_date)) / nullif(count(*), 0), 2)
from order_items
union all
select 'order_reviews', 'review_creation_date',
       count(*), count(*) - count(review_creation_date),
       round(100.0 * (count(*) - count(review_creation_date)) / nullif(count(*), 0), 2)
from order_reviews
union all
select 'order_reviews', 'review_answer_timestamp',
       count(*), count(*) - count(review_answer_timestamp),
       round(100.0 * (count(*) - count(review_answer_timestamp)) / nullif(count(*), 0), 2)
from order_reviews
order by table_name, column_name;

-- CHECK: delivered date earlier than purchase date
-- PRD 7: orders with a delivered date before the purchase date. Must be zero.
select count(*) as orders_delivered_before_purchase,
       round(100.0 * count(*) / (select count(*) from orders), 2) as pct_of_orders,
       case when count(*) = 0 then 'ok' else 'FAIL' end as status
from orders
where order_delivered_customer_date is not null
  and order_delivered_customer_date < order_purchase_timestamp;

-- CHECK: orders with multiple reviews
-- PRD 7: orders with multiple reviews. These exist in the dataset, so any
-- order-level join must aggregate reviews instead of joining raw.
with per_order as (
    select o.order_id, count(r.review_id) as review_count
    from orders o
    left join order_reviews r using (order_id)
    group by o.order_id
)
select count(*) filter (where review_count = 0) as orders_without_review,
       count(*) filter (where review_count = 1) as orders_with_one_review,
       count(*) filter (where review_count > 1) as orders_with_multiple_reviews,
       coalesce(sum(review_count) filter (where review_count > 1), 0) as review_rows_on_multi_review_orders,
       max(review_count) as max_reviews_per_order
from per_order;

-- CHECK: share of orders in each status
-- PRD 7: share of orders in each status.
select order_status,
       count(*) as orders,
       round(100.0 * count(*) / sum(count(*)) over (), 2) as share_pct
from orders
group by order_status
order by orders desc, order_status;

-- CHECK: analysis population and exclusions
-- PRD 5 defines the analysis population as delivered orders with a delivered
-- date; PRD 7 says every exclusion is documented with its count.
select count(*) as all_orders,
       count(*) filter (where order_status = 'delivered') as delivered_orders,
       count(*) filter (where order_status = 'delivered' and order_delivered_customer_date is not null) as analysis_population,
       count(*) filter (where order_status = 'delivered' and order_delivered_customer_date is null) as excluded_delivered_missing_date,
       count(*) filter (where order_status <> 'delivered') as excluded_not_delivered
from orders;
