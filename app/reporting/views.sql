-- ==============================================================================
-- Telesales Intelligence System - Power BI Reporting Views
-- Version: 2.0 (Production-Minded MVP)
-- Power BI connects exclusively to these views, never directly to base tables.
-- ==============================================================================

-- 1. Dimension: Calls (Core metadata and typed timestamps)
CREATE OR REPLACE VIEW v_dim_calls AS
SELECT
    c.call_id,
    COALESCE(c.agent_id, 'Unassigned') AS agent_id,
    c.call_date,
    CAST(c.call_date AS DATE) AS call_date_only,
    CAST(c.call_date AS TIME) AS call_time_only,
    COALESCE(c.call_objective, 'General Sales') AS call_objective,
    c.source,
    c.source_ref,
    c.turn_count,
    COALESCE(c.duration_seconds, c.turn_count * 15) AS duration_seconds,
    c.status,
    c.created_at
FROM calls c;


-- 2. Dimension: Categories & Lookups (Bilingual Arabic / English Labels)
CREATE OR REPLACE VIEW v_dim_categories AS
SELECT
    id AS lookup_id,
    category_type,
    code,
    label_en,
    label_ar,
    description
FROM category_lookups;


-- 3. Fact: Call Assessments (Call-level summary KPIs and Scores)
CREATE OR REPLACE VIEW v_fact_call_assessments AS
SELECT
    ca.id AS assessment_id,
    ca.call_id,
    c.agent_id,
    c.call_date,
    ca.overall_score,
    ca.objection_count,
    ca.objections_addressed_count,
    ca.objections_partially_count,
    ca.objections_unaddressed_count,
    -- Deterministic objection resolution rate (0 if no objections)
    CASE 
        WHEN ca.objection_count = 0 THEN 100.0
        ELSE ROUND(CAST((ca.objections_addressed_count + (ca.objections_partially_count * 0.5)) * 100.0 / ca.objection_count AS NUMERIC), 2)
    END AS objection_resolution_rate_pct,
    ca.leakage_count,
    ca.critical_leakage_count,
    ca.high_leakage_count,
    ca.medium_leakage_count,
    ca.low_leakage_count,
    ca.summary_assessment,
    ca.review_status,
    ca.reviewer_notes,
    ca.model_id,
    ca.prompt_version,
    ca.analyzed_at
FROM call_assessments ca
JOIN calls c ON ca.call_id = c.call_id;


-- 4. Fact: Customer Objections (Traceable to transcript excerpts)
CREATE OR REPLACE VIEW v_fact_objections AS
SELECT
    o.finding_id,
    o.call_id,
    c.agent_id,
    c.call_date,
    o.category_code,
    COALESCE(lk_cat.label_en, o.category_code) AS category_label_en,
    COALESCE(lk_cat.label_ar, o.category_code) AS category_label_ar,
    o.customer_excerpt,
    COALESCE(o.turn_reference, 'N/A') AS turn_reference,
    o.agent_response_excerpt,
    o.addressed_status,
    COALESCE(lk_addr.label_en, o.addressed_status) AS addressed_status_label_en,
    COALESCE(lk_addr.label_ar, o.addressed_status) AS addressed_status_label_ar,
    o.speaker_attribution,
    o.explanation,
    o.confidence,
    o.company_guidance_ref,
    o.review_status,
    o.created_at
FROM objection_findings o
JOIN calls c ON o.call_id = c.call_id
LEFT JOIN category_lookups lk_cat 
    ON lk_cat.category_type = 'objection' AND lk_cat.code = o.category_code
LEFT JOIN category_lookups lk_addr 
    ON lk_addr.category_type = 'addressed_status' AND lk_addr.code = o.addressed_status;


-- 5. Fact: Sales Leakages (Missed opportunities and rubric failures)
CREATE OR REPLACE VIEW v_fact_leakages AS
SELECT
    l.finding_id,
    l.call_id,
    c.agent_id,
    c.call_date,
    l.category_code,
    COALESCE(lk_cat.label_en, l.category_code) AS category_label_en,
    COALESCE(lk_cat.label_ar, l.category_code) AS category_label_ar,
    l.severity,
    COALESCE(lk_sev.label_en, l.severity) AS severity_label_en,
    COALESCE(lk_sev.label_ar, l.severity) AS severity_label_ar,
    l.evidence_class,
    COALESCE(lk_ev.label_en, l.evidence_class) AS evidence_class_label_en,
    COALESCE(lk_ev.label_ar, l.evidence_class) AS evidence_class_label_ar,
    l.transcript_excerpt,
    COALESCE(l.turn_reference, 'N/A') AS turn_reference,
    l.expected_behavior,
    l.missing_behavior,
    l.confidence,
    l.rubric_ref,
    l.related_objection_id,
    l.recommended_human_review,
    l.review_status,
    l.created_at
FROM leakage_findings l
JOIN calls c ON l.call_id = c.call_id
LEFT JOIN category_lookups lk_cat 
    ON lk_cat.category_type = 'leakage' AND lk_cat.code = l.category_code
LEFT JOIN category_lookups lk_sev 
    ON lk_sev.category_type = 'severity' AND lk_sev.code = l.severity
LEFT JOIN category_lookups lk_ev 
    ON lk_ev.category_type = 'evidence_class' AND lk_ev.code = l.evidence_class;


-- 6. Fact: Coaching Actions (Actionable recommendations linked to findings)
CREATE OR REPLACE VIEW v_fact_coaching AS
SELECT
    ch.action_id,
    ch.call_id,
    c.agent_id,
    c.call_date,
    ch.related_finding_id,
    ch.skill_domain,
    ch.priority,
    COALESCE(lk_pri.label_en, ch.priority) AS priority_label_en,
    COALESCE(lk_pri.label_ar, ch.priority) AS priority_label_ar,
    ch.evidence_excerpt,
    ch.recommended_behavior,
    ch.example_phrase,
    ch.coaching_guideline_ref,
    ch.language,
    ch.review_status,
    ch.created_at
FROM coaching_actions ch
JOIN calls c ON ch.call_id = c.call_id
LEFT JOIN category_lookups lk_pri 
    ON lk_pri.category_type = 'priority' AND lk_pri.code = ch.priority;


-- 7. Dimension / Aggregate: Agent Performance Rollup
CREATE OR REPLACE VIEW v_dim_agents AS
SELECT
    c.agent_id,
    COUNT(c.call_id) AS total_calls,
    ROUND(CAST(AVG(ca.overall_score) AS NUMERIC), 2) AS avg_overall_score,
    SUM(ca.objection_count) AS total_objections,
    SUM(ca.objections_addressed_count) AS total_addressed_objections,
    CASE 
        WHEN SUM(ca.objection_count) = 0 THEN 100.0
        ELSE ROUND(CAST((SUM(ca.objections_addressed_count) + (SUM(ca.objections_partially_count) * 0.5)) * 100.0 / SUM(ca.objection_count) AS NUMERIC), 2)
    END AS overall_objection_resolution_rate_pct,
    SUM(ca.leakage_count) AS total_leakages,
    SUM(ca.critical_leakage_count) AS total_critical_leakages
FROM calls c
LEFT JOIN call_assessments ca ON c.call_id = ca.call_id
WHERE c.agent_id IS NOT NULL
GROUP BY c.agent_id;


-- 8. Composite: Single-Call Dashboard Detail View
-- Designed for the dedicated Call-Level Page in Power BI (Drill-through & Deep-linking)
CREATE OR REPLACE VIEW v_call_dashboard_detail AS
SELECT
    c.call_id,
    c.agent_id,
    c.call_date,
    c.call_objective,
    c.turn_count,
    c.transcript_raw,
    ca.overall_score,
    ca.objection_count,
    ca.objections_addressed_count,
    ca.objections_unaddressed_count,
    ca.leakage_count,
    ca.critical_leakage_count,
    ca.summary_assessment,
    ca.review_status AS assessment_review_status,
    ca.model_id,
    ca.analyzed_at
FROM calls c
JOIN call_assessments ca ON c.call_id = ca.call_id;
