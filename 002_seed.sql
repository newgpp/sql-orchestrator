-- 002_seed.sql  (B: ~1000 orders)
USE demo_bi;

-- ========= 重置数据（可重复执行） =========
SET FOREIGN_KEY_CHECKS = 0;

TRUNCATE TABLE bridge_order_coupon;
TRUNCATE TABLE fact_shipment;
TRUNCATE TABLE fact_refund;
TRUNCATE TABLE fact_payment;
TRUNCATE TABLE fact_order_item;
TRUNCATE TABLE fact_order;

TRUNCATE TABLE dim_customer_address;
TRUNCATE TABLE dim_customer;
TRUNCATE TABLE dim_product;
TRUNCATE TABLE dim_category;
TRUNCATE TABLE dim_store;
TRUNCATE TABLE dim_coupon;
TRUNCATE TABLE dim_channel;
TRUNCATE TABLE dim_region;

SET FOREIGN_KEY_CHECKS = 1;

-- ========= 维表：region（包含广东多城，方便“广东”场景） =========
INSERT INTO dim_region(country, province, city) VALUES
('CN','广东','广州'),
('CN','广东','深圳'),
('CN','广东','佛山'),
('CN','广东','东莞'),
('CN','北京','北京'),
('CN','上海','上海'),
('CN','浙江','杭州'),
('CN','江苏','南京'),
('CN','四川','成都'),
('CN','湖北','武汉');

-- ========= 维表：channel（给渠道做偏斜） =========
INSERT INTO dim_channel(channel_name, channel_type) VALUES
('自然流量','organic'),
('抖音广告','ads'),
('抖音直播','ads'),
('微信社群','affiliate'),
('线下地推','offline'),
('小红书','ads');

-- ========= 维表：category（两级） =========
INSERT INTO dim_category(parent_id, category_name) VALUES
(NULL,'3C数码'),
(1,'手机'),
(1,'电脑'),
(1,'配件'),
(NULL,'家居'),
(5,'清洁'),
(5,'收纳'),
(NULL,'食品'),
(8,'零食'),
(8,'饮料');

-- ========= 维表：store（每个 region 一个店） =========
INSERT INTO dim_store(store_name, store_type, region_id, opened_at)
SELECT
  CONCAT('店铺_', r.province, '_', r.city) AS store_name,
  CASE WHEN r.region_id % 2 = 0 THEN 'online' ELSE 'offline' END AS store_type,
  r.region_id,
  DATE('2022-01-01') + INTERVAL (r.region_id % 365) DAY
FROM dim_region r;

-- ========= 维表：coupon =========
INSERT INTO dim_coupon(coupon_code, coupon_type, coupon_value, start_at, end_at) VALUES
('CNY10','amount',10,'2024-01-01','2026-12-31'),
('CNY20','amount',20,'2024-01-01','2026-12-31'),
('CNY30','amount',30,'2024-01-01','2026-12-31'),
('PCT5','percent',5,'2024-01-01','2026-12-31'),
('PCT10','percent',10,'2024-01-01','2026-12-31');

-- ========= 维表：product（120 个，价格分层：低/中/高） =========
DROP PROCEDURE IF EXISTS seed_products;
DELIMITER $$
CREATE PROCEDURE seed_products(IN n INT)
BEGIN
  DECLARE i INT DEFAULT 1;
  DECLARE cat INT;
  DECLARE tier INT;
  DECLARE base_price DECIMAL(18,2);

  WHILE i <= n DO
    SET cat = 1 + FLOOR(RAND() * 10); -- category_id 1..10

    -- 价格分层：30% 低价、50% 中价、20% 高价
    SET tier = CASE
      WHEN RAND() < 0.30 THEN 1
      WHEN RAND() < 0.80 THEN 2
      ELSE 3
    END;

    SET base_price = CASE tier
      WHEN 1 THEN 10 + RAND()*190          -- 10~200
      WHEN 2 THEN 200 + RAND()*1800        -- 200~2000
      ELSE 2000 + RAND()*8000              -- 2000~10000
    END;

    INSERT INTO dim_product(sku, product_name, category_id, brand, unit_price, status, created_at)
    VALUES(
      CONCAT('SKU', LPAD(i, 6, '0')),
      CONCAT(
        ELT(1 + FLOOR(RAND()*6), '旗舰','经典','轻量','专业','家用','便携'),
        '_',
        ELT(1 + FLOOR(RAND()*6), 'Pro','Max','Mini','Plus','Air','Lite'),
        '_商品_',
        i
      ),
      cat,
      ELT(1 + FLOOR(RAND()*6), 'Apple','Huawei','Xiaomi','Lenovo','Philips','Sony'),
      ROUND(base_price, 2),
      IF(RAND() < 0.92, 'active', 'inactive'),
      '2024-01-01' + INTERVAL FLOOR(RAND()*365) DAY + INTERVAL FLOOR(RAND()*86400) SECOND
    );

    SET i = i + 1;
  END WHILE;
END$$
DELIMITER ;

CALL seed_products(120);

-- ========= 维表：customer（300 个，VIP ~18%，注册渠道偏斜） =========
DROP PROCEDURE IF EXISTS seed_customers;
DELIMITER $$
CREATE PROCEDURE seed_customers(IN n INT)
BEGIN
  DECLARE i INT DEFAULT 1;
  DECLARE ch INT;

  WHILE i <= n DO
    -- 渠道偏斜：ads 更高
    SET ch = CASE
      WHEN RAND() < 0.15 THEN 1   -- 自然
      WHEN RAND() < 0.60 THEN 2   -- 抖音广告
      WHEN RAND() < 0.70 THEN 3   -- 抖音直播
      WHEN RAND() < 0.90 THEN 4   -- 微信社群
      ELSE 6                       -- 小红书
    END;

    INSERT INTO dim_customer(customer_name, email, phone, gender, birthday, register_channel_id, created_at, is_vip)
    VALUES(
      CONCAT('客户_', i),
      CONCAT('user', i, '@demo.com'),
      CONCAT('13', LPAD(FLOOR(RAND()*1000000000), 9, '0')),
      ELT(1 + FLOOR(RAND()*3), 'M','F','U'),
      DATE('1985-01-01') + INTERVAL FLOOR(RAND()*12000) DAY,
      ch,
      '2024-01-01' + INTERVAL FLOOR(RAND()*500) DAY + INTERVAL FLOOR(RAND()*86400) SECOND,
      IF(RAND() < 0.18, 1, 0)
    );

    SET i = i + 1;
  END WHILE;
END$$
DELIMITER ;

CALL seed_customers(300);

-- ========= 地址：每客户 1 默认，50% 追加 1 非默认 =========
INSERT INTO dim_customer_address(customer_id, region_id, address_line, is_default, created_at)
SELECT
  c.customer_id,
  -- 地址地域偏斜：广东更高（便于“广东”问题高频）
  CASE
    WHEN RAND() < 0.55 THEN (SELECT region_id FROM dim_region WHERE province='广东' ORDER BY RAND() LIMIT 1)
    ELSE (SELECT region_id FROM dim_region WHERE province<>'广东' ORDER BY RAND() LIMIT 1)
  END,
  CONCAT('示例路 ', FLOOR(RAND()*200), ' 号'),
  1,
  c.created_at + INTERVAL FLOOR(RAND()*30) DAY
FROM dim_customer c;

INSERT INTO dim_customer_address(customer_id, region_id, address_line, is_default, created_at)
SELECT
  c.customer_id,
  (SELECT region_id FROM dim_region ORDER BY RAND() LIMIT 1),
  CONCAT('备选路 ', FLOOR(RAND()*200), ' 号'),
  0,
  c.created_at + INTERVAL 40 DAY
FROM dim_customer c
WHERE RAND() < 0.50;

-- ========= 订单 + 明细 + 支付 + 发货 + 退款 + 用券 =========
DROP PROCEDURE IF EXISTS seed_orders;
DELIMITER $$
CREATE PROCEDURE seed_orders(IN n INT)
BEGIN
  DECLARE i INT DEFAULT 1;

  DECLARE cust BIGINT;
  DECLARE region INT;
  DECLARE store INT;
  DECLARE ch INT;

  DECLARE st VARCHAR(16);
  DECLARE created DATETIME;
  DECLARE paid DATETIME;
  DECLARE shipped DATETIME;
  DECLARE completed DATETIME;

  DECLARE items INT;
  DECLARE j INT;
  DECLARE prod BIGINT;
  DECLARE qty INT;
  DECLARE price DECIMAL(18,2);

  DECLARE order_amount DECIMAL(18,2);
  DECLARE discount_amount DECIMAL(18,2);
  DECLARE paid_amount DECIMAL(18,2);

  DECLARE use_coupon TINYINT;
  DECLARE coupon_cnt INT;

  WHILE i <= n DO
    SET cust = 1 + FLOOR(RAND() * 300);

    -- 地域偏斜：广东订单更多（55%）
    IF RAND() < 0.55 THEN
      SET region = (SELECT region_id FROM dim_region WHERE province='广东' ORDER BY RAND() LIMIT 1);
    ELSE
      SET region = (SELECT region_id FROM dim_region WHERE province<>'广东' ORDER BY RAND() LIMIT 1);
    END IF;

    -- 渠道偏斜：ads 更高
    SET ch = CASE
      WHEN RAND() < 0.18 THEN 1
      WHEN RAND() < 0.55 THEN 2
      WHEN RAND() < 0.70 THEN 3
      WHEN RAND() < 0.88 THEN 4
      WHEN RAND() < 0.95 THEN 6
      ELSE 5
    END;

    -- store：同 region 选择一个
    SET store = (SELECT store_id FROM dim_store WHERE region_id = region LIMIT 1);

    -- 下单时间：2024全年随机
    SET created = '2024-01-01' + INTERVAL FLOOR(RAND()*365) DAY + INTERVAL FLOOR(RAND()*86400) SECOND;

    -- 状态分布：created 12% / paid 20% / shipped 23% / completed 40% / cancelled 5%
    SET st = CASE
      WHEN RAND() < 0.12 THEN 'created'
      WHEN RAND() < 0.32 THEN 'paid'
      WHEN RAND() < 0.55 THEN 'shipped'
      WHEN RAND() < 0.95 THEN 'completed'
      ELSE 'cancelled'
    END;

    SET paid = NULL;
    SET shipped = NULL;
    SET completed = NULL;

    IF st IN ('paid','shipped','completed') THEN
      SET paid = created + INTERVAL (5 + FLOOR(RAND()*72)) HOUR;
    END IF;
    IF st IN ('shipped','completed') THEN
      SET shipped = paid + INTERVAL (6 + FLOOR(RAND()*120)) HOUR;
    END IF;
    IF st IN ('completed') THEN
      SET completed = shipped + INTERVAL (8 + FLOOR(RAND()*240)) HOUR;
    END IF;

    -- 先插订单（金额后更新）
    INSERT INTO fact_order(
      order_no, customer_id, store_id, channel_id, region_id, order_status,
      created_at, paid_at, shipped_at, completed_at,
      order_amount, discount_amount, paid_amount
    ) VALUES(
      CONCAT('NO', DATE_FORMAT(created,'%Y%m%d'), LPAD(i, 8, '0')),
      cust, store, ch, region, st,
      created, paid, shipped, completed,
      0, 0, 0
    );

    SET @oid = LAST_INSERT_ID();

    -- 订单明细：1~4行，且 35% 概率 2~4 行（增强 join/聚合测试）
    IF RAND() < 0.35 THEN
      SET items = 2 + FLOOR(RAND()*3); -- 2..4
    ELSE
      SET items = 1 + FLOOR(RAND()*2); -- 1..2
    END IF;

    SET j = 1;
    SET order_amount = 0;

    WHILE j <= items DO
      SET prod = 1 + FLOOR(RAND() * 120);
      SET qty = 1 + FLOOR(RAND()*3);
      SET price = (SELECT unit_price FROM dim_product WHERE product_id = prod);

      INSERT INTO fact_order_item(order_id, product_id, quantity, unit_price, item_amount)
      VALUES(@oid, prod, qty, price, ROUND(qty*price,2));

      SET order_amount = order_amount + ROUND(qty*price,2);
      SET j = j + 1;
    END WHILE;

    -- 用券：35% 概率，且 10% 概率用 2 张（桥表覆盖）
    SET use_coupon = IF(RAND() < 0.35, 1, 0);
    SET discount_amount = 0;

    IF use_coupon = 1 THEN
      SET coupon_cnt = IF(RAND() < 0.10, 2, 1);

      SET @k = 1;
      WHILE @k <= coupon_cnt DO
        SET @cid = (SELECT coupon_id FROM dim_coupon ORDER BY RAND() LIMIT 1);
        SET @ctype = (SELECT coupon_type FROM dim_coupon WHERE coupon_id=@cid);
        SET @cval = (SELECT coupon_value FROM dim_coupon WHERE coupon_id=@cid);

        IF @ctype = 'amount' THEN
          SET @d = LEAST(@cval, order_amount * 0.30); -- 单券最多抵 30%
        ELSE
          SET @d = ROUND(order_amount * (@cval/100), 2);
        END IF;

        SET discount_amount = discount_amount + @d;

        INSERT INTO bridge_order_coupon(order_id, coupon_id, discount_amount)
        VALUES(@oid, @cid, @d);

        SET @k = @k + 1;
      END WHILE;

      -- 总折扣最多不超过订单金额的 50%
      IF discount_amount > order_amount * 0.50 THEN
        SET discount_amount = ROUND(order_amount * 0.50, 2);
      END IF;
    END IF;

    SET paid_amount = GREATEST(order_amount - discount_amount, 0);

    -- 金额口径：未支付/取消 paid_amount=0，其他为 paid_amount
    UPDATE fact_order
    SET order_amount = ROUND(order_amount,2),
        discount_amount = ROUND(discount_amount,2),
        paid_amount = ROUND(CASE WHEN st IN ('paid','shipped','completed') THEN paid_amount ELSE 0 END,2)
    WHERE order_id = @oid;

    -- payment：paid/shipped/completed 才会有（95% 成功；5% 失败样本）
    IF st IN ('paid','shipped','completed') THEN
      IF RAND() < 0.95 THEN
        INSERT INTO fact_payment(order_id, pay_method, pay_status, pay_amount, paid_at, transaction_no)
        VALUES(
          @oid,
          ELT(1+FLOOR(RAND()*4), 'wechat','alipay','card','bank'),
          'success',
          ROUND(paid_amount,2),
          paid,
          CONCAT('TX', LPAD(@oid, 10, '0'))
        );
      ELSE
        INSERT INTO fact_payment(order_id, pay_method, pay_status, pay_amount, paid_at, transaction_no)
        VALUES(
          @oid,
          ELT(1+FLOOR(RAND()*4), 'wechat','alipay','card','bank'),
          'failed',
          ROUND(paid_amount,2),
          paid,
          CONCAT('TXF', LPAD(@oid, 10, '0'))
        );
      END IF;
    END IF;

    -- shipment：shipped/completed 才会有（少量异常：lost）
    IF st IN ('shipped','completed') THEN
      INSERT INTO fact_shipment(order_id, carrier, tracking_no, shipped_at, delivered_at, ship_status)
      VALUES(
        @oid,
        ELT(1+FLOOR(RAND()*4), 'sf','yto','jd','ems'),
        CONCAT('TR', LPAD(@oid, 10, '0')),
        shipped,
        CASE WHEN st='completed' THEN completed ELSE NULL END,
        CASE
          WHEN RAND() < 0.02 THEN 'lost'
          WHEN st='completed' THEN 'delivered'
          ELSE 'shipped'
        END
      );
    END IF;

    -- refund：约 12% 的 paid/shipped/completed 有退款；其中 20% 为部分退款（更真实）
    IF st IN ('paid','shipped','completed') AND RAND() < 0.12 THEN
      SET @refund_amt = CASE
        WHEN RAND() < 0.20 THEN ROUND(paid_amount * (0.10 + RAND()*0.40), 2) -- 部分：10%~50%
        ELSE ROUND(paid_amount * (0.60 + RAND()*0.40), 2)                   -- 大额：60%~100%
      END;

      INSERT INTO fact_refund(order_id, refund_reason, refund_status, refund_amount, requested_at, refunded_at)
      VALUES(
        @oid,
        ELT(1+FLOOR(RAND()*4), 'quality','delay','user_cancel','other'),
        'refunded',
        @refund_amt,
        paid + INTERVAL (6+FLOOR(RAND()*240)) HOUR,
        paid + INTERVAL (12+FLOOR(RAND()*360)) HOUR
      );
    END IF;

    SET i = i + 1;
  END WHILE;
END$$
DELIMITER ;

CALL seed_orders(1000);
