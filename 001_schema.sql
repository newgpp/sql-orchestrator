-- 001_schema.sql
CREATE DATABASE IF NOT EXISTS demo_bi
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_general_ci;

USE demo_bi;

-- ========= 清理 =========

DROP TABLE IF EXISTS bridge_order_coupon;
DROP TABLE IF EXISTS dim_category;
DROP TABLE IF EXISTS dim_channel;
DROP TABLE IF EXISTS dim_coupon;
DROP TABLE IF EXISTS dim_customer;
DROP TABLE IF EXISTS dim_customer_address;
DROP TABLE IF EXISTS dim_product;
DROP TABLE IF EXISTS dim_region;
DROP TABLE IF EXISTS dim_store;
DROP TABLE IF EXISTS fact_order;
DROP TABLE IF EXISTS fact_order_item;
DROP TABLE IF EXISTS fact_payment;
DROP TABLE IF EXISTS fact_refund;
DROP TABLE IF EXISTS fact_shipment;

-- ========= 维表 =========

CREATE TABLE dim_region (
  region_id INT PRIMARY KEY AUTO_INCREMENT COMMENT '地域ID | role=dimension',
  country   VARCHAR(64) NOT NULL COMMENT '国家/地区（示例：CN）',
  province  VARCHAR(64) NOT NULL COMMENT '省/州（示例：广东）',
  city      VARCHAR(64) NOT NULL COMMENT '城市（示例：广州）',
  UNIQUE KEY uk_region (country, province, city)
) ENGINE=InnoDB COMMENT='地域维表：国家/省/市';

CREATE TABLE dim_channel (
  channel_id INT PRIMARY KEY AUTO_INCREMENT COMMENT '渠道ID | role=dimension',
  channel_name VARCHAR(64) NOT NULL COMMENT '渠道名称（示例：抖音广告）',
  channel_type VARCHAR(32) NOT NULL COMMENT '渠道类型（organic/ads/affiliate/offline）',
  UNIQUE KEY uk_channel (channel_name)
) ENGINE=InnoDB COMMENT='渠道维表：用户来源/投放渠道';

CREATE TABLE dim_store (
  store_id INT PRIMARY KEY AUTO_INCREMENT COMMENT '门店ID | role=dimension',
  store_name VARCHAR(128) NOT NULL COMMENT '门店名称',
  store_type VARCHAR(32) NOT NULL COMMENT '门店类型（online/offline）',
  region_id INT NOT NULL COMMENT '所在地域ID | ref=dim_region.region_id | join=N:1 | role=dimension',
  opened_at DATE NOT NULL COMMENT '开业日期',
  INDEX idx_store_region (region_id)
) ENGINE=InnoDB COMMENT='门店维表：线上/线下经营主体';

CREATE TABLE dim_category (
  category_id INT PRIMARY KEY AUTO_INCREMENT COMMENT '类目ID | role=dimension',
  parent_id INT NULL COMMENT '父类目ID | ref=dim_category.category_id | join=N:1 | role=dimension',
  category_name VARCHAR(128) NOT NULL COMMENT '类目名称',
  INDEX idx_cat_parent (parent_id)
) ENGINE=InnoDB COMMENT='品类维表：支持父子层级';

CREATE TABLE dim_product (
  product_id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '商品ID | role=dimension',
  sku        VARCHAR(64) NOT NULL COMMENT 'SKU编码（业务唯一）',
  product_name VARCHAR(256) NOT NULL COMMENT '商品名称',
  category_id INT NOT NULL COMMENT '类目ID | ref=dim_category.category_id | join=N:1 | role=dimension',
  brand      VARCHAR(64) NOT NULL COMMENT '品牌',
  unit_price DECIMAL(18,2) NOT NULL COMMENT '标准售价（可能与成交价不同）',
  status     VARCHAR(16) NOT NULL COMMENT '商品状态（active/inactive）',
  created_at DATETIME NOT NULL COMMENT '商品创建时间 | time=event',
  UNIQUE KEY uk_sku (sku),
  INDEX idx_prod_cat (category_id),
  INDEX idx_prod_brand (brand),
  INDEX idx_prod_created (created_at)
) ENGINE=InnoDB COMMENT='商品维表：SKU/品牌/类目/定价';

CREATE TABLE dim_customer (
  customer_id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '客户ID | role=dimension',
  customer_name VARCHAR(128) NOT NULL COMMENT '客户名称/昵称',
  email VARCHAR(128) NULL COMMENT '邮箱',
  phone VARCHAR(32) NULL COMMENT '手机号',
  gender VARCHAR(16) NULL COMMENT '性别（M/F/U）',
  birthday DATE NULL COMMENT '生日',
  register_channel_id INT NOT NULL COMMENT '注册渠道ID | ref=dim_channel.channel_id | join=N:1 | role=dimension',
  created_at DATETIME NOT NULL COMMENT '注册时间 | time=event',
  is_vip TINYINT NOT NULL DEFAULT 0 COMMENT '是否VIP（1=是）'
) ENGINE=InnoDB COMMENT='客户维表：注册信息与标签';

CREATE TABLE dim_customer_address (
  address_id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '地址ID | role=dimension',
  customer_id BIGINT NOT NULL COMMENT '客户ID | ref=dim_customer.customer_id | join=N:1 | role=dimension',
  region_id INT NOT NULL COMMENT '地址地域ID | ref=dim_region.region_id | join=N:1 | role=dimension',
  address_line VARCHAR(256) NOT NULL COMMENT '详细地址（示例）',
  is_default TINYINT NOT NULL DEFAULT 0 COMMENT '是否默认地址（1=默认）',
  created_at DATETIME NOT NULL COMMENT '创建时间 | time=event',
  INDEX idx_addr_customer (customer_id),
  INDEX idx_addr_region (region_id)
) ENGINE=InnoDB COMMENT='客户地址：一个客户可有多个地址';

-- ========= 事实表（订单域） =========

CREATE TABLE fact_order (
  order_id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '订单ID | role=fact',
  order_no VARCHAR(64) NOT NULL COMMENT '订单号（业务唯一）',

  customer_id BIGINT NOT NULL COMMENT '客户ID | ref=dim_customer.customer_id | join=N:1 | role=dimension',
  store_id INT NOT NULL COMMENT '门店ID | ref=dim_store.store_id | join=N:1 | role=dimension',
  channel_id INT NOT NULL COMMENT '渠道ID | ref=dim_channel.channel_id | join=N:1 | role=dimension',
  region_id INT NOT NULL COMMENT '地域ID | ref=dim_region.region_id | join=N:1 | role=dimension',

  order_status VARCHAR(16) NOT NULL COMMENT '订单状态（created/paid/shipped/completed/cancelled）',

  created_at DATETIME NOT NULL COMMENT '下单时间 | time=event',
  paid_at DATETIME NULL COMMENT '支付时间 | time=event',
  shipped_at DATETIME NULL COMMENT '发货时间 | time=event',
  completed_at DATETIME NULL COMMENT '完成时间 | time=event',

  order_amount DECIMAL(18,2) NOT NULL COMMENT '订单金额 | metric=order_amount | semantic=gmv',
  discount_amount DECIMAL(18,2) NOT NULL COMMENT '优惠金额',
  paid_amount DECIMAL(18,2) NOT NULL COMMENT '实付金额 | metric=paid_amount | semantic=sales',

  INDEX idx_order_created (created_at),
  INDEX idx_order_paid (paid_at),
  INDEX idx_order_customer (customer_id)
) ENGINE=InnoDB COMMENT='订单事实表：订单生命周期与金额口径';

CREATE TABLE fact_order_item (
  order_item_id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '订单明细ID | role=fact',
  order_id BIGINT NOT NULL COMMENT '订单ID | ref=fact_order.order_id | join=N:1 | role=fact',
  product_id BIGINT NOT NULL COMMENT '商品ID | ref=dim_product.product_id | join=N:1 | role=dimension',
  quantity INT NOT NULL COMMENT '购买数量',
  unit_price DECIMAL(18,2) NOT NULL COMMENT '成交单价（下单时价格）',
  item_amount DECIMAL(18,2) NOT NULL COMMENT '行金额（quantity*unit_price）',
  INDEX idx_item_order (order_id),
  INDEX idx_item_product (product_id)
) ENGINE=InnoDB COMMENT='订单明细：一单多行商品';

CREATE TABLE fact_payment (
  payment_id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '支付记录ID | role=fact',
  order_id BIGINT NOT NULL COMMENT '订单ID | ref=fact_order.order_id | join=N:1 | role=fact',
  pay_method VARCHAR(32) NOT NULL COMMENT '支付方式（wechat/alipay/card/bank）',
  pay_status VARCHAR(16) NOT NULL COMMENT '支付状态（success/failed）',
  pay_amount DECIMAL(18,2) NOT NULL COMMENT '支付金额',
  paid_at DATETIME NOT NULL COMMENT '支付完成时间 | time=event',
  transaction_no VARCHAR(64) NOT NULL COMMENT '支付流水号',
  INDEX idx_pay_order (order_id),
  INDEX idx_pay_paid (paid_at),
  INDEX idx_pay_method (pay_method)
) ENGINE=InnoDB COMMENT='支付事实：支付记录';

CREATE TABLE fact_refund (
  refund_id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '退款记录ID | role=fact',
  order_id BIGINT NOT NULL COMMENT '订单ID | ref=fact_order.order_id | join=N:1 | role=fact',
  refund_reason VARCHAR(64) NOT NULL COMMENT '退款原因（quality/delay/user_cancel/other）',
  refund_status VARCHAR(16) NOT NULL COMMENT '退款状态（requested/approved/rejected/refunded）',
  refund_amount DECIMAL(18,2) NOT NULL COMMENT '退款金额 | metric=refund_amount',
  requested_at DATETIME NOT NULL COMMENT '发起退款时间 | time=event',
  refunded_at DATETIME NULL COMMENT '退款完成时间 | time=event',
  INDEX idx_ref_order (order_id),
  INDEX idx_ref_status (refund_status),
  INDEX idx_ref_req (requested_at)
) ENGINE=InnoDB COMMENT='退款事实：退款申请与完成记录';

CREATE TABLE fact_shipment (
  shipment_id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '发货记录ID | role=fact',
  order_id BIGINT NOT NULL COMMENT '订单ID | ref=fact_order.order_id | join=N:1 | role=fact',
  carrier VARCHAR(32) NOT NULL COMMENT '承运商（sf/yto/jd/ems）',
  tracking_no VARCHAR(64) NOT NULL COMMENT '运单号',
  shipped_at DATETIME NOT NULL COMMENT '发货时间 | time=event',
  delivered_at DATETIME NULL COMMENT '签收时间 | time=event',
  ship_status VARCHAR(16) NOT NULL COMMENT '物流状态（shipped/delivered/lost）',
  INDEX idx_ship_order (order_id),
  INDEX idx_ship_shipped (shipped_at)
) ENGINE=InnoDB COMMENT='发货事实：物流与签收';

CREATE TABLE dim_coupon (
  coupon_id INT PRIMARY KEY AUTO_INCREMENT COMMENT '优惠券ID | role=dimension',
  coupon_code VARCHAR(32) NOT NULL COMMENT '券码（业务唯一）',
  coupon_type VARCHAR(16) NOT NULL COMMENT '类型（amount=固定金额, percent=百分比）',
  coupon_value DECIMAL(18,2) NOT NULL COMMENT '面值（amount=金额; percent=比例）',
  start_at DATETIME NOT NULL COMMENT '生效时间 | time=event',
  end_at DATETIME NOT NULL COMMENT '失效时间 | time=event',
  UNIQUE KEY uk_coupon_code (coupon_code),
  INDEX idx_coupon_time (start_at, end_at)
) ENGINE=InnoDB COMMENT='优惠券维表：满减/折扣';

CREATE TABLE bridge_order_coupon (
  id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '桥表ID | role=bridge',
  order_id BIGINT NOT NULL COMMENT '订单ID | ref=fact_order.order_id | join=N:1 | role=fact',
  coupon_id INT NOT NULL COMMENT '优惠券ID | ref=dim_coupon.coupon_id | join=N:1 | role=dimension',
  discount_amount DECIMAL(18,2) NOT NULL COMMENT '该券贡献的优惠金额'
) ENGINE=InnoDB COMMENT='订单-优惠券桥表：一单可使用多张券';
