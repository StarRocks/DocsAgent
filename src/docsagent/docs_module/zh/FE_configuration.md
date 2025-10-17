---
displayed_sidebar: docs
keywords: ['Canshu']
---

import FEConfigMethod from '../../_assets/commonMarkdown/FE_config_method.mdx'

import AdminSetFrontendNote from '../../_assets/commonMarkdown/FE_config_note.mdx'

import StaticFEConfigNote from '../../_assets/commonMarkdown/StaticFE_config_note.mdx'

import EditionSpecificFEItem from '../../_assets/commonMarkdown/Edition_Specific_FE_Item.mdx'

# FE 配置项

<FEConfigMethod />

## 查看 FE 配置项

FE 启动后，您可以在 MySQL 客户端执行 ADMIN SHOW FRONTEND CONFIG 命令来查看参数配置。如果您想查看具体参数的配置，执行如下命令：

```SQL
 ADMIN SHOW FRONTEND CONFIG [LIKE "pattern"];
```

详细的命令返回字段解释，参见 [ADMIN SHOW CONFIG](../../sql-reference/sql-statements/cluster-management/config_vars/ADMIN_SHOW_CONFIG.md)。

:::note
只有拥有 `cluster_admin` 角色的用户才可以执行集群管理相关命令。
:::

## 配置 FE 参数

### 配置 FE 动态参数

您可以通过 [ADMIN SET FRONTEND CONFIG](../../sql-reference/sql-statements/cluster-management/config_vars/ADMIN_SET_CONFIG.md) 命令在线修改 FE 动态参数。

```sql
ADMIN SET FRONTEND CONFIG ("key" = "value");
```

<AdminSetFrontendNote />

### 配置 FE 静态参数

<StaticFEConfigNote />

## FE 参数描述

${outputs}


<EditionSpecificFEItem />
