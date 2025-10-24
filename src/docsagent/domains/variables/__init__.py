"""
Variables domain: Extract, generate, and persist system variables documentation
"""

from docsagent.domains.variables.extractor import VariablesExtractor
from docsagent.domains.variables.generator import VariablesDocGenerator
from docsagent.domains.variables.persister import VariablesPersister
from docsagent.domains.variables.git_persister import VariablesGitPersister

__all__ = [
    'VariablesExtractor',
    'VariablesDocGenerator',
    'VariablesPersister',
    'VariablesGitPersister',
]
