"""
Blueprint:
- Named parameterized SQL queries for validation repository.
- Adheres to naming convention: FLOW_{VERB}_{ENTITY}_{CRITERIA}.
"""

FLOW_INSERT_VALIDATION_REPORT = """
INSERT INTO validation_reports (
    validation_id,
    target_name,
    target_type,
    status,
    is_valid,
    errors_json,
    metadata_json,
    trace_id,
    created_at
) VALUES (
    %(validation_id)s,
    %(target_name)s,
    %(target_type)s,
    %(status)s,
    %(is_valid)s,
    %(errors_json)s,
    %(metadata_json)s,
    %(trace_id)s,
    NOW()
)
"""

FLOW_SELECT_VALIDATION_REPORT_BY_ID = """
SELECT
    validation_id,
    target_name,
    target_type,
    status,
    is_valid,
    errors_json,
    metadata_json,
    trace_id,
    created_at
FROM validation_reports
WHERE validation_id = %(validation_id)s
"""
