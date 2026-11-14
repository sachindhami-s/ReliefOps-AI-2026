"""
ReliefOps AI — Inventory Management Plugin
Provides Semantic Kernel plugin functions for querying warehouse stocks,
reserving resource allocations, and committing dispatches in SQLite.

Academic Disclaimer:
Synthetic demonstration platform developed exclusively for CSE476 (Agentic AI and Intelligent Automation).
"""

import json
from typing import Annotated, Dict, List, Optional
from semantic_kernel.functions import kernel_function
from backend.database.db_manager import DatabaseManager, default_db_manager


class InventoryPlugin:
    """Semantic Kernel plugin for regional warehouse inventory management."""

    def __init__(self, db: Optional[DatabaseManager] = None) -> None:
        """
        Initializes InventoryPlugin with a DatabaseManager.
        """
        self._db = db or default_db_manager

    @kernel_function(
        name="get_available_inventory",
        description="Retrieve all available stock from operational warehouses grouped by warehouse.",
    )
    def get_available_inventory(self) -> str:
        """
        Queries SQLite for stock across operational warehouses.

        Returns:
            JSON string containing warehouse list, stock by resource_type, and summary totals.
        """
        sql = """
            SELECT w.warehouse_id, w.name, w.latitude, w.longitude, w.status,
                   wi.resource_type, wi.available_quantity, wi.reserved_quantity, wi.unit
            FROM warehouse_inventory wi
            JOIN warehouses w ON wi.warehouse_id = w.warehouse_id
            WHERE w.status = 'OPERATIONAL'
            ORDER BY w.warehouse_id, wi.resource_type
        """
        try:
            rows = self._db.execute_query(sql)
            warehouse_map: Dict[str, Dict] = {}

            for row in rows:
                wid = row["warehouse_id"]
                if wid not in warehouse_map:
                    warehouse_map[wid] = {
                        "warehouse_id": wid,
                        "warehouse_name": row["name"],
                        "latitude": row["latitude"],
                        "longitude": row["longitude"],
                        "status": row["status"],
                        "resources": {},
                    }
                warehouse_map[wid]["resources"][row["resource_type"]] = {
                    "resource_type": row["resource_type"],
                    "available_quantity": row["available_quantity"],
                    "reserved_quantity": row["reserved_quantity"],
                    "unit": row["unit"],
                }

            warehouses = list(warehouse_map.values())
            total_items = sum(len(w["resources"]) for w in warehouses)

            return json.dumps(
                {
                    "success": True,
                    "warehouses": warehouses,
                    "total_warehouses": len(warehouses),
                    "total_items": total_items,
                }
            )
        except Exception as exc:
            return json.dumps(
                {"success": False, "error": str(exc), "warehouses": [], "total_warehouses": 0, "total_items": 0}
            )

    @kernel_function(
        name="reserve_stock_for_plan",
        description="Reserve resources for an allocation plan atomically across warehouses.",
    )
    def reserve_stock_for_plan(
        self,
        plan_id: Annotated[str, "Unique plan identifier"],
        reservations_json: Annotated[str, "JSON list of {warehouse_id, resource_type, quantity}"],
    ) -> str:
        """
        Reserves available stock for an allocation plan.
        """
        try:
            reservations = json.loads(reservations_json) if isinstance(reservations_json, str) else reservations_json
        except Exception as exc:
            return json.dumps({"success": False, "reserved": [], "failed": [], "message": f"Malformed JSON: {exc}"})

        reserved = []
        failed = []

        for item in reservations:
            wid = item.get("warehouse_id")
            rtype = item.get("resource_type") or item.get("sku_id")
            qty = int(item.get("quantity", 0))

            if not wid or not rtype or qty <= 0:
                failed.append({**item, "reason": "Missing warehouse_id, resource_type, or quantity <= 0"})
                continue

            sql = """
                UPDATE warehouse_inventory
                SET reserved_quantity = reserved_quantity + ?
                WHERE warehouse_id = ? AND resource_type = ? AND (available_quantity - reserved_quantity) >= ?
            """
            try:
                affected = self._db.execute_non_query(sql, (qty, wid, rtype, qty))
                if affected and affected > 0:
                    reserved.append({"warehouse_id": wid, "resource_type": rtype, "quantity": qty})
                else:
                    failed.append({**item, "reason": "Insufficient unreserved inventory or warehouse not found"})
            except Exception as exc:
                failed.append({**item, "reason": str(exc)})

        return json.dumps(
            {
                "success": len(failed) == 0,
                "plan_id": plan_id,
                "reserved": reserved,
                "failed": failed,
                "reserved_count": len(reserved),
                "failed_count": len(failed),
            }
        )

    @kernel_function(
        name="commit_released_allocation",
        description="Finalize committed stock: deducts reserved_quantity from available_quantity and resets reserved_quantity to 0.",
    )
    def commit_released_allocation(
        self,
        plan_id: Annotated[str, "Plan identifier"],
    ) -> str:
        """
        Deducts reserved stock from available stock when allocation plan is released.
        """
        sql = """
            UPDATE warehouse_inventory
            SET available_quantity = available_quantity - reserved_quantity,
                reserved_quantity = 0
            WHERE reserved_quantity > 0
        """
        try:
            affected = self._db.execute_non_query(sql)
            return json.dumps({"success": True, "plan_id": plan_id, "committed_rows": affected or 0})
        except Exception as exc:
            return json.dumps({"success": False, "plan_id": plan_id, "committed_rows": 0, "error": str(exc)})
