"""VariablesDocGenerator: Generate English docs using LLM"""

from typing import Optional
from loguru import logger
from langchain_core.language_models.chat_models import BaseChatModel

from docsagent.core.protocols import DocGenerator
from docsagent.domains.models import ConfigItem
from docsagent.agents.config_doc_agent import ConfigDocAgent


class VariablesDocGenerator(DocGenerator):
    """Generate documentation using LLM (implements DocGenerator protocol)"""
    
    def __init__(self):
        self.agent = ConfigDocAgent()
        logger.debug("VariablesDocGenerator initialized")
    
    def generate(self, item: ConfigItem) -> str:
        """Generate English documentation for a config item"""
        logger.debug(f"Generating doc: {item.name}")
        
        try:
            doc = self.agent.generate(item)
            
            if not doc or not doc.strip():
                logger.warning(f"Empty doc for {item.name}, using fallback")
                return self._generate_fallback_doc(item)
            
            logger.debug(f"Generated {len(doc)} chars for {item.name}")
            return doc
            
        except Exception as e:
            logger.error(f"Generation failed for {item.name}: {e}")
            return self._generate_fallback_doc(item)
    
    def _generate_fallback_doc(self, item: ConfigItem) -> str:
        """Generate basic fallback doc when LLM fails"""
        doc_parts = [
            f"## {item.name}\n",
            f"**Type:** `{item.type}`\n",
            f"**Default:** `{item.defaultValue}`\n",
            f"**Mutable:** `{item.isMutable}`\n",
        ]
        
        if item.comment:
            doc_parts.append(f"\n### Description\n{item.comment}\n")
        
        if item.define:
            doc_parts.append(f"\n**Defined in:** `{item.define}`\n")
        
        return "\n".join(doc_parts)
    