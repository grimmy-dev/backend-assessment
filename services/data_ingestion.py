import pandas as pd
from typing import Dict, List, Tuple, Optional
import hashlib
import logging
from database.connection import Database
from lib.schemas import SalesData, UploadResponse, DataSummary

logger = logging.getLogger(__name__)


class DataProcessor:
    def __init__(self, db: Database):
        self.db = db

        # Dynamic column mapping - extensible for different CSV formats
        self.column_mappings = {
            # Date columns
            "date": [
                "date",
                "order_date",
                "transaction_date",
                "sale_date",
                "created_date",
                "timestamp",
            ],
            # Sales amount columns
            "sales_amount": [
                "sales_amount",
                "revenue",
                "amount",
                "total_sales",
                "value",
                "price",
                "cost",
                "sales",
                "total_amount",
            ],
            # Product columns
            "product": [
                "product",
                "item",
                "sku",
                "product_name",
                "item_name",
                "product_id",
                "name",
            ],
            # Category columns
            "category": [
                "category",
                "product_category",
                "type",
                "group",
                "segment",
                "class",
            ],
            # Quantity columns
            "quantity": [
                "quantity",
                "qty",
                "units",
                "orders",
                "count",
                "volume",
                "items",
            ],
            # Region columns
            "region": [
                "region",
                "location",
                "market",
                "area",
                "territory",
                "country",
                "state",
                "city",
            ],
        }

    def calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of file content"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    async def process_csv(
        self, file_path: str, filename: str, user_id: Optional[int] = None
    ) -> UploadResponse:
        try:
            # Calculate file hash for duplicate detection
            file_hash = self.calculate_file_hash(file_path)

            # Check for duplicate
            is_duplicate = await self.db.check_file_duplicate(file_hash, user_id)
            if is_duplicate:
                summary = await self.db.get_enhanced_summary(user_id)
                return UploadResponse(
                    status="success",
                    rows_processed=0,
                    rows_stored=0,
                    summary=summary,
                    insights=["File already uploaded previously - skipping duplicate"],
                    file_hash=file_hash,
                    duplicate_upload=True,
                )

            # Dynamic CSV processing
            df, processing_info = self._read_and_clean_csv_dynamic(file_path)

            # Record file upload first to get file_upload_id
            file_upload_id = await self.db.record_file_upload(
                file_hash, filename, len(df), user_id
            )

            # Convert to typed data with file reference
            sales_data = self._convert_to_sales_data(df, file_upload_id)

            # Store in database
            stored_count = await self.db.insert_sales_data_batch(
                sales_data, user_id, file_upload_id
            )

            # Get enhanced summary with insights
            summary = await self.db.get_enhanced_summary(user_id)
            insights = self._generate_comprehensive_insights(
                df, processing_info, summary
            )

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
            empty_summary = DataSummary(
                total_sales=0,
                average_sales=0,
                record_count=0,
                top_products=[],
                unique_products=0,
                unique_regions=0,
                insights=[],
            )
            return UploadResponse(
                status="error",
                rows_processed=0,
                rows_stored=0,
                summary=empty_summary,
                insights=[f"Processing failed: {str(e)}"],
                file_hash="",
            )

    def _read_and_clean_csv_dynamic(self, file_path: str) -> Tuple[pd.DataFrame, Dict]:
        """Dynamically read and clean CSV with intelligent column detection"""
        # Try different encodings and separators
        encoding_options = ["utf-8", "latin-1", "cp1252"]
        separator_options = [",", ";", "\t", "|"]

        df = None
        for encoding in encoding_options:
            for sep in separator_options:
                try:
                    test_df = pd.read_csv(
                        file_path, encoding=encoding, sep=sep, nrows=5
                    )
                    if len(test_df.columns) > 1:  # Valid CSV structure
                        df = pd.read_csv(file_path, encoding=encoding, sep=sep)
                        break
                except:
                    continue
            if df is not None:
                break

        if df is None:
            raise ValueError("Could not parse CSV file with standard formats")

        original_rows = len(df)
        original_columns = list(df.columns)

        # Clean column names
        df.columns = (
            df.columns.str.lower()
            .str.strip()
            .str.replace(" ", "_")
            .str.replace("[^a-z0-9_]", "", regex=True)
        )

        # Dynamic column mapping
        mapped_columns = {}
        for target_col, possible_names in self.column_mappings.items():
            for col in df.columns:
                if any(possible in col for possible in possible_names):
                    mapped_columns[col] = target_col
                    break

        df = df.rename(columns=mapped_columns)

        # Smart date parsing
        date_parsed = self._parse_dates_smart(df)

        # Dynamic numeric conversion
        numeric_stats = self._convert_numerics_smart(df)

        # Handle categorical data
        categorical_info = self._process_categorical_smart(df)

        # Quality filtering
        quality_info = self._apply_quality_filters(df)

        final_rows = len(df)

        processing_info = {
            "original_rows": original_rows,
            "final_rows": final_rows,
            "rows_dropped": original_rows - final_rows,
            "original_columns": original_columns,
            "mapped_columns": mapped_columns,
            "date_parsed": date_parsed,
            "numeric_conversions": numeric_stats,
            "categorical_processing": categorical_info,
            "quality_filters": quality_info,
        }

        return df, processing_info

    def _parse_dates_smart(self, df: pd.DataFrame) -> bool:
        """Smart date parsing with multiple format detection"""
        date_formats = [
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%d/%m/%Y",
            "%Y/%m/%d",
            "%m-%d-%Y",
            "%d-%m-%Y",
            "%Y%m%d",
        ]

        for col in df.columns:
            if "date" in col and col in df.columns:
                for fmt in date_formats:
                    try:
                        df["date"] = pd.to_datetime(
                            df[col], format=fmt, errors="coerce"
                        ).dt.date
                        if df["date"].notna().sum() > len(df) * 0.8:  # 80% success rate
                            return True
                    except:
                        continue

                # Fallback to pandas auto-detection
                try:
                    df["date"] = pd.to_datetime(df[col], errors="coerce").dt.date
                    if df["date"].notna().sum() > len(df) * 0.5:
                        return True
                except:
                    continue

        return False

    def _convert_numerics_smart(self, df: pd.DataFrame) -> Dict:
        """Smart numeric conversion with outlier detection"""
        conversions = {}

        # Sales amount conversion
        if "sales_amount" in df.columns:
            original_na = df["sales_amount"].isna().sum()
            df["sales_amount"] = pd.to_numeric(
                df["sales_amount"].astype(str).str.replace(r"[,$]", "", regex=True),
                errors="coerce",
            )

            # Outlier detection and capping
            if df["sales_amount"].notna().sum() > 0:
                q99 = df["sales_amount"].quantile(0.99)
                outliers = (df["sales_amount"] > q99 * 3).sum()
                if outliers > 0:
                    df.loc[df["sales_amount"] > q99 * 3, "sales_amount"] = q99
                    conversions["sales_amount_outliers_capped"] = outliers

            df["sales_amount"] = df["sales_amount"].fillna(0)
            conversions["sales_amount_na_filled"] = (
                df["sales_amount"].isna().sum() - original_na
            )

        # Quantity conversion
        if "quantity" in df.columns:
            df["quantity"] = (
                pd.to_numeric(df["quantity"], errors="coerce").fillna(1).astype(int)
            )
            conversions["quantity_defaulted_to_1"] = (df["quantity"] == 1).sum()

        return conversions

    def _process_categorical_smart(self, df: pd.DataFrame) -> Dict:
        """Smart categorical data processing"""
        info = {}

        categorical_columns = ["product", "category", "region"]
        for col in categorical_columns:
            if col in df.columns:
                # Clean and standardize
                df[col] = df[col].astype(str).str.strip().str.title()

                # Replace obvious nulls
                null_patterns = ["nan", "null", "none", "", "n/a", "na"]
                df[col] = df[col].replace(
                    {pattern.title(): "Unknown" for pattern in null_patterns}
                )
                df[col] = df[col].fillna("Unknown")

                # Track unique values
                info[f"{col}_unique_count"] = df[col].nunique()
                info[f"{col}_unknown_count"] = (df[col] == "Unknown").sum()

        return info

    def _apply_quality_filters(self, df: pd.DataFrame) -> Dict:
        """Apply intelligent quality filters"""
        initial_count = len(df)
        filters_applied = {}

        # Remove rows where ALL key fields are missing/unknown
        key_fields = ["product", "sales_amount"]
        before_filter = len(df)

        # Filter out completely invalid rows
        if "product" in df.columns:
            invalid_products = df["product"].isin(["Unknown", "", "Nan", "None"])
            if "sales_amount" in df.columns:
                zero_sales = (df["sales_amount"] == 0) | (df["sales_amount"].isna())
                completely_invalid = invalid_products & zero_sales
                df = df[~completely_invalid]
                filters_applied["invalid_product_zero_sales"] = completely_invalid.sum()

        # Remove obvious duplicates
        if len(df) > 1:
            duplicates = df.duplicated().sum()
            if duplicates > 0:
                df = df.drop_duplicates()
                filters_applied["duplicates_removed"] = duplicates

        # Remove extreme outliers (beyond 99.9th percentile)
        if "sales_amount" in df.columns and len(df) > 10:
            q999 = df["sales_amount"].quantile(0.999)
            extreme_outliers = (df["sales_amount"] > q999 * 5).sum()
            if extreme_outliers > 0:
                df = df[df["sales_amount"] <= q999 * 5]
                filters_applied["extreme_outliers_removed"] = extreme_outliers

        filters_applied["total_rows_filtered"] = initial_count - len(df)
        return filters_applied

    def _convert_to_sales_data(
        self, df: pd.DataFrame, file_upload_id: Optional[int] = None
    ) -> List[SalesData]:
        """Convert DataFrame to typed SalesData objects with file reference"""
        sales_data = []
        for _, row in df.iterrows():
            try:
                data = SalesData(
                    date=row.get("date"),
                    product=str(row.get("product", "Unknown")),
                    category=str(row.get("category", "Unknown")),
                    sales_amount=float(row.get("sales_amount", 0)),
                    quantity=int(row.get("quantity", 1)),
                    region=str(row.get("region", "Unknown")),
                    file_upload_id=file_upload_id,
                )
                sales_data.append(data)
            except Exception as e:
                logger.warning(f"Skipping invalid row: {e}")
                continue

        return sales_data

    def _generate_comprehensive_insights(
        self, df: pd.DataFrame, processing_info: Dict, summary: DataSummary
    ) -> List[str]:
        """Generate comprehensive business insights from processed data"""
        insights = []

        # Data quality insights
        if processing_info["rows_dropped"] > 0:
            drop_rate = (
                processing_info["rows_dropped"] / processing_info["original_rows"]
            ) * 100
            insights.append(
                f"Data quality: {drop_rate:.1f}% of rows cleaned/filtered for better accuracy"
            )

        # Business performance insights
        if summary.record_count > 0:
            insights.append(
                f"Dataset contains {summary.record_count:,} validated transactions worth ${summary.total_sales:,.0f}"
            )

            # Transaction size analysis
            if summary.average_sales > 500:
                insights.append(
                    f"High-value transactions (avg ${summary.average_sales:.0f}) suggest premium market positioning"
                )
            elif summary.average_sales < 50:
                insights.append(
                    f"Low transaction values (avg ${summary.average_sales:.0f}) indicate volume-driven business model"
                )

            # Portfolio concentration analysis
            if summary.top_products and len(summary.top_products) > 0:
                top_product = summary.top_products[0]
                concentration = (top_product["total_sales"] / summary.total_sales) * 100

                if concentration > 60:
                    insights.append(
                        f"High concentration risk: '{top_product['product']}' dominates with {concentration:.1f}% of sales"
                    )
                elif concentration < 20 and summary.unique_products > 5:
                    insights.append(
                        f"Well-diversified portfolio: top product represents only {concentration:.1f}% of sales"
                    )

            # Market coverage insights
            if summary.unique_regions == 1:
                insights.append(
                    "Single-region operation presents geographic expansion opportunities"
                )
            elif summary.unique_regions > 5:
                insights.append(
                    f"Strong geographic diversification across {summary.unique_regions} regions reduces market risk"
                )

            # Product portfolio insights
            if summary.unique_products > 20:
                insights.append(
                    "Extensive product catalog may benefit from portfolio optimization analysis"
                )
            elif summary.unique_products < 5:
                insights.append(
                    "Limited product range suggests potential for line extension opportunities"
                )

        # Processing insights
        if processing_info.get("mapped_columns"):
            insights.append(
                f"Successfully mapped {len(processing_info['mapped_columns'])} columns to standard format"
            )

        # Advanced statistical insights
        if "sales_amount" in df.columns and len(df) > 10:
            cv = df["sales_amount"].std() / df["sales_amount"].mean()
            if cv > 1.5:
                insights.append(
                    "High sales variability detected - investigate demand patterns and pricing strategy"
                )
            elif cv < 0.3:
                insights.append(
                    "Consistent transaction values suggest stable customer base and pricing"
                )

        # Seasonal/temporal insights if dates available
        if "date" in df.columns and df["date"].notna().sum() > 0:
            date_span = (df["date"].max() - df["date"].min()).days
            if date_span > 90:
                insights.append(
                    f"Multi-quarter dataset ({date_span} days) enables trend analysis and forecasting"
                )

        return insights[:6]  # Return top 6 most relevant insights
