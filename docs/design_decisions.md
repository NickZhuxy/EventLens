# Design decisions

The user confirmed the macro-event direction and agent structure. The implementation choices below were selected with AI assistance and remain available for Nick to inspect and change.

| Decision | Reason | Tradeoff |
| --- | --- | --- |
| One explicit Python controller | Make actions, budgets, and failures easy to follow | We maintain the orchestration code ourselves |
| JSON actions through the existing model adapter | Reuse a small, inspectable interface | Providers must support the adapter's request fields |
| Saved corpus and read-only tools | Make runs reproducible and source boundaries enforceable | No live event monitoring or web discovery |
| FOMC first | Complete the full workflow with clear official sources | Limited event and market coverage |
| Extract dates from the next-meeting sentence | Keep each calendar date tied to explicit text | Other event families need separate adapters |
| Lexical paragraph retrieval | No runtime dependencies or opaque index | Synonyms and context can be missed |
| Return validation errors to the agent | Let the controller attempt evidence-based revision | Extra model calls; success remains unmeasured live |
| Keep semantic review human | Literal citations cannot establish interpretation quality | Review work remains necessary |
| Separate context, publication, and capture dates | Prevent minutes from appearing available on their meeting date | Historical snapshot availability is still not proven |
| Keep the earnings experiment | Preserve valid prior work and regression checks | Two documented workflows remain in the repository |

The stack may change if a measured failure justifies it. Adding an orchestration framework, vector store, multiple agents, or a UI is not itself a research result.
