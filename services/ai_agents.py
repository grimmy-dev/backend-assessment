import asyncio
from typing import Dict, List
from database.connection import Database
from lib.schemas import DataSummary, GenerationResponse
import logging
from datetime import date
from google import genai
from google.genai import types
from config import settings

logger = logging.getLogger(__name__)

client = genai.Client(api_key=settings.google_ai_api_key)


class AIService:
    def __init__(self, db: Database):
        self.db = db
        self.llm = client.models
        self.agents = {
            "market_analyst": "Market Analyst",
            "business_reporter": "Business Reporter",
            "sales_strategist": "Sales Strategist",
            "trend_forecaster": "Trend Forecaster",
            "executive_briefer": "Executive Briefer",
        }

    async def generate_articles_with_check(
        self, user_id: int = None
    ) -> GenerationResponse:
        """Generate articles with concurrent processing after checking data availability"""
        storage_info = await self.db.get_storage_info()
        summary = await self.db.get_enhanced_summary(user_id)

        if storage_info["file_count"] == 0 or summary.record_count == 0:
            return GenerationResponse(
                status="error",
                articles_generated=0,
                articles=[],
                generation_date=str(date.today()),
                data_summary=summary,
            )

        # Generate all articles concurrently
        articles = await self._generate_articles_concurrent(summary)

        # Store articles concurrently
        stored_articles = await self._store_articles_concurrent(articles, user_id)

        return GenerationResponse(
            status="success",
            articles_generated=len(stored_articles),
            articles=stored_articles,
            generation_date=str(date.today()),
            data_summary=summary,
        )

    async def _generate_articles_concurrent(self, summary: DataSummary) -> List[Dict]:
        """Generate all articles concurrently using asyncio.gather"""
        summary_text = self._format_summary(summary)

        # Create all generation tasks
        tasks = [
            self._generate_single_article(agent_type, agent_name, summary_text, summary)
            for agent_type, agent_name in self.agents.items()
        ]

        # Run all generations concurrently
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out failed generations
            articles = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    agent_type = list(self.agents.keys())[i]
                    logger.error(f"Failed to generate {agent_type}: {result}")
                else:
                    articles.append(result)

            return articles
        except Exception as e:
            logger.error(f"Error in concurrent generation: {e}")
            return []

    async def _generate_single_article(
        self, agent_type: str, agent_name: str, summary_text: str, summary: DataSummary
    ) -> Dict:
        """Generate a single article asynchronously"""
        try:
            content = await self._generate_content(agent_type, summary_text, summary)
            title = f"{agent_name} Report - {date.today().strftime('%B %Y')}"
            return {"title": title, "content": content, "agent_type": agent_type}
        except Exception as e:
            logger.error(f"Error generating {agent_type}: {e}")
            raise

    async def _store_articles_concurrent(
        self, articles: List[Dict], user_id: int = None
    ) -> List:
        """Store multiple articles concurrently"""
        if not articles:
            return []

        tasks = [
            self.db.insert_article(
                article["title"], article["content"], article["agent_type"], user_id
            )
            for article in articles
        ]

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            # Filter out None values and exceptions properly
            stored_articles = [
                result
                for result in results
                if result is not None and not isinstance(result, Exception)
            ]
            return stored_articles
        except Exception as e:
            logger.error(f"Error storing articles concurrently: {e}")
            return []

    def _format_summary(self, summary: DataSummary) -> str:
        """Format summary for article generation"""
        parts = [
            f"Total Sales: ${summary.total_sales:,.2f}",
            f"Transactions: {summary.record_count:,}",
            f"Average Order: ${summary.average_sales:.2f}",
            f"Product Portfolio: {summary.unique_products} products",
            f"Market Coverage: {summary.unique_regions} regions",
        ]

        if summary.date_range:
            parts.append(
                f"Period: {summary.date_range['start']} to {summary.date_range['end']}"
            )

        return " | ".join(parts)

    async def _generate_content(
        self, agent_type: str, summary_text: str, summary: DataSummary
    ) -> str:
        """Generate article content using Gemini with enhanced prompts"""

        prompts = {
            "market_analyst": """Role: Senior Market Analyst
            You're analyzing performance data for strategic decision-making. Focus on:
            - Market position and competitive implications
            - Revenue concentration risks and opportunities  
            - Customer segment analysis based on transaction patterns
            - Growth trajectory and sustainability factors
            - Strategic recommendations for market expansion
            Tone: Analytical, data-driven, strategic. Write for C-suite audience.""",
            "business_reporter": """Role: Business Journalist
            Write a compelling business story from this data. Focus on:
            - The narrative behind the numbers (growth story, market dynamics)
            - Industry context and performance benchmarks
            - Key success factors and potential challenges
            - Future outlook and market implications
            - What stakeholders should know about this performance
            Tone: Engaging, informative, objective. Write for informed business readers.""",
            "sales_strategist": """Role: Sales Strategy Director  
            Develop actionable sales insights and tactics. Focus on:
            - High-performing products and regions for scaling
            - Cross-selling and upselling opportunities
            - Channel optimization and resource allocation
            - Customer acquisition vs retention balance
            - Specific tactical recommendations for sales teams
            Tone: Action-oriented, practical, results-focused. Write for sales leadership.""",
            "trend_forecaster": """Role: Business Trend Analyst
            Identify patterns and predict future developments. Focus on:
            - Emerging trends in product performance and customer behavior
            - Seasonal patterns and cyclical opportunities
            - Market shifts and disruption indicators
            - Future growth catalysts and risk factors
            - Predictive insights for strategic planning
            Tone: Forward-thinking, analytical, trend-focused. Write for strategic planners.""",
            "executive_briefer": """Role: Executive Advisor
            Create a concise executive summary for leadership decisions. Focus on:
            - Critical performance metrics and their business impact
            - Key risks and opportunities requiring attention
            - Resource allocation recommendations
            - Strategic priorities and next steps
            - Bottom-line implications for business objectives
            Tone: Concise, decisive, executive-level. Write for time-constrained leaders.""",
        }

        system_instruction = prompts.get(
            agent_type, "Write a comprehensive business analysis."
        )

        # Enhanced context with insights
        context_parts = [f"Performance Overview: {summary_text}"]

        if summary.top_products:
            valid_products = [
                p
                for p in summary.top_products
                if p["product"] and p["product"].lower() != "unknown"
            ]
            if valid_products:
                top_products_text = ", ".join(
                    f"{p['product']} (${p['total_sales']:,.0f})"
                    for p in valid_products[:3]
                )
                context_parts.append(f"Leading Products: {top_products_text}")

        if summary.insights:
            context_parts.append(f"Key Insights: {'; '.join(summary.insights[:3])}")

        if summary.date_range:
            context_parts.append(
                f"Analysis Period: {summary.date_range['start']} to {summary.date_range['end']}"
            )

        context = "\n".join(context_parts)

        # Async Gemini call
        try:
            response = self.llm.generate_content(
                model="gemini-2.0-flash-lite",
                contents=f"{system_instruction}\n\nBusiness Data:\n{context}\n\nGenerate a focused 250-300 word analysis with specific insights and actionable recommendations.",
                config=types.GenerateContentConfig(
                    max_output_tokens=900,
                    temperature=0.7,
                    response_mime_type="text/plain",
                ),
            )
            return response.text
        except Exception as e:
            logger.error(f"Error calling Gemini API: {e}")
            return f"Unable to generate {agent_type} content at this time. Please try again later."
