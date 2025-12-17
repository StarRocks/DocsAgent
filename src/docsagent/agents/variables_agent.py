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
VariableDocAgent: Generate English documentation for session/global variables using LangGraph
"""
from typing import TypedDict, Sequence, Annotated
import operator
from loguru import logger

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage

from docsagent.agents.llm import get_default_chat_model
from docsagent.agents.tools import get_code_reading_tools
from docsagent.domains.models import VariableItem
from docsagent.tools import stats


# Define state schema for the workflow
class VariableDocState(TypedDict):
    """State for variable documentation generation workflow"""
    variable: VariableItem          # Input: variable item
    messages: Annotated[Sequence[BaseMessage], operator.add] # Message history for tool-enabled workflow (auto-append)
    prompt: str                     # Prepared prompt for LLM
    raw_output: str                 # Raw LLM output
    documentation: str              # Final formatted documentation


class VariableDocAgent:
    """
    LangGraph-based agent for generating variable documentation
    
    Enhanced with code reading tools to understand variable usage in codebase.
    
    Workflow:
        variable -> prepare_prompt -> generate (with tools) -> format -> documentation
    """
    
    def __init__(self, chat_model: BaseChatModel = None):
        """
        Initialize the variable documentation agent
        
        Args:
            chat_model: LangChain chat model (default: from config)
        """
        self.chat_model = chat_model or get_default_chat_model()
        
        # Get tools and bind to LLM
        self.tools = get_code_reading_tools()
        self.llm_with_tools = self.chat_model.bind_tools(self.tools)
            
        self.workflow = self._build_workflow()
        logger.debug("VariableDocAgent initialized")
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(VariableDocState)
        
        # Add nodes
        workflow.add_node("prepare_prompt", self._prepare_prompt)
        workflow.add_node("generate", self._generate)
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
                "format": "format"
            }
        )
        workflow.add_edge("tools", "generate")  # Loop back after tool use
            
        workflow.add_edge("format", END)
        
        return workflow.compile()
    
    def _should_continue(self, state: VariableDocState) -> str:
        """Decide whether to use tools or proceed to format"""
        messages = state.get('messages', [])
        if not messages:
            return "format"
        
        last_message = messages[-1]
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "tools"
        return "format"
    
    # Node implementations
    def _prepare_prompt(self, state: VariableDocState) -> VariableDocState:
        """
        Node 1: Prepare prompt for LLM
        
        Constructs a detailed prompt including variable metadata
        """
        variable = state['variable']
        logger.debug(f"Preparing prompt for variable: {variable.name}")
        
        # Build user prompt with config information
        prompt = self._build_user_prompt(variable)
        
        # Initialize messages for tool-enabled workflow
        # Note: messages field uses operator.add, so we return a list that will be appended
        system_prompt = self._build_system_prompt()
        return {
            **state,
            'prompt': prompt,
            'messages': [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ]
        }
    
    def _generate(self, state: VariableDocState) -> VariableDocState:
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
                'raw_output': self.generate_fallback_doc(state['variable'])
            }
    
    def _format(self, state: VariableDocState) -> VariableDocState:
        """
        Node 3: Format output as standard Markdown
        
        Ensures consistent formatting and structure
        """
        logger.debug("Formatting documentation")
        
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
        - Description should be generated based on the provided metadata and codebase analysis
        - Be specific and avoid vague statements
        - When using other configurations, use `configuration name` format
        - The characters </>/>=/<= must use HTML escape format
        - Keep the documentation less than 300 words

        **About UseLocations**:
        - The `UseLocations` field contains file paths where this variable is USED in the codebase
        - These locations show real usage and help you understand the variable's purpose
        - You can use `read_file` to read these files and understand how the variable is used
        - Example: If UseLocations shows "fe/src/main/java/VariableManager.java:156", you can read that file

        **Code Reading Tools Available**:
        You have access to two tools to read and search the codebase:
        1. `search_code`: Search for keywords in code files (e.g. find function implementation)
           - **REQUIRED**: The `file_paths` parameter MUST be specific file paths from the UseLocations field
        2. `read_file`: Read specific file content (e.g. read function code details)
           - **REQUIRED**: The `file_path` parameter MUST be from UseLocations field        
        
        **Recommended workflow**:
        1. Review the variable metadata (name, type, default, scope, comment, UseLocations)
        2. **OPTIONAL**: Use `read_file` to check those files for usage context if UseLocations is provided and needed
        3. **OPTIONAL**: Use `search_code` to find codes which you want to explore if needed
        4. Generate documentation based on your findings

        Output only the documentation content, no additional commentary. The output format should be like this:
        ### ${show Name} ${when scope is global, add "(Global)"}

        * **Description**: ${description}
        * **Default**: ${default value, use `` to enclose when the value is a code snippet}
        * **Data Type**: ${variable type}
        * **Introduced in**: ${Introduced in from metadata, use '-' if not available}
        
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
        # Format version info
        versions = [v if v.startswith('v') else 'v' + v for v in variable.version]
        version_info = ", ".join(versions) if versions else "-"

        prompt = f"""
        Generate documentation for the following StarRocks variable:
        
        **Variable Name**: {variable.name}
        **Data Type**: {variable.type}
        **Default Value**: {variable.defaultValue}
        **Scope**: {variable.scope}
        **Show Name**: {variable.show}
        **Introduced in**: {version_info}
        **UseLocations**: {variable.useLocations}
        **Comment**: {variable.comment}

        Please generate comprehensive documentation following the required structure.
        """
        
        return prompt
    
    def generate_fallback_doc(self, variable: VariableItem) -> str:
        """Generate fallback documentation when LLM fails"""
        scope_suffix = "(Global)" if variable.scope.lower() == "global" else ""
        version_info = ", ".join(variable.version) if variable.version else "-"
        
        fallback = f"""
        ### {variable.show} {scope_suffix}

        * **Description**: {variable.comment}
        * **Default**: {variable.defaultValue}
        * **Data Type**: {variable.type}
        * **Introduced in**: {version_info}
        """
        return fallback.strip()
    
    def _ensure_markdown_structure(self, raw: str, variable: VariableItem) -> str:
        """Ensure the documentation has proper Markdown structure"""
        # Otherwise, wrap it in a basic structure
        name = variable.name
        if not raw.startswith('#'):
            logger.warning(f"Raw output missing header for {name}, adding header")
        
        formatted = raw
        if "<" in formatted or ">" in formatted:
            logger.warning(f"Raw output contains unescaped characters for {name}, escaping them")
            formatted = formatted.replace("<", "&lt;").replace(">", "&gt;")
        
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
        logger.debug(f"Generating documentation for variable: {variable.name}")
        
        # Initialize state
        initial_state = VariableDocState(
            variable=variable,
            prompt="",
            raw_output="",
            documentation=""
        )
        
        # Run workflow
        final_state = self.workflow.invoke(initial_state)
        
        logger.debug(f"Documentation generated ({len(final_state['documentation'])} chars)")
        
        return final_state['documentation']
