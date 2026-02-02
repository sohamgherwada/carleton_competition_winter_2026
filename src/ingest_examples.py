from src.knowledge_base import KnowledgeBase

kb = KnowledgeBase()

# FEW-SHOT EXAMPLES (The most powerful way to fix logic)
examples = [
    {
        "prompt": "Which staff member sold the most products?",
        "sql": """
        SELECT s.first_name, s.last_name, SUM(oi.quantity) as total_sold
        FROM staffs s
        JOIN orders o ON s.staff_id = o.staff_id
        JOIN order_items oi ON o.order_id = oi.order_id
        GROUP BY s.staff_id, s.first_name, s.last_name
        ORDER BY total_sold DESC LIMIT 1;
        """
    },
    {
        "prompt": "List products in 'Electric Bikes' category.",
        "sql": """
        SELECT p.product_name 
        FROM products p
        JOIN categories c ON p.category_id = c.category_id
        WHERE c.category_name = 'Electric Bikes';
        """
    },
    {
        "prompt": "Find customers who bought 'Trek' products.",
        "sql": """
        SELECT DISTINCT c.first_name, c.last_name
        FROM customers c
        JOIN orders o ON c.customer_id = o.customer_id
        JOIN order_items oi ON o.order_id = oi.order_id
        JOIN products p ON oi.product_id = p.product_id
        JOIN brands b ON p.brand_id = b.brand_id
        WHERE b.brand_name = 'Trek';
        """
    }, 
    {
        "prompt": "Staff who sold 'Electric Bikes' but not 'Children Bicycles'",
        "sql": """
        SELECT s.first_name, s.last_name
        FROM staffs s
        JOIN orders o ON s.staff_id = o.staff_id
        JOIN order_items oi ON o.order_id = oi.order_id
        JOIN products p ON oi.product_id = p.product_id
        JOIN categories c ON p.category_id = c.category_id
        WHERE c.category_name = 'Electric Bikes'
        EXCEPT
        SELECT s.first_name, s.last_name
        FROM staffs s
        JOIN orders o ON s.staff_id = o.staff_id
        JOIN order_items oi ON o.order_id = oi.order_id
        JOIN products p ON oi.product_id = p.product_id
        JOIN categories c ON p.category_id = c.category_id
        WHERE c.category_name = 'Children Bicycles';
        """
    }
]

for ex in examples:
    kb.add_learned_query(ex['prompt'], ex['sql'])

print(f"Ingested {len(examples)} high-quality examples.")
