from flask import Flask, request, jsonify

# Initialize Flask application
app = Flask(__name__)

# Define endpoint to handle user questions
@app.route('/ask', methods=['POST'])
def ask():
    user_input = request.json['question']  # Get the user's question from the request
    
    # Fetch data from Kafka
    kafka_data = get_kafka_data()
    
    # Fetch data from Neo4j
    neo4j_query = "MATCH (n) RETURN n LIMIT 5"  # Example query to fetch data from Neo4j
    neo4j_data = get_neo4j_data(neo4j_query)
    
    # Prepare prompt for LLM
    prompt = f"User asked: {user_input}\nKafka data: {kafka_data}\nNeo4j data: {neo4j_data}\nAnswer:"
    
    # Get response from LLM
    response = query_llm(prompt)
    
    return jsonify({'response': response})  # Return the LLM's response as JSON

# Run the Flask application
if __name__ == '__main__':
    app.run(debug=True)