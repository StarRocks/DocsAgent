"""FEConfigDocGenerator: Generate English docs using LLM"""

from typing import Optional
from loguru import logger
from langchain_core.language_models.chat_models import BaseChatModel

from docsagent.core.protocols import DocGenerator
from docsagent.domains.models import ConfigItem
from docsagent.agents.config_doc_agent import ConfigDocAgent


class FEConfigDocGenerator(DocGenerator):
    """Generate documentation using LLM (implements DocGenerator protocol)"""
    
    def __init__(self):
        self.agent = ConfigDocAgent()
        logger.debug("FEConfigDocGenerator initialized")
    
    def generate(self, item: ConfigItem, **kwargs) -> str:
        """Generate English documentation for a config item"""
        logger.debug(f"Generating doc: {item.name}")
        
        try:
            doc = self.agent.generate(item)
            
            if not doc or not doc.strip():
                logger.warning(f"Empty doc for {item.name}, using fallback")
                return self.agent.generate_fallback_doc(item)
            
            logger.debug(f"Generated {len(doc)} chars for {item.name}")
            return doc
            
        except Exception as e:
            logger.error(f"Generation failed for {item.name}: {e}")
            return self.agent.generate_fallback_doc(item)
    