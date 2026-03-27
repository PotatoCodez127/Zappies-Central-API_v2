# /ingestion/ingest.py

import os
import re
import hashlib
import sys
import time
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
load_dotenv()

# --- PUT YOUR TWO API KEYS HERE! ---
API_KEY_1 = "AIzaSyCW5rPy2mHhJWV6PoDmFHO7pJxaYCC7EqY" 
API_KEY_2 = "AIzaSyCVhZO5XHqjU0B0ayHQMYu_jPDzi4e4cjw"
# -----------------------------------

def calculate_checksum(file_path):
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

def get_processed_files_from_db(supabase: Client):
    try:
        response = supabase.table(settings.DB_INGESTION_LOG_TABLE).select("file_path, checksum").execute()
        return {item['file_path']: item['checksum'] for item in response.data}
    except Exception:
        return {}

def normalize_text(text):
    return re.sub(r'\s+', ' ', text).strip()

def standardize_terms(text):
    term_map = {
        r'\bplay park\b': 'IPIC Play',
        r'\bplay area\b': 'IPIC Play',
        r'\bgym\b': 'IPIC Active',
    }
    for old, new in term_map.items():
        text = re.sub(old, new, text, flags=re.IGNORECASE)
    return text

def main():
    print("🚀 Starting knowledge base ingestion pipeline...")

    print("Step 1: Establishing database connections...")
    env_vars_to_kill = ["NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "NEO4J_DATABASE"]
    for var in env_vars_to_kill:
        if var in os.environ:
            del os.environ[var]

    graph = Neo4jGraph(
        url="neo4j+ssc://ea98a3f7.databases.neo4j.io",
        username="ea98a3f7",  
        password="BH_JCMJl4miigovZk9UUWd3AqPdm8fsrBAd-fgdV--c",
        database="ea98a3f7"
    )

    supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

    # Initialize Google's newest embedding model
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/text-embedding-004",
        google_api_key=API_KEY_1
    )

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

    files_requiring_deletion = files_to_delete.union(files_to_update)
    if files_requiring_deletion:
        print(f"\nStep 3: Deleting outdated data for {len(files_requiring_deletion)} file(s)...")
        for file_path in files_requiring_deletion:
            graph.query("MATCH (s:Source {uri: $source_path})-[*0..]-(n) DETACH DELETE s, n", params={"source_path": file_path})
            supabase.table(settings.DB_VECTOR_TABLE).delete().eq("metadata->>source", file_path).execute()
            supabase.table(settings.DB_INGESTION_LOG_TABLE).delete().eq("file_path", file_path).execute()
        print("Deletion complete.")

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

        print("\nStep 5: Generating graph data with DUAL-KEY Batching...")
        
        # --- DUAL-KEY BATCHING LOGIC ---
        midpoint = len(all_chunks) // 2
        chunks_batch_1 = all_chunks[:midpoint]
        chunks_batch_2 = all_chunks[midpoint:]

        graph_documents = []

        # --- BATCH 1 ---
        print(f"\n--- Starting Batch 1 ({len(chunks_batch_1)} chunks) with API Key 1 ---")
        llm_1 = ChatGoogleGenerativeAI(model=settings.GENERATIVE_MODEL, temperature=0, google_api_key=API_KEY_1)
        transformer_1 = LLMGraphTransformer(llm=llm_1, allowed_nodes=settings.GRAPH_ALLOWED_NODES, allowed_relationships=settings.GRAPH_ALLOWED_RELATIONSHIPS, strict_mode=True)
        
        for i, chunk in enumerate(chunks_batch_1):
            print(f"  - Extracting graph from chunk {i+1}/{len(chunks_batch_1)}...")
            try:
                doc = transformer_1.convert_to_graph_documents([chunk])
                graph_documents.extend(doc)
                time.sleep(4) 
            except Exception as e:
                print(f"    Hitting a limit, pausing for 10 seconds... Error: {e}")
                time.sleep(10)

        # --- BATCH 2 ---
        print(f"\n--- Starting Batch 2 ({len(chunks_batch_2)} chunks) with API Key 2 ---")
        llm_2 = ChatGoogleGenerativeAI(model=settings.GENERATIVE_MODEL, temperature=0, google_api_key=API_KEY_2)
        transformer_2 = LLMGraphTransformer(llm=llm_2, allowed_nodes=settings.GRAPH_ALLOWED_NODES, allowed_relationships=settings.GRAPH_ALLOWED_RELATIONSHIPS, strict_mode=True)
        
        for i, chunk in enumerate(chunks_batch_2):
            print(f"  - Extracting graph from chunk {i+1}/{len(chunks_batch_2)}...")
            try:
                doc = transformer_2.convert_to_graph_documents([chunk])
                graph_documents.extend(doc)
                time.sleep(4) 
            except Exception as e:
                print(f"    Hitting a limit, pausing for 10 seconds... Error: {e}")
                time.sleep(10)
        # -------------------------------

        print(f"\nGenerated {len(graph_documents)} total graph documents.")

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

    print("\nStep 6: Updating database ingestion log...")
    for file_path in files_to_process:
        checksum = current_files[file_path]
        supabase.table(settings.DB_INGESTION_LOG_TABLE).upsert({"file_path": file_path, "checksum": checksum}).execute()

    print("\n✅ Ingestion pipeline completed successfully!")

if __name__ == "__main__":
    main()