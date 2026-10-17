# RecallTracer — End-to-End Demo Presentation & Hackathon Workflow

This document provides a step-by-step presentation script, talking points, and workflow guide for demonstrating **RecallTracer** to hackathon judges, technical evaluators, and stakeholders.

---

## 1. Executive Summary & Value Proposition

### The Problem
During food or consumer product contamination incidents, tracking a faulty ingredient to the right store shelves takes days of frantic queries across disconnected spreadsheets, ERPs, and warehouse databases. This leads to:
1. **Slow Reaction Times**: Delays of 48–72 hours before affected stock is pulled from shelves.
2. **Costly False Positives**: Over-recalling innocent products because ubiquitous ingredients (like salt, water, or oil) appear everywhere.
3. **Hidden Multi-Hop Mixes**: Intermediate batches (e.g. pre-mixed seasonings or roasted nut batches) conceal the true origin of contamination across product lines.

### The RecallTracer Solution
RecallTracer combines a **shared supply-chain graph** (`network`) with **retail store operations graphs** (`bazaarmart`) powered by **FalkorDB**:
* **Graph Traversals (`*1..2`)**: Traces ingredients through multi-hop intermediate mixes in milliseconds.
* **Coverage × Specificity Scoring**: Mathematically isolates the true root cause while ruling out ubiquitous ingredients.
* **Persistent Organizational Memory**: Caches confirmed incident findings so future complaints trigger instant recall actions without re-computation.
* **Closed-Loop Store Actioning**: Automatically dispatches targeted pull tasks with exact aisle/shelf coordinates directly to on-duty retail associates.

---

## 2. Presentation Setup & Architecture

RecallTracer supports two presentation modes:

| Mode | Entry Point | Target Audience & Purpose |
| :--- | :--- | :--- |
| **Scripted Demo UI** | `http://localhost:8501` (`app.py`) | **Hackathon Judges & General Demos**: Runs 100% deterministically and instantaneously with zero API key dependencies. |
| **Agent Companion UI** | `http://localhost:8502` (`app_agent.py`) | **Technical & Agent Evaluators**: Demonstrates autonomous LangGraph ReAct agents and human-in-the-loop confirmation. |

---

## 3. Step-by-Step Demo Walkthrough (Port 8501)

### Act 1: The Hero Groundnut Outbreak (`GN-2214`)

#### Step 1: Load the Incident
1. Open [http://localhost:8501](http://localhost:8501).
2. Click **"📋 Load Hero Groundnut Outbreak"** in the preset bar.
3. **Talking Point**:  
   > *"Three severe allergic reactions have just been reported by customers across three different stores: Thane West (`TH-01`), Mulund (`TH-02`), and Pune FC Road (`TH-03`). The customers bought different products: Masala Peanuts in Thane and Mulund, but Bhujia in Pune."*

#### Step 2: Run Investigation
1. Click **"🚀 Run Graph Investigation"**.
2. **Talking Point**:  
   > *"Our graph reasoning engine runs against FalkorDB. Let's look at the results."*

#### Step 3: Explain Depth 1 vs Depth 2 Multi-Hop Attribution
1. Point to the **Depth 1 Tab**:
   * Lot `GN-2214` (groundnut) has `coverage = 0.67` and status `inconclusive`. Why? Because at 1-hop, it only links to Masala Peanuts (`TH-01` and `TH-02`). It does not directly touch Bhujia.
   * Lot `SL-0042` (salt) has `coverage = 1.0` (it is in all 3 products), but its score is `0.30 < 0.40`. Our algorithm automatically **rules out salt** because salt is delivered to 10 stores across the region.
2. Click the **Depth 2 Tab**:
   * At 2-hops, `GN-2214` connects to Bhujia through intermediate roasted mix **`RG-2409-04`** (`GN-2214 -> RG-2409-04 -> BH-2410-03`).
   * Coverage becomes **`1.0`** (3/3 stores explained), specificity is **`0.75`**, and score is **`0.75 >= 0.40`**.
   * **Root cause `GN-2214` is confirmed!**
3. Show the interactive **Attribution Graph**:
   * Teal node: Confirmed lot `GN-2214`.
   * Orange node: Intermediate mix `RG-2409-04`.
   * Blue nodes: Finished batches `MP-2410-01`, `MP-2410-02`, `BH-2410-03`.
   * Green nodes: Stores `TH-01`, `TH-02`, `TH-03`.

#### Step 4: Human-in-the-Loop Confirmation Gate
1. Point to the yellow status banner:  
   > *"Notice the safety guardrail: the investigation status is currently **OPEN**. Autonomous agents are strictly barred from dispatching physical store recall tasks until a human coordinator verifies the finding."*
2. Click **"✅ Confirm Root Cause & Save Finding"**.
3. **Talking Point**:  
   > *"Once confirmed, two things happen immediately:  
   > 1. The root cause is saved to organizational memory (`Finding` node in FalkorDB).  
   > 2. The Store Operations module automatically activates."*

#### Step 5: Store Operations & Shelf Pull Visualizer
1. Scroll down to **Section 3: Store Operations & Shelf Pull Visualizer**:
   * Show the tall hierarchical graph: `Lot -> Mix -> Batches -> Stores -> Sections -> Aisles -> On-Duty Associates`.
   * Note Store `TH-04`: it received a delivery, but has zero stock on the shelf, so the graph correctly labels it *"delivered, not on a shelf"* without losing the delivery node.
2. Review the **Dispatched Tasks Cards**:
   * `T-INV-COMPLAINTS-TH-01`: Assigned to Associate 001 at Aisle-01 with a 2-hour SLA.
   * `T-INV-COMPLAINTS-TH-02`: Assigned to Associate 002 at Aisle-01.
   * `T-INV-COMPLAINTS-TH-03`: Assigned to Associate 003 at Aisle-01.
3. Click **"Mark Done"** on one of the tasks:
   * Status flips from `PENDING` to `DONE`, showing closed-loop operational resolution.

---

### Act 2: Ubiquitous Ingredient Test (Salt-Only Complaints)

1. Click **"🧂 Load Salt-Only Complaints"** in the preset bar.
2. Click **"🚀 Run Graph Investigation"**.
3. **Talking Point**:  
   > *"Here, three customers reported mild symptoms after eating three different namkeen batches. In traditional systems, queries would highlight salt and potentially trigger a catastrophic recall of all salted snacks.  
   > In RecallTracer, salt achieves `coverage = 1.0` but has a specificity score of only `0.30`, so it is marked `ruled_out`. The investigation concludes as `inconclusive` (`no_link`), avoiding costly false-positive recalls."*

---

### Act 3: Supplier Early Warning Notice (`RX-7781` & Typo Handling)

1. Click **"⚠️ Load Supplier Notice (RX-7781)"**.
2. Click **"🚀 Run Graph Investigation"**.
3. **Talking Point**:  
   > *"A supplier reports microbial contamination in raw extract lot `RX-7781`. RecallTracer checks the graph: `used_in == 0`. The ingredient was never introduced into production batches or delivered to stores. The investigation immediately closes as `no_link`, and zero store tasks are dispatched."*

#### Typo Handling Demo
1. Expand **"🔍 More Scenarios"** and click **"🔤 Load Typo Lot (GN-22l4)"** (with a lowercase 'l').
2. Click **"🚀 Run Graph Investigation"**.
3. **Talking Point**:  
   > *"Notice entity resolution: Rather than failing or hallucinating, `resolve_lot` flags an `unknown_entity`, suggests `GN-2214`, and strictly avoids executing expensive graph traversals on unknown tokens."*

---

### Act 4: Instant Organizational Memory Recall

1. Expand **"🔍 More Scenarios"** and click **"🧠 Load Memory Replay (Pune / BH-2410-03)"**.
2. Click **"🚀 Run Graph Investigation"**.
3. **Talking Point**:  
   > *"A new complaint comes in from Pune regarding Bhujia batch `BH-2410-03`. Instead of re-running the multi-depth graph ranking algorithm, RecallTracer checks organizational memory via `lots_behind` and `recall_findings`.  
   > Because `GN-2214` was confirmed in Act 1, the system instantly matches the finding from memory, skipping the ranking phase entirely and accelerating incident response to sub-millisecond speeds."*

---

### Act 5: Inspecting Telemetry & Guardrails

1. Expand **"🛠️ Tool Execution Trace"** at the bottom of the page.
2. **Talking Point**:  
   > *"Every graph query is tracked with execution latency (typically 1–5 ms in FalkorDB), row counts, and serialized argument signatures. Furthermore, our `sentence_ok` guardrail validates every summary sentence against verified database tokens before rendering to prevent UI hallucination."*

---

## 4. Agent Companion Mode with LangGraph Studio (Port 8502)

To demonstrate autonomous agent coordination:

1. Launch the Agent Companion UI in a separate terminal:
   ```powershell
   conda activate recall
   streamlit run app_agent.py --server.port 8502
   ```
2. In another terminal, start LangGraph Studio:
   ```powershell
   langgraph dev
   ```
3. Open LangGraph Studio:
   * Select the **`investigator`** graph.
   * Send the complaint list:
     ```json
     {
       "messages": [
         {
           "role": "user",
           "content": "Investigate complaints: store TH-01 batch MP-2410-01, store TH-02 batch MP-2410-02, store TH-03 batch BH-2410-03."
         }
       ]
     }
     ```
   * Watch the ReAct agent invoke `record_complaints`, `lots_behind`, `rank_lots(1)`, `rank_lots(2)`, `forward_trace`, `illness`, and `write_investigation(status='open')`.
4. Switch to [http://localhost:8502](http://localhost:8502) and click **"🔄 Refresh Graph State"**:
   * The live graph state is immediately rendered.
   * Click **"🛡️ Confirm Class I Recall"** on the companion UI.
5. In LangGraph Studio, switch to the **`store_ops`** graph:
   * Prompt: `"Dispatch pull tasks for the confirmed recall investigation."`
   * Watch the agent inspect `load_investigation`, check `pull_list`, inspect `current_tasks`, and dispatch tasks to `TH-01`, `TH-02`, and `TH-03`.
6. Refresh [http://localhost:8502](http://localhost:8502) to see all dispatched tasks and shelf locations update live.

---

## 5. Hackathon Judging Matrix Reference

| Feature | FalkorDB & Technical Highlights | Business Value |
| :--- | :--- | :--- |
| **Multi-Hop Traversal** | Variable-length path matching (`USED_IN*1..2`) in Cypher | Discovers contamination through intermediate seasoning/flour mixes that relational databases miss. |
| **Specificity Scoring** | In-database graph reach joined with store delivery counts | Prevents catastrophic false-positive recalls of ubiquitous ingredients like salt, water, or oil. |
| **Cross-Graph Join** | Joins supply-chain `network` with retailer `bazaarmart` | Preserves retailer privacy while enabling unified supply-chain traceability. |
| **Human-in-the-Loop** | Strict state machine: `open` -> `confirmed` -> `closed` | Prevents autonomous agents from accidentally triggering store pulls without human verification. |
| **Operational Dispatch** | Live shelf mapping to on-duty associates with 2h SLAs | Translates abstract database investigation into immediate physical store action. |
| **Enterprise Reliability** | 7/7 automated end-to-end tests (`eval.py`) with 100% pass | Production-grade software engineering ready for live deployment. |
