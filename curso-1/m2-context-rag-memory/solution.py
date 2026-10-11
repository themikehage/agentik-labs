from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any


class ContextBudgetGovernor:
    def __init__(self, max_node_tokens: int = 4000) -> None:
        self.max_node_tokens = max_node_tokens

    def allocate_node_budget(
        self,
        current_tokens: int,
        incoming_tokens: int,
        apply_tool_clearing: bool = False,
        cleared_tokens: int = 0,
    ) -> int:
        effective_current = (current_tokens - cleared_tokens) if apply_tool_clearing else current_tokens
        total = effective_current + incoming_tokens

        if total > self.max_node_tokens:
            raise ValueError(
                f"Context budget exceeded: total {total} tokens exceeds maximum node limit of {self.max_node_tokens} tokens. "
                "Apply JIT injection and tool result clearing."
            )

        return total


class DeterministicContextCompactor:
    @staticmethod
    def _compute_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def compact(
        self,
        system_directives: str,
        working_variables: dict[str, Any],
        dialogue_history: list[dict[str, str]],
        retain_recent_turns: int = 2,
    ) -> dict[str, Any]:
        initial_hash = self._compute_hash(system_directives)

        # Invariant 1: System directives are strictly immutable
        # Invariant 2: Working variables are preserved without loss
        preserved_vars = dict(working_variables)

        # Deterministic compaction of dialogue history:
        # Keep recent turns, compact older turns into structured summary lines
        if len(dialogue_history) <= retain_recent_turns:
            compacted_history = list(dialogue_history)
        else:
            older_turns = dialogue_history[:-retain_recent_turns]
            recent_turns = dialogue_history[-retain_recent_turns:]

            summary_points = [
                f"[Summary Turn {i+1}]: {turn.get('role', 'user')}: {turn.get('content', '')[:60]}..."
                for i, turn in enumerate(older_turns)
            ]
            summary_message = {
                "role": "system_summary",
                "content": "\n".join(summary_points),
            }
            compacted_history = [summary_message] + recent_turns

        final_hash = self._compute_hash(system_directives)
        assert initial_hash == final_hash, "Critical Invariant Violated: System directives hash mutated during compaction."

        return {
            "system_directives": system_directives,
            "system_hash": final_hash,
            "working_variables": preserved_vars,
            "compacted_history": compacted_history,
            "original_turn_count": len(dialogue_history),
            "compacted_turn_count": len(compacted_history),
        }


@dataclass(frozen=True)
class DocumentItem:
    doc_id: str
    tenant_id: str
    content: str
    dense_score: float
    bm25_score: float


class HybridRrfRetriever:
    def __init__(self, k_rrf: int = 60) -> None:
        self.k_rrf = k_rrf

    def retrieve(
        self,
        query: str,
        corpus: list[DocumentItem],
        tenant_id: str,
        enforce_pre_filter: bool = True,
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        if not enforce_pre_filter:
            raise ValueError(
                "Multi-tenant isolation breach: Tenant filtering MUST be enforced as an authoritative search pre-condition. "
                "Post-filtering leaks cross-tenant documents and wastes retrieval capacity."
            )

        # Pre-condition filter: only documents belonging to tenant
        filtered_corpus = [d for d in corpus if d.tenant_id == tenant_id]

        if not filtered_corpus:
            return []

        # Sort by Dense
        dense_ranked = sorted(filtered_corpus, key=lambda d: d.dense_score, reverse=True)
        dense_ranks = {doc.doc_id: rank + 1 for rank, doc in enumerate(dense_ranked)}

        # Sort by BM25
        bm25_ranked = sorted(filtered_corpus, key=lambda d: d.bm25_score, reverse=True)
        bm25_ranks = {doc.doc_id: rank + 1 for rank, doc in enumerate(bm25_ranked)}

        # Reciprocal Rank Fusion: 1 / (k + rank_dense) + 1 / (k + rank_bm25)
        fused_scores: list[dict[str, Any]] = []
        for doc in filtered_corpus:
            r_dense = dense_ranks[doc.doc_id]
            r_bm25 = bm25_ranks[doc.doc_id]
            rrf_score = (1.0 / (self.k_rrf + r_dense)) + (1.0 / (self.k_rrf + r_bm25))
            fused_scores.append({
                "doc_id": doc.doc_id,
                "tenant_id": doc.tenant_id,
                "content": doc.content,
                "rrf_score": round(rrf_score, 6),
            })

        fused_scores.sort(key=lambda x: x["rrf_score"], reverse=True)
        return fused_scores[:top_k]

    def evaluate_metrics(
        self,
        retrieved_ids: list[str],
        gold_relevant_ids: set[str],
        k: int = 3,
    ) -> dict[str, float]:
        top = retrieved_ids[:k]
        hits = [1 if did in gold_relevant_ids else 0 for did in top]

        # Recall@k
        recall_k = sum(hits) / float(len(gold_relevant_ids)) if gold_relevant_ids else 0.0

        # MRR (Mean Reciprocal Rank)
        mrr = 0.0
        for i, hit in enumerate(hits):
            if hit == 1:
                mrr = 1.0 / (i + 1)
                break

        # nDCG@k
        dcg = sum((hit / math.log2(i + 2)) for i, hit in enumerate(hits))
        ideal_hits = [1] * min(len(gold_relevant_ids), k)
        idcg = sum((1.0 / math.log2(i + 2)) for i in range(len(ideal_hits)))
        ndcg = (dcg / idcg) if idcg > 0 else 0.0

        return {
            "recall_at_k": round(recall_k, 4),
            "mrr": round(mrr, 4),
            "ndcg": round(ndcg, 4),
        }


@dataclass
class MemoryEntry:
    memory_id: str
    tenant_id: str
    user_id: str
    content: str
    timestamp: float
    ttl_seconds: float


class HierarchicalMemoryStore:
    POISONING_PATTERNS = (
        "ignore previous instructions",
        "system override",
        "new system directive",
        "act as admin",
        "cambia las instrucciones del sistema",
    )

    def __init__(self) -> None:
        self.working: dict[str, Any] = {}
        self.episodic: list[MemoryEntry] = []
        self.semantic: dict[str, list[str]] = {}

    def store_episodic(
        self,
        entry: MemoryEntry,
        current_timestamp: float,
    ) -> None:
        # Memory poisoning inspection
        content_lower = entry.content.lower()
        for pattern in self.POISONING_PATTERNS:
            if pattern in content_lower:
                raise ValueError(
                    f"Memory poisoning attempt rejected: Injected episodic fact contains adversarial command '{pattern}'."
                )

        self.episodic.append(entry)

    def retrieve_episodic(
        self,
        tenant_id: str,
        user_id: str,
        current_timestamp: float,
    ) -> list[MemoryEntry]:
        valid_entries: list[MemoryEntry] = []
        for e in self.episodic:
            # Strict multi-tenant isolation
            if e.tenant_id == tenant_id and e.user_id == user_id:
                # TTL Expiration check
                if (current_timestamp - e.timestamp) <= e.ttl_seconds:
                    valid_entries.append(e)

        return valid_entries


class ContextDegradationDiagnoser:
    def diagnose_failure(
        self,
        target_doc_retrieved: bool,
        target_doc_position_ratio: float,
        context_window_saturated: bool,
    ) -> str:
        if not target_doc_retrieved:
            return "retrieval_deficit"
        if context_window_saturated:
            return "budget_saturation"
        if 0.35 <= target_doc_position_ratio <= 0.70:
            return "lost_in_the_middle"
        return "model_reasoning_gap"

    def assert_valid_diagnosis(self, target_doc_retrieved: bool, claimed_diagnosis: str) -> None:
        if not target_doc_retrieved and claimed_diagnosis == "lost_in_the_middle":
            raise ValueError(
                "Diagnostic error: The document was never retrieved (retrieval_deficit); "
                "attributing the failure to attention degradation/lost-in-the-middle is factually false."
            )
