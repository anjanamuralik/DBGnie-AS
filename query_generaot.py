import os
import re
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

# Load environment variables
load_dotenv()

# Qdrant Configuration
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

def generate_embeddings(text):
    """Generate embeddings using the BGE model."""
    inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512)
    with torch.no_grad():
        outputs = model(**inputs).last_hidden_state.mean(dim=1)
    return outputs.numpy().flatten()

def vector_search(query, collection_name, limit=5):
    """Search Qdrant for multiple relevant tables."""
    embeddings = generate_embeddings(query)
    results = qdrant_client.search(
        collection_name=collection_name,
        query_vector=embeddings.tolist(),
        limit=limit
    )
    return [result.payload for result in results] if results else []

def escape_special_chars(text):
    """Escape special characters in text."""
    if isinstance(text, str):
        return text.replace('{', '{{').replace('}', '}}')
    return str(text)

def clean_sql_query(response):
    """Clean and extract SQL query from the response."""
    try:
        sql_match = re.search(r'```sql\s*(.*?)\s*```', response, re.DOTALL)
        if sql_match:
            query = sql_match.group(1)
        else:
            sql_match = re.search(r'SELECT.*?(?:;|\Z)', response, re.DOTALL | re.IGNORECASE)
            if sql_match:
                query = sql_match.group(0)
            else:
                return None

        query = query.replace('`', '')
        query = ' '.join(query.split())
        query = query.strip(';')
        query = query.strip()
        
        print(f"Cleaned SQL Query: {query}")
        return query
    except Exception as e:
        print(f"Error cleaning SQL query: {str(e)}")
        return None

def generate_sql_from_metadata(user_query, table_metadata_list):

    """Generate SQL query from metadata with proper template handling."""

    if not table_metadata_list:

        return "No metadata found to generate the SQL query."
 
    # Combine metadata from multiple tables with escaped special characters

    combined_metadata = ""

    for table_metadata in table_metadata_list:

        table_name = table_metadata.get("table_name", "UNKNOWN_TABLE")

        table_owner = table_metadata.get("table_owner", ["UNKNOWN_OWNER"])[0]  # Default to the first owner

        fully_qualified_table_name = f"{table_owner}.{table_name}" if table_owner != "UNKNOWN_OWNER" else table_name
 
        # Process columns with escaped special characters

        columns = table_metadata.get("columns", [])

        columns_list = "\n".join([

            f"{col['column_name']} ({col['data_type']}): {escape_special_chars(col.get('description', ''))}"

            for col in columns

        ])
 
        # Process relationships with escaped special characters

        relationships = table_metadata.get("relationships", [])

        relationship_list = "\n".join([

            f"Related Table: {rel['related_table']}, Conditions: {' AND '.join(escape_special_chars(cond) for cond in rel['on_conditions'])}"

            for rel in relationships

        ])
 
        # Process business logic with escaped special characters

        business_logic = table_metadata.get("business_logic", {})

        business_logic_text = "\n".join([

            f"{key}: {escape_special_chars(value)}"

            for key, value in business_logic.items()

        ])
 
        # Add table owner to metadata description

        combined_metadata += f"""Table: {fully_qualified_table_name}

Columns:

{columns_list}

Relationships:

{relationship_list}

Business Logic:

{business_logic_text}
 
"""
 
    # Define the prompt template with proper variable placeholders

    prompt_template = """You are an expert Oracle SQL query generator.

    Generate precise Oracle SQL queries **ONLY** using the provided metadata of tables, columns, and their relationships.

    - If no metadata is provided, respond with: "No metadata found to generate the SQL query."

    - Do not assume or invent tables or columns that are not explicitly described in the metadata.

    - Use standard Oracle SQL syntax

    - Use fully qualified table names (owner.table_name) when the owner information is available.

    - Join tables based on their defined relationships to include requested fields.

    - Ensure to include all necessary conditions and filters relevant to the user query.

    - Optimize the query for performance

    - If calculating size or usage, convert sizes from BYTES to GIGABYTES (GB) by dividing BYTES by 1024 * 1024 * 1024

    - Prioritize tables and columns mentioned in the user query if available

    - Use the provided status mappings for decoding `PHASE_CODE` and other relevant columns.
 
    Available Tables, Columns, Relationships, and Business Logic:

    {metadata}
 
    User Query: {query}

    SQL Query:"""
 
    # Create messages with proper variable mapping

    messages = [

        SystemMessagePromptTemplate.from_template(prompt_template),

        HumanMessagePromptTemplate.from_template("{query}")

    ]

    chat_prompt = ChatPromptTemplate.from_messages(messages)

    try:

        # Invoke the chain with properly mapped variables

        chain = chat_prompt | llm | StrOutputParser()

        query_result = chain.invoke({

            "metadata": combined_metadata,

            "query": user_query

        })

        return query_result

    except Exception as e:

        print(f"Error generating SQL: {str(e)}")

        return f"Error generating SQL query: {str(e)}"

 
    
def analyze_query_results(query, results):
    """Generate a summary of the query results."""
    try:
        if not results or not isinstance(results, list):
            return "No results to analyze."

        # Create a simple prompt template
        prompt_template = """As a data analyst, please provide a brief summary of these SQL query results:

Query: {query}
Number of rows: {row_count}
Sample data: {sample}

Provide a 1-2 sentence summary of what these results show."""

        # Create chat prompt
        chat_prompt = ChatPromptTemplate.from_template(prompt_template)
        
        # Create the chain with the prompt
        chain = chat_prompt | llm | StrOutputParser()
        
        # Invoke the chain with the variables
        analysis = chain.invoke({
            "query": query,
            "row_count": len(results),
            "sample": str(results[:3])
        })
        
        return analysis.strip()
    except Exception as e:
        print(f"Error analyzing results: {str(e)}")
        return f"Query returned {len(results)} rows."    

def generate_query(user_query):
    """Process user query and generate SQL."""
    try:
        print(f"Performing Qdrant semantic search for: {user_query}")
        relevant_tables = vector_search(user_query, qdrant_collection, limit=5)
        if not relevant_tables:
            return None, "No relevant table metadata found."
        
        generated_response = generate_sql_from_metadata(user_query, relevant_tables)
        print(f"Generated response: {generated_response}")
        
        clean_query = clean_sql_query(generated_response)
        if not clean_query:
            return None, "Could not extract valid SQL query from response."
        
        return clean_query, None
        
    except Exception as e:
        print(f"Query generation error: {str(e)}")
        return None, str(e)
