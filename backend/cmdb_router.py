from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from server import get_current_user, db
from cmdb_manager import CMDBManager

cmdb_router = APIRouter(prefix="/cmdb", tags=["CMDB Management"])

class CICreate(BaseModel):
    name: str
    category: str  # hardware, software, virtual_machine, service, cloud_instance
    environment: str = "on-prem"  # on-prem, cloud
    provider: str = "Internal"
    attributes: Dict[str, Any] = {}
    status: str = "active"

class CIRelationshipCreate(BaseModel):
    source_id: str
    target_id: str
    relation_type: str

@cmdb_router.get("/cis")
async def get_all_cis(category: Optional[str] = None, environment: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Retrieve all configuration items with optional filters for cloud/on-prem."""
    query = {}
    if category:
        query["category"] = category
    if environment:
        query["environment"] = environment
    
    cis = await db.cmdb_cis.find(query, {"_id": 0}).to_list(1000)
    return cis

@cmdb_router.post("/cis")
async def create_configuration_item(data: CICreate, current_user: dict = Depends(get_current_user)):
    """Create a new Cloud or On-Premises CI record."""
    result = await CMDBManager.create_ci(db, data.model_dump(), current_user["name"])
    return {"success": True, "ci": result}

@cmdb_router.put("/cis/{ci_id}")
async def update_configuration_item(ci_id: str, data: dict, current_user: dict = Depends(get_current_user)):
    """Update a CI record with full version control history logging."""
    updated = await CMDBManager.update_ci(db, ci_id, data, current_user["name"])
    if not updated:
        raise HTTPException(status_code=404, detail="CI not found")
    return {"success": True, "ci": updated}

@cmdb_router.post("/relationships")
async def create_relationship(data: CIRelationshipCreate, current_user: dict = Depends(get_current_user)):
    """Map dependencies between CIs."""
    rel = await CMDBManager.link_ci_relationship(db, data.source_id, data.target_id, data.relation_type, current_user["name"])
    return {"success": True, "relationship": rel}

@cmdb_router.get("/cis/{ci_id}/impact-path")
async def get_ci_impact_path(ci_id: str, current_user: dict = Depends(get_current_user)):
    """View dependency impact path when a component fails."""
    path = await CMDBManager.get_impact_path(db, ci_id)
    return path

@cmdb_router.get("/cis/{ci_id}/history")
async def get_ci_history(ci_id: str, current_user: dict = Depends(get_current_user)):
    """Fetch lifecycle modification history and version changes over time."""
    history = await db.cmdb_history.find({"ci_id": ci_id}, {"_id": 0}).sort("timestamp", -1).to_list(100)
    return history