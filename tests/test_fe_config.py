#!/usr/bin/env python3

"""
Test script for FE Config Parser
"""

import os

from src.docsagent.code_extract.fe_config_parser import FEConfigParser

def test_parser():
    """Test the FE config parser with a mock Java file"""
    
    # Create a test Java file content
    test_java_content = '''
package com.starrocks.common;

public class TestConfig {
    // Enable user defined functions
    @ConfField(mutable = false, description = "Enable UDF feature")
    public static boolean enable_udf = false;
    
    /**
     * Maximum number of connections
     */
    @ConfField(mutable = true)
    public static int max_connections = 1000;

    @ConfField
    public static String regular_field = "value";

    
    // Regular field without annotation - should be ignored
    public static String regular_field = Config.default_value ? "yes" : "no";
}
'''
    
    # Create temporary test file
    test_file_path = "/tmp/TestConfig.java"
    with open(test_file_path, 'w') as f:
        f.write(test_java_content)
    
    try:
        # Test the parser
        parser = FEConfigParser()
        config_items = parser._extract_config_items(test_file_path)
        
        print(f"Found {len(config_items)} config items:")
        for item in config_items:
            print(f"  - {item['name']}: {item['type']} = {item['defaultValue']}")
            print(f"    Comment: {item['comment']}")
            print(f"    Mutable: {item['isMutable']}")
            print(f"    File: {item['file_path']}")
            print(f"    Line: {item['line_number']}")
            print()
    
    finally:
        # Clean up
        if os.path.exists(test_file_path):
            os.remove(test_file_path)

if __name__ == "__main__":
    test_parser()