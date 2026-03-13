# MCProtocol (MCP) Examples and Documentation

> **Note:** This repository demonstrates how to build, connect, and run **MCP (Multi-Channel Protocol)** servers and clients in Python, then use them through an LLM agent to solve real-world tasks (like searching job listings via Dice).

---

## 📌 What is MCP?

*MCP* stands for **Multi-Channel Protocol** (also called **Multi-Channel Process**). It is a lightweight framework that enables you to define **tool APIs** as standalone services.

### Key Concepts

- **MCP Server**: A process that exposes *tools* (functions) and listens on a transport channel (e.g., `stdio`, `http`).
- **Tools**: Python functions registered with `@mcp.tool()` that can be invoked remotely.
- **Transport**: The communication channel used to talk to the MCP server. Common transports are:
  - `stdio` (standard input/output) for local subprocess communication
  - `http` for remote services
- **Client**: A component that connects to one or more MCP servers, discovers available tools, and calls them.

### Why MCP?

MCP makes it easy to:

- Build **modular tool services** that can be independently developed and deployed.
- Connect multiple tools into a **single agent workflow**.
- Use an **LLM agent** to dynamically decide which tool(s) to call based on natural language.

---

## 🧠 What problem are we solving in this repo?

This repository demonstrates a full workflow where an LLM-powered agent:

1. **Starts and manages** multiple MCP servers (local and remote).
2. **Discovers tools** exposed by those servers.
3. **Decides which tool to call** based on a user prompt.
4. **Aggregates, filters, and formats** the tool output into a useful response.

### The current “real-world” problem we solve

The example in this repository uses a remote MCP endpoint (Dice.com job search) to:

- **Search job listings** based on a user prompt (e.g., “Find junior software developer roles”).
- **Retrieve raw job data** (title, company, location, description, etc.).
- **Format** the job data into a clean, structured job posting.

This shows how a language model can orchestrate: (a) a remote API call through MCP, and (b) a “post-processing” step to clean and format results.

---

## 📁 Repository Structure

```
MCProtocol/
├── agent.py           # (Optional) agent wrapper / utilities (if present)
├── client.py          # Main example client that runs tools via an LLM agent
├── main.py            # (Optional) example entrypoint
├── requirements.txt   # Python dependencies
├── servers/           # MCP servers (local tool servers)
│   ├── math_mcp.py    # Simple math tool server
│   └── weather_mcp.py # Simple weather tool server
├── pyproject.toml     # Project metadata for Poetry (if used)
└── README.md          # This documentation file
```

---

## 🧩 MCP Server Concepts (Deep Dive)

### 🧱 What is an MCP “tool”?

A tool is a Python function decorated with `@mcp.tool()`.

Example:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="math")

@mcp.tool()
def add(a: int, b: int) -> int:
    return a + b
```

When the server runs, MCP automatically exposes:

- Tool name: `add`
- Input schema: `{ "a": int, "b": int }`
- Output schema: `int`

This metadata is used by an LLM agent (e.g., LangChain) to decide which tool to call and how to format the arguments.

### 🔌 What is a Transport?

A transport defines how the client and server talk to each other.

| Transport | Usage | Notes |
|----------|-------|-------|
| `stdio`  | Local subprocess | Best for running tools on the same machine (most common in examples) |
| `http`   | Remote MCP server | Used for remote services (e.g., Dice job search) |

Example (local math server):

```python
mcp.run(transport="stdio")
```

Example (remote):

```python
"my-mcp-server": {
  "url": "https://mcp.dice.com/mcp",
  "transport": "http"
}
```

### 🧠 How does the agent know which tools exist?

The MCP client exposes a *tool metadata list* that includes:

- Tool name
- Description (if provided)
- Argument schema (`args_schema`)

In `client.py`, we call:

```python
tools = await client.get_tools()
```

Then we pass `tools` into `create_agent(...)`, and the language model uses the schemas to decide how to call each tool.

---

## 📘 Code Walkthrough — Local MCP Servers

### ✅ `servers/math_mcp.py` (math tools)

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="math")

@mcp.tool()
def add(a: int, b: int) -> int:
    return a + b

@mcp.tool()
def subtract(a: int, b: int) -> int:
    return a - b

@mcp.tool()
def multiply(a: int, b: int) -> int:
    return a * b

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

✅ **What this gives us:**
- A tool named `add` that can be called with `{ "a": 3, "b": 5 }`.
- A tool named `multiply` that can be called with `{ "a": 4, "b": 7 }`.

### ✅ `servers/weather_mcp.py` (weather tool)

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="weather")

@mcp.tool()
async def get_weather(location: str) -> str:
    return f"The weather in {location} is sunny."

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

✅ **What this gives us:**
- An async tool `get_weather` that accepts `{ "location": "Bangalore" }` and returns a string.

---

## 🧩 Code Walkthrough — Agent + Tool Orchestration (`client.py`)

`client.py` is the orchestration entrypoint that:

1. Starts local MCP servers.
2. Connects to a remote MCP server.
3. Builds an LLM agent that can call any exposed tool.
4. Sends a prompt to the agent to search for job listings.
5. Formats the returned job data into a clean job description.

### Key pieces in `client.py`

#### 1) MultiServerMCPClient configuration

```python
client = MultiServerMCPClient(
    {
        "math": {
            "command": "python",
            "args": ["servers/math_mcp.py"],
            "transport": "stdio",
        },
        "postgres": {
            "command": "uv",
            "args": [
                "run",
                "postgres-mcp",
                "--access-mode=unrestricted"
            ],
            "env": {
                "DATABASE_URI": "postgresql://agentic:Anurag2004@localhost:5432/blog"
            },
            "transport": "stdio"
        },
        "my-mcp-server-96a35bfe": {
            "url": "https://mcp.dice.com/mcp",
            "transport": "http"
        }
    }
)
```

**What this does:**
- Starts a local Python subprocess for `math_mcp.py`.
- Starts a subprocess (via `uv run postgres-mcp`) for a Postgres-related MCP server.
- Connects to a remote, publicly accessible MCP service at `https://mcp.dice.com/mcp`.

#### 2) Retrieve tools and build the agent

```python
tools = await client.get_tools()
model = ChatGroq(model="openai/gpt-oss-20b")
agent = create_agent(model, tools, checkpointer=InMemorySaver())
```

- `client.get_tools()` returns a list of tool metadata objects that the agent uses.
- `ChatGroq` is the ground-truth LLM model used to interpret the prompt and choose tools.
- `create_agent(...)` wraps everything into a tool-using agent.

> 💡 Tip: You can inspect the tool metadata by uncommenting the loop in `client.py`:
>
> ```python
> for t in tools:
>     print(t.name)
>     print(t.description)
>     print(t.args_schema)
> ```

#### 3) Sending a prompt to the agent

The agent expects a message history (system + user). In this repository, the call looks like this:

```python
user_prompt = "Find junior software developer roles"

job_description_search = await agent.ainvoke(
    {
        "messages": [
            SystemMessage(content="From the list of Jobs, ask the user which job post you should take, and return all details of it properly in json format."),
            HumanMessage(content=user_prompt)
        ]
    },
    config=config
)

job_search_result = job_description_search["messages"][-1].content
```

- The agent decides which tool to call based on the prompt.
- The tool output becomes part of the agent’s response history.

#### 4) Formatting the job data (prompt engineering)

After the agent returns raw job data, the code runs a second agent call to clean and format it:

```python
system_prompt = """
You are an expert technical recruiter and job description writer.
...
"""

job_response = await agent.ainvoke(
    {
        "messages": [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Generate the JD for this Job post: {job_search_result}")
        ]
    },
    config=config
)

print("Job Description Response:\n", job_response['messages'][-1].content)
```

This shows a common pattern:

1. Use the tool to fetch raw data.
2. Use the agent to post-process and present it in a structured, human-readable form.

---

## 🔧 Configuration & Environment Variables

This repo uses environment variables to manage secrets / API keys.

- `GROQ_API_KEY`: required by `langchain_groq` (the model backend used in `client.py`).

To set it up, create a `.env` file in the repo root or set it in your shell:

```bash
export GROQ_API_KEY="your_api_key_here"
```

Then run:

```bash
source .venv/bin/activate
python3 client.py
```

> ⚠️ If you don’t have a `.venv`, create one with:
>
> ```bash
> python3 -m venv .venv
> source .venv/bin/activate
> pip install -r requirements.txt
> ```

---

## 🧩 How the Dice Job Search Tool Works (Deep Dive)

### The remote MCP endpoint

`https://mcp.dice.com/mcp` is a remote MCP server that exposes job search capabilities via one or more tools.

It is registered in `client.py` like this:

```python
"my-mcp-server-96a35bfe": {
    "url": "https://mcp.dice.com/mcp",
    "transport": "http"
}
```

The LangChain MCP adapter treats it just like a local tool server—when the agent wants to run one of its tools, it sends a structured request to the remote endpoint and receives a JSON response.

### What tool names look like

The tool names are derived from the MCP server’s exposed functions. For example, the Dice MCP server likely exposes a tool such as:

- `search_jobs` (or similar)

When you run `tools = await client.get_tools()`, you can see the exact names.

### What the agent does with the job data

1. The agent invokes the job search tool with an argument like:

```json
{ "keyword": "Junior AI Engineer", "location": "Bangalore" }
```

2. The tool returns a structured response (array of job objects), like:

```json
{
  "data": [
    {
      "title": "AI Test Engineer",
      "companyName": "Dice API Test",
      "jobLocation": { "displayName": "Bengaluru, Karnataka, India" },
      ...
    }
  ]
}
```

3. The agent uses prompt logic (system + user messages) to decide which job(s) to show, and in what format.

---

## ✅ Extending This Repository (Add Your Own MCP Server)

### 1) Create a new server in `servers/`

Example: `servers/math2_mcp.py`

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="math2")

@mcp.tool()
def divide(a: int, b: int) -> float:
    return a / b

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

### 2) Register it in `client.py`

```python
"math2": {
    "command": "python",
    "args": ["servers/math2_mcp.py"],
    "transport": "stdio",
},
```

### 3) Use it via the agent prompt

Now the agent can call the `divide` tool automatically when the user asks something like:

> “What is 42 divided by 7?”

---

## 🧩 Debugging Tips

### ✅ See which tools are available

Uncomment the inspection section in `client.py`:

```python
for t in tools:
    print(t.name)
    print(t.description)
    print(t.args_schema)
```

This tells you exactly what tool names and arguments the agent can use.

### ✅ Logging the agent’s tool calls

The agent logs tool calls through its message history. In `client.py`, you can print the full message list to see what it decided to do.

---

## 📌 Next Steps (Suggested Improvements)

- Add a `servers/jobs_mcp.py` that wraps the Dice job search API directly, giving you full control over query parameters and output formatting.
- Add unit/integration tests validating tool outputs and the agent’s decision-making.
- Add documentation for how to interpret the MCP tool metadata (`args_schema`, tool `name`, etc.).
- Add a small CLI that lets you run the agent with different prompt templates and tools.

---

## ✅ Summary

This repo is a **minimal but complete example** of using MCP servers + an LLM agent to:

- **Expose tools** as standalone services.
- **Discover and orchestrate** tools from a single agent.
- **Solve a real task** (searching job listings and formatting results).

Key concepts:

- **MCP server** = a process exposing tool functions.
- **MCP client** = a controller that starts servers + calls tools.
- **Agent integration** = a language model that can orchestrate tools based on natural language prompts.

Happy experimenting! 🎉
