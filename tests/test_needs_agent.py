"""
ReliefOps AI — Phase 2 Unit Tests: BaseAgent & NeedsAssessmentAgent
Validates BaseAgent lifecycle, Blackboard interaction, NeedsAssessmentAgent multi-zone
execution, Semantic Kernel plugin registration, RAG integration, and error handling.
"""

import json
import os
import sys
import unittest
from semantic_kernel import Kernel

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.agents import BaseAgent, NeedsAssessmentAgent
from backend.plugins.needs_plugin import NeedsAssessmentPlugin


class MockBlackboard:
    """Mock blackboard with read and update methods imitating BlackboardManager."""

    def __init__(self):
        self.state = {}
        self.events = []

    def read(self, section: str):
        return self.state.get(section)

    def update(self, section: str, data, agent_name: str = "Anonymous"):
        self.state[section] = data
        self.events.append({"section": section, "agent": agent_name})


class ConcreteTestAgent(BaseAgent):
    """Concrete implementation of BaseAgent for testing abstract base methods."""

    def execute(self, context=None):
        ctx = context or self.read_section("test_input") or {}
        val = ctx.get("value", 0) * 2
        self.write_section("test_output", {"result": val})
        return {"status": "SUCCESS", "result": val}


class TestBaseAgentAndNeedsAgent(unittest.TestCase):
    """Comprehensive test suite for BaseAgent and NeedsAssessmentAgent."""

    def test_base_agent_initialization_and_kernel_injection(self):
        """Test BaseAgent initialization with default and custom Kernel injection."""
        # Default kernel instantiation
        agent_default = ConcreteTestAgent(name="DefaultAgent")
        self.assertEqual(agent_default.name, "DefaultAgent")
        self.assertIsInstance(agent_default.kernel, Kernel)
        self.assertIsNone(agent_default.blackboard)

        # Injected custom kernel
        custom_kernel = Kernel()
        mock_bb = MockBlackboard()
        agent_custom = ConcreteTestAgent(name="CustomAgent", kernel=custom_kernel, blackboard=mock_bb)
        self.assertIs(agent_custom.kernel, custom_kernel)
        self.assertIs(agent_custom.blackboard, mock_bb)

    def test_blackboard_read_write_functionality(self):
        """Test BaseAgent read_section and write_section across dict and object blackboards."""
        # 1. With MockBlackboard object (with .read() and .update())
        mock_bb = MockBlackboard()
        agent = ConcreteTestAgent(name="Tester", blackboard=mock_bb)

        agent.write_section("disaster_data", {"alert": "RED"})
        self.assertEqual(agent.read_section("disaster_data"), {"alert": "RED"})
        self.assertEqual(mock_bb.state["disaster_data"], {"alert": "RED"})
        self.assertEqual(mock_bb.events[0]["agent"], "Tester")

        # 2. With plain dict blackboard
        dict_bb = {}
        agent_dict = ConcreteTestAgent(name="DictTester", blackboard=dict_bb)
        agent_dict.write_section("status", "ACTIVE")
        self.assertEqual(agent_dict.read_section("status"), "ACTIVE")
        self.assertEqual(dict_bb["status"], "ACTIVE")

        # 3. With unattached blackboard (None)
        agent_none = ConcreteTestAgent(name="NoneTester", blackboard=None)
        self.assertIsNone(agent_none.read_section("anything"))
        agent_none.write_section("key", "val")  # Should log warning and not crash
        self.assertTrue(any("Blackboard not attached" in m for m in agent_none.log_history))

    def test_needs_assessment_agent_initialization_and_sk_registration(self):
        """Test NeedsAssessmentAgent initialization and automatic plugin registration on SK."""
        kernel = Kernel()
        agent = NeedsAssessmentAgent(kernel=kernel)
        self.assertIsInstance(agent.plugin, NeedsAssessmentPlugin)

        # Verify NeedsAssessment plugin is registered on the Semantic Kernel
        plugin = agent.kernel.get_plugin("NeedsAssessment")
        function_names = [f.name for f in plugin]
        self.assertIn("retrieve_sop_guidelines", function_names)
        self.assertIn("calculate_zone_demands", function_names)
        self.assertIn("compute_zone_priority", function_names)

    def test_needs_agent_sop_retrieval_and_citations(self):
        """Test that executing NeedsAssessmentAgent retrieves SOP guidelines and records sop_context."""
        bb = MockBlackboard()
        agent = NeedsAssessmentAgent(blackboard=bb)

        context = {
            "event_id": "EVT-TEST-01",
            "disaster_type": "FLOOD",
            "severity": "Level 4",
            "planning_days": 1,
            "zones": [
                {
                    "zone_id": "ZONE-A",
                    "zone_name": "Riverside Alpha",
                    "affected_population": 5000,
                    "damage_level": 4.0,
                    "vulnerability_index": 0.8,
                    "medical_urgency": 0.7,
                    "road_status": "DEGRADED",
                }
            ],
        }

        res = agent.execute(context)
        self.assertEqual(res["status"], "SUCCESS")

        # Verify sop_context was written to Blackboard
        sop_ctx = bb.read("sop_context")
        self.assertIsNotNone(sop_ctx)
        self.assertEqual(sop_ctx["status"], "SUCCESS")
        self.assertIn("SOP-FL-001", sop_ctx["sop_ids"])
        self.assertGreater(len(sop_ctx["chunks"]), 0)

        # Verify citations include authentic SOP IDs and non-empty content excerpts
        for chunk in sop_ctx["chunks"]:
            self.assertTrue(chunk["sop_id"].startswith("SOP-"))
            self.assertTrue(len(chunk["content_excerpt"]) > 20)

    def test_multi_zone_flood_assessment_and_ranking(self):
        """Test multi-zone evaluation, independent demand calculations, and ZPS ranking."""
        bb = MockBlackboard()
        agent = NeedsAssessmentAgent(blackboard=bb)

        # Three distinct zones with varying severity, vulnerability, and medical urgency
        context = {
            "event_id": "EVT-2026-FL01",
            "disaster_type": "FLOOD",
            "severity": "Level 3",
            "planning_days": 3,
            "zones": [
                {
                    "zone_id": "ZONE-LOW",
                    "zone_name": "Low Risk Periphery",
                    "affected_population": 2000,
                    "damage_level": 1.0,
                    "vulnerability_index": 0.2,
                    "medical_urgency": 0.3,
                    "road_status": "OPEN",
                },
                {
                    "zone_id": "ZONE-HIGH",
                    "zone_name": "Critical Inundated Settlement",
                    "affected_population": 10000,
                    "damage_level": 5.0,
                    "vulnerability_index": 0.9,
                    "medical_urgency": 0.85,
                    "road_status": "BLOCKED",
                },
                {
                    "zone_id": "ZONE-MED",
                    "zone_name": "Moderate Town Center",
                    "affected_population": 6000,
                    "damage_level": 3.0,
                    "vulnerability_index": 0.5,
                    "medical_urgency": 0.62,
                    "road_status": "DEGRADED",
                },
            ],
        }

        result = agent.execute(context)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["zones_assessed"], 3)

        # Verify Blackboard state updated
        zone_needs = bb.read("zone_needs")
        self.assertIsNotNone(zone_needs)
        self.assertEqual(len(zone_needs), 3)

        # Verify correct priority ranking: ZONE-HIGH must be Rank 1, ZONE-LOW must be Rank 3
        self.assertEqual(zone_needs[0]["zone_id"], "ZONE-HIGH")
        self.assertEqual(zone_needs[0]["priority_rank"], 1)
        self.assertEqual(zone_needs[1]["zone_id"], "ZONE-MED")
        self.assertEqual(zone_needs[1]["priority_rank"], 2)
        self.assertEqual(zone_needs[2]["zone_id"], "ZONE-LOW")
        self.assertEqual(zone_needs[2]["priority_rank"], 3)

        # Verify ZPS ordering: ZPS_1 > ZPS_2 > ZPS_3
        self.assertGreater(zone_needs[0]["zps"], zone_needs[1]["zps"])
        self.assertGreater(zone_needs[1]["zps"], zone_needs[2]["zps"])

    def test_correct_resource_calculations_in_multi_zone(self):
        """Test exact mathematical demands across zones with multi-cycle planning horizon."""
        agent = NeedsAssessmentAgent()
        context = {
            "disaster_type": "FLOOD",
            "planning_days": 4,  # ceil(4 / 3) = 2 replenishment cycles
            "zones": [
                {
                    "zone_id": "Z1",
                    "zone_name": "Zone One",
                    "affected_population": 1000,
                    "damage_level": 3.0,  # Disp = min(1.0, 3*0.2) = 0.60 -> 600 people displaced
                    "vulnerability_index": 0.5,
                    "medical_urgency": 0.65,  # >= 0.60 -> medical kits active
                },
                {
                    "zone_id": "Z2",
                    "zone_name": "Zone Two",
                    "affected_population": 2000,
                    "damage_level": 1.0,  # Disp = min(1.0, 1*0.2) = 0.20 -> 400 people displaced
                    "vulnerability_index": 0.4,
                    "medical_urgency": 0.45,  # < 0.60 -> 0 medical kits
                },
            ],
        }

        res = agent.execute(context)
        self.assertEqual(res["status"], "SUCCESS")

        profiles = {z["zone_id"]: z for z in res["zone_needs"]}

        # Zone 1 Checks:
        # Tents: ceil(600 / 5) = 120
        self.assertEqual(profiles["Z1"]["demands"]["tents"], 120)
        # Water: 1000 * 15 * 4 = 60,000 L -> 6,000 jerrycans
        self.assertEqual(profiles["Z1"]["demands"]["water_liters"], 60000.0)
        self.assertEqual(profiles["Z1"]["demands"]["jerrycans_10l"], 6000)
        # Food: ceil(600 / 5) * ceil(4 / 3) = 120 * 2 = 240 packs
        self.assertEqual(profiles["Z1"]["demands"]["food_packs"], 240)
        # Medical: ceil(1000 / 250) = 4 kits
        self.assertEqual(profiles["Z1"]["demands"]["medical_kits"], 4)

        # Zone 2 Checks:
        # Tents: ceil(400 / 5) = 80
        self.assertEqual(profiles["Z2"]["demands"]["tents"], 80)
        # Water: 2000 * 15 * 4 = 120,000 L -> 12,000 jerrycans
        self.assertEqual(profiles["Z2"]["demands"]["water_liters"], 120000.0)
        # Food: ceil(400 / 5) * ceil(4 / 3) = 80 * 2 = 160 packs
        self.assertEqual(profiles["Z2"]["demands"]["food_packs"], 160)
        # Medical: M_i < 0.60 -> 0 kits
        self.assertEqual(profiles["Z2"]["demands"]["medical_kits"], 0)

        # Total Aggregates Checks:
        totals = res["total_demands"]
        self.assertEqual(totals["total_affected_population"], 3000)
        self.assertEqual(totals["total_displaced_population"], 1000.0)
        self.assertEqual(totals["total_water_liters"], 180000.0)
        self.assertEqual(totals["total_jerrycans_10l"], 18000)
        self.assertEqual(totals["total_food_packs"], 400)
        self.assertEqual(totals["total_medical_kits"], 4)
        self.assertEqual(totals["total_tents"], 200)

    def test_empty_and_invalid_disaster_context_handling(self):
        """Test graceful handling of empty, None, and invalid disaster contexts."""
        bb = MockBlackboard()
        agent = NeedsAssessmentAgent(blackboard=bb)

        # Case 1: None context and empty blackboard
        res_none = agent.execute(None)
        self.assertEqual(res_none["status"], "EMPTY_CONTEXT")
        self.assertEqual(res_none["zones_assessed"], 0)

        # Case 2: Empty dict context
        res_empty = agent.execute({})
        self.assertEqual(res_empty["status"], "EMPTY_CONTEXT")

        # Case 3: Context with empty zones list
        res_no_zones = agent.execute({"event_id": "EVT-00", "disaster_type": "FLOOD", "zones": []})
        self.assertEqual(res_no_zones["status"], "NO_ZONES")
        self.assertEqual(res_no_zones["zones_assessed"], 0)

        # Case 4: Reading from populated Blackboard when context argument is None
        bb.update(
            "disaster_context",
            {
                "event_id": "EVT-BB",
                "disaster_type": "FLOOD",
                "zones": [
                    {
                        "zone_id": "Z-BB",
                        "affected_population": 100,
                        "damage_level": 2.0,
                    }
                ],
            },
        )
        res_from_bb = agent.execute(None)
        self.assertEqual(res_from_bb["status"], "SUCCESS")
        self.assertEqual(res_from_bb["zones_assessed"], 1)
        self.assertEqual(res_from_bb["event_id"], "EVT-BB")

    def test_malformed_zone_records_and_invalid_planning_days(self):
        """Test resilience against missing/corrupt values and bad planning_days."""
        agent = NeedsAssessmentAgent()

        # 1. Test invalid planning_days values (negative, zero, string, None)
        for bad_days in [-5, 0, "corrupt", None]:
            res = agent.execute({
                "disaster_type": "FLOOD",
                "planning_days": bad_days,
                "zones": [{"zone_id": "Z1", "affected_population": 500, "damage_level": 2.0}]
            })
            self.assertEqual(res["status"], "SUCCESS")
            self.assertGreaterEqual(res["planning_days"], 1)

        # 2. Test malformed zone records
        malformed_zones = [
            {"zone_id": "Z_NO_POP"},                                           # Missing population, damage
            {"zone_id": "Z_NEG_POP", "affected_population": -1000},            # Negative population
            {"zone_id": "Z_STR_VALS", "affected_population": "2000", "damage_level": "3.5"},  # String numbers
            {"zone_id": "Z_EXTREME_DMG", "affected_population": 500, "damage_level": 99.0},   # Damage > 5.0
            {"zone_id": "Z_EXTREME_VULN", "affected_population": 500, "vulnerability_index": 5.0}, # Vuln > 1.0
            "not_a_dict_entry"                                                 # Invalid entry type
        ]

        res_malformed = agent.execute({
            "disaster_type": "FLOOD",
            "zones": malformed_zones
        })
        self.assertEqual(res_malformed["status"], "SUCCESS")
        self.assertEqual(res_malformed["zones_assessed"], 5)

        # Verify negative pop was clamped to 0
        neg_profile = [z for z in res_malformed["zone_needs"] if z["zone_id"] == "Z_NEG_POP"][0]
        self.assertEqual(neg_profile["affected_population"], 0)
        self.assertEqual(neg_profile["demands"]["water_liters"], 0.0)

        # Verify extreme damage was clamped to 5.0
        ext_dmg = [z for z in res_malformed["zone_needs"] if z["zone_id"] == "Z_EXTREME_DMG"][0]
        self.assertEqual(ext_dmg["damage_level"], 5.0)
        self.assertEqual(ext_dmg["displacement_ratio"], 1.0)

    def test_semantic_kernel_duplicate_plugin_prevention(self):
        """Test that multiple agent instantiations with the same Kernel do not duplicate plugins."""
        shared_kernel = Kernel()
        agent1 = NeedsAssessmentAgent(kernel=shared_kernel)
        self.assertEqual(len(shared_kernel.plugins), 1)

        # Instantiate second agent sharing the same kernel
        agent2 = NeedsAssessmentAgent(kernel=shared_kernel)
        self.assertEqual(len(shared_kernel.plugins), 1)
        self.assertIn("NeedsAssessment", shared_kernel.plugins)


if __name__ == "__main__":
    unittest.main()

