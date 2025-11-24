import os
from typing import Any
from datetime import datetime
from mcp.server.fastmcp import FastMCP


# Initialize FastMCP server
mcp = FastMCP("flightsearch")
API_KEY = os.environ.get("FLIGHT_API_KEY")
if API_KEY is None:
    raise RuntimeError("FLIGHT_API_KEY environment variable is not set.")

def validate_api_key(key: str) -> bool:
    return key == API_KEY

@mcp.tool()
def search_flights(origin: str, destination: str, date: str) -> dict:
    """Validate date and return the inputs."""
    try:
        parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        return {"error": "Invalid date format. Use YYYY-MM-DD."}

    return {
        "origin": origin,
        "destination": destination,
        "date": str(parsed_date)
    }