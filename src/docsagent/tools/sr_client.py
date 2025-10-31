#!/usr/bin/env python3
# Copyright 2021-present StarRocks, Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
StarRocks Client Tool for executing READ-ONLY SQL queries

This tool provides a safe, read-only interface for agents to query StarRocks.
ONLY SELECT queries (with functions and constants) are allowed.
"""

from typing import Optional, List, Dict, Any
import re
import mysql.connector
from mysql.connector import Error
from loguru import logger
from langchain_core.tools import tool


class StarRocksClient:
    """
    StarRocks database client wrapper - READ ONLY mode
    
    Only allows SELECT queries for safe database access.
    
    Example configuration in conf/agent.conf:
        SR_HOST=localhost
        SR_PORT=9030
        SR_USER=root
        SR_PASSWORD=
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 9030,
        user: str = "root",
        password: str = ""
    ):
        """
        Initialize StarRocks client
        
        Args:
            host: StarRocks FE host
            port: StarRocks FE query port (default: 9030)
            user: Database user
            password: Database password
        """
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.connection = None
        
    def connect(self) -> bool:
        """
        Establish connection to StarRocks
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password
            )
            
            if self.connection.is_connected():
                logger.debug(f"Connected to StarRocks at {self.host}:{self.port}")
                return True
            return False
            
        except Error as e:
            logger.error(f"Error connecting to StarRocks: {e}")
            return False
    
    def disconnect(self):
        """Close the database connection"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            logger.debug("Disconnected from StarRocks")
    
    def _validate_select_query(self, sql: str) -> tuple[bool, str]:
        """
        Validate that the query is a safe SELECT statement
        
        Allowed patterns:
        - SELECT function(args)  # e.g., SELECT NOW(), SELECT VERSION()
        - SELECT constant        # e.g., SELECT 1, SELECT 'test'
        - SELECT ... FROM ...    # Standard SELECT queries
        
        Not allowed:
        - Any DDL (CREATE, DROP, ALTER, TRUNCATE)
        - Any DML except SELECT (INSERT, UPDATE, DELETE)
        - Multiple statements (no semicolons)
        
        Args:
            sql: SQL query to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        sql_stripped = sql.strip().upper()
        
        # Check for multiple statements
        if ';' in sql.rstrip(';'):
            return False, "Multiple SQL statements not allowed"
        
        # Must start with SELECT
        if not sql_stripped.startswith('SELECT'):
            return False, "Only SELECT queries are allowed"
        
        # Blocked keywords (DDL/DML)
        blocked_keywords = [
            'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
            'TRUNCATE', 'REPLACE', 'MERGE', 'GRANT', 'REVOKE'
        ]
        
        for keyword in blocked_keywords:
            # Use word boundaries to avoid false positives
            pattern = r'\b' + keyword + r'\b'
            if re.search(pattern, sql_stripped):
                return False, f"Keyword '{keyword}' is not allowed (read-only mode)"
        
        return True, ""
    
    def execute_select_query(
        self,
        sql: str,
        max_rows: int = 100
    ) -> Dict[str, Any]:
        """
        Execute a SELECT query (read-only)
        
        Args:
            sql: SELECT query to execute
            max_rows: Maximum number of rows to return
            
        Returns:
            Dictionary containing:
                - success: bool
                - data: List of rows
                - columns: List of column names
                - row_count: Number of rows returned
                - error: Error message (if any)
        """
        result = {
            "success": False,
            "data": [],
            "columns": [],
            "row_count": 0,
            "error": None
        }
        
        # Validate query
        is_valid, error_msg = self._validate_select_query(sql)
        if not is_valid:
            result["error"] = f"Query validation failed: {error_msg}"
            logger.warning(f"Invalid query rejected: {error_msg}")
            return result
        
        cursor = None
        try:
            if not self.connection or not self.connection.is_connected():
                if not self.connect():
                    result["error"] = "Failed to connect to database"
                    return result
            
            cursor = self.connection.cursor()
            cursor.execute(sql)
            
            # Fetch results
            rows = cursor.fetchmany(size=max_rows)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            
            result["data"] = rows
            result["columns"] = columns
            result["row_count"] = len(rows)
            result["success"] = True
            
            logger.debug(f"Query executed successfully. Rows returned: {result['row_count']}")
            
        except Error as e:
            logger.error(f"Error executing query: {e}")
            result["error"] = str(e)
                
        finally:
            if cursor:
                cursor.close()
        
        return result
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()


# ============================================================================
# Connection Test Function
# ============================================================================

def test_connection(
    host: str = "localhost",
    port: int = 9030,
    user: str = "root",
    password: str = ""
) -> bool:
    """
    Test StarRocks database connection
    
    This function is used to verify connectivity before registering tools.
    
    Args:
        host: StarRocks FE host
        port: StarRocks FE query port
        user: Database user
        password: Database password
        
    Returns:
        True if connection successful, False otherwise
    """
    try:
        client = StarRocksClient(host, port, user, password)
        
        if not client.connect():
            return False
        
        # Try a simple query
        result = client.execute_select_query("SELECT 1", max_rows=1)
        client.disconnect()
        
        return result["success"]
            
    except Exception as e:
        logger.warning(f"StarRocks connection test error: {e}")
        return False


# ============================================================================
# LangGraph Tool: Execute SQL Query (READ-ONLY)
# ============================================================================

@tool
def execute_sql(
    sql: str,
    host: str = "localhost",
    port: int = 9030,
    user: str = "root",
    password: str = "",
    max_rows: int = 50
) -> str:
    """
    Execute a READ-ONLY SELECT query against StarRocks database.
    
    🔒 SECURITY RESTRICTIONS - READ ONLY MODE:
    ==========================================
    ✅ ALLOWED:
    - SELECT queries with functions: SELECT NOW(), SELECT VERSION()
    - SELECT with constants: SELECT 1, SELECT 'hello'
    - SELECT from tables: SELECT * FROM table LIMIT 10
    - SELECT with JOINs, WHERE, GROUP BY, ORDER BY
    
    ❌ NOT ALLOWED:
    - INSERT, UPDATE, DELETE (data modification)
    - CREATE, DROP, ALTER, TRUNCATE (schema changes)
    - Multiple statements (no semicolons allowed)
    - Any other non-SELECT statements
    
    💡 RECOMMENDED USES:
    - Query system information: SELECT VERSION(), SELECT NOW()
    - Get metadata: SELECT * FROM information_schema.tables
    - Check variables: SELECT @@version_comment
    - Test functions: SELECT UPPER('test')
    
    Args:
        sql: SELECT query to execute (e.g., "SELECT NOW()", "SELECT * FROM table LIMIT 10")
        host: StarRocks FE host (default: localhost)
        port: StarRocks FE query port (default: 9030)
        user: Database user (default: root)
        password: Database password (default: empty)
        max_rows: Maximum number of rows to return (default: 50)
        
    Returns:
        Query results formatted as a table string, or error message
        
    Examples:
        Get system info:
        >>> execute_sql("SELECT VERSION()")
        >>> execute_sql("SELECT NOW(), CURRENT_DATE()")
        
        Test functions:
        >>> execute_sql("SELECT CONCAT('Hello', ' ', 'World')")
        >>> execute_sql("SELECT 1 + 1")
        
        Query metadata:
        >>> execute_sql("SELECT * FROM information_schema.schemata LIMIT 5")
    """
    try:
        # Create client and execute query
        with StarRocksClient(host, port, user, password) as client:
            result = client.execute_select_query(sql, max_rows=max_rows)
            
            if not result["success"]:
                return f"❌ Query failed: {result['error']}"
            
            # Format output
            if result["data"]:
                output = _format_table_output(result["columns"], result["data"])
                if len(result["data"]) >= max_rows:
                    output += f"\n\n⚠️  Results truncated to {max_rows} rows."
                return output
            else:
                return "✓ Query executed successfully. No results returned."
                
    except Exception as e:
        logger.error(f"Error in execute_sql tool: {e}")
        return f"❌ Error: {str(e)}"


def _format_table_output(columns: List[str], rows: List[tuple]) -> str:
    """
    Format query results as a readable table
    
    Args:
        columns: Column names
        rows: Data rows
        
    Returns:
        Formatted table string
    """
    if not rows:
        return "No results"
    
    # Calculate column widths
    col_widths = [len(col) for col in columns]
    for row in rows:
        for i, val in enumerate(row):
            val_str = str(val) if val is not None else "NULL"
            col_widths[i] = max(col_widths[i], len(val_str))
    
    # Build table
    header = " | ".join(col.ljust(w) for col, w in zip(columns, col_widths))
    separator = "-+-".join("-" * w for w in col_widths)
    
    lines = [header, separator]
    for row in rows:
        row_str = " | ".join(
            str(val).ljust(w) if val is not None else "NULL".ljust(w)
            for val, w in zip(row, col_widths)
        )
        lines.append(row_str)
    
    row_count = f"\n({len(rows)} row{'s' if len(rows) > 1 else ''})"
    return "\n".join(lines) + row_count
