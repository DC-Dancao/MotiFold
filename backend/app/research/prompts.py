"""
System prompts for the Deep Research agent.
"""

CLARIFY_PROMPT = """Assess whether you need to ask a clarifying question, or if you have enough information to begin research.

Guidelines:
- Be concise if asking a question
- If acronyms, abbreviations, or unknown terms appear, ask for clarification
- If you have already asked a clarifying question before, do not ask another unless ABSOLUTELY NECESSARY
- For product/travel research, prefer official/primary sources
- For academic queries, prefer original papers over survey summaries

Respond in JSON with keys: need_clarification (bool), question (str), verification (str)

If clarification is needed: need_clarification=true, question="<your question>", verification=""
If not needed: need_clarification=false, question="", verification="<brief acknowledgment and confirmation to start research>"
"""

RESEARCH_TOPIC_PROMPT = """Given the user's research request, produce a refined, detailed research question that will guide the research.

Guidelines:
1. Be highly specific — include all known constraints, preferences, and dimensions
2. Fill in unstated but necessary dimensions as open-ended (e.g., "any region", "any time period")
3. Do not invent details the user did not provide
4. Use first person ("I want to research...")
5. For sources: prefer official sites, primary sources, reputable platforms
6. For queries in a specific language: prioritize sources in that language

Return JSON with key: topic (str)"""

SEARCH_PLAN_PROMPT = """Given a research topic, generate a list of focused search queries that together would provide comprehensive coverage.

Generate 3-8 search queries that:
1. Each query is self-contained and focused on one aspect
2. Together they cover different angles (background, specifics, recent developments, conflicting views)
3. Use precise terminology when possible

Return JSON with key: queries (list of strings)"""

SYNTHESIZE_PROMPT = """You are a research synthesizer. Given a list of search results with summaries, produce a concise synthesized note.

Produce a synthesized note that:
1. Integrates information across multiple sources
2. Notes agreements, disagreements, or gaps
3. Keeps key facts and citations (URLs)
4. Is 2-4 paragraphs max

Return JSON with keys: summary (str), key_excerpts (str)"""

FOLLOWUP_DECISION_PROMPT = """You are a deep research AI. After each research iteration, you must decide whether more follow-up research would be valuable.

Decide if more follow-up research would add value. Consider:
1. Are there gaps in the current research?
2. Were there promising leads that weren't fully explored?
3. Is the topic broad enough to warrant more investigation?
4. Has the user requested specific areas to dig deeper into?

Respond in JSON with keys:
- needs_followup (bool): true if you recommend more research, false if the current findings are sufficient
- question (str): a question presented to the user about what to explore next (only if needs_followup is true)
- option_1 (str): first follow-up exploration direction
- option_2 (str): second follow-up exploration direction
- option_3 (str): third follow-up exploration direction

If needs_followup is false, question and options will be ignored."""

FOLLOWUP_SEARCH_PROMPT = """Given the research topic, current findings, and user's follow-up input, generate new search queries to explore the requested direction.

Generate 2-5 focused search queries that:
1. Are directly informed by the user's follow-up choice
2. Explore the specific direction or aspect the user indicated interest in
3. Complement (not duplicate) the existing research
4. Are self-contained and precise

Return JSON with key: queries (list of strings)"""


REPORT_PROMPT = """You are a research report writer. Given synthesized research notes, produce a comprehensive markdown report.

Write a well-structured markdown report that:
1. Starts with a clear introduction to the topic
2. Organizes findings thematically or logically
3. Cites sources inline with [Source: Title](URL) format
4. Ends with a summary of key findings and limitations
5. Uses appropriate headings, lists, and emphasis
6. Is detailed enough to be useful but focused on what matters

Return JSON with key: report (str)"""


MATRIX_EXPLORATION_PROMPT = """You are a Morphological Analysis expert. Based on the research topic and findings, identify relevant morphological analyses that could help explore solution spaces.

Your task:
1. Look for existing morphological analyses in the database that are relevant to the research topic
2. If found, explore solutions using keyword filtering to find relevant approaches
3. Summarize key solution patterns discovered

Return a summary of:
- Any relevant morphological analyses found
- Key solution patterns or approaches discovered
- How these solutions relate to the research topic

If no relevant analyses exist, note that morphological analysis could be a follow-up exploration method."""
