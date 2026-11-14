---
sop_id: SOP-VULN-008
title: Vulnerable Population Prioritisation and Equity Weighting Standard Operating Procedure
category: Vulnerable Population
hazard_type: ALL
source_agency: Humanitarian Protection Directorate / UNICEF Adapted
version: 2.5-SYNTHETIC
effective_date: 2026-01-01
status: ACTIVE
academic_disclaimer: "SYNTHETIC DEMONSTRATION DOCUMENT FOR ACADEMIC/COURSEWORK PURPOSES ONLY (CSE476). NOT OFFICIAL EMERGENCY GUIDANCE."
---

# SOP-VULN-008: Vulnerable Population Prioritisation & Equity Protocol

> **ACADEMIC DISCLAIMER**: This is a synthetic operational document generated solely for academic evaluation in CSE476 (Agentic AI and Intelligent Automation). Do not use for actual civil defense or disaster deployment.

## 1. Purpose and Operational Scope
Establishes standardized criteria to identify, quantify, and protect high-vulnerability demographic groups (infants, young children under 5, pregnant and lactating mothers, elderly persons aged 65+, and persons with mobility disabilities) during emergency resource allocation.

## 2. Demographic Vulnerability Index ($V_i$) Formulation
The Vulnerability Index $V_i \in [0.0, 1.0]$ is calculated as:
$$V_i = 0.35 \cdot f_{\text{infants}} + 0.30 \cdot f_{\text{elderly}} + 0.20 \cdot f_{\text{disability}} + 0.15 \cdot \text{PovertyRatio}$$
Where $f_k$ is the fraction of group $k$ within the total residing zone population.
- **Critical Vulnerability ($V_i \ge 0.80$):** High concentration of dependent infants, nursing mothers, or immobile elders.
- **High Vulnerability ($0.60 \le V_i < 0.80$):** Substantial vulnerable demographic concentration requiring targeted logistics.
- **Moderate Vulnerability ($V_i < 0.60$):** Standard demographic cross-section.

## 3. Vulnerability Resource Multipliers
- **Infant Nutrition and Hygiene Supplements:** When $V_i \ge 0.75$, the calculated demand for clean water increases by **+20%** to facilitate formula reconstitution and hygiene sanitation.
- **Priority Surge:** High vulnerability directly elevates the Zone Priority Score ($ZPS$), acting as a multiplicative weight in the Coordinator's optimization objective.

## 4. Protection and Non-Discrimination Guardrails
- Under no circumstance may resources be withheld from high-vulnerability peripheral zones in order to achieve faster turnaround or fuel savings for closer urban hubs.
- The Fairness Auditor Agent must flag an automatic audit violation if a zone with $V_i \ge 0.80$ receives a lower satisfaction ratio than an adjacent low-vulnerability zone.

