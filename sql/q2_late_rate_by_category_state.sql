-- Q2: Which categories and customer states have the worst late rate?
-- (PRD section 6)
--
-- Run with: uv run scripts/run_queries.py
--
-- Grain: category rows are one row per (order, distinct category). An order
-- with three categories counts once in each, so category counts do not sum to
-- the 96,470 delivered orders. This avoids counting an order multiple times
-- for repeated items in the same category. State rows are one row per order.
-- 1,332 delivered orders contain only uncategorized items, so they contribute
-- to state rates but to no category rate.
--
-- Minimum filter: 200 delivered orders per group, the example in PRD section 6.
-- Groups below the minimum are not ranked. Late uses calendar dates per PRD
-- section 5: delivered date later than estimated date.

-- OUTPUT: q2_late_rate_by_category_state.csv
with delivered as (
    select
        order_id,
        customer_id,
        order_delivered_customer_date::date > order_estimated_delivery_date::date
            as is_late
    from orders
    where order_status = 'delivered'
      and order_delivered_customer_date is not null
),
category_orders as (
    select distinct
        d.order_id,
        d.is_late,
        coalesce(
            t.product_category_name_english,
            p.product_category_name
        ) as category_name
    from delivered d
    join order_items i using (order_id)
    left join products p using (product_id)
    left join product_category_name_translation t using (product_category_name)
    where p.product_category_name is not null
),
group_counts as (
    select
        'category' as dimension,
        category_name as group_name,
        count(*) as delivered_orders,
        count(*) filter (where is_late) as late_orders
    from category_orders
    group by category_name
    union all
    select
        'state',
        c.customer_state,
        count(*),
        count(*) filter (where d.is_late)
    from delivered d
    join customers c using (customer_id)
    group by c.customer_state
)
select
    dimension,
    group_name,
    delivered_orders,
    late_orders,
    round(100.0 * late_orders / delivered_orders, 2) as late_pct
from group_counts
where delivered_orders >= 200
order by dimension, late_pct desc, delivered_orders desc, group_name;
