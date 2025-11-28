# MCPFlightBooking

Creation of an MCP mock system used to book flights that uses cache and replication to achieve:
- lower average latency  
- higher reliability  
- higher fault tolerance  

---

## MCP Servers

### `flightsearch.py`

**Tools:**

- `search_flights(origin, destination, date)`  
  Returns all flights with the given parameters.

- `getflightbyid(id)`  
  Returns the details of the flight with the given ID.

### `flightbooking.py`

**Tools:**

- `book_flight(user_id, flight_id, passenger_name, passenger_email, seats)`  
  Creates a booking for the given user and flight.

- `get_booking_details(booking_id)`  
  Returns the details of the booking with the given ID.

- `get_user_bookings(user_id)`  
  Returns all bookings associated with the given user ID.

---

## Fake API

Includes a mock API created to mimic a real API which generates **100,000** flights.
