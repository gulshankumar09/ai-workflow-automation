"""
Test Math MCP Server

A simple MCP server for testing the MCP Connection Manager with basic math operations.
This server provides tools for addition, subtraction, multiplication, and division.
"""

import asyncio
from builtins import ValueError
import json
import sys
from typing import Any, Dict

from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types


# Create server instance
server = Server("test-math-server")


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available math tools"""
    return [
        types.Tool(
            name="add",
            description="Add two numbers together",
            inputSchema={
                "type": "object", 
                "properties": {
                    "a": {"type": "number", "description": "First number"},
                    "b": {"type": "number", "description": "Second number"}
                },
                "required": ["a", "b"]
            }
        ),
        types.Tool(
            name="subtract", 
            description="Subtract second number from first number",
            inputSchema={
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "First number"},
                    "b": {"type": "number", "description": "Second number"}
                },
                "required": ["a", "b"]
            }
        ),
        types.Tool(
            name="multiply",
            description="Multiply two numbers",
            inputSchema={
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "First number"},
                    "b": {"type": "number", "description": "Second number"}
                },
                "required": ["a", "b"]
            }
        ),
        types.Tool(
            name="divide",
            description="Divide first number by second number",
            inputSchema={
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "Dividend"},
                    "b": {"type": "number", "description": "Divisor (cannot be zero)"}
                },
                "required": ["a", "b"]
            }
        ),
        types.Tool(
            name="power",
            description="Raise first number to the power of second number",
            inputSchema={
                "type": "object",
                "properties": {
                    "base": {"type": "number", "description": "Base number"},
                    "exponent": {"type": "number", "description": "Exponent"}
                },
                "required": ["base", "exponent"]
            }
        ),
        types.Tool(
            name="sqrt",
            description="Calculate square root of a number",
            inputSchema={
                "type": "object",
                "properties": {
                    "number": {"type": "number", "description": "Number to calculate square root of"}
                },
                "required": ["number"]
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handle tool calls"""
    try:
        if name == "add":
            a = arguments.get("a")
            b = arguments.get("b")
            if a is None or b is None:
                raise ValueError("Both 'a' and 'b' parameters are required")
            result = a + b
            return [types.TextContent(
                type="text",
                text=f"The sum of {a} and {b} is {result}"
            )]
        
        elif name == "subtract":
            a = arguments.get("a") 
            b = arguments.get("b")
            if a is None or b is None:
                raise ValueError("Both 'a' and 'b' parameters are required")
            result = a - b
            return [types.TextContent(
                type="text",
                text=f"The difference of {a} and {b} is {result}"
            )]
        
        elif name == "multiply":
            a = arguments.get("a")
            b = arguments.get("b") 
            if a is None or b is None:
                raise ValueError("Both 'a' and 'b' parameters are required")
            result = a * b
            return [types.TextContent(
                type="text",
                text=f"The product of {a} and {b} is {result}"
            )]
        
        elif name == "divide":
            a = arguments.get("a")
            b = arguments.get("b")
            if a is None or b is None:
                raise ValueError("Both 'a' and 'b' parameters are required")
            if b == 0:
                raise ValueError("Cannot divide by zero")
            result = a / b
            return [types.TextContent(
                type="text",
                text=f"The quotient of {a} divided by {b} is {result}"
            )]
        
        elif name == "power":
            base = arguments.get("base")
            exponent = arguments.get("exponent")
            if base is None or exponent is None:
                raise ValueError("Both 'base' and 'exponent' parameters are required")
            result = base ** exponent
            return [types.TextContent(
                type="text",
                text=f"{base} raised to the power of {exponent} is {result}"
            )]
        
        elif name == "sqrt":
            number = arguments.get("number")
            if number is None:
                raise ValueError("'number' parameter is required")
            if number < 0:
                raise ValueError("Cannot calculate square root of negative number")
            result = number ** 0.5
            return [types.TextContent(
                type="text", 
                text=f"The square root of {number} is {result}"
            )]
        
        else:
            raise ValueError(f"Unknown tool: {name}")
    
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"Error executing {name}: {str(e)}"
        )]


async def main():
    """Main entry point for the math server"""
    # Run the server using stdio transport
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream, 
            InitializationOptions(
                server_name="test-math-server",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            )
        )


if __name__ == "__main__":
    asyncio.run(main()) 