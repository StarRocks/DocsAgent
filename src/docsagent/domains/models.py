#!/usr/bin/env python3
# Copyright 2021-present StarRocks, Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Domain models for DocsAgent"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any

from docsagent.core.protocols import DocumentableItem
import json


# Valid configuration item catalogs
VALID_CATALOGS = [
    'Logging',
    'Server',
    'Metadata and cluster management',
    'User, role, and privilege',
    'Query engine',
    'Loading and unloading',
    'Statistic report',
    'Storage',
    'Shared-data',
    'Data Lake',
    'Loading',
    'Other'
]

CATALOGS_LANGS = {
    'Logging': {'en': 'Logging', 'zh': '日志', 'ja': 'ロギング'},
    'Server': {'en': 'Server', 'zh': '服务器', 'ja': 'サーバー'},
    'Metadata and cluster management': {'en': 'Metadata and cluster management', 'zh': '元数据与集群管理', 'ja': 'メタデータとクラスタ管理'},
    'User, role, and privilege': {'en': 'User, role, and privilege', 'zh': '用户，角色及权限', 'ja': 'ユーザー、役割、特権'},
    'Query engine': {'en': 'Query engine', 'zh': '查询引擎', 'ja': 'クエリエンジン'},
    'Loading': {'en': 'Loading', 'zh': '导入', 'ja': 'ロード'},
    'Loading and unloading': {'en': 'Loading and unloading', 'zh': '导入导出', 'ja': 'ロードとアンロード'},
    'Statistic report': {'en': 'Statistic report', 'zh': '统计信息', 'ja': '統計レポート'},
    'Storage': {'en': 'Storage', 'zh': '存储', 'ja': 'ストレージ'},
    'Shared-data': {'en': 'Shared-data', 'zh': '存算分离', 'ja': '共有データ'},
    'Data Lake': {'en': 'Data Lake', 'zh': '数据湖', 'ja': 'データレイク'},
    'Other': {'en': 'Other', 'zh': '其他', 'ja': 'その他'}, 
}


FUNCTION_CATALOGS = [
    "aggregate-functions",
    "array-functions",
    "binary-functions",
    "bit-functions",
    "bitmap-functions",
    "condition-functions",
    "crytographic-functions",
    "date-time-functions",
    "dict-functions",
    "hash-functions",
    "json-functions",
    "like-predicate-functions",
    "map-functions",
    "math-functions",
    "meta-functions",
    "percentile-functions",
    "scalar-functions",
    "spatial-functions",
    "string-functions",
    "struct-functions",
    "table-functions",
    "utility-functions",
]


def is_valid_catalog(catalog: str) -> bool:
    """Check if the given catalog is valid"""
    return catalog in VALID_CATALOGS


def get_default_catalog() -> str:
    """Get default catalog for unclassified items"""
    return 'Other'


@dataclass
class ConfigItem:
    """
    FE/BE configuration item model.
    
    Implements the DocumentableItem protocol for use with the generic
    documentation generation pipeline.
    
    Attributes:
        name: Configuration parameter name (unique identifier)
        type: Data type (e.g., 'int', 'string', 'boolean')
        defaultValue: Default value for the parameter
        comment: Source code comment/description
        isMutable: Whether the config can be changed at runtime ("true"/"false")
        scope: Where the config applies ("FE" for frontend, "BE" for backend)
        define: Definition location in source code
        useLocations: List of places where the config is used
        documents: Multi-language documentation (lang code -> content)
        catalog: Documentation category (e.g., 'Logging', 'Server', etc.)
    """
    # Required fields (from source code parsing)
    name: str
    type: str
    defaultValue: str
    comment: str
    isMutable: str  # "true" or "false"
    scope: str  # "FE" or "BE"
    define: str
    
    # Optional fields with defaults
    useLocations: List[str] = field(default_factory=list)
    documents: Dict[str, str] = field(default_factory=dict)  # Multi-language documentation
    catalog: str = None  # Options: VALID_CATALOGS
    version: List[str] = field(default_factory=list)  # Version introduced
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConfigItem":
        return cls(**data)
    
    # ============ Additional Methods ============
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass
class VariableItem:
    """
    Variable configuration item model, implements DocumentableItem protocol.
    
    Additional attributes or methods specific to variable configs can be added here.
    """
    # Required fields (from source code parsing)
    name: str
    show: str
    type: str
    defaultValue: str
    comment: str
    invisible: bool  # true or false
    scope: str  # "Session" or "Global"
    
    # Optional fields with defaults
    useLocations: List[str] = field(default_factory=list)
    documents: Dict[str, str] = field(default_factory=dict)  # Multi-language documentation
    version: List[str] = field(default_factory=list)  # Version introduced

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VariableItem":
        return cls(**data)
    
    # ============ Additional Methods ============
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)    
    
@dataclass
class FunctionItem:
    """
    Variable configuration item model, implements DocumentableItem protocol.
    
    Additional attributes or methods specific to variable configs can be added here.
    """
    # Required fields (from source code parsing)
    name: str
    alias: List[str]
    signature: List[str]
    catalog: str # e.g., "String Functions", "Math Functions"
    module: str # e.g., "Scalar", "Aggregate", "Window"
    implement_fns: List[str]
    testCases: List[str]
    
    # Optional fields with defaults
    useLocations: List[str] = field(default_factory=list)
    documents: Dict[str, str] = field(default_factory=dict)  # Multi-language documentation
    version: List[str] = field(default_factory=list)  # Version introduced

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FunctionItem":
        return cls(**data)
    
    # ============ Additional Methods ============
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)    