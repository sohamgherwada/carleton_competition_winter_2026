"""
SQL Query Writer Agent

This file contains the QueryWriter class that generates SQL queries from natural language.
Implement your agent logic in this file.
"""

import os
import duckdb
from db.bike_store import get_schema_info
from ollama import Client
try:
    from src.knowledge_base import KnowledgeBase
except ImportError:
    # Handle case where dependencies might not be fully set up yet during initial loads
    KnowledgeBase = None

def get_ollama_client():
    from ollama import Client
    return Client(host="http://localhost:11434", timeout=1200.0)

def get_model_name():
    return "deepseek-coder:6.7b-base-q4_K_M"

 



class QueryWriter:
    """
    SQL Query Writer Agent that converts natural language to SQL queries.

    This class is the main interface for the competition evaluation.
    You must implement the generate_query method.
    """

    def __init__(self, db_path: str = 'bike_store.db'):
        """
        Initialize the QueryWriter.

        Args:
            db_path (str): Path to the DuckDB database file.
        """
        self.db_path = db_path
        self.schema = get_schema_info(db_path=db_path)
        self.client = get_ollama_client()
        self.model = get_model_name()
        
        # Initialize Knowledge Base
        try:
            self.kb = KnowledgeBase() if KnowledgeBase else None
            # Optional: Ingest docs on first run if empty
            # self.kb.ingest_docs() 
        except Exception as e:
            print(f"Warning: Could not initialize Knowledge Base: {e}")
            self.kb = None

    def generate_query(self, prompt: str) -> str:
        """
        Generate a SQL query from a natural language prompt.
        Includes RAG retrieval and Auto-Retry on syntax errors.
        """
        # 1. Retrieve Context from RAG
        rag_context = ""
        if self.kb:
            try:
                results = self.kb.search(prompt)
                
                if results.get("learned"):
                    rag_context += "\nPossibly Relevant Past Queries:\n"
                    for item in results["learned"]:
                        rag_context += f"- Q: {item['prompt']}\n  SQL: {item['sql']}\n"
                
                if results.get("docs"):
                     rag_context += "\nSyntax Reference:\n"
                     for item in results["docs"]:
                         rag_context += f"- {item['text']}\n"
            except Exception as e:
                print(f"RAG search failed: {e}")

        # 2. Format Schema
        schema_text = self._format_schema()

        # 3. Execution Loop with Retry
        max_retries = 3
        current_attempt = 0
        error_history = ""
        
        last_generated_sql = ""

        previous_sql_signatures = set()
        
        while current_attempt < max_retries:
            # Base Model Prompting: Comments + SQL Context
            # We avoid "You are an expert" chat instructions which confuse base models.
            full_prompt = f"""/* Database Schema */
{schema_text}

/* Relevant Examples */
{rag_context}

/* User Question: {prompt} */
/* Previous Errors to fix: {error_history} */

/* CRITICAL RULES:
   1. ALWAYS use table aliases (e.g. p.list_price, oi.list_price) to prevent "Ambiguous column" errors.
   2. Use explicit JOINs.
*/

-- Generate the valid DuckDB SQL query for the question:
SELECT"""
            
            # Note for later: We might need to handle the response not starting with SELECT if we don't complete it.
            # But let's try standard chat first. Deepseek Base often just completes code.


            # Call LLM
            try:
                # Decide model - user asked to use Deepseek for fixing? 
                response = self.client.chat(
                    model=self.model,
                    messages=[
                        {'role': 'user', 'content': full_prompt}
                    ]
                )
                sql = response['message']['content']
                
                # If the model completes " * FROM...", we need to add "SELECT" back
                if not sql.strip().upper().startswith("SELECT") and not sql.strip().upper().startswith("WITH"):
                     sql = "SELECT " + sql
                # Robust cleanup using regex
                import re
                # Find content between ```sql and ``` or just ``` and ```
                match = re.search(r'```(?:sql)?\s*(.*?)\s*```', sql, re.DOTALL | re.IGNORECASE)
                if match:
                    sql = match.group(1)
                else:
                    # If no code blocks, assume the whole response is SQL but strip generic chat text if possible
                    # Or just strip whitespace
                    sql = sql.strip()
                    # Remove common prefixes if they exist (hacky but useful for chat models)
                    sql = re.sub(r'^(Here is the SQL|Sure|The query is|Based on the schema).*?:', '', sql, flags=re.IGNORECASE | re.DOTALL).strip()

                last_generated_sql = sql
                
                # Dry Run Validation
                error_msg = self._validate_sql(sql)
                if error_msg is None:
                    return sql
                else:
                    print(f"Attempt {current_attempt+1} failed: {error_msg}")
                    # Construct a stronger error prompt
                    error_history += f"\nAttempt {current_attempt+1} SQL:\n{sql}\nError: {error_msg}\n"
                    # Add explicit instruction to change approach
                    previous_sql_signatures.add(sql)

            except Exception as e:
                print(f"LLM generation failed: {e}")
                
            current_attempt += 1
        
        # If all retries failed, return the last generated SQL (best effort)
        return last_generated_sql

    def _validate_sql(self, sql: str) -> str | None:
        """
        Tries to Prepare/Explain the query to check for syntax errors.
        Returns None if valid, or the error message string if invalid.
        """
        con = duckdb.connect(self.db_path, read_only=True)
        try:
            # Use EXPLAIN to check validity without running expensive queries
            con.execute(f"EXPLAIN {sql}")
            return None
        except Exception as e:
            return str(e)
        finally:
            con.close()

    def learn(self, prompt: str, sql: str):
        """
        Save a successful query to the Knowledge Base.
        """
        if self.kb:
            self.kb.add_learned_query(prompt, sql)

    def _format_schema(self) -> str:
        """
        Format the database schema as a string for the LLM prompt.

        Returns:
            str: A formatted string representation of the database schema.
        """
        schema_parts = []
        for table_name, columns in self.schema.items():
            cols = ", ".join([f"{col['name']} ({col['type']})" for col in columns])
            schema_parts.append(f"Table {table_name}: {cols}")
        return "\n".join(schema_parts)


if __name__ == "__main__":
    # Test code to verify connection
    print("Testing Ollama connection...")
    try:
        client = get_ollama_client()
        model = get_model_name()
        print(f"Connecting to {client._client.base_url} with model {model}...")
        
        response = client.chat(
            model=model,
            messages=[{'role': 'user', 'content': 'Hello, are you working?'}]
        )
        print("\nSuccess! Response from LLM:")
        print(response['message']['content'])
    except Exception as e:
        print(f"\nConnection failed: {e}")
