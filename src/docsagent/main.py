"""
DocsAgent - StarRocks Documentation Generation Tool

Main entry point for the command-line interface.
"""
import sys
import os
import argparse
from pathlib import Path
from loguru import logger

from docsagent.domains.factory import create_fe_config_pipeline
from docsagent import config


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
  %(prog)s -g --type fe_config
  
  # Load from existing configs and update
  %(prog)s -g --type fe_config --config ./conf/agent.conf
        """
    )
    
    # Add arguments
    parser.add_argument(
        '-g', '--generate',
        action='store_true',
        help='Generate documentation'
    )
    
    parser.add_argument(
        '-t', '--type',
        choices=['fe_config', 'be_config'],
        default='fe_config',
        help='Type of documentation to generate (default: fe_config)'
    )
    
    parser.add_argument(
        '-c', '--config',
        type=str,
        help='Load existing config'
    )
    
    args = parser.parse_args()

    if args.config is not None:
        config.reload_config(args.config)
    else:
        config.reload_config()

    # Initialize logger
    init_logger()
    
    # Execute command
    if args.generate:
        generate_docs(args)
    else:
        parser.print_help()


def generate_docs(args):
    """Generate documentation based on arguments"""
    logger.info("=" * 60)
    logger.info("DocsAgent - Documentation Generation")
    logger.info("=" * 60)
    
    # Create pipeline
    if args.type in ['fe_config', 'be_config']:
        logger.info(f"Creating {args.type} documentation pipeline...")
        pipeline = create_fe_config_pipeline()
    else:
        logger.error(f"Unsupported type: {args.type}")
        sys.exit(1)
    
    # Run pipeline
    try:
        logger.info(f"Starting documentation generation for {args.type}...")
        logger.info("-" * 60)
        
        stats = pipeline.run(
            source=None,  # Use default paths from config
            limit=None,   # Generate all items (remove limit=1 for production)
            output_dir=config.DOCS_OUTPUT_DIR,
            target_langs=config.TARGET_LANGS,
            force_search_code=False,
            ignore_miss_usage=True
        )
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ Documentation generation completed successfully!")
        logger.info(f"   • Total items: {stats.get('total_items', 0)}")
        logger.info(f"   • Languages: {', '.join(config.TARGET_LANGS)}")
        logger.info(f"   • Output: {config.DOCS_OUTPUT_DIR}")
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"\n❌ Documentation generation failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    main()

