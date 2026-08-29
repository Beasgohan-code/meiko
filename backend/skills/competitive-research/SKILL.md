---
name: Competitive / Market Research
description: Run a structured competitive analysis or market research pass on a company, product, or topic with cited sources.
triggers: [competitor, competitive analysis, market research, compare products, vs]
---

# Competitive / Market Research

1. Call `update_plan` first with concrete steps, e.g.: identify competitors → search each →
   extract pricing/features/positioning → synthesize comparison → cite sources.
2. Use `web_search` for each entity separately (don't lump multiple companies into one query) —
   run at least 2-3 distinct searches per subject to triangulate facts (official site, a review site,
   recent news).
3. Use `fetch_url` on the most authoritative-looking result (usually the official pricing/product page)
   to pull exact details rather than trusting a snippet.
4. Synthesize into a markdown comparison table: columns = competitors, rows = pricing / key features /
   target audience / differentiators / notable weaknesses.
5. Always end with a short "so what" section — 2-3 sentences of actual insight/recommendation, not just
   a data dump.
6. Cite every non-obvious factual claim with a markdown link so the user can verify it themselves.
