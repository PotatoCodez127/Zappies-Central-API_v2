from langchain_neo4j import Neo4jGraph

URI = "neo4j+ssc://ea98a3f7.databases.neo4j.io"
USERNAME = "neo4j"
PASSWORD = "BH_JCMJl4miigovZk9UUWd3AqPdm8fsrBAd-fgdV--c"

print("Testing LangChain connection...")
try:
    # Notice we are setting database=None to let it auto-detect
    graph = Neo4jGraph(
        url=URI,
        username=USERNAME,
        password=PASSWORD,
        database=None 
    )
    print("✅ SUCCESS! LangChain connected to the database.")
    print("Schema:", graph.schema)
except Exception as e:
    print("❌ LANGCHAIN FAILED. Error:")
    print(e)