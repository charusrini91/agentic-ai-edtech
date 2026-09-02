# iwAIIS Agentic AI EdTech Working Model

## Run locally
pip install -r agentic_ai_edtech_requirements.txt
streamlit run agentic_ai_edtech_app.py

## Optional LLM baseline
Set OPENAI_API_KEY and optionally OPENAI_MODEL.

The default prototype is a transparent heuristic implementation. It is useful for demonstrating the agent pipeline and collecting preliminary labeled data. For the paper, use a frozen held-out test set and an actual single-LLM baseline; do not report the heuristic fallback as an LLM experiment.
