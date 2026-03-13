# MCProtocol — MCP Servers + FastAPI + Cursor

This directory is a hands-on training project for **MCP (Model Context Protocol)** in Python.

You will learn how to:

- Run **MCP servers** (tool providers) locally.
- Connect to them with an **MCP client** that discovers tools automatically.
- Let an LLM **call those tools** (math + weather) using a ReAct-style agent.
- Serve the whole thing behind a **FastAPI** HTTP API (`/chat`) so it can be used from any frontend (instead of Streamlit).

---

## What problem are we solving right now?

We started with a **Streamlit chat app pipeline** (textbox → call LLM → show answer) and needed to:

1. Move it to a **FastAPI pipeline** (a real backend service).
2. **Integrate MCP servers** so the model can use tools like:
   - `math.add(a, b)`
   - `math.multiply(a, b)`
   - `weather.get_weather(location)`
3. Fix a common confusion:
   - “I ran an MCP server on `localhost:8000` but I don’t see an API in the browser.”

### Why `localhost:8000` “didn’t show the MCP server”

MCP servers are **not REST APIs by default**. Even when an MCP server runs on HTTP (like “streamable HTTP”), it exposes an MCP **protocol endpoint** meant for an MCP client—not a human-friendly web page.

In our final solution, we avoid that confusion by:

- Running MCP servers locally via `stdio` (subprocess transport).
- Exposing a separate, normal HTTP API using **FastAPI**.

---

## Repository structure (this directory)

```
MCProtocol/
├── agent.py                 # FastAPI backend that uses MCP tools via an LLM agent
├── client.py                # Simple script showing MCP client + tool-using agent
├── servers/
│   ├── math_mcp.py           # MCP server exposing math tools (stdio)
│   └── weather_mcp.py        # MCP server exposing a weather tool (stdio)
├── pyproject.toml           # Dependencies managed by uv
├── requirements.txt         # (Optional) requirements-style dependency list
└── learnings.md             # Notes / older documentation
```

---

## Core concepts (MCP) — explained simply

## 1) What is MCP?

**MCP (Model Context Protocol)** is a standard way to expose **tools** (functions) from a server process so that:

- A client can **discover** what tools exist (name, input schema, output schema).
- A client (or an agent framework) can **call** those tools with structured arguments.

Think of MCP as “**tool APIs for LLMs**,” with consistent discovery and invocation behavior across different servers.

---

## 2) MCP server

An **MCP server** is just a Python process that:

- Registers functions as tools (via a decorator).
- Runs a transport to accept tool calls.

In this project we use the **FastMCP** server implementation.

### FastMCP in this repo

Both servers import:

```python
from mcp.server.fastmcp import FastMCP
```

and create a server instance:

```python
mcp = FastMCP(name="math")     # in math_mcp.py
mcp = FastMCP(name="weather")  # in weather_mcp.py
```

The `name=` is important because clients often group tools by server.

---

## 3) Tools

A **tool** is a function decorated with `@mcp.tool()`:

```python
@mcp.tool()
def add(a: int, b: int) -> int:
    return a + b
```

MCP uses the function signature to infer a schema:

- **Tool name**: `add`
- **Arguments**: `{ "a": int, "b": int }`
- **Return type**: `int`

### Tools in this repo

#### Math server tools (`servers/math_mcp.py`)

- `add(a: int, b: int) -> int`
- `subtract(a: int, b: int) -> int`
- `multiply(a: int, b: int) -> int`

#### Weather server tool (`servers/weather_mcp.py`)

- `get_weather(location: str) -> str` (async)

---

## 4) Transports (how the client talks to the server)

An MCP **transport** is the communication channel between the client and the server.

### The transports you’ll encounter

- **`stdio`**:
  - The server runs as a subprocess.
  - The client communicates over the subprocess’ stdin/stdout.
  - Best for local development and Cursor local tools.

- **`streamable-http`** (sometimes used for remote deployment):
  - The server listens on an HTTP endpoint.
  - The client connects via URL.
  - This is MCP protocol over HTTP (not a typical REST API).

### What we chose here (and why)

For the FastAPI integration we use **`stdio`** for both servers so:

- FastAPI can start them reliably on startup.
- No port conflicts.
- No “why doesn’t `localhost:8000` show my tools?” confusion.

---

## 5) MCP client

An MCP **client** connects to one or more MCP servers and can:

- Start local servers (stdio subprocesses)
- Connect to remote servers (HTTP)
- Discover tool metadata
- Invoke tools

In this directory we use:

```python
from langchain_mcp_adapters.client import MultiServerMCPClient
```

### What does `client.get_tools()` do?

It connects to each configured MCP server, asks “what tools do you have?”, and returns a list of tools that agent frameworks can consume.

---

## 6) Why “LLM + MCP tools” needs an agent framework

An LLM by itself only generates text. To actually call tools, you typically use an “agent” loop that:

1. Sends a user message to the model.
2. If the model requests a tool call, run the tool.
3. Feed the tool result back to the model.
4. Repeat until the model returns a final answer.

In this project we use a **ReAct-style agent** from LangGraph:

```python
from langgraph.prebuilt import create_react_agent
```

This agent can:

- Decide when to call `add/multiply/get_weather`
- Format the tool arguments
- Combine tool outputs into a final answer

---

## FastAPI pipeline (what replaced Streamlit)

## 1) Why FastAPI instead of Streamlit

Streamlit is great for quick demos, but FastAPI gives you a proper backend that:

- Can serve multiple clients.
- Has clear endpoints.
- Works well with frontends (React, mobile apps, etc.).
- Can run in production behind a reverse proxy.

---

## 2) `agent.py` architecture (important)

`agent.py` does three major things:

### A) App startup: start MCP servers + load tools (FastAPI lifespan)

On startup, it creates a `MultiServerMCPClient` configured like:

```python
{
  "math": {
    "command": "python",
    "args": ["servers/math_mcp.py"],
    "transport": "stdio",
  },
  "weather": {
    "command": "python",
    "args": ["servers/weather_mcp.py"],
    "transport": "stdio",
  }
}
```

Then it loads tools once:

```python
tools = await mcp_client.get_tools()
```

### B) Build a tool-using agent

It creates an LLM (Groq) and a ReAct agent:

```python
model = ChatGroq(model="llama-3.1-8b-instant", groq_api_key=groq_api_key)
agent = create_react_agent(model, tools, prompt=SYSTEM_PROMPT)
```

### C) Preserve chat history per session_id

Your original Streamlit app used `st.session_state` to keep chat memory.

FastAPI doesn’t have UI session state, so we keep an in-memory dictionary:

```python
session_store: dict[str, ChatMessageHistory] = {}
```

and use:

```python
RunnableWithMessageHistory(...)
```

So each request with the same `session_id` continues the conversation context.

> Note: this memory is **process-local** and will reset when you restart the server. For production, you’d store history in Redis/DB.

---

## API surface (FastAPI)

## 1) Health check

- **GET** `/health`
- Returns: `{ "ok": true }`

## 2) Chat endpoint

- **POST** `/chat`

Request JSON:

```json
{
  "session_id": "chat_1",
  "message": "What is (43 - 12) * (19 + 34)? Use tools."
}
```

Response JSON:

```json
{
  "session_id": "chat_1",
  "response": "..."
}
```

The response is the final model answer after it optionally called MCP tools.

---

## Running the project (recommended with uv)

## 1) Prerequisites

- Python \(>= 3.13\) (as specified in `pyproject.toml`)
- `uv`

## 2) Environment variables

Create `MCProtocol/.env`:

```bash
GROQ_API_KEY="your_groq_key_here"
LANGCHAIN_PROJECT="mcprotocol"   # optional
```

## 3) Install dependencies

From `MCProtocol/`:

```bash
uv sync
```

## 4) Run FastAPI

```bash
uv run uvicorn agent:app --reload --host 127.0.0.1 --port 8000
```

Open interactive docs:

- `http://127.0.0.1:8000/docs`

---

## Testing the API quickly

## 1) Health

```bash
curl http://127.0.0.1:8000/health
```

## 2) Math tool usage

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo","message":"Compute (43 - 12) * (19 + 34). Use tools."}'
```

## 3) Weather tool usage

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo","message":"What is the weather in California? Use the weather tool."}'
```

---

## Using this with Cursor (conceptual guide)

Cursor can act as an MCP host that connects to MCP servers and exposes their tools inside the editor/agent.

In general, Cursor connections look like either:

- **Local stdio server**: Cursor spawns your server command and talks over stdio.
- **Remote streamable HTTP**: Cursor connects to a URL that speaks MCP protocol.

### Important clarification

- Your **FastAPI app** is a normal HTTP server for your product/API (`/chat`).
- Your **MCP servers** are separate tool servers used by the agent.

In this project, **FastAPI is the host** that spawns MCP servers, not Cursor.

If you instead want Cursor to connect directly to the MCP servers (without FastAPI), you can run the servers and configure them in Cursor as MCP servers. That’s a separate “Cursor as host” setup.

---

## Troubleshooting

## 1) “Huge error: `httpx.ConnectError: All connection attempts failed`”

This happens when your MCP client is configured to connect to a URL (HTTP transport), but nothing is listening there.

Example: `http://localhost:8000/mcp` fails if you didn’t start an MCP HTTP server on that port/path.

**Fix**:

- Prefer stdio for local development, or
- Start the HTTP MCP server and ensure URL/path match exactly.

## 2) “Why doesn’t visiting `localhost:8000` show my MCP tools?”

Because MCP-over-HTTP is **not a typical REST API** and usually won’t show a UI page in the browser.

In this project, `localhost:8000` is the **FastAPI** server (docs at `/docs`).

## 3) Session history resets

Expected: session history is stored in RAM. Restarting FastAPI clears it.

---

## Extending this project

## 1) Add a new tool server

Create a new file `servers/my_tools.py`:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="mytools")

@mcp.tool()
def greet(name: str) -> str:
    return f"Hello, {name}!"

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

Register it in the MCP client configuration inside `agent.py`:

```python
"mytools": {
  "command": "python",
  "args": ["servers/my_tools.py"],
  "transport": "stdio",
}
```

Restart FastAPI, and the agent can now call `greet`.

---

## Notes on production hardening (next steps)

- Persist chat history (Redis/DB) instead of in-memory dict.
- Add timeouts / retries for tool calls.
- Add auth for `/chat`.
- Run uvicorn with multiple workers (and externalize session history).
- Make tool servers long-lived services if needed (instead of subprocess).

