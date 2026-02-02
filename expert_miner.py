import requests
import duckdb
import re
from agent import QueryWriter, get_ollama_client, get_model_name
from src.knowledge_base import KnowledgeBase
import time
import random
from duckduckgo_search import DDGS

class ExpertMiner:
    def __init__(self):
        self.kb = KnowledgeBase()
        self.agent = QueryWriter() # to get schema
        self.client = get_ollama_client()
        self.model = get_model_name() 
        self.db = duckdb.connect("bike_store.db", read_only=True)
        self.search = DDGS()
        self.seen_urls = set()
        
    def adapt_query(self, raw_sql):
        """
        Uses DeepSeek to 'transfer learn' the concept from raw_sql to our schema.
        """
        schema = self.agent._format_schema()
        
        prompt = f"""/* Task: Adapt SQL Concept from Source to Target Schema */

/* Source SQL (Example of a concept like Window Function, CTE, or Complex Join) */
{raw_sql}

/* Target Database Schema (Bike Store) */
{schema}

/* Goal */
1. Analyze what the Source SQL is doing (e.g. "Calculate running total", "Rank items").
2. Create a SIMILAR query for the Target Schema.
3. If the concept doesn't apply, return "N/A".
4. Output Format:
-- QUESTION: <Natural Language Description of what the query does>
-- SQL: <The Valid DuckDB Query for Target Schema>
SELECT ...
"""
        try:
             # Use completion style
             resp = self.client.chat(model=self.model, messages=[{'role': 'user', 'content': prompt}])
             content = resp['message']['content']
             
             if "N/A" in content: return None, None
             
             # Parse output
             q_match = re.search(r'-- QUESTION: (.*)', content)
             question = q_match.group(1).strip() if q_match else "Complex Query"
             
             # Extract SQL (from -- SQL: downwards)
             sql_match = re.search(r'-- SQL:(.*)', content, re.DOTALL)
             if sql_match:
                 sql = sql_match.group(1).strip()
             else:
                 # Fallback regex for code blocks
                 sql_code = re.search(r'```sql(.*?)```', content, re.DOTALL)
                 sql = sql_code.group(1).strip() if sql_code else content

             # Clean SQL
             if "SELECT" in sql and not sql.upper().startswith("SELECT") and not sql.upper().startswith("WITH"):
                 # Try to find start of query
                 idx = sql.upper().find("SELECT")
                 if idx == -1: idx = sql.upper().find("WITH")
                 if idx != -1: sql = sql[idx:]

             return question, sql
        except Exception as e:
            # print(f"Adaptation failed: {e}")
            return None, None

    def mine(self):
        print("Starting Expert Miner (Autonomously Finding Resources)...")
        
        search_terms = [
            "advanced sql query examples github gist",
            "complex sql joins for e-commerce",
            "duckdb window function examples",
            "sql recursive cte examples",
            "sql business intelligence queries examples",
            "postgres advanced sql patterns github"
        ]
        
        iteration = 0
        while True:
            term = random.choice(search_terms)
            print(f"\n[Iteration {iteration}] Searching for: '{term}'...", flush=True)
            
            try:
                # Add fallback if DDGS fails or returns empty
                results = []
                try:
                    results = list(self.search.text(term, max_results=5))
                except Exception as e:
                    print(f"  [Search Engine Error: {e}]")
                
                if not results:
                    print("  [No results found. Using fallback sources...]", flush=True)
                    # Add fallback sources here if search fails repeatedly
                    if iteration % 5 == 0:
                         results = [{'href': "https://gist.githubusercontent.com/fernandofother/a9bd9dd756e187b545f4/raw/255c2d30836102da83942007f354f9d8548c772e/ADVANCEDSQL-SOLVED.sql"}]

                for res in results:
                    url = res['href']
                    if url in self.seen_urls: continue
                    self.seen_urls.add(url)
                    
                    print(f"  > Inspection: {url}", flush=True)
                    
                    # Fetching
                    try:
                        # Fake Browser UA to avoid 403
                        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                        resp = requests.get(url, headers=headers, timeout=10)
                        
                        if resp.status_code != 200:
                            print(f"    [Status {resp.status_code}]")
                            continue
                        
                        content = resp.text
                        # Find potential SQL blocks
                        # Rough heuristic: content with "SELECT" and "FROM"
                        if "SELECT" not in content.upper():
                            continue
                            
                        # Extract Code Blocks logic (simple)
                        # We try to extract text between ```sql and ``` or just assume whole file if it ends in .sql
                        sql_blocks = []
                        if url.endswith('.sql') or 'raw' in url:
                             sql_blocks.append(content)
                        else:
                             # Regex for markdown
                             blocks = re.findall(r'```sql(.*?)```', content, re.DOTALL | re.IGNORECASE)
                             sql_blocks.extend(blocks)
                        
                        print(f"    Found {len(sql_blocks)} SQL blocks.")
                        
                        for block in sql_blocks:
                            if len(block) < 50: continue
                            
                            print("    > Transfer Learning...", end="", flush=True)
                            question, adapted_sql = self.adapt_query(block[:2000])
                            
                            if adapted_sql:
                                # Validate
                                try:
                                    self.db.execute(adapted_sql)
                                    print(" [SUCCESS - MEMORIZED ✅]")
                                    self.kb.add_learned_query(question, adapted_sql)
                                except Exception as e:
                                    print(" [Invalid SQL]")
                            else:
                                print(" [Skpped]")
                                
                    except Exception as e:
                        print(f"  Fetch error: {e}")
                        
            except Exception as e:
                print(f"Search error: {e}")
            
            print("Sleeping...")
            time.sleep(5)
            iteration += 1


if __name__ == "__main__":
    miner = ExpertMiner()
    miner.mine()
