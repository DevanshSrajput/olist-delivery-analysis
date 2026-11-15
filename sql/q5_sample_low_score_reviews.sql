-- Q5 sample: 100 low-score reviews with comment text (PRD section 8).
--
-- Population: review_score 1 or 2 and non-empty (non-whitespace) comment text.
-- Fixed seed: 42, DuckDB reservoir sampling. The seed makes the sample
-- repeatable across connections and reruns.
-- Distinct review_id: the review table contains duplicate review_id rows with
-- identical score and comment text. Sampling distinct reviews avoids handing
-- the same review to the labeler twice.
--
-- labels_human.csv is written by scripts/export_review_sample.py, which adds
-- an empty label column. Do not label in SQL.

select
    review_id,
    review_comment_message as comment
from (
    select distinct
        review_id,
        review_comment_message
    from order_reviews
    where review_score in (1, 2)
      and trim(review_comment_message) <> ''
)
using sample 100 rows (reservoir, 42)
order by review_id;
