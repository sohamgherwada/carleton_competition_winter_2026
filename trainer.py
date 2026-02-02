import duckdb
import pandas as pd
from agent import QueryWriter, get_ollama_client, get_model_name
import time
import json
import hashlib

class Trainer:
    def __init__(self, target_per_level=5): # Default to 5 for safety, user can edit to 100
        self.agent = QueryWriter()
        self.client = get_ollama_client()
        # Use instruct model for generation too
        self.model = "mistral:7b-instruct-q4_K_M" 
        self.target = target_per_level
        self.seen_hashes = set()
        self.db = duckdb.connect("bike_store.db", read_only=True)

    def generate_ground_truth(self, difficulty):
        """
        Asks LLM to generate a valid SQL query for the schema + a question.
        """
        schema = self.agent._format_schema()
        
        # Prompts tailored by difficulty
        prompt_logic = ""
        if difficulty == "easy":
            prompt_logic = "Use single table, basic SELECT ... WHERE filtering."
        elif difficulty == "medium":
            prompt_logic = "Use JOIN between 2 tables."
        elif difficulty == "hard":
            prompt_logic = "Use JOINs across 3+ tables, GROUP BY, and Aggregates."
        elif difficulty == "expert":
            prompt_logic = "Use Window Functions (RANK, LEAD), CTEs, or Subqueries."

        prompt = f"""You are a SQL Teacher. 
Schema:
{schema}

Task: Generate 1 unique SQL query and its corresponding natural language question.
Difficulty: {difficulty} ({prompt_logic}).
Constraint: The SQL MUST be valid DuckDB syntax and return data (not empty).

Output Format JSON ONLY:
{{
  "question": "...",
  "sql": "..."
}}
"""
        max_retries = 5
        for _ in range(max_retries):
            try:
                resp = self.client.chat(model=self.model, messages=[{'role': 'user', 'content': prompt}], format='json')
                data = json.loads(resp['message']['content'])
                question = data['question']
                sql = data['sql']
                
                # Check Uniqueness
                q_hash = hashlib.md5((question + sql).encode()).hexdigest()
                if q_hash in self.seen_hashes:
                    continue
                
                # Verify Validity (Must run and return rows)
                df = self.db.execute(sql).fetch_df()
                if df.empty:
                    continue
                
                self.seen_hashes.add(q_hash)
                return question, sql, df
            except Exception as e:
                # Retry on json error or sql error
                continue
        return None, None, None

    def train(self):
        levels = ['easy', 'medium', 'hard', 'expert']
        
        for level in levels:
            print(f"\n=== Starting Level: {level.upper()} ===")
            success = 0
            fails_in_row = 0
            
            while success < self.target:
                if fails_in_row >= 10:
                    print(f"!!! CRITICAL: 10 failures in a row at level {level}. Aborting level.")
                    break
                
                print(f"Generating Q ({success+1}/{self.target})...", end="", flush=True)
                q, truth_sql, truth_df = self.generate_ground_truth(level)
                
                if not q:
                    print(" [Gen Failed]")
                    continue
                
                print(f"\nQ: {q}")
                
                # Student Attempt
                print("  Student solving...", end="", flush=True)
                try:
                    start = time.time()
                    student_sql = self.agent.generate_query(q)
                    student_df = self.db.execute(student_sql).fetch_df()
                    
                    # Validation: Compare DataFrames
                    # Standardize sorting for comparison (handle read-only arrays by copying)
                    def standardize(df):
                        if df.empty: return df
                        # Sort by all columns
                        return df.sort_values(by=list(df.columns)).reset_index(drop=True)

                    # Check structure/values
                    t_std = standardize(truth_df)
                    s_std = standardize(student_df)
                    
                    if t_std.equals(s_std) or (t_std.shape == s_std.shape and (t_std.values == s_std.values).all()):
                        print(" [SUCCESS - MEMORIZED ✅]")
                        self.agent.learn(q, student_sql)
                        success += 1
                        fails_in_row = 0
                    else:
                        print(f" [WRONG RESULT]")
                        # print(f"    Truth: {truth_sql}")
                        # print(f"    Student: {student_sql}")
                        fails_in_row += 1
                        
                except Exception as e:
                    print(f" [ERROR: {e}]")
                    fails_in_row += 1
                    
        print("\n\nTraining Complete!")

if __name__ == "__main__":
    # Start with small batch to prove it works, user can edit file to 100
    t = Trainer(target_per_level=5) 
    t.train()
