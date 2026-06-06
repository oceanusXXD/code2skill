# Algorithm Notes

`code2skill` does not try to train a model over the repository. It builds a
small structural graph and a compact AST skeleton, then gives the LLM grounded
evidence for planning and Skill generation.

## What Was Borrowed

- AST path evidence: inspired by code2vec, which showed that paths through code
  structure are stronger signals than plain token lists.
- Program graph evidence: inspired by graph-based program representation work
  and Code Property Graphs, which combine syntax and semantic edges instead of
  treating code as isolated files.
- Data-flow evidence: inspired by GraphCodeBERT, which uses data-flow structure
  to connect variables and operations beyond lexical proximity.

## Current Implementation

- Python AST extraction records imports, exports, functions, classes, methods,
  route decorators, model/schema signals, call targets, type references,
  raised exceptions, dynamic imports, class attributes, and simple data-flow
  edges such as `scope:target<-source`.
- Import graph construction uses detailed `ImportInfo`, including `from ...
  import ...` names and dynamic imports, so package-level imports resolve to
  concrete internal files when possible.
- File priority combines path heuristics with content evidence. Route, service,
  model, main-guard, call-target, type-reference, and data-flow signals can
  raise selection priority.
- Planner prompts receive dependency, call, type, and flow evidence for core
  modules. Generation prompts use the same skeleton lines when large files are
  summarized instead of inlined.

## Boundaries

The extractor is deliberately conservative. It records shallow data-flow edges
from assignments, loops, and context managers, but it does not attempt full
interprocedural static analysis, control-flow reconstruction, type inference, or
runtime import evaluation. Missing or ambiguous evidence should still be marked
as uncertain by generated Skills.

## References

- Alon et al., code2vec: Learning Distributed Representations of Code:
  https://arxiv.org/abs/1803.09473
- Allamanis et al., Learning to Represent Programs with Graphs:
  https://arxiv.org/abs/1711.00740
- Yamaguchi et al., Modeling and Discovering Vulnerabilities with Code Property
  Graphs: https://ieeexplore.ieee.org/document/6956581
- Guo et al., GraphCodeBERT: Pre-training Code Representations with Data Flow:
  https://arxiv.org/abs/2009.08366
