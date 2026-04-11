# Morphological Analysis Enhancement Design
**Feature Branch**: feature-2
**Date**: 2026-04-11
**Status**: Draft

---

## Overview

Enhance the existing morphological analysis implementation with:
1. Better parameter extraction with orthogonality verification
2. Contradiction classification with brief explanations
3. New Tab 4: Solution Convergence (clustering + AHP)
4. Separate Heatmap page

---

## Tab 1: Problem Definition (Enhanced)

### 1.1 Inline Editing
- **Trigger**: Click on parameter name or state value
- **Behavior**: Converts to input field, blur/Enter saves
- **Validation**: Max 7 states per parameter, max 50 chars per state

### 1.2 Orthogonality Check
- **Trigger**: After LLM generates parameters, before user edits
- **LLM Analysis**: Review pairs of parameters for overlap
- **Display**: Warning icon on potentially overlapping parameters
- **Action**: User can merge, split, or ignore

### 1.3 Parameter Management
- **Add state**: "+" button per parameter (max 7)
- **Remove state**: "×" button on each state (min 3)
- **Regenerate single param**: Regenerate icon on param header
- **Reorder**: Drag handle on states

### 1.4 Strict 7×7 Enforcement
- Exactly 7 parameters
- Each parameter has 3-7 states
- No empty states allowed

---

## Tab 2: Cross-Consistency Assessment (Enhanced)

### 2.1 Contradiction Classification
| Code | Type | Description |
|------|------|-------------|
| L | Logical | Conceptually incompatible |
| E | Empirical | Violates physics/engineering |
| N | Normative | Social/legal/policy conflict |

### 2.2 Brief Explanations
- One-line reason per contradiction type
- Stored in matrix metadata
- Toggle to show/hide on hover

### 2.3 Batch Pre-calculation Table
```json
{
  "pair": ["Environment", "Power_Source"],
  "comparisons": [
    {"s1": 0, "s2": 3, "status": "red", "type": "L", "reason": "Underwater requires sealed power"}
  ]
}
```

### 2.4 JSON Export/Import
- Export: Download full evaluation as JSON
- Import: Load from JSON file
- Format: Compatible with internal schema

---

## Tab 3: Solution Space Explorer

**No changes** - Keep existing parallel coordinates visualization.

Heatmap moved to separate page.

---

## New Tab 4: Solution Convergence

### 4.1 Solution Enumeration
- Enumerate all valid solution combinations
- Respect red (impossible) constraints
- Allow up to N yellows (configurable, default 2)
- Display count: "Found 847 valid solutions"

### 4.2 Auto-Clustering
- **Input**: All valid solutions
- **LLM Prompt**: Group by similar characteristics
- **Output**:
```json
{
  "clusters": [
    {
      "name": "Low-Cost Baseline",
      "description": "Uses existing infrastructure",
      "solution_indices": [0, 3, 7, 12]
    },
    {
      "name": "High-Tech Future",
      "description": "Advanced but expensive",
      "solution_indices": [1, 4, 8, 15]
    }
  ]
}
```

### 4.3 Hybrid Refinement
- **View**: Tree/folder view of clusters
- **Actions**:
  - Rename cluster
  - Merge clusters
  - Split cluster
  - Move solution between clusters
  - Create new custom cluster

### 4.4 AHP Weight Setup
- **LLM Suggestion**: Propose initial criteria weights
  - Cost (e.g., 0.25)
  - Implementation Time (e.g., 0.20)
  - Risk (e.g., 0.30)
  - Performance (e.g., 0.25)
- **User Adjustment**: Slider or direct input per criterion
- **Validation**: Weights must sum to 1.0

### 4.5 Scoring & Ranking
- **Per Solution Score**: Weighted sum of criterion ratings
- **LLM Rating**: For each solution in Top-K, rate 1-5 per criterion
- **Output**: Ranked list with scores and reasoning
```json
{
  "ranked_solutions": [
    {
      "rank": 1,
      "solution_index": 42,
      "score": 0.87,
      "ratings": {"cost": 4, "time": 3, "risk": 5, "performance": 4},
      "summary": "Best balance of low risk with good performance"
    }
  ]
}
```

### 4.6 Top-K Recommendations
- Display top 3-5 solutions
- Show: Rank, key characteristics, score, brief reasoning
- "Why this solution" expandable section

---

## Heatmap Page (Separate)

### 5.1 Route
`/matrix/heatmap` or `/workspace/heatmap`

### 5.2 Interactive Selection View
- 7 parameter cards (like Tab 3)
- Click to select one state per parameter
- Shows compatibility status for selection

### 5.3 Full Matrix Browse
- Large heatmap grid
- All pairwise parameter comparisons
- Zoom/pan controls
- Color legend

### 5.4 Toggle Between Views
- Tab/toggle: "Selection Mode" vs "Browse Mode"
- Selection: Interactive state picking
- Browse: Full scrollable matrix

---

## Data Model Changes

### Backend: New Fields

```python
# MatrixData enhanced
class MatrixCell:
    status: Literal['green', 'yellow', 'red']
    contradiction_type: Optional[Literal['L', 'E', 'N']]
    reason: Optional[str]  # Brief explanation

# Solution clustering
class SolutionCluster:
    id: str
    name: str
    description: str
    solution_indices: List[int]

# AHP weights
class AHPWeights:
    criteria: Dict[str, float]  # name -> weight
    pairwise_comparisons: List[Dict]  # Original pairwise data
```

### Frontend: New State

```typescript
interface EnhancedMatrixData {
  [pairId: string]: {
    [statePair: string]: {
      status: 'green' | 'yellow' | 'red';
      type?: 'L' | 'E' | 'N';
      reason?: string;
    }
  }
}

interface SolutionCluster {
  id: string;
  name: string;
  description: string;
  solutionIndices: number[];
}

interface AHPWeights {
  criteria: { name: string; weight: number }[];
}
```

---

## API Changes

### New Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/matrix/morphological/orthogonality-check` | Check param overlap |
| POST | `/matrix/morphological/cluster` | Auto-cluster solutions |
| POST | `/matrix/morphological/ahp-suggest` | Get initial weights |
| POST | `/matrix/morphological/score` | Score and rank solutions |
| GET | `/matrix/morphological/solutions` | Get enumerated solutions |

### Enhanced Existing

- `POST /matrix/morphological/generate` - Returns with orthogonality warnings
- `POST /matrix/morphological/evaluate` - Returns with contradiction types

---

## File Structure

```
feature-2/
├── backend/
│   └── app/matrix/
│       ├── models.py          # Enhanced models
│       ├── schemas.py         # Enhanced schemas
│       ├── service.py         # Enhanced + new functions
│       ├── router.py          # New endpoints
│       └── tasks.py           # New Celery tasks
│
├── frontend/
│   ├── app/(workspace)/matrix/
│   │   ├── page.tsx          # Existing
│   │   └── heatmap/
│   │       └── page.tsx      # NEW: Heatmap page
│   │
│   └── components/matrix/
│       ├── MorphologicalTab.tsx    # Enhanced tabs
│       ├── MatrixArea.tsx          # Add Tab 4 nav
│       ├── Tab4Convergence.tsx    # NEW: Tab 4 component
│       ├── SolutionClusters.tsx   # NEW: Cluster UI
│       ├── AHPWeights.tsx         # NEW: Weight setup
│       └── SolutionRanking.tsx    # NEW: Ranked list
```

---

## Implementation Priority

1. **Phase 1**: Tab 1 enhancements (inline editing, orthogonality)
2. **Phase 2**: Tab 2 enhancements (contradiction types, export)
3. **Phase 3**: Heatmap page
4. **Phase 4**: Tab 4 - Solution enumeration & clustering
5. **Phase 5**: Tab 4 - AHP weights & ranking

---

## Dependencies

- ECharts (already in use) for heatmap visualization
- Existing SSE infrastructure for async operations
- No new external libraries required
