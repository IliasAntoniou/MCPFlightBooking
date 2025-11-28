from fastapi import FastAPI, Query, HTTPException
from typing import List, Dict, Any
import datetime
import time
import random

app = FastAPI(title="Fake Flight API")

# ---------------------------
# Config for data generation
# ---------------------------

AIRPORTS = [
    "ATH", "LHR", "CDG", "FRA", "AMS", "MAD", "BCN", "MUC", "ZRH", "VIE",
    "ROM", "BER", "DUB", "CPH", "ARN", "OSL", "HEL", "IST", "PRG", "BUD"
]

AIRLINES = [
    "Hellas Air",
    "EuroSky",
    "Global Wings",
    "SkyLink",
    "Air Continental",
    "BlueJet",
]

BASE_DATE = datetime.date(2025, 12, 1)
NUM_DAYS = 60              # how many days forward to generate
TARGET_FLIGHTS = 100_000   # total number of flights to generate


def generate_flights(num_flights: int) -> List[Dict[str, Any]]:
    """Generate num_flights fake flight records."""
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
            }
        )
        current_id += 1

    return flights


# 🔹 Generate ~100k flights at startup
FLIGHTS: List[Dict[str, Any]] = generate_flights(TARGET_FLIGHTS)
print(f"[flight_api] Generated {len(FLIGHTS)} flights")  # goes to server console

# 🔹 Fast lookup by flight id
FLIGHTS_BY_ID: Dict[str, Dict[str, Any]] = {f["id"]: f for f in FLIGHTS}


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

    # ✅ simulate network latency (for thesis experiments)
    time.sleep(random.uniform(0.2, 0.6))

    # ✅ basic date validation
    try:
        datetime.date.fromisoformat(date)
    except ValueError:
        return []

    return [
        f
        for f in FLIGHTS
        if f["origin"] == origin
        and f["destination"] == destination
        and f["date"] == date
    ]


@app.get("/flights/{flight_id}")
def get_flight_by_id(flight_id: str) -> Dict[str, Any]:
    """
    Get a single flight by its ID.

    Example:
    GET /flights/FL-000123
    """

    # ✅ simulate network latency (optional, a bit shorter)
    time.sleep(random.uniform(0.1, 0.3))

    flight = FLIGHTS_BY_ID.get(flight_id)
    if not flight:
        raise HTTPException(status_code=404, detail="Flight not found")

    return flight
