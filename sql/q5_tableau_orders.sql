-- Tableau export: delivered-order analysis table plus the Q5 complaint category.
--
-- Grain: one row per delivered order from analysis_orders.
-- The review join uses the same ranking as sql/01_analysis_orders.sql, so
-- complaint_category belongs to the latest review (the review_score already
-- stored in analysis_orders). Orders whose latest review is not a low-score
-- review with comment text get a blank/NULL category.
--
-- Run with:
--   uv run scripts/run_queries.py --sql sql/q5_tableau_orders.sql
--
-- The label file is written by:
--   uv run scripts/classify_reviews.py --input data/q5_full_population.csv \
--       --output outputs/q5_model_labels_full.csv

-- OUTPUT: tableau_orders_with_complaints.csv
with ranked_reviews as (
    select
        order_id,
        review_id,
        review_score,
        review_comment_message,
        row_number() over (
            partition by order_id
            order by review_answer_timestamp desc,
                     review_creation_date desc,
                     review_id
        ) as review_rank
    from order_reviews
),
latest_review as (
    select
        order_id,
        review_id,
        review_score,
        review_comment_message
    from ranked_reviews
    where review_rank = 1
),
labels as (
    select
        review_id,
        label as complaint_category
    from read_csv_auto('outputs/q5_model_labels_full.csv')
)
select
    a.order_id,
    a.customer_unique_id,
    a.customer_state,
    a.delay_days,
    a.delivery_time_days,
    a.is_late,
    a.review_score,
    a.category_en,
    a.seller_id,
    l.complaint_category
from analysis_orders a
left join latest_review r using (order_id)
left join labels l using (review_id)
order by a.order_id;
