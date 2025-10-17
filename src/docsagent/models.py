#!/usr/bin/env python3

from dataclasses import dataclass, field, asdict
from typing import List
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
    'Other': {'en': 'Other', 'zh': '其他', 'ja': 'その他'}, 
}


def is_valid_catalog(catalog: str) -> bool:
    """Check if the given catalog is valid"""
    return catalog in VALID_CATALOGS


def get_default_catalog() -> str:
    """Get default catalog for unclassified items"""
    return 'Other'


@dataclass
class ConfigItem:
    """FE/BE configuration item model - simple data container (POD)"""
    name: str
    type: str
    defaultValue: str
    comment: str
    isMutable: str  # "true" or "false"
    scope: str  # "FE" or "BE"
    define: str
    useLocations: List[str] = field(default_factory=list)
    # key: str, lang; value: str, document content
    documents: dict = field(default_factory=dict)
    # Options: ['Logging', 'Server', 'Metadata and cluster management', 'User, role, and privilege', 'Query engine', 'Loading and unloading', 'Storage', 'Shared-data', 'Other']
    catalog: str = None
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "ConfigItem":
        """Create instance from dict"""
        return cls(**data)
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
