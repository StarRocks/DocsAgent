"""
FE Config domain: Extract, generate, and persist FE configuration documentation
"""

from docsagent.domains.fe_config.extractor import FEConfigExtractor
from docsagent.domains.fe_config.generator import FEConfigDocGenerator
from docsagent.domains.fe_config.persister import FEConfigPersister
from docsagent.domains.fe_config.git_persister import FEConfigGitPersister

__all__ = [
    'FEConfigExtractor',
    'FEConfigDocGenerator',
    'FEConfigPersister',
    'FEConfigGitPersister',
]
