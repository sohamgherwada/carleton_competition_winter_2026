from lancedb.pydantic import LanceModel, Vector
from lancedb.embeddings import EmbeddingFunctionRegistry
import lancedb
import os
import requests
from bs4 import BeautifulSoup
from agent import get_ollama_client, get_model_name

class DocItem(LanceModel):
    text: str
    vector: Vector(2048) # Approximate dimension for many models, will adjust dynamic if needed or catch error
    source: str

class LearnedItem(LanceModel):
    prompt: str
    sql: str
    vector: Vector(2048)
    avg_success: float = 1.0

class KnowledgeBase:
    def __init__(self, db_path="data/lancedb"):
        os.makedirs(db_path, exist_ok=True)
        self.db = lancedb.connect(db_path)
        self.client = get_ollama_client()
        self.model = "nomic-embed-text:latest"
        
        # We need to determine embedding dimension dynamically or pick a standard one
        # For this prototype, I'll try to fetch one embedding to see size
        sample_embed = self.client.embed(model=self.model, input="test")
        # Handle different response formats (newer ollama returns 'embeddings' list)
        if 'embeddings' in sample_embed:
             self.dim = len(sample_embed['embeddings'][0])
        else:
             self.dim = len(sample_embed['embedding'])
             
        # Re-define models with correct dimension
        # Note: LanceDB Pydantic models are a bit static with Vector(dim). 
        # We might need to use dynamic schema or just standard PyArrow schema if this is complex.
        # For simplicity, I will use tables created from data directly, skipping strict Pydantic class pre-definition if possible,
        # OR I will just use the dimension I found.
        
        # Create/Open tables
        # We will use "create_table(..., exist_ok=True)" with the first data item to define schema automatically
        self.docs_table = None
        self.learned_table = None

    def _get_embedding(self, text):
        resp = self.client.embed(model=self.model, input=text)
        if 'embeddings' in resp:
            return resp['embeddings'][0]
        return resp['embedding']

    def ingest_docs(self):
        """
        Scrapes basic DuckDB docs and stores them.
        """
        # Cheatsheet URL or similar
        url = "https://duckdb.org/docs/sql/query_syntax/select" 
        try:
            r = requests.get(url)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                # Extract code blocks and descriptions
                # This is a basic scraper
                content = []
                for code in soup.find_all('code'):
                    text = code.get_text()
                    if len(text) > 10: # filtering noise
                        content.append({"text": text, "source": url, "vector": self._get_embedding(text)})
                
                if content:
                    if "documentation" in self.db.table_names():
                        self.docs_table = self.db.open_table("documentation")
                        self.docs_table.add(content)
                    else:
                        self.docs_table = self.db.create_table("documentation", content)
                    print(f"Ingested {len(content)} doc snippets.")
        except Exception as e:
            print(f"Failed to ingest docs: {e}")

    def add_learned_query(self, prompt, sql):
        vector = self._get_embedding(prompt)
        data = [{"prompt": prompt, "sql": sql, "vector": vector}]
        
        if "learned_queries" in self.db.table_names():
            self.learned_table = self.db.open_table("learned_queries")
            self.learned_table.add(data)
        else:
            self.learned_table = self.db.create_table("learned_queries", data)
        print("Learned new query!")

    def search(self, prompt, k=3):
        results = {"docs": [], "learned": []}
        query_vec = self._get_embedding(prompt)
        
        if "learned_queries" in self.db.table_names():
            tbl = self.db.open_table("learned_queries")
            res = tbl.search(query_vec).limit(k).to_list()
            results["learned"] = res
            
        if "documentation" in self.db.table_names():
            tbl = self.db.open_table("documentation")
            res = tbl.search(query_vec).limit(k).to_list()
            results["docs"] = res
            
        return results
