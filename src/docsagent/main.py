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
  # Extract FE config metadata and generate documentation
  %(prog)s -e -g -t fe_config --config ./conf/agent.conf
  
  # Generate BE config documentation with git commit
  %(prog)s -g -t be_config --git-ci
  
  # Generate variables documentation and create PR
  %(prog)s -g -t variables --git-ci --git-pr
  
  # Extract functions metadata only
  %(prog)s -e -t functions
  
  # Generate with force code search and limit
  %(prog)s -g -t fe_config -f -l 10
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
        '--config',
        type=str,
        default=None,
        help='Path to configuration file (default: conf/agent.conf)'
    )
    
    parser.add_argument(
        '-f', '--force_search_code',
        action='store_true',
        help='Force search code even if meta file exists'
    )
    
    parser.add_argument(
        '-i', '--ignore_miss_usage',
        action='store_true',
        help='Ignore missing usage information'
    )
    
    parser.add_argument(
        '-l', '--limit',
        type=int,
        default=None,
        help='Limit the number of items to process'
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
    
    # Load configuration
    try:
        if args.config is not None:
            config.reload_config(args.config)
            logger.info(f"Loaded configuration from: {args.config}")
        else:
            config.reload_config()
            logger.info("Loaded default configuration")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)

    # Initialize logger
    init_logger(log_dir=config.LOG_DIR, log_level=config.LOG_LEVEL)
    
    # Check if at least one action is specified
    if not args.extract and not args.generate:
        logger.warning("No action specified. Use -e to extract or -g to generate.")
        parser.print_help()
        sys.exit(1)
    
    # Execute actions
    try:
        if args.extract:
            extract_meta(args)
        
        if args.generate:
            generate_docs(args)
    except Exception as e:
        logger.exception(f"Execution failed: {e}")
        sys.exit(1)

def extract_meta(args):
    """Extract metadata from documentation files"""
    logger.info("=" * 60)
    logger.info(f"EXTRACTING METADATA: {args.type.upper()}")
    logger.info("=" * 60)
    
    try:
        if args.type in ['fe_config', 'be_config']:
            # Extract config metadata
            extractor = ConfigMetaExtract()
            if args.type == 'fe_config':
                configs = extractor.extract_fe()
                logger.success(f"✓ Extracted {len(configs)} FE configs")
            else:
                configs = extractor.extract_be()
                logger.success(f"✓ Extracted {len(configs)} BE configs")
        
        elif args.type == 'variables':
            # Extract variables metadata
            extractor = VariablesMetaExtract()
            variables = extractor.extract()
            logger.success(f"✓ Extracted {len(variables)} variables")
        
        elif args.type == 'functions':
            # Extract functions metadata
            extractor = FunctionMetaExtract()
            functions = extractor.extract()
            logger.success(f"✓ Extracted {len(functions)} functions")
        
        logger.info("=" * 60)
        logger.success("Metadata extraction completed")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.exception(f"Failed to extract metadata: {e}")
        raise


def generate_docs(args):
    """Generate documentation based on type"""
    logger.info("=" * 60)
    logger.info(f"GENERATING DOCUMENTATION: {args.type.upper()}")
    logger.info("=" * 60)
    
    if args.git_pr:
        args.git_ci = True  # Ensure commit is enabled if PR is requested
    
    # Log configuration
    logger.info(f"Configuration:")
    logger.info(f"  Type: {args.type}")
    logger.info(f"  Force search code: {args.force_search_code}")
    logger.info(f"  Limit: {args.limit or 'None'}")
    logger.info(f"  Git commit: {args.git_ci}")
    logger.info(f"  Git PR: {args.git_pr}")
    logger.info(f"  Target languages: {config.TARGET_LANGS}")
    logger.info(f"  Output directory: {config.DOCS_OUTPUT_DIR}")
    
    # Update config if needed
    if args.force_search_code:
        config.FORCE_RESEARCH_CODE = True
        logger.info("  Force code search: ENABLED")
    
    try:
        # Create pipeline based on type
        logger.info("Creating pipeline...")
        if args.type == 'fe_config':
            pipeline = factory.create_fe_config_pipeline()
        elif args.type == 'be_config':
            pipeline = factory.create_be_config_pipeline()
        elif args.type == 'variables':
            pipeline = factory.create_variable_pipeline()
        elif args.type == 'functions':
            pipeline = factory.create_function_pipeline()
        else:
            logger.error(f"Unknown type: {args.type}")
            return
        
        # Run pipeline with git options
        logger.info("Running pipeline...")
        result = pipeline.run(
            output_dir=config.DOCS_OUTPUT_DIR,
            target_langs=config.TARGET_LANGS,
            auto_commit=args.git_ci,
            create_pr=args.git_pr,
            limit=args.limit
        )
        
        # Log results
        logger.info("=" * 60)
        logger.success(f"Documentation generation completed!")
        logger.info(f"Total items processed: {result['total']}")
        
        if result.get('success', 0) > 0:
            logger.success(f"  ✓ Success: {result['success']}")
        if result.get('failed', 0) > 0:
            logger.warning(f"  ✗ Failed: {result['failed']}")
        if result.get('skipped', 0) > 0:
            logger.info(f"  ⊘ Skipped: {result['skipped']}")
        
        logger.info("=" * 60)
        
    except Exception as e:
        logger.exception(f"Failed to generate documentation: {e}")
        raise


if __name__ == '__main__':
    main()

