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
FunctionDocAgent: Generate English documentation for SQL functions using LangGraph
"""
from typing import TypedDict, Sequence, Annotated
import operator
from loguru import logger

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage

from docsagent.agents.llm import get_default_chat_model
from docsagent.agents.tools import get_all_tools
from docsagent.domains.models import FunctionItem, FUNCTION_CATALOGS
from docsagent.tools import stats


# Define state schema for the workflow
class FunctionDocState(TypedDict):
    """State for function documentation generation workflow"""
    func: FunctionItem              # Input: function item
    messages: Annotated[Sequence[BaseMessage], operator.add] # Message history for tool-enabled workflow (auto-append)
    prompt: str                     # Prepared prompt for LLM
    raw_output: str                 # Raw LLM output
    documentation: str              # Final formatted documentation


class FunctionDocAgent:
    """
    LangGraph-based agent for generating SQL function documentation
    
    Enhanced with code reading tools to understand function implementation.
    
    Workflow:
        func -> prepare_prompt -> generate (with tools) -> format -> documentation
    """
    
    def __init__(self, chat_model: BaseChatModel = None):
        """
        Initialize the function documentation agent
        
        Args:
            chat_model: LangChain chat model (default: from config)
        """
        self.chat_model = chat_model or get_default_chat_model()
        
        # Get tools - include StarRocks SQL execution tool if enabled
        self.tools = get_all_tools(include_starrocks=True, test_sr_connection=True)
        logger.debug("Function agent initialized with SQL execution capability")
        
        self.llm_with_tools = self.chat_model.bind_tools(self.tools)
            
        self.workflow = self._build_workflow()
        logger.debug("FunctionDocAgent workflow built")
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(FunctionDocState)
        
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
    
    def _should_continue(self, state: FunctionDocState) -> str:
        """Decide whether to use tools or proceed to classify"""
        messages = state.get('messages', [])
        if not messages:
            return "classify"
        
        last_message = messages[-1]
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "tools"
        return "classify"
    
    # Node implementations
    def _prepare_prompt(self, state: FunctionDocState) -> FunctionDocState:
        """
        Node 1: Prepare prompt for LLM
        
        Constructs a detailed prompt including function metadata
        """
        func = state['func']
        logger.debug(f"Preparing prompt for function: {func.name}")
        
        # Build user prompt with function information
        prompt = self._build_user_prompt(func)
        
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

    def _generate(self, state: FunctionDocState) -> FunctionDocState:
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
            raise e
    
    def _format(self, state: FunctionDocState) -> FunctionDocState:
        """
        Node 3: Format output as standard Markdown
        
        Ensures consistent formatting and structure
        """
        logger.debug("Formatting documentation")
        
        raw = state['raw_output']
        func = state['func']
        
        # Basic formatting: ensure proper structure
        formatted = self._ensure_markdown_structure(raw, func)
        state['documentation'] = formatted
        
        return state
    
    # Helper methods
    def _build_system_prompt(self) -> str:
        """Build system prompt for the LLM"""
        
        # Check if SQL execution tool is available
        has_sql_tool = any(tool.name == 'execute_sql' for tool in self.tools)
        
        sql_tool_instruction = ""
        if has_sql_tool:
            sql_tool_instruction = """
        
        **SQL Execution Tool Available** (OPTIONAL):
        You have access to `execute_sql` tool to execute SELECT queries on StarRocks.
        
        **When to use**:
        - To test the function with REAL data and get ACTUAL results
        - To generate accurate, verified examples with real output
        - To understand edge cases by testing different inputs
        
        **How to use**:
        - Execute simple SELECT queries: SELECT function_name(test_input)
        - Example: SELECT NOW(), SELECT CONCAT('Hello', ' ', 'World')
        - Use the actual output in your Examples section
        
        **Important restrictions** (READ-ONLY mode):
        - ONLY SELECT queries are allowed
        - NO INSERT, UPDATE, DELETE, DROP, CREATE, etc.
        - NO SHOW or DESCRIBE commands (use SELECT from information_schema instead)
        - NO multiple statements (no semicolons)
        
        **When NOT to use**:
        - If you can generate clear examples without execution
        - For functions that need tables with specific data
        
        This tool is OPTIONAL. Use it ONLY when it helps generate better examples.
        If you choose not to use it, generate examples based on the function signature and your knowledge.
        """
        
        return f"""
        You are a technical documentation writer for StarRocks database system.

        Your task is to generate clear, concise, and accurate documentation for SQL functions.

        Requirements:
        - Write in professional English
        - Use Markdown format with proper frontmatter
        - Include these sections: 
          1. Frontmatter (displayed_sidebar: docs)
          2. Function name as H1
          3. Brief description
          4. Syntax section with code block
          5. Parameters section (if applicable)
          6. Return value section
          7. Usage notes section (optional but recommended)
          8. Examples section with SQL examples
          9. keyword section (function name in uppercase)
        - Be specific and avoid vague statements
        - Focus on practical usage with real examples
        - Examples should use Plain text code blocks for SQL output
        
        **About UseLocations** (IMPORTANT):
        - The `UseLocations` field MIGHT contain files related to function implementation
        - **WARNING**: These locations are NOT always accurate and may include false positives
        - You MUST verify if a location actually contains the function implementation
        - Some locations might be test files, unrelated code, or caller code (not the actual implementation)
        
        **About implement_fns**:
        - This field contains the actual C++ implementation function names
        - Use these names to search for the real implementation code
        - Example: If implement_fns contains "StringFunctions::like", search for that in the codebase
        
        **Code Reading Tools Available**:
        You have access to two tools to read and search the codebase:
        1. `search_code`: Search for keywords in code files (e.g. find function implementation)
           - **REQUIRED**: The `file_paths` parameter MUST be specific file paths from the UseLocations field
           - Example: search_code(keywords=["StringFunctions::like"], file_paths=["/path/from/UseLocations/file.cpp"])
        2. `read_file`: Read specific file content (e.g. read function code details)
           - **REQUIRED**: The `file_path` parameter MUST be from UseLocations field
        {sql_tool_instruction}        
        
        **Recommended workflow**:
        1. Review function metadata (name, signature, implement_fns)
        2. **OPTIONAL**: Use `search_code` with implement_fns to find actual implementation if you need
        3. **OPTIONAL**: verify them with `read_file` (but be critical) if UseLocations is provided and you need
        4. **OPTIONAL**: Read testCases if available for understanding usage examples
        5. **OPTIONAL**: Use `execute_sql` to test the function and get real results for examples
        6. Generate documentation based on verified findings
        
        **Critical**: Don't blindly trust UseLocations - always verify the code is actually relevant!

        Output only the documentation content, no additional commentary. The output format should be exactly like this:

        ---
        displayed_sidebar: docs
        ---

        # function_name

        Brief description of what the function does.
        
        ## Aliases (if applicable)
        (if applicable) List of alternative names for the function.

        ## Syntax

        ```Haskell
        RETURN_TYPE function_name(TYPE param1[, TYPE param2, ...])
        ```

        ### Parameters

        `param1`: Description of the parameter, including data type constraints and behavior.

        `param2`: (if applicable) Description of additional parameters.

        ## Return value

        Returns a value of the RETURN_TYPE data type. Explain what the return value represents.

        ## Usage notes

        Important notes about function behavior, edge cases, or special considerations.

        ## Examples

        ```Plain
        mysql> SELECT function_name(example_input);
        +---------------------------+
        | function_name(example_input) |
        +---------------------------+
        |          result_value      |
        +---------------------------+
        ```

        ## keyword
        FUNCTION_NAME, Aliases (if applicable)
        """
    
    def _build_user_prompt(self, func: FunctionItem) -> str:
        """Build user prompt with function metadata"""
        
        # Format UseLocations if available
        use_locations_text = "  None available"
        if func.useLocations:
            use_locations_text = '\n'.join([f"  - {loc}" for loc in func.useLocations])
        
        prompt = f"""
        Generate documentation for the following StarRocks SQL function:
        
        **Function Name**: {func.name}
        **Aliases**: {", ".join([alias for alias in func.alias])}
        **Signatures**: 
        {chr(10).join([f"  - {sig}" for sig in func.signature])}
        **Implementation Functions**: 
        {chr(10).join([f"  - {impl}" for impl in func.implement_fns])}
        **UseLocations** (file paths where this function might be used or implemented):
        {use_locations_text}
        **Test Cases**: 
        {chr(10).join([f"  - {test}" for test in func.testCases]) if func.testCases else '  None available'}

        Please generate comprehensive documentation following the required structure.
        Make sure to include practical examples that demonstrate the function's usage.
        """
        
        return prompt
    
    def generate_fallback_doc(self, func: FunctionItem) -> str:
        """Generate fallback documentation when LLM fails"""
        signatures = '\n'.join([f"{sig}" for sig in func.signature])
        
        fallback = f"""
        ---
        displayed_sidebar: docs
        ---

        # {func.name}

        {func.catalog} function.

        ## Syntax

        ```Haskell
        {signatures}
        ```

        ## Return value

        Returns a value based on the function signature.

        ## Examples

        ```Plain
        mysql> SELECT {func.name}();
        ```

        ## keyword
        {func.name.upper()}
        """
        return fallback
    
    def _ensure_markdown_structure(self, raw: str, func: FunctionItem) -> str:
        """Ensure the documentation has proper Markdown structure"""
        # If raw output already looks good (has frontmatter), return it
        if raw.startswith('---') and '# ' in raw:
            return raw
        
        # Otherwise, wrap it in a basic structure with frontmatter
        name = func.name
        
        if not raw.startswith('---'):
            formatted = f"""
            ---
            displayed_sidebar: docs
            ---

            # {name}

            {raw}

            ## keyword
            {name.upper()}
            """
        else:
            formatted = raw
        
        return formatted.strip()
    
    def _build_classify_system_prompt(self) -> str:
        """Build system prompt for function classification"""
        # TODO: Define valid function catalogs based on FUNCTION_CATALOGS_DIRS
        return f"""
        You are a StarRocks SQL function classification expert.

        Your task is to classify SQL functions into appropriate categories.

        Requirements:
        - Return ONLY the category name
        - Base your decision on the function's purpose and generated documentation
        - Be specific about the function's primary use case
        
        categories include:
        {chr(10).join([f"  - {impl}" for impl in FUNCTION_CATALOGS])}
        """
    
    def _build_classify_user_prompt(self, func: FunctionItem, documentation: str) -> str:
        """Build user prompt for classification with function and documentation"""
        return f"""
        Please classify the following SQL function:

        **Function Name**: {func.name}

        **Generated Documentation**:
        {documentation}

        Please return the most appropriate category for this function.
        If the current category is already accurate, return it as-is.
        """
    
    def _classify(self, state: FunctionDocState) -> FunctionDocState:
        """
        Node: Classify the function based on generated documentation
        
        Updates func.catalog with the classification result if needed
        """
        func = state['func']
        documentation = state['documentation']
        
        logger.debug(f"Classifying function: {func.name} (current: {func.catalog})")
        
        try:
            system_prompt = self._build_classify_system_prompt()
            user_prompt = self._build_classify_user_prompt(func, documentation)
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = self.chat_model.invoke(messages)
            catalog = response.content.strip()
            
            # Update func.catalog
            func.catalog = catalog
            logger.debug(f"Classified {func.name} as: {catalog}")
            
        except Exception as e:
            logger.error(f"Classification failed: {e}, keeping original catalog")
            # Keep the original catalog on failure
        
        return state
    
    # Public interface
    def generate(self, func: FunctionItem) -> str:
        """
        Generate documentation for a SQL function
        
        Args:
            func: FunctionItem object with metadata
        
        Returns:
            Generated English Markdown documentation as string
            
        Example:
            >>> agent = FunctionDocAgent()
            >>> func = FunctionItem(
            ...     name="atan",
            ...     alias=[],
            ...     signature=["DOUBLE atan(DOUBLE arg)"],
            ...     catalog="Math Functions",
            ...     module="Scalar",
            ...     implement_fns=["atan"],
            ...     testCases=[]
            ... )
            >>> doc = agent.generate(func)
        """
        logger.debug(f"Generating documentation for function: {func.name}")
        
        # Initialize state
        initial_state = FunctionDocState(
            func=func,
            prompt="",
            raw_output="",
            documentation=""
        )
        
        # Run workflow
        final_state = self.workflow.invoke(initial_state)
        
        logger.debug(f"Documentation generated ({len(final_state['documentation'])} chars)")
        
        return final_state['documentation']
