#!/usr/bin/env python3

import os
import json
from pathlib import Path

from docsagent.code_extract.fe_config_parser import FEConfigParser

def test_meta_building():
    test_dir = "/tmp/test_starrocks"
    fe_dir = f"{test_dir}/fe/fe-core/src/main/java/com/starrocks"
    os.makedirs(fe_dir, exist_ok=True)

    config_content = '''
package com.starrocks.common;

public class Config {
    // Enable user defined functions
    @ConfField(mutable = false, description = "Enable UDF feature")
    public static boolean enable_udf = false;
    
    /**
     * Maximum number of connections per frontend
     */
    @ConfField(mutable = true)
    public static int max_connections = 1000;
    
    // Query timeout in seconds
    @ConfField(mutable = true, description = "Query timeout")  
    public static long query_timeout = 300L;
}
'''

    config_file = f"{fe_dir}/Config.java"
    with open(config_file, 'w') as f:
        f.write(config_content)

    try:
        parser = FEConfigParser(code_paths=[fe_dir])
        meta = parser.build_meta()
        print(json.dumps(meta, indent=2, ensure_ascii=False))
        assert meta["total_count"] >= 2
    finally:
        import shutil
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)

if __name__ == "__main__":
    test_meta_building()