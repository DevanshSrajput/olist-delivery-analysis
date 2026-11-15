# PRD: E-commerce Delivery and Customer Experience Analysis (Olist)

**Author:** Devansh Singh
**Status:** Draft
**Last updated:** 2026-11-15
**Type:** Analytics case study (portfolio, public data)

> Everything here is a portfolio exercise on public data. It is framed as if for an outbound fulfilment team, but no company asked for it and no company data is used.

---

## 1. Objective

Find out how delivery performance affects customer satisfaction and repeat purchase in a real marketplace dataset, and turn the findings into recommendations with metrics that would confirm they worked.

## 2. Why this project

Outbound supply chain work is about getting orders fulfilled with speed and easy post-order experiences. A marketplace dataset with delivery dates, review scores and review text lets me practice the same chain of reasoning: spot friction, find the cause, propose a fix, define how to measure it.

## 3. Dataset

**Source:** Brazilian E-Commerce Public Dataset by Olist (Kaggle). Roughly 100k orders between 2016 and 2018.

**Tables used:**

| Table | Use |
|---|---|
| orders | Status and timestamps: purchase, approval, carrier handover, delivered, estimated delivery |
| order_items | Items, price, freight, seller per item |
| order_payments | Payment type, installments, value |
| order_reviews | Score (1 to 5), optional comment text, timestamps |
| customers | Customer location. `customer_id` is per order, `customer_unique_id` identifies a real person |
| sellers | Seller location |
| products | Category, dimensions, weight |
| product_category_name_translation | Portuguese to English categories |

## 4. Known limitations (state these in the final write-up)

1. **No returns data.** The dataset does not mark returns. Proxies: low review scores, cancellations, late deliveries. These are proxies and the write-up says so.
2. **Repeat purchase uses `customer_unique_id`.** Using `customer_id` would show almost no repeat customers, which is wrong.
3. **Delivery dates exist only for delivered orders.** Filter before computing delay.
4. **Many reviews have no text.** The LLM step covers only reviews with comments.
5. **Review text is Portuguese.** The model needs to handle it or translate first.
6. **Old data from one country.** Findings are illustrative. They do not predict any Indian marketplace.
7. **Review score is subjective** and affected by things unrelated to delivery.

## 5. Definitions (lock these before querying)

- **Late order:** `order_delivered_customer_date` later than `order_estimated_delivery_date`.
- **Delay days:** delivered date minus estimated date, in whole days. Negative means early.
- **Delivery time:** delivered date minus purchase date.
- **Low review:** score of 1 or 2.
- **Repeat customer:** a `customer_unique_id` with 2 or more delivered orders.
- **Analysis population:** orders with status `delivered` and a non-null delivered date, unless a query says otherwise.

## 6. Research questions

| # | Question | Method |
|---|---|---|
| Q1 | How does review score change with delay days? | Bucket delay (early, on time, 1-3 days late, 4-7, 8+). Average score and low-review share per bucket |
| Q2 | Which categories and customer states have the worst late rate? | Group by category and state, filter to groups with enough orders to matter (set a minimum, for example 200 orders) |
| Q3 | Do sellers differ in lateness, and how concentrated is the problem? | Late rate per seller with a minimum order count. Share of all late orders coming from the worst 10 percent of sellers |
| Q4 | Does a late delivery change the chance of a repeat purchase? | Cohort by first-order lateness. Share placing a second order |
| Q5 | What do unhappy customers actually complain about? | LLM classification of low-score review text, validated against my hand labels |

Add Q6 only if time remains: how accurate is the estimated delivery date by category and state, and is it padded?

## 7. Data quality checks (run before analysis, record results in README)

- Row counts per table after load.
- Row count of the joined orders table equals the count of distinct `order_id` after every join (catches duplicate-row bugs from multi-item orders and multiple reviews).
- Null rates on key date columns.
- Orders with delivered date earlier than purchase date.
- Orders with multiple reviews.
- Share of orders in each status.

Any exclusion gets documented with its count.

## 8. LLM classification protocol (Q5)

**Population:** reviews with score 1 or 2 and non-empty comment text.

**Taxonomy (v1, adjust after reading samples):**
- Late or never arrived
- Wrong item
- Damaged or defective
- Poor quality or not as described
- Seller or customer service
- Other

**Steps:**
1. Draw a random sample of 100 from the population with a fixed seed.
2. Hand-label all 100 before the model sees them. Save as `labels_human.csv`.
3. Run the model on the same 100. Save as `labels_model.csv`.
4. Compute accuracy and Cohen's kappa. Look at the confusion matrix. Read every disagreement.
5. Refine the prompt or taxonomy once. Rerun on the same 100 and report both rounds.
6. Only then classify the full population.
7. Cache outputs so reruns do not call the model again.

**Reporting rule:** the agreement number goes in the README, whatever it is. If it is poor, the write-up says the classification is rough and which categories to trust.

## 9. Deliverables

1. **Repo** `olist-delivery-analysis`:
   - `sql/` with one file per question and a comment explaining each
   - `notebooks/` for exploration and the LLM step
   - `data/` ignored by git, with instructions to download
   - `outputs/` with CSV extracts for the dashboard
   - `README.md`
2. **Tableau Public dashboard**, one page:
   - Review score by delay bucket
   - Late rate by category and by state
   - Complaint breakdown from Q5
   - Filter by state and category
3. **Findings doc**, one page, three findings. Each finding has the number, the likely cause, a recommended fix, a confirming metric and the main caveat.

## 10. Finding template (use for each)

- **Finding:** one sentence with the number.
- **Evidence:** query file and output.
- **Likely cause:** and how confident I am.
- **Recommendation:** what a fulfilment team could change.
- **Confirming metric and guardrail:** what moves if it worked, and what must not get worse.
- **Caveat:** correlation, proxies, dataset age.

## 11. Acceptance criteria

- [ ] Every number in the findings doc traces to a SQL file or notebook cell
- [ ] Join integrity checks documented and passing
- [ ] Limitations section is in the README, not hidden
- [ ] LLM agreement on the labeled sample is reported with kappa
- [ ] Dashboard is public and linked from the README
- [ ] A stranger can reproduce the outputs from the README in under 30 minutes

## 12. Risks

| Risk | Mitigation |
|---|---|
| Bad join inflates counts | Row-count assertions after each join |
| Free LLM rate limits | Batch, cache, use a small sample first |
| Tableau Desktop setup eats time | Use Tableau Public, fall back to Looker Studio if blocked, say so |
| Overclaiming causality | Language rule: "associated with", not "causes", unless the design supports it |

## 13. What I got wrong

`[FILL at the end. Required section.]`
