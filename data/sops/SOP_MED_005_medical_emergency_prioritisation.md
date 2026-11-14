---
sop_id: SOP-MED-005
title: Medical Emergency Prioritisation and Mass Casualty Triage Standard Operating Procedure
category: Medical Emergency
hazard_type: ALL
source_agency: World Health Organization / Emergency Medical Services Directorate Adapted
version: 3.0-SYNTHETIC
effective_date: 2026-01-01
status: ACTIVE
academic_disclaimer: "SYNTHETIC DEMONSTRATION DOCUMENT FOR ACADEMIC/COURSEWORK PURPOSES ONLY (CSE476). NOT OFFICIAL EMERGENCY GUIDANCE."
---

# SOP-MED-005: Medical Emergency Prioritisation & Trauma Care Protocol

> **ACADEMIC DISCLAIMER**: This is a synthetic operational document generated solely for academic evaluation in CSE476 (Agentic AI and Intelligent Automation). Do not use for actual civil defense or disaster deployment.

## 1. Purpose and Operational Scope
Establishes standardized criteria for evaluating medical criticality, distributing trauma kits, and dispatching medical countermeasures to mass-casualty disaster zones under severe supply scarcity.

## 2. Medical Urgency Index ($M_i$) Formulation
Medical urgency is a normalized scalar index $M_i \in [0.0, 1.0]$ computed from three clinical indicators:
$$M_i = 0.50 \cdot \text{TraumaRatio} + 0.30 \cdot \text{DiseaseOutbreakRisk} + 0.20 \cdot (1.0 - \text{HospitalFunctionality})$$
- **High Criticality ($M_i \ge 0.75$):** Severe trauma incidents, compound fractures, crushing injuries, collapsed local hospitals.
- **Moderate Criticality ($0.40 \le M_i < 0.75$):** Non-life-threatening lacerations, treatable dehydration, minor fractures.
- **Low Criticality ($M_i < 0.40$):** Mild superficial injuries, outpatient care sufficient.

## 3. Standard Medical Kit Allocation Norms
- **Tier 1 (Advanced Trauma & Surgical Kit):**
  - Standard: 1 kit per 100 affected persons when $M_i \ge 0.75$.
  - Contents: Tourniquets, IV crystalloid bags, airway tubes, chest seals, systemic antibiotics, sterile field drapes.
- **Tier 2 (General Emergency Health Kit):**
  - Standard: 1 kit per 250 affected persons when $0.40 \le M_i < 0.75$.
  - Contents: ORS rehydration sachets, antipyretics, water-purification tablets, topical antiseptics, bandages.

## 4. Triage and Anti-Starvation Rules
- **Rule of Non-Zero Medical Allocation:** Any zone with an active medical urgency index $M_i \ge 0.70$ must NEVER receive zero medical kits if warehouse inventory has any unallocated kits remaining.
- In extreme scarcity, medical kits must be allocated strictly proportional to $M_i \times \text{Pop}_i$.

