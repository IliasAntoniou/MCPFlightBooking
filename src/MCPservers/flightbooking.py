import sys
from pathlib import Path
import logging
from datetime import datetime
from typing import Any, Dict, Optional, List

from mcp.server.fastmcp import FastMCP

# -------------------------
# Make src/backend importable
# -------------------------

CURRENT_DIR = Path(__file__).resolve().parent          # .../src/MCPservers
BACKEND_DIR = CURRENT_DIR.parent / "backend"           # .../src/backend

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Import from db module (path added to sys.path above)
from db import (  # type: ignore
    init_db,
    create_booking as db_create_booking,
    get_booking as db_get_booking,
    get_bookings_by_user as db_get_bookings_by_user,
    update_booking_status as db_update_booking_status,
)

# -------------------------
# MCP server init
# -------------------------

mcp = FastMCP("booking")  # or "flights-booking"


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

# Ensure DB schema (flights + bookings) exists
init_db()
logger.info("Database initialized (init_db called from booking server).")


# -------------------------
# Helpers
# -------------------------

def format_booking(booking: Dict[str, Any]) -> str:
    """
    Turn a booking row (from DB) into a human-readable string.
    Matches the bookings table schema in db.py:
      id, user_id, flight_id, passenger_name, passenger_email,
      seats, status, created_at, updated_at, hold_expires_at, cancellation_reason
    """
    name = booking.get("passenger_name", "Unknown Passenger")
    email = booking.get("passenger_email", "unknown@example.com")

    hold_expires_at = booking.get("hold_expires_at")
    hold_line = f"  Hold expires at: {hold_expires_at}\n" if hold_expires_at else ""

    return (
        f"Booking {booking.get('id', 'UNKNOWN')}:\n"
        f"  User ID: {booking.get('user_id', 'UNKNOWN')}\n"
        f"  Flight ID: {booking.get('flight_id', 'UNKNOWN')}\n"
        f"  Passenger: {name} ({email})\n"
        f"  Seats: {booking.get('seats', '?')}\n"
        f"  Status: {booking.get('status', 'UNKNOWN')}\n"
        f"{hold_line}"
        f"  Created at: {booking.get('created_at', '')}\n"
        f"  Updated at: {booking.get('updated_at', '')}"
    ).rstrip()


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
    Create a CONFIRMED booking for a given flight and user.
    """
    logger.info(
        f"book_flight called | user_id={user_id} flight_id={flight_id} "
        f"passenger_name={passenger_name} seats={seats}"
    )

    if seats <= 0:
        logger.warning(f"Invalid seats value: {seats}")
        return "Seats must be at least 1."

    booking = db_create_booking(
        user_id=user_id,
        flight_id=flight_id,
        passenger_name=passenger_name,
        passenger_email=passenger_email,
        seats=seats,
        status="CONFIRMED",
    )

    logger.info(
        f"Booking created | booking_id={booking['id']} "
        f"user_id={user_id} flight_id={flight_id} status=CONFIRMED"
    )

    return format_booking(booking)


@mcp.tool()
async def hold_flight(
    user_id: str,
    flight_id: str,
    passenger_name: str,
    passenger_email: str,
    seats: int = 1,
    hold_minutes: int = 30,
) -> str:
    """
    Create a HELD booking (a temporary hold) for a given flight and user.
    """
    logger.info(
        f"hold_flight called | user_id={user_id} flight_id={flight_id} "
        f"passenger_name={passenger_name} seats={seats} hold_minutes={hold_minutes}"
    )

    if seats <= 0:
        logger.warning(f"Invalid seats value: {seats}")
        return "Seats must be at least 1."

    if hold_minutes <= 0:
        logger.warning(f"Invalid hold_minutes value: {hold_minutes}")
        return "hold_minutes must be at least 1."

    booking = db_create_booking(
        user_id=user_id,
        flight_id=flight_id,
        passenger_name=passenger_name,
        passenger_email=passenger_email,
        seats=seats,
        status="HELD",
        hold_minutes=hold_minutes,
    )

    logger.info(
        f"Hold created | booking_id={booking['id']} "
        f"user_id={user_id} flight_id={flight_id} status=HELD"
    )

    return format_booking(booking)


@mcp.tool()
async def confirm_held_booking(booking_id: str) -> str:
    """
    Turn a HELD booking into a CONFIRMED booking.
    """
    logger.info(f"confirm_held_booking called | booking_id={booking_id}")

    booking = db_get_booking(booking_id)
    if booking is None:
        logger.warning(f"Booking not found | booking_id={booking_id}")
        return f"No booking found with ID {booking_id}."

    if booking.get("status") != "HELD":
        return f"Booking {booking_id} is not in HELD status (current status: {booking.get('status')})."

    # Check hold expiry if present
    hold_expires_at = booking.get("hold_expires_at")
    if hold_expires_at:
        try:
            expires_dt = datetime.fromisoformat(hold_expires_at.replace("Z", ""))
            if datetime.utcnow() > expires_dt:
                logger.info(f"Hold expired | booking_id={booking_id}")
                db_update_booking_status(booking_id, "CANCELLED")
                return (
                    f"Hold for booking {booking_id} has expired and is now CANCELLED."
                )
        except Exception:
            # Ignore parsing issues; best effort only
            pass

    updated = db_update_booking_status(booking_id, "CONFIRMED")
    if not updated:
        return f"Failed to update booking {booking_id}."

    logger.info(f"Booking confirmed from HELD | booking_id={booking_id}")
    return format_booking(updated)


@mcp.tool()
async def cancel_booking(booking_id: str, reason: Optional[str] = None) -> str:
    """
    Cancel an existing booking.
    """
    logger.info(f"cancel_booking called | booking_id={booking_id} reason={reason!r}")

    booking = db_get_booking(booking_id)
    if booking is None:
        logger.warning(f"Booking not found | booking_id={booking_id}")
        return f"No booking found with ID {booking_id}."

    current_status = booking.get("status")
    if current_status == "CANCELLED":
        return f"Booking {booking_id} is already CANCELLED."

    updated = db_update_booking_status(booking_id, "CANCELLED", cancellation_reason=reason)
    if not updated:
        return f"Failed to update booking {booking_id}."

    logger.info(
        f"Booking cancelled | booking_id={booking_id} previous_status={current_status} reason={reason!r}"
    )
    return format_booking(updated)


@mcp.tool()
async def get_booking_details(booking_id: str) -> str:
    """
    Retrieve details of a booking by its ID.
    """
    logger.info(f"get_booking_details called | booking_id={booking_id}")

    booking = db_get_booking(booking_id)
    if booking is None:
        logger.warning(f"Booking not found | booking_id={booking_id}")
        return f"No booking found with ID {booking_id}."

    return format_booking(booking)


@mcp.tool()
async def get_user_bookings(user_id: str) -> str:
    """
    Retrieve all bookings for a given user ID.
    Use this when the user asks about "my bookings", "my reservations", or "my flights".
    The user_id should be the logged-in user's ID from the user context.
    """
    logger.info(f"get_user_bookings called | user_id={user_id}")

    user_bookings: List[Dict[str, Any]] = db_get_bookings_by_user(user_id)

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
