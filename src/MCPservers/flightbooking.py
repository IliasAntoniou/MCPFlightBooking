import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, List
from uuid import uuid4

from mcp.server.fastmcp import FastMCP

# -------------------------
# MCP server init
# -------------------------

mcp = FastMCP("booking")

# -------------------------
# Logging setup
# -------------------------

DEFAULT_LOG_PATH = Path(__file__).parent / "booking.log"
LOG_FILE = Path(DEFAULT_LOG_PATH)

logger = logging.getLogger("booking")
logger.setLevel(logging.INFO)

if not logger.handlers:
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

logger.info("==== Booking MCP server starting ====")
logger.info(f"Logging to file: {LOG_FILE.resolve()}")


# -------------------------
# In-memory booking store
# -------------------------

bookings: Dict[str, Dict[str, Any]] = {}


def create_booking(
    user_id: str,
    flight_id: str,
    passenger: Dict[str, Any],
    seats: int = 1,
) -> Dict[str, Any]:
    booking_id = f"BK-{uuid4().hex[:10].upper()}"
    now = datetime.utcnow().isoformat() + "Z"

    booking = {
        "id": booking_id,
        "user_id": user_id,
        "flight_id": flight_id,
        "passenger": passenger,
        "seats": seats,
        "status": "CONFIRMED",
        "created_at": now,
        "updated_at": now,
    }
    bookings[booking_id] = booking
    return booking


def get_booking(booking_id: str) -> Optional[Dict[str, Any]]:
    return bookings.get(booking_id)


def get_bookings_by_user(user_id: str) -> List[Dict[str, Any]]:
    return [
        b for b in bookings.values()
        if b.get("user_id") == user_id
    ]


def format_booking(booking: Dict[str, Any]) -> str:
    passenger = booking.get("passenger", {})
    name = passenger.get("name", "Unknown Passenger")
    email = passenger.get("email", "unknown@example.com")

    return (
        f"Booking {booking.get('id', 'UNKNOWN')}:\n"
        f"  User ID: {booking.get('user_id', 'UNKNOWN')}\n"
        f"  Flight ID: {booking.get('flight_id', 'UNKNOWN')}\n"
        f"  Passenger: {name} ({email})\n"
        f"  Seats: {booking.get('seats', '?')}\n"
        f"  Status: {booking.get('status', 'UNKNOWN')}\n"
        f"  Created at: {booking.get('created_at', '')}\n"
        f"  Updated at: {booking.get('updated_at', '')}"
    )


# -------------------------
# MCP tools
# -------------------------

@mcp.tool()
async def book_flight(
    user_id: str,
    flight_id: str,
    passenger_name: str,
    passenger_email: str,
    seats: int = 1,
) -> str:
    """
    Create a booking for a given flight and user.

    Arguments:
      - user_id: ID of the user making the booking
      - flight_id: ID of the flight (e.g., FL-000123)
      - passenger_name: Full name of the passenger
      - passenger_email: Email of the passenger
      - seats: Number of seats to book (default: 1)
    """
    logger.info(
        f"book_flight called | user_id={user_id} flight_id={flight_id} "
        f"passenger_name={passenger_name} seats={seats}"
    )

    if seats <= 0:
        logger.warning(f"Invalid seats value: {seats}")
        return "Seats must be at least 1."

    passenger = {
        "name": passenger_name,
        "email": passenger_email,
    }

    booking = create_booking(user_id, flight_id, passenger, seats)
    logger.info(
        f"Booking created | booking_id={booking['id']} "
        f"user_id={user_id} flight_id={flight_id}"
    )

    return format_booking(booking)


@mcp.tool()
async def get_booking_details(booking_id: str) -> str:
    """
    Retrieve details of a booking by its ID.

    Arguments:
      - booking_id: ID of the booking (e.g., BK-XXXXXXXXXX)
    """
    logger.info(f"get_booking_details called | booking_id={booking_id}")

    booking = get_booking(booking_id)
    if booking is None:
        logger.warning(f"Booking not found | booking_id={booking_id}")
        return f"No booking found with ID {booking_id}."

    return format_booking(booking)


@mcp.tool()
async def get_user_bookings(user_id: str) -> str:
    """
    Retrieve all bookings for a given user ID.

    Arguments:
      - user_id: ID of the user
    """
    logger.info(f"get_user_bookings called | user_id={user_id}")

    user_bookings = get_bookings_by_user(user_id)

    if not user_bookings:
        logger.info(f"No bookings for user_id={user_id}")
        return f"No bookings found for user {user_id}."

    lines = [
        f"{i+1}. {format_booking(b)}"
        for i, b in enumerate(user_bookings)
    ]
    return "\n\n".join(lines)


# -------------------------
# Entry point
# -------------------------

def main() -> None:
    logger.info("Running Booking MCP server (transport=stdio)")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
