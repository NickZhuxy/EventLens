# Contribution and provenance record

Owner and maintainer: **Xiangyi (Nick) Zhu**.

## Nick's confirmed contribution

Nick supplied the internship context, directed the project toward macro-event risk briefing, confirmed that his basic information-organizing agent supported that workflow, and approved retaining an agent structure. He requested a README that makes the tech stack and agent logic clear to a new reader.

These statements do not imply that Nick manually authored generated code, reviewed draft labels, selected every implementation detail, or measured model performance.

## AI-assisted work in this repository

The coding assistant inspected the original workflow locally, proposed the architecture, implemented the Python controller and tools, collected public source captures, prepared draft calendar labels, wrote tests and documentation, and ran the reproducibility checks. The user is reviewing and taking ownership of that work. No AI co-author trailer is added to Git commits.

## Internship boundary

The original internship agent's framework and model are unconfirmed. The new implementation is inspired by the problem and workflow. It is not a recovered employer system, an assertion of fund deployment, or evidence of trading impact. No internship source documents, proprietary strategy data, or employer code are included in the new corpus.

## Third-party material

The Federal Reserve Board authored the macro source documents. Issuers authored the disclosures in the supporting earnings experiment. Python and setuptools supply the runtime and build tools. The optional provider supplies live model inference when configured. See [third-party notices](../THIRD_PARTY_NOTICES.md).

## Evidence status

Offline rule outputs and scripted controller traces are reproducible. Scripted actions are not LLM results. Calendar labels and semantic review queues are pending Nick's review. No current evidence establishes that the agent outperforms the single-pass method.

The v0.3 service adds authenticated HTTP requests, a durable SQLite queue, a separate worker, Federal Reserve RSS collection, source imports, provider retries, and Docker deployment. Acceptance checks run against native processes and real containers. They verify live public-source ingestion and deterministic briefing, including persistence after restart. Model-driven acceptance remains a separate check that requires a configured provider; infrastructure tests do not establish model quality.
