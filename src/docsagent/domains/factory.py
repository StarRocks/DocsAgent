"""Factory functions for creating documentation pipelines"""

from loguru import logger

from docsagent.core.pipeline import DocGenerationPipeline
from pathlib import Path
from typing import Tuple

from docsagent.domains.models import ConfigItem
from docsagent.domains.fe_config.extractor import FEConfigExtractor
from docsagent.domains.fe_config.generator import FEConfigDocGenerator
from docsagent.domains.fe_config.persister import FEConfigPersister
from docsagent.agents.translation_agent import TranslationAgent
from docsagent import config


def create_config_pipeline() -> DocGenerationPipeline[ConfigItem]:
    """
    Create FE config documentation pipeline (all components use global config).
    
    Example:
        >>> pipeline = create_config_pipeline()
        >>> pipeline.run(output_dir='output', target_langs=['en', 'zh', 'ja'])
    """
    logger.info("Creating FE Config pipeline...")
    
    logger.debug(f"Config: STARROCKS_HOME={config.STARROCKS_HOME}")
    logger.debug(f"        DOCS_MODULE_DIR={config.DOCS_MODULE_DIR}")
    logger.debug(f"        META_DIR={config.META_DIR}")
    
    logger.debug("Initializing components...")
    
    extractor = FEConfigExtractor()
    logger.debug("✓ FEConfigExtractor")
    
    generator = FEConfigDocGenerator()
    logger.debug("✓ FEConfigDocGenerator")
    
    translation_agent = TranslationAgent()
    logger.debug("✓ TranslationAgent")
    
    persister = FEConfigPersister()
    logger.debug("✓ FEConfigPersister")
    
    pipeline = DocGenerationPipeline[ConfigItem](
        extractor=extractor,
        doc_generator=generator,
        translation_agent=translation_agent,
        persister=persister
    )
    
    logger.success("Pipeline created")
    return pipeline


def create_be_config_pipeline():
    """
    Create a pipeline for BE configuration documentation (placeholder).
    
    TODO: Implement when BE config support is added.
    
    Returns:
        DocGenerationPipeline configured for BE config documentation
    """
    raise NotImplementedError("BE Config pipeline not yet implemented")


def create_variable_pipeline():
    """
    Create a pipeline for session variable documentation (placeholder).
    
    TODO: Implement when variable support is added.
    
    Returns:
        DocGenerationPipeline configured for session variables
    """
    raise NotImplementedError("Variable pipeline not yet implemented")


def create_function_pipeline():
    """
    Create a pipeline for function documentation (placeholder).
    
    TODO: Implement when function support is added.
    
    Returns:
        DocGenerationPipeline configured for functions
    """
    raise NotImplementedError("Function pipeline not yet implemented")
