from flask import Flask, render_template, request
import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from transformers import AutoTokenizer, AutoModel
from langchain.prompts.chat import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import AzureChatOpenAI
import torch

app = Flask(__name__)

# Load environment variables
load_dotenv()
qdrant_host = os.getenv('QDRANT_HOST', '192.168.1.36')
qdrant_port = int(os.getenv('QDRANT_PORT', 6333))
qdrant_collection = os.getenv('QDRANT_COLLECTION', 'Master_Metadata')
qdrant_client = QdrantClient(host=qdrant_host, port=qdrant_port)

# Initialize embedding model (BGE-small)
tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-small-en")
model = AutoModel.from_pretrained("BAAI/bge-small-en")

# Initialize Azure OpenAI LLM
llm = AzureChatOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
    openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview"),
    temperature=0.1,
    max_tokens=400
)

# Function to generate embeddings using the BGE model
def generate_embeddings(text):
    inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512)
    with torch.no_grad():
        outputs = model(**inputs).last_hidden_state.mean(dim=1)
    return outputs.numpy().flatten()

# Perform Qdrant search
def vector_search(query, collection_name, limit=5):
    """Search Qdrant for multiple relevant tables."""
    embeddings = generate_embeddings(query)
    results = qdrant_client.search(
        collection_name=collection_name,
        query_vector=embeddings.tolist(),
        limit=limit  # Fetch multiple relevant matches
    )
    return [result.payload for result in results] if results else []

def generate_sql_from_metadata(user_query, table_metadata_list):
    if not table_metadata_list:
        return "No metadata found to generate the SQL query."

    # Combine metadata from multiple tables
    combined_metadata = ""
    for table_metadata in table_metadata_list:
        table_name = table_metadata.get("table_name", "UNKNOWN_TABLE")
        columns = table_metadata.get("columns", [])
        columns_list = "\n".join([
            f"{col['column_name']} ({col['data_type']}): {col['description']}."
            for col in columns
        ])
        relationships = table_metadata.get("relationships", [])
        relationship_list = "\n".join([
            f"Related Table: {rel['related_table']}, Conditions: {' AND '.join(rel['on_conditions'])}"
            for rel in relationships
        ])
        business_logic = table_metadata.get("business_logic", {})
        business_logic_text = "\n".join([
            f"{key}: {value}" for key, value in business_logic.items()
        ])
        combined_metadata += f"Table: {table_name}\nColumns:\n{columns_list}\nRelationships:\n{relationship_list}\nBusiness Logic:\n{business_logic_text}\n\n"

    # Prompt template with combined metadata
    prompt_template = f"""
    You are an expert Oracle SQL query generator. DO NOT PERFORM INTERNET SEARCH IF NOT IN THE METADATA
    Given the user query, metadata of multiple related tables, and their relationships, generate a precise SQL query.
    - Use standard Oracle SQL syntax
    - Join tables based on their defined relationships
    - Ensure to include all necessary conditions and filters relevant to the user query
    - Optimize the query for performance
    - If calculating size or usage, convert sizes from BYTES to GIGABYTES (GB) by dividing BYTES by 1024 * 1024 * 1024
    - Prioritize tables and columns mentioned in the user query if available

    Available Tables, Columns, Relationships, and Business Logic:
    {combined_metadata}

    User Query: {user_query}
    SQL Query:
    """
    
    # Use the LLM to generate the query
    chain = (ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(prompt_template),
        HumanMessagePromptTemplate.from_template(user_query),
    ]) | llm | StrOutputParser())
    
    query_result = chain.invoke({})
    return query_result

def process_query(user_query):
    # Perform semantic search in Qdrant
    print(f"Performing Qdrant semantic search for: {user_query}")
    relevant_tables = vector_search(user_query, qdrant_collection, limit=5)  # Fetch multiple relevant tables
    
    if relevant_tables:
        # Generate SQL query based on combined metadata
        return generate_sql_from_metadata(user_query, relevant_tables)
    return "No relevant table metadata found for generating the SQL query."

# Flask routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/get', methods=['POST'])
def get_bot_response():
    user_message = request.form['msg']
    try:
        response = process_query(user_message)
        return response
    except Exception as e:
        print(f"Error processing query: {str(e)}")  # Log the error
        return f"Error: {str(e)}"

if __name__ == "__main__":
    app.run(debug=True, port=5000)
