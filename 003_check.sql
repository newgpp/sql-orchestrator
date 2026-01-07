USE demo_bi;

SELECT COUNT(*) orders FROM fact_order;
SELECT order_status, COUNT(*) cnt FROM fact_order GROUP BY order_status;

SELECT
  SUM(order_amount) gmv,
  SUM(paid_amount) sales,
  SUM(discount_amount) discount
FROM fact_order;

SELECT r.province, COUNT(*) cnt
FROM fact_order o
JOIN dim_region r ON o.region_id = r.region_id
GROUP BY r.province
ORDER BY cnt DESC;

SELECT COUNT(*) payments, SUM(pay_status='failed') failed
FROM fact_payment;

SELECT COUNT(*) refunds, AVG(refund_amount) avg_refund
FROM fact_refund;

SELECT
  COUNT(*) coupon_orders
FROM bridge_order_coupon;
