-- Q4: Does a late delivery change the chance of a repeat purchase?
-- (PRD section 6)
--
-- Run with: uv run scripts/run_queries.py
--
-- Grain: one row per customer_unique_id with at least one delivered order.
-- The first order is the earliest delivered order by purchase timestamp, with
-- order_id as the tie-break. The cohort is whether that first order was late,
-- using the calendar-date definition from PRD section 5.
-- Repeat customer follows PRD section 5: 2 or more delivered orders.
-- The "all customers" row is the baseline across both cohorts.

-- OUTPUT: q4_repeat_purchase_by_first_order_lateness.csv
with delivered as (
    select
        o.order_id,
        c.customer_unique_id,
        o.order_purchase_timestamp,
        o.order_delivered_customer_date::date > o.order_estimated_delivery_date::date
            as is_late
    from orders o
    join customers c using (customer_id)
    where o.order_status = 'delivered'
      and o.order_delivered_customer_date is not null
),
ranked as (
    select
        *,
        row_number() over (
            partition by customer_unique_id
            order by order_purchase_timestamp, order_id
        ) as order_rank,
        count(*) over (partition by customer_unique_id) as delivered_orders
    from delivered
),
first_orders as (
    select customer_unique_id, is_late, delivered_orders
    from ranked
    where order_rank = 1
),
cohorts as (
    select
        case when is_late then 'late' else 'on time' end as first_order_cohort,
        count(*) as customers,
        count(*) filter (where delivered_orders >= 2) as repeat_customers,
        round(
            100.0 * count(*) filter (where delivered_orders >= 2) / count(*),
            2
        ) as repeat_pct,
        round(avg(delivered_orders), 2) as avg_delivered_orders
    from first_orders
    group by is_late
)
select first_order_cohort, customers, repeat_customers, repeat_pct,
       avg_delivered_orders
from cohorts
union all
select
    'all customers',
    count(*),
    count(*) filter (where delivered_orders >= 2),
    round(100.0 * count(*) filter (where delivered_orders >= 2) / count(*), 2),
    round(avg(delivered_orders), 2)
from first_orders
order by case first_order_cohort
    when 'late' then 1
    when 'on time' then 2
    else 3
end;
