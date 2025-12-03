import os
from datetime import datetime
from typing import Any, List, Dict, Tuple, Optional
import sys
import time
import logging
from pathlib import Path
from collections import OrderedDict
import re

import httpx
from pydantic import BaseModel, Field, validator
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
# LRU Cache with size limit
# -------------------------

CACHE_ENABLED: bool = True
MAX_CACHE_SIZE: int = 100  # Maximum number of cached queries

# LRU cache: OrderedDict maintains insertion order, we'll move accessed items to end
# key: (origin, destination, date)
# value: final string returned to Claude
flight_cache: OrderedDict[Tuple[str, str, str], str] = OrderedDict()

# cache stats
cache_hits: int = 0
cache_misses: int = 0
cache_evictions: int = 0  # Track how many items were evicted


# -------------------------
# Validation Models
# -------------------------

class FlightSearchValidation(BaseModel):
    """Validation model for flight search parameters."""
    origin: str = Field(..., min_length=3, max_length=3, pattern=r'^[A-Z]{3}$')
    destination: str = Field(..., min_length=3, max_length=3, pattern=r'^[A-Z]{3}$')
    date: str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$')
    
    @validator('date')
    def validate_date(cls, v):
        try:
            date_obj = datetime.strptime(v, '%Y-%m-%d').date()
            # Check if date is not in the past
            if date_obj < datetime.now().date():
                raise ValueError('Date cannot be in the past')
            return v
        except ValueError as e:
            if 'does not match format' in str(e):
                raise ValueError('Date must be in YYYY-MM-DD format')
            raise
    
    @validator('origin', 'destination')
    def validate_airport_code(cls, v):
        if not v.isupper():
            raise ValueError('Airport code must be uppercase')
        return v


class FlightIdValidation(BaseModel):
    """Validation model for flight ID."""
    flight_id: str = Field(..., pattern=r'^FL-\d{6}$')


def validate_search_params(origin: str, destination: str, date: str) -> tuple[bool, Optional[str]]:
    """Validate flight search parameters. Returns (is_valid, error_message)."""
    try:
        # Normalize to uppercase
        origin = origin.upper()
        destination = destination.upper()
        
        FlightSearchValidation(origin=origin, destination=destination, date=date)
        return True, None
    except Exception as e:
        error_msg = str(e)
        if "origin" in error_msg.lower() or "destination" in error_msg.lower():
            if "3" in error_msg:
                return False, "Airport codes must be exactly 3 letters (e.g., ATH, LHR, BCN)."
            else:
                return False, "Airport codes must be 3 uppercase letters (e.g., ATH, LHR, BCN)."
        elif "date" in error_msg.lower():
            if "past" in error_msg.lower():
                return False, "Cannot search for flights in the past. Please select a future date."
            else:
                return False, "Invalid date format. Please use YYYY-MM-DD format (e.g., 2025-12-15)."
        else:
            return False, f"Validation error: {error_msg}"


def validate_flight_id(flight_id: str) -> tuple[bool, Optional[str]]:
    """Validate flight ID format. Returns (is_valid, error_message)."""
    try:
        FlightIdValidation(flight_id=flight_id)
        return True, None
    except Exception:
        return False, "Invalid flight ID format. Flight ID should be in format FL-XXXXXX (e.g., FL-001234)."


# -------------------------
# API Helper Functions
# -------------------------

async def fetch_flight_by_id(flight_id: str) -> Dict[str, Any] | None:
    url = f"{FLIGHT_API_BASE}/flights/{flight_id}"

    try:
        logger.info(
            "Fetching flight by ID from API",
            extra={"action": "fetch_flight_by_id", "flight_id": flight_id}
        )
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            flight = response.json()
            logger.info(
                "Flight retrieved successfully",
                extra={"action": "fetch_flight_by_id_success", "flight_id": flight_id}
            )
            return flight
    except httpx.HTTPStatusError as e:
        logger.error(
            "HTTP error fetching flight",
            extra={
                "action": "fetch_flight_by_id_error",
                "status_code": e.response.status_code,
                "flight_id": flight_id
            }
        )
        return None
    except Exception as e:
        logger.exception(
            "Unexpected error fetching flight",
            extra={"action": "fetch_flight_by_id_exception", "flight_id": flight_id}
        )
        return None


async def fetch_flights_from_api(
    origin: str,
    destination: str,
    date: str,
) -> List[Dict[str, Any]] | None:
    url = f"{FLIGHT_API_BASE}/flights"

    try:
        logger.info(
            "Fetching flights from API",
            extra={
                "action": "fetch_flights",
                "origin": origin,
                "destination": destination,
                "date": date
            }
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
            flight_count = len(flights) if isinstance(flights, list) else 0
            logger.info(
                "Flights retrieved successfully",
                extra={
                    "action": "fetch_flights_success",
                    "origin": origin,
                    "destination": destination,
                    "date": date,
                    "count": flight_count
                }
            )
            return flights
    except httpx.HTTPStatusError as e:
        logger.error(
            "HTTP error fetching flights",
            extra={
                "action": "fetch_flights_error",
                "status_code": e.response.status_code,
                "origin": origin,
                "destination": destination
            }
        )
        return None
    except httpx.TimeoutException:
        logger.error(
            "Timeout fetching flights",
            extra={
                "action": "fetch_flights_timeout",
                "origin": origin,
                "destination": destination
            }
        )
        return None
    except Exception as e:
        logger.exception(
            "Unexpected error fetching flights",
            extra={
                "action": "fetch_flights_exception",
                "origin": origin,
                "destination": destination
            }
        )
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
    """Get details of a specific flight by its ID."""
    logger.info(
        "getflightbyid tool called",
        extra={"tool": "getflightbyid", "flight_id": flight_id}
    )
    
    # Validate flight ID format
    is_valid, error_msg = validate_flight_id(flight_id)
    if not is_valid:
        logger.warning(
            "Invalid flight ID format",
            extra={"tool": "getflightbyid", "flight_id": flight_id}
        )
        return f"❌ {error_msg}"
    
    flight = await fetch_flight_by_id(flight_id)
    if flight is None:
        return f"❌ Flight not found: No flight exists with ID {flight_id}. Please check the flight ID and try again."
    return "✈️ " + format_flight(flight)

@mcp.tool()
async def search_flights(origin: str, destination: str, date: str) -> str:
    """Search for available flights between two airports on a specific date."""
    global cache_hits, cache_misses

    logger.info(
        "search_flights tool called",
        extra={
            "tool": "search_flights",
            "origin": origin,
            "destination": destination,
            "date": date
        }
    )

    # Normalize airport codes to uppercase
    origin = origin.upper().strip()
    destination = destination.upper().strip()
    date = date.strip()

    # Validate search parameters
    is_valid, error_msg = validate_search_params(origin, destination, date)
    if not is_valid:
        logger.warning(
            "Flight search validation failed",
            extra={
                "tool": "search_flights",
                "origin": origin,
                "destination": destination,
                "date": date,
                "error": error_msg
            }
        )
        return f"❌ {error_msg}"

    # Additional check: origin and destination can't be the same
    if origin == destination:
        return "❌ Origin and destination cannot be the same airport."

    try:
        parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        return "❌ Invalid date format. Please use YYYY-MM-DD format (e.g., 2025-12-15)."

    cache_key = (origin, destination, str(parsed_date))
    start_time = time.time()

    # 1) Check cache first
    if CACHE_ENABLED and cache_key in flight_cache:
        cache_hits += 1
        # Move to end (mark as recently used in LRU)
        flight_cache.move_to_end(cache_key)
        duration = (time.time() - start_time) * 1000
        logger.info(
            f"[CACHE HIT] {cache_key} | hits={cache_hits} misses={cache_misses} evictions={cache_evictions} | size={len(flight_cache)}/{MAX_CACHE_SIZE} | {duration:.2f}ms"
        )
        logger.info(f"[CACHE VALUE] key={cache_key} value={flight_cache[cache_key]!r}")
        return flight_cache[cache_key]

    cache_misses += 1

    # 2) Call backend on miss
    flights = await fetch_flights_from_api(origin, destination, str(parsed_date))

    if flights is None:
        duration = (time.time() - start_time) * 1000
        logger.error(
            f"[CACHE MISS/ERROR] {cache_key} | hits={cache_hits} misses={cache_misses} evictions={cache_evictions} | size={len(flight_cache)}/{MAX_CACHE_SIZE} | {duration:.2f}ms"
        )
        return "❌ Unable to search flights: The flight service is currently unavailable. Please try again in a few moments."

    if not flights:
        result = f"🚫 No flights available from {origin} to {destination} on {parsed_date}.\n\nTry searching for:\n- A different date\n- Nearby airports\n- Alternative routes"
        if CACHE_ENABLED:
            _add_to_cache(cache_key, result)
            logger.info(f"[CACHE WRITE EMPTY] key={cache_key} value={result!r}")
        duration = (time.time() - start_time) * 1000
        logger.info(
            f"[CACHE MISS/EMPTY] {cache_key} | hits={cache_hits} misses={cache_misses} evictions={cache_evictions} | size={len(flight_cache)}/{MAX_CACHE_SIZE} | {duration:.2f}ms"
        )
        return result

    formatted_list = [format_flight(f) for f in flights]
    result = f"✈️ Found {len(flights)} flight(s) from {origin} to {destination} on {parsed_date}:\n\n" + "\n".join(formatted_list)

    if CACHE_ENABLED:
        _add_to_cache(cache_key, result)
        logger.info(f"[CACHE WRITE] key={cache_key} value={result!r}")

    duration = (time.time() - start_time) * 1000
    logger.info(
        f"[CACHE MISS] {cache_key} | hits={cache_hits} misses={cache_misses} evictions={cache_evictions} | size={len(flight_cache)}/{MAX_CACHE_SIZE} | {duration:.2f}ms"
    )

    return result


def _add_to_cache(key: Tuple[str, str, str], value: str) -> None:
    """
    Add item to LRU cache with eviction policy.
    If cache is full, removes the least recently used item (first item in OrderedDict).
    """
    global cache_evictions
    
    # Check if we need to evict
    if len(flight_cache) >= MAX_CACHE_SIZE and key not in flight_cache:
        # Remove least recently used (first item)
        evicted_key = next(iter(flight_cache))
        flight_cache.pop(evicted_key)
        cache_evictions += 1
        logger.info(f"[CACHE EVICTION] Evicted LRU key={evicted_key} | total_evictions={cache_evictions}")
    
    # Add new item (goes to end, marking it as most recently used)
    flight_cache[key] = value


def main() -> None:
    logger.info("Running MCP server (transport=stdio)")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
