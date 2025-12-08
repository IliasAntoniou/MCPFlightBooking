# MCPFlightBooking

An AI-powered flight booking application demonstrating the Model Context Protocol (MCP). Users interact with a conversational AI assistant through a web interface to search flights and manage bookings. The system integrates Google Gemini with MCP servers to provide natural language access to flight data and booking operations.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│ Web Frontend (index.html)                           │
│ - Chat interface & user authentication              │
│ - Tool authorization (approve/deny actions)         │
└────────────────────┬────────────────────────────────┘
                     │ HTTP
                     ↓
┌─────────────────────────────────────────────────────┐
│ Backend Server (server.py) - Port 8001              │
│ - Gemini AI + MCP client host                       │
│ - Conversation & session management                 │
└────────────────────┬────────────────────────────────┘
                     │ MCP Protocol (STDIO)
         ┌───────────┴──────────────┐
         │                          │
┌────────▼─────────┐      ┌─────────▼─────────┐
│ flightsearch.py  │      │ flightbooking.py  │
│ MCP Server       │      │ MCP Server        │
└────────┬─────────┘      └─────────┬─────────┘
         │ HTTP                     │ HTTP
         └────────────┬─────────────┘
                      ↓
┌─────────────────────────────────────────────────────┐
│ Flight API (flight_api.py) - Port 8000              │
│ - SQLite database (100k flights, seat tracking)     │
│ - REST endpoints for search & booking               │
└─────────────────────────────────────────────────────┘
```

## ✨ Key Features

- **Natural Language Interface**: Chat with AI to search and book flights
- **MCP Integration**: Two MCP servers (search & booking) using JSON-RPC over STDIO
- **Tool Authorization**: Users approve AI actions before execution
- **Seat Management**: Real-time tracking with 100 seats per flight, prevents overbooking
- **User Authentication**: Profile management with persistent sessions
- **100,000 Flights**: Pre-generated SQLite database with realistic flight data
- **Context Awareness**: AI understands conversation history and current date/time

## 📁 Project Structure

```
MCPFlightBooking/
├── src/
│   ├── backend/
│   │   ├── server.py          # Main FastAPI app + MCP client host
│   │   ├── config.py          # Centralized configuration
│   │   ├── db.py              # Database operations
│   │   ├── flight_api.py      # FastAPI flight search API
│   │   ├── flight_app.db      # SQLite database (100k flights)
│   │   └── .env               # API keys (GOOGLE_AI_STUDIO_API_KEY)
│   │
│   ├── frontend/
│   │   └── index.html         # Web UI with chat interface
│   │
│   └── MCPservers/
│       ├── flightsearch.py    # MCP server for flight search
│       └── flightbooking.py   # MCP server for booking management
│
├── start.ps1                  # PowerShell startup script
├── start.bat                  # Batch startup script
└── README.md
```

## 🛠️ Technology Stack

- **Backend**: Python 3.13, FastAPI, Uvicorn
- **AI Model**: Google Gemini (gemini-flash-latest)
- **MCP Framework**: FastMCP, MCP Python SDK
- **Database**: SQLite
- **Frontend**: Vanilla HTML/CSS/JavaScript
- **Transport**: STDIO (Standard Input/Output) for MCP communication

## 📦 Installation

### Prerequisites
- Python 3.13+
- UV package manager (for running MCP servers)
- Google AI Studio API key

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/IliasAntoniou/MCPFlightBooking.git
   cd MCPFlightBooking
   ```

2. **Install dependencies**
   ```bash
   pip install fastapi uvicorn python-dotenv google-generativeai mcp httpx
   ```

3. **Configure environment variables**
   
   Create `src/backend/.env`:
   ```
   GOOGLE_AI_STUDIO_API_KEY=your_api_key_here
   ```

4. **Initialize database** (automatic on first run)
   
   The system will automatically generate 100,000 flights on first startup.

## 🚀 Running the Application

### Option 1: Automated Start (Recommended)

**Windows PowerShell:**
```powershell
.\start.ps1
```

**Windows Command Prompt:**
```cmd
start.bat
```

This will:
1. Start the Flight API server (port 8000)
2. Start the Gemini + MCP server (port 8001)
3. Open the web interface in your browser

### Option 2: Manual Start

**Terminal 1 - Flight API:**
```bash
cd src/backend
python -m uvicorn flight_api:app --reload --port 8000
```

**Terminal 2 - Main Server:**
```bash
cd src/backend
python -m uvicorn server:app --reload --port 8001
```

**Terminal 3 - Open Browser:**
```bash
start src/frontend/index.html
```

## 💬 Usage

1. **Login** with demo credentials:
   - Email: `john.doe@example.com`
   - Password: `secret123`

2. **Chat with the AI assistant**:
   - "Search flights from ATH to BCN on 2025-12-03"
   - "Show me my bookings"
   - "Book flight FL-012345 for John Doe"

3. **Approve tool calls** when prompted

4. **Manage your profile** via the profile page

## 🔧 MCP Tools

**Flight Search** (`flightsearch.py`)
- `search_flights` - Find flights by origin, destination, and date
- `getflightbyid` - Get details for a specific flight
- Features: LRU caching, input validation, structured logging

**Flight Booking** (`flightbooking.py`)
- `book_flight` - Create confirmed booking (checks seat availability)
- `hold_flight` - Temporary hold with expiration
- `confirm_held_booking` - Convert hold to confirmed booking
- `cancel_booking` - Delete booking and restore seats
- `get_booking_details` - View booking information
- `get_user_bookings` - List all user bookings
- Features: Atomic seat updates, overbooking prevention, hold expiration tracking

## 🔒 How It Works

1. User sends message via web interface
2. Gemini AI determines if tool execution is needed
3. User approves/denies tool call
4. MCP server executes tool and returns result
5. AI formats response and displays to user

All tool executions require explicit user approval for safety.

## 📝 Notes

This is a thesis project demonstrating Model Context Protocol integration with conversational AI for flight booking operations.

## 🔗 Resources

- [Model Context Protocol Documentation](https://modelcontextprotocol.io/)
- [FastMCP Framework](https://github.com/jlowin/fastmcp)
- [Google Gemini API](https://ai.google.dev/)
