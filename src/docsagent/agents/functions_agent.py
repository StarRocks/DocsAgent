"""
FunctionDocAgent: Generate English documentation for SQL functions using LangGraph
"""
from typing import TypedDict
from loguru import logger

from langgraph.graph import StateGraph, END
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from docsagent.agents.llm import get_default_chat_model
from docsagent.domains.models import FunctionItem, FUNCTION_CATALOGS


# Define state schema for the workflow
class FunctionDocState(TypedDict):
    """State for function documentation generation workflow"""
    func: FunctionItem              # Input: function item
    prompt: str                     # Prepared prompt for LLM
    raw_output: str                 # Raw LLM output
    documentation: str              # Final formatted documentation


class FunctionDocAgent:
    """
    LangGraph-based agent for generating SQL function documentation
    
    Workflow:
        func -> prepare_prompt -> generate -> format -> documentation
    """
    
    def __init__(self, chat_model: BaseChatModel = None):
        """
        Initialize the function documentation agent
        
        Args:
            chat_model: LangChain chat model (default: from config)
        """
        self.chat_model = chat_model or get_default_chat_model()
        self.workflow = self._build_workflow()
        logger.info("FunctionDocAgent initialized")
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(FunctionDocState)
        
        # Add nodes
        workflow.add_node("prepare_prompt", self._prepare_prompt)
        workflow.add_node("generate", self._generate)
        workflow.add_node("classify", self._classify)
        workflow.add_node("format", self._format)
        
        # Define edges: prepare_prompt → generate → classify → format
        workflow.set_entry_point("prepare_prompt")
        workflow.add_edge("prepare_prompt", "generate")
        workflow.add_edge("generate", "classify")
        workflow.add_edge("classify", "format")
        workflow.add_edge("format", END)
        
        return workflow.compile()
    
    # Node implementations
    def _prepare_prompt(self, state: FunctionDocState) -> FunctionDocState:
        """
        Node 1: Prepare prompt for LLM
        
        Constructs a detailed prompt including function metadata
        """
        func = state['func']
        logger.info(f"Preparing prompt for function: {func.name}")
        
        # Build user prompt with function information
        prompt = self._build_user_prompt(func)
        state['prompt'] = prompt
        
        return state

    def _generate(self, state: FunctionDocState) -> FunctionDocState:
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
            raise e
        
        return state
    
    def _format(self, state: FunctionDocState) -> FunctionDocState:
        """
        Node 3: Format output as standard Markdown
        
        Ensures consistent formatting and structure
        """
        logger.info("Formatting documentation")
        
        raw = state['raw_output']
        func = state['func']
        
        # Basic formatting: ensure proper structure
        formatted = self._ensure_markdown_structure(raw, func)
        state['documentation'] = formatted
        
        return state
    
    # Helper methods
    def _build_system_prompt(self) -> str:
        """Build system prompt for the LLM"""
        return """
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
        prompt = f"""
        Generate documentation for the following StarRocks SQL function:
        
        **Function Name**: {func.name}
        **Aliases**: {', '.join(func.alias) if func.alias else 'None'}
        **Signatures**: 
        {chr(10).join([f"  - {sig}" for sig in func.signature])}
        **Implementation Functions**: 
        {chr(10).join([f"  - {impl}" for impl in func.implement_fns])}
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
        
        logger.info(f"Classifying function: {func.name} (current: {func.catalog})")
        
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
            logger.info(f"Classified {func.name} as: {catalog}")
            
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
        logger.info(f"Generating documentation for function: {func.name}")
        
        # Initialize state
        initial_state = FunctionDocState(
            func=func,
            prompt="",
            raw_output="",
            documentation=""
        )
        
        # Run workflow
        final_state = self.workflow.invoke(initial_state)
        
        logger.info(f"Documentation generated ({len(final_state['documentation'])} chars)")
        
        return final_state['documentation']
