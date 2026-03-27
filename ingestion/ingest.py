# /ingestion/ingest.py

import os
import re
import hashlib
import sys
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader, UnstructuredMarkdownLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_neo4j import Neo4jGraph
from langchain_community.vectorstores import SupabaseVectorStore
from supabase.client import Client, create_client
from langchain_core.documents import Document

# Add the project root directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings

# Load environment variables from the root .env file
load_dotenv()

# --- Helper and Pre-processing Functions ---

def calculate_checksum(file_path):
    """Calculates the SHA256 checksum of a file."""
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

def get_processed_files_from_db(supabase: Client):
    """Retrieves a log of already processed files from Supabase."""
    try:
        response = supabase.table(settings.DB_INGESTION_LOG_TABLE).select("file_path, checksum").execute()
        return {item['file_path']: item['checksum'] for item in response.data}
    except Exception:
        return {}

def normalize_text(text):
    """Removes extra whitespace from text."""
    return re.sub(r'\s+', ' ', text).strip()

def standardize_terms(text):
    """Standardizes specific business terms for consistency."""
    # This can be customized for each client
    term_map = {
        r'\bplay park\b': 'IPIC Play',
        r'\bplay area\b': 'IPIC Play',
        r'\bgym\b': 'IPIC Active',
    }
    for old, new in term_map.items():
        text = re.sub(old, new, text, flags=re.IGNORECASE)
    return text

def main():
    """
    Main ingestion pipeline to process and load data into the knowledge base.
    """
    print("🚀 Starting knowledge base ingestion pipeline...")

    # --- 1. Establish Connections ---
    print("Step 1: Establishing database connections...")
    #==============================================================================================



    # --- SLEDGEHAMMER FIX ---
    # 1. Nuke the broken environment variables so LangChain can't use them  
    import os
    env_vars_to_kill = ["NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "NEO4J_DATABASE"]
    for var in env_vars_to_kill:
        if var in os.environ:
            del os.environ[var]

    # 2. Connect with the 100% verified credentials
    graph = Neo4jGraph(
        url="neo4j+ssc://ea98a3f7.databases.neo4j.io",
        username="ea98a3f7",  # <-- The missing link we finally found!
        password="BH_JCMJl4miigovZk9UUWd3AqPdm8fsrBAd-fgdV--c",
        database="ea98a3f7"
    )
    # ------------------------


    #==============================================================================================
    supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    #================================================================================================
    # --- ADD THIS LINE TO FORCE THE GOOGLE API KEY ---
    os.environ["GOOGLE_API_KEY"] = "AIzaSyBsY8VVzS5_svLkdXGKDJgpmUa72c1CsAg"

    # --- UPDATE THIS BLOCK ---
    graph_generation_llm = ChatGoogleGenerativeAI(
        model=settings.GENERATIVE_MODEL, 
        temperature=0,
        google_api_key=os.environ["GOOGLE_API_KEY"]  # <-- Force it to read the key
    )


    #================================================================================================
    # Initialize Google's newest embedding model
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/text-embedding-004", # <-- This is the crucial update!
        google_api_key=os.environ["GOOGLE_API_KEY"]
    )

    # --- 2. Check for File Changes ---
    print("\nStep 2: Checking for new, updated, or deleted files...")
    processed_log = get_processed_files_from_db(supabase)
    source_path = settings.SOURCE_DIRECTORY_PATH
    current_files = {
        os.path.join(source_path, f): calculate_checksum(os.path.join(source_path, f))
        for f in os.listdir(source_path)
        if os.path.isfile(os.path.join(source_path, f)) and (f.endswith(".pdf") or f.endswith(".md"))
    }

    files_to_add = {f for f in current_files if f not in processed_log}
    files_to_delete = {f for f in processed_log if f not in current_files}
    files_to_update = {f for f in current_files if f in processed_log and current_files[f] != processed_log[f]}

    if not files_to_add and not files_to_delete and not files_to_update:
        print("✅ Knowledge base is already up-to-date.")
        return

    # --- 3. Handle Deletions and Updates ---
    files_requiring_deletion = files_to_delete.union(files_to_update)
    if files_requiring_deletion:
        print(f"\nStep 3: Deleting outdated data for {len(files_requiring_deletion)} file(s)...")
        for file_path in files_requiring_deletion:
            # Delete from Neo4j
            graph.query("MATCH (s:Source {uri: $source_path})-[*0..]-(n) DETACH DELETE s, n", params={"source_path": file_path})
            # Delete from Supabase Vector Store
            supabase.table(settings.DB_VECTOR_TABLE).delete().eq("metadata->>source", file_path).execute()
            # Delete from Ingestion Log
            supabase.table(settings.DB_INGESTION_LOG_TABLE).delete().eq("file_path", file_path).execute()
        print("Deletion complete.")

    # --- 4. Process and Add New/Updated Files ---
    files_to_process = files_to_add.union(files_to_update)
    if files_to_process:
        print(f"\nStep 4: Processing {len(files_to_process)} new or updated file(s)...")
        all_chunks = []
        for file_path in files_to_process:
            print(f"  - Processing: {file_path}")
            
            if file_path.endswith(".pdf"):
                loader = PyPDFLoader(file_path)
            elif file_path.endswith(".md"):
                loader = UnstructuredMarkdownLoader(file_path)
            
            documents = loader.load()

            # Use RecursiveCharacterTextSplitter for chunking
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=2000,
                chunk_overlap=200
            )
            chunks = text_splitter.split_documents(documents)

            for chunk in chunks:
                chunk.page_content = normalize_text(standardize_terms(chunk.page_content))
                chunk.metadata["source"] = file_path
            all_chunks.extend(chunks)

        print(f"Created {len(all_chunks)} document chunks from files.")

        # --- 5. Generate Graph and Vector Embeddings ---
        print("\nStep 5: Generating graph data and vector embeddings...")
        llm_transformer = LLMGraphTransformer(
            llm=graph_generation_llm,
            allowed_nodes=settings.GRAPH_ALLOWED_NODES,
            allowed_relationships=settings.GRAPH_ALLOWED_RELATIONSHIPS,
            strict_mode=True
        )

        # --- SPEED BUMP FIX FOR FREE TIER ---
        import time
        graph_documents = []
        print(f"Processing {len(all_chunks)} chunks slowly to respect Google's free API limits...")
        
        for i, chunk in enumerate(all_chunks):
            print(f"  - Extracting graph from chunk {i+1}/{len(all_chunks)}...")
            try:
                # Process one chunk at a time
                doc = llm_transformer.convert_to_graph_documents([chunk])
                graph_documents.extend(doc)
                # Sleep for 4 seconds to stay well under the 15 requests/minute limit
                time.sleep(4) 
            except Exception as e:
                print(f"    Hitting a limit, pausing for 10 seconds... Error: {e}")
                time.sleep(10)
        # ------------------------------------

        
        print(f"Generated {len(graph_documents)} graph documents.")

        if graph_documents:
            graph.add_graph_documents(graph_documents, baseEntityLabel=True, include_source=True)

        if all_chunks:
            SupabaseVectorStore.from_documents(
                documents=all_chunks,
                embedding=embeddings,
                client=supabase,
                table_name=settings.DB_VECTOR_TABLE,
                query_name=settings.DB_VECTOR_QUERY_NAME
            )
        print("Embeddings and graph data stored successfully.")

    # --- 6. Update Ingestion Log ---
    print("\nStep 6: Updating database ingestion log...")
    for file_path in files_to_process:
        checksum = current_files[file_path]
        supabase.table(settings.DB_INGESTION_LOG_TABLE).upsert({"file_path": file_path, "checksum": checksum}).execute()

    print("\n✅ Ingestion pipeline completed successfully!")

if __name__ == "__main__":
    main()