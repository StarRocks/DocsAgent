#!/usr/bin/env python3
"""
Debug script to understand the tree-sitter Java AST structure for annotations
"""

import tree_sitter_java
from tree_sitter import Language, Parser

# Sample Java code with @ConfField annotation
test_code = '''
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
    
    // Regular field without annotation - should be ignored
    public static String regular_field = Config.default_value ? "yes" : "no";
}
'''

# Initialize parser
lang = Language(tree_sitter_java.language())
parser = Parser(lang)

# Parse the code
tree = parser.parse(test_code.encode('utf-8'))
root = tree.root_node

def print_tree(node, indent=0, max_depth=10):
    """Recursively print the AST tree structure"""
    if indent > max_depth:
        return
    
    prefix = "  " * indent
    text = test_code[node.start_byte:node.end_byte]
    
    # Truncate long text for readability
    if len(text) > 50:
        text = text[:50] + "..."
    text = text.replace('\n', '\\n')
    
    print(f"{prefix}{node.type} [{node.start_point[0]}:{node.start_point[1]}] '{text}'")
    
    for child in node.children:
        print_tree(child, indent + 1, max_depth)

print("=" * 80)
print("Complete AST Structure:")
print("=" * 80)
print_tree(root, max_depth=15)

print("\n" + "=" * 80)
print("Looking for annotation nodes specifically:")
print("=" * 80)

def find_annotations(node):
    """Find all annotation nodes in the tree"""
    if node.type == 'annotation':
        print(f"\nFound annotation at line {node.start_point[0]}:")
        print_tree(node, indent=1, max_depth=5)
    
    for child in node.children:
        find_annotations(child)

find_annotations(root)
