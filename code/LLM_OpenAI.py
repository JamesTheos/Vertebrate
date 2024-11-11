import openai

# Initialize OpenAI API
openai.api_key = 'your_openai_api_key'  # Set your OpenAI API key

# Function to query the LLM
def query_llm(prompt):
    response = openai.Completion.create(
        engine="text-davinci-003",  # Specify the LLM engine
        prompt=prompt,  # Provide the prompt to the LLM
        max_tokens=150  # Set the maximum number of tokens in the response
    )
    return response.choices[0].text.strip()  # Return the response text