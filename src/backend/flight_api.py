from fastapi import FastAPI, Query, HTTPException
from typing import List, Dict, Any
import datetime
import time
import random
import sqlite3

# Import from centralized config and db module
from config import TARGET_FLIGHTS
from db import (
    get_conn,
    init_db,
    count_flights,
    bulk_insert_flights,
    generate_flights,
)

app = FastAPI(title="Flight API (DB-backed)")


# ---------------------------
# Startup: ensure DB + seed
# ---------------------------

@app.on_event("startup")
def startup_event() -> None:
    """Initialize database and seed flights if empty."""
    init_db()
    existing = count_flights()
    if existing == 0:
        print(f"[flight_api] No flights in DB, generating {TARGET_FLIGHTS} flights...")
        flights = generate_flights(TARGET_FLIGHTS)
        bulk_insert_flights(flights)
        print(f"[flight_api] Inserted {len(flights)} flights into DB")
    else:
        print(f"[flight_api] DB already has {existing} flights, skipping generation")


# ---------------------------
# Endpoints
# ---------------------------

@app.get("/flights")
def search_flights(
    origin: str = Query(..., min_length=3, max_length=3),
    destination: str = Query(..., min_length=3, max_length=3),
    date: str = Query(..., description="YYYY-MM-DD"),
) -> List[Dict[str, Any]]:
    """
    Search flights by origin, destination, and date.

    Example:
    GET /flights?origin=ATH&destination=LHR&date=2025-12-01
    """

    # simulate network latency (for thesis experiments)
    time.sleep(random.uniform(0.2, 0.6))

    # basic date validation
    try:
        datetime.date.fromisoformat(date)
    except ValueError:
        return []

    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT * FROM flights
            WHERE origin = ? AND destination = ? AND date = ?
            ORDER BY price ASC
            """,
            (origin.upper(), destination.upper(), date),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    return [dict(r) for r in rows]


@app.get("/flights/{flight_id}")
def get_flight_by_id(flight_id: str) -> Dict[str, Any]:
    """
    Get a single flight by its ID.

    Example:
    GET /flights/FL-000123
    """

    # simulate network latency (optional, a bit shorter)
    time.sleep(random.uniform(0.1, 0.3))

    conn = get_conn()
    try:
        cur = conn.execute("SELECT * FROM flights WHERE id = ?", (flight_id,))
        row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="Flight not found")

    return dict(row)
