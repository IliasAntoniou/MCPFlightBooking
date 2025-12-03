import sqlite3
import datetime
import random
from typing import List, Dict, Any, Optional
from datetime import datetime as dt, timedelta
from uuid import uuid4

# Import centralized configuration
from config import (
    DB_PATH,
    AIRPORTS,
    AIRLINES,
    BASE_DATE,
    NUM_DAYS,
    TARGET_FLIGHTS,
)


# ---------------------------
# DB helpers
# ---------------------------

def get_conn() -> sqlite3.Connection:
    """
    Open a SQLite connection to the flight_app.db database.
    Caller is responsible for closing it.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """
    Create tables if they don't exist yet.
    Currently: flights, bookings.
    """
    conn = get_conn()
    try:
        # Flights table with seat capacity tracking
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS flights (
                id TEXT PRIMARY KEY,
                origin TEXT NOT NULL,
                destination TEXT NOT NULL,
                date TEXT NOT NULL,       -- YYYY-MM-DD
                airline TEXT NOT NULL,
                price REAL NOT NULL,
                available_seats INTEGER NOT NULL DEFAULT 100
            )
            """
        )

        # Bookings table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bookings (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                flight_id TEXT NOT NULL,
                passenger_name TEXT NOT NULL,
                passenger_email TEXT NOT NULL,
                seats INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                hold_expires_at TEXT,
                cancellation_reason TEXT
            )
            """
        )

        conn.commit()
    finally:
        conn.close()


# ---------------------------
# Flights: seed & helpers
# ---------------------------

def count_flights() -> int:
    """
    Return how many rows are currently in the flights table.
    """
    conn = get_conn()
    try:
        cur = conn.execute("SELECT COUNT(*) AS c FROM flights")
        row = cur.fetchone()
        return int(row["c"])
    finally:
        conn.close()


def check_seat_availability(flight_id: str, seats_requested: int) -> Dict[str, Any]:
    """
    Check if a flight has enough available seats.
    Returns dict with 'available' (bool) and 'seats_remaining' (int).
    """
    conn = get_conn()
    try:
        cur = conn.execute(
            "SELECT available_seats FROM flights WHERE id = ?",
            (flight_id,)
        )
        row = cur.fetchone()
        if not row:
            return {"available": False, "seats_remaining": 0, "error": "Flight not found"}
        
        seats_remaining = int(row["available_seats"])
        return {
            "available": seats_remaining >= seats_requested,
            "seats_remaining": seats_remaining
        }
    finally:
        conn.close()


def update_flight_seats(flight_id: str, seats_delta: int) -> bool:
    """
    Update available seats for a flight by adding seats_delta.
    Use negative delta to decrease seats (booking).
    Use positive delta to increase seats (cancellation).
    Returns True if successful, False if flight not found.
    This operation is atomic within a transaction.
    """
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            UPDATE flights 
            SET available_seats = available_seats + ? 
            WHERE id = ?
            """,
            (seats_delta, flight_id)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def bulk_insert_flights(flights: List[Dict[str, Any]]) -> None:
    """
    Insert a list of flight dicts into the flights table.
    Each dict must have keys: id, origin, destination, date, airline, price, available_seats.
    """
    conn = get_conn()
    try:
        conn.executemany(
            """
            INSERT INTO flights (id, origin, destination, date, airline, price, available_seats)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    f["id"],
                    f["origin"],
                    f["destination"],
                    f["date"],
                    f["airline"],
                    f["price"],
                    f.get("available_seats", 100),
                )
                for f in flights
            ],
        )
        conn.commit()
    finally:
        conn.close()


def generate_flights(num_flights: int) -> List[Dict[str, Any]]:
    """
    Generate num_flights fake flight records in memory.
    Does NOT write to the database by itself.
    """
    flights: List[Dict[str, Any]] = []
    random.seed(42)  # for reproducibility

    current_id = 1
    while len(flights) < num_flights:
        origin, destination = random.sample(AIRPORTS, 2)  # ensures origin != destination

        # random date in [BASE_DATE, BASE_DATE + NUM_DAYS)
        day_offset = random.randint(0, NUM_DAYS - 1)
        date = BASE_DATE + datetime.timedelta(days=day_offset)

        airline = random.choice(AIRLINES)
        price = round(random.uniform(50.0, 600.0), 2)

        flights.append(
            {
                "id": f"FL-{current_id:06d}",
                "origin": origin,
                "destination": destination,
                "date": date.isoformat(),
                "airline": airline,
                "price": price,
                "available_seats": 100,
            }
        )
        current_id += 1

    return flights


def seed_flights_if_empty(target: Optional[int] = None) -> int:
    """
    If the flights table is empty, generate and insert flights.
    Returns the number of flights in the DB after seeding.

    target: how many flights to generate. If None, uses TARGET_FLIGHTS.
    """
    init_db()
    existing = count_flights()
    if existing > 0:
        print(f"[db] flights table already has {existing} rows, skipping seeding.")
        return existing

    n = target if target is not None else TARGET_FLIGHTS
    print(f"[db] flights table empty, generating {n} flights...")
    flights = generate_flights(n)
    bulk_insert_flights(flights)
    final_count = count_flights()
    print(f"[db] seeding done, flights table now has {final_count} rows.")
    return final_count


# ---------------------------
# Bookings: helpers
# ---------------------------

def _now_iso() -> str:
    return dt.utcnow().isoformat(timespec="seconds") + "Z"


def create_booking(
    user_id: str,
    flight_id: str,
    passenger_name: str,
    passenger_email: str,
    seats: int = 1,
    status: str = "CONFIRMED",
    hold_minutes: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Create a new booking and atomically update flight seat availability.
    
    Validates seat availability before creating the booking. If sufficient seats
    are available, creates the booking and decrements available seats in a single
    transaction. Raises ValueError if insufficient seats or flight not found.
    """
    # Check seat availability first
    availability = check_seat_availability(flight_id, seats)
    if not availability["available"]:
        if "error" in availability:
            raise ValueError(availability["error"])
        raise ValueError(
            f"Not enough seats available. This flight has only {availability['seats_remaining']} seats remaining."
        )
    
    booking_id = f"BK-{uuid4().hex[:10].upper()}"
    now = _now_iso()

    hold_expires_at: Optional[str] = None
    if status == "HELD" and hold_minutes and hold_minutes > 0:
        hold_expires_at = (
            dt.utcnow() + timedelta(minutes=hold_minutes)
        ).isoformat(timespec="seconds") + "Z"

    conn = get_conn()
    try:
        # Start transaction - create booking and update seats atomically
        conn.execute(
            """
            INSERT INTO bookings (
                id, user_id, flight_id,
                passenger_name, passenger_email,
                seats, status, created_at, updated_at,
                hold_expires_at, cancellation_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                booking_id,
                user_id,
                flight_id,
                passenger_name,
                passenger_email,
                seats,
                status,
                now,
                now,
                hold_expires_at,
                None,
            ),
        )
        
        # Decrease available seats (negative delta)
        conn.execute(
            """
            UPDATE flights 
            SET available_seats = available_seats - ? 
            WHERE id = ?
            """,
            (seats, flight_id)
        )
        
        conn.commit()

        cur = conn.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,))
        row = cur.fetchone()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

    return dict(row)


def get_booking(booking_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,))
        row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        return None
    return dict(row)


def get_bookings_by_user(user_id: str) -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT * FROM bookings
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    return [dict(r) for r in rows]


def update_booking_status(
    booking_id: str,
    new_status: str,
    cancellation_reason: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        now = _now_iso()
        if cancellation_reason is not None:
            conn.execute(
                """
                UPDATE bookings
                SET status = ?, updated_at = ?, hold_expires_at = NULL,
                    cancellation_reason = ?
                WHERE id = ?
                """,
                (new_status, now, cancellation_reason, booking_id),
            )
        else:
            conn.execute(
                """
                UPDATE bookings
                SET status = ?, updated_at = ?, hold_expires_at = NULL
                WHERE id = ?
                """,
                (new_status, now, booking_id),
            )
        conn.commit()

        cur = conn.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,))
        row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        return None
    return dict(row)


def delete_booking(booking_id: str) -> bool:
    """
    Delete a booking and atomically restore seats to the flight.
    
    Returns True if booking was deleted, False if booking not found.
    The deletion and seat restoration occur in a single transaction.
    """
    conn = get_conn()
    try:
        # First, get the booking to find out how many seats to restore
        cur = conn.execute(
            "SELECT flight_id, seats FROM bookings WHERE id = ?",
            (booking_id,)
        )
        row = cur.fetchone()
        
        if not row:
            return False
        
        flight_id = row["flight_id"]
        seats = int(row["seats"])
        
        # Delete the booking and restore seats atomically
        conn.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
        
        # Restore seats (positive delta)
        conn.execute(
            """
            UPDATE flights 
            SET available_seats = available_seats + ? 
            WHERE id = ?
            """,
            (seats, flight_id)
        )
        
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
