#!/usr/bin/env python3

from dataclasses import dataclass, field, asdict
from typing import List
import json


@dataclass
class ConfigItem:
    """FE/BE configuration item model - simple data container (POD)"""
    name: str
    type: str
    defaultValue: str
    comment: str
    isMutable: str  # "true" or "false"
    scope: str  # "FE" or "BE"
    file_path: str
    line_number: int
    useLocations: List[str] = field(default_factory=list)
    documents: str = ""
    catalog: str = "" # Options: []
    
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
