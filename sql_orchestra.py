"""
SQL ORCHESTRA (Based on JARVIS Architecture)
Autonomous Agents finding, adapting, and validating SQL specific knowledge.
"""
import sys
import os
import time
import random
import threading
import queue
import requests
import re
import duckdb
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from agent import QueryWriter, get_ollama_client, get_model_name
from src.knowledge_base import KnowledgeBase

# --- CONFIG ---
MAX_AGENTS = 1  # Keep low for local LLM to prevent overloading Ollama
TOPICS = [
    "advanced sql joins e-commerce",
    "sql window functions usage examples",
    "recursive cte sql examples",
    "sql pivot table dynamic columns",
    "duckdb specific sql features",
    "sql lateral join examples",
    "sql cross apply vs outer apply",
    "cohort analysis sql query",
    "retention rate sql query",
    "market basket analysis sql"
]

class SQLAgent:
    def __init__(self, agent_id):
        self.id = agent_id
        self.kb = KnowledgeBase()
        self.client = get_ollama_client()
        self.model = get_model_name()
        # We use a separate DB connection per agent if needed, or shared read-only
        self.db = duckdb.connect("bike_store.db", read_only=True)
        self.agent_helper = QueryWriter() # For schema access

    def think(self, prompt):
        try:
            res = self.client.chat(model=self.model, messages=[{'role': 'user', 'content': prompt}])
            return res['message']['content']
        except Exception as e:
            print(f"   [Agent {self.id} Brain Error: {e}]")
            return ""

    def scrape_sql_blocks(self, url):
        """Scrapes columns of text and specifically looks for SQL code blocks."""
        print(f"   🕷️ Agent {self.id} scraping: {url[:100]}...")
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200: return []
            
            content = resp.text
            blocks = []
            
            # 1. Markdown blocks
            md_blocks = re.findall(r'```sql(.*?)```', content, re.DOTALL | re.IGNORECASE)
            blocks.extend(md_blocks)
            
            # 2. HTML <pre><code> (StackOverflow style)
            soup = BeautifulSoup(content, 'html.parser')
            for code in soup.find_all('code'):
                text = code.get_text()
                if "SELECT" in text.upper() and "FROM" in text.upper():
                    blocks.append(text)
                    
            return [b.strip() for b in blocks if len(b.strip()) > 50]
        except Exception as e:
            print(f"   ⚠️ Agent {self.id} scrape error: {e}")
            return []

    def adapt_and_validate(self, raw_sql):
        """The 'Visual Cortex' of the SQL Agent: Adapts random SQL to our BikeStore Schema."""
        schema = self.agent_helper._format_schema()
        
        prompt = f"""/* Task: Adapt SQL Concept to Target Schema */
/* Source SQL Pattern: */
{raw_sql[:2000]}

/* Target Schema (Bike Stores): */
{schema}

/* Instruction */
1. Understand the logic (e.g. Ranking, Moving Average).
2. Rewrite it to work on the Bike Store data.
3. Use Aliases (e.g. p.product_name) to avoid ambiguity.
4. If impossible, return "N/A".

-- QUESTION: <Description>
-- SQL:
SELECT ...
"""
        response = self.think(prompt)
        if "N/A" in response or not response: return None
        
        # Extract
        q_match = re.search(r'-- QUESTION: (.*)', response)
        question = q_match.group(1).strip() if q_match else "Advanced SQL Logic"
        
        # Extract SQL
        sql_match = re.search(r'-- SQL:(.*)', response, re.DOTALL)
        if hasattr(sql_match, 'group'):
             sql = sql_match.group(1).strip()
        else:
             # Fallback
             if "SELECT" in response:
                 sql = response[response.find("SELECT"):]
             else:
                 return None

        # Validate
        try:
            self.db.execute(sql)
            return (question, sql)
        except Exception as e:
            # print(f"   [Validation Fail: {e}]")
            return None

    def run_mission(self, topic):
        print(f"   🎻 Agent {self.id}: Focusing on '{topic}'")
        
        # Search
        try:
            results = DDGS().text(topic, max_results=3)
            if not results: return
            
            for res in results:
                url = res['href']
                sql_blocks = self.scrape_sql_blocks(url)
                
                print(f"      found {len(sql_blocks)} code snippets.")
                
                for block in sql_blocks:
                    # Adapt
                    success_pair = self.adapt_and_validate(block)
                    if success_pair:
                        q, sql = success_pair
                        self.kb.add_learned_query(q, sql)
                        print(f"      💎 Agent {self.id}: LEARNED NEW SKILL! '{q}'")
                        
        except Exception as e:
            print(f"   ⚠️ Agent {self.id} search error: {e}")


class SQLOrchestra:
    def __init__(self):
        self.queue = queue.Queue()
        for t in TOPICS:
            self.queue.put(t)
            
    def worker(self, agent_id):
        agent = SQLAgent(agent_id)
        while True:
            try:
                topic = self.queue.get(timeout=5)
            except queue.Empty:
                # Refill or Randomize
                new_topic = random.choice(TOPICS) + f" examples {random.randint(1,100)}"
                time.sleep(5)
                self.queue.put(new_topic)
                continue
                
            agent.run_mission(topic)
            self.queue.task_done()
            time.sleep(2) # Rest

    def start(self):
        print(f"🎼 Starting SQL Orchestra with {MAX_AGENTS} Agents...")
        for i in range(MAX_AGENTS):
            t = threading.Thread(target=self.worker, args=(i+1,))
            t.daemon = True
            t.start()
            
        # Keep alive
        while True:
            time.sleep(10)

if __name__ == "__main__":
    orch = SQLOrchestra()
    orch.start()
