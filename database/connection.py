import asyncpg
import asyncpg.exceptions
from typing import Dict, Optional, List
from datetime import date, datetime
from lib.schemas import SalesData, Article, DataSummary, StorageType, User
import logging

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, database_url: str = ""):
        self.database_url = database_url
        self.pool: Optional[asyncpg.Pool] = None
        self.use_memory = not database_url
        self.memory_storage = {
            "users": [],
            "sales_data": [],
            "articles": [],
            "file_hashes": set(),
            "metadata": {"last_upload": None},
        }
        self.storage_type = (
            StorageType.MEMORY if self.use_memory else StorageType.DATABASE
        )

    async def connect(self):
        if self.use_memory:
            logger.info("Using in-memory storage; no database connection pool created.")
            return
        if self.pool is None:
            try:
                logger.info("Creating asyncpg connection pool...")
                self.pool = await asyncpg.create_pool(
                    dsn=self.database_url,
                    min_size=2,
                    max_size=10,
                    statement_cache_size=50,
                )
                await self.create_tables()
                self.storage_type = StorageType.DATABASE
                logger.info("Database connection pool created.")
            except Exception as e:
                logger.error(f"Failed to create connection pool: {e}")
                self.use_memory = True
                self.pool = None
                self.storage_type = StorageType.MEMORY

    async def disconnect(self):
        if self.pool:
            try:
                await self.pool.close()
                logger.info("Database connection pool closed.")
            except Exception as e:
                logger.error(f"Error closing database connection pool: {e}")
            finally:
                self.pool = None

    async def create_tables(self):
        if self.use_memory or not self.pool:
            return
        try:
            async with self.pool.acquire() as conn:
                # Users table
                await self._execute_with_retry(
                    conn,
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        username VARCHAR(100) UNIQUE NOT NULL,
                        email VARCHAR(255) UNIQUE NOT NULL,
                        created_at TIMESTAMP DEFAULT NOW()
                    );
                    """,
                )

                # File uploads with user reference and filename
                await self._execute_with_retry(
                    conn,
                    """
                    CREATE TABLE IF NOT EXISTS file_uploads (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER REFERENCES users(id),
                        file_hash VARCHAR(64) UNIQUE,
                        filename VARCHAR(255),
                        upload_date TIMESTAMP DEFAULT NOW(),
                        record_count INTEGER
                    );
                    """,
                )

                # Sales data with file reference
                await self._execute_with_retry(
                    conn,
                    """
                    CREATE TABLE IF NOT EXISTS sales_data (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER REFERENCES users(id),
                        file_upload_id INTEGER REFERENCES file_uploads(id),
                        date DATE,
                        product VARCHAR(255),
                        category VARCHAR(255),
                        sales_amount DECIMAL(10,2),
                        quantity INTEGER,
                        region VARCHAR(255),
                        created_at TIMESTAMP DEFAULT NOW()
                    );
                    """,
                )
                # Articles with user reference
                await self._execute_with_retry(
                    conn,
                    """
                CREATE TABLE IF NOT EXISTS articles (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    title VARCHAR(500) NOT NULL,
                    content TEXT NOT NULL,
                    article_type VARCHAR(100) NOT NULL,
                    generated_date DATE DEFAULT CURRENT_DATE,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                """,
                )
        except Exception as e:
            logger.error(f"Error creating tables: {e}")

    async def _execute_with_retry(self, conn: asyncpg.Connection, query: str, *args):
        try:
            return await conn.execute(query, *args)
        except asyncpg.exceptions.InvalidCachedStatementError:
            logger.warning(
                f"InvalidCachedStatementError detected, retrying query: {query[:50]}..."
            )
            return await conn.execute(query, *args)
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            raise

    async def _fetchrow_with_retry(self, conn: asyncpg.Connection, query: str, *args):
        try:
            return await conn.fetchrow(query, *args)
        except asyncpg.exceptions.InvalidCachedStatementError:
            logger.warning(
                f"InvalidCachedStatementError detected, retrying fetchrow: {query[:50]}..."
            )
            return await conn.fetchrow(query, *args)
        except Exception as e:
            logger.error(f"Error fetching row: {e}")
            raise

    async def _fetch_with_retry(self, conn: asyncpg.Connection, query: str, *args):
        try:
            return await conn.fetch(query, *args)
        except asyncpg.exceptions.InvalidCachedStatementError:
            logger.warning(
                f"InvalidCachedStatementError detected, retrying fetch: {query[:50]}..."
            )
            return await conn.fetch(query, *args)
        except Exception as e:
            logger.error(f"Error fetching data: {e}")
            raise

    # User management methods
    async def create_user(self, username: str, email: str) -> Optional[User]:
        if self.use_memory:
            try:
                user_data = {
                    "id": len(self.memory_storage["users"]) + 1,
                    "username": username,
                    "email": email,
                    "created_at": datetime.now(),
                }
                self.memory_storage["users"].append(user_data)
                return User(**user_data)
            except Exception as e:
                logger.error(f"Error creating user in memory: {e}")
                return None

        try:
            async with self.pool.acquire() as conn:
                row = await self._fetchrow_with_retry(
                    conn,
                    """
                    INSERT INTO users(username, email)
                    VALUES ($1, $2)
                    RETURNING id, username, email, created_at
                    """,
                    username,
                    email,
                )
                return User(**dict(row)) if row else None
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None

    async def get_user(self, user_id: int) -> Optional[User]:
        if self.use_memory:
            try:
                for user_data in self.memory_storage["users"]:
                    if user_data["id"] == user_id:
                        return User(**user_data)
                return None
            except Exception as e:
                logger.error(f"Error getting user from memory: {e}")
                return None

        try:
            async with self.pool.acquire() as conn:
                row = await self._fetchrow_with_retry(
                    conn,
                    "SELECT id, username, email, created_at FROM users WHERE id = $1",
                    user_id,
                )
                return User(**dict(row)) if row else None
        except Exception as e:
            logger.error(f"Error getting user: {e}")
            return None

    async def check_file_duplicate(
        self, file_hash: str, user_id: Optional[int] = None
    ) -> bool:
        if self.use_memory:
            return file_hash in self.memory_storage["file_hashes"]

        try:
            async with self.pool.acquire() as conn:
                if user_id:
                    result = await self._fetchrow_with_retry(
                        conn,
                        "SELECT EXISTS(SELECT 1 FROM file_uploads WHERE file_hash=$1 AND user_id=$2) AS exists;",
                        file_hash,
                        user_id,
                    )
                else:
                    result = await self._fetchrow_with_retry(
                        conn,
                        "SELECT EXISTS(SELECT 1 FROM file_uploads WHERE file_hash=$1) AS exists;",
                        file_hash,
                    )
            return result["exists"] if result else False
        except Exception as e:
            logger.error(f"Error checking file duplicate: {e}")
            return False

    async def record_file_upload(
        self,
        file_hash: str,
        filename: str,
        record_count: int,
        user_id: Optional[int] = None,
    ) -> Optional[int]:
        """Record file upload and return file_upload_id"""
        if self.use_memory:
            file_id = len([f for f in self.memory_storage.get("file_uploads", [])]) + 1
            self.memory_storage.setdefault("file_uploads", []).append(
                {
                    "id": file_id,
                    "user_id": user_id,
                    "file_hash": file_hash,
                    "filename": filename,
                    "upload_date": datetime.now(),
                    "record_count": record_count,
                }
            )
            self.memory_storage["file_hashes"].add(file_hash)
            return file_id

        try:
            async with self.pool.acquire() as conn:
                row = await self._fetchrow_with_retry(
                    conn,
                    """INSERT INTO file_uploads(file_hash, filename, record_count, user_id) 
                       VALUES($1, $2, $3, $4) 
                       ON CONFLICT (file_hash) DO UPDATE SET record_count = EXCLUDED.record_count
                       RETURNING id""",
                    file_hash,
                    filename,
                    record_count,
                    user_id,
                )
                return row["id"] if row else None
        except Exception as e:
            logger.error(f"Error recording file upload: {e}")
            return None

    async def insert_sales_data_batch(
        self,
        data_list: List[SalesData],
        user_id: Optional[int] = None,
        file_upload_id: Optional[int] = None,
    ) -> int:
        if not data_list:
            return 0
        if self.use_memory:
            for item in data_list:
                item_dict = item.model_dump()
                item_dict["id"] = len(self.memory_storage["sales_data"]) + 1
                item_dict["user_id"] = user_id
                item_dict["file_upload_id"] = file_upload_id
                item_dict["created_at"] = datetime.now()
                self.memory_storage["sales_data"].append(item_dict)
            return len(data_list)

        records = [
            (
                user_id,
                file_upload_id,
                item.date,
                item.product,
                item.category,
                item.sales_amount,
                item.quantity,
                item.region,
            )
            for item in data_list
        ]
        try:
            async with self.pool.acquire() as conn:
                try:
                    await conn.executemany(
                        """
                        INSERT INTO sales_data(user_id, file_upload_id, date, product, category, sales_amount, quantity, region)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        """,
                        records,
                    )
                except asyncpg.exceptions.InvalidCachedStatementError:
                    logger.warning(
                        "InvalidCachedStatementError on executemany, retrying once"
                    )
                    await conn.executemany(
                        """
                        INSERT INTO sales_data(user_id, file_upload_id, date, product, category, sales_amount, quantity, region)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        """,
                        records,
                    )
            return len(records)
        except Exception as e:
            logger.error(f"Error inserting sales data batch: {e}")
            return 0

    async def clear_user_data(self, user_id: int) -> Dict[str, int]:
        """Clear all data for a specific user"""
        if self.use_memory:
            sales_cleared = len(
                [
                    item
                    for item in self.memory_storage["sales_data"]
                    if item.get("user_id") == user_id
                ]
            )
            articles_cleared = len(
                [
                    item
                    for item in self.memory_storage["articles"]
                    if item.get("user_id") == user_id
                ]
            )
            files_cleared = len(
                [
                    item
                    for item in self.memory_storage.get("file_uploads", [])
                    if item.get("user_id") == user_id
                ]
            )

            self.memory_storage["sales_data"] = [
                item
                for item in self.memory_storage["sales_data"]
                if item.get("user_id") != user_id
            ]
            self.memory_storage["articles"] = [
                item
                for item in self.memory_storage["articles"]
                if item.get("user_id") != user_id
            ]
            self.memory_storage["file_uploads"] = [
                item
                for item in self.memory_storage.get("file_uploads", [])
                if item.get("user_id") != user_id
            ]

            return {
                "sales_data": sales_cleared,
                "articles": articles_cleared,
                "file_uploads": files_cleared,
            }

        try:
            async with self.pool.acquire() as conn:
                # Count first, then delete
                sales_cleared = (
                    await conn.fetchval(
                        "SELECT COUNT(*) FROM sales_data WHERE user_id = $1", user_id
                    )
                    or 0
                )
                await conn.execute("DELETE FROM sales_data WHERE user_id = $1", user_id)

                articles_cleared = (
                    await conn.fetchval(
                        "SELECT COUNT(*) FROM articles WHERE user_id = $1", user_id
                    )
                    or 0
                )
                await conn.execute("DELETE FROM articles WHERE user_id = $1", user_id)

                files_cleared = (
                    await conn.fetchval(
                        "SELECT COUNT(*) FROM file_uploads WHERE user_id = $1", user_id
                    )
                    or 0
                )
                await conn.execute(
                    "DELETE FROM file_uploads WHERE user_id = $1", user_id
                )

                return {
                    "sales_data": sales_cleared,
                    "articles": articles_cleared,
                    "file_uploads": files_cleared,
                }
        except Exception as e:
            logger.error(f"Error clearing user data: {e}")
            return {"sales_data": 0, "articles": 0, "file_uploads": 0}

    async def insert_article(
        self, title: str, content: str, article_type: str, user_id: Optional[int] = None
    ) -> Optional[Article]:
        if self.use_memory:
            try:
                article_data = {
                    "id": len(self.memory_storage["articles"]) + 1,
                    "user_id": user_id,
                    "title": title,
                    "content": content,
                    "article_type": article_type,
                    "generated_date": date.today(),
                    "created_at": datetime.now(),
                }
                self.memory_storage["articles"].append(article_data)
                return Article(**article_data)
            except Exception as e:
                logger.error(f"Error inserting article in memory: {e}")
                return None

        try:
            async with self.pool.acquire() as conn:
                row = await self._fetchrow_with_retry(
                    conn,
                    """
                    INSERT INTO articles(user_id, title, content, article_type)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id, user_id, title, content, article_type, generated_date, created_at
                    """,
                    user_id,
                    title,
                    content,
                    article_type,
                )
                return Article(**dict(row)) if row else None
        except Exception as e:
            logger.error(f"Error inserting article: {e}")
            return None

    async def get_enhanced_summary(self, user_id: Optional[int] = None) -> DataSummary:
        if self.use_memory:
            try:
                data = [
                    item
                    for item in self.memory_storage["sales_data"]
                    if user_id is None or item.get("user_id") == user_id
                ]

                if not data:
                    return DataSummary(
                        total_sales=0,
                        average_sales=0,
                        record_count=0,
                        top_products=[],
                        unique_products=0,
                        unique_regions=0,
                        insights=[],
                    )

                sales_amounts = [float(item.get("sales_amount", 0)) for item in data]
                total_sales = sum(sales_amounts)
                avg_sales = total_sales / len(data) if data else 0

                product_sales = {}
                products, regions = set(), set()

                for item in data:
                    products.add(item.get("product", "Unknown"))
                    regions.add(item.get("region", "Unknown"))
                    product = item.get("product", "Unknown")
                    product_sales[product] = product_sales.get(product, 0) + float(
                        item.get("sales_amount", 0)
                    )

                top_products = sorted(
                    [
                        {"product": p, "total_sales": s}
                        for p, s in product_sales.items()
                    ],
                    key=lambda x: x["total_sales"],
                    reverse=True,
                )[:5]

                insights = self._generate_insights_from_data(
                    data, total_sales, avg_sales, products, regions
                )

                return DataSummary(
                    total_sales=total_sales,
                    average_sales=avg_sales,
                    record_count=len(data),
                    top_products=top_products,
                    unique_products=len(products),
                    unique_regions=len(regions),
                    insights=insights,
                )
            except Exception as e:
                logger.error(f"Error calculating in-memory enhanced summary: {e}")
                return DataSummary(
                    total_sales=0,
                    average_sales=0,
                    record_count=0,
                    top_products=[],
                    unique_products=0,
                    unique_regions=0,
                    insights=[],
                )

        try:
            async with self.pool.acquire() as conn:
                where_clause = "WHERE user_id = $1" if user_id else ""
                params = [user_id] if user_id else []

                summary = await self._fetchrow_with_retry(
                    conn,
                    f"""
                    SELECT 
                        COUNT(*) as record_count,
                        COALESCE(SUM(sales_amount), 0) as total_sales,
                        COALESCE(AVG(sales_amount), 0) as average_sales,
                        COUNT(DISTINCT product) as unique_products,
                        COUNT(DISTINCT region) as unique_regions,
                        MIN(date) as start_date,
                        MAX(date) as end_date
                    FROM sales_data {where_clause}
                    """,
                    *params,
                )

                top_products_raw = await self._fetch_with_retry(
                    conn,
                    f"""
                    SELECT product, SUM(sales_amount) as total_sales
                    FROM sales_data {where_clause}
                    GROUP BY product
                    ORDER BY total_sales DESC
                    LIMIT 5
                    """,
                    *params,
                )

                date_range = None
                if summary and summary["start_date"] and summary["end_date"]:
                    date_range = {
                        "start": str(summary["start_date"]),
                        "end": str(summary["end_date"]),
                    }

                top_products = (
                    [
                        {
                            "product": row["product"],
                            "total_sales": float(row["total_sales"]),
                        }
                        for row in top_products_raw
                    ]
                    if top_products_raw
                    else []
                )

                return DataSummary(
                    total_sales=float(summary["total_sales"]) if summary else 0,
                    average_sales=float(summary["average_sales"]) if summary else 0,
                    record_count=summary["record_count"] if summary else 0,
                    unique_products=summary["unique_products"] if summary else 0,
                    unique_regions=summary["unique_regions"] if summary else 0,
                    top_products=top_products,
                    date_range=date_range,
                    insights=[],
                )
        except Exception as e:
            logger.error(f"Error fetching enhanced summary: {e}")
            return DataSummary(
                total_sales=0,
                average_sales=0,
                record_count=0,
                top_products=[],
                unique_products=0,
                unique_regions=0,
                insights=[],
            )

    def _generate_insights_from_data(
        self,
        data: List[dict],
        total_sales: float,
        avg_sales: float,
        products: set,
        regions: set,
    ) -> List[str]:
        """Generate business insights from processed data"""
        insights = []

        if len(products) == 1:
            insights.append(
                "Single product focus - consider diversification opportunities"
            )
        elif len(products) > 10:
            insights.append(
                "High product diversity - monitor for portfolio optimization"
            )

        if avg_sales > 1000:
            insights.append("High-value transactions indicate premium customer segment")
        elif avg_sales < 50:
            insights.append(
                "Low transaction values suggest volume-based business model"
            )

        if len(regions) == 1:
            insights.append("Single region operation - expansion potential exists")
        elif len(regions) > 5:
            insights.append("Multi-region presence provides market diversification")

        # Product concentration analysis
        if len(data) > 0:
            product_sales = {}
            for item in data:
                product = item.get("product", "Unknown")
                product_sales[product] = product_sales.get(product, 0) + float(
                    item.get("sales_amount", 0)
                )

            if product_sales:
                top_product_share = max(product_sales.values()) / total_sales * 100
                if top_product_share > 50:
                    insights.append(
                        f"High concentration risk: top product represents {top_product_share:.1f}% of sales"
                    )

        return insights[:4]  # Limit to top 4 insights

    async def get_recent_articles(
        self, days: int = 7, user_id: Optional[int] = None
    ) -> List[Article]:
        if self.use_memory:
            cutoff_date = date.today()
            try:
                articles = [
                    Article(**art)
                    for art in self.memory_storage["articles"]
                    if (
                        art["generated_date"] >= cutoff_date
                        and (user_id is None or art.get("user_id") == user_id)
                    )
                ]
                return articles
            except Exception as e:
                logger.error(f"Error fetching recent articles from memory: {e}")
                return []

        try:
            async with self.pool.acquire() as conn:
                where_clause = (
                    "WHERE generated_date >= CURRENT_DATE - INTERVAL '{} days'".format(
                        days
                    )
                )
                if user_id:
                    where_clause += f" AND user_id = {user_id}"

                rows = await conn.fetch(
                    f"""
                    SELECT id, user_id, title, content, article_type, generated_date, created_at
                    FROM articles 
                    {where_clause}
                    ORDER BY created_at DESC
                    """
                )
                return [Article(**dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"Error fetching recent articles: {e}")
            return []

    async def get_storage_info(self) -> dict:
        if self.use_memory:
            return {
                "type": self.storage_type.value,
                "connected": not self.use_memory,
                "file_count": len(self.memory_storage["file_hashes"]),
                "user_count": len(self.memory_storage["users"]),
            }
        try:
            async with self.pool.acquire() as conn:
                file_count = await conn.fetchval("SELECT COUNT(*) FROM file_uploads")
                user_count = await conn.fetchval("SELECT COUNT(*) FROM users")
            return {
                "type": self.storage_type.value,
                "connected": not self.use_memory,
                "file_count": file_count if file_count is not None else 0,
                "user_count": user_count if user_count is not None else 0,
            }
        except Exception as e:
            logger.error(f"Error fetching storage info: {e}")
            return {
                "type": self.storage_type.value,
                "connected": not self.use_memory,
                "file_count": "Error",
                "user_count": "Error",
            }
