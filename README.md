# RecallTracer

RecallTracer is a graph-powered product incident and recall investigation demo. It combines supply-chain provenance with retailer operations data so investigators can trace reported batches to ingredient lots, assess downstream exposure, and coordinate store actions with a human confirmation gate.

Blog Post: https://medium.com/@virajsonar/dont-let-your-ai-agent-guess-0e207e657a1d

Video Demo: https://www.youtube.com/watch?v=JdcYg0kVkhQ

## What it demonstrates

- **Multi-hop provenance:** follow ingredient lots through intermediate mixes to finished product batches.
- **Evidence-based attribution:** rank candidate lots using complaint coverage and specificity, helping distinguish a shared cause from a ubiquitous ingredient.
- **Organizational memory:** save human-confirmed findings and reuse them for later complaints. For example, a new Pune complaint for Bhujia batch `BH-2410-03` can trace upstream to `GO-0611`, find its confirmed memory record, and skip candidate ranking.
- **Downstream exposure:** trace a confirmed lot to batches and stores beyond those named in complaints.
- **Guarded store operations:** require human confirmation before dispatching tasks; check shelf stock and duplicate tasks.
- **Inspectable agent workflows:** use optional LangGraph chat to observe the Investigator and Store Operations agents calling typed tools.

The project is a local demonstration and uses seeded example data. It is not a production recall-management system.

## Architecture

RecallTracer uses two FalkorDB graphs joined by batch identifiers:

| Graph | Example data |
| --- | --- |
| `network` | Suppliers, ingredient lots, intermediate mixes, finished batches, products, and supplier notices |
| `bazaarmart` | Stores, complaints, delivered batches, shelf stock, findings, associates, and pull tasks |

Python tools run parameterized Cypher queries and deterministic scoring. LangGraph agents orchestrate the tools and communicate findings; they do not invent graph relationships or authorize physical store actions.

## Requirements

- Docker Desktop or another Docker Engine
- Python 3.11 for local setup
- FalkorDB, started with Docker Compose below
- An OpenAI-compatible model provider only if you want to use agent chat

## Quick start

### 1. Start FalkorDB

From the project root:

```powershell
docker compose up -d falkordb
```

FalkorDB listens on `localhost:6379`; its browser interface is available at [http://localhost:3000](http://localhost:3000).

### 2. Create a Python environment and install dependencies

For Conda on Windows:

```powershell
conda create -y -n recall python=3.11
conda activate recall
pip install -r requirements.txt
```

Alternatively, create and activate a Python 3.11 virtual environment, then install `requirements.txt`.

### 3. Configure environment variables

Copy the example configuration:

```powershell
Copy-Item .env.example .env
```

The example uses LM Studio. Start its local server, load the configured model, and set the endpoint/model if your local setup differs:

```env
FALKOR_HOST=localhost
FALKOR_PORT=6379
LLM_PROVIDER=lm_studio
LM_STUDIO_BASE_URL=http://localhost:1234/v1
LM_STUDIO_MODEL=qwen/qwen3-4b-2507
```

To use OpenAI instead, set `LLM_PROVIDER=openai`, `OPENAI_MODEL` (optional; defaults to `gpt-4o-mini`), and `OPENAI_API_KEY`. Keep credentials in `.env`; do not commit them. The scripted demo and evaluation suite do not require an LLM API key.

### 4. Seed the demo graphs

```powershell
python scripts/seed_clean.py
```

> **Note:** This seed script clears and recreates the `network` and `bazaarmart` graphs. Run it only against the local demo database when it is safe to replace their contents.

Optional graph inspection:

```powershell
python scripts/check_graphs.py
```

### 5. Run the application

Start the agent and graph-visualization interface:

```powershell
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501). This page includes agent chat, a quick forward-trace tool, and live complaint, graph, and task views. Agent chat requires the configured model provider.

To run the scripted demo and scenario runner in another terminal:

```powershell
conda activate recall
streamlit run app_demo_scripted.py --server.port 8502
```

Open [http://localhost:8502](http://localhost:8502). The deterministic scenario runner works without an LLM; its optional **LangGraph Agent Chat** section requires the configured model provider. LangGraph Studio is optional; start it with `langgraph dev` if you want to inspect the agent execution graph.

## Try the scenarios

The main app includes presets for:

- **Groundnut-oil outbreak:** three complaints across Thane and Pune; compare direct and multi-hop lot attribution.
- **Salt-only complaints:** demonstrate low-specificity candidate rejection.
- **Supplier notice:** check a lot for downstream use.
- **Unknown lot typo:** demonstrate entity resolution without proceeding on an unknown identifier.
- **Memory replay:** after saving a confirmed finding for the outbreak, load **Memory Replay (Pune / BH-2410-03)**. The workflow records the complaint, traces the batch to upstream lots, and checks organizational memory. A match for `GO-0611` reuses the prior confirmed finding instead of running candidate ranking again.
- **Forward trace:** inspect products and stores downstream of an ingredient lot.

For detailed environment setup, see [SETUP.md](./SETUP.md). View the [project presentation](./presentation/RECALLTRACER_PROJECT_PRESENTATION.html).

## Human confirmation and store tasks

Investigation and action are separate steps. A confirmed memory match can provide a prior conclusion, but a new investigation is not by itself permission to dispatch store tasks. For a fresh attribution, review the open finding and explicitly confirm the root cause in the UI. Store Operations then checks investigation status, stock availability, and existing tasks before dispatching.

## Run the evaluation suite

```powershell
python eval.py
```

The evaluation suite reseeds the demo graphs to a known state, then runs the end-to-end checks, including attribution, false-positive handling, notice investigation, typo resolution, forward tracing, and Pune memory replay. Run it only against the local demo database because seeding replaces graph contents.

## Repository layout

| Path | Purpose |
| --- | --- |
| `app.py` | Agent UI with graph and task visualizations (port 8501) |
| `app_demo_scripted.py` | Scripted demo and optional Investigator / Store Operations chat (port 8502) |
| `agents.py` | LangGraph agent factories and typed tool definitions |
| `investigator.py`, `store_ops.py` | Deterministic investigation and operational workflows |
| `tools.py` | FalkorDB access, Cypher-backed tools, scoring, memory, and operational checks |
| `queries/` | Parameterized Cypher query files |
| `scripts/seed_clean.py` | Clean seed for both demo graphs |
| `eval.py` | End-to-end evaluation suite |
| `SETUP.md` | Detailed environment setup and troubleshooting |
| `presentation/RECALLTRACER_PROJECT_PRESENTATION.html` | HTML project presentation |

## Troubleshooting

- **Cannot connect to `localhost:6379`:** verify Docker is running and start FalkorDB with `docker compose up -d falkordb`.
- **Agent reports missing model configuration:** check `LLM_PROVIDER` and its provider-specific variables in `.env`; for LM Studio, make sure the local server is running and the selected model is loaded.
- **Port 8501 or 8502 is in use:** choose another port, for example `streamlit run app_demo_scripted.py --server.port 8503`.
- **Missing Python module:** activate the project environment and run `pip install -r requirements.txt`.
