---
sop_id: SOP-FOOD-007
title: Caloric Food Security and Emergency Ration Distribution Standard Operating Procedure
category: Food Distribution
hazard_type: ALL
source_agency: World Food Programme / Sphere Food Security Standard 1.1 Adapted
version: 3.1-SYNTHETIC
effective_date: 2026-01-01
status: ACTIVE
academic_disclaimer: "SYNTHETIC DEMONSTRATION DOCUMENT FOR ACADEMIC/COURSEWORK PURPOSES ONLY (CSE476). NOT OFFICIAL EMERGENCY GUIDANCE."
---

# SOP-FOOD-007: Caloric Food Security & Emergency Ration Protocol

> **ACADEMIC DISCLAIMER**: This is a synthetic operational document generated solely for academic evaluation in CSE476 (Agentic AI and Intelligent Automation). Do not use for actual civil defense or disaster deployment.

## 1. Purpose and Operational Scope
Governs the dispatch, nutritional auditing, and equity-constrained distribution of emergency food rations across disaster-affected zones to prevent acute malnutrition.

## 2. Quantitative Nutritional Standards
- **Baseline Nutritional Requirement:** Minimum **2,100 kcal per person per day** with standard macronutrient distribution:
  - 10%–12% of total energy from protein (minimum 52.5g protein/person-day).
  - Minimum 17% of total energy from fat.
- **Emergency Family Ration Pack (SKU: `FOOD_RATIONS`):**
  - Designed for a standard family of 5 persons for a duration of 3 days (15 person-days per pack).
  - Total pack energy: 31,500 kcal ($15 \times 2,100 \text{ kcal}$).
  - Gross pack weight: 12.5 kg containing fortified pre-cooked pulses, high-energy biscuits, iodized salt, and fortified edible oil.

## 3. Allocation Formula
The gross requirement of family food packs for zone $i$ over an operational 3-day planning window is computed as:
$$\text{Demand}_{i, \text{FOOD}} = \left\lceil \frac{\text{Population}_i \times \text{DisplacementFactor}_i}{5} \right\rceil$$
Where $\text{DisplacementFactor}_i = \min(1.0, 0.20 + 0.16 \cdot \text{DamageLevel}_i)$.

## 4. Equity and Fairness Rules in Food Allocation
- **Starvation Ban:** Food distribution must satisfy a Gini inequality coefficient $G \le 0.30$.
- In situations where regional warehouse stock is insufficient to provide 100% of demand, all affected zones must receive an equal baseline percentage of their need before residual stock is allocated based on priority scores.

