---
displayed_sidebar: docs
keywords: ['session','variable']
---

# 系统变量

StarRocks 提供多个系统变量（system variables），方便您根据业务情况进行调整。本文介绍 StarRocks 支持的变量。您可以在 MySQL 客户端通过命令 [SHOW VARIABLES](sql-statements/cluster-management/config_vars/SHOW_VARIABLES.md) 查看当前变量。也可以通过 [SET](sql-statements/cluster-management/config_vars/SET.md) 命令动态设置或者修改变量。您可以设置变量在系统全局 (global) 范围内生效、仅在当前会话 (session) 中生效、或者仅在单个查询语句中生效。

StarRocks 中的变量参考 MySQL 中的变量设置，但**部分变量仅用于兼容 MySQL 客户端协议，并不产生其在 MySQL 数据库中的实际意义**。

> **说明**
>
> 任何用户都有权限通过 SHOW VARIABLES 查看变量。任何用户都有权限设置变量在 Session 级别生效。只有拥有 System 级 OPERATE 权限的用户才可以设置变量为全局生效。设置全局生效后，后续所有新的会话都会使用新配置，当前会话仍然使用老的配置。

## 查看变量

可以通过 `SHOW VARIABLES [LIKE 'xxx'];` 查看所有或指定的变量。例如：

```SQL

-- 查看系统中所有变量。
SHOW VARIABLES;

-- 查看符合匹配规则的变量。
SHOW VARIABLES LIKE '%time_zone%';
```

## 变量层级和类型

StarRocks 支持三种类型（层级）的变量：全局变量、Session 变量和 `SET_VAR` Hint。它们的层级关系如下：

* 全局变量在全局级别生效，可以被 Session 变量和 `SET_VAR` Hint 覆盖。
* Session 变量仅在当前会话中生效，可以被 `SET_VAR` Hint 覆盖。
* `SET_VAR` Hint 仅在当前查询语句中生效。

## 设置变量

### 设置变量全局生效或在会话中生效

变量一般可以设置为**全局**生效或**仅当前会话**生效。设置为全局生效后，**后续所有新的会话**连接中会使用新设置的值，当前会话还会继续使用之前设置的值；设置为仅当前会话生效时，变量仅对当前会话产生作用。

通过 `SET <var_name> = xxx;` 语句设置的变量仅在当前会话生效。如：

```SQL
SET query_mem_limit = 137438953472;

SET forward_to_master = true;

SET time_zone = "Asia/Shanghai";
```

通过 `SET GLOBAL <var_name> = xxx;` 语句设置的变量全局生效。如：

 ```SQL
SET GLOBAL query_mem_limit = 137438953472;
 ```

以下变量仅支持全局生效，不支持设置为会话级别生效。您必须使用 `SET GLOBAL <var_name> = xxx;`，不能使用 `SET <var_name> = xxx;`，否则返回错误。

${global_variables_list}

Session 级变量既可以设置全局生效也可以设置 session 级生效。

此外，变量设置也支持常量表达式，如：

```SQL
SET query_mem_limit = 10 * 1024 * 1024 * 1024;
```

```SQL
SET forward_to_master = concat('tr', 'u', 'e');
```

### 设置变量在单个查询语句中生效

在一些场景中，可能需要对某些查询专门设置变量。可以使用 SET_VAR 提示 (Hint) 在查询中设置仅在单个语句内生效的会话变量。

当前，StarRocks 支持在以下语句中使用 `SET_VAR` Hint：

- SELECT
- INSERT（自 v3.1.12 和 v3.2.0 起支持）
- UPDATE（自 v3.1.12 和 v3.2.0 起支持）
- DELETE（自 v3.1.12 和 v3.2.0 起支持）

`SET_VAR` 只能跟在以上关键字之后，必须以 `/*+` 开头，以 `*/` 结束。

举例：

```sql
SELECT /*+ SET_VAR(query_mem_limit = 8589934592) */ name FROM people ORDER BY name;

SELECT /*+ SET_VAR(query_timeout = 1) */ sleep(3);

UPDATE /*+ SET_VAR(insert_timeout=100) */ tbl SET c1 = 2 WHERE c1 = 1;

DELETE /*+ SET_VAR(query_mem_limit = 8589934592) */
FROM my_table PARTITION p1
WHERE k1 = 3;

INSERT /*+ SET_VAR(insert_timeout = 10000000) */
INTO insert_wiki_edit
    SELECT * FROM FILES(
        "path" = "s3://inserttest/parquet/insert_wiki_edit_append.parquet",
        "format" = "parquet",
        "aws.s3.access_key" = "XXXXXXXXXX",
        "aws.s3.secret_key" = "YYYYYYYYYY",
        "aws.s3.region" = "us-west-2"
);
```

StarRocks 同时支持在单个语句中设置多个变量，参考如下示例：

```sql
SELECT /*+ SET_VAR
  (
  exec_mem_limit = 515396075520,
  query_timeout=10000000,
  batch_size=4096,
  parallel_fragment_exec_instance_num=32
  )
  */ * FROM TABLE;
```

### 设置变量为用户属性

您可以通过 [ALTER USER](../sql-reference/sql-statements/account-management/ALTER_USER.md) 将 Session 变量设置为用户属性该功能自 v3.3.3 起支持。

示例：

```SQL
-- 设置用户 jack 的 Session 变量 `query_timeout` 为 `600`。
ALTER USER 'jack' SET PROPERTIES ('session.query_timeout' = '600');
```

## 支持的变量

本节以字母顺序对变量进行解释。带 `global` 标记的变量为全局变量，仅支持全局生效。其余变量既可以设置全局生效，也可设置会话级别生效。

${variables_lists}
