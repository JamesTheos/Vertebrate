from neo4j import GraphDatabase

# Initialize Neo4j driver
driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "ISPEROME"))

# Function to get data from Neo4j
def get_neo4j_data(query):
    with driver.session() as session:  # Open a new session
        result = session.run(query)  # Run the provided query
        return [record for record in result]  # Return the query results as a list of records