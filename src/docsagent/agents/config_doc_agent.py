"""
ConfigDocAgent: Generate English documentation for configuration items using LangGraph
"""
from typing import TypedDict
from loguru import logger

from langgraph.graph import StateGraph, END
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from docsagent.agents.llm import get_default_chat_model
from docsagent.models import ConfigItem


# Define state schema for the workflow
class ConfigDocState(TypedDict):
    """State for config documentation generation workflow"""
    config: ConfigItem              # Input: configuration item
    prompt: str                     # Prepared prompt for LLM
    raw_output: str                 # Raw LLM output
    documentation: str              # Final formatted documentation


class ConfigDocAgent:
    """
    LangGraph-based agent for generating configuration documentation
    
    Workflow:
        config -> prepare_prompt -> generate -> format -> documentation
    """
    
    def __init__(self, chat_model: BaseChatModel = None):
        """
        Initialize the config documentation agent
        
        Args:
            chat_model: LangChain chat model (default: from config)
        """
        self.chat_model = chat_model or get_default_chat_model()
        self.workflow = self._build_workflow()
        logger.info("ConfigDocAgent initialized")
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(ConfigDocState)
        
        # Add nodes
        workflow.add_node("prepare_prompt", self._prepare_prompt)
        workflow.add_node("generate", self._generate)
        workflow.add_node("format", self._format)
        
        # Define edges
        workflow.set_entry_point("prepare_prompt")
        workflow.add_edge("prepare_prompt", "generate")
        workflow.add_edge("generate", "format")
        workflow.add_edge("format", END)
        
        return workflow.compile()
    
    # Node implementations
    def _prepare_prompt(self, state: ConfigDocState) -> ConfigDocState:
        """
        Node 1: Prepare prompt for LLM
        
        Constructs a detailed prompt including config metadata
        """
        config = state['config']
        logger.info(f"Preparing prompt for config: {config.name}")
        
        # Build user prompt with config information
        prompt = self._build_user_prompt(config)
        state['prompt'] = prompt
        
        return state
    
    def _generate(self, state: ConfigDocState) -> ConfigDocState:
        """
        Node 2: Call LLM to generate documentation
        
        Invokes the chat model with system and user prompts
        """
        logger.info("Calling LLM to generate documentation")
        
        try:
            system_prompt = self._build_system_prompt()
            user_prompt = state['prompt']
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = self.chat_model.invoke(messages)
            state['raw_output'] = response.content.strip()
            logger.debug(f"Generated {len(state['raw_output'])} characters")
            
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            # Fallback: generate basic documentation
            state['raw_output'] = self._generate_fallback_doc(state['config'])
        
        return state
    
    def _format(self, state: ConfigDocState) -> ConfigDocState:
        """
        Node 3: Format output as standard Markdown
        
        Ensures consistent formatting and structure
        """
        logger.info("Formatting documentation")
        
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
        - Description should be generated based on the provided codebase, the input will contains comment and usage code files
        - Be specific and avoid vague statements
        - Focus on practical usage and implications
        - Keep the documentation less than 200 words

        Output only the documentation content, no additional commentary. The output format should be like this:
        // document start, just to marked the document is start and doesn't need to be included in the output.
        ##### ${config name} 

        - Default: ${default value}
        - Type: ${config type}
        - Unit: ${unit if applicable, else N/A}
        - Is mutable: ${is mutable}
        - Description: ${description}
        - Introduced in: -
        // document end, just to marked the document is end and doesn't need to be included in the output.
        
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
        prompt = f"""
        Generate documentation for the following StarRocks configuration item:
        
        **Configuration Name**: {config.name}
        **Type**: {config.type}
        **Default Value**: {config.defaultValue}
        **isMutable**: {config.isMutable}
        **UseLocations**: {config.useLocations}
        **Comment**: {config.comment}

        Please generate comprehensive documentation following the required structure.
        """
        
        return prompt
    
    def _generate_fallback_doc(self, config: ConfigItem) -> str:
        """Generate fallback documentation when LLM fails"""
        fallback = f"""
        ##### {config.name}

        - Default: {config.defaultValue}
        - Type: {config.type}
        - Unit: N/A
        - Is mutable: {config.isMutable}
        - Description: {config.comment}
        - Introduced in: -
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
            formatted = f"## {name}\n\n{raw}"
        else:
            formatted = raw
        
        return formatted.strip()
    
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
        logger.info(f"Generating documentation for: {config.name}")
        
        # Initialize state
        initial_state = ConfigDocState(
            config=config,
            prompt="",
            raw_output="",
            documentation=""
        )
        
        # Run workflow
        final_state = self.workflow.invoke(initial_state)
        
        logger.info(f"Documentation generated ({len(final_state['documentation'])} chars)")
        
        return final_state['documentation']
