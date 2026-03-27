from langchain_neo4j import Neo4jGraph
from neo4j import GraphDatabase
import neo4j

URI = "neo4j+ssc://ea98a3f7.databases.neo4j.io"
PASSWORD = "BH_JCMJl4miigovZk9UUWd3AqPdm8fsrBAd-fgdV--c"

print("1. Connecting raw driver...")
working_driver = GraphDatabase.driver(URI, auth=("neo4j", PASSWORD))
working_driver.verify_connectivity()
print("✅ Raw driver connected!")

print("2. Hijacking LangChain...")
# We use a lambda to intercept LangChain's internal connection attempt 
# and force it to use our pre-verified working driver instead.
neo4j.GraphDatabase.driver = lambda *args, **kwargs: working_driver

print("3. Initializing Neo4jGraph...")
try:
    # We MUST pass the correct database name here
    graph = Neo4jGraph(database="ea98a3f7")
    print("✅ SUCCESS! LangChain is officially connected and bypassed.")
    print("Graph Schema Loaded Successfully!")
except Exception as e:
    print("❌ LANGCHAIN CRASHED DURING SCHEMA LOAD. Error:")
    print(e)