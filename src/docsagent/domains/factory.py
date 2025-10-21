"""Factory functions for creating documentation pipelines"""

from loguru import logger

from docsagent.core.pipeline import DocGenerationPipeline
from pathlib import Path
from typing import Tuple

from docsagent.domains.models import ConfigItem
from docsagent.domains.fe_config.extractor import FEConfigExtractor
from docsagent.domains.fe_config.generator import FEConfigDocGenerator
from docsagent.domains.fe_config.persister import FEConfigPersister

from docsagent.domains.be_config.extractor import BEConfigExtractor
from docsagent.domains.be_config.persister import BEConfigPersister
from docsagent.domains.be_config.generator import BEConfigDocGenerator

from docsagent.domains.variables.persister import VariablesPersister
from docsagent.domains.variables.generator import VariablesDocGenerator
from docsagent.domains.variables.extractor import VariablesExtractor

from docsagent.agents.translation_agent import TranslationAgent
from docsagent import config


def create_fe_config_pipeline() -> DocGenerationPipeline[ConfigItem]:
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
        persister=persister,
        item_type_name="FE Config"
    )
    
    logger.info("Pipeline created")
    return pipeline


def create_be_config_pipeline():
    logger.info("Creating BE Config pipeline...")
    
    logger.debug(f"Config: STARROCKS_HOME={config.STARROCKS_HOME}")
    logger.debug(f"        DOCS_MODULE_DIR={config.DOCS_MODULE_DIR}")
    logger.debug(f"        META_DIR={config.META_DIR}")
    
    logger.debug("Initializing components...")
    
    extractor = BEConfigExtractor()
    logger.debug("✓ BEConfigExtractor")
    
    generator = BEConfigDocGenerator()
    logger.debug("✓ BEConfigDocGenerator")
    
    translation_agent = TranslationAgent()
    logger.debug("✓ TranslationAgent")
    
    persister = BEConfigPersister()
    logger.debug("✓ BEConfigPersister")
    
    pipeline = DocGenerationPipeline[ConfigItem](
        extractor=extractor,
        doc_generator=generator,
        translation_agent=translation_agent,
        persister=persister,
        item_type_name="BE Config"
    )
    
    logger.info("Pipeline created")
    return pipeline


def create_variable_pipeline():
    logger.info("Creating Variable pipeline...")
    
    logger.debug(f"Config: STARROCKS_HOME={config.STARROCKS_HOME}")
    logger.debug(f"        DOCS_MODULE_DIR={config.DOCS_MODULE_DIR}")
    logger.debug(f"        META_DIR={config.META_DIR}")
    
    logger.debug("Initializing components...")
    
    extractor = VariablesExtractor()
    logger.debug("✓ VariablesExtractor")
    
    generator = VariablesDocGenerator()
    logger.debug("✓ VariablesDocGenerator")
    
    translation_agent = TranslationAgent()
    logger.debug("✓ TranslationAgent")
    
    persister = VariablesPersister()
    logger.debug("✓ VariablesPersister")
    
    pipeline = DocGenerationPipeline[ConfigItem](
        extractor=extractor,
        doc_generator=generator,
        translation_agent=translation_agent,
        persister=persister,
        item_type_name="Variables"
    )
    
    logger.info("Pipeline created")
    return pipeline

def create_function_pipeline():
    """
    Create a pipeline for function documentation (placeholder).
    
    TODO: Implement when function support is added.
    
    Returns:
        DocGenerationPipeline configured for functions
    """
    raise NotImplementedError("Function pipeline not yet implemented")
