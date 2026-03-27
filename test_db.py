import os
from langchain_neo4j import Neo4jGraph

print("1. Nuking environment variables...")
# If LangChain is secretly reading your .env file, this stops it dead.
env_vars_to_kill = ["NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "NEO4J_DATABASE"]
for var in env_vars_to_kill:
    if var in os.environ:
        del os.environ[var]
        print(f"   - Deleted hidden {var} from memory")

# Hardcode the golden credentials
URI = "neo4j+ssc://ea98a3f7.databases.neo4j.io"
USERNAME = "ea98a3f7"
PASSWORD = "BH_JCMJl4miigovZk9UUWd3AqPdm8fsrBAd-fgdV--c"

print(f"\n2. Password check: Your password is exactly {len(PASSWORD)} characters long.")

print("\n3. Attempting pure LangChain connection...")
try:
    graph = Neo4jGraph(
        url=URI,
        username=USERNAME,
        password=PASSWORD,
        database="ea98a3f7"
    )
    print("✅ SUCCESS! LangChain connected perfectly.")
    print("\nCONCLUSION: LangChain was secretly reading a broken .env file behind our backs!")
except Exception as e:
    print("❌ FAILED. The error is:")
    print(e)