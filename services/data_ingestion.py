import pandas as pd
from typing import Dict, List, Tuple
import hashlib
import logging
from database.connection import Database
from lib.schemas import SalesData, UploadResponse, DataSummary

logger = logging.getLogger(__name__)


class DataProcessor:
    def __init__(self, db: Database):
        self.db = db

    def calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of file content"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    async def process_csv(self, file_path: str) -> UploadResponse:
        try:
            # Calculate file hash for duplicate detection
            file_hash = self.calculate_file_hash(file_path)

            # Check for duplicate
            is_duplicate = await self.db.check_file_duplicate(file_hash)
            if is_duplicate:
                summary = await self.db.get_enhanced_summary()
                return UploadResponse(
                    status="success",
                    rows_processed=0,
                    rows_stored=0,
                    summary=summary,
                    insights=["File already uploaded previously - skipping duplicate"],
                    file_hash=file_hash,
                    duplicate_upload=True,
                )

            # Process CSV
            df, processing_info = self._read_and_clean_csv(file_path)

            # Convert to typed data
            sales_data = self._convert_to_sales_data(df)

            # Store in database
            stored_count = await self.db.insert_sales_data_batch(sales_data)

            # Record successful upload
            await self.db.record_file_upload(file_hash, stored_count)

            # Get enhanced summary and insights
            summary = await self.db.get_enhanced_summary()
            insights = self._generate_insights(df, processing_info, summary)

            return UploadResponse(
                status="success",
                rows_processed=len(df),
                rows_stored=stored_count,
                summary=summary,
                insights=insights,
                file_hash=file_hash,
                duplicate_upload=False,
            )

        except Exception as e:
            logger.error(f"CSV processing error: {e}")
            # Return empty summary on error
            empty_summary = DataSummary(
                total_sales=0,
                average_sales=0,
                record_count=0,
                top_products=[],
                unique_products=0,
                unique_regions=0,
            )
            return UploadResponse(
                status="error",
                rows_processed=0,
                rows_stored=0,
                summary=empty_summary,
                insights=[f"Processing failed: {str(e)}"],
                file_hash="",
            )

    def _read_and_clean_csv(self, file_path: str) -> Tuple[pd.DataFrame, Dict]:
        """Read and clean CSV with detailed processing info"""
        # Read CSV
        df = pd.read_csv(file_path, encoding="utf-8")
        original_rows = len(df)

        # Clean column names
        df.columns = df.columns.str.lower().str.strip().str.replace(" ", "_")

        # Column mapping
        column_mapping = {
            "revenue": "sales_amount",
            "amount": "sales_amount",
            "total_sales": "sales_amount",
            "orders": "quantity",
            "units": "quantity",
            "qty": "quantity",
            "item": "product",
            "sku": "product",
            "product_category": "category",
            "location": "region",
            "market": "region",
        }

        df = df.rename(columns=column_mapping)

        # Handle dates
        date_columns = ["date", "order_date", "transaction_date"]
        date_parsed = False
        for col in date_columns:
            if col in df.columns:
                try:
                    df["date"] = pd.to_datetime(df[col], errors="coerce").dt.date
                    date_parsed = True
                    break
                except:
                    continue

        # Type conversion with error handling
        if "sales_amount" in df.columns:
            df["sales_amount"] = pd.to_numeric(
                df["sales_amount"], errors="coerce"
            ).fillna(0)

        if "quantity" in df.columns:
            df["quantity"] = (
                pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)
            )

        # Fill string columns
        string_columns = ["product", "category", "region"]
        for col in string_columns:
            if col in df.columns:
                df[col] = df[col].fillna("Unknown").astype(str)

        # **Remove rows where product is 'Unknown'**
        if "product" in df.columns:
            df = df[df["product"].str.lower() != "unknown"]

        # Remove completely empty rows
        df = df.dropna(how="all")
        final_rows = len(df)

        processing_info = {
            "original_rows": original_rows,
            "final_rows": final_rows,
            "rows_dropped": original_rows - final_rows,
            "date_parsed": date_parsed,
            "columns_mapped": len(set(df.columns) & set(column_mapping.values())),
        }

        return df, processing_info

    def _convert_to_sales_data(self, df: pd.DataFrame) -> List[SalesData]:
        """Convert DataFrame to typed SalesData objects"""
        sales_data = []
        for _, row in df.iterrows():
            try:
                data = SalesData(
                    date=row.get("date"),
                    product=str(row.get("product", "Unknown")),
                    category=str(row.get("category", "Unknown")),
                    sales_amount=float(row.get("sales_amount", 0)),
                    quantity=int(row.get("quantity", 0)),
                    region=str(row.get("region", "Unknown")),
                )
                sales_data.append(data)
            except Exception as e:
                logger.warning(f"Skipping invalid row: {e}")
                continue

        return sales_data

    def _generate_insights(
        self, df: pd.DataFrame, processing_info: Dict, summary: DataSummary
    ) -> List[str]:
        """Generate detailed insights from processed data"""
        insights = []

        # Data quality insights
        if processing_info["rows_dropped"] > 0:
            insights.append(
                f"Data cleaning: {processing_info['rows_dropped']} incomplete rows removed"
            )

        if processing_info["date_parsed"]:
            insights.append("Date column successfully parsed and standardized")

        # Business insights
        if summary.record_count > 0:
            insights.append(f"Processed {summary.record_count} sales transactions")
            insights.append(f"Total revenue: ${summary.total_sales:,.2f}")
            insights.append(f"Average transaction: ${summary.average_sales:.2f}")

            if summary.unique_products > 1:
                insights.append(
                    f"Product diversity: {summary.unique_products} unique products"
                )

            if summary.unique_regions > 1:
                insights.append(
                    f"Geographic spread: {summary.unique_regions} regions covered"
                )

            # Top performer insight
            if summary.top_products:
                top_product = summary.top_products[0]
                contribution = (top_product["total_sales"] / summary.total_sales) * 100
                insights.append(
                    f"Top product '{top_product['product']}' contributes {contribution:.1f}% of total sales"
                )

        return insights
