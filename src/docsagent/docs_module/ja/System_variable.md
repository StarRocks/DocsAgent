---
displayed_sidebar: docs
---

# システム変数

StarRocks は、多くのシステム変数を提供しており、要件に応じて設定や変更が可能です。このセクションでは、StarRocks がサポートする変数について説明します。これらの変数の設定を確認するには、MySQL クライアントで [SHOW VARIABLES](sql-statements/cluster-management/config_vars/SHOW_VARIABLES.md) コマンドを実行します。また、[SET](sql-statements/cluster-management/config_vars/SET.md) コマンドを使用して、変数を動的に設定または変更することもできます。これらの変数は、システム全体でグローバルに、現在のセッションのみで、または単一のクエリ文でのみ有効にすることができます。

StarRocks の変数は、MySQL の変数セットを参照していますが、**一部の変数は MySQL クライアントプロトコルとの互換性のみを持ち、MySQL データベースでは機能しません**。

> **注意**
>
> どのユーザーでも SHOW VARIABLES を実行し、セッションレベルで変数を有効にする権限があります。ただし、SYSTEM レベルの OPERATE 権限を持つユーザーのみが、変数をグローバルに有効にすることができます。グローバルに有効な変数は、すべての将来のセッション（現在のセッションを除く）で有効になります。
>
> 現在のセッションの設定変更を行い、さらにその設定変更をすべての将来のセッションに適用したい場合は、`GLOBAL` 修飾子を使用せずに一度、使用してもう一度変更を行うことができます。例：
>
> ```SQL
> SET query_mem_limit = 137438953472; -- 現在のセッションに適用。
> SET GLOBAL query_mem_limit = 137438953472; -- すべての将来のセッションに適用。
> ```

## 変数の階層と種類

StarRocks は、グローバル変数、セッション変数、`SET_VAR` ヒントの3種類（レベル）の変数をサポートしています。それらの階層関係は次のとおりです：

* グローバル変数はグローバルレベルで有効であり、セッション変数や `SET_VAR` ヒントによって上書きされることがあります。
* セッション変数は現在のセッションでのみ有効であり、`SET_VAR` ヒントによって上書きされることがあります。
* `SET_VAR` ヒントは、現在のクエリ文でのみ有効です。

## 変数の表示

`SHOW VARIABLES [LIKE 'xxx']` を使用して、すべてまたは一部の変数を表示できます。例：

```SQL
-- システム内のすべての変数を表示。
SHOW VARIABLES;

-- 特定のパターンに一致する変数を表示。
SHOW VARIABLES LIKE '%time_zone%';
```

## 変数の設定

### 変数をグローバルまたは単一のセッションで設定

変数を **グローバルに** または **現在のセッションのみで** 有効に設定できます。グローバルに設定すると、新しい値はすべての将来のセッションで使用されますが、現在のセッションは元の値を使用します。「現在のセッションのみ」に設定すると、変数は現在のセッションでのみ有効になります。

`SET <var_name> = xxx;` で設定された変数は、現在のセッションでのみ有効です。例：

```SQL
SET query_mem_limit = 137438953472;

SET forward_to_master = true;

SET time_zone = "Asia/Shanghai";
```

`SET GLOBAL <var_name> = xxx;` で設定された変数はグローバルに有効です。例：

```SQL
SET GLOBAL query_mem_limit = 137438953472;
```

以下の変数はグローバルにのみ有効です。単一のセッションで有効にすることはできません。これらの変数には `SET GLOBAL <var_name> = xxx;` を使用する必要があります。単一のセッションでそのような変数を設定しようとすると（`SET <var_name> = xxx;`）、エラーが返されます。

${global_variables_list}

さらに、変数設定は定数式もサポートしています。例：

```SQL
SET query_mem_limit = 10 * 1024 * 1024 * 1024;
```

```SQL
SET forward_to_master = concat('tr', 'u', 'e');
```

### 単一のクエリ文で変数を設定

特定のクエリに対して変数を設定する必要がある場合があります。`SET_VAR` ヒントを使用することで、単一の文内でのみ有効なセッション変数を設定できます。

StarRocks は、以下の文で `SET_VAR` の使用をサポートしています：

- SELECT
- INSERT (v3.1.12 および v3.2.0 以降)
- UPDATE (v3.1.12 および v3.2.0 以降)
- DELETE (v3.1.12 および v3.2.0 以降)

`SET_VAR` は、上記のキーワードの後にのみ配置され、`/*+...*/` で囲まれます。

例：

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

単一の文で複数の変数を設定することもできます。例：

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

### ユーザーのプロパティとして変数を設定

[ALTER USER](../sql-reference/sql-statements/account-management/ALTER_USER.md) を使用して、セッション変数をユーザーのプロパティとして設定できます。この機能は v3.3.3 からサポートされています。

例：

```SQL
-- ユーザー jack に対してセッション変数 `query_timeout` を `600` に設定。
ALTER USER 'jack' SET PROPERTIES ('session.query_timeout' = '600');
```

## 変数の説明

変数は **アルファベット順** に説明されています。`global` ラベルが付いた変数はグローバルにのみ有効です。他の変数はグローバルまたは単一のセッションで有効にすることができます。

${variables_lists}
