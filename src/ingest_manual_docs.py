from src.knowledge_base import KnowledgeBase

kb = KnowledgeBase()

# DuckDB CTE Scoping rule/pattern
text = """
DuckDB CTE Scoping Rules:
Common Table Expressions (WITH clauses) define temporary tables.
You can use multiple CTEs separated by commas:
WITH cte1 AS (...), cte2 AS (...) SELECT * FROM cte1 JOIN cte2 ...
Important: You CANNOT define a CTE inside a subquery and reference it outside.
Valid: WITH t1 AS (SELECT...) SELECT * FROM t1
Invalid: SELECT * FROM (WITH t1 AS...)
"""

# Force add this to docs
if kb.docs_table:
    kb.docs_table.add([{"text": text, "source": "manual_fix", "vector": kb._get_embedding(text)}])
    print("Added CTE documentation fix.")
else:
    # Create if missing (simplified logic, usually it exists)
    pass
