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

"""
Statistics Collection Module

Collects and reports execution statistics for DocsAgent including:
- Item counts from meta extraction
- Item counts from code parsing
- Document counts per language
- Agent and tool invocation statistics
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
from loguru import logger


@dataclass
class ExecutionStats:
    """Statistics for a single execution"""
    
    # Execution metadata
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    doc_type: str = ""  # fe_config, be_config, variables, functions
    
    # Item extraction statistics
    meta_items_count: int = 0  # Items loaded from meta files
    code_items_count: int = 0  # Items extracted from code parsing
    total_items: int = 0  # Total unique items
    
    # Document generation statistics
    docs_per_language: Dict[str, int] = field(default_factory=dict)  # {lang: count}
    
    # Agent invocation statistics
    agent_calls: Dict[str, int] = field(default_factory=dict)  # {agent_name: call_count}
    agent_tokens: Dict[str, Dict[str, int]] = field(default_factory=dict)  # {agent_name: {input: x, output: y}}
    
    # Tool invocation statistics
    tool_calls: Dict[str, int] = field(default_factory=dict)  # {tool_name: call_count}
    
    # Generated items tracking
    generated_items: List[str] = field(default_factory=list)  # List of item names that generated docs
    
    # Error tracking
    errors: List[str] = field(default_factory=list)
    
    def mark_complete(self):
        """Mark execution as complete"""
        self.end_time = datetime.now()
    
    def duration(self) -> float:
        """Get execution duration in seconds"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return (datetime.now() - self.start_time).total_seconds()
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration(),
            "doc_type": self.doc_type,
            "extraction": {
                "meta_items": self.meta_items_count,
                "code_items": self.code_items_count,
                "total_items": self.total_items,
            },
            "documents": {
                "by_language": self.docs_per_language,
                "total": sum(self.docs_per_language.values()),
            },
            "agents": {
                "calls": self.agent_calls,
                "total_calls": sum(self.agent_calls.values()),
                "tokens": self.agent_tokens,
            },
            "tools": {
                "calls": self.tool_calls,
                "total_calls": sum(self.tool_calls.values()),
            },
            "generated_items": {
                "items": self.generated_items,
                "count": len(self.generated_items),
            },
            "errors": self.errors,
        }
    
    def print_summary(self):
        """Print formatted summary to console"""
        logger.info("=" * 80)
        logger.info("EXECUTION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Document Type: {self.doc_type}")
        logger.info(f"Duration: {self.duration():.2f} seconds")
        logger.info("")
        
        # Item extraction
        logger.info("ITEM EXTRACTION:")
        logger.info(f"  ├─ Items from meta files: {self.meta_items_count}")
        logger.info(f"  ├─ Items from code parsing: {self.code_items_count}")
        logger.info(f"  └─ Total unique items: {self.total_items}")
        logger.info("")
        
        # Document generation
        logger.info("DOCUMENT GENERATION:")
        for lang, count in sorted(self.docs_per_language.items()):
            logger.info(f"  ├─ {lang.upper()}: {count} documents")
        logger.info(f"  └─ Total: {sum(self.docs_per_language.values())} documents")
        logger.info("")
        
        # Agent calls
        if self.agent_calls:
            logger.info("AGENT INVOCATIONS:")
            for agent, count in sorted(self.agent_calls.items(), key=lambda x: -x[1]):
                tokens_info = ""
                if agent in self.agent_tokens:
                    tokens = self.agent_tokens[agent]
                    tokens_info = f" (Input: {tokens.get('input', 0)}, Output: {tokens.get('output', 0)} tokens)"
                logger.info(f"  ├─ {agent}: {count} calls{tokens_info}")
            logger.info(f"  └─ Total: {sum(self.agent_calls.values())} calls")
            logger.info("")
        
        # Tool calls
        if self.tool_calls:
            logger.info("TOOL INVOCATIONS:")
            for tool, count in sorted(self.tool_calls.items(), key=lambda x: -x[1]):
                logger.info(f"  ├─ {tool}: {count} calls")
            logger.info(f"  └─ Total: {sum(self.tool_calls.values())} calls")
            logger.info("")
        
        # Generated items
        if self.generated_items:
            logger.info("GENERATED ITEMS:")
            logger.info(f"  ├─ Total: {len(self.generated_items)} items")
            # Show first 10 items as preview
            preview_count = min(10, len(self.generated_items))
            for i, item_name in enumerate(self.generated_items[:preview_count]):
                prefix = "  ├─" if i < preview_count - 1 else "  └─"
                logger.info(f"{prefix} {item_name}")
            if len(self.generated_items) > preview_count:
                logger.info(f"  ... and {len(self.generated_items) - preview_count} more items")
            logger.info("")
        
        # Errors
        if self.errors:
            logger.warning("ERRORS:")
            for error in self.errors:
                logger.warning(f"  ├─ {error}")
            logger.info("")
        
        logger.info("=" * 80)


class StatsCollector:
    """Global statistics collector singleton"""
    
    _instance: Optional['StatsCollector'] = None
    _stats: Optional[ExecutionStats] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def reset(cls, doc_type: str = ""):
        """Reset statistics for new execution"""
        cls._stats = ExecutionStats(doc_type=doc_type)
        logger.debug(f"Statistics collector initialized for doc_type: {doc_type}")
    
    @classmethod
    def get_stats(cls) -> ExecutionStats:
        """Get current statistics object"""
        if cls._stats is None:
            cls.reset()
        return cls._stats
    
    @classmethod
    def record_meta_items(cls, count: int):
        """Record items loaded from meta files"""
        stats = cls.get_stats()
        stats.meta_items_count = count
        logger.debug(f"Recorded {count} items from meta files")
    
    @classmethod
    def record_code_items(cls, count: int):
        """Record items extracted from code"""
        stats = cls.get_stats()
        stats.code_items_count = count
        logger.debug(f"Recorded {count} items from code parsing")
    
    @classmethod
    def record_total_items(cls, count: int):
        """Record total unique items"""
        stats = cls.get_stats()
        stats.total_items = count
        logger.debug(f"Recorded {count} total unique items")
    
    @classmethod
    def record_document(cls, language: str, count: int = 1):
        """Record generated document for a language"""
        stats = cls.get_stats()
        stats.docs_per_language[language] = stats.docs_per_language.get(language, 0) + count
        logger.debug(f"Recorded {count} document(s) for language: {language}")
    
    @classmethod
    def record_agent_call(cls, agent_name: str, input_tokens: int = 0, output_tokens: int = 0):
        """Record agent invocation"""
        stats = cls.get_stats()
        stats.agent_calls[agent_name] = stats.agent_calls.get(agent_name, 0) + 1
        
        if input_tokens > 0 or output_tokens > 0:
            if agent_name not in stats.agent_tokens:
                stats.agent_tokens[agent_name] = {"input": 0, "output": 0}
            stats.agent_tokens[agent_name]["input"] += input_tokens
            stats.agent_tokens[agent_name]["output"] += output_tokens
        
        logger.debug(f"Recorded agent call: {agent_name} (in: {input_tokens}, out: {output_tokens} tokens)")
    
    @classmethod
    def record_tool_call(cls, tool_name: str):
        """Record tool invocation"""
        stats = cls.get_stats()
        stats.tool_calls[tool_name] = stats.tool_calls.get(tool_name, 0) + 1
        logger.debug(f"Recorded tool call: {tool_name}")
    
    @classmethod
    def record_generated_item(cls, item_name: str):
        """Record an item that generated documentation"""
        stats = cls.get_stats()
        if item_name not in stats.generated_items:
            stats.generated_items.append(item_name)
            logger.debug(f"Recorded generated item: {item_name}")
    
    @classmethod
    def record_error(cls, error: str):
        """Record an error"""
        stats = cls.get_stats()
        stats.errors.append(error)
        logger.debug(f"Recorded error: {error}")
    
    @classmethod
    def finalize(cls) -> ExecutionStats:
        """Finalize and return statistics"""
        stats = cls.get_stats()
        stats.mark_complete()
        return stats
    
    @classmethod
    def save_to_file(cls, filepath: Path):
        """Save statistics to text file (same format as print_summary)"""
        stats = cls.get_stats()
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Build the same content as print_summary
        lines = []
        lines.append("=" * 80)
        lines.append("EXECUTION SUMMARY")
        lines.append("=" * 80)
        lines.append(f"Document Type: {stats.doc_type}")
        lines.append(f"Duration: {stats.duration():.2f} seconds")
        lines.append("")
        
        # Item extraction
        lines.append("ITEM EXTRACTION:")
        lines.append(f"  ├─ Items from meta files: {stats.meta_items_count}")
        lines.append(f"  ├─ Items from code parsing: {stats.code_items_count}")
        lines.append(f"  └─ Total unique items: {stats.total_items}")
        lines.append("")
        
        # Document generation
        lines.append("DOCUMENT GENERATION:")
        for lang, count in sorted(stats.docs_per_language.items()):
            lines.append(f"  ├─ {lang.upper()}: {count} documents")
        lines.append(f"  └─ Total: {sum(stats.docs_per_language.values())} documents")
        lines.append("")
        
        # Agent calls
        if stats.agent_calls:
            lines.append("AGENT INVOCATIONS:")
            for agent, count in sorted(stats.agent_calls.items(), key=lambda x: -x[1]):
                tokens_info = ""
                if agent in stats.agent_tokens:
                    tokens = stats.agent_tokens[agent]
                    tokens_info = f" (Input: {tokens.get('input', 0)}, Output: {tokens.get('output', 0)} tokens)"
                lines.append(f"  ├─ {agent}: {count} calls{tokens_info}")
            lines.append(f"  └─ Total: {sum(stats.agent_calls.values())} calls")
            lines.append("")
        
        # Tool calls
        if stats.tool_calls:
            lines.append("TOOL INVOCATIONS:")
            for tool, count in sorted(stats.tool_calls.items(), key=lambda x: -x[1]):
                lines.append(f"  ├─ {tool}: {count} calls")
            lines.append(f"  └─ Total: {sum(stats.tool_calls.values())} calls")
            lines.append("")
        
        # Generated items
        if stats.generated_items:
            lines.append("GENERATED ITEMS:")
            lines.append(f"  ├─ Total: {len(stats.generated_items)} items")
            # Show all items in file (not just preview)
            for i, item_name in enumerate(stats.generated_items):
                prefix = "  ├─" if i < len(stats.generated_items) - 1 else "  └─"
                lines.append(f"{prefix} {item_name}")
            lines.append("")
        
        # Errors
        if stats.errors:
            lines.append("ERRORS:")
            for error in stats.errors:
                lines.append(f"  ├─ {error}")
            lines.append("")
        
        lines.append("=" * 80)
        
        # Write to file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        logger.info(f"Statistics saved to: {filepath}")
    
    @classmethod
    def print_summary(cls):
        """Print execution summary"""
        stats = cls.get_stats()
        stats.print_summary()


# Convenience functions for easy access
def reset_stats(doc_type: str = ""):
    """Reset statistics for new execution"""
    StatsCollector.reset(doc_type)


def record_meta_items(count: int):
    """Record items loaded from meta files"""
    StatsCollector.record_meta_items(count)


def record_code_items(count: int):
    """Record items extracted from code"""
    StatsCollector.record_code_items(count)


def record_total_items(count: int):
    """Record total unique items"""
    StatsCollector.record_total_items(count)


def record_document(language: str, count: int = 1):
    """Record generated document"""
    StatsCollector.record_document(language, count)


def record_agent_call(agent_name: str, input_tokens: int = 0, output_tokens: int = 0):
    """Record agent invocation"""
    StatsCollector.record_agent_call(agent_name, input_tokens, output_tokens)


def record_tool_call(tool_name: str):
    """Record tool invocation"""
    StatsCollector.record_tool_call(tool_name)


def record_generated_item(item_name: str):
    """Record an item that generated documentation"""
    StatsCollector.record_generated_item(item_name)


def record_error(error: str):
    """Record an error"""
    StatsCollector.record_error(error)


def get_stats() -> ExecutionStats:
    """Get current statistics"""
    return StatsCollector.get_stats()


def finalize_stats() -> ExecutionStats:
    """Finalize and return statistics"""
    return StatsCollector.finalize()


def print_summary():
    """Print execution summary"""
    StatsCollector.print_summary()


def save_stats(filepath: Path):
    """Save statistics to file"""
    StatsCollector.save_to_file(filepath)
