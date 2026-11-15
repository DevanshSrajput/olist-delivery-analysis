-- Q3: Do sellers differ in lateness, and how concentrated is the problem?
-- (PRD section 6)
--
-- Run with: uv run scripts/run_queries.py
--
-- Grain: one row per distinct (seller, order) delivered exposure. A multi-item
-- order counts once for a seller; a multi-seller order counts once for each
-- seller involved.
--
-- Minimum filter: 50 delivered seller-order exposures per seller. 425 of the
-- 2,970 sellers with delivered orders pass; smaller sellers are excluded from
-- the per-seller ranking because their rates are too noisy.
--
-- Worst decile: among qualifying sellers, rank by late rate descending, then
-- late_orders descending, then seller_id, and take the top ceil(10%). The
-- concentration share uses distinct order_ids: it is the share of all late
-- orders that involve at least one worst-decile seller. Late seller-order
-- exposures are kept separately because they are the denominator for seller
-- late rates; a multi-seller late order contributes an exposure to each seller.

-- OUTPUT: q3_seller_late_rate.csv
with delivered as (
    select
        order_id,
        order_delivered_customer_date::date > order_estimated_delivery_date::date
            as is_late
    from orders
    where order_status = 'delivered'
      and order_delivered_customer_date is not null
),
seller_orders as (
    select distinct
        i.seller_id,
        d.order_id,
        d.is_late
    from delivered d
    join order_items i using (order_id)
),
seller_stats as (
    select
        seller_id,
        count(*) as delivered_orders,
        count(*) filter (where is_late) as late_orders,
        round(100.0 * count(*) filter (where is_late) / count(*), 2) as late_pct
    from seller_orders
    group by seller_id
)
select seller_id, delivered_orders, late_orders, late_pct
from seller_stats
where delivered_orders >= 50
order by late_pct desc, late_orders desc, seller_id;

-- OUTPUT: q3_seller_concentration.csv
with delivered as (
    select
        order_id,
        order_delivered_customer_date::date > order_estimated_delivery_date::date
            as is_late
    from orders
    where order_status = 'delivered'
      and order_delivered_customer_date is not null
),
seller_orders as (
    select distinct
        i.seller_id,
        d.order_id,
        d.is_late
    from delivered d
    join order_items i using (order_id)
),
seller_stats as (
    select
        seller_id,
        count(*) as delivered_orders,
        count(*) filter (where is_late) as late_orders,
        100.0 * count(*) filter (where is_late) / count(*) as late_pct
    from seller_orders
    group by seller_id
),
qualifying as (
    select *
    from seller_stats
    where delivered_orders >= 50
),
ranked as (
    select
        q.*,
        row_number() over (
            order by late_pct desc, late_orders desc, seller_id
        ) as seller_rank,
        count(*) over () as qualifying_sellers
    from qualifying q
),
selected as (
    select
        r.*,
        cast(ceil(0.1 * r.qualifying_sellers) as integer) as worst_seller_count
    from ranked r
),
worst_sellers as (
    select seller_id
    from selected
    where seller_rank <= worst_seller_count
),
totals as (
    select
        (select count(*) from seller_stats) as sellers_all,
        (select count(*) from qualifying) as sellers_meeting_minimum,
        (select max(worst_seller_count) from selected) as worst_decile_sellers,
        (select count(*) from seller_orders) as seller_order_exposures_all,
        (select count(*) from seller_orders where is_late)
            as late_seller_order_exposures_all,
        (select count(distinct order_id) from seller_orders where is_late)
            as late_orders_all,
        (
            select count(distinct so.order_id)
            from seller_orders so
            join qualifying q using (seller_id)
            where so.is_late
        ) as late_orders_qualifying
),
worst as (
    select
        sum(delivered_orders) filter (
            where seller_rank <= worst_seller_count
        ) as seller_order_exposures_worst_decile,
        sum(late_orders) filter (
            where seller_rank <= worst_seller_count
        ) as late_seller_order_exposures_worst_decile,
        min(late_pct) filter (
            where seller_rank <= worst_seller_count
        ) as worst_decile_min_late_pct,
        min(delivered_orders) filter (
            where seller_rank <= worst_seller_count
        ) as worst_decile_min_orders,
        (
            select count(distinct so.order_id)
            from seller_orders so
            join worst_sellers w using (seller_id)
            where so.is_late
        ) as late_orders_worst_decile
    from selected
)
select
    t.sellers_all,
    t.sellers_meeting_minimum,
    t.worst_decile_sellers,
    round(
        100.0 * w.late_seller_order_exposures_worst_decile
        / w.seller_order_exposures_worst_decile,
        2
    ) as worst_decile_late_pct,
    w.late_orders_worst_decile,
    t.late_orders_all,
    round(
        100.0 * w.late_orders_worst_decile / nullif(t.late_orders_all, 0),
        2
    ) as share_of_all_late_orders_pct,
    t.late_orders_qualifying,
    round(
        100.0 * w.late_orders_worst_decile / nullif(t.late_orders_qualifying, 0),
        2
    ) as share_of_qualifying_late_orders_pct,
    w.seller_order_exposures_worst_decile,
    w.late_seller_order_exposures_worst_decile,
    t.seller_order_exposures_all,
    t.late_seller_order_exposures_all,
    round(w.worst_decile_min_late_pct, 2) as worst_decile_min_late_pct,
    w.worst_decile_min_orders
from totals t
cross join worst w;
