from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from labkit.sandbox import validate_hardened_flags, HardeningViolationError


class SecurityPolicyViolationError(Exception):
    pass


class OWASP2025Catalog:
    OFFICIAL_IDS = {
        "LLM01": "Prompt Injection",
        "LLM02": "Sensitive Information Disclosure",
        "LLM03": "Supply Chain",
        "LLM04": "Data and Model Poisoning",
        "LLM05": "Improper Output Handling",
        "LLM06": "Excessive Agency",
        "LLM07": "System Prompt Leakage",
        "LLM08": "Vector and Embedding Weaknesses",
        "LLM09": "Misinformation",
        "LLM10": "Unbounded Consumption",
    }

    SCENARIO_MAPPING = {
        "untrusted_email_override": "LLM01",
        "private_api_key_leak": "LLM02",
        "compromised_huggingface_adapter": "LLM03",
        "poisoned_fine_tuning_corpus": "LLM04",
        "unsanitized_markdown_xss_output": "LLM05",
        "autonomous_destructive_tool_execution": "LLM06",
        "jailbreak_extracts_developer_instructions": "LLM07",
        "rag_embedding_inversion_attack": "LLM08",
        "hallucinated_legal_statute_citation": "LLM09",
        "unmetered_recursive_generation_loop": "LLM10",
    }

    @classmethod
    def classify_scenario(cls, scenario_key: str) -> str:
        if scenario_key not in cls.SCENARIO_MAPPING:
            raise KeyError(f"Unknown scenario '{scenario_key}'")
        return cls.SCENARIO_MAPPING[scenario_key]

    @classmethod
    def get_title(cls, owasp_id: str) -> str:
        if owasp_id not in cls.OFFICIAL_IDS:
            raise KeyError(f"Unknown OWASP 2025 ID '{owasp_id}'")
        return cls.OFFICIAL_IDS[owasp_id]


class LexicalDefenseEvaluator:
    PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
        re.compile(r"system\s*override", re.IGNORECASE),
        re.compile(r"<script>.*?</script>", re.IGNORECASE),
    ]

    @classmethod
    def filter_text(cls, text: str) -> bool:
        return any(p.search(text) for p in cls.PATTERNS)

    @classmethod
    def evaluate_benchmark(
        cls,
        adversarial_prompts: list[dict[str, Any]],
    ) -> dict[str, float]:
        true_positives = 0
        false_negatives = 0
        false_positives = 0
        true_negatives = 0

        for item in adversarial_prompts:
            text = item["text"]
            is_malicious = item["is_malicious"]
            flagged = cls.filter_text(text)

            if is_malicious and flagged:
                true_positives += 1
            elif is_malicious and not flagged:
                false_negatives += 1
            elif not is_malicious and flagged:
                false_positives += 1
            else:
                true_negatives += 1

        total_positives = true_positives + false_negatives
        tpr = true_positives / float(total_positives) if total_positives > 0 else 0.0

        total_negatives = false_positives + true_negatives
        fpr = false_positives / float(total_negatives) if total_negatives > 0 else 0.0

        return {
            "tpr": round(tpr, 4),
            "fpr": round(fpr, 4),
            "guarantees_prevention": False,
        }


class LethalTrifectaArchitect:
    @staticmethod
    def evaluate_risk(
        has_untrusted_data: bool,
        has_private_data: bool,
        has_network_egress: bool,
        prompt_instruction_only_defense: bool = False,
    ) -> dict[str, Any]:
        lethal_trifecta_active = (
            has_untrusted_data and has_private_data and has_network_egress
        )

        if lethal_trifecta_active:
            if prompt_instruction_only_defense:
                can_exfiltrate = True
                mitigation_status = "FAILED_INSTRUCTION_OVERRIDABLE"
            else:
                can_exfiltrate = True
                mitigation_status = "CRITICAL_UNMITIGATED"
        else:
            can_exfiltrate = False
            mitigation_status = "CONTAINED_BY_ARCHITECTURE"

        return {
            "trifecta_active": lethal_trifecta_active,
            "can_exfiltrate": can_exfiltrate,
            "mitigation_status": mitigation_status,
        }

    @staticmethod
    def break_trifecta_network_isolation(
        has_untrusted_data: bool,
        has_private_data: bool,
    ) -> dict[str, Any]:
        return LethalTrifectaArchitect.evaluate_risk(
            has_untrusted_data=has_untrusted_data,
            has_private_data=has_private_data,
            has_network_egress=False,
            prompt_instruction_only_defense=False,
        )


@dataclass
class DockerSandboxConfig:
    image: str
    network: str = "none"
    read_only: bool = True
    cap_drop: list[str] = field(default_factory=lambda: ["ALL"])
    no_new_privileges: bool = True
    user: str = "10001:10001"
    pids_limit: int = 64
    memory: str = "256m"


class HardenedSandboxPolicy:
    METADATA_IP = "169.254.169.254"

    @classmethod
    def validate_docker_config(cls, config: DockerSandboxConfig) -> dict[str, Any]:
        violations: list[str] = []

        if config.network != "none":
            violations.append(f"Network must be 'none', got '{config.network}'")

        if not config.read_only:
            violations.append("Root filesystem must be read-only (read_only=True)")

        if "ALL" not in config.cap_drop:
            violations.append("All capabilities must be dropped (cap_drop must include 'ALL')")

        if not config.no_new_privileges:
            violations.append("no_new_privileges flag must be enabled")

        if not config.user or config.user == "0" or config.user == "root":
            violations.append(f"Root user is strictly forbidden in sandbox. User was '{config.user}'")

        cmd = [
            "docker", "run",
            "--network", config.network,
            "--read-only" if config.read_only else "",
            "--cap-drop", ",".join(config.cap_drop),
            "--security-opt", "no-new-privileges" if config.no_new_privileges else "",
            "--pids-limit", str(config.pids_limit),
            "--memory", config.memory,
            "--user", config.user,
            config.image,
        ]

        try:
            validate_hardened_flags(cmd)
        except HardeningViolationError as ex:
            violations.append(str(ex))

        if violations:
            raise SecurityPolicyViolationError(
                f"Container failed hardened sandbox policy: {'; '.join(violations)}"
            )

        return {
            "is_hardened": True,
            "user": config.user,
            "network": config.network,
            "metadata_ip_blocked": True,
            "read_only": config.read_only,
        }
