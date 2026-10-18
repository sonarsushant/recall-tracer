# RecallTracer — Setup & Installation Guide

This document provides complete instructions for setting up the local development environment, database, Python dependencies, and running the automated test suite for **RecallTracer** (GraphHacks FalkorDB hackathon project).

---

## 1. System Requirements & Architecture

| Component | Requirement / Specification |
| :--- | :--- |
| **Operating System** | Windows 10/11 (or Linux / macOS) |
| **Container Engine** | Docker Desktop (running) |
| **Graph Database** | FalkorDB (v1.2+ or latest Docker image) |
| **Database Ports** | `6379` (FalkorDB Cypher/Redis), `3000` (FalkorDB Web Browser) |
| **Python Environment** | Python 3.11 (via Conda or venv) |
| **Web Applications** | Streamlit on Port `8501` (Demo UI) & Port `8502` (Agent Companion UI) |
| **Agent Framework** | LangGraph / LangChain OpenAI-compatible chat models |

---

## 2. Step 1: Start FalkorDB via Docker

FalkorDB runs inside a Docker container providing graph database capabilities on port `6379` and an interactive web explorer on port `3000`.

### A. Run via Docker CLI
Open PowerShell or your terminal and run:
```powershell
docker run -d --name falkordb -p 6379:6379 -p 3000:3000 falkordb/falkordb:latest
```

### B. Or Run via Docker Compose
From the project root directory:
```powershell
docker compose up -d falkordb
```

### C. Verify FalkorDB
1. **FalkorDB Browser**: Open your web browser at [http://localhost:3000](http://localhost:3000). You should see the FalkorDB Browser interface.
2. **Container Status**: Run `docker ps` to verify container `falkordb` is `Up` and bound to `0.0.0.0:6379` and `0.0.0.0:3000`.

---

## 3. Step 2: Set Up Python 3.11 Environment

A dedicated Python 3.11 environment (e.g. `recall`) ensures full compatibility with `langgraph`, `streamlit-agraph`, `falkordb`, and `mcp`.

### A. Create and Activate Conda Environment
```powershell
conda create -y -n recall python=3.11
conda activate recall
```

### B. Install Python Dependencies
```powershell
pip install -r requirements.txt
```

The installed packages include:
* `falkordb`: Official Python client for FalkorDB.
* `streamlit`: Fast web dashboard framework.
* `streamlit-agraph`: Graph visualization canvas.
* `langgraph` & `langgraph-cli[inmem]`: Multi-agent ReAct orchestration.
* `langchain-openai`: LLM integration.
* `python-dotenv`: Environment configuration manager.
* `mcp`: Model Context Protocol server/client.

### C. Configure Environment Variables
Copy `.env.example` to `.env`:
```powershell
cp .env.example .env
```
Ensure your `.env` contains:
```env
FALKOR_HOST=localhost
FALKOR_PORT=6379
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
LLM_PROVIDER=lm_studio
LM_STUDIO_MODEL=qwen/qwen3-4b-2507
```

`LLM_PROVIDER` selects the backend for both LangGraph agents. Set it to `lm_studio` to use a locally running LM Studio server, or `openai` to use OpenAI. The default LM Studio endpoint for local runs is `http://localhost:1234/v1`; change `LM_STUDIO_BASE_URL` if LM Studio is listening elsewhere. With Docker Compose, the default endpoint is `http://host.docker.internal:1234/v1`, which lets the container connect to LM Studio on the host. Make sure the selected model is loaded and the LM Studio local server is running. `OPENAI_API_KEY` is required only when `LLM_PROVIDER=openai`; the scripted demo UI and evaluation suite run locally and deterministically without LLM API keys.

---

## 4. Step 3: Seed the Graph Databases

RecallTracer operates with two interconnected graph models:
1. `network`: The shared supply chain graph (Suppliers, Lots, Intermediate Mixes, Finished Batches, Products, Recall Notices).
2. `bazaarmart`: The private retailer operations graph (Stores, Sections, Shelf Locations, Associates on Duty, Batch References, Deliveries, Customer Purchases, Tasks).

Run the deterministic clean seed script:
```powershell
python scripts/seed_clean.py
```

Expected terminal output:
```text
Connected to FalkorDB at localhost:6379
Clearing network graph...
Seeding network graph...
Network graph seeded successfully!
Clearing bazaarmart graph...
Seeding bazaarmart graph...
BazaarMart graph seeded successfully!

Database is fully seeded and ready for eval.py!
```

To inspect node and relationship counts at any time, run:
```powershell
python scripts/check_graphs.py
```

---

## 5. Step 4: Run the Automated Evaluation Suite (`eval.py`)

Run the 7-check end-to-end evaluation suite to verify that all Cypher queries, graph path traversals, scoring rules, and operations logic work properly:

```powershell
python eval.py
```

### Expected Output:
```text
================================================================================
RECALLTRACER END-TO-END EVALUATION SUITE
================================================================================
Seeding database to pristine state...
...
================================================================================
#   | Check Description                                | Status | Details
--------------------------------------------------------------------------------
1   | Hero complaints, depth 1 rejects salt            | PASS   | salt status=ruled_out, coverage=1.0, score=0.3, groundnut oil absent=True
2   | Depth 2 groundnut-oil recall dispatch            | PASS   | GO status=confirmed, cov=1.0, score=0.5, traced batches=7, stores dispatched=6
3   | Salt-only complaints on three namkeen batches    | PASS   | salt depth-1=ruled_out, LOT-011 depth-2 path through mix=True, depth-1/depth-2 graphs differ=True, confirmed candidates=0
4   | notice('RX-7781') then store_ops.run()           | PASS   | INV-NOTICE status=no_link, new tasks dispatched=0
5   | notice('GN-22l4') (lowercase L typo)             | PASS   | outcome=unknown_entity, candidates=['GN-2214'], forward_trace_called=False
6   | forward_trace('RP-0099')                         | PASS   | purchases=2, standalone scenario outcome=answered, graph includes product link=True
7   | Save GO-0611 finding & memory replay Pune / BH-2410-03 | PASS   | outcome=from_memory, lots_behind_in_trace=True, rank_lots_in_trace=False
================================================================================

ALL 7 EVALUATION CHECKS PASSED SUCCESSFULLY (Exit Code 0)
```

---

## 6. Step 5: Launch the User Interfaces

### A. Launch the Agent and Graph UI (Port 8501)
```powershell
conda activate recall
streamlit run app.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser. This page includes in-app agent chat, a **Quick Forward Trace** input, and live graph and task views. Agent chat requires the selected LLM provider in `.env` to be configured and available; LangGraph Studio is not needed. See [DEMO_WORKFLOW.md](./DEMO_WORKFLOW.md) for copy-paste prompts and the human-confirmation step.

### B. Launch the Scripted Demo and Agent Chat (Port 8502)
In a separate terminal:
```powershell
conda activate recall
streamlit run app_demo_scripted.py --server.port 8502
```
Open [http://localhost:8502](http://localhost:8502) in your browser. The scripted scenarios work without an LLM; the optional Investigator and Store Operations chat requires a configured provider.

### C. Launch LangGraph Studio (Optional)
If you wish to inspect agent execution in Studio instead of using the in-app chat:
```powershell
langgraph dev
```

---

## 7. Troubleshooting & FAQ

* **Issue: `redis.exceptions.ConnectionError: Error 10061 connecting to localhost:6379`**  
  *Solution:* Ensure Docker Desktop is running and the FalkorDB container is started (`docker start falkordb` or `docker ps`).

* **Issue: `ModuleNotFoundError: No module named 'streamlit_agraph'`**  
  *Solution:* Ensure you activated the Python 3.11 conda environment (`conda activate recall`) before launching Streamlit.

* **Issue: `langgraph dev` fails with `AttributeError: module 'langgraph_api' has no attribute 'logging'` on Windows**
  *Solution:* This can be caused by the missing `colorama` dependency used by LangGraph's colored console logger. Install the project dependencies with `pip install -r requirements.txt` (or run `python -m pip install colorama` in the active environment), then retry `langgraph dev`.

* **Issue: Port conflict on `8501` or `8502`**  
  *Solution:* Specify a different port using `--server.port <port_number>`.
