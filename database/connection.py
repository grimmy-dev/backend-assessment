import asyncpg
import asyncpg.exceptions
from typing import Optional, List
from datetime import date, datetime
from lib.schemas import SalesData, Article, DataSummary, StorageType
import logging

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, database_url: str = ""):
        self.database_url = database_url
        self.pool: Optional[asyncpg.Pool] = None
        self.use_memory = not database_url
        self.memory_storage = {
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
                    statement_cache_size=50,  # default cache size
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
                await self._execute_with_retry(
                    conn,
                    """
                    CREATE TABLE IF NOT EXISTS sales_data (
                        id SERIAL PRIMARY KEY,
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
                await self._execute_with_retry(
                    conn,
                    """
                    CREATE TABLE IF NOT EXISTS articles (
                        id SERIAL PRIMARY KEY,
                        title VARCHAR(500),
                        content TEXT,
                        article_type VARCHAR(100),
                        generated_date DATE DEFAULT CURRENT_DATE,
                        created_at TIMESTAMP DEFAULT NOW()
                    );
                    """,
                )
                await self._execute_with_retry(
                    conn,
                    """
                    CREATE TABLE IF NOT EXISTS file_uploads (
                        id SERIAL PRIMARY KEY,
                        file_hash VARCHAR(64) UNIQUE,
                        upload_date TIMESTAMP DEFAULT NOW(),
                        record_count INTEGER
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

    async def check_file_duplicate(self, file_hash: str) -> bool:
        if self.use_memory:
            return file_hash in self.memory_storage["file_hashes"]

        try:
            async with self.pool.acquire() as conn:
                result = await self._fetchrow_with_retry(
                    conn,
                    "SELECT EXISTS(SELECT 1 FROM file_uploads WHERE file_hash=$1) AS exists;",
                    file_hash,
                )
            return result["exists"] if result else False
        except Exception as e:
            logger.error(f"Error checking file duplicate: {e}")
            return False

    async def record_file_upload(self, file_hash: str, record_count: int):
        if self.use_memory:
            self.memory_storage["file_hashes"].add(file_hash)
            self.memory_storage["metadata"]["last_upload"] = datetime.now()
            return
        try:
            async with self.pool.acquire() as conn:
                await self._execute_with_retry(
                    conn,
                    "INSERT INTO file_uploads(file_hash, record_count) VALUES($1, $2) ON CONFLICT DO NOTHING",
                    file_hash,
                    record_count,
                )
        except Exception as e:
            logger.error(f"Error recording file upload: {e}")

    async def insert_sales_data_batch(self, data_list: List[SalesData]) -> int:
        if not data_list:
            return 0
        if self.use_memory:
            for item in data_list:
                item_dict = item.dict()
                item_dict["id"] = len(self.memory_storage["sales_data"]) + 1
                item_dict["created_at"] = datetime.now()
                self.memory_storage["sales_data"].append(item_dict)
            return len(data_list)

        records = [
            (
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
                        INSERT INTO sales_data(date, product, category, sales_amount, quantity, region)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        """,
                        records,
                    )
                except asyncpg.exceptions.InvalidCachedStatementError:
                    logger.warning(
                        "InvalidCachedStatementError on executemany, retrying once"
                    )
                    await conn.executemany(
                        """
                        INSERT INTO sales_data(date, product, category, sales_amount, quantity, region)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        """,
                        records,
                    )
            return len(records)
        except Exception as e:
            logger.error(f"Error inserting sales data batch: {e}")
            return 0

    async def insert_article(
        self, title: str, content: str, article_type: str
    ) -> Optional[Article]:
        if self.use_memory:
            try:
                article_data = {
                    "id": len(self.memory_storage["articles"]) + 1,
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
                    INSERT INTO articles(title, content, article_type)
                    VALUES ($1, $2, $3)
                    RETURNING id, title, content, article_type, generated_date, created_at
                    """,
                    title,
                    content,
                    article_type,
                )
                return Article(**dict(row)) if row else None
        except Exception as e:
            logger.error(f"Error inserting article: {e}")
            return None

    async def get_enhanced_summary(self) -> DataSummary:
        if self.use_memory:
            try:
                data = self.memory_storage["sales_data"]
                if not data:
                    return DataSummary(
                        total_sales=0,
                        average_sales=0,
                        record_count=0,
                        top_products=[],
                        unique_products=0,
                        unique_regions=0,
                    )
                sales_amounts = [float(item.get("sales_amount", 0)) for item in data]
                total_sales = sum(sales_amounts)
                avg_sales = total_sales / len(data) if data else 0

                product_sales = {}
                products = set()
                regions = set()
                dates = []

                for item in data:
                    products.add(item.get("product", "Unknown"))
                    regions.add(item.get("region", "Unknown"))
                    if item.get("date"):
                        dates.append(item["date"])
                    product_sales[item.get("product", "Unknown")] = product_sales.get(
                        item.get("product", "Unknown"), 0
                    ) + float(item.get("sales_amount", 0))

                top_products = sorted(
                    [
                        {"product": p, "total_sales": s}
                        for p, s in product_sales.items()
                    ],
                    key=lambda x: x["total_sales"],
                    reverse=True,
                )[:5]

                date_range = None
                if dates:
                    dates.sort()
                    date_range = {"start": str(dates[0]), "end": str(dates[-1])}

                return DataSummary(
                    total_sales=total_sales,
                    average_sales=avg_sales,
                    record_count=len(data),
                    top_products=top_products,
                    unique_products=len(products),
                    unique_regions=len(regions),
                    date_range=date_range,
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
                )

        try:
            async with self.pool.acquire() as conn:
                summary = await self._fetchrow_with_retry(
                    conn,
                    """
                    SELECT 
                        COUNT(*) as record_count,
                        COALESCE(SUM(sales_amount), 0) as total_sales,
                        COALESCE(AVG(sales_amount), 0) as average_sales,
                        COUNT(DISTINCT product) as unique_products,
                        COUNT(DISTINCT region) as unique_regions,
                        MIN(date) as start_date,
                        MAX(date) as end_date
                    FROM sales_data
                    """,
                )

                top_products_raw = await self._fetch_with_retry(
                    conn,
                    """
                    SELECT product, SUM(sales_amount) as total_sales
                    FROM sales_data
                    GROUP BY product
                    ORDER BY total_sales DESC
                    LIMIT 5
                    """,
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
            )

    async def get_recent_articles(self, days: int = 7) -> List[Article]:
        if self.use_memory:
            cutoff_date = date.today()
            try:
                articles = [
                    Article(**art)
                    for art in self.memory_storage["articles"]
                    if art["generated_date"] >= cutoff_date
                ]
                return articles
            except Exception as e:
                logger.error(f"Error fetching recent articles from memory: {e}")
                return []

        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, title, content, article_type, generated_date, created_at
                    FROM articles 
                    WHERE generated_date >= CURRENT_DATE - INTERVAL '{} days'
                    ORDER BY created_at DESC
                    """.format(
                        days
                    )
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
            }
        try:
            async with self.pool.acquire() as conn:
                count = await conn.fetchval("SELECT COUNT(*) FROM file_uploads")
            return {
                "type": self.storage_type.value,
                "connected": not self.use_memory,
                "file_count": count if count is not None else 0,
            }
        except Exception as e:
            logger.error(f"Error fetching file count from database: {e}")
            return {
                "type": self.storage_type.value,
                "connected": not self.use_memory,
                "file_count": "Error",
            }
