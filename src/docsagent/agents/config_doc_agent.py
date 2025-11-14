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
ConfigDocAgent: Generate English documentation for configuration items using LangGraph
"""
from typing import TypedDict, Annotated, Sequence
import operator
from loguru import logger

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage

from docsagent.agents.llm import get_default_chat_model
from docsagent.agents.tools import get_code_reading_tools
from docsagent.domains.models import ConfigItem, VALID_CATALOGS, is_valid_catalog, get_default_catalog
from docsagent.tools import stats


# Define state schema for the workflow
class ConfigDocState(TypedDict):
    """State for config documentation generation workflow"""
    config: ConfigItem              # Input: configuration item
    messages: Annotated[Sequence[BaseMessage], operator.add] # Message history for tool-enabled workflow (auto-append)
    prompt: str                     # Prepared prompt for LLM
    raw_output: str                 # Raw LLM output
    documentation: str              # Final formatted documentation


class ConfigDocAgent:
    """
    LangGraph-based agent for generating configuration documentation
    
    Enhanced with code reading tools to understand config usage in codebase.
    
    Workflow:
        config -> prepare_prompt -> generate (with tools) -> format -> documentation
    """
    
    def __init__(self, chat_model: BaseChatModel = None):
        """
        Initialize the config documentation agent
        
        Args:
            chat_model: LangChain chat model (default: from config)
        """
        self.chat_model = chat_model or get_default_chat_model()
        
        # Get tools and bind to LLM
        self.tools = get_code_reading_tools()
        self.llm_with_tools = self.chat_model.bind_tools(self.tools)
            
        self.workflow = self._build_workflow()
        logger.debug("ConfigDocAgent initialized")
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(ConfigDocState)
        
        # Add nodes
        workflow.add_node("prepare_prompt", self._prepare_prompt)
        workflow.add_node("generate", self._generate)
        workflow.add_node("classify", self._classify)
        workflow.add_node("format", self._format)
        workflow.add_node("tools", ToolNode(self.tools))
        
        # Define edges
        workflow.set_entry_point("prepare_prompt")
        workflow.add_edge("prepare_prompt", "generate")
        
        # Add conditional edge for tool usage
        workflow.add_conditional_edges(
            "generate",
            self._should_continue,
            {
                "tools": "tools",
                "classify": "classify"
            }
        )
        workflow.add_edge("tools", "generate")  # Loop back after tool use
            
        workflow.add_edge("classify", "format")
        workflow.add_edge("format", END)
        
        return workflow.compile()
    
    def _should_continue(self, state: ConfigDocState) -> str:
        """Decide whether to use tools or proceed to classify"""
        messages = state.get('messages', [])
        if not messages:
            return "classify"
        
        last_message = messages[-1]
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "tools"
        return "classify"
    
    # Node implementations
    def _prepare_prompt(self, state: ConfigDocState) -> ConfigDocState:
        """
        Node 1: Prepare prompt for LLM
        
        Constructs a detailed prompt including config metadata
        """
        config = state['config']
        logger.debug(f"Preparing prompt for config: {config.name}")
        
        # Build user prompt with config information
        prompt = self._build_user_prompt(config)
        state['prompt'] = prompt
        
        # Initialize messages for tool-enabled workflow
        # Note: messages field uses operator.add, so we return a list that will be appended
        system_prompt = self._build_system_prompt()
        return {
            **state,
            'messages': [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ]
        }
    
    def _generate(self, state: ConfigDocState) -> ConfigDocState:
        """
        Node 2: Call LLM to generate documentation
        
        Invokes the chat model with system and user prompts
        """
        logger.debug("Calling LLM to generate documentation")
        
        try:
            # Use messages for tool-enabled workflow
            messages = state['messages']
            response = self.llm_with_tools.invoke(messages)
            
            # Record token usage if available
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage = response.usage_metadata
                input_tokens = getattr(usage, 'input_tokens', 0)
                output_tokens = getattr(usage, 'output_tokens', 0)
                if input_tokens or output_tokens:
                    logger.debug(f"Token usage: input={input_tokens}, output={output_tokens}")
            
            # Return response in messages (will be auto-appended due to operator.add)
            result = {'messages': [response]}
            
            # Extract content if this is final response (no tool calls)
            if not hasattr(response, 'tool_calls') or not response.tool_calls:
                result['raw_output'] = response.content.strip()
                logger.debug(f"Generated {len(result['raw_output'])} characters")
            
            return result
                
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            # Fallback: generate basic documentation
            return {
                'raw_output': self.generate_fallback_doc(state['config'])
            }
    
    def _format(self, state: ConfigDocState) -> ConfigDocState:
        """
        Node 3: Format output as standard Markdown
        
        Ensures consistent formatting and structure
        """
        logger.debug("Formatting documentation")
        
        raw = state['raw_output']
        config = state['config']
        
        # Basic formatting: ensure proper structure
        formatted = self._ensure_markdown_structure(raw, config)
        state['documentation'] = formatted
        
        return state
    
    # Helper methods
    def _build_system_prompt(self) -> str:
        """Build system prompt for the LLM"""
        return """
        You are a technical documentation writer for StarRocks database system.

        Your task is to generate clear, concise, and accurate documentation for configuration items.

        Requirements:
        - Write in professional English
        - Use Markdown format
        - Include these sections: Name, Description, Default Value, Type, Mutable, Unit
        - Description should be generated based on the provided metadata and codebase analysis, and there is no need to report whether it is mutable or not
        - When uses other configurations in the Description, use `configuration name` format
        - Be specific and avoid vague statements
        - Focus on practical usage and implications
        - The characters < and > should use HTML escape format
        - Keep the documentation less than 200 words
        
        **Code Reading Tools Available**:
        You have access to two tools to read and search the codebase:
        1. `search_code`: Search for keywords in code files (e.g., find where config is used)
        2. `read_file`: Read specific file content (e.g., read implementation details)
        
        **About UseLocations**:
        - The `UseLocations` field contains file paths where this configuration is USED in the codebase
        - These locations show real usage and help you understand the config's purpose
        - You can use `read_file` to read these files and understand the context
        - Example: If UseLocations shows "fe/src/main/java/ConfigManager.java:42", you can read that file

        **Recommended workflow**:
        1. Review the config metadata (name, type, default, comment, UseLocations)
        2. **OPTIONAL**: Use `read_file` to check those files for usage context if UseLocations is provided and needed
        3. **OPTIONAL**: Use `search_code` to find codes which you want to explore if needed
        4. Generate documentation based on your findings

        Output only the documentation content, no additional commentary. The output format should be like this:
        ##### ${config name} 

        - Default: ${default value, use `` to enclose when the value is a code snippet}
        - Type: ${config type}
        - Unit: ${unit if applicable, else -}
        - Is mutable: ${is mutable}
        - Description: ${description}
        - Introduced in: ${`Introduced in` info from metadata, use '-' if not available}
        
        output example:
        ##### black_host_history_sec

        - Default: 2 * 60
        - Type: Int
        - Unit: Seconds
        - Is mutable: Yes
        - Description: The time duration for retaining historical connection failures of BE nodes in the BE Blacklist. If a BE node is added to the BE Blacklist automatically, StarRocks will assess its connectivity and judge whether it can be removed from the BE Blacklist. Within `black_host_history_sec`, only if a blacklisted BE node has fewer connection failures than the threshold set in `black_host_connect_failures_within_time`, it can be removed from the BE Blacklist.
        - Introduced in: v3.3.0
        """
    
    def _build_user_prompt(self, config: ConfigItem) -> str:
        """Build user prompt with config metadata"""
        # Format version info
        versions = [v if v.startswith('v') else 'v' + v for v in config.version]
        version_info = ", ".join(versions) if versions else "-"
        
        prompt = f"""
        Generate documentation for the following StarRocks configuration item:
        
        **Configuration Name**: {config.name}
        **Type**: {config.type}
        **Default Value**: {config.defaultValue}
        **isMutable**: {config.isMutable}
        **Introduced in**: {version_info}
        **UseLocations**: {config.useLocations}
        **Comment**: {config.comment}

        Please generate comprehensive documentation following the required structure.
        """
        
        return prompt
    
    def generate_fallback_doc(self, config: ConfigItem) -> str:
        """Generate fallback documentation when LLM fails"""
        version_info = ", ".join(config.version) if config.version else "-"
        
        fallback = f"""
        ##### {config.name}

        - Default: {config.defaultValue}
        - Type: {config.type}
        - Unit: -
        - Is mutable: {config.isMutable}
        - Description: {config.comment}
        - Introduced in: {version_info}
        """
        return fallback
    
    def _ensure_markdown_structure(self, raw: str, config: ConfigItem) -> str:
        """Ensure the documentation has proper Markdown structure"""
        # If raw output already looks good, return it
        if raw.startswith('##') and len(raw) > 50:
            return raw
        
        # Otherwise, wrap it in a basic structure
        name = config.name
        
        if not raw.startswith('#'):
            logger.warning(f"Raw output missing header for {name}, adding header")
        
        formatted = raw
        return formatted.strip()
    
    def _build_classify_system_prompt(self) -> str:
        """Build system prompt for config classification"""
        catalogs_list = '\n'.join([f"{i+1}. {cat}" for i, cat in enumerate(VALID_CATALOGS)])
        
        return f"""
        You are a StarRocks database configuration expert.

        Your task is to classify configuration items into one of the following {len(VALID_CATALOGS)} categories:

        {catalogs_list}

        Category descriptions:
        - Logging: Log-related settings (log level, log files, audit logs)
        - Server: Basic server configuration (ports, threads, memory, network)
        - Metadata and cluster management: Metadata management, catalog, cluster coordination, FE/BE communication
        - User, role, and privilege: User authentication, permission control, security
        - Query engine: Query optimization, execution, scheduling, cache, statistics, optimizer
        - Loading and unloading: Data import/export, Stream Load, Broker Load, etc.
        - Storage: Storage engine, disk, compression, Tablet, Rowset, Compaction
        - Shared-data: Shared-data mode, object storage, cache
        - Data Lake: Data lake related configurations
        - Other: Uncategorized items

        Requirements:
        - Return ONLY the category name (e.g., "Query engine")
        - Must select one from the above {len(VALID_CATALOGS)} categories
        - Base your decision primarily on the Description section
        - If multiple categories apply, choose the most relevant one
        - If uncertain, choose "Other"
        """
    
    def _build_classify_user_prompt(self, config: ConfigItem, documentation: str) -> str:
        """Build user prompt for classification with config and documentation"""
        return f"""
        Please classify the following configuration item:

        **Configuration Name**: {config.name}

        **Generated Documentation**:
        {documentation}

        Please return the category this configuration item belongs to.
        """
    
    def _classify(self, state: ConfigDocState) -> ConfigDocState:
        """
        Node: Classify the configuration item based on generated documentation
        
        Updates config.catalog with the classification result
        """
        config = state['config']
        documentation = state['documentation']
        
        # Skip if already classified
        if config.catalog is not None and is_valid_catalog(config.catalog):
            logger.debug(f"Config {config.name} already classified as: {config.catalog}")
            return state
        
        logger.debug(f"Classifying config: {config.name}")
        
        try:
            system_prompt = self._build_classify_system_prompt()
            user_prompt = self._build_classify_user_prompt(config, documentation)
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = self.chat_model.invoke(messages)
            catalog = response.content.strip()
            
            # Validate the returned catalog
            if not is_valid_catalog(catalog):
                logger.warning(f"LLM returned invalid catalog '{catalog}', using default")
                catalog = get_default_catalog()

            # Update config
            config.catalog = catalog
            logger.debug(f"Classified {config.name} as: {catalog}")
            
        except Exception as e:
            logger.error(f"Classification failed: {e}, using default catalog")
            config.catalog = get_default_catalog()
        
        return state
    
    # Public interface
    def generate(self, config: ConfigItem) -> str:
        """
        Generate documentation for a configuration item
        
        Args:
            config: ConfigItem object with metadata
        
        Returns:
            Generated English Markdown documentation as string
            
        Example:
            >>> agent = ConfigDocAgent()
            >>> config = ConfigItem(
            ...     name="query_timeout",
            ...     type="int",
            ...     defaultValue="300",
            ...     isMutable="true",
            ...     comment="Query execution timeout in seconds",
            ...     scope="FE",
            ...     file_path="/path/to/Config.java",
            ...     line_number=100
            ... )
            >>> doc = agent.generate(config)
        """
        logger.debug(f"Generating documentation for: {config.name}")
        
        # Initialize state
        initial_state = ConfigDocState(
            config=config,
            prompt="",
            raw_output="",
            documentation=""
        )
        
        # Run workflow
        final_state = self.workflow.invoke(initial_state)
        
        logger.debug(f"Documentation generated ({len(final_state['documentation'])} chars)")
        
        return final_state['documentation']
