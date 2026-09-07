# Investigation Intake

Classify the business question and identify only the semantic context needed to plan it.

Allowed intents: descriptive, comparative, diagnostic, ranking, trend, funnel,
product_analysis, marketing_analysis.

Use only table and metric names present below. An empty relevant list means all
available context is needed. Put uncertainty that does not block analysis in
`assumptions`. Put only material missing information that would change the metric,
time period, or comparison in `ambiguities`.

## Available Schema

{schema_context}

## Available Metrics

{metric_context}

## Question

{question}

## Output

Return one JSON object only:

{{
  "intent": "diagnostic",
  "primary_metric": "conversion_rate",
  "time_period": "Q3 2014",
  "comparison_period": "Q2 2014",
  "dimensions_to_consider": ["utm_source", "device_type"],
  "relevant_tables": ["website_sessions", "orders"],
  "relevant_metrics": ["sessions", "orders", "conversion_rate"],
  "assumptions": [],
  "ambiguities": []
}}
