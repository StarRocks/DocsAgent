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
