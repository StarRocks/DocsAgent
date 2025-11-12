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

"""VariablesDocGenerator: Generate English docs using LLM"""

from loguru import logger

from docsagent.core.protocols import DocGenerator
from docsagent.domains.models import VariableItem
from docsagent.agents.variables_agent import VariableDocAgent
from docsagent.tools import stats


class VariablesDocGenerator(DocGenerator):
    """Generate documentation using LLM (implements DocGenerator protocol)"""
    
    def __init__(self):
        self.agent = VariableDocAgent()
        logger.debug("VariablesDocGenerator initialized")
    
    def generate(self, item: VariableItem) -> str:
        """Generate English documentation for a config item"""
        logger.debug(f"Generating doc: {item.name}")
        
        try:
            # Record agent call
            stats.record_agent_call("VariableDocAgent")
            
            doc = self.agent.generate(item)
            
            if not doc or not doc.strip():
                logger.warning(f"Empty doc for {item.name}, using fallback")
                return self.agent.generate_fallback_doc(item)
            
            # Record successful generation
            stats.record_document("en")
            stats.record_generated_item(item.name)
            
            logger.debug(f"Generated {len(doc)} chars for {item.name}")
            return doc
            
        except Exception as e:
            stats.record_error(f"Generation failed for {item.name}: {e}")
            logger.error(f"Generation failed for {item.name}: {e}")
            return self.agent.generate_fallback_doc(item)