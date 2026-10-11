# Telesales Intelligence System — Windows Quickstart & Power BI Guide

This guide explains how to run and open the **Telesales Intelligence System** on a **Windows** device with **Microsoft Power BI Desktop**.

---

## 1. Opening the Power BI Dashboard on Windows

You have two ready-to-use options in the [`powerbi/`](powerbi/) folder:

### Option A: Open the Power BI Template (`.pbit`) — Recommended
1. Install [Microsoft Power BI Desktop](https://powerbi.microsoft.com/desktop/) on Windows (free download from Microsoft Store).
2. Double-click **`powerbi/Telesales_Intelligence.pbit`**.
3. Power BI Desktop will launch and prompt for the database parameters.
4. Enter your PostgreSQL server host (e.g., `localhost` or your Linux machine's IP, port `5434`, database `telesales_db`).
5. Power BI will load the reporting views and open the report with all visuals and measures.

### Option B: Open the Power BI Project (`.pbip`)
1. In Power BI Desktop, enable **Power BI Project (.pbip) save option** under `File > Options and settings > Options > Preview features > Power BI Project (.pbip)`.
2. Double-click **`powerbi/Telesales_Intelligence.pbip`**.
3. Power BI Desktop will open the full source-controlled project directly.

---

## 2. Report Navigation & Arabic RTL Features

- **Page 1: Executive Overview (`Section_Overview`)**:
  - High-level KPIs: Total Calls, Average Rubric Score (0-100), Objection Resolution Rate, and Critical Leakages.
  - Objection Category breakdown & Sales Leakage severity distribution.
  - **Drill-Through**: Right-click any call row in the inventory grid and select **Drill-through > Call-Level Deep Dive Dashboard**.
- **Page 2: Call-Level Dashboard (`Section_CallDashboard`)**:
  - **Call Slicer**: Filter to any individual call (`CALL-JO-2026-001` to `005`).
  - **Score Gauge**: Visual 0-100 speedometer gauge with target 85.
  - **Executive Summary Box**: Right-to-left Arabic executive text.
  - **Customer Objections Table**: Exact Jordanian Arabic quotes, agent response, and resolution status badges.
  - **Sales Leakages Table**: Severity classifications, missing behaviors, and rubric reference codes.
  - **Actionable Coaching Plan**: Behavioral advice with authentic Jordanian conversational scripts.
  - **Verbatim Transcript Viewer**: Scrollable full dialogue with timestamps.

---

## 3. Running the Backend Pipeline on Windows (Optional)

If you want to run the ingestion pipeline, Cohere LLM analysis, and FastAPI server locally on Windows:

### Step 1: Install Python & uv
Open PowerShell:
```powershell
winget install Python.Python.3.12
winget install astral-sh.uv
```

### Step 2: Setup Environment
```powershell
cd telesales-intelligence
uv venv .venv --python 3.12
.venv\Scripts\activate
uv pip install -r requirements.txt
Copy-Item .env.example .env
```

### Step 3: Start PostgreSQL
If using Docker Desktop on Windows:
```powershell
docker run -d --name telesales-postgres -e POSTGRES_DB=telesales_db -e POSTGRES_USER=telesales -e POSTGRES_PASSWORD=telesales_secret -p 5434:5432 pgvector/pgvector:pg17
```

### Step 4: Run Database Migrations & Batch Runner
```powershell
alembic upgrade head
python app\ingestion\batch_runner.py --source folder --folder .\data\sample_transcripts
```

### Step 5: Start Headless API
```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
View the interactive in-browser dashboard preview at: `http://localhost:8000/dashboard`
