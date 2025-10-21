"""
VariableDocAgent: Generate English documentation for session/global variables using LangGraph
"""
from typing import TypedDict
from loguru import logger

from langgraph.graph import StateGraph, END
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from docsagent.agents.llm import get_default_chat_model
from docsagent.domains.models import VariableItem


# Define state schema for the workflow
class VariableDocState(TypedDict):
    """State for variable documentation generation workflow"""
    variable: VariableItem          # Input: variable item
    prompt: str                     # Prepared prompt for LLM
    raw_output: str                 # Raw LLM output
    documentation: str              # Final formatted documentation


class VariableDocAgent:
    """
    LangGraph-based agent for generating variable documentation
    
    Workflow:
        variable -> prepare_prompt -> generate -> format -> documentation
    """
    
    def __init__(self, chat_model: BaseChatModel = None):
        """
        Initialize the variable documentation agent
        
        Args:
            chat_model: LangChain chat model (default: from config)
        """
        self.chat_model = chat_model or get_default_chat_model()
        self.workflow = self._build_workflow()
        logger.info("VariableDocAgent initialized")
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(VariableDocState)
        
        # Add nodes
        workflow.add_node("prepare_prompt", self._prepare_prompt)
        workflow.add_node("generate", self._generate)
        workflow.add_node("format", self._format)

        # Define edges: prepare_prompt → generate → format
        workflow.set_entry_point("prepare_prompt")
        workflow.add_edge("prepare_prompt", "generate")
        workflow.add_edge("generate", "format")
        workflow.add_edge("format", END)
        
        return workflow.compile()
    
    # Node implementations
    def _prepare_prompt(self, state: VariableDocState) -> VariableDocState:
        """
        Node 1: Prepare prompt for LLM
        
        Constructs a detailed prompt including variable metadata
        """
        variable = state['variable']
        logger.info(f"Preparing prompt for variable: {variable.name}")
        
        # Build user prompt with config information
        prompt = self._build_user_prompt(variable)
        state['prompt'] = prompt
        
        return state
    
    def _generate(self, state: VariableDocState) -> VariableDocState:
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
            state['raw_output'] = self.generate_fallback_doc(state['variable'])
        
        return state
    
    def _format(self, state: VariableDocState) -> VariableDocState:
        """
        Node 3: Format output as standard Markdown
        
        Ensures consistent formatting and structure
        """
        logger.info("Formatting documentation")
        
        raw = state['raw_output']
        variable = state['variable']
        
        # Basic formatting: ensure proper structure
        formatted = self._ensure_markdown_structure(raw, variable)
        state['documentation'] = formatted
        
        return state
    
    # Helper methods
    def _build_system_prompt(self) -> str:
        """Build system prompt for the LLM"""
        return """
        You are a technical documentation writer for StarRocks database system.

        Your task is to generate clear, concise, and accurate documentation for session and global variables.

        Requirements:
        - Write in professional English
        - Use Markdown format
        - Include these sections: Show Name, Scope, Default Value, Type, Description, Introduced in
        - Description should be generated based on the provided comment and usage context
        - Be specific and avoid vague statements
        - Keep the documentation less than 300 words

        Output only the documentation content, no additional commentary. The output format should be like this:
        // document start, just to mark that the document starts and doesn't need to be included in the output.
        ### ${show Name} ${when scope is global, add "(Global)"}

        * **Description**: ${description}
        * **Default**: ${default value}
        * **Data Type**: ${variable type}
        * **Introduced in**: -
        // document end, just to mark that the document ends and doesn't need to be included in the output.
        
        output example:
        ### tablet_internal_parallel_mode

        * **Description**: Internal Parallel Scan strategy of tablets. Valid Values:
            * `auto`: When the number of Tablets to be scanned on BE or CN nodes is less than the Degree of Parallelism (DOP), the system automatically determines whether Parallel Scan is needed based on the estimated size of the Tablets.
            * `force_split`: Forces the splitting of Tablets and performs Parallel Scan.
        * **Default**: auto
        * **Data type**: String
        * **Introduced in**: v2.5.0
        """
    
    def _build_user_prompt(self, variable: VariableItem) -> str:
        """Build user prompt with variable metadata"""
        prompt = f"""
        Generate documentation for the following StarRocks variable:
        
        **Variable Name**: {variable.name}
        **Data Type**: {variable.type}
        **Default Value**: {variable.defaultValue}
        **Scope**: {variable.scope}
        **Show Name**: {variable.show}
        **UseLocations**: {variable.useLocations}
        **Comment**: {variable.comment}

        Please generate comprehensive documentation following the required structure.
        """
        
        return prompt
    
    def generate_fallback_doc(self, variable: VariableItem) -> str:
        """Generate fallback documentation when LLM fails"""
        scope_suffix = "(Global)" if variable.scope.lower() == "global" else ""
        fallback = f"""
        ### {variable.show} {scope_suffix}

        * **Description**: {variable.comment}
        * **Default**: {variable.defaultValue}
        * **Data Type**: {variable.type}
        * **Introduced in**: -
        """
        return fallback.strip()
    
    def _ensure_markdown_structure(self, raw: str, variable: VariableItem) -> str:
        """Ensure the documentation has proper Markdown structure"""
        # If raw output already looks good (starts with ###), return it
        if raw.startswith('###') and len(raw) > 50:
            return raw
        
        # Otherwise, wrap it in a basic structure
        name = variable.name
        
        if not raw.startswith('#'):
            formatted = f"### {name}\n\n{raw}"
        else:
            formatted = raw
        
        return formatted.strip()
    
    # Public interface
    def generate(self, variable: VariableItem) -> str:
        """
        Generate documentation for a variable item
        
        Args:
            variable: VariableItem object with metadata
        
        Returns:
            Generated English Markdown documentation as string
            
        Example:
            >>> agent = VariableDocAgent()
            >>> variable = VariableItem(
            ...     name="query_timeout",
            ...     show="query_timeout",
            ...     type="int",
            ...     defaultValue="300",
            ...     comment="Query execution timeout in seconds",
            ...     invisible=False,
            ...     scope="Session",
            ...     useLocations=[]
            ... )
            >>> doc = agent.generate(variable)
        """
        logger.info(f"Generating documentation for variable: {variable.name}")
        
        # Initialize state
        initial_state = VariableDocState(
            variable=variable,
            prompt="",
            raw_output="",
            documentation=""
        )
        
        # Run workflow
        final_state = self.workflow.invoke(initial_state)
        
        logger.info(f"Documentation generated ({len(final_state['documentation'])} chars)")
        
        return final_state['documentation']
