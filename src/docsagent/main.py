"""
DocsAgent - StarRocks Documentation Generation Tool

Main entry point for the command-line interface.
"""
import sys
import os
import argparse
from pathlib import Path
from loguru import logger

from docsagent import config
from docsagent.domains import factory
from docsagent.docs_extract.config_meta_extract import ConfigMetaExtract
from docsagent.docs_extract.function_meta_extract import FunctionMetaExtract
from docsagent.docs_extract.variables_meta_extract import VariablesMetaExtract


def init_logger(log_dir: str = "logs", max_size: str = "10 MB", log_level: str = "INFO"):
    """Initialize logger with console and file output"""
    os.makedirs(log_dir, exist_ok=True)
    logger.remove()                         
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        colorize=True,
    )
    logger.add(
        f"{log_dir}/app.{{time:YYYY-MM-DD}}.log",
        level="INFO",
        rotation=max_size,
        retention="7 days",
        compression="zip",
        enqueue=True,
        encoding="utf-8",
    )

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='DocsAgent - StarRocks Documentation Generation Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
  Examples:
  # Generate FE config documentation
  %(prog)s -e -g -t fe_config/be_config/variable/functions --config ./conf/agent.conf --git-ci --git-pr
        """
    )
    
    # Add arguments
    parser.add_argument(
        '-e', '--extract',
        action='store_true',
        help='Enable extraction meta from documents'
    )
    
    parser.add_argument(
        '-g', '--generate',
        action='store_true',
        help='Generate documentation'
    )
    
    parser.add_argument(
        '-t', '--type',
        choices=['fe_config', 'be_config', 'variables', 'functions'],
        default='fe_config',
        help='Type of documentation to generate (default: fe_config)'
    )
    
    parser.add_argument(
        '-c', '--config',
        type=str,
        help='Load existing config'
    )
    
    parser.add_argument(
        '--git-ci',
        action='store_true',
        help='Enable commit to git'
    )

    parser.add_argument(
        '--git-pr',
        action='store_true',
        help='Enable create PRs to remote git repository'
    )
    
    args = parser.parse_args()

    if args.config is not None:
        config.reload_config(args.config)
    else:
        config.reload_config()

    # Initialize logger
    init_logger()
    
    if args.extract:
        extract_meta(args)
    
    # Execute command
    if args.generate:
        generate_docs(args)

def extract_meta(args):
    pass


def generate_docs(args):
    pass


if __name__ == '__main__':
    main()

