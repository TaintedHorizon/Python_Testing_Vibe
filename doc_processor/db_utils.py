"""
Database connection and context management utilities.
"""
import sqlite3
from contextlib import contextmanager
from typing import Generator
import logging
from .exceptions import DatabaseError

@contextmanager
def database_transaction() -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager for database transactions that ensures proper commit/rollback.
    
    Yields:
        sqlite3.Connection: Database connection with transaction management
        
    Raises:
        DatabaseError: If there is any error during database operations
    """
    conn = None
    try:
        conn = sqlite3.connect(app_config.DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        # Start transaction
        yield conn
        # Commit if no exceptions occurred
        conn.commit()
    except sqlite3.Error as e:
        if conn:
            try:
                conn.rollback()
            except Exception as rollback_error:
                logging.error(f"Failed to rollback transaction: {rollback_error}")
        raise DatabaseError(f"Database error: {str(e)}", details=str(e))
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception as rollback_error:
                logging.error(f"Failed to rollback transaction: {rollback_error}")
        raise
    finally:
        if conn:
            try:
                conn.close()
            except Exception as close_error:
                logging.error(f"Failed to close database connection: {close_error}")

def execute_query(query: str, params: tuple = ()) -> list:
    """
    Executes a SELECT query and returns results.
    
    Args:
        query: SQL query string
        params: Query parameters
        
    Returns:
        list: Query results
        
    Raises:
        DatabaseError: If there is any error during query execution
    """
    try:
        with database_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()
    except Exception as e:
        raise DatabaseError(f"Query execution failed: {str(e)}", details=query)

def execute_command(command: str, params: tuple = ()) -> int:
    """
    Executes an INSERT, UPDATE, or DELETE command.
    
    Args:
        command: SQL command string
        params: Command parameters
        
    Returns:
        int: Number of affected rows or last insert ID
        
    Raises:
        DatabaseError: If there is any error during command execution
    """
    try:
        with database_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(command, params)
            return cursor.lastrowid if command.strip().upper().startswith('INSERT') else cursor.rowcount
    except Exception as e:
        raise DatabaseError(f"Command execution failed: {str(e)}", details=command)