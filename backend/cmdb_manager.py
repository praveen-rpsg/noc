import uuid
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

class CMDBManager:
    """Core CMDB Manager for Cloud and On-Premises CI Tracking & Relationship Mapping"""

    @staticmethod
    async def create_ci(db, ci_data: dict, user_name: str) -> dict:
        """Stores individual hardware, software, VM, or service record."""
        ci_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        record = {
            "id": ci_id,
            "name": ci_data.get("name"),
            "category": ci_data.get("category"),  # hardware, software, virtual_machine, service, cloud_instance
            "environment": ci_data.get("environment", "on-prem"),  # on-prem, cloud, hybrid
            "provider": ci_data.get("provider", "Internal"),  # AWS, Azure, VMware, Bare-Metal, etc.
            "attributes": ci_data.get("attributes", {}),
            "status": ci_data.get("status", "active"),
            "version": 1,
            "created_by": user_name,
            "created_at": now,
            "updated_at": now
        }

        await db.cmdb_cis.insert_one(record)
        
        # Log version history
        await CMDBManager._log_lifecycle_change(db, ci_id, "CREATED", record, user_name)
        return record

    @staticmethod
    async def update_ci(db, ci_id: str, update_data: dict, user_name: str) -> dict:
        """Records historical modifications, configurations, and operational changes."""
        existing = await db.cmdb_cis.find_one({"id": ci_id})
        if not existing:
            return None

        now = datetime.now(timezone.utc).isoformat()
        new_version = existing.get("version", 1) + 1

        update_payload = {
            **update_data,
            "version": new_version,
            "updated_at": now
        }

        await db.cmdb_cis.update_one({"id": ci_id}, {"$set": update_payload})
        
        updated_record = await db.cmdb_cis.find_one({"id": ci_id}, {"_id": 0})
        await CMDBManager._log_lifecycle_change(db, ci_id, "UPDATED", updated_record, user_name)
        return updated_record

    @staticmethod
    async def link_ci_relationship(db, source_id: str, target_id: str, relation_type: str, user_name: str) -> dict:
        """Connects CIs to show dependencies for impact path analysis."""
        relationship_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        relation_record = {
            "id": relationship_id,
            "source_id": source_id,
            "target_id": target_id,
            "relation_type": relation_type,  # e.g., "depends_on", "runs_on", "connected_to"
            "created_at": now,
            "created_by": user_name
        }

        await db.cmdb_relationships.insert_one(relation_record)
        return relation_record

    @staticmethod
    async def get_impact_path(db, ci_id: str) -> dict:
        """Recursively maps upstream and downstream dependencies to evaluate failure impacts."""
        ci = await db.cmdb_cis.find_one({"id": ci_id}, {"_id": 0})
        if not ci:
            return {"error": "CI not found"}

        # Find direct dependencies (what depends on this CI, or what this CI depends on)
        downstream = await db.cmdb_relationships.find({"source_id": ci_id}, {"_id": 0}).to_list(100)
        upstream = await db.cmdb_relationships.find({"target_id": ci_id}, {"_id": 0}).to_list(100)

        return {
            "ci": ci,
            "impacts_downstream": downstream,  # Components broken if this fails
            "dependent_on_upstream": upstream  # Components this CI relies on
        }

    @staticmethod
    async def _log_lifecycle_change(db, ci_id: str, action: str, snapshot: dict, user_name: str):
        """Internal helper for historical version control audits."""
        await db.cmdb_history.insert_one({
            "id": str(uuid.uuid4()),
            "ci_id": ci_id,
            "action": action,
            "version": snapshot.get("version", 1),
            "snapshot": snapshot,
            "modified_by": user_name,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })