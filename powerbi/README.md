# Power BI Reporting & Semantic Model Architecture
**Telesales Intelligence System — Production-Minded MVP**  
*Auditor: Sales Operations & Quality Assurance*

---

## 1. Overview & Architectural Principles

Power BI is the **exclusive human-facing interface** for the Telesales Intelligence System. All upstream data ingestion, dialect reasoning, evidence validation, and persistence run in a completely headless, automated pipeline.

### Core Architectural Decisions:
1. **Views-Only Connection**: Power BI connects strictly to read-only PostgreSQL reporting views (`v_dim_*` and `v_fact_*`). Power BI **never** connects directly to underlying transaction tables. This shields the reporting layer from schema refactoring and enforces database-side business logic and security.
2. **Single Scalable Report**: As mandated by the architecture, the report contains a **dedicated Call-Level Page** that dynamically displays a single call selected via **Drill-Through, Slicers, or Deep-Linking URL parameters**. We do **not** generate separate `.pbix` files per call.
3. **Arabic Dialect & RTL First**: Designed specifically for Jordanian Arabic telesales transcripts, handling colloquial phrasing and Arabic-English code-switching cleanly in Power BI visuals.

### Core Deliverables Provided in this Folder:
1. **`Telesales_Intelligence.pbit`**: Microsoft Power BI Template file ready to open in Power BI Desktop.
2. **`Telesales_Intelligence.pbip`**: Modern source-controlled Power BI Project format (`.Report/report.json` + `.Dataset/model.bim`).
3. **`dashboard.html` / `GET /dashboard`**: Interactive Power BI dashboard live replica for instant in-browser inspection on Linux.
4. **`measures.dax`**: 35+ DAX production measures.
5. **`build_pbit.py`**: Automated build script to recompile `.pbit` from source.

---

## 2. Reporting Views Specification

The database exposes the following optimized views:

| View Name | Granularity | Purpose |
| :--- | :--- | :--- |
| `v_dim_calls` | 1 row per call | Call metadata, duration, timestamps, sales agent, and objective |
| `v_dim_categories` | 1 row per lookup code | Bilingual English (`label_en`) and Arabic (`label_ar`) taxonomy labels |
| `v_dim_agents` | 1 row per sales agent | Aggregated performance metrics (calls, average score, resolution rate) |
| `v_fact_call_assessments` | 1 row per call | Overall score (0-100), objection counts, leakage counts, executive summary |
| `v_fact_objections` | 1 row per detected objection | Verbatim customer excerpt, turn reference, agent response, resolution status |
| `v_fact_leakages` | 1 row per leakage finding | Category, severity (`critical`, `high`, `medium`), evidence class, rubric code |
| `v_fact_coaching` | 1 row per coaching action | Practical guidance, skill domain, conversational example phrase in Jordanian Arabic |
| `v_call_dashboard_detail` | 1 row per call | Denormalized view optimized for the single-call drill-through dashboard |

---

## 3. Data Model & Star Schema Relationships

In Power BI Desktop, relationships are configured in a clean **Star Schema**:

```
           [v_dim_categories] (Filter Lookups)
                   |
     +-------------+-------------+
     |                           |
[v_dim_calls] (1)           [v_dim_agents] (1)
     |
     +--- (1:1) ---> [v_fact_call_assessments] (Call Score Facts)
     |
     +--- (1:N) ---> [v_fact_objections]        (Customer Objections)
     |
     +--- (1:N) ---> [v_fact_leakages]          (Sales Leakages)
     |
     +--- (1:N) ---> [v_fact_coaching]          (Coaching Recommendations)
```

- **Cross Filter Direction**: Single (`v_dim_calls` filters fact tables).
- **Cardinality**: `1 to Many` (`1:*`) from `v_dim_calls` to fact tables on column `call_id`.

---

## 4. Connecting Power BI to the Database

### Option A: Direct PostgreSQL Connector
1. Open **Microsoft Power BI Desktop**.
2. Click **Get Data** > **PostgreSQL database**.
3. Server: `127.0.0.1:5434` (or your production host).
4. Database: `telesales_db`.
5. Data Connectivity mode: Select **Import** (recommended for sub-second visual performance) or **DirectQuery**.
6. In Navigator, check only the views starting with `v_`:
   - `v_dim_calls`
   - `v_dim_categories`
   - `v_dim_agents`
   - `v_fact_call_assessments`
   - `v_fact_objections`
   - `v_fact_leakages`
   - `v_fact_coaching`
7. Click **Load**.

### Option B: DAX Measures Import
Open the Modeling tab, create a new measure table `_Measures`, and paste all measures from [`measures.dax`](measures.dax).

---

## 5. Report Page Layouts

### Page 1: "Executive Telesales Overview"
- **KPI Summary Cards**:
  - Total Calls (`[Total Calls]`)
  - Average Call Score (`[Average Call Score]`)
  - Objection Resolution Rate (`[Objection Resolution Rate %]`)
  - Calls with Critical Leakage (`[Critical Leakages]`)
- **Visuals**:
  - **Donut Chart**: Objections Breakdown by Category (`v_fact_objections[category_label_ar]`).
  - **Clustered Bar Chart**: Sales Leakages by Severity (`v_fact_leakages[severity_label_ar]`).
  - **Agent Performance Matrix**: Agent ID, Calls, Avg Score, Objection Resolution %, Leakage Count.
  - **Call Drill-Through Grid**: Call ID, Date, Agent, Objective, Score Badge. (Right-click a call -> Drill-Through -> Call Dashboard).

---

### Page 2: "Call-Level Deep Dive Dashboard" (Single-Call View)
This is the core view requested: **a dashboard for each call**.

#### Visual Structure:
1. **Header Cards**:
   - Call ID: `[Selected Call ID]`
   - Agent: `[Selected Call Agent]`
   - Date & Time: `[Selected Call Date Formatted]`
   - Call Objective: `[Selected Call Objective]`
   - Status Badge: `[Selected Call Score Status Badge]`
2. **Score & Evaluation Gauge**:
   - Value: `[Selected Call Score]` (Min: 0, Max: 100, Target: 85).
3. **Executive Summary Card (RTL Arabic)**:
   - Visual: Card or Text Visual bound to `[Selected Call Summary RTL]`.
   - Font: Segoe UI / Arial, Size 13, Right-Aligned.
4. **Customer Objections Table**:
   - Columns: `turn_reference`, `category_label_ar`, `customer_excerpt` (Arabic), `agent_response_excerpt`, `addressed_status_label_ar`.
   - Conditional formatting: Green for `Fully Addressed`, Yellow for `Partially`, Red for `Unaddressed`.
5. **Sales Leakage & Missed Opportunities Table**:
   - Columns: `turn_reference`, `category_label_ar`, `severity_label_ar`, `evidence_class_label_ar`, `transcript_excerpt`, `missing_behavior`, `rubric_ref`.
6. **Targeted Coaching Action Plan**:
   - Columns: `priority_label_ar`, `skill_domain`, `recommended_behavior`, `example_phrase` (Authentic Jordanian script).
7. **Verbatim Transcript Viewer**:
   - Multi-row card or table displaying full dialogue with turn numbers.

---

## 6. Drill-Through and Deep-Linking URL Setup

### Configuring Drill-Through:
1. Navigate to Page 2 (Call-Level Dashboard).
2. In the **Visualizations** pane, expand **Drill-through**.
3. Drag `v_dim_calls[call_id]` into the **Drill-through fields** well.
4. Set "Keep all filters" to **On**.
5. Power BI automatically enables right-click drill-through on any visual mentioning a call across the report.

### Deep-Linking URL Syntax:
You can link directly from your CRM, telephony system, or ticketing tool to a specific call's dashboard using URL filtering:

```
https://app.powerbi.com/groups/{workspace_id}/reports/{report_id}/ReportSection?filter=v_dim_calls/call_id eq 'CALL-JO-2026-001'
```

When opened, Power BI immediately filters the page to show exclusively the selected call.

---

## 7. Arabic (Jordanian Dialect) RTL Rendering Guidelines

Jordanian telesales transcripts often mix Arabic colloquial phrasing with English product terminology (e.g., *"الـ package غالية"*, *"الـ SLA ممتاز"*).

### Formatting Rules for Crisp Arabic Legibility:
1. **Right-to-Left Alignment**: For tables containing Arabic excerpts (`customer_excerpt`, `summary_assessment`), set column alignment to **Right** in the Field Formatting tab.
2. **Text Wrapping**: Always enable **"Text wrap"** on both headers and values in Table/Matrix visuals to prevent excerpts from being clipped.
3. **Typography**: Recommended fonts for clean Arabic glyph rendering:
   - `Segoe UI` (native Power BI default, excellent Arabic-Latin kerning)
   - `Arial`
   - `Cairo` / `Tajawal` (if custom theme JSON is loaded)
4. **Zero Values**: Calls with zero objections explicitly show `0` (via `[Calls With Zero Objections]`), not blank or missing data.

---

## 8. Automated Refresh Mechanism

After a batch ingestion runner completes, the Power BI semantic model can be automatically refreshed:
- Via `app/reporting/powerbi_refresh.py` using the Power BI Service REST API (`POST /refreshes`).
- Configured via Azure AD App Registration (Service Principal with `Dataset.ReadWrite.All` permissions).
- Or scheduled in Power BI Service using an on-premises data gateway connecting to PostgreSQL.
