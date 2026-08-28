# Stage 6 — Evidence Retrieval & Linking

**Job:** pull unstructured evidence (CRM, tickets, reviews), tag it before/during/after the changepoint, and attach lineage + freshness metadata to every snippet.

**Status:** Not yet designed. No stage design report exists yet.

**Related prior art:** the original Round 1 architecture's Component E (Unstructured Evidence Pipeline — see [`docs/01-architecture/architecture-report.md`](../../docs/01-architecture/architecture-report.md) §7) sketches the tool chain: `sentence-transformers` (MiniLM) for chunking/embedding, `sqlite-vec`/FAISS for the vector store, spaCy for entity extraction, VADER/DistilBERT for sentiment. The before/during/after temporal tagging relative to the changepoint is called out as a cheap rule most teams skip, and as what stops the system from mistaking a consequence for a cause.

**Consumes:** the Identity Resolution Graph (Stage 1's cross-cutting service) to link evidence to the correct account/entity.

**Feeds:** Stage 7's hypothesis debate — each debate agent retrieves only evidence filtered to its entity scope and relevant time window, not a generic RAG dump.

No code yet, no design report yet.
