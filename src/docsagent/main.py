"""
DocsAgent - StarRocks Documentation Generation Tool

Main entry point for the command-line interface.
"""
import sys
import os
import argparse
from pathlib import Path
from loguru import logger

from docsagent.agents.llm import create_chat_model
from docsagent.agents import create_doc_workflow
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


def cmd_generate(args):
    """Generate documentation from source code"""
    logger.info(f"Generating documentation for {args.type}")
    logger.info(f"Model: {args.model}")
    logger.info(f"Output: {args.output}")
    
    # Create chat model
    chat_model = create_chat_model(
        model=args.model,
        api_key=args.api_key,
        temperature=args.temperature
    )
    
    # Create document generation workflow
    workflow = create_doc_workflow(chat_model=chat_model)
    
    # Generate documentation
    docs = workflow.generate_documents(
        config_type=args.type,
        output_file=args.output
    )
    
    logger.info(f"✓ Generated documentation for {len(docs)} items")
    logger.info(f"✓ Results saved to: {args.output}")


def cmd_extract(args):
    """Extract metadata from source code (without generating docs)"""
    logger.info(f"Extracting metadata for {args.type}")
    
    from docsagent.code_extract.fe_config_parser import FEConfigParser
    
    if args.type == 'fe_config':
        parser = FEConfigParser()
        items = parser.extract_all_configs()
        
        # Save to file
        import json
        output_dir = Path(args.output).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✓ Extracted {len(items)} items")
        logger.info(f"✓ Metadata saved to: {args.output}")
    else:
        logger.error(f"Unsupported type: {args.type}")


def cmd_info(args):
    """Show configuration information"""
    logger.info("DocsAgent Configuration:")
    logger.info(f"  STARROCKS_HOME: {config.STARROCKS_HOME or '(not set)'}")
    logger.info(f"  LLM_MODEL: {config.LLM_MODEL}")
    logger.info(f"  LLM_API_KEY: {'***' + config.LLM_API_KEY[-4:] if config.LLM_API_KEY else '(not set)'}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='DocsAgent - StarRocks Documentation Generation Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate FE config documentation
  %(prog)s generate --type fe_config --output output/fe_config_docs.json
  
  # Extract metadata only
  %(prog)s extract --type fe_config --output meta/fe_config/items.json
  
  # Show configuration
  %(prog)s info
  
  # Use a specific model (format: provider:model-name)
  %(prog)s generate --type fe_config --model openai:gpt-4 --output output/docs.json
  %(prog)s generate --type fe_config --model anthropic:claude-3-sonnet-20240229 --output output/docs.json
        """
    )
    
    # Global options
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
    parser.add_argument('--log-dir', default='logs', help='Log directory (default: logs)')
    
    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Generate command
    generate_parser = subparsers.add_parser('generate', help='Generate documentation')
    generate_parser.add_argument(
        '--type',
        choices=['fe_config', 'be_config', 'variable', 'function'],
        default='fe_config',
        help='Type of documentation to generate (default: fe_config)'
    )
    generate_parser.add_argument(
        '--output', '-o',
        default='output/generated_docs.json',
        help='Output file path (default: output/generated_docs.json)'
    )
    generate_parser.add_argument(
        '--model',
        default=config.LLM_MODEL,
        help=f'LLM model to use (format: provider:model-name, default: {config.LLM_MODEL})'
    )
    generate_parser.add_argument(
        '--api-key',
        default=config.LLM_API_KEY,
        help='API key for the LLM model'
    )
    generate_parser.add_argument(
        '--temperature',
        type=float,
        default=0.5,
        help='Temperature for generation (default: 0.5)'
    )
    generate_parser.set_defaults(func=cmd_generate)
    
    # Extract command
    extract_parser = subparsers.add_parser('extract', help='Extract metadata only')
    extract_parser.add_argument(
        '--type',
        choices=['fe_config', 'be_config', 'variable', 'function'],
        default='fe_config',
        help='Type of metadata to extract (default: fe_config)'
    )
    extract_parser.add_argument(
        '--output', '-o',
        default='meta/fe_config/items.json',
        help='Output file path (default: meta/fe_config/items.json)'
    )
    extract_parser.set_defaults(func=cmd_extract)
    
    # Info command
    info_parser = subparsers.add_parser('info', help='Show configuration information')
    info_parser.set_defaults(func=cmd_info)
    
    # Parse arguments
    args = parser.parse_args()
    
    # Initialize logger
    log_level = "DEBUG" if args.verbose else "INFO"
    init_logger(log_dir=args.log_dir, log_level=log_level)
    
    # Check if command was provided
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Execute command
    try:
        args.func(args)
    except Exception as e:
        logger.error(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

