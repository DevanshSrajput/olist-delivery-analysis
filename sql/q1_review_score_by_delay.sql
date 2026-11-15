-- Q1: How does review score change with delay days? (PRD section 6)
--
-- Run with: uv run scripts/run_queries.py
--
-- Grain: one row per delivered order from analysis_orders. review_score is the
-- latest review for that order (see sql/01_analysis_orders.sql).
-- Buckets follow PRD section 6: early, on time, 1-3, 4-7, 8+ days late.
-- review_score is null for some delivered orders. Those orders stay in the
-- "orders" count but are excluded from the average and low-review share, whose
-- denominator is reviewed orders. Low review = score 1 or 2 (PRD section 5).

-- OUTPUT: q1_review_score_by_delay.csv
with bucketed as (
    select
        review_score,
        case
            when delay_days < 0 then 'early'
            when delay_days = 0 then 'on time'
            when delay_days between 1 and 3 then '1-3 days late'
            when delay_days between 4 and 7 then '4-7 days late'
            else '8+ days late'
        end as delay_bucket,
        case
            when delay_days < 0 then 1
            when delay_days = 0 then 2
            when delay_days between 1 and 3 then 3
            when delay_days between 4 and 7 then 4
            else 5
        end as bucket_order
    from analysis_orders
)
select
    delay_bucket,
    count(*) as orders,
    count(review_score) as reviewed_orders,
    round(avg(review_score), 2) as avg_review_score,
    count(*) filter (where review_score <= 2) as low_review_orders,
    round(
        100.0 * count(*) filter (where review_score <= 2)
        / nullif(count(review_score), 0),
        2
    ) as low_review_pct
from bucketed
group by delay_bucket, bucket_order
order by bucket_order;
