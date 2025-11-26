import os
from datetime import datetime
from typing import Any, List, Dict

import httpx
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("flightsearch")

# Base URL for your fake flight API server
# e.g. http://localhost:8000 if you're running the FastAPI example
FLIGHT_API_BASE = os.environ.get("FLIGHT_API_BASE", "http://localhost:8000")


async def fetch_flights_from_api(origin: str, destination: str, date: str) -> List[Dict[str, Any]] | None:
    """
    Call the external flight API and return a list of flights, or None on failure.
    This is the equivalent of make_nws_request in the weather example.
    """
    url = f"{FLIGHT_API_BASE}/flights"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                params={
                    "origin": origin,
                    "destination": destination,
                    "date": date,
                },
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()
    except Exception:
        # For now, hide the details and just signal "no data"
        return None


def format_flight(flight: Dict[str, Any]) -> str:
    """
    Convert a single flight dict into a readable string.
    This is analogous to format_alert in the weather example.
    """
    return (
        f"Flight {flight.get('id', 'UNKNOWN')}: "
        f"{flight.get('origin', '???')} → {flight.get('destination', '???')} "
        f"on {flight.get('date', '????-??-??')} "
        f"with {flight.get('airline', 'Unknown Airline')} "
        f"for {flight.get('price', 'N/A')} EUR"
    )


@mcp.tool()
async def search_flights(origin: str, destination: str, date: str) -> str:
    """
    Search for flights between origin and destination on a given date.

    Args:
        origin: Origin airport code (e.g. ATH)
        destination: Destination airport code (e.g. LHR)
        date: Departure date in YYYY-MM-DD format
    """
    # 1) Validate date format
    try:
        parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        return "Invalid date format. Use YYYY-MM-DD."

    # (Optional) you can also validate origin/destination length
    if len(origin) != 3 or len(destination) != 3:
        return "Origin and destination should be 3-letter airport codes (e.g. ATH, LHR)."

    # 2) Call the external flight API
    flights = await fetch_flights_from_api(origin, destination, str(parsed_date))

    if flights is None:
        return "Unable to fetch flights from the flight API."

    if not flights:
        return f"No flights found from {origin} to {destination} on {parsed_date}."

    # 3) Format the flights into a readable response
    formatted = [format_flight(f) for f in flights]
    return "\n".join(formatted)


def main() -> None:
    # Start the MCP server, communicating over stdio
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
