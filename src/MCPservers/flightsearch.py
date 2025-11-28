import os
from datetime import datetime
from typing import Any, List, Dict, Tuple
import sys
import time
import logging
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("flightsearch")

FLIGHT_API_BASE = os.environ.get("FLIGHT_API_BASE", "http://localhost:8000")

# -------------------------
# Logging setup
# -------------------------

# Default: log file sits next to this Python file
DEFAULT_LOG_PATH = Path(__file__).parent / "flightsearch.log"
LOG_FILE = Path(os.environ.get("FLIGHTSEARCH_LOG_FILE", str(DEFAULT_LOG_PATH)))

logger = logging.getLogger("flightsearch")
logger.setLevel(logging.INFO)

# Only add handlers once (important if the module is imported multiple times)
if not logger.handlers:
    # File handler ONLY – safest in MCP/stdio context
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s"
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

# Let’s log where we’re writing so you can find it easily
logger.info("==== Flightsearch MCP server starting ====")
logger.info(f"Logging to file: {LOG_FILE.resolve()}")


# -------------------------
# Simple in-memory cache
# -------------------------

CACHE_ENABLED: bool = True

# key: (origin, destination, date)
# value: final string returned to Claude
flight_cache: dict[Tuple[str, str, str], str] = {}

# basic stats
cache_hits: int = 0
cache_misses: int = 0

async def fetch_flight_by_id(flight_id: str) -> Dict[str, Any] | None:
    url = f"{FLIGHT_API_BASE}/flights/{flight_id}"

    try:
        logger.info(f"Fetching flight by ID from API | flight_id={flight_id}")
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            flight = response.json()
            logger.info(f"API response received for flight_id={flight_id}")
            return flight
    except Exception as e:
        logger.exception(f"Error fetching flight by ID from API: {e}")
        return None


async def fetch_flights_from_api(
    origin: str,
    destination: str,
    date: str,
) -> List[Dict[str, Any]] | None:
    url = f"{FLIGHT_API_BASE}/flights"

    try:
        logger.info(
            f"Fetching flights from API | origin={origin} destination={destination} date={date}"
        )
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
            flights = response.json()
            logger.info(
                f"API response received | flights_count="
                f"{len(flights) if isinstance(flights, list) else 'unknown'}"
            )
            return flights
    except Exception as e:
        logger.exception(f"Error fetching flights from API: {e}")
        return None


def format_flight(flight: Dict[str, Any]) -> str:
    return (
        f"[{flight.get('id', 'UNKNOWN')}] "
        f"{flight.get('origin', '???')} → {flight.get('destination', '???')} | "
        f"Date: {flight.get('date', '????-??-??')} | "
        f"Airline: {flight.get('airline', 'Unknown')} | "
        f"Price: {flight.get('price', 'N/A')} EUR"
    )


@mcp.tool()
async def getflightbyid(flight_id: str) -> str:
    logger.info(f"getflightbyid called | flight_id={flight_id}")
    flight = await fetch_flight_by_id(flight_id)
    if flight is None:
        return "Unable to fetch flight details from the flight API."
    return format_flight(flight)

@mcp.tool()
async def search_flights(origin: str, destination: str, date: str) -> str:
    global cache_hits, cache_misses

    logger.info(f"search_flights called | origin={origin} destination={destination} date={date}")

    try:
        parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        msg = "Invalid date format. Use YYYY-MM-DD."
        logger.warning(f"Invalid date format: {date}")
        return msg

    if len(origin) != 3 or len(destination) != 3:
        msg = "Origin and destination should be 3-letter airport codes (e.g. ATH, LHR)."
        logger.warning(f"Invalid airport codes | origin={origin} destination={destination}")
        return msg

    origin = origin.upper()
    destination = destination.upper()

    cache_key = (origin, destination, str(parsed_date))
    start_time = time.time()

    # 1) Check cache first
    if CACHE_ENABLED and cache_key in flight_cache:
        cache_hits += 1
        duration = (time.time() - start_time) * 1000
        logger.info(
            f"[CACHE HIT] {cache_key} | hits={cache_hits} misses={cache_misses} | {duration:.2f}ms"
        )
        logger.info(f"[CACHE VALUE] key={cache_key} value={flight_cache[cache_key]!r}")
        return flight_cache[cache_key]

    cache_misses += 1

    # 2) Call backend on miss
    flights = await fetch_flights_from_api(origin, destination, str(parsed_date))

    if flights is None:
        duration = (time.time() - start_time) * 1000
        logger.error(
            f"[CACHE MISS/ERROR] {cache_key} | hits={cache_hits} misses={cache_misses} | {duration:.2f}ms"
        )
        return "Unable to fetch flights from the flight API."

    if not flights:
        result = f"No flights found from {origin} to {destination} on {parsed_date}."
        if CACHE_ENABLED:
            flight_cache[cache_key] = result
            logger.info(f"[CACHE WRITE EMPTY] key={cache_key} value={result!r}")
        duration = (time.time() - start_time) * 1000
        logger.info(
            f"[CACHE MISS/EMPTY] {cache_key} | hits={cache_hits} misses={cache_misses} | {duration:.2f}ms"
        )
        return result

    formatted_list = [format_flight(f) for f in flights]
    result = "\n".join(formatted_list)

    if CACHE_ENABLED:
        flight_cache[cache_key] = result
        logger.info(f"[CACHE WRITE] key={cache_key} value={result!r}")

    duration = (time.time() - start_time) * 1000
    logger.info(
        f"[CACHE MISS] {cache_key} | hits={cache_hits} misses={cache_misses} | {duration:.2f}ms"
    )

    return result


def main() -> None:
    logger.info("Running MCP server (transport=stdio)")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
