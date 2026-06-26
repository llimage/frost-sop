# FROST-SOP V1.0

**FROST-SOP** (Family-based Recursive Orchestration System for Tasks - Standard Operating Procedure) is a framework for building hierarchical agent systems that execute tasks following defined SOPs (Standard Operating Procedures).

## 🎯 Key Concepts

### 1. Store & HierarchicalStore
- **Store**: Basic key-value storage
- **HierarchicalStore**: Inherits from parent stores, supports read-only keys and controlled inheritance

### 2. Skill
- Stateless callable unit that transforms context
- Pure functions with signature `func(context: dict) -> dict`
- Composable and testable

### 3. Agent
- Autonomous unit with memory (Store), capabilities (Skills), and procedures (SOP)
- **Generation model**: Enables hierarchical agent families (Ancestor → Parent → Child)
- Spawns child agents with controlled generation depth

### 4. SOP (Standard Operating Procedure)
- YAML-defined workflows that agents follow
- Staged execution with validation against constitution rules

### 5. Agent Families
- **Ancestor** (generation=0): Root agent, holds constitution, spawns parents
- **Parent** (generation=1): Coordinates task execution, searches SOPs/Skills
- **Child** (generation=2+): Executes specific tasks

## 📁 Project Structure

```
frost-sop/
├── core/               # Core framework classes
│   ├── store.py       # Store & HierarchicalStore
│   ├── skill.py       # Skill class
│   ├── agent.py       # Agent class (with generation model)
│   └── sop.py        # SOP engine (load, validate, execute)
├── agents/            # Agent factory functions
│   ├── ancestor.py    # Ancestor agent factory
│   └── parent.py      # Parent agent factory
├── stores/            # Store factory functions
│   ├── constitution.py # Constitution store (read-only rules)
│   └── asset.py       # Asset store (SOPs, Skills, records)
├── sops/              # SOP templates
│   └── templates/     # YAML SOP definitions
│       ├── DEV-001.yaml  # New feature development
│       └── STR-002.yaml  # Self-evolution validation
├── skills/            # Skill implementations
│   ├── orchestration.py # spawn, emit, validate_sop, merge_from
│   ├── search.py      # search_sop, search_skill
│   └── llm.py        # call_llm (placeholder)
├── tests/             # Unit and integration tests
│   ├── test_store.py
│   ├── test_agent.py
│   ├── test_sop.py
│   └── test_integration.py  # Smoke test
├── requirements.txt
└── README.md
```

## 🚀 Quick Start

### Installation

```bash
pip install -r requirements.txt
```

### Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python tests/test_store.py
python tests/test_agent.py
python tests/test_sop.py

# Run smoke test (integration test)
python tests/test_integration.py
```

### Basic Usage

```python
from core.store import HierarchicalStore
from core.skill import Skill
from core.agent import Agent
from stores.constitution import create_constitution_store
from stores.asset import create_asset_store
from agents.ancestor import create_ancestor

# 1. Create stores
constitution = create_constitution_store()
asset = create_asset_store(backend="memory")

# 2. Create ancestor agent
ancestor = create_ancestor(constitution, asset)

# 3. Spawn a parent agent
parent_store = HierarchicalStore(parent=asset)
parent = ancestor.spawn("Parent", parent_store, skills={}, sop_steps=[])

# 4. Execute tasks...
```

## 🧪 Testing

### Unit Tests
- `test_store.py`: Tests for Store and HierarchicalStore
- `test_agent.py`: Tests for Agent creation, execution, spawning
- `test_sop.py`: Tests for SOP loading, validation, execution

### Integration Test (Smoke Test)
`test_integration.py::test_smoke_ancestor_spawns_parent_and_parent_loads_sop`:
1. Creates constitution and asset stores
2. Creates ancestor agent
3. Simulates LLM task decomposition
4. Ancestor spawns parent with SOP type "DEV-001"
5. Parent loads DEV-001 SOP template
6. Ancestor validates SOP
7. Parent executes SOP stages
8. Parent emits results
9. Verifies asset store has task record

## 📝 Design Philosophy

### 1. Stateless Skills
Skills are pure functions that transform context. This makes them composable, testable, and easy to serialize.

### 2. Hierarchical Memory
HierarchicalStore enables controlled inheritance. Children inherit from parents, with read-only keys for governance.

### 3. Generation Model
Agents have a generation number. Ancestor (gen 0) spawns Parents (gen 1), who spawn Children (gen 2+). Max generation limits prevent unbounded spawning.

### 4. SOP-Driven Execution
Agents follow SOPs (YAML-defined workflows). SOPs are validated against constitution rules before execution.

### 5. Zero External Dependencies (Core)
The FROST kernel (core/) has zero external dependencies. External tools (LLM, search) are encapsulated in Skills.

## 🔧 Extending

### Adding a New Skill
```python
# skills/my_skill.py
def my_skill_func(context):
    # Do something
    context['result'] = "done"
    return context

# Register in agent
from core.skill import Skill
agent.skills['my_skill'] = Skill('my_skill', my_skill_func)
```

### Adding a New SOP Template
```yaml
# sops/templates/MY-001.yaml
sop_id: "MY-001"
name: "My SOP"
version: "1.0"
stages:
  - name: "Stage 1"
    agent: "my_agent"
    skills: ["skill1"]
required_stages: ["Stage 1"]
forbidden_skills: ["bad_skill"]
```

### Adding a New Agent Type
```python
# agents/my_agent.py
from ..core.agent import Agent

def create_my_agent(name, store):
    skills = {
        "skill1": Skill("skill1", func1),
        "skill2": Skill("skill2", func2)
    }
    return Agent(name=name, store=store, skills=skills, generation=1)
```

## 📄 License

[Add your license here]

## 🤝 Contributing

[Add contributing guidelines here]

---

**Built with ❤️ by WorkBuddy**
