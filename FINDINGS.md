# Findings: Olist Delivery and Customer Experience

One page, three findings. All numbers are from the committed CSV outputs; the analysis population is delivered orders with a non-null delivered date. Limitations are in [README.md](README.md#limitations).

## 1. Late delivery is associated with much lower review scores

- **Finding:** Orders delivered 8+ days late have a 79.29% low-review share and a 1.70 average review score, versus 9.22% and 4.29 for early orders.
- **Evidence:** `sql/q1_review_score_by_delay.sql` -> `outputs/q1_review_score_by_delay.csv`. The 8+ bucket contains 2,862 orders and 2,781 reviewed orders; the early bucket contains 88,644 orders and 88,163 reviewed orders.
- **Likely cause:** Missed delivery promises are associated with dissatisfaction; confidence is high for the association and low for causality.
- **Recommendation:** Tighten promised dates and carrier handoff for high-risk lanes, and send a proactive delay update before the promise date.
- **Confirming metric and guardrail:** Low-review share and average score in the late buckets should improve; on-time rate and delivery cost must not get worse.
- **Caveat:** Observational data; review scores are subjective and can reflect product or service issues; the data is old and from one country.

## 2. Late/never arrived and wrong item dominate low-score complaints

- **Finding:** Late/never arrived (3,461) and wrong item (2,520) account for 5,981 of 9,234 categorized low-score complaints (64.8%).
- **Evidence:** `sql/q5_tableau_orders.sql` -> `outputs/tableau_orders_with_complaints.csv`, using labels from `outputs/q5_model_labels_full.csv`. Q5 sample agreement is 80/100, accuracy 0.8000, Cohen's kappa 0.7335 under the documented crosswalk.
- **Likely cause:** Fulfilment reliability and item-accuracy failures; confidence is moderate because the labels are model-generated and validated on 100 reviews.
- **Recommendation:** Prioritize delivery-promise reliability and a second item check at packing for high-risk categories; route wrong-item complaints to seller coaching.
- **Confirming metric and guardrail:** The share of complaints in these two categories should fall; other complaint categories and review scores must not get worse.
- **Caveat:** Only 9,234 of 12,272 low-score delivered orders (75.2%) have a categorized complaint; the rest lack comment text or a label. The taxonomy is coarse and the labels are not human-verified at full scale.

## 3. Late orders concentrate in a small group of sellers

- **Finding:** The worst 43 of 425 sellers with at least 50 delivered seller-order exposures account for 749 late orders - 15.07% of late orders from qualifying sellers and 11.46% of all 6,534 late orders.
- **Evidence:** `sql/q3_seller_lateness.sql` -> `outputs/q3_seller_concentration.csv`. There are 2,970 sellers with delivered orders; 425 meet the 50-exposure minimum; the worst-decile late rate is 15.28%.
- **Likely cause:** A minority of sellers have operational or carrier-handoff problems; confidence is moderate because this is an association and small sellers are excluded.
- **Recommendation:** Put the 43 sellers on a late-rate improvement plan; review carrier handoff and dispatch SLA weekly.
- **Confirming metric and guardrail:** Their late rate and share of late orders should fall; order volume, seller retention and customer review score must not get worse.
- **Caveat:** The 50-exposure minimum excludes small sellers; a multi-seller order can contribute to more than one seller; the design is observational.

---

Source: Olist public e-commerce dataset (Kaggle). The Q4 repeat-purchase check was weak (2.52% late vs 3.04% on-time) and is not one of the three findings. See [README.md](README.md) for the full limitations.
