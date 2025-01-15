from flask import Flask, render_template, request, jsonify
import cx_Oracle
import os
from dotenv import load_dotenv
from query_generator import generate_query
from query_generator import (
    generate_query,
    generate_sql_from_metadata,
    clean_sql_query,
    vector_search,
    generate_embeddings,
    analyze_query_results,  # Add this import
    llm,
    qdrant_client,
    qdrant_collection
)

app = Flask(__name__)

# Load environment variables
load_dotenv()

# Database configuration
DB_CONFIG = {
    'TEST': {
        'host': os.getenv('TEST_DB_HOST', '192.168.1.50'),
        'port': int(os.getenv('TEST_DB_PORT', '1531')),
        'service_name': os.getenv('TEST_DB_SERVICE', 'TEST'),
        'username': os.getenv('TEST_DB_USER', 'test_user'),
        'password': os.getenv('TEST_DB_PASSWORD', 'test_password')
    },
    'R13': {
        'host': os.getenv('R13_DB_HOST', '192.168.1.225'),
        'port': int(os.getenv('R13_DB_PORT', '1521')),
        'service_name': os.getenv('R13_DB_SERVICE', 'VIS'),
        'username': os.getenv('R13_DB_USER', 'r13_user'),
        'password': os.getenv('R13_DB_PASSWORD', 'r13_password')
    },
    'R26': {
        'host': os.getenv('R26_DB_HOST', 'localhost'),
        'port': int(os.getenv('R26_DB_PORT', '1521')),
        'service_name': os.getenv('R26_DB_SERVICE', 'r26'),
        'username': os.getenv('R26_DB_USER', 'r26_user'),
        'password': os.getenv('R26_DB_PASSWORD', 'r26_password')
    },
    'DEMO': {
        'host': os.getenv('DEMO_DB_HOST', 'localhost'),
        'port': int(os.getenv('DEMO_DB_PORT', '1521')),
        'service_name': os.getenv('DEMO_DB_SERVICE', 'demo'),
        'username': os.getenv('DEMO_DB_USER', 'demo_user'),
        'password': os.getenv('DEMO_DB_PASSWORD', 'demo_password')
    }
}


def execute_query(query, database):
    try:
        config = DB_CONFIG.get(database)
        if not config:
            return {
                "error": f"Unknown database: {database}",
                "solution": "Please select a valid database"
            }

        dsn = cx_Oracle.makedsn(
            config['host'],
            config['port'],
            service_name=config['service_name']
        )

        print(f"Connecting to database: {database}")
        print(f"DSN: {dsn}")

        connection = cx_Oracle.connect(
            user=config['username'],
            password=config['password'],
            dsn=dsn
        )

        cursor = connection.cursor()
        print(f"Executing query: {query}")
        cursor.execute(query)
        
        if query.strip().upper().startswith('SELECT'):
            columns = [col[0] for col in cursor.description]
            results = cursor.fetchall()
            
            result_table = []
            for row in results:
                result_row = {}
                for idx, col in enumerate(columns):
                    result_row[col] = str(row[idx])
                result_table.append(result_row)
            
            cursor.close()
            connection.close()
            return {"success": True, "data": result_table}
        
        connection.commit()
        cursor.close()
        connection.close()
        return {"success": True, "message": "Query executed successfully."}
                
    except cx_Oracle.Error as e:
        error_obj = e.args[0]
        print(f"Oracle Error: {error_obj.code} - {error_obj.message}")
        return {
            "error": f"Oracle Error [{error_obj.code}]: {error_obj.message}",
            "solution": "Please check your database connection and query."
        }
    except Exception as e:
        print(f"General Error: {str(e)}")
        return {
            "error": f"Error: {str(e)}",
            "solution": "An unexpected error occurred."
        }

def process_query(user_query, database):
    try:
        print(f"Processing query for database: {database}")
        
        generated_query, error = generate_query(user_query)
        if error:
            return {
                "error": error,
                "solution": "Try rephrasing your question."
            }
        
        execution_result = execute_query(generated_query, database)
        print(f"Execution result: {execution_result}")
        
        # Generate summary if we have data
        summary = None
        if execution_result.get("success") and "data" in execution_result:
            summary = analyze_query_results(generated_query, execution_result["data"])
            print(f"Generated summary: {summary}")  # Debug print

        return {
            "query": generated_query,
            "result": execution_result,
            "summary": summary
        }
        
    except Exception as e:
        print(f"Process query error: {str(e)}")
        return {
            "error": str(e),
            "solution": "An error occurred while processing your query."
        }

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/get', methods=['POST'])
def get_bot_response():
    user_message = request.form['msg']
    selected_db = request.form.get('database', 'TEST')
    
    print(f"Received request - Message: {user_message}, Database: {selected_db}")
    
    response = process_query(user_message, selected_db)
    return jsonify(response)


if __name__ == "__main__":
    app.run(debug=True, port=5000)

