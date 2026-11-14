---
sop_id: SOP-LOG-009
title: Emergency Logistics Fleet Dispatch, Road Impedance and Routing Standard Operating Procedure
category: Emergency Logistics
hazard_type: ALL
source_agency: Logistics Cluster / National Highway Disaster Directorate Adapted
version: 2.2-SYNTHETIC
effective_date: 2026-01-01
status: ACTIVE
academic_disclaimer: "SYNTHETIC DEMONSTRATION DOCUMENT FOR ACADEMIC/COURSEWORK PURPOSES ONLY (CSE476). NOT OFFICIAL EMERGENCY GUIDANCE."
---

# SOP-LOG-009: Emergency Logistics Fleet Dispatch & Routing Protocol

> **ACADEMIC DISCLAIMER**: This is a synthetic operational document generated solely for academic evaluation in CSE476 (Agentic AI and Intelligent Automation). Do not use for actual civil defense or disaster deployment.

## 1. Purpose and Operational Scope
Provides mathematical and operational rules for calculating terrestrial delivery distances, selecting supply depots, estimating transit hours, and incorporating road network degradation.

## 2. Distance Computation and Winding Model
1. **Haversine Great-Circle Distance ($d_{\text{harv}}$):**
   Calculated using standard spherical trigonometry with Earth radius $R = 6,371.0 \text{ km}$.
2. **Effective Road Transit Distance ($D_{\text{eff}}$):**
   Because road corridors wind through natural terrain, true driving distance is modeled via:
   $$D_{\text{eff}} = d_{\text{harv}} \times W_t$$
   Where $W_t = 1.35$ for plain/delta riverine terrain and $W_t = 1.85$ for hilly/mountain terrain.

## 3. Road Network Status and Transit Speed Multipliers
Transit hours ($T_{\text{hours}}$) are computed based on corridor status:
$$T_{\text{hours}} = \frac{D_{\text{eff}}}{V_{\text{base}} \times \eta_{\text{road}}}$$
Where baseline truck cruise speed $V_{\text{base}} = 45.0 \text{ km/h}$, and the impedance coefficient $\eta_{\text{road}}$ is:
- **`OPEN` Corridor ($\eta_{\text{road}} = 1.0$):** Full speed ($45.0 \text{ km/h}$). Pavement dry and unobstructed.
- **`DEGRADED` Corridor ($\eta_{\text{road}} = 0.50$):** Reduced speed ($22.5 \text{ km/h}$). Waterlogging $< 0.5m$ or partial shoulder debris.
- **`BLOCKED` Corridor ($\eta_{\text{road}} = 0.15$):** Impassable to standard commercial cargo trucks ($6.75 \text{ km/h}$). Requires heavy earthmovers, military 6x6 amphibious carriers, or aerial dispatch.
- **`AIR_ONLY` Corridor:** Reserved for aerial helicopter/fixed-wing relief ($90.0 \text{ km/h}$ air transit).

## 4. Multi-Depot Sourcing Rules
- Primary dispatch must originate from the nearest operational warehouse having adequate unreserved stock.
- If the nearest warehouse lacks sufficient inventory, the Logistics Agent must evaluate secondary transshipment depots within a 300 km radius, penalizing the candidate plan by transit duration.

