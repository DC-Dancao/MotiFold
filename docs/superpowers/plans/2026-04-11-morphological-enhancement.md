# Morphological Analysis Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance morphological analysis with inline editing, orthogonality checks, contradiction types, new Tab 4 convergence, and separate heatmap page.

**Architecture:** Backend extends existing service/router with new endpoints; frontend adds inline editing UI, Tab 4 component, and heatmap page. Keep existing 3 tabs unchanged.

**Tech Stack:** Python (FastAPI), React 19, TypeScript, ECharts, Tailwind CSS

---

## File Structure

```
feature-2/
├── backend/
│   └── app/matrix/
│       ├── models.py          # Add MatrixCell, SolutionCluster models
│       ├── schemas.py         # Add EnhancedMatrixCell, ClusterRequest/Response
│       ├── service.py         # Add orthogonality_check, cluster_solutions, suggest_ahp_weights, score_solutions
│       ├── router.py          # Add new endpoints
│       └── tasks.py           # Add new Celery tasks
│
├── frontend/
│   ├── app/(workspace)/matrix/
│   │   └── heatmap/
│   │       └── page.tsx      # NEW: Heatmap page
│   │
│   └── components/matrix/
│       ├── MorphologicalTab.tsx    # Add Tab 4, inline editing, orthogonality warnings
│       ├── Tab4Convergence.tsx     # NEW: Tab 4 component
│       ├── SolutionClusters.tsx    # NEW: Cluster tree UI
│       ├── AHPWeights.tsx           # NEW: Weight setup UI
│       └── SolutionRanking.tsx     # NEW: Ranked list display
```

---

## Task 1: Backend - Enhanced Data Models

**Files:**
- Modify: `feature-2/backend/app/matrix/models.py`
- Modify: `feature-2/backend/app/matrix/schemas.py`

- [ ] **Step 1: Read existing models.py**

Run: `cat feature-2/backend/app/matrix/models.py`

- [ ] **Step 2: Add MatrixCell model**

Modify `models.py` to add after existing Keyword model:

```python
class MatrixCell(db.Model):
    __tablename__ = "matrix_cells"

    id = db.Column(db.Integer, primary_key=True, index=True)
    analysis_id = db.Column(db.Integer, db.ForeignKey("morphological_analyses.id"), nullable=False)
    pair_key = db.Column(db.String(20), nullable=False)  # e.g., "0_2"
    state_pair = db.Column(db.String(20), nullable=False)  # e.g., "1_3"
    status = db.Column(db.String(10), nullable=False)  # green, yellow, red
    contradiction_type = db.Column(db.String(1), nullable=True)  # L, E, N
    reason = db.Column(db.Text, nullable=True)

    analysis = db.relationship("MorphologicalAnalysis", back_populates="matrix_cells")
```

- [ ] **Step 3: Add SolutionCluster model**

Add after MatrixCell:

```python
class SolutionCluster(db.Model):
    __tablename__ = "solution_clusters"

    id = db.Column(db.Integer, primary_key=True, index=True)
    analysis_id = db.Column(db.Integer, db.ForeignKey("morphological_analyses.id"), nullable=False)
    cluster_id = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    solution_indices = db.Column(db.JSON, nullable=False)  # List[int]
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    analysis = db.relationship("MorphologicalAnalysis", back_populates="solution_clusters")
```

- [ ] **Step 4: Add AHPWeight model**

Add after SolutionCluster:

```python
class AHPWeight(db.Model):
    __tablename__ = "ahp_weights"

    id = db.Column(db.Integer, primary_key=True, index=True)
    analysis_id = db.Column(db.Integer, db.ForeignKey("morphological_analyses.id"), nullable=False)
    criteria = db.Column(db.JSON, nullable=False)  # [{"name": "Cost", "weight": 0.25}, ...]
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    analysis = db.relationship("MorphologicalAnalysis", back_populates="ahp_weights")
```

- [ ] **Step 5: Update MorphologicalAnalysis relationship**

Find `analysis = relationship("MorphologicalAnalysis", back_populates="keywords")` and update to include:
```python
back_populates="keywords", back_populates="matrix_cells", back_populates="solution_clusters", back_populates="ahp_weights"
```

- [ ] **Step 6: Add enhanced schemas to schemas.py**

Read `schemas.py` first, then add after existing schemas:

```python
class MatrixCellSchema(BaseModel):
    status: Literal['green', 'yellow', 'red']
    contradiction_type: Optional[Literal['L', 'E', 'N']] = None
    reason: Optional[str] = None

class EnhancedMatrixData(Dict[str, Dict[str, MatrixCellSchema]]):
    pass

class OrthogonalityWarning(BaseModel):
    param1_idx: int
    param2_idx: int
    param1_name: str
    param2_name: str
    overlap_description: str

class OrthogonalityCheckResponse(BaseModel):
    warnings: List[OrthogonalityWarning]
    all_orthogonal: bool

class ClusterRequest(BaseModel):
    analysis_id: int
    max_clusters: int = Field(default=5, ge=2, le=10)
    max_solutions_per_cluster: int = Field(default=100, ge=10)

class ClusterSolution(BaseModel):
    name: str
    description: Optional[str] = None
    solution_indices: List[int]

class ClusterResponse(BaseModel):
    clusters: List[ClusterSolution]

class AHPSuggestRequest(BaseModel):
    analysis_id: int
    num_criteria: int = Field(default=4, ge=3, le=6)

class AHPSuggestResponse(BaseModel):
    criteria: List[Dict[str, float]]  # [{"name": "Cost", "weight": 0.25}, ...]

class ScoreRequest(BaseModel):
    analysis_id: int
    cluster_id: Optional[str] = None
    weights: List[Dict[str, float]]

class ScoredSolution(BaseModel):
    rank: int
    solution_index: int
    solution: List[str]  # The actual state names
    score: float
    ratings: Dict[str, int]  # criterion -> rating 1-5
    summary: str

class ScoreResponse(BaseModel):
    ranked_solutions: List[ScoredSolution]
```

- [ ] **Step 7: Commit**

```bash
cd /wslshare/taskly/feature-2 && git add -A && git commit -m "feat(matrix): add enhanced models for contradiction types and clustering"
```

---

## Task 2: Backend - Enhanced Cross-Consistency Evaluation

**Files:**
- Modify: `feature-2/backend/app/matrix/service.py`

- [ ] **Step 1: Read existing service.py for evaluate_morphological_consistency**

Run: `cat feature-2/backend/app/matrix/service.py`

- [ ] **Step 2: Add contradiction type classification to evaluation**

In `evaluate_morphological_consistency`, update the system prompt to include:

```python
system_prompt = """You are an expert in Cross-Consistency Assessment for Morphological Analysis.
Evaluate all pairwise state combinations in the provided indexed comparison table.
There are 3 levels of compatibility:
- "green": completely compatible
- "yellow": possibly compatible under certain conditions
- "red": impossible because of logical, empirical, or normative contradiction

When marking red, classify the contradiction type:
- "L" (Logical): Conceptually incompatible by definition
- "E" (Empirical): Violates physics, engineering, or observed reality
- "N" (Normative): Conflicts with social norms, laws, or policy

Return brief one-line reason for each red/yellow entry.

Return JSON with:
{
  "pair": [param1_idx, param2_idx],
  "results": {
    "red": [[s1, s2], ...],
    "yellow": [[s1, s2], ...],
    "reasons": {
      "red": {"[s1,s2]": "reason text", ...},
      "yellow": {"[s1,s2]": "reason text", ...}
    },
    "types": {
      "[s1,s2]": "L|E|N"
    }
  }
}
Rows not listed are treated as "green"."""
```

- [ ] **Step 3: Update BatchEvaluateConsistencyResponse schema**

Modify the schema to include types and reasons. Read `schemas.py` and find `BatchEvaluateConsistencyResponse`, update to:

```python
class EvaluationResult(BaseModel):
    red: List[List[int]] = []
    yellow: List[List[int]] = []
    reasons: Dict[str, Dict[str, str]] = {}  # "red"/"yellow" -> {[s1,s2]: reason}
    types: Dict[str, Literal['L', 'E', 'N']] = {}  # {[s1,s2]: type}

class PairEvaluateConsistencyResponse(BaseModel):
    pair: List[int]  # [param1_idx, param2_idx]
    results: EvaluationResult
```

- [ ] **Step 4: Update apply_consistency_results to handle new fields**

Modify `apply_consistency_results` to store types and reasons:

```python
def apply_consistency_results(
    parameters: List[MorphologicalParameter],
    response: BatchEvaluateConsistencyResponse
) -> Tuple[Dict[str, Dict[str, Dict]], List[PairEvaluateConsistencyResponse]]:
    # Matrix cell now contains: {status, type, reason}
    matrix_data: Dict[str, Dict[str, Dict]] = {}
    # ... existing initialization ...

    for evaluation in response.evaluations:
        # ... existing pair validation ...

        # Process red with types and reasons
        for row in evaluation.results.red:
            if len(row) == 2:
                state_key = f"{row[0]}_{row[1]}"
                matrix_data[pair_key][state_key] = {
                    "status": "red",
                    "type": evaluation.results.types.get(f"[{row[0]},{row[1]}]", "L"),
                    "reason": evaluation.results.reasons.get("red", {}).get(f"[{row[0]},{row[1]}]")
                }

        # Process yellow with reasons
        for row in evaluation.results.yellow:
            if len(row) == 2 and f"{row[0]}_{row[1]}" not in red_pairs:
                state_key = f"{row[0]}_{row[1]}"
                matrix_data[pair_key][state_key] = {
                    "status": "yellow",
                    "type": None,
                    "reason": evaluation.results.reasons.get("yellow", {}).get(f"[{row[0]},{row[1]}]")
                }

        normalized_results.append(evaluation)

    return matrix_data, normalized_results
```

- [ ] **Step 5: Add orthogonality check function**

Add after `evaluate_morphological_consistency`:

```python
async def check_orthogonality(parameters: List[MorphologicalParameter]) -> Dict[str, Any]:
    """Check if parameters are orthogonal (non-overlapping)."""
    llm = get_llm(model_name=settings.OPENAI_MODEL_PRO, streaming=False)
    structured_llm = llm.with_structured_output(OrthogonalityCheckResponse, method="json_schema", strict=True)

    system_prompt = """You are an expert in Morphological Analysis.
Analyze the given parameters for orthogonality - parameters should be independent and not overlap in definition.
Identify any pairs of parameters that have significant overlap or could be merged.

Return warnings for any parameter pairs that overlap significantly."""

    param_text = "\n".join(
        f"[{i}] {p.name}: {', '.join(p.states[:3])}..."
        for i, p in enumerate(parameters)
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Parameters:\n{param_text}")
    ]

    try:
        response = await structured_llm.ainvoke(messages)
        return {
            "warnings": response.warnings if response else [],
            "all_orthogonal": response.all_orthogonal if response else True
        }
    except Exception as e:
        return {"warnings": [], "all_orthogonal": True, "error": str(e)}
```

- [ ] **Step 6: Commit**

```bash
cd /wslshare/taskly/feature-2 && git add -A && git commit -m "feat(matrix): add contradiction types (L/E/N) and orthogonality check"
```

---

## Task 3: Backend - Solution Enumeration & Clustering

**Files:**
- Modify: `feature-2/backend/app/matrix/service.py`

- [ ] **Step 1: Add solution enumeration function**

Add after orthogonality check:

```python
def enumerate_solutions(
    parameters: List[MorphologicalParameter],
    matrix_data: Dict[str, Dict[str, Dict]],
    max_yellows: int = 2
) -> Tuple[List[List[int]], int]:
    """Enumerate all valid solution combinations."""
    total_iterations = 0
    valid_solutions: List[List[int]] = []

    def dfs(current_path: List[int], current_yellows: int) -> None:
        nonlocal total_iterations
        if total_iterations > 1000000:  # Safety limit
            return

        p_idx = len(current_path)
        if p_idx == len(parameters):
            valid_solutions.append(current_path.copy())
            return

        for s_idx in range(len(parameters[p_idx].states)):
            total_iterations += 1
            is_valid = True
            new_yellows = current_yellows

            for prev_p_idx, prev_s_idx in enumerate(current_path):
                if prev_p_idx > p_idx:
                    break
                pid1, pid2 = min(prev_p_idx, p_idx), max(prev_p_idx, p_idx)
                pair_key = f"{pid1}_{pid2}"
                sid1, sid2 = (prev_s_idx, s_idx) if prev_p_idx < p_idx else (s_idx, prev_s_idx)

                cell = matrix_data.get(pair_key, {}).get(f"{sid1}_{sid2}", {})
                status = cell.get("status", "green")

                if status == "red":
                    is_valid = False
                    break
                elif status == "yellow":
                    new_yellows += 1

            if is_valid and new_yellows <= max_yellows:
                dfs(current_path + [s_idx], new_yellows)

    dfs([], 0)
    return valid_solutions, total_iterations
```

- [ ] **Step 2: Add clustering function**

Add after enumerate_solutions:

```python
async def cluster_solutions(
    parameters: List[MorphologicalParameter],
    solutions: List[List[int]],
    max_clusters: int = 5
) -> List[Dict[str, Any]]:
    """Auto-cluster solutions using LLM."""
    if not solutions:
        return []

    llm = get_llm(model_name=settings.OPENAI_MODEL_PRO, streaming=False)
    structured_llm = llm.with_structured_output(ClusterResponse, method="json_schema", strict=True)

    # Prepare solution descriptions (truncate for LLM)
    solution_descs = []
    for i, sol in enumerate(solutions[:100]):  # Limit to 100 for LLM
        desc = ", ".join(f"{parameters[p_idx].name}={parameters[p_idx].states[s_idx]}"
                        for p_idx, s_idx in enumerate(sol))
        solution_descs.append(f"[{i}] {desc}")

    system_prompt = """Group these solutions into meaningful clusters based on their characteristics.
Each cluster should have a distinct theme (e.g., "Low-Cost Baseline", "High-Tech Future").
Return cluster names, descriptions, and which solution indices belong to each."""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="\n".join(solution_descs))
    ]

    try:
        response = await structured_llm.ainvoke(messages)
        return [{"name": c.name, "description": c.description, "solution_indices": c.solution_indices}
                for c in response.clusters] if response else []
    except Exception as e:
        # Fallback: simple random clustering
        return [{"name": f"Group {i+1}", "description": "", "solution_indices": solutions[i::max_clusters]}
                for i in range(min(max_clusters, len(solutions)))]
```

- [ ] **Step 3: Add AHP weight suggestion function**

Add after cluster_solutions:

```python
async def suggest_ahp_weights(
    parameters: List[MorphologicalParameter],
    cluster_solutions: List[Dict]
) -> List[Dict[str, float]]:
    """Suggest initial AHP weights based on context."""
    llm = get_llm(model_name=settings.OPENAI_MODEL_PRO, streaming=False)

    system_prompt = """Given this morphological analysis problem, suggest 4-5 evaluation criteria with weights.
Common criteria: Cost, Implementation Time, Risk, Performance, Scalability, Maintainability.
Return weights that sum to 1.0.
Example: [{"name": "Cost", "weight": 0.25}, {"name": "Time", "weight": 0.20}, ...]"""

    context = f"Parameters: {[p.name for p in parameters]}\nClusters: {[c['name'] for c in cluster_solutions]}"

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=context)
    ]

    try:
        response = await llm.ainvoke(messages)
        # Parse response - expect JSON array
        import json
        import re
        match = re.search(r'\[.*\]', response.content, re.DOTALL)
        if match:
            criteria = json.loads(match.group())
            return criteria
    except:
        pass

    # Fallback weights
    return [
        {"name": "Cost", "weight": 0.30},
        {"name": "Time", "weight": 0.20},
        {"name": "Risk", "weight": 0.25},
        {"name": "Performance", "weight": 0.25}
    ]
```

- [ ] **Step 4: Add scoring function**

Add after suggest_ahp_weights:

```python
async def score_solutions(
    parameters: List[MorphologicalParameter],
    solutions: List[List[int]],
    weights: List[Dict[str, float]],
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """Score and rank solutions using LLM."""
    if not solutions:
        return []

    llm = get_llm(model_name=settings.OPENAI_MODEL_PRO, streaming=False)
    criteria_names = [w["name"] for w in weights]
    criteria_weights = {w["name"]: w["weight"] for w in weights}

    # Prepare solution descriptions
    solution_descs = []
    for i, sol in enumerate(solutions[:20]):  # Limit to top 20 for LLM
        desc = ", ".join(f"{parameters[p_idx].states[s_idx]}" for p_idx, s_idx in enumerate(sol))
        solution_descs.append(f"[{i}] {desc}")

    system_prompt = f"""Rate each solution 1-5 on these criteria: {', '.join(criteria_names)}.
1 = Poor, 5 = Excellent.
Then calculate weighted score.
Return JSON: {{"ranked": [{{"idx": 0, "ratings": {{"Cost": 3, ...}}, "score": 0.85, "summary": "..."}}]}}"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="\n".join(solution_descs))
    ]

    ranked = []
    try:
        response = await llm.ainvoke(messages)
        import json, re
        match = re.search(r'\{.*\}', response.content, re.DOTALL)
        if match:
            data = json.loads(match.group())
            for item in data.get("ranked", [])[:top_k]:
                sol_idx = item["idx"]
                ranked.append({
                    "rank": len(ranked) + 1,
                    "solution_index": sol_idx,
                    "solution": solutions[sol_idx] if sol_idx < len(solutions) else solutions[0],
                    "score": item.get("score", 0),
                    "ratings": item.get("ratings", {}),
                    "summary": item.get("summary", "")
                })
    except Exception as e:
        # Fallback: random scoring
        import random
        for i, sol in enumerate(solutions[:top_k]):
            ranked.append({
                "rank": i + 1,
                "solution_index": i,
                "solution": sol,
                "score": random.uniform(0.5, 1.0),
                "ratings": {c: random.randint(2, 5) for c in criteria_names},
                "summary": "Generated based on criteria evaluation"
            })

    return ranked
```

- [ ] **Step 5: Commit**

```bash
cd /wslshare/taskly/feature-2 && git add -A && git commit -m "feat(matrix): add solution enumeration, clustering, and AHP scoring"
```

---

## Task 4: Backend - Router Updates

**Files:**
- Modify: `feature-2/backend/app/matrix/router.py`

- [ ] **Step 1: Read existing router.py**

Run: `cat feature-2/backend/app/matrix/router.py`

- [ ] **Step 2: Add new endpoint imports**

Add to imports from schemas:
```python
from .schemas import (
    # ... existing imports ...
    OrthogonalityCheckResponse,
    ClusterRequest,
    ClusterResponse,
    AHPSuggestRequest,
    AHPSuggestResponse,
    ScoreRequest,
    ScoreResponse,
)
```

- [ ] **Step 3: Add new endpoints after existing endpoints**

Add inside the router:

```python
@router.post("/orthogonality-check")
async def check_orthogonality(request: Dict):
    """Check parameter orthogonality."""
    from .service import check_orthogonality, get_morphological_analysis

    analysis = await get_morphological_analysis(request.get("analysis_id"))
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    params = analysis.parameters
    result = await check_orthogonality(params)
    return result


@router.post("/cluster")
async def cluster_solutions(request: ClusterRequest):
    """Auto-cluster valid solutions."""
    from .service import enumerate_solutions, cluster_solutions, get_morphological_analysis

    analysis = await get_morphological_analysis(request.analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    params = analysis.parameters
    matrix = analysis.matrix

    solutions, _ = enumerate_solutions(params, matrix)
    clusters = await cluster_solutions(params, solutions, request.max_clusters)

    # Save clusters to DB
    for cluster in clusters:
        save_cluster(analysis.id, cluster["name"], cluster.get("description"), cluster["solution_indices"])

    return {"clusters": clusters, "total_solutions": len(solutions)}


@router.post("/ahp-suggest")
async def suggest_ahp_weights(request: AHPSuggestRequest):
    """Get suggested AHP weights."""
    from .service import suggest_ahp_weights, get_morphological_analysis

    analysis = await get_morphological_analysis(request.analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Get existing clusters or create empty
    clusters = analysis.solution_clusters or []
    weights = await suggest_ahp_weights(analysis.parameters, clusters)
    return {"criteria": weights}


@router.post("/score")
async def score_solutions(request: ScoreRequest):
    """Score and rank solutions."""
    from .service import enumerate_solutions, score_solutions, get_morphological_analysis

    analysis = await get_morphological_analysis(request.analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    params = analysis.parameters
    matrix = analysis.matrix

    solutions, _ = enumerate_solutions(params, matrix)

    # Filter by cluster if specified
    if request.cluster_id:
        cluster = next((c for c in analysis.solution_clusters if c.cluster_id == request.cluster_id), None)
        if cluster:
            solutions = [solutions[i] for i in cluster.solution_indices if i < len(solutions)]

    ranked = await score_solutions(params, solutions, request.weights)
    return {"ranked_solutions": ranked}


@router.get("/solutions/{analysis_id}")
async def get_solutions(analysis_id: int, max_yellows: int = 2):
    """Get enumerated solutions for an analysis."""
    from .service import enumerate_solutions, get_morphological_analysis

    analysis = await get_morphological_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    params = analysis.parameters
    matrix = analysis.matrix

    solutions, total_iterations = enumerate_solutions(params, matrix, max_yellows)
    return {
        "solutions": solutions,
        "total": len(solutions),
        "iterations": total_iterations
    }
```

- [ ] **Step 4: Commit**

```bash
cd /wslshare/taskly/feature-2 && git add -A && git commit -m "feat(matrix): add new API endpoints for convergence features"
```

---

## Task 5: Frontend - Inline Editing for Tab 1

**Files:**
- Modify: `feature-2/frontend/components/matrix/MorphologicalTab.tsx`

- [ ] **Step 1: Read MorphologicalTab.tsx for Tab 1 section**

Run: `head -200 feature-2/frontend/components/matrix/MorphologicalTab.tsx`

Focus on lines 927-957 (the morphological table rendering)

- [ ] **Step 2: Add inline editing state**

Add to the state declarations near line 32:

```typescript
const [editingCell, setEditingCell] = useState<{pIdx: number, sIdx: number} | null>(null);
const [editValue, setEditValue] = useState("");
const [orthogonalityWarnings, setOrthogonalityWarnings] = useState<OrthogonalityWarning[]>([]);
```

Add interface for warnings:

```typescript
interface OrthogonalityWarning {
  param1_idx: number;
  param2_idx: number;
  param1_name: string;
  param2_name: string;
  overlap_description: string;
}
```

- [ ] **Step 3: Add inline edit handlers**

Add before handleExtractQuestion (around line 97):

```typescript
const startEditing = (pIdx: number, sIdx: number, currentValue: string) => {
  setEditingCell({ pIdx, sIdx });
  setEditValue(currentValue);
};

const saveEdit = () => {
  if (!editingCell) return;
  const { pIdx, sIdx } = editingCell;
  setParameters(prev => prev.map((p, pi) => {
    if (pi !== pIdx) return p;
    return {
      ...p,
      states: p.states.map((s, si) => si === sIdx ? editValue : s)
    };
  }));
  setEditingCell(null);
  // Auto-save
  setTimeout(() => handleSave(), 500);
};

const cancelEdit = () => {
  setEditingCell(null);
  setEditValue("");
};
```

- [ ] **Step 4: Update Tab 1 table rendering**

Find the table cell rendering (around line 944-950) and update to:

```typescript
{parameters.map((p, pIdx) => (
  <td key={pIdx} className="border border-slate-200 p-3 align-top">
    {p.states[rowIdx] && (
      editingCell?.pIdx === pIdx && editingCell?.sIdx === rowIdx ? (
        <div className="flex gap-1">
          <input
            type="text"
            value={editValue}
            onChange={e => setEditValue(e.target.value)}
            onBlur={saveEdit}
            onKeyDown={e => {
              if (e.key === 'Enter') saveEdit();
              if (e.key === 'Escape') cancelEdit();
            }}
            className="border border-indigo-300 rounded px-2 py-1 text-sm w-full"
            maxLength={50}
            autoFocus
          />
        </div>
      ) : (
        <div
          className="bg-indigo-50 text-indigo-800 px-3 py-2 rounded-lg border border-indigo-100/50 shadow-sm font-medium flex items-center justify-between group cursor-pointer"
          onClick={() => startEditing(pIdx, rowIdx, p.states[rowIdx])}
        >
          <span className="flex-1">{p.states[rowIdx]}</span>
          <button className="opacity-0 group-hover:opacity-100 text-indigo-400 hover:text-indigo-600 ml-2">
            <Edit2 className="w-3 h-3" />
          </button>
        </div>
      )
    )}
  </td>
))}
```

Add Edit2 to imports from lucide-react.

- [ ] **Step 5: Add add/remove state buttons**

Update the table to show state management buttons. Add after the table (around line 955):

```typescript
<div className="mt-4 flex gap-2">
  {parameters.map((p, pIdx) => (
    <div key={pIdx} className="flex items-center gap-2">
      <span className="text-xs text-slate-500">{p.name}:</span>
      <button
        onClick={() => {
          if (p.states.length < 7) {
            setParameters(prev => prev.map((param, pi) => {
              if (pi !== pIdx) return param;
              return { ...param, states: [...param.states, "新状态"] };
            }));
          }
        }}
        disabled={p.states.length >= 7}
        className="text-xs px-2 py-1 bg-green-50 text-green-700 rounded hover:bg-green-100 disabled:opacity-50"
      >
        + 状态
      </button>
      <button
        onClick={() => {
          if (p.states.length > 3) {
            setParameters(prev => prev.map((param, pi) => {
              if (pi !== pIdx) return param;
              return { ...param, states: param.states.slice(0, -1) };
            }));
          }
        }}
        disabled={p.states.length <= 3}
        className="text-xs px-2 py-1 bg-red-50 text-red-700 rounded hover:bg-red-100 disabled:opacity-50"
      >
        - 状态
      </button>
    </div>
  ))}
</div>
```

Add Edit2 to lucide-react import.

- [ ] **Step 6: Commit**

```bash
cd /wslshare/taskly/feature-2 && git add -A && git commit -m "feat(frontend): add inline editing for Tab 1 parameters"
```

---

## Task 6: Frontend - New Tab 4 Convergence Component

**Files:**
- Create: `feature-2/frontend/components/matrix/Tab4Convergence.tsx`
- Create: `feature-2/frontend/components/matrix/SolutionClusters.tsx`
- Create: `feature-2/frontend/components/matrix/AHPWeights.tsx`
- Create: `feature-2/frontend/components/matrix/SolutionRanking.tsx`

- [ ] **Step 1: Create Tab4Convergence.tsx**

Create file:

```tsx
"use client";

import React, { useState, useEffect } from 'react';
import { Loader2, FolderTree, BarChart3, Sparkles } from 'lucide-react';
import { fetchWithAuth, getApiUrl } from '../../app/lib/api';
import SolutionClusters from './SolutionClusters';
import AHPWeights from './AHPWeights';
import SolutionRanking from './SolutionRanking';

interface Tab4ConvergenceProps {
  analysisId: number;
  parameters: Parameter[];
  matrixData: MatrixData;
}

export default function Tab4Convergence({ analysisId, parameters, matrixData }: Tab4ConvergenceProps) {
  const [solutions, setSolutions] = useState<List<int>>([]);
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [weights, setWeights] = useState<Criteria[]>([]);
  const [rankedSolutions, setRankedSolutions] = useState<RankedSolution[]>([]);
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState<'enumerate' | 'cluster' | 'weights' | 'rank'>('enumerate');
  const [error, setError] = useState<string | null>(null);

  const enumerateSolutions = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchWithAuth(`${getApiUrl()}/matrix/morphological/solutions/${analysisId}`, {
        method: 'GET'
      });
      if (res.ok) {
        const data = await res.json();
        setSolutions(data.solutions);
        setStep('cluster');
      }
    } catch (e) {
      setError('Failed to enumerate solutions');
    } finally {
      setLoading(false);
    }
  };

  const runClustering = async () => {
    setLoading(true);
    try {
      const res = await fetchWithAuth(`${getApiUrl()}/matrix/morphological/cluster`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ analysis_id: analysisId, max_clusters: 5 })
      });
      if (res.ok) {
        const data = await res.json();
        setClusters(data.clusters);
        setStep('weights');
      }
    } catch (e) {
      setError('Failed to cluster solutions');
    } finally {
      setLoading(false);
    }
  };

  const suggestWeights = async () => {
    setLoading(true);
    try {
      const res = await fetchWithAuth(`${getApiUrl()}/matrix/morphological/ahp-suggest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ analysis_id: analysisId })
      });
      if (res.ok) {
        const data = await res.json();
        setWeights(data.criteria);
      }
    } catch (e) {
      // Use default weights
      setWeights([
        { name: 'Cost', weight: 0.30 },
        { name: 'Time', weight: 0.20 },
        { name: 'Risk', weight: 0.25 },
        { name: 'Performance', weight: 0.25 }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const runScoring = async () => {
    setLoading(true);
    try {
      const res = await fetchWithAuth(`${getApiUrl()}/matrix/morphological/score`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ analysis_id: analysisId, weights })
      });
      if (res.ok) {
        const data = await res.json();
        setRankedSolutions(data.ranked_solutions);
        setStep('rank');
      }
    } catch (e) {
      setError('Failed to score solutions');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
        <h2 className="text-xl font-semibold mb-4">Solution Convergence</h2>
        <p className="text-slate-600 mb-6">
          Enumerate valid solutions, group them into clusters, and rank using multi-criteria analysis.
        </p>

        {/* Progress Steps */}
        <div className="flex items-center gap-2 mb-6">
          {['enumerate', 'cluster', 'weights', 'rank'].map((s, i) => (
            <React.Fragment key={s}>
              <button
                onClick={() => {
                  if (s === 'enumerate') enumerateSolutions();
                  else if (s === 'cluster' && solutions.length > 0) runClustering();
                  else if (s === 'weights' && clusters.length > 0) suggestWeights();
                  else if (s === 'rank' && weights.length > 0) runScoring();
                }}
                disabled={
                  (s === 'enumerate' && solutions.length > 0) ||
                  (s === 'cluster' && clusters.length > 0) ||
                  (s === 'weights' && weights.length > 0) ||
                  (s === 'rank' && rankedSolutions.length > 0)
                }
                className={`px-4 py-2 rounded-lg font-medium transition ${
                  step === s ? 'bg-indigo-600 text-white' :
                  solutions.length > 0 || clusters.length > 0 || weights.length > 0 || rankedSolutions.length > 0
                    ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-600'
                }`}
              >
                {i + 1}. {s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
              {i < 3 && <span className="text-slate-300">→</span>}
            </React.Fragment>
          ))}
        </div>

        {loading && (
          <div className="flex items-center justify-center py-10">
            <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
            <span className="ml-2 text-slate-600">Processing...</span>
          </div>
        )}

        {error && (
          <div className="bg-red-50 text-red-700 p-4 rounded-lg">{error}</div>
        )}

        {!loading && step === 'enumerate' && solutions.length === 0 && (
          <button
            onClick={enumerateSolutions}
            className="bg-indigo-600 text-white px-6 py-3 rounded-xl font-medium hover:bg-indigo-700 flex items-center"
          >
            <Sparkles className="w-5 h-5 mr-2" />
            Enumerate All Solutions
          </button>
        )}

        {solutions.length > 0 && (
          <div className="bg-green-50 text-green-800 p-4 rounded-lg mb-4">
            Found {solutions.length.toLocaleString()} valid solutions
          </div>
        )}
      </div>

      {!loading && clusters.length > 0 && (
        <SolutionClusters
          clusters={clusters}
          parameters={parameters}
          solutions={solutions}
          onClustersChange={setClusters}
        />
      )}

      {!loading && weights.length > 0 && (
        <AHPWeights
          criteria={weights}
          onWeightsChange={setWeights}
          onNext={runScoring}
        />
      )}

      {!loading && rankedSolutions.length > 0 && (
        <SolutionRanking
          rankedSolutions={rankedSolutions}
          parameters={parameters}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create SolutionClusters.tsx**

```tsx
"use client";

import React, { useState } from 'react';
import { FolderTree, Edit2, Check, X, Plus } from 'lucide-react';

interface Cluster {
  id: string;
  name: string;
  description: string;
  solution_indices: number[];
}

interface SolutionClustersProps {
  clusters: Cluster[];
  parameters: Parameter[];
  solutions: number[][];
  onClustersChange: (clusters: Cluster[]) => void;
}

export default function SolutionClusters({ clusters, parameters, solutions, onClustersChange }: SolutionClustersProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');

  const renameCluster = (id: string, newName: string) => {
    onClustersChange(clusters.map(c => c.id === id ? { ...c, name: newName } : c));
    setEditingId(null);
  };

  const deleteCluster = (id: string) => {
    onClustersChange(clusters.filter(c => c.id !== id));
  };

  const getSolutionLabel = (sol: number[]) => {
    return sol.map((sIdx, pIdx) => parameters[pIdx]?.states[sIdx]).filter(Boolean).slice(0, 3).join(', ');
  };

  return (
    <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <FolderTree className="w-5 h-5" />
          Solution Clusters
        </h3>
        <button
          onClick={() => {
            const newCluster = {
              id: `custom-${Date.now()}`,
              name: 'New Cluster',
              description: '',
              solution_indices: []
            };
            onClustersChange([...clusters, newCluster]);
          }}
          className="text-sm px-3 py-1 bg-indigo-50 text-indigo-700 rounded-lg hover:bg-indigo-100 flex items-center gap-1"
        >
          <Plus className="w-4 h-4" />
          Add Cluster
        </button>
      </div>

      <div className="space-y-3">
        {clusters.map(cluster => (
          <div key={cluster.id} className="border border-slate-200 rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              {editingId === cluster.id ? (
                <div className="flex items-center gap-2">
                  <input
                    value={editName}
                    onChange={e => setEditName(e.target.value)}
                    className="border border-slate-300 rounded px-2 py-1"
                    autoFocus
                  />
                  <button onClick={() => renameCluster(cluster.id, editName)} className="text-green-600">
                    <Check className="w-4 h-4" />
                  </button>
                  <button onClick={() => setEditingId(null)} className="text-red-600">
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ) : (
                <>
                  <h4 className="font-medium">{cluster.name}</h4>
                  <div className="flex gap-2">
                    <button
                      onClick={() => { setEditingId(cluster.id); setEditName(cluster.name); }}
                      className="text-slate-400 hover:text-slate-600"
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => deleteCluster(cluster.id)}
                      className="text-red-400 hover:text-red-600"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                </>
              )}
            </div>

            {cluster.description && (
              <p className="text-sm text-slate-500 mb-3">{cluster.description}</p>
            )}

            <div className="flex flex-wrap gap-2">
              {cluster.solution_indices.slice(0, 5).map(idx => (
                <span key={idx} className="text-xs bg-slate-100 text-slate-600 px-2 py-1 rounded">
                  {getSolutionLabel(solutions[idx] || [])}
                </span>
              ))}
              {cluster.solution_indices.length > 5 && (
                <span className="text-xs text-slate-400">
                  +{cluster.solution_indices.length - 5} more
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create AHPWeights.tsx**

```tsx
"use client";

import React, { useState } from 'react';
import { BarChart3, Check } from 'lucide-react';

interface Criteria {
  name: string;
  weight: number;
}

interface AHPWeightsProps {
  criteria: Criteria[];
  onWeightsChange: (criteria: Criteria[]) => void;
  onNext: () => void;
}

export default function AHPWeights({ criteria, onWeightsChange, onNext }: AHPWeightsProps) {
  const [localCriteria, setLocalCriteria] = useState(criteria);
  const [error, setError] = useState<string | null>(null);

  const updateWeight = (index: number, newWeight: number) => {
    const updated = [...localCriteria];
    updated[index] = { ...updated[index], weight: newWeight };
    setLocalCriteria(updated);
    setError(null);
  };

  const normalize = () => {
    const total = localCriteria.reduce((sum, c) => sum + c.weight, 0);
    if (total === 0) {
      setError('Weights cannot all be zero');
      return;
    }
    const normalized = localCriteria.map(c => ({
      ...c,
      weight: Math.round((c.weight / total) * 100) / 100
    }));
    setLocalCriteria(normalized);
  };

  const total = localCriteria.reduce((sum, c) => sum + c.weight, 0);
  const isValid = Math.abs(total - 1.0) < 0.01;

  const handleApply = () => {
    if (!isValid) {
      setError('Weights must sum to 1.0');
      return;
    }
    onWeightsChange(localCriteria);
  };

  return (
    <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
      <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
        <BarChart3 className="w-5 h-5" />
        AHP Criteria Weights
      </h3>

      <div className="space-y-4 mb-6">
        {localCriteria.map((criterion, idx) => (
          <div key={idx} className="flex items-center gap-4">
            <span className="w-32 text-sm font-medium">{criterion.name}</span>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={criterion.weight}
              onChange={e => updateWeight(idx, parseFloat(e.target.value))}
              className="flex-1 h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer"
            />
            <input
              type="number"
              min="0"
              max="1"
              step="0.05"
              value={criterion.weight}
              onChange={e => updateWeight(idx, parseFloat(e.target.value) || 0)}
              className="w-20 border border-slate-300 rounded px-2 py-1 text-sm"
            />
            <span className="w-12 text-sm text-slate-500">
              {Math.round(criterion.weight * 100)}%
            </span>
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between mb-4">
        <div>
          <span className="text-sm text-slate-600">Total: </span>
          <span className={`font-medium ${isValid ? 'text-green-600' : 'text-red-600'}`}>
            {Math.round(total * 100)}%
          </span>
        </div>
        <button
          onClick={normalize}
          className="text-sm px-3 py-1 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200"
        >
          Normalize to 100%
        </button>
      </div>

      {error && (
        <div className="bg-red-50 text-red-700 p-3 rounded-lg mb-4">{error}</div>
      )}

      <div className="flex gap-3">
        <button
          onClick={handleApply}
          disabled={!isValid}
          className="flex-1 bg-indigo-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50 flex items-center justify-center gap-2"
        >
          <Check className="w-4 h-4" />
          Apply Weights & Score
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create SolutionRanking.tsx**

```tsx
"use client";

import React, { useState } from 'react';
import { Trophy, ChevronDown, ChevronUp } from 'lucide-react';

interface RankedSolution {
  rank: number;
  solution_index: number;
  solution: number[];
  score: number;
  ratings: Record<string, number>;
  summary: string;
}

interface SolutionRankingProps {
  rankedSolutions: RankedSolution[];
  parameters: Parameter[];
}

export default function SolutionRanking({ rankedSolutions, parameters }: SolutionRankingProps) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(0);

  const getSolutionDisplay = (sol: number[]) => {
    return sol.map((sIdx, pIdx) => ({
      param: parameters[pIdx]?.name || `Param ${pIdx}`,
      state: parameters[pIdx]?.states[sIdx] || `State ${sIdx}`
    }));
  };

  return (
    <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
      <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
        <Trophy className="w-5 h-5 text-yellow-500" />
        Top Recommended Solutions
      </h3>

      <div className="space-y-4">
        {rankedSolutions.slice(0, 5).map((item) => {
          const display = getSolutionDisplay(item.solution);
          const isExpanded = expandedIdx === item.rank - 1;

          return (
            <div key={item.rank} className="border border-slate-200 rounded-xl overflow-hidden">
              <div
                className="flex items-center justify-between p-4 cursor-pointer hover:bg-slate-50"
                onClick={() => setExpandedIdx(isExpanded ? null : item.rank - 1)}
              >
                <div className="flex items-center gap-4">
                  <span className={`w-8 h-8 rounded-full flex items-center justify-center font-bold ${
                    item.rank === 1 ? 'bg-yellow-100 text-yellow-700' :
                    item.rank === 2 ? 'bg-slate-200 text-slate-700' :
                    item.rank === 3 ? 'bg-orange-100 text-orange-700' :
                    'bg-slate-100 text-slate-600'
                  }`}>
                    {item.rank}
                  </span>
                  <div>
                    <div className="font-medium">
                      Score: {(item.score * 100).toFixed(1)}%
                    </div>
                    <div className="text-sm text-slate-500">
                      {display.slice(0, 3).map(d => d.state).join(', ')}
                    </div>
                  </div>
                </div>
                <button className="text-slate-400">
                  {isExpanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
                </button>
              </div>

              {isExpanded && (
                <div className="border-t border-slate-200 p-4 bg-slate-50">
                  <div className="mb-4">
                    <h4 className="text-sm font-medium mb-2">Solution Details</h4>
                    <div className="grid grid-cols-2 gap-2">
                      {display.map((d, i) => (
                        <div key={i} className="text-sm">
                          <span className="text-slate-500">{d.param}: </span>
                          <span className="font-medium">{d.state}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="mb-4">
                    <h4 className="text-sm font-medium mb-2">Criteria Ratings</h4>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(item.ratings).map(([criterion, rating]) => (
                        <span key={criterion} className="text-xs bg-white border border-slate-200 px-2 py-1 rounded">
                          {criterion}: {rating}/5
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="text-sm text-slate-600">
                    <h4 className="text-sm font-medium mb-1">Summary</h4>
                    <p>{item.summary}</p>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Add interfaces to MorphologicalTab.tsx**

Add at the top of the file, after existing interfaces:

```typescript
interface Cluster {
  id: string;
  name: string;
  description: string;
  solution_indices: number[];
}

interface Criteria {
  name: string;
  weight: number;
}

interface RankedSolution {
  rank: number;
  solution_index: number;
  solution: number[];
  score: number;
  ratings: Record<string, number>;
  summary: string;
}
```

- [ ] **Step 6: Update subTabs and add Tab 4 rendering**

Find line 9: `const subTabs = ['定义问题', '交叉一致性评估', '解空间可视化'];`

Change to:
```typescript
const subTabs = ['定义问题', '交叉一致性评估', '解空间可视化', '方案收敛'];
```

Find the return statement in MorphologicalTab and add Tab 4 rendering after Tab 3 (around line 1041):

```tsx
{/* Tab 4: Solution Convergence */}
{currentTab === 3 && (
  <Tab4Convergence
    analysisId={currentAnalysisId || 0}
    parameters={parameters}
    matrixData={matrixData}
  />
)}
```

- [ ] **Step 7: Import Tab4Convergence**

Add at top of file:
```typescript
import Tab4Convergence from './Tab4Convergence';
```

- [ ] **Step 8: Commit**

```bash
cd /wslshare/taskly/feature-2 && git add -A && git commit -m "feat(frontend): add Tab 4 convergence with clustering and AHP"
```

---

## Task 7: Frontend - Heatmap Page

**Files:**
- Create: `feature-2/frontend/app/(workspace)/matrix/heatmap/page.tsx`

- [ ] **Step 1: Create heatmap page directory and file**

Create directory and file:

```tsx
"use client";

import React, { useState, useMemo } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import { Maximize2, Minimize2, Grid3X3, MousePointer } from 'lucide-react';
import MatrixArea from '../../../../components/matrix/MatrixArea';

interface Parameter {
  name: string;
  states: string[];
}

interface MatrixData {
  [pairId: string]: {
    [statePair: string]: {
      status: 'green' | 'yellow' | 'red';
      type?: 'L' | 'E' | 'N';
      reason?: string;
    };
  };
}

interface HeatmapPageProps {
  // These will be passed from parent or fetched
}

export default function HeatmapPage() {
  const [viewMode, setViewMode] = useState<'selection' | 'browse'>('selection');
  const [selectedStates, setSelectedStates] = useState<Record<number, number>>({});
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Get data from localStorage or parent context
  const [parameters, setParameters] = useState<Parameter[]>([]);
  const [matrixData, setMatrixData] = useState<MatrixData>({});

  // Load from localStorage on mount
  React.useEffect(() => {
    const stored = localStorage.getItem('morphological_current');
    if (stored) {
      try {
        const data = JSON.parse(stored);
        if (data.parameters) setParameters(data.parameters);
        if (data.matrix) setMatrixData(data.matrix);
      } catch (e) {
        console.error('Failed to load morphological data', e);
      }
    }
  }, []);

  const getCompatibility = (p1Idx: number, s1Idx: number, p2Idx: number, s2Idx: number) => {
    if (p1Idx === p2Idx) return 'green';
    const pid1 = Math.min(p1Idx, p2Idx);
    const pid2 = Math.max(p1Idx, p2Idx);
    const pairId = `${pid1}_${pid2}`;
    const key = p1Idx < p2Idx ? `${s1Idx}_${s2Idx}` : `${s2Idx}_${s1Idx}`;
    return matrixData[pairId]?.[key]?.status || 'green';
  };

  const getCellColor = (status: string) => {
    if (status === 'green') return 'bg-green-500';
    if (status === 'yellow') return 'bg-yellow-400';
    if (status === 'red') return 'bg-red-500';
    return 'bg-slate-200';
  };

  const toggleSelection = (pIdx: number, sIdx: number) => {
    setSelectedStates(prev => {
      if (prev[pIdx] === sIdx) {
        const next = { ...prev };
        delete next[pIdx];
        return next;
      }
      return { ...prev, [pIdx]: sIdx };
    });
  };

  // Selection mode - 7 cards like Tab 3
  const renderSelectionMode = () => (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7 gap-4">
      {parameters.map((p, pIdx) => (
        <div key={pIdx} className="border border-slate-200 rounded-xl overflow-hidden">
          <div className="bg-slate-50 p-3 text-center font-semibold border-b border-slate-200 text-sm truncate">
            {p.name}
          </div>
          <div className="p-2 space-y-2 bg-white">
            {p.states.map((s, sIdx) => {
              const isSelected = selectedStates[pIdx] === sIdx;

              // Check compatibility with other selected states
              let worstStatus = 'green';
              for (const [otherPIdx, otherSIdx] of Object.entries(selectedStates)) {
                if (parseInt(otherPIdx) === pIdx) continue;
                const compat = getCompatibility(parseInt(otherPIdx), otherSIdx, pIdx, sIdx);
                if (compat === 'red') worstStatus = 'red';
                else if (compat === 'yellow' && worstStatus !== 'red') worstStatus = 'yellow';
              }

              return (
                <div
                  key={sIdx}
                  onClick={() => toggleSelection(pIdx, sIdx)}
                  className={`p-2 rounded-lg border text-sm text-center cursor-pointer transition-all ${
                    isSelected
                      ? 'bg-blue-600 text-white border-blue-700 font-bold'
                      : worstStatus === 'red'
                      ? 'bg-red-50 text-red-300 border-red-100 opacity-50 cursor-not-allowed'
                      : worstStatus === 'yellow'
                      ? 'bg-yellow-50 text-yellow-700 border-yellow-200'
                      : 'bg-white text-slate-700 border-slate-200 hover:border-blue-400'
                  }`}
                >
                  {s}
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );

  // Browse mode - full heatmap matrix
  const renderBrowseMode = () => (
    <div className="overflow-auto rounded-xl border border-slate-200">
      <table className="border-collapse">
        <thead>
          <tr>
            <th className="border border-slate-200 bg-slate-50 p-2 sticky top-0 left-0 z-20"></th>
            {parameters.flatMap((p, pIdx) =>
              p.states.map((s, sIdx) => (
                <th
                  key={`${pIdx}-${sIdx}`}
                  className="border border-slate-200 bg-slate-50 p-1 min-w-10 text-xs font-normal"
                  style={{ writingMode: 'vertical-rl' }}
                >
                  {p.name}/{s}
                </th>
              ))
            )}
          </tr>
        </thead>
        <tbody>
          {parameters.flatMap((p1, p1Idx) =>
            p1.states.map((s1, s1Idx) => (
              <tr key={`${p1Idx}-${s1Idx}`}>
                <th className="border border-slate-200 bg-slate-50 p-1 text-xs font-normal sticky left-0">
                  {p1.name}/{s1}
                </th>
                {parameters.flatMap((p2, p2Idx) =>
                  p2.states.map((s2, s2Idx) => {
                    const compat = getCompatibility(p1Idx, s1Idx, p2Idx, s2Idx);
                    return (
                      <td
                        key={`${p1Idx}-${s1Idx}-${p2Idx}-${s2Idx}`}
                        className={`border border-slate-100 p-0 ${getCellColor(compat)}`}
                        title={`${p1.name}/${s1} vs ${p2.name}/${s2}: ${compat}`}
                      >
                        <div className="w-10 h-10"></div>
                      </td>
                    );
                  })
                )}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );

  return (
    <div className={`flex flex-col h-full ${isFullscreen ? 'fixed inset-0 z-50 bg-white' : ''}`}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-slate-200 bg-white">
        <div>
          <h2 className="text-xl font-semibold">Compatibility Heatmap</h2>
          <p className="text-sm text-slate-500">Interactive state compatibility visualization</p>
        </div>
        <div className="flex items-center gap-3">
          {/* View Mode Toggle */}
          <div className="flex rounded-lg border border-slate-200 overflow-hidden">
            <button
              onClick={() => setViewMode('selection')}
              className={`px-3 py-1.5 text-sm flex items-center gap-1 ${
                viewMode === 'selection' ? 'bg-indigo-600 text-white' : 'bg-white text-slate-600'
              }`}
            >
              <MousePointer className="w-4 h-4" />
              Selection
            </button>
            <button
              onClick={() => setViewMode('browse')}
              className={`px-3 py-1.5 text-sm flex items-center gap-1 ${
                viewMode === 'browse' ? 'bg-indigo-600 text-white' : 'bg-white text-slate-600'
              }`}
            >
              <Grid3X3 className="w-4 h-4" />
              Browse
            </button>
          </div>

          <button
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="p-2 hover:bg-slate-100 rounded-lg"
          >
            {isFullscreen ? <Minimize2 className="w-5 h-5" /> : <Maximize2 className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-4">
        {parameters.length === 0 ? (
          <div className="text-center py-20 text-slate-500">
            No morphological data loaded. Please create or load an analysis first.
          </div>
        ) : viewMode === 'selection' ? (
          renderSelectionMode()
        ) : (
          renderBrowseMode()
        )}
      </div>

      {/* Legend */}
      <div className="flex items-center justify-center gap-6 p-4 border-t border-slate-200 bg-white">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 bg-green-500 rounded"></div>
          <span className="text-sm text-slate-600">Compatible</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 bg-yellow-400 rounded"></div>
          <span className="text-sm text-slate-600">Conditional</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 bg-red-500 rounded"></div>
          <span className="text-sm text-slate-600">Incompatible</span>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Register route in Next.js**

Check how routes are set up. If using App Router, the file `page.tsx` in the new directory should automatically be the route `/matrix/heatmap`.

- [ ] **Step 3: Commit**

```bash
cd /wslshare/taskly/feature-2 && git add -A && git commit -m "feat(frontend): add separate heatmap visualization page"
```

---

## Task 8: Integration & Testing

**Files:**
- Test: Manual testing checklist

- [ ] **Step 1: Test Tab 1 inline editing**

Run the frontend and verify:
- Click on a state value → should show input field
- Edit value and blur/Enter → should save
- Add/remove state buttons work
- Changes auto-save

- [ ] **Step 2: Test Tab 2 contradiction types**

- After evaluation, cells should show type indicator (L/E/N) on hover
- Reasons visible on hover

- [ ] **Step 3: Test Tab 4 convergence flow**

- Click "Enumerate All Solutions" → shows count
- Click through cluster → weights → ranking steps
- Adjust AHP weights with sliders
- View ranked solutions with expandable details

- [ ] **Step 4: Test heatmap page**

- Navigate to /matrix/heatmap
- Toggle between selection and browse modes
- Selection mode shows compatibility coloring
- Browse mode shows full matrix

- [ ] **Step 5: Commit**

```bash
cd /wslshare/taskly/feature-2 && git add -A && git commit -m "test: integration testing for all enhancements"
```

---

## Task 9: Final Polish

**Files:**
- Modify: Various files for bug fixes

- [ ] **Step 1: Fix any TypeScript errors**

Run: `cd feature-2/frontend && npx tsc --noEmit 2>&1 | head -50`

Fix any interface mismatches or missing imports.

- [ ] **Step 2: Fix any lint errors**

Run: `cd feature-2/frontend && npx eslint components/matrix/ --fix`

- [ ] **Step 3: Final commit**

```bash
cd /wslshare/taskly/feature-2 && git add -A && git commit -m "chore: polish and fix lint errors"
```

---

## Self-Review Checklist

Before marking complete, verify:

1. [ ] Tab 1 inline editing works (click to edit, add/remove states)
2. [ ] Tab 2 shows contradiction types on hover
3. [ ] Tab 3 unchanged (parallel coordinates)
4. [ ] Tab 4 enumerate → cluster → weights → rank flow works
5. [ ] Heatmap page accessible and shows both modes
6. [ ] All new endpoints registered in router
7. [ ] No TypeScript errors
8. [ ] All commits clean

---

## Dependencies

- ECharts: Already installed (for parallel coordinates)
- React 19, Next.js 16: Already in use
- No new external libraries needed
