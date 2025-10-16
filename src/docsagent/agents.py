"""
Document Generation Workflow using LangGraph
"""
from typing import TypedDict, List, Dict, Any, Annotated
from loguru import logger
import json

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from .agents.llm import LLMManager, get_llm
from .code_extract.fe_config_parser import FEConfigParser


# Define the state structure
class DocumentGenerationState(TypedDict):
    """State for document generation workflow"""
    # Input
    config_type: str  # 'fe_config', 'be_config', 'variable', 'function'
    config_items: List[Dict[str, Any]]  # Extracted config items
    
    # Processing
    current_index: int  # Current processing index
    messages: Annotated[list, add_messages]  # Messages for tracking
    
    # Output
    generated_docs: List[Dict[str, Any]]  # Generated documentation
    errors: List[str]  # Errors during processing


class DocumentGenerationAgent:
    """Agent for generating documentation from code metadata"""
    
    def __init__(self, llm: LLMManager = None):
        """
        Initialize the document generation agent
        
        Args:
            llm: LLM manager instance
        """
        self.llm = llm or get_llm()
        self.graph = self._build_graph()
        logger.info("Document Generation Agent initialized")
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(DocumentGenerationState)
        
        # Add nodes
        workflow.add_node("extract_metadata", self._extract_metadata)
        workflow.add_node("generate_doc", self._generate_documentation)
        workflow.add_node("validate_doc", self._validate_documentation)
        
        # Set entry point
        workflow.set_entry_point("extract_metadata")
        
        # Add edges
        workflow.add_edge("extract_metadata", "generate_doc")
        workflow.add_edge("generate_doc", "validate_doc")
        workflow.add_edge("validate_doc", END)
        
        return workflow.compile()
    
    def _extract_metadata(self, state: DocumentGenerationState) -> DocumentGenerationState:
        """Extract metadata from source code"""
        logger.info(f"Extracting metadata for {state['config_type']}")
        
        config_type = state.get('config_type', 'fe_config')
        
        if config_type == 'fe_config':
            parser = FEConfigParser()
            config_items = parser.extract_all_configs()
            logger.info(f"Extracted {len(config_items)} FE config items")
        else:
            logger.warning(f"Unsupported config type: {config_type}")
            config_items = []
        
        return {
            **state,
            "config_items": config_items,
            "current_index": 0,
            "generated_docs": [],
            "errors": [],
            "messages": [{"role": "system", "content": f"Extracted {len(config_items)} items"}]
        }
    
    def _generate_documentation(self, state: DocumentGenerationState) -> DocumentGenerationState:
        """Generate documentation for each config item"""
        logger.info("Generating documentation")
        
        config_items = state.get('config_items', [])
        generated_docs = []
        errors = []
        
        for idx, item in enumerate(config_items):
            try:
                logger.info(f"Generating doc for item {idx + 1}/{len(config_items)}: {item.get('name', 'unknown')}")
                
                # Generate documentation using LLM
                doc = self._generate_single_doc(item)
                generated_docs.append({
                    **item,
                    "documentation": doc
                })
                
            except Exception as e:
                error_msg = f"Error generating doc for {item.get('name', 'unknown')}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        return {
            **state,
            "generated_docs": generated_docs,
            "errors": errors,
            "messages": state.get("messages", []) + [
                {"role": "system", "content": f"Generated {len(generated_docs)} docs with {len(errors)} errors"}
            ]
        }
    
    def _generate_single_doc(self, config_item: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate documentation for a single config item
        
        Args:
            config_item: Configuration item metadata
            
        Returns:
            Dictionary with documentation in multiple languages
        """
        # Build prompt
        system_prompt = """You are a technical documentation writer for StarRocks database.
Your task is to generate clear, concise, and accurate documentation for configuration items.

The documentation should include:
1. Brief description of the configuration
2. Default value and valid range
3. When to modify this configuration
4. Example usage or impact

Keep the documentation professional and consistent with database documentation style."""

        user_prompt = f"""Generate documentation for the following StarRocks FE configuration:

Name: {config_item.get('name', 'N/A')}
Type: {config_item.get('type', 'N/A')}
Default Value: {config_item.get('defaultValue', 'N/A')}
Mutable: {config_item.get('mutable', 'N/A')}
Description: {config_item.get('description', 'N/A')}

Generate documentation in Chinese (zh) only for this demo.
Format your response as JSON with this structure:
{{
    "zh": "# 配置名称\\n\\n## 描述\\n...\\n\\n## 默认值\\n...\\n\\n## 使用建议\\n..."
}}
"""

        try:
            response = self.llm.generate_structured(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.5
            )
            return response
        except Exception as e:
            logger.error(f"Failed to generate documentation: {e}")
            # Return a fallback documentation
            return {
                "zh": f"# {config_item.get('name', '未知配置')}\n\n{config_item.get('description', '暂无描述')}"
            }
    
    def _validate_documentation(self, state: DocumentGenerationState) -> DocumentGenerationState:
        """Validate generated documentation"""
        logger.info("Validating documentation")
        
        generated_docs = state.get('generated_docs', [])
        
        # Basic validation: check if documentation was generated
        valid_count = sum(1 for doc in generated_docs if doc.get('documentation'))
        
        logger.info(f"Validation complete: {valid_count}/{len(generated_docs)} docs have content")
        
        return {
            **state,
            "messages": state.get("messages", []) + [
                {"role": "system", "content": f"Validated {valid_count}/{len(generated_docs)} documents"}
            ]
        }
    
    def generate_documents(
        self,
        config_type: str = 'fe_config',
        output_file: str = None
    ) -> List[Dict[str, Any]]:
        """
        Generate documentation for configuration items
        
        Args:
            config_type: Type of configuration ('fe_config', 'be_config', etc.)
            output_file: Optional output file path to save results
            
        Returns:
            List of generated documentation items
        """
        logger.info(f"Starting document generation for {config_type}")
        
        # Initialize state
        initial_state = {
            "config_type": config_type,
            "config_items": [],
            "current_index": 0,
            "messages": [],
            "generated_docs": [],
            "errors": []
        }
        
        # Run the workflow
        result = self.graph.invoke(initial_state)
        
        # Save results if output file specified
        if output_file:
            self._save_results(result['generated_docs'], output_file)
        
        # Log summary
        logger.info(f"Document generation complete:")
        logger.info(f"  - Total items: {len(result.get('config_items', []))}")
        logger.info(f"  - Generated docs: {len(result.get('generated_docs', []))}")
        logger.info(f"  - Errors: {len(result.get('errors', []))}")
        
        if result.get('errors'):
            for error in result['errors']:
                logger.error(f"  - {error}")
        
        return result['generated_docs']
    
    def _save_results(self, docs: List[Dict[str, Any]], output_file: str):
        """Save generated documentation to file"""
        try:
            import os
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(docs, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Results saved to {output_file}")
        except Exception as e:
            logger.error(f"Failed to save results: {e}")


def create_doc_agent(llm: LLMManager = None) -> DocumentGenerationAgent:
    """Create a document generation agent"""
    return DocumentGenerationAgent(llm=llm)
