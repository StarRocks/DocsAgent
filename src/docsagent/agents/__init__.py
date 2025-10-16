"""
Agents module for document generation
"""
from docsagent.agents.llm import create_chat_model, get_default_chat_model

__all__ = [
    'create_chat_model',
    'get_default_chat_model',
    'create_doc_workflow'
]
