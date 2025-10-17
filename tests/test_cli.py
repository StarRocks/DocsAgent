"""
Test CLI for DocsAgent

A simple command-line interface for testing various DocsAgent functionalities.
"""
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from docsagent import main
from docsagent import config
from docsagent.agents.config_pipeline import ConfigGenerationPipeline


if __name__ == '__main__':
    config.reload_config()

    main.init_logger()
    pipeline = ConfigGenerationPipeline()

    pipeline.run(
        output_dir=config.DOCS_OUTPUT_DIR,
        target_langs=config.TARGET_LANGS,
        limit=1
    )