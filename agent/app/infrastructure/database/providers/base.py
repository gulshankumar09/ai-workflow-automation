"""
Abstract database provider interface for the ai-workflow-automation system.

This module defines the base interface that all database providers must implement,
ensuring consistent behavior across different database backends.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from app.shared.logger import get_logger

logger = get_logger(__name__)


class AbstractDatabaseProvider(ABC):
    """
    Abstract base class for database providers.
    
    This interface defines the contract that all database providers must implement,
    enabling the system to work with different database backends seamlessly.
    """
    
    def __init__(self, name: str, **kwargs):
        """
        Initialize the database provider.
        
        Args:
            name: Human-readable name for this provider instance
            **kwargs: Provider-specific configuration parameters
        """
        self.name = name
        self._connected = False
        self._config = kwargs
        self._connection_time = None
    
    @property
    def is_connected(self) -> bool:
        """Check if the provider is currently connected."""
        return self._connected
    
    @property
    def connection_time(self) -> Optional[float]:
        """Get the time when the connection was established."""
        return self._connection_time
    
    @abstractmethod
    async def connect(self) -> None:
        """
        Establish connection to the database.
        
        Raises:
            DatabaseException: If connection fails
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """
        Close the database connection.
        
        Raises:
            DatabaseException: If disconnection fails
        """
        pass
    
    @abstractmethod
    async def execute_query(
        self, 
        query: str, 
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a raw SQL query.
        
        Args:
            query: SQL query string
            params: Query parameters for safe parameter binding
            
        Returns:
            Query result dictionary with data and metadata
            
        Raises:
            DatabaseException: If query execution fails
            ValidationException: If query or parameters are invalid
        """
        pass
    
    @abstractmethod
    async def insert(
        self, 
        table: str, 
        data: Dict[str, Any],
        returning: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Insert data into a table.
        
        Args:
            table: Table name
            data: Data to insert as key-value pairs
            returning: Columns to return after insert
            
        Returns:
            Result dictionary with inserted data
            
        Raises:
            DatabaseException: If insert operation fails
            ValidationException: If table name or data is invalid
        """
        pass
    
    @abstractmethod
    async def update(
        self, 
        table: str, 
        data: Dict[str, Any], 
        filters: Dict[str, Any],
        returning: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Update data in a table.
        
        Args:
            table: Table name
            data: Data to update as key-value pairs
            filters: WHERE conditions as key-value pairs
            returning: Columns to return after update
            
        Returns:
            Result dictionary with updated data
            
        Raises:
            DatabaseException: If update operation fails
            ValidationException: If table name, data, or filters are invalid
        """
        pass
    
    @abstractmethod
    async def select(
        self, 
        table: str, 
        columns: Optional[List[str]] = None, 
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[Dict[str, str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Select data from a table.
        
        Args:
            table: Table name
            columns: Columns to select (None for all columns)
            filters: WHERE conditions as key-value pairs
            order_by: Order by clauses as {column: direction}
            limit: Maximum number of rows to return
            offset: Number of rows to skip
            
        Returns:
            Result dictionary with selected data
            
        Raises:
            DatabaseException: If select operation fails
            ValidationException: If parameters are invalid
        """
        pass
    
    @abstractmethod
    async def delete(
        self, 
        table: str, 
        filters: Dict[str, Any],
        returning: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Delete data from a table.
        
        Args:
            table: Table name
            filters: WHERE conditions as key-value pairs
            returning: Columns to return from deleted rows
            
        Returns:
            Result dictionary with deleted data
            
        Raises:
            DatabaseException: If delete operation fails
            ValidationException: If table name or filters are invalid
        """
        pass
    
    @abstractmethod
    async def upsert(
        self, 
        table: str, 
        data: Dict[str, Any],
        conflict_columns: List[str],
        returning: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Insert or update data (upsert operation).
        
        Args:
            table: Table name
            data: Data to upsert as key-value pairs
            conflict_columns: Columns to check for conflicts
            returning: Columns to return after upsert
            
        Returns:
            Result dictionary with upserted data
            
        Raises:
            DatabaseException: If upsert operation fails
            ValidationException: If parameters are invalid
        """
        pass
    
    @abstractmethod
    async def begin_transaction(self) -> Any:
        """
        Begin a database transaction.
        
        Returns:
            Transaction object or identifier
            
        Raises:
            DatabaseException: If transaction cannot be started
        """
        pass
    
    @abstractmethod
    async def commit_transaction(self, transaction: Any) -> None:
        """
        Commit a database transaction.
        
        Args:
            transaction: Transaction object or identifier
            
        Raises:
            DatabaseException: If transaction cannot be committed
        """
        pass
    
    @abstractmethod
    async def rollback_transaction(self, transaction: Any) -> None:
        """
        Rollback a database transaction.
        
        Args:
            transaction: Transaction object or identifier
            
        Raises:
            DatabaseException: If transaction cannot be rolled back
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the database connection.
        
        Returns:
            Health status dictionary with details
            
        Raises:
            DatabaseException: If health check fails
        """
        pass
    
    async def validate_table_name(self, table: str) -> None:
        """
        Validate table name for SQL injection protection.
        
        Args:
            table: Table name to validate
            
        Raises:
            ValidationException: If table name is invalid
        """
        from app.shared.exceptions import ValidationException
        
        if not table or not isinstance(table, str):
            raise ValidationException("Table name must be a non-empty string")
        
        if not table.replace('_', '').replace('-', '').isalnum():
            raise ValidationException(f"Invalid table name: {table}")
        
        if len(table) > 63:  # PostgreSQL limit
            raise ValidationException(f"Table name too long: {table}")
    
    async def validate_column_names(self, columns: List[str]) -> None:
        """
        Validate column names for SQL injection protection.
        
        Args:
            columns: Column names to validate
            
        Raises:
            ValidationException: If any column name is invalid
        """
        from app.shared.exceptions import ValidationException
        
        if not columns or not isinstance(columns, list):
            raise ValidationException("Columns must be a non-empty list")
        
        for column in columns:
            if not column or not isinstance(column, str):
                raise ValidationException("Column names must be non-empty strings")
            
            if not column.replace('_', '').replace('-', '').isalnum():
                raise ValidationException(f"Invalid column name: {column}")
    
    def __repr__(self) -> str:
        """String representation of the provider."""
        return f"{self.__class__.__name__}(name='{self.name}', connected={self._connected})" 