# MCPFlightBooking

An AI-powered flight booking application that demonstrates the Model Context Protocol (MCP) by integrating multiple MCP servers with a conversational AI interface powered by Google Gemini. The system features a web-based chat interface where users can search flights, manage bookings, and interact naturally with an AI assistant that has access to flight data through MCP tools.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│ Web Frontend (index.html)                          │
│ - Aviation-themed UI with chat interface          │
│ - User authentication & profile management        │
│ - Tool authorization (approve/deny actions)       │
└────────────────────┬────────────────────────────────┘
                     │ HTTP/REST
                     ↓
┌─────────────────────────────────────────────────────┐
│ Backend Server (server.py)                         │
│ - GeminiMCPHost: Manages MCP client connections   │
│ - Conversation history & session management        │
│ - Tool authorization & execution flow              │
│ - Gemini API integration for natural language     │
└────────────────────┬────────────────────────────────┘
                     │ MCP Protocol (JSON-RPC over STDIO)
         ┌───────────┴──────────────┐
         │                          │
┌────────▼─────────┐      ┌────────▼──────────┐
│ MCP Server       │      │ MCP Server        │
│ flightsearch.py  │      │ flightbooking.py  │
│ - search_flights │      │ - book_flight     │
│ - getflightbyid  │      │ - hold_flight     │
└────────┬─────────┘      │ - confirm_held    │
         │                │ - cancel_booking  │
         │                │ - get_bookings    │
         │                │ - get_user_bkgs   │
         │                └───────────────────┘
         │ HTTP API
         ↓
┌─────────────────────────────────────────────────────┐
│ Flight API (flight_api.py)                         │
│ - SQLite database with 100,000 flights            │
│ - Flight search & retrieval endpoints             │
│ - Booking management                               │
└─────────────────────────────────────────────────────┘
```

## 🚀 Features

### Conversational AI Interface
- Natural language interaction with flight booking system
- Context-aware responses using conversation history
- User authentication with profile management
- Real-time chat with typing indicators and avatars

### MCP Integration
- **Two MCP Servers**: Flight search and booking management
- **Tool Discovery**: Dynamic tool listing via MCP protocol
- **Tool Execution**: Secure tool calls through MCP sessions
- **Multi-Server Support**: Seamless integration of multiple MCP servers

### User Safety & Transparency
- **Tool Authorization**: Users approve/deny AI actions before execution
- **Visual Feedback**: Clear display of tool calls with arguments
- **Session Management**: Persistent conversation history per user

### Database
- SQLite database with 100,000 pre-generated flights
- Flight search by origin, destination, and date
- Booking status management (CONFIRMED, HELD, CANCELLED)
- User booking history

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

## 🔧 MCP Servers

### `flightsearch.py`

**Purpose**: Provides flight search capabilities through MCP protocol

**Tools:**
- `search_flights(origin: str, destination: str, date: str)` - Search flights by criteria
- `getflightbyid(flight_id: str)` - Get specific flight details

**Features:**
- In-memory caching for improved performance
- Detailed logging to `flightsearch.log`
- HTTP API integration with backend

### `flightbooking.py`

**Purpose**: Manages flight bookings and reservations

**Tools:**
- `book_flight(user_id, flight_id, passenger_name, passenger_email, seats)` - Create confirmed booking
- `hold_flight(user_id, flight_id, passenger_name, passenger_email, seats, hold_minutes)` - Temporary hold
- `confirm_held_booking(booking_id)` - Confirm a held booking
- `cancel_booking(booking_id, reason)` - Cancel existing booking
- `get_booking_details(booking_id)` - Retrieve booking information
- `get_user_bookings(user_id)` - Get all bookings for a user

**Features:**
- Direct database integration
- Booking status management (CONFIRMED, HELD, CANCELLED)
- Expiration tracking for held bookings

## 🎯 Key Components

### GeminiMCPHost Class
The core orchestrator that:
- Connects to multiple MCP servers via STDIO transport
- Manages MCP client sessions
- Integrates with Gemini API for natural language understanding
- Handles tool discovery and execution
- Manages conversation context

### Tool Authorization Flow
1. User sends message
2. Gemini determines if tool call is needed
3. System requests user approval with tool details
4. User approves/denies
5. If approved, tool executes via MCP
6. Result formatted by Gemini and returned to user

## 🔒 Security Features

- User authentication required
- Tool authorization before execution
- Session-based conversation isolation
- User info validation
- Error handling and logging

## 🧪 Testing

Example queries to test the system:
```
"Search for flights from ATH to LHR on 2025-12-15"
"Show me my bookings"
"Book flight FL-001234 for Jane Smith (jane@example.com)"
"Cancel booking BK-123456"
"Hold flight FL-005678 for 30 minutes"
```

## 📊 Database Schema

**Flights Table:**
- id, origin, destination, date, airline, price

**Bookings Table:**
- id, user_id, flight_id, passenger_name, passenger_email
- seats, status, created_at, updated_at
- hold_expires_at, cancellation_reason

## 🤝 Contributing

This is a thesis project demonstrating MCP integration with AI applications.

## 📝 License

See LICENSE file for details.

## 👨‍💻 Author

Ilias Antoniou - Thesis Project

## 🔗 Resources

- [Model Context Protocol Documentation](https://modelcontextprotocol.io/)
- [FastMCP Framework](https://github.com/jlowin/fastmcp)
- [Google Gemini API](https://ai.google.dev/)
