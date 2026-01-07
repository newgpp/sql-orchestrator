### 一个将自然语言问题转化为可解释、可校验 SQL 的后端服务，负责语义解析、数据库元数据检索、SQL 生成与交互式澄清。


sql-orchestrator 是一个基于 Python 的后端服务，用于将用户的自然语言查询逐步转换为结构化 SQL。
它通过数据库表/字段/关系的元数据检索、规则校验和必要的交互式追问，生成安全、可理解、可复查的 SQL 查询结果。
该服务本身不直接执行 SQL，专注于生成与决策逻辑的编排（orchestration）。

### 核心职责：

- 解析用户查询意图（IR）

- 检索相关数据库表、字段和关联关系

- 生成并校验 SQL

- 在信息不充分时发起结构化追问

- 输出 SQL 及其生成依据（explanation）


### 环境&启动

- 开发环境 python3.8+

```shell
# 创建并激活虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

```

- 启动命令

```shell

uvicorn sql_orchestrator.main:app --reload --port 10072

```

### 测试数据

- 启动mariadb

```shell
docker network create infra-net

docker run -d \
  --name mariadb \
  --network infra-net \
  --restart unless-stopped \
  -p 3306:3306 \
  -e MYSQL_ROOT_PASSWORD=123456 \
  -v mariadb-data:/var/lib/mysql \
  -v mariadb-config:/etc/mysql/conf.d \
  mariadb:10.11

```

- 初始化测试数据

```shell

docker exec -i mariadb mariadb -uroot -p123456 < 001_schema.sql
docker exec -i mariadb mariadb -uroot -p123456 < 002_seed.sql


```

- 检查数据分布

```shell
003_chcek.sql
```

### 抽取 Cards

```shell
# 抽取
pytest tests/test_export_schema_cards.py -s

# 校验 schema
# 注释 ref 写错、表名/字段名拼错，立即爆出来
# join 写成 n:1 或 N-1 这种不规范，直接报错
# role 缺失给 warning（不影响导出，但提醒你补）
pytest tests/test_validate_schema_cards.py -s


# 校验 Join Path 可达性校验
# 能否通过 relations 连通到所有 dimension
# 是否存在 孤立维表
# 是否存在 断链字段（ref 正确，但整体不可达）
pytest tests/test_validate_join_cards.py -s

```