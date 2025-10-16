#!/usr/bin/env python3
"""
Simple test script for DocsAgent demo
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from docsagent.agents.llm import create_chat_model
from docsagent.agents import create_doc_workflow, ConfigDocumentAgent
from docsagent.code_extract.fe_config_parser import FEConfigParser
from loguru import logger

def test_fe_config_extraction():
    """Test FE config extraction"""
    logger.info("Testing FE config extraction...")
    
    parser = FEConfigParser()
    items = parser.extract_all_configs()
    
    logger.info(f"✓ Extracted {len(items)} FE config items")
    
    if items:
        logger.info(f"Sample item: {items[0].get('name', 'N/A')}")
    
    return len(items) > 0

def test_llm_basic():
    """Test basic chat model creation"""
    logger.info("Testing chat model creation...")
    
    try:
        chat_model = create_chat_model(model='openai:gpt-3.5-turbo', api_key='test-key')
        logger.info(f"✓ Chat model created successfully")
        return True
    except Exception as e:
        logger.error(f"✗ Chat model creation failed: {e}")
        return False

def test_workflow_creation():
    """Test workflow creation"""
    logger.info("Testing workflow creation...")
    
    try:
        chat_model = create_chat_model(model='openai:gpt-3.5-turbo', api_key='test-key')
        workflow = create_doc_workflow(chat_model=chat_model)
        logger.info("✓ Workflow created successfully")
        return True
    except Exception as e:
        logger.error(f"✗ Workflow creation failed: {e}")
        return False

def test_config_doc_agent():
    """Test ConfigDocumentAgent"""
    logger.info("Testing ConfigDocumentAgent...")
    
    try:
        chat_model = create_chat_model(model='openai:gpt-3.5-turbo', api_key='test-key')
        agent = ConfigDocumentAgent(chat_model=chat_model)
        logger.info("✓ ConfigDocumentAgent created successfully")
        return True
    except Exception as e:
        logger.error(f"✗ ConfigDocumentAgent creation failed: {e}")
        return False

def main():
    """Run all tests"""
    logger.info("=" * 60)
    logger.info("DocsAgent Demo Test Suite")
    logger.info("=" * 60)
    
    tests = [
        ("FE Config Extraction", test_fe_config_extraction),
        ("Chat Model Creation", test_llm_basic),
        ("Workflow Creation", test_workflow_creation),
        ("ConfigDocumentAgent", test_config_doc_agent),
    ]
    
    results = []
    for name, test_func in tests:
        logger.info(f"\nRunning: {name}")
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            logger.error(f"Test failed with exception: {e}")
            results.append((name, False))
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{status}: {name}")
    
    logger.info(f"\nTotal: {passed}/{total} tests passed")
    
    return passed == total

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
