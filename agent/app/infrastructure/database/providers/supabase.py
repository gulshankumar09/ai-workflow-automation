"""
Supabase database provider implementation for the ai-workflow-automation system.

This module provides the Supabase-specific implementation of the database provider
interface, serving as the MVP database solution for the ai-workflow-automation system.
"""

from typing import Any, Dict, List, Optional
import time
import json
import asyncio
from datetime import datetime
from app.shared.logger import get_logger

from .base import AbstractDatabaseProvider
from app.shared.exceptions import (
    DatabaseException, 
    ValidationException, 
    NotFoundException,
    create_error_context,
    ConfigurationException
)

logger = get_logger(__name__)


class SupabaseConnectionPool:
    """
    Connection pool manager for Supabase REST API requests.
    
    While Supabase uses REST API (no persistent connections), this pool manages
    request rate limiting, retry logic, and connection health monitoring.
    """
    
    def __init__(
        self,
        max_concurrent_requests: int = 10,
        request_timeout: float = 30,
        retry_attempts: int = 3,
        retry_delay: float = 1.0
    ):
        self.max_concurrent_requests = max_concurrent_requests
        self.request_timeout = request_timeout
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        
        # Request tracking
        self._semaphore = asyncio.Semaphore(max_concurrent_requests)
        self._active_requests = 0
        self._total_requests = 0
        self._failed_requests = 0
        self._avg_response_time = 0.0
        
        # Health monitoring
        self._last_health_check = None
        self._health_status = "unknown"
        self._consecutive_failures = 0
        
    async def execute_with_pool(self, operation_func, *args, **kwargs):
        """
        Execute an operation through the connection pool with rate limiting and retries.
        
        Args:
            operation_func: Function to execute (synchronous Supabase operation)
            *args, **kwargs: Function arguments
            
        Returns:
            Operation result
            
        Raises:
            DatabaseException: If operation fails after all retries
        """
        async with self._semaphore:
            self._active_requests += 1
            self._total_requests += 1
            
            start_time = time.time()
            last_error = None
            
            try:
                for attempt in range(self.retry_attempts):
                    try:
                        # Run synchronous Supabase operation in thread pool
                        loop = asyncio.get_event_loop()
                        result = await asyncio.wait_for(
                            loop.run_in_executor(None, operation_func, *args, **kwargs),
                            timeout=self.request_timeout
                        )
                        
                        # Update success metrics
                        execution_time = time.time() - start_time
                        self._update_response_time(execution_time)
                        self._health_status = "healthy"
                        
                        return result
                        
                    except asyncio.TimeoutError as e:
                        last_error = f"Request timeout after {self.request_timeout}s"
                        logger.warning(
                            "Supabase request timeout",
                            attempt=attempt + 1,
                            timeout=self.request_timeout
                        )
                        
                    except Exception as e:
                        last_error = str(e)
                        logger.warning(
                            "Supabase request failed",
                            attempt=attempt + 1,
                            error=str(e)
                        )
                    
                    # Wait before retry (except for last attempt)
                    if attempt < self.retry_attempts - 1:
                        await asyncio.sleep(self.retry_delay * (attempt + 1))
                
                # All retries failed
                self._failed_requests += 1
                self._consecutive_failures += 1
                self._health_status = "unhealthy" if self._consecutive_failures > 3 else "degraded"
                
                raise DatabaseException(
                    f"Operation failed after {self.retry_attempts} attempts: {last_error}"
                )
                
            finally:
                self._active_requests -= 1
    
    def _update_response_time(self, execution_time: float):
        """Update average response time with exponential moving average."""
        if self._avg_response_time == 0.0:
            self._avg_response_time = execution_time
        else:
            # Exponential moving average with alpha = 0.1
            self._avg_response_time = 0.1 * execution_time + 0.9 * self._avg_response_time
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        return {
            "max_concurrent_requests": self.max_concurrent_requests,
            "active_requests": self._active_requests,
            "total_requests": self._total_requests,
            "failed_requests": self._failed_requests,
            "success_rate": (
                (self._total_requests - self._failed_requests) / self._total_requests 
                if self._total_requests > 0 else 0.0
            ),
            "avg_response_time": self._avg_response_time,
            "health_status": self._health_status,
            "consecutive_failures": self._consecutive_failures
        }


class SupabaseDatabaseProvider(AbstractDatabaseProvider):
    """
    Supabase database provider implementation.
    
    This provider uses the Supabase Python client to interact with PostgreSQL
    through Supabase's REST API, providing a managed database solution with
    enhanced connection pooling and health monitoring.
    """
    
    def __init__(
        self,
        supabase_client=None,
        name: str = "supabase",
        correlation_id: str = None,
        max_concurrent_requests: int = 10,
        request_timeout: int = 30,
        retry_attempts: int = 3,
        health_check_interval: int = 300,  # 5 minutes
        auto_create: bool = False,
        settings = None
    ):
        """
        Initialize the Supabase database provider.
        
        Args:
            supabase_client: Initialized Supabase client instance (optional if auto_create=True)
            name: Human-readable name for this provider instance
            correlation_id: Request correlation ID for tracking
            max_concurrent_requests: Maximum concurrent API requests
            request_timeout: Request timeout in seconds
            retry_attempts: Number of retry attempts for failed requests
            health_check_interval: Health check interval in seconds
            auto_create: Whether to auto-create client from environment/settings
            settings: Application settings instance (required if auto_create=True)
            
        Raises:
            ValidationException: If required parameters are missing
            ConfigurationException: If auto-creation fails
        """
        super().__init__(name)
        
        # Auto-create client from environment/settings if requested
        if auto_create:
            if not settings:
                raise ValidationException(
                    "Settings are required for auto-creation",
                    correlation_id=correlation_id
                )
            
            self.supabase = self._create_client_from_settings(settings, correlation_id)
        else:
            if not supabase_client:
                raise ValidationException(
                    "Supabase client is required when auto_create=False",
                    correlation_id=correlation_id
                )
            
            self.supabase = supabase_client
        self._correlation_id = correlation_id
        self.health_check_interval = health_check_interval
        
        # Initialize connection pool
        self._pool = SupabaseConnectionPool(
            max_concurrent_requests=max_concurrent_requests,
            request_timeout=request_timeout,
            retry_attempts=retry_attempts,
            retry_delay=1.0
        )
        
        # Performance tracking
        self._stats = {
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "avg_execution_time": 0.0,
            "last_query_time": None,
            "connection_established": None
        }
        
        # Health monitoring
        self._health_task = None
        self._last_health_check = None
        
        logger.info(
            "Supabase database provider initialized",
            name=self.name,
            max_concurrent_requests=max_concurrent_requests,
            request_timeout=request_timeout,
            retry_attempts=retry_attempts,
            correlation_id=correlation_id
        )

    def _create_client_from_settings(self, settings, correlation_id: str = None):
        """
        Create Supabase client from application settings.
        
        Args:
            settings: Application settings instance
            correlation_id: Request correlation ID for tracking
            
        Returns:
            Configured Supabase client instance
            
        Raises:
            ConfigurationException: If required settings are missing
            DatabaseException: If client creation fails
        """
        try:
            from supabase import create_client
            
            # Get Supabase configuration from settings
            supabase_url = settings.supabase.url
            supabase_key = settings.supabase.api_key
            
            if not supabase_url:
                raise ConfigurationException(
                    "Supabase URL is required (SUPABASE_URL environment variable)",
                    correlation_id=correlation_id,
                    details=create_error_context(
                        operation="_create_client_from_settings",
                        component="supabase_provider",
                        missing_setting="supabase_url",
                        correlation_id=correlation_id
                    )
                )
            
            if not supabase_key:
                raise ConfigurationException(
                    "Supabase API key is required (SUPABASE_API_KEY environment variable)",
                    correlation_id=correlation_id,
                    details=create_error_context(
                        operation="_create_client_from_settings",
                        component="supabase_provider",
                        missing_setting="supabase_key",
                        correlation_id=correlation_id
                    )
                )
            
            # Create Supabase client
            client = create_client(supabase_url, supabase_key)
            
            logger.info(
                "Supabase client created from environment settings",
                supabase_url=supabase_url[:30] + "..." if len(supabase_url) > 30 else supabase_url,
                correlation_id=correlation_id
            )
            
            return client
            
        except ImportError as e:
            raise ConfigurationException(
                "Supabase client library not installed. Run: uv add supabase",
                correlation_id=correlation_id,
                details=create_error_context(
                    operation="_create_client_from_settings",
                    component="supabase_provider",
                    error_type="ImportError",
                    error_message=str(e),
                    correlation_id=correlation_id
                )
            )
        
        except Exception as e:
            # Re-raise custom exceptions as-is
            if isinstance(e, ConfigurationException):
                raise
            
            # Wrap other exceptions
            raise DatabaseException(
                f"Failed to create Supabase client from settings: {str(e)}",
                correlation_id=correlation_id,
                details=create_error_context(
                    operation="_create_client_from_settings",
                    component="supabase_provider",
                    error_type=type(e).__name__,
                    error_message=str(e),
                    correlation_id=correlation_id
                )
            )

    async def connect(self) -> None:
        """
        Establish connection to Supabase.
        
        Note: Supabase uses REST API, so no persistent connection is needed.
        This method validates the client configuration and starts health monitoring.
        """
        try:
            start_time = time.time()
            
            # Test connection with a simple health check
            await self.health_check()
            
            self._connected = True
            self._connection_time = time.time()
            self._stats["connection_established"] = datetime.utcnow().isoformat()
            
            # Start periodic health monitoring
            self._start_health_monitoring()
            
            connection_time = time.time() - start_time
            
            logger.info(
                "Supabase database provider connected",
                provider=self.name,
                connection_time=connection_time,
                pool_config=self._pool.get_pool_stats(),
                correlation_id=self._correlation_id
            )
            
        except Exception as e:
            error_context = create_error_context(
                operation="connect",
                component="supabase",
                correlation_id=self._correlation_id
            )
            
            logger.error(
                "Failed to connect to Supabase",
                error=str(e),
                **error_context
            )
            
            raise DatabaseException(
                f"Failed to connect to Supabase: {str(e)}",
                correlation_id=self._correlation_id,
                details=error_context
            )

    async def disconnect(self) -> None:
        """
        Disconnect from Supabase.
        
        Note: Supabase uses REST API, so no persistent connection to close.
        This method stops health monitoring and marks the provider as disconnected.
        """
        # Stop health monitoring
        if self._health_task and not self._health_task.done():
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
        
        self._connected = False
        self._connection_time = None
        
        logger.info(
            "Supabase database provider disconnected",
            provider=self.name,
            final_stats=self.get_stats(),
            correlation_id=self._correlation_id
        )

    def _start_health_monitoring(self):
        """Start periodic health monitoring task."""
        self._health_task = asyncio.create_task(self._periodic_health_check())

    async def _periodic_health_check(self):
        """Perform periodic health checks."""
        while self._connected:
            try:
                await asyncio.sleep(self.health_check_interval)
                await self.health_check()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(
                    "Periodic health check failed",
                    error=str(e),
                    provider=self.name
                )

    async def execute_query(
        self, 
        query: str, 
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a raw SQL query using Supabase's RPC functionality with connection pooling.
        
        Args:
            query: SQL query string (as RPC function name)
            params: Query parameters
            
        Returns:
            Query result dictionary
            
        Raises:
            DatabaseException: If query execution fails
            ValidationException: If query is invalid
        """
        if not query or not isinstance(query, str):
            raise ValidationException(
                "Query must be a non-empty string",
                correlation_id=self._correlation_id
            )
        
        start_time = time.time()
        
        def _execute():
            return self.supabase.rpc(query, params or {}).execute()
        
        try:
            result = await self._pool.execute_with_pool(_execute)
            
            execution_time = time.time() - start_time
            self._update_stats(execution_time, success=True)
            
            logger.debug(
                "Query executed successfully",
                query=query,
                execution_time=execution_time,
                correlation_id=self._correlation_id
            )
            
            return {
                "data": result.data,
                "count": len(result.data) if result.data else 0,
                "execution_time": execution_time
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            self._update_stats(execution_time, success=False, error=str(e))
            
            error_context = create_error_context(
                operation="execute_query",
                component="supabase",
                query=query,
                correlation_id=self._correlation_id,
                execution_time=execution_time
            )
            
            logger.error(
                "Query execution failed",
                error=str(e),
                **error_context
            )
            
            raise DatabaseException(
                f"Query execution failed: {str(e)}",
                correlation_id=self._correlation_id,
                details=error_context
            )

    async def insert(
        self, 
        table: str, 
        data: Dict[str, Any],
        returning: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Insert data into a Supabase table with connection pooling.
        """
        await self.validate_table_name(table)
        
        if not data or not isinstance(data, dict):
            raise ValidationException(
                "Data must be a non-empty dictionary",
                correlation_id=self._correlation_id
            )
        
        start_time = time.time()
        
        def _insert():
            try:
                # Build the insert query
                query = self.supabase.table(table).insert(data)
                
                # Add returning clause if specified
                if returning:
                    # Use the correct method for adding select to insert
                    query = query.select(",".join(returning))
                
                # Execute the query
                result = query.execute()
                return result
                
            except AttributeError as e:
                # Handle the case where select method is not available on insert
                if "select" in str(e):
                    # Try without returning clause
                    result = self.supabase.table(table).insert(data).execute()
                    return result
                else:
                    raise e
        
        try:
            result = await self._pool.execute_with_pool(_insert)
            
            execution_time = time.time() - start_time
            self._update_stats(execution_time, success=True)
            
            logger.debug(
                "Insert operation successful",
                table=table,
                rows_inserted=len(result.data) if result.data else 1,
                execution_time=execution_time,
                correlation_id=self._correlation_id
            )
            
            return {
                "data": result.data,
                "count": len(result.data) if result.data else 1,
                "execution_time": execution_time
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            self._update_stats(execution_time, success=False, error=str(e))
            
            error_context = create_error_context(
                operation="insert",
                component="supabase",
                table=table,
                correlation_id=self._correlation_id,
                execution_time=execution_time
            )
            
            logger.error(
                "Insert operation failed",
                error=str(e),
                **error_context
            )
            
            raise DatabaseException(
                f"Insert operation failed: {str(e)}",
                correlation_id=self._correlation_id,
                details=error_context
            )

    async def update(
        self, 
        table: str, 
        data: Dict[str, Any], 
        filters: Dict[str, Any],
        returning: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Update data in a Supabase table.
        
        Args:
            table: Table name
            data: Data to update
            filters: WHERE conditions
            returning: Columns to return after update
            
        Returns:
            Result dictionary with updated data
        """
        await self.validate_table_name(table)
        
        if not data or not isinstance(data, dict):
            raise ValidationException(
                "Data must be a non-empty dictionary",
                correlation_id=self._correlation_id
            )
        
        if not filters or not isinstance(filters, dict):
            raise ValidationException(
                "Filters must be a non-empty dictionary",
                correlation_id=self._correlation_id
            )
        
        start_time = time.time()
        
        def _update():
            query = self.supabase.table(table)
            
            # Apply filters
            for key, value in filters.items():
                query = query.eq(key, value)
            
            query = query.update(data)
            
            if returning:
                query = query.select(",".join(returning))
            
            return query.execute()
        
        try:
            result = await self._pool.execute_with_pool(_update)
            
            execution_time = time.time() - start_time
            self._update_stats(execution_time, success=True)
            
            logger.debug(
                "Update operation successful",
                table=table,
                rows_updated=len(result.data) if result.data else 0,
                execution_time=execution_time,
                correlation_id=self._correlation_id
            )
            
            return {
                "data": result.data,
                "count": len(result.data) if result.data else 0,
                "execution_time": execution_time
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            self._update_stats(execution_time, success=False, error=str(e))
            
            error_context = create_error_context(
                operation="update",
                component="supabase",
                table=table,
                correlation_id=self._correlation_id,
                execution_time=execution_time
            )
            
            logger.error(
                "Update operation failed",
                error=str(e),
                **error_context
            )
            
            raise DatabaseException(
                f"Update operation failed: {str(e)}",
                correlation_id=self._correlation_id,
                details=error_context
            )
    
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
        Select data from a Supabase table.
        
        Args:
            table: Table name
            columns: Columns to select
            filters: WHERE conditions
            order_by: Order by clauses
            limit: Maximum number of rows
            offset: Number of rows to skip
            
        Returns:
            Result dictionary with selected data
        """
        await self.validate_table_name(table)
        
        if columns:
            await self.validate_column_names(columns)
        
        start_time = time.time()
        
        def _select():
            # Build query
            if columns:
                query = self.supabase.table(table).select(",".join(columns))
            else:
                query = self.supabase.table(table).select("*")
            
            # Apply filters
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            
            # Apply ordering
            if order_by:
                for column, direction in order_by.items():
                    ascending = direction.lower() != "desc"
                    query = query.order(column, desc=not ascending)
            
            # Apply pagination
            if limit:
                query = query.limit(limit)
            
            if offset:
                query = query.offset(offset)
            
            return query.execute()
        
        try:
            result = await self._pool.execute_with_pool(_select)
            
            execution_time = time.time() - start_time
            self._update_stats(execution_time, success=True)
            
            logger.debug(
                "Select operation successful",
                table=table,
                rows_returned=len(result.data) if result.data else 0,
                execution_time=execution_time,
                correlation_id=self._correlation_id
            )
            
            return {
                "data": result.data,
                "count": len(result.data) if result.data else 0,
                "execution_time": execution_time
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            self._update_stats(execution_time, success=False, error=str(e))
            
            error_context = create_error_context(
                operation="select",
                component="supabase",
                table=table,
                correlation_id=self._correlation_id,
                execution_time=execution_time
            )
            
            logger.error(
                "Select operation failed",
                error=str(e),
                **error_context
            )
            
            raise DatabaseException(
                f"Select operation failed: {str(e)}",
                correlation_id=self._correlation_id,
                details=error_context
            )
    
    async def delete(
        self, 
        table: str, 
        filters: Dict[str, Any],
        returning: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Delete data from a Supabase table.
        
        Args:
            table: Table name
            filters: WHERE conditions
            returning: Columns to return from deleted rows
            
        Returns:
            Result dictionary with deleted data
        """
        await self.validate_table_name(table)
        
        if not filters or not isinstance(filters, dict):
            raise ValidationException(
                "Filters must be a non-empty dictionary for delete operations",
                correlation_id=self._correlation_id
            )
        
        start_time = time.time()
        
        def _delete():
            query = self.supabase.table(table)
            
            # Apply filters
            for key, value in filters.items():
                query = query.eq(key, value)
            
            query = query.delete()
            
            if returning:
                query = query.select(",".join(returning))
            
            return query.execute()
        
        try:
            result = await self._pool.execute_with_pool(_delete)
            
            execution_time = time.time() - start_time
            self._update_stats(execution_time, success=True)
            
            logger.debug(
                "Delete operation successful",
                table=table,
                rows_deleted=len(result.data) if result.data else 0,
                execution_time=execution_time,
                correlation_id=self._correlation_id
            )
            
            return {
                "data": result.data,
                "count": len(result.data) if result.data else 0,
                "execution_time": execution_time
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            self._update_stats(execution_time, success=False, error=str(e))
            
            error_context = create_error_context(
                operation="delete",
                component="supabase",
                table=table,
                correlation_id=self._correlation_id,
                execution_time=execution_time
            )
            
            logger.error(
                "Delete operation failed",
                error=str(e),
                **error_context
            )
            
            raise DatabaseException(
                f"Delete operation failed: {str(e)}",
                correlation_id=self._correlation_id,
                details=error_context
            )
    
    async def upsert(
        self, 
        table: str, 
        data: Dict[str, Any],
        conflict_columns: List[str],
        returning: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Upsert data into a Supabase table.
        
        Args:
            table: Table name
            data: Data to upsert
            conflict_columns: Columns to check for conflicts
            returning: Columns to return after upsert
            
        Returns:
            Result dictionary with upserted data
        """
        await self.validate_table_name(table)
        await self.validate_column_names(conflict_columns)
        
        if not data or not isinstance(data, dict):
            raise ValidationException(
                "Data must be a non-empty dictionary",
                correlation_id=self._correlation_id
            )
        
        start_time = time.time()
        
        def _upsert():
            query = self.supabase.table(table).upsert(
                data, 
                on_conflict=",".join(conflict_columns)
            )
            
            if returning:
                query = query.select(",".join(returning))
            
            return query.execute()
        
        try:
            result = await self._pool.execute_with_pool(_upsert)
            
            execution_time = time.time() - start_time
            self._update_stats(execution_time, success=True)
            
            logger.debug(
                "Upsert operation successful",
                table=table,
                rows_affected=len(result.data) if result.data else 0,
                execution_time=execution_time,
                correlation_id=self._correlation_id
            )
            
            return {
                "data": result.data,
                "count": len(result.data) if result.data else 0,
                "execution_time": execution_time
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            self._update_stats(execution_time, success=False, error=str(e))
            
            error_context = create_error_context(
                operation="upsert",
                component="supabase",
                table=table,
                correlation_id=self._correlation_id,
                execution_time=execution_time
            )
            
            logger.error(
                "Upsert operation failed",
                error=str(e),
                **error_context
            )
            
            raise DatabaseException(
                f"Upsert operation failed: {str(e)}",
                correlation_id=self._correlation_id,
                details=error_context
            )
    
    async def begin_transaction(self) -> Any:
        """
        Begin a database transaction.
        
        Note: Supabase REST API doesn't support explicit transactions.
        This method returns a mock transaction object for compatibility.
        """
        transaction_id = f"supabase_tx_{int(time.time())}"
        
        logger.debug(
            "Transaction started (mock)",
            transaction_id=transaction_id,
            correlation_id=self._correlation_id
        )
        
        return transaction_id
    
    async def commit_transaction(self, transaction: Any) -> None:
        """
        Commit a database transaction.
        
        Note: Supabase REST API doesn't support explicit transactions.
        This method is a no-op for compatibility.
        """
        logger.debug(
            "Transaction committed (mock)",
            transaction_id=transaction,
            correlation_id=self._correlation_id
        )
    
    async def rollback_transaction(self, transaction: Any) -> None:
        """
        Rollback a database transaction.
        
        Note: Supabase REST API doesn't support explicit transactions.
        This method is a no-op for compatibility.
        """
        logger.debug(
            "Transaction rolled back (mock)",
            transaction_id=transaction,
            correlation_id=self._correlation_id
        )
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the Supabase connection.
        
        Returns:
            Health status dictionary
        """
        start_time = time.time()
        
        def _health_check():
            # Try a simple query to test connection
            return self.supabase.table("mcp_tools").select("id").limit(1).execute()
        
        try:
            result = await self._pool.execute_with_pool(_health_check)
            
            response_time = time.time() - start_time
            
            return {
                "status": "healthy",
                "provider": "supabase",
                "response_time": response_time,
                "connected": self._connected,
                "stats": self._stats.copy(),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            response_time = time.time() - start_time
            
            error_context = create_error_context(
                operation="health_check",
                component="supabase",
                correlation_id=self._correlation_id,
                response_time=response_time
            )
            
            logger.error(
                "Health check failed",
                error=str(e),
                **error_context
            )
            
            return {
                "status": "unhealthy",
                "provider": "supabase",
                "error": str(e),
                "response_time": response_time,
                "connected": False,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def _update_stats(self, execution_time: float, success: bool, error: str = None) -> None:
        """Update internal statistics."""
        self._stats["total_queries"] += 1
        self._stats["avg_execution_time"] += execution_time
        
        if success:
            self._stats["successful_queries"] += 1
        else:
            self._stats["failed_queries"] += 1
            self._stats["last_query_time"] = execution_time
            self._stats["last_error"] = error
    
    def get_stats(self) -> Dict[str, Any]:
        """Get provider statistics."""
        stats = self._stats.copy()
        
        if stats["total_queries"] > 0:
            stats["avg_execution_time"] /= stats["total_queries"]
        else:
            stats["avg_execution_time"] = 0.0
        
        return stats 