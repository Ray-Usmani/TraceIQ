# Investigation Planner

Create the minimum SQL-only investigation needed to answer the question. Do not
write SQL. Target 2 to 6 steps and never exceed {max_steps}. Establish the
baseline before segmenting it. Every step must be independently executable from
the original question and semantic context; do not depend on a value that a prior
step has not yet identified. Adaptive drilling is implemented in a later phase.

## Question

{question}

## Intake

{intake}

## Relevant Schema

{schema_context}

## Relevant Metrics

{metric_context}

## Output

Return one JSON object only. Step IDs are assigned by the server:

{{
  "objective": "Confirm and segment the reported conversion decline.",
  "steps": [
    {{
      "question": "Calculate monthly sessions, orders, and conversion rate for the requested periods.",
      "tool": "sql",
      "purpose": "Verify the baseline and size of the change."
    }},
    {{
      "question": "Compare conversion rate by acquisition source across the requested periods.",
      "tool": "sql",
      "purpose": "Locate which channels account for the observed change."
    }}
  ]
}}
