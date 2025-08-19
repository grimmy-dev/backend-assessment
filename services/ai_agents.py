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

    async def generate_articles_with_check(self) -> GenerationResponse:
        """Generate articles after checking data availability"""
        storage_info = await self.db.get_storage_info()
        summary = await self.db.get_enhanced_summary()

        if storage_info["file_count"] == 0:
            return GenerationResponse(
                status="error",
                articles_generated=0,
                articles=[],
                generation_date=str(date.today()),
                data_summary=summary,
            )

        if summary.record_count == 0:
            return GenerationResponse(
                status="error",
                articles_generated=0,
                articles=[],
                generation_date=str(date.today()),
                data_summary=summary,
            )

        articles = await self._generate_articles(summary)

        stored_articles = []
        for article_data in articles:
            stored = await self.db.insert_article(
                article_data["title"],
                article_data["content"],
                article_data["agent_type"],
            )
            stored_articles.append(stored)

        return GenerationResponse(
            status="success",
            articles_generated=len(stored_articles),
            articles=stored_articles,
            generation_date=str(date.today()),
            data_summary=summary,
        )

    async def _generate_articles(self, summary: DataSummary) -> List[Dict]:
        """Generate article content based on data summary"""
        articles = []
        summary_text = self._format_summary(summary)

        for agent_type, agent_name in self.agents.items():
            try:
                content = await self._generate_content(
                    agent_type, summary_text, summary
                )
                title = f"{agent_name} Report - {date.today().strftime('%B %Y')}"
                articles.append(
                    {"title": title, "content": content, "agent_type": agent_type}
                )
            except Exception as e:
                logger.error(f"Error generating {agent_type}: {e}")

        return articles

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
        """Generate ~200–300 word article with distinct agent persona using Gemini"""

        prompts = {
            "market_analyst": """Role: Market Analyst
            Think like a consultant reviewing a client’s quarterly numbers. Your job is to turn raw sales data into sharp insights.
            Instructions:
            - Do not repeat the numbers plainly — explain what they *mean*.
            - Identify drivers behind performance: product concentration, transaction size, regional spread.
            - Call out risks (e.g., overdependence, lack of diversity, volatility).
            - Highlight 2–3 opportunities where the client can realistically grow.
            Tone: professional, concise, critical but constructive. Aim for actionable intelligence, not just description.""",
            "business_reporter": """Role: Business Reporter
            Imagine you’re writing a short Financial Times/WSJ-style article about these results.
            Instructions:
            - Find the “story” in the numbers (is it strong growth, overreliance, or unusual order sizes?).
            - Compare performance against what a reader might expect of a healthy business.
            - Explain why these results matter for stakeholders (investors, customers, competitors).
            Tone: clear, engaging, slightly narrative. Avoid corporate fluff; write like you’re informing the public with a crisp news brief.""",
            "sales_strategist": """Role: Sales Strategist
            You are briefing a sales team on how to turn this data into wins.
            Instructions:
            - Focus only on insights that can lead to action (upselling, new regions, product mix).
            - Identify weak spots or bottlenecks and suggest tactical moves.
            - End with 2–3 clear, practical recommendations.
            Tone: direct, motivational, no jargon. Write as if your advice will be executed immediately.""",
            "trend_forecaster": """Role: Trend Forecaster
            Your goal is to read signals from the current data and project what’s next.
            Instructions:
            - Highlight anomalies or patterns that suggest a future shift.
            - Identify where growth is likely to accelerate or stall.
            - Connect today’s results to medium-term trends (e.g., reliance on high-value orders, lack of product diversity).
            Tone: thoughtful, predictive, forward-looking — but grounded in evidence, not speculation.""",
            "executive_briefer": """Role: Executive Briefer
            You are preparing a 1-page CEO update.
            Instructions:
            - Strip away all noise — focus only on the 2–3 most important takeaways.
            - Frame each takeaway as an implication (e.g., “High reliance on a single product increases concentration risk”).
            - Conclude with 1–2 clear priorities for leadership to consider.
            Tone: sharp, confident, business-focused. Imagine the CEO has 60 seconds to read this — make it count.""",
        }

        system_instruction = prompts.get(
            agent_type, "Write a 200–300 word business summary."
        )

        context_parts = [f"Summary: {summary_text}"]

        if summary.top_products:
            valid_products = [
                p
                for p in summary.top_products
                if p["product"] and p["product"].lower() != "unknown"
            ]
            if valid_products:
                top_products_text = ", ".join(
                    f"{p['product']} (${p['total_sales']:,.2f})"
                    for p in valid_products[:2]
                )
                context_parts.append(f"Top Products: {top_products_text}")

        if summary.date_range:
            context_parts.append(
                f"Date Range: {summary.date_range['start']} to {summary.date_range['end']}"
            )

        context = "\n".join(context_parts)

        # Gemini call (async safe)
        response = self.llm.generate_content(
            model="gemini-2.0-flash-lite",
            contents=f"{system_instruction}\n\nUse the following data:\n{context}\n\nLength: 200–300 words.",
            config=types.GenerateContentConfig(
                max_output_tokens=800,
                temperature=0.7,
                response_mime_type="text/plain",
            ),
        )

        return response.text
