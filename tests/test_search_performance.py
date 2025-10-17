#!/usr/bin/env python3

import time
import tempfile
from pathlib import Path
from docsagent.code_extract.code_search import CodeFileSearch

def create_test_files(temp_dir: Path, file_count: int = 100):
    """Create test Java files with various keywords"""
    keywords_in_files = [
        "class", "public", "private", "static", "void",
        "String", "int", "boolean", "final", "return",
        "import", "package", "extends", "implements", "interface",
        "try", "catch", "throw", "throws", "finally",
        "if", "else", "for", "while", "switch",
    ]
    
    for i in range(file_count):
        file_path = temp_dir / f"TestFile{i}.java"
        with open(file_path, 'w') as f:
            f.write(f"package com.test{i};\n\n")
            f.write(f"public class TestFile{i} {{\n")
            # Add some keywords
            for keyword in keywords_in_files[i % len(keywords_in_files):i % len(keywords_in_files) + 5]:
                f.write(f"    private {keyword} field{i};\n")
            f.write("}\n")
    
    return temp_dir

def test_search_performance():
    """Test search performance with large keyword list"""
    # Create test data
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        print(f"Creating test files in {temp_path}...")
        create_test_files(temp_path, file_count=200)
        
        # Create large keyword list (simulate 700+ keywords)
        keywords = [
            f"keyword_{i}" for i in range(500)  # Non-existent keywords
        ] + [
            "class", "public", "private", "static", "void",
            "String", "int", "boolean", "final", "return",
            "import", "package", "extends", "implements", "interface",
            "try", "catch", "throw", "throws", "finally",
            "if", "else", "for", "while", "switch",
        ] * 10  # Some real keywords
        
        print(f"Testing with {len(keywords)} keywords and 200 files...")
        
        # Test search performance
        searcher = CodeFileSearch([str(temp_path)])
        
        start_time = time.time()
        results = searcher.search(keywords)
        end_time = time.time()
        
        elapsed = end_time - start_time
        print(f"\n=== Performance Results ===")
        print(f"Total keywords: {len(keywords)}")
        print(f"Total files: 200")
        print(f"Time taken: {elapsed:.2f} seconds")
        print(f"Keywords found: {len(results)}")
        print(f"Average time per file: {elapsed/200*1000:.2f} ms")
        
        # Show some results
        print(f"\n=== Sample Results ===")
        for keyword, files in list(results.items())[:5]:
            print(f"{keyword}: {len(files)} files")
        
        # Performance benchmark
        if elapsed < 5:
            print(f"\n✓ Performance: GOOD (< 5s)")
        elif elapsed < 10:
            print(f"\n⚠ Performance: ACCEPTABLE (5-10s)")
        else:
            print(f"\n✗ Performance: NEEDS IMPROVEMENT (> 10s)")

if __name__ == "__main__":
    test_search_performance()
