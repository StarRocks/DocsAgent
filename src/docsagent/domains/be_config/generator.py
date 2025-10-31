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

"""BEConfigDocGenerator: Generate English docs using LLM"""

from typing import Optional
from loguru import logger
from langchain_core.language_models.chat_models import BaseChatModel

from docsagent.core.protocols import DocGenerator
from docsagent.domains.models import ConfigItem
from docsagent.agents.config_doc_agent import ConfigDocAgent


class BEConfigDocGenerator(DocGenerator):
    """Generate documentation using LLM (implements DocGenerator protocol)"""
    
    def __init__(self):
        self.agent = ConfigDocAgent()
        logger.debug("BEConfigDocGenerator initialized")
    
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