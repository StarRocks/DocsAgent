#!/usr/bin/env python3
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
    'Storage',
    'Shared-data',
    'Data Lake',
    'Other'
]

CATALOGS_LANGS = {
    'Logging': {'en': 'Logging', 'zh': '日志记录', 'ja': 'ロギング'},
    'Server': {'en': 'Server', 'zh': '服务器', 'ja': 'サーバー'},
    'Metadata and cluster management': {'en': 'Metadata and cluster management', 'zh': '元数据和集群管理', 'ja': 'メタデータとクラスタ管理'},
    'User, role, and privilege': {'en': 'User, role, and privilege', 'zh': '用户、角色和权限', 'ja': 'ユーザー、役割、特権'},
    'Query engine': {'en': 'Query engine', 'zh': '查询引擎', 'ja': 'クエリエンジン'},
    'Loading and unloading': {'en': 'Loading and unloading', 'zh': '加载和卸载', 'ja': 'ロードとアンロード'},
    'Storage': {'en': 'Storage', 'zh': '存储', 'ja': 'ストレージ'},
    'Shared-data': {'en': 'Shared-data', 'zh': '共享数据', 'ja': '共有データ'},
    'Data Lake': {'en': 'Data Lake', 'zh': '数据湖', 'ja': 'データレイク'},
    'Other': {'en': 'Other', 'zh': '其他', 'ja': 'その他'}, 
}


def is_valid_catalog(catalog: str) -> bool:
    """Check if the given catalog is valid"""
    return catalog in VALID_CATALOGS


def get_default_catalog() -> str:
    """Get default catalog for unclassified items"""
    return 'Other'


@dataclass
class ConfigItem(DocumentableItem):
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
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConfigItem":
        return cls(**data)
    
    # ============ Additional Methods ============
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class VariableItem(DocumentableItem):
    """
    Variable configuration item model, extends DocumentableItem.
    
    Additional attributes or methods specific to variable configs can be added here.
    """
        # Required fields (from source code parsing)
    name: str
    show: str
    type: str
    defaultValue: str
    comment: str
    invisble: bool # true or false
    scope: str  # "Session" or "Global"
    
    # Optional fields with defaults
    useLocations: List[str] = field(default_factory=list)
    documents: Dict[str, str] = field(default_factory=dict)  # Multi-language documentation

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConfigItem":
        return cls(**data)
    
    # ============ Additional Methods ============
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)    