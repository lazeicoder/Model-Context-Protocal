import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from langchain_core.messages import HumanMessage
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_groq import ChatGroq
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent


load_dotenv()

# Optional LangSmith tracing setup (safe if env vars are missing).
os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
if os.getenv("LANGCHAIN_PROJECT"):
    os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "")

groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    raise RuntimeError("Missing GROQ_API_KEY in environment (.env).")


SYSTEM_PROMPT = (
    "You are an expert AI Engineer with over 30+ years of experience in the Software and AI Research domain, "
    "with large scale understanding of how AI (different machine learning, deep learning, reinforcement "
    "learning techniques, transformers, agentic ai) systems work, perform, architecture, and how to scale "
    "them for larger client and user base. So based on your experience in the field, provide me with answers."
)


class ChatRequest(BaseModel):
    session_id: str = Field(default="chat_1", min_length=1)
    message: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    session_id: str
    response: str


# In-memory session store (process-local). For production, back this with Redis/DB.
session_store: dict[str, ChatMessageHistory] = {}


def get_session_history(session_id: str) -> BaseChatMessageHistory:
    if session_id not in session_store:
        session_store[session_id] = ChatMessageHistory()
    return session_store[session_id]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start MCP servers and load tool schema once at startup.
    mcp_client = MultiServerMCPClient(
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
            },
        }
    )

    await mcp_client.__aenter__()
    try:
        tools = await mcp_client.get_tools()
        model = ChatGroq(model="llama-3.1-8b-instant", groq_api_key=groq_api_key)

        agent = create_react_agent(model, tools, prompt=SYSTEM_PROMPT)

        app.state.mcp_client = mcp_client
        app.state.agent_with_history = RunnableWithMessageHistory(
            agent,
            get_session_history,
            input_messages_key="messages",
            output_messages_key="messages",
            history_messages_key="messages",
        )
        yield
    finally:
        await mcp_client.__aexit__(None, None, None)


app = FastAPI(title="AIGpt", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"ok": True}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    try:
        result = await app.state.agent_with_history.ainvoke(
            {"messages": [HumanMessage(content=req.message)]},
            config={"configurable": {"session_id": req.session_id}},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    # ReAct agent returns a dict with a "messages" list.
    messages = result.get("messages", [])
    last_content = messages[-1].content if messages else ""
    return ChatResponse(session_id=req.session_id, response=last_content)
