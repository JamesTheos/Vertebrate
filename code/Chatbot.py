from flask import Blueprint,Flask, request, jsonify
#from huggingface_hub import login
from LLM_Consumer import get_kafka_data
from Neo4j import get_neo4j_data
# Load model directly # Use a pipeline as a high-level helper
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
import os
import torch

# Create a blueprint
Chatbot = Blueprint('Chatbot', __name__)

# Load the token from the environment variable
token = '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'

# Load LLaMA model and tokenizer
# Use the token to authenticate with the Hugging Face API
model_name = "meta-llama/Llama-3.2-1B"
tokenizer = AutoTokenizer.from_pretrained(model_name, use_auth_token=token)
model = AutoModelForCausalLM.from_pretrained(model_name, use_auth_token=token)

pipe = pipeline("text-generation", model="meta-llama/Llama-3.2-1B")

def query_llama(prompt):
    inputs = tokenizer(prompt, return_tensors="pt")
    outputs = model.generate(**inputs, max_length=150)
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return response

# Define endpoint to handle user questions
@Chatbot.route('/ask', methods=['POST'])
def ask():
    user_input = request.json['question']  # Get the user's question from the request
    
    # Fetch data from Kafka
    kafka_data = get_kafka_data()
    
    # Fetch data from Neo4j
    neo4j_query = "MATCH (n) RETURN n LIMIT 5"  # Example query to fetch data from Neo4j
    neo4j_data = get_neo4j_data(neo4j_query)
    
    # Prepare prompt for LLaMA
    prompt = f"User asked: {user_input}\nKafka data: {kafka_data}\nNeo4j data: {neo4j_data}\nAnswer:"
    
    # Get response from LLaMA
    response = query_llama(prompt)
    
    return jsonify({'response': response})  # Return the LLaMA's response as JSON
