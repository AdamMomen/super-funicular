# Cold Outreach Email to Dirk Breeuwer (Corvera AI CTO)

**Subject:** Data integration layer + demand forecasting demo (GitHub)

---

Hi Dirk,

I saw Corvera's role for a Full-Stack / AI Product Engineer and built a minimal proof-of-work to show how I think about the problem.

The data integration layer is where Corvera's product either wins or loses. CPG ops data is fragmented—supplier confirmations in email, inventory in Airtable, sales in Shopify exports—and gluing that into a unified state an AI agent can act on is the hard part. I built a small demand forecasting module that ingests historical order CSV, runs ETL, applies a time-series model, and outputs 90-day inventory recommendations with a visual summary. It's structured so the ETL and data model could extend to Shopify APIs, EDI feeds, or email ingestion—the same pipeline that would feed an agentic system.

GitHub: https://github.com/AdamMomen/super-funicular

I'd welcome the chance to discuss how you're thinking about reliability and correctness in the pipelines that feed your agents.

Adam
