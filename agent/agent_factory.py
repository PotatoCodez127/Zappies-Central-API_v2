# agent/agent_factory.py
import logging
import sys
from typing import Any
import uuid
import json 

# LangChain Imports FORCE REDEPLOY
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain_community.vectorstores import SupabaseVectorStore
from langchain_core.documents import Document
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.tools import Tool, render_text_description
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_neo4j import GraphCypherQAChain, Neo4jGraph
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI

# Local Imports
from config.settings import settings
from tools.custom_tools import get_custom_tools
from supabase.client import Client, create_client

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

class ToolCallbackHandler(BaseCallbackHandler):
    """Callback handler to store tool calls in the correct, structured format."""
    def __init__(self):
        self.tool_calls = []

    def on_agent_action(self, action, **kwargs: Any) -> Any:
        """Run when agent takes an action and capture the full tool call details."""
        if action.tool:
            tool_input = action.tool_input
            # --- THIS IS THE FIX ---
            # Ensure the tool arguments are always a dictionary
            if isinstance(tool_input, str):
                try:
                    # If it's a JSON string, parse it into a dict
                    args = json.loads(tool_input)
                except json.JSONDecodeError:
                    # If it's a regular string, wrap it in a dict
                    args = {"query": tool_input}
            else:
                # If it's already a dict, use it as is
                args = tool_input

            self.tool_calls.append(
                {
                    "name": action.tool,
                    "args": args, # Use the processed 'args' dictionary
                    "id": str(uuid.uuid4())
                }
            )

def create_agent_executor(memory, conversation_id: str):
    """Builds and returns the complete AI agent executor."""
    logger.info("🚀 Creating new agent executor instance...")
    # if not settings.GOOGLE_API_KEY:
    #      logger.error("GOOGLE_API_KEY not found in settings.")
    #      raise ValueError("Google API Key is not configured.")

    # ======================TESTING=================================
    # llm = ChatGoogleGenerativeAI(
    #     model=settings.GENERATIVE_MODEL,
    #     temperature=settings.AGENT_TEMPERATURE,
    #     google_api_key=settings.GOOGLE_API_KEY, # Explicitly pass the key
    #     convert_system_message_to_human=True
    # )
    # ======================TESTING=================================

    # --- OLLAMA CLOUD LLM (TESTING) ---
    from langchain_community.chat_models import ChatOllama
    import os

    llm = ChatOllama(
        model="gpt-oss:20b-cloud",           # The 20-billion parameter cloud model
        base_url="https://ollama.com",       # Point to the cloud instead of localhost
        headers={"Authorization": f"Bearer {os.environ.get('OLLAMA_API_KEY')}"}, # Secure Auth
        temperature=0.1
    )
    # ----------------------------------

    # --- Tool Setup ---
    graph = Neo4jGraph(
        url="neo4j+ssc://ea98a3f7.databases.neo4j.io",
        username="ea98a3f7",
        password="BH_JCMJl4miigovZk9UUWd3AqPdm8fsrBAd-fgdV--c",
        database="ea98a3f7"  # <-- This is what the bot was missing!
    )
    graph.refresh_schema()

    graph_chain = GraphCypherQAChain.from_llm(
        llm,
        graph=graph,
        verbose=True,
        allow_dangerous_requests=True
    )
    graph_tool = Tool(
        name="Knowledge_Graph_Search",
        func=graph_chain.invoke,
        description="Use for specific questions about rules, policies, costs, and fees."
    )

    supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    embeddings = HuggingFaceEmbeddings(
     model_name="sentence-transformers/all-mpnet-base-v2"
    )
    
    def run_vector_search(query: str, k: int = 4) -> list[Document]:
        """Performs a similarity search on the Supabase vector store."""
        logger.info(f"--- ACTION: Performing vector search for query: '{query}' ---")
        query_embedding = embeddings.embed_query(query)
        
        response = supabase.rpc(settings.DB_VECTOR_QUERY_NAME, {
            'query_embedding': query_embedding,
            'match_count': k,
            'filter': {}
        }).execute()

        match_result = [
            Document(
                page_content=doc["content"],
                metadata=doc["metadata"],
            )
            for doc in response.data
        ]
        return match_result

    vector_tool = Tool(
        name="General_Information_Search",
        func=run_vector_search,
        description="Use for general, conceptual, or 'how-to' questions."
    )
    
    custom_tools = get_custom_tools()
    all_tools = [graph_tool, vector_tool] + custom_tools
    logger.info(f"🛠️  Loaded tools: {[tool.name for tool in all_tools]}")

    # --- Prompt Setup ---
    with open("agent/persona.prompt", "r") as f:
        persona_template = f.read()

    prompt = PromptTemplate.from_template(persona_template)

    # --- Agent and Executor Construction ---
    agent_runnable = create_react_agent(llm, all_tools, prompt)
    
    tool_callback = ToolCallbackHandler()
    
    agent_executor = AgentExecutor(
        agent=agent_runnable,
        tools=all_tools,
        memory=memory,
        verbose=True,
        handle_parsing_errors="I made a formatting error. I will correct it and try again.",
        max_iterations=settings.AGENT_MAX_ITERATIONS,
        callbacks=[tool_callback]
    )
    
    logger.info(f"📦 Returning AgentExecutor instance and callback: {type(agent_executor)}")
    return agent_executor, tool_callback
