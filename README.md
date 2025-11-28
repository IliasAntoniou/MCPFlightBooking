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

---

## Fake API

Includes a mock API created to mimic a real API which generates **100,000** flights.
