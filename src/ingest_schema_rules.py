from src.knowledge_base import KnowledgeBase

kb = KnowledgeBase()

# DuckDB Schema Relationships (helping the agent find columns)
text = """
Database Relationship Rues:
1. 'store_name' is ONLY in the 'stores' table.
2. To get store name from 'stocks', you MUST join 'stores': 
   `FROM stocks JOIN stores ON stocks.store_id = stores.store_id`.
3. 'category_name' is ONLY in 'categories'.
4. To get category name from 'products', join 'categories':
   `FROM products JOIN categories ON products.category_id = categories.category_id`.
5. 'brand_name' is ONLY in 'brands'.
"""

# Force add this to docs
if kb.docs_table:
    kb.docs_table.add([{"text": text, "source": "schema_fix", "vector": kb._get_embedding(text)}])
    print("Added Schema Relationship rules.")
else:
    pass
