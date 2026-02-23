# Zappies-AI Bot Template

This repository contains a production-ready, reusable template for building powerful, data-driven AI agents. It's designed for rapid development and deployment of customized bots for any client, using a Retrieval-Augmented Generation (RAG) architecture with a Knowledge Graph and Vector Store.

## 🚀 Version 2: Key Improvements & Omnichannel Features

This repository (`zappies-central-api_v2`) represents a major evolution from the original text-based chatbot template. It transforms the project into a comprehensive **Omnichannel API** capable of handling synchronous voice agents, SMS notifications, and automated background tasks.

### 1. 🗣️ Voice Agent Integration
The API now supports real-time, synchronous voice interactions (e.g., for Vapi or Bland AI) alongside the standard chat interface.
-   **New Endpoints**:
    -   `POST /get-availability`: Provides optimized, human-readable time slots specifically for voice synthesis (e.g., "10:00 AM" instead of raw ISO dates).
    -   `POST /book-appointment`: Allows immediate, synchronous booking without requiring a confirmation link flow.
    -   `POST /log-call`: Logs details of voice calls that didn't result in a meeting for analytics.
-   **New Schemas**: Added `VoiceBookingRequest` and `CallLogRequest` to handle specific voice agent data structures.

### 2. 📲 SMS Notifications & Reminders (Twilio)
Integrated **Twilio** to reduce no-show rates through multi-channel communication.
-   **Instant Confirmation**: Automatically sends an SMS confirmation ("Hi [Name], your call is confirmed for...") alongside the email invite when a booking occurs.
-   **Automated Reminders**: A new notification system handles the entire reminder lifecycle:
    -   **24-Hour Reminder**: Sent one day before the call.
    -   **Morning-Of Reminder**: Sent at 8:00 AM on the day of the call.
    -   **1-Hour Reminder**: Sent 60 minutes before the meeting starts.

### 3. ⏰ Automated Scheduling & Cron Jobs
The system now includes a dedicated scheduler to handle background tasks.
-   **Scheduler Logic**: `tools/scheduler.py` actively scans the database for upcoming meetings and triggers the appropriate SMS reminders.
-   **Cron Endpoint**: Added a secure `POST /tasks/send-reminders` endpoint. This allows external schedulers (like Railway Cron or Heroku Scheduler) to trigger the reminder script reliably without keeping the server awake 24/7.

### 4. ⚙️ Advanced Business Logic & Cloud Deployment
Refined configuration to support real-world business constraints and easier cloud deployment.
-   **Cloud-Native Credentials**: Replaced file-based `service_account.json` with `GOOGLE_CREDENTIALS_STR` (Base64 encoded), allowing secure credential management via environment variables.
-   **Strict Business Hours**: Added `VOICE_AGENT_CONFIG` settings to strictly enforce operating hours (e.g., 8 AM - 4 PM) and timezone handling (`Africa/Johannesburg`) across all booking tools.
-   **Smart Disqualification**: The booking tool now automatically rejects leads below a defined `MINIMUM_BUDGET` (e.g., R8000), returning a polite disqualification message instead of booking the slot.

### 5. 🛠️ Tech Stack Upgrades
-   **Twilio**: For SMS infrastructure.
-   **APScheduler**: For internal task scheduling logic.
-   **Gunicorn**: Added for robust production server deployment.
-   **LangChain Fixes**: Pinned specific versions to resolve AgentExecutor stability issues.

## ✨ Features

-   **Dynamic RAG Architecture**: Combines a **Neo4j Knowledge Graph** for precise, factual queries (like rules and fees) and a **Supabase Vector Store** for general, contextual information retrieval.
-   **Configuration-Driven**: Onboard new clients by changing configuration files (`.env`, `settings.py`) and adding data—not by rewriting the core logic.
-   **Pluggable Persona**: Easily define and modify the bot's name, personality, and core instructions in a simple text file (`agent/persona.prompt`).
-   **Modular Custom Tools**: Extend the bot's capabilities by adding custom Python functions for business logic (e.g., booking appointments, capturing leads, escalating to support).
-   **Automated Data Ingestion**: A smart script processes client-provided Markdown files, automatically chunks the data, and populates both the graph and vector databases.
-   **Production-Ready API**: Built with **FastAPI**, including API key security, asynchronous processing, and concurrency limiting to handle real-world traffic.
-   **Powered by Google Gemini**: Leverages Google's powerful `gemini-2.5-flash` model for agent reasoning and `embedding-001` for high-quality vector embeddings.

## 🛠️ Tech Stack

-   **Backend**: Python, FastAPI
-   **AI Orchestration**: LangChain
-   **LLM & Embeddings**: Google Gemini
-   **Databases**:
    -   **Neo4j** (Graph Database)
    -   **Supabase** (PostgreSQL with pgvector for Vector Storage)
-   **Deployment**: Uvicorn, Procfile for Heroku/Render

## 📂 Project Structure

The project is organized into modules with a clear separation of concerns, making it easy to maintain and scale.

```
/zappies-ai-bot-template/
|
├── 📂 agent/               # Core AI agent logic and persona
|   ├── 📄 agent_factory.py # Builds the agent executor
|   └── 📄 persona.prompt   # <-- EDIT THIS: Define bot's personality
|
├── 📂 api/                 # FastAPI server and endpoints
|   └── 📄 server.py        # API logic, security, and chat endpoint
|
├── 📂 config/              # Centralized application settings
|   └── 📄 settings.py       # Loads and manages configuration
|
├── 📂 data/                # <-- ADD FILES HERE: Client's knowledge base
|   └── 📄 example.md       # Add your client's markdown files here
|
├── 📂 ingestion/           # Data processing and loading scripts
|   └── 📄 ingest.py         # Script to populate the databases
|
├── 📂 tools/               # Custom capabilities for the bot
|   ├── 📄 action_schemas.py # <-- EDIT THIS: Pydantic models for tool inputs
|   └── 📄 custom_tools.py   # <-- EDIT THIS: Python functions for business logic
|
├── 📄 .env.example        # Template for environment variables
├── 📄 .gitignore
├── 📄 main.py               # Main entry point to run the API
├── 📄 Procfile              # For deployment to services like Heroku
├── 📄 README.md
└── 📄 requirements.txt      # Python dependencies
```

## 🚀 Getting Started: Setup & Installation

Follow these steps to get your first bot running.

### 1. Prerequisites

-   Python 3.9+
-   Access to Google AI Studio, Supabase, and Neo4j (AuraDB is a great cloud option).

### 2. Clone the Repository

```bash
git clone <your-repository-url>
cd zappies-ai-bot-template
```

### 3. Set Up a Virtual Environment

```bash
# For Windows
python -m venv venv
venv\Scripts\activate

# For macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables

1.  Copy the example environment file:
    ```bash
    cp .env.example .env
    ```
2.  Open the `.env` file and fill in the credentials for your services:
    -   `API_SECRET_KEY`: A strong, random key you create to protect your API.
    -   `GOOGLE_API_KEY`: Your API key from Google AI Studio.
    -   `SUPABASE_URL` & `SUPABASE_SERVICE_KEY`: From your Supabase project's API settings.
    -   `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`: From your Neo4j database instance.

## ⚙️ How to Use: Onboarding a New Client

This is the standard workflow for configuring the template for a new client.

### Step 1: Add Knowledge Data

-   Delete the `example.md` file inside the `/data/` directory.
-   Add all of your client's knowledge base documents as **Markdown (`.md`) files** inside the `/data/` directory.

### Step 2: Run the Data Ingestion Script

This script will read your Markdown files, process them, and load them into your Supabase and Neo4j databases.

-   From the root of the project, run:
    ```bash
    python -m ingestion.ingest
    ```
-   The script will track file changes, so you only need to run it again when you add, update, or remove knowledge files.

### Step 3: Customize the Bot's Persona

-   Open `agent/persona.prompt`.
-   Edit the bot's name, personality description, and any special rules to match your client's brand voice.

### Step 4: Define Custom Tools & Actions

-   **Define Inputs**: Open `tools/action_schemas.py`. Create or modify the Pydantic classes to define the arguments for your bot's custom actions (e.g., collecting a name, email, and reason for contact).
-   **Implement Logic**: Open `tools/custom_tools.py`. Write the Python functions that perform the actions. This is where you would integrate with a client's CRM, calendar API, or other external systems. The template includes examples for lead capture and escalation.

### Step 5: Run the API Server

-   Start the application from the root directory:
    ```bash
    python main.py
    ```
-   The API server will start, typically on `http://127.0.0.1:8000`.

## 🔌 API Usage

Interact with your running bot by sending POST requests to the `/chat` endpoint.

-   **Endpoint**: `POST /chat`
-   **Headers**:
    -   `Content-Type: application/json`
    -   `x-api-key: YOUR_API_SECRET_KEY` (The one you set in your `.env` file)
-   **Request Body**:

    ```json
    {
      "conversation_id": "a_unique_id_for_the_user_session",
      "query": "What are your operating hours?"
    }
    ```

-   **Success Response (200 OK)**:

    ```json
    {
      "response": "The bot's generated answer will be here."
    }
    ```

## 💾 Database

You need to have a Supabase Account and Project to store all the data. Run the below SQL snippet to create the tables and schema needed for the project.

```sql
-- Create the table to store your document chunks and their embeddings
DROP TABLE IF EXISTS public.documents;
create table documents (
  id uuid primary key,
  content text, -- Stores the actual text
  metadata jsonb, -- Stores metadata like file names or sources
  embedding vector(768) -- Stores the vector embedding. The dimension is 768 for Google's "embedding-001" model.
);

-- Create a function to perform similarity searches on your documents
create or replace function match_documents (
  query_embedding vector(768),
  match_count int,
  filter jsonb
) returns table (
  id uuid,
  content text,
  metadata jsonb,
  similarity float
)
language plpgsql
as $$
begin
  return query
  select
    documents.id,
    documents.content,
    documents.metadata,
    1 - (documents.embedding <=> query_embedding) as similarity
  from documents
  where documents.metadata @> filter -- Explicitly specify the table here too
  order by documents.embedding <=> query_embedding
  limit match_count;
end;
$$;

DROP TABLE IF EXISTS public.ingestion_log;
-- Create a table to log which files have been processed
create table ingestion_log (
  -- The path of the file that was ingested
  file_path text primary key,

  -- A checksum of the file to detect if it has changed
  checksum text,

  -- A timestamp to know when it was last ingested
  last_ingested_at timestamptz default now()
);


-- 1. Drop the old, incorrect table to avoid conflicts
DROP TABLE IF EXISTS public.conversation_history;

-- 2. Re-create the table with the correct structure
-- This version sets `conversation_id` as the PRIMARY KEY.
-- This is the crucial change that makes `upsert` work as intended.
CREATE TABLE public.conversation_history (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    conversation_id TEXT NOT NULL PRIMARY KEY, -- Set as the unique Primary Key
    history JSONB NULL
);
-- Add a 'status' column to track if a conversation is active or handed over
ALTER TABLE public.conversation_history
ADD COLUMN status TEXT NOT NULL DEFAULT 'active';

-- Optional: Create an index on the status for faster lookups
CREATE INDEX idx_conversation_status ON public.conversation_history (status);

-- 3. Enable Row Level Security (RLS) - Best Practice
-- ALTER TABLE public.conversation_history ENABLE ROW LEVEL SECURITY;

-- Create a table to store and manage all booked appointments
CREATE TABLE public.meetings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    google_calendar_event_id TEXT,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL,
    company_name TEXT,
    start_time TIMESTAMPTZ NOT NULL,
    goal TEXT,
    monthly_budget REAL,
    status TEXT NOT NULL DEFAULT 'booked', -- e.g., 'booked', 'confirmed', 'cancelled'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Optional: Create an index on the email and start_time for faster lookups
CREATE INDEX idx_meetings_email_start_time ON public.meetings (email, start_time);
```

## ☁️ Deployment

The included `Procfile` is configured for easy deployment on platforms like Heroku or Render.

```
web: uvicorn api.server:app --host 0.0.0.0 --port $PORT
```

## 📄 License

This project is licensed under the MIT License. See the `LICENSE` file for details.
