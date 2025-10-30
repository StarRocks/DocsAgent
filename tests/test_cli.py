"""
Test CLI for DocsAgent

A simple command-line interface for testing various DocsAgent functionalities.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from docsagent import main
from docsagent import config
from docsagent.domains.factory import create_fe_config_pipeline
from docsagent.domains.factory import create_be_config_pipeline
from docsagent.domains.factory import create_variable_pipeline
from docsagent.domains.factory import create_function_pipeline

if __name__ == '__main__':
    config.reload_config()

    main.init_logger()
    # pipeline = create_variable_pipeline()
    # pipeline = create_be_config_pipeline()
    pipeline = create_function_pipeline()

    # Use the source path from config extractor (if any) or pass None to use defaults
    pipeline.run(
        output_dir=config.DOCS_OUTPUT_DIR,
        target_langs=config.TARGET_LANGS,
        force_search_code=True,
        ignore_miss_usage=False,
        without_llm=False,
        limit=1,
        auto_commit=False,
        create_pr=False
    )