"""
Test Weather MCP Server

A simple MCP server for testing the MCP Connection Manager with mock weather operations.
This server provides tools for getting weather information and forecasts.
"""

import asyncio
from builtins import ValueError
import json
import random
import sys
from typing import Any, Dict

from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types


# Create server instance
server = Server("test-weather-server")

# Mock weather data
WEATHER_DATA = {
    "new_york": {
        "temperature": 22,
        "humidity": 65,
        "condition": "partly cloudy",
        "wind_speed": 12
    },
    "london": {
        "temperature": 15,
        "humidity": 80,
        "condition": "rainy",
        "wind_speed": 8
    },
    "tokyo": {
        "temperature": 28,
        "humidity": 70,
        "condition": "sunny",
        "wind_speed": 5
    },
    "sydney": {
        "temperature": 19,
        "humidity": 60,
        "condition": "cloudy",
        "wind_speed": 15
    }
}

WEATHER_CONDITIONS = ["sunny", "cloudy", "partly cloudy", "rainy", "stormy", "snowy"]


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available weather tools"""
    return [
        types.Tool(
            name="get_current_weather",
            description="Get current weather for a city",
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"}
                },
                "required": ["city"]
            }
        ),
        types.Tool(
            name="get_weather_forecast",
            description="Get weather forecast for a city",
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"},
                    "days": {"type": "integer", "description": "Number of days to forecast (1-7)", "minimum": 1, "maximum": 7}
                },
                "required": ["city", "days"]
            }
        ),
        types.Tool(
            name="get_temperature",
            description="Get just the temperature for a city",
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"},
                    "unit": {"type": "string", "description": "Temperature unit (celsius or fahrenheit)", "enum": ["celsius", "fahrenheit"]}
                },
                "required": ["city"]
            }
        ),
        types.Tool(
            name="check_rain_probability",
            description="Check probability of rain for a city",
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"}
                },
                "required": ["city"]
            }
        ),
        types.Tool(
            name="get_air_quality",
            description="Get air quality index for a city",
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"}
                },
                "required": ["city"]
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handle tool calls"""
    try:
        if name == "get_current_weather":
            city = arguments.get("city", "").lower().replace(" ", "_")
            if not city:
                raise ValueError("City name is required")
            
            # Get weather data or generate random data
            if city in WEATHER_DATA:
                weather = WEATHER_DATA[city]
            else:
                weather = {
                    "temperature": random.randint(-10, 35),
                    "humidity": random.randint(30, 95),
                    "condition": random.choice(WEATHER_CONDITIONS),
                    "wind_speed": random.randint(0, 25)
                }
            
            return [types.TextContent(
                type="text",
                text=f"Current weather in {city.replace('_', ' ').title()}:\n"
                     f"Temperature: {weather['temperature']}°C\n"
                     f"Condition: {weather['condition']}\n"
                     f"Humidity: {weather['humidity']}%\n"
                     f"Wind Speed: {weather['wind_speed']} km/h"
            )]
        
        elif name == "get_weather_forecast":
            city = arguments.get("city", "").lower().replace(" ", "_")
            days = arguments.get("days", 3)
            
            if not city:
                raise ValueError("City name is required")
            if not 1 <= days <= 7:
                raise ValueError("Days must be between 1 and 7")
            
            forecast_text = f"Weather forecast for {city.replace('_', ' ').title()} ({days} days):\n"
            
            for day in range(1, days + 1):
                temp = random.randint(-5, 30)
                condition = random.choice(WEATHER_CONDITIONS)
                forecast_text += f"Day {day}: {temp}°C, {condition}\n"
            
            return [types.TextContent(
                type="text",
                text=forecast_text.strip()
            )]
        
        elif name == "get_temperature":
            city = arguments.get("city", "").lower().replace(" ", "_")
            unit = arguments.get("unit", "celsius").lower()
            
            if not city:
                raise ValueError("City name is required")
            
            if city in WEATHER_DATA:
                temp_c = WEATHER_DATA[city]["temperature"]
            else:
                temp_c = random.randint(-10, 35)
            
            if unit == "fahrenheit":
                temp = (temp_c * 9/5) + 32
                unit_symbol = "°F"
            else:
                temp = temp_c
                unit_symbol = "°C"
            
            return [types.TextContent(
                type="text",
                text=f"Temperature in {city.replace('_', ' ').title()}: {temp:.1f}{unit_symbol}"
            )]
        
        elif name == "check_rain_probability":
            city = arguments.get("city", "").lower().replace(" ", "_")
            
            if not city:
                raise ValueError("City name is required")
            
            # Generate probability based on city or random
            if city in WEATHER_DATA:
                condition = WEATHER_DATA[city]["condition"]
                if "rain" in condition:
                    probability = random.randint(60, 90)
                elif "cloud" in condition:
                    probability = random.randint(20, 50)
                else:
                    probability = random.randint(0, 20)
            else:
                probability = random.randint(0, 100)
            
            return [types.TextContent(
                type="text",
                text=f"Rain probability in {city.replace('_', ' ').title()}: {probability}%"
            )]
        
        elif name == "get_air_quality":
            city = arguments.get("city", "").lower().replace(" ", "_")
            
            if not city:
                raise ValueError("City name is required")
            
            # Generate random air quality index (0-500 scale)
            aqi = random.randint(0, 300)
            
            if aqi <= 50:
                quality = "Good"
            elif aqi <= 100:
                quality = "Moderate"
            elif aqi <= 150:
                quality = "Unhealthy for Sensitive Groups"
            elif aqi <= 200:
                quality = "Unhealthy"
            elif aqi <= 300:
                quality = "Very Unhealthy"
            else:
                quality = "Hazardous"
            
            return [types.TextContent(
                type="text",
                text=f"Air Quality in {city.replace('_', ' ').title()}:\n"
                     f"AQI: {aqi}\n"
                     f"Quality: {quality}"
            )]
        
        else:
            raise ValueError(f"Unknown tool: {name}")
    
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"Error executing {name}: {str(e)}"
        )]


async def main():
    """Main entry point for the weather server"""
    # Run the server using stdio transport
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="test-weather-server",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            )
        )


if __name__ == "__main__":
    asyncio.run(main()) 