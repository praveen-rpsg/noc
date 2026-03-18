"""
ATECH NOC Commander - Agent Management and Activation System
"""

import uuid
import random
import string
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field

def generate_activation_code() -> str:
    """Generate activation code in format ATECH-XXXX-XXXX-XXXX"""
    parts = []
    for _ in range(3):
        part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        parts.append(part)
    return f"ATECH-{'-'.join(parts)}"

def generate_activation_codes(count: int = 200) -> List[dict]:
    """Generate multiple unique activation codes"""
    codes = []
    generated = set()
    
    while len(codes) < count:
        code = generate_activation_code()
        if code not in generated:
            generated.add(code)
            codes.append({
                "id": str(uuid.uuid4()),
                "code": code,
                "status": "available",  # available, activated, expired
                "created_at": datetime.now(timezone.utc).isoformat(),
                "activated_at": None,
                "activated_by": None,
                "agent_id": None
            })
    
    return codes

# Models for Agent System
class Agent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: Optional[str] = None
    organization_id: Optional[str] = None
    activation_code: str
    status: str = "active"  # active, inactive, suspended
    max_devices: int = 15
    assigned_devices: List[str] = []
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AgentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    activation_code: str

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

class ActivationCode(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    code: str
    status: str = "available"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    activated_at: Optional[datetime] = None
    activated_by: Optional[str] = None
    agent_id: Optional[str] = None

# Escalation Configuration
ESCALATION_LEVELS = [
    {
        "level": 1,
        "name": "Team Lead",
        "threshold_hours": 4,
        "priority_filter": ["P1", "P2"]
    },
    {
        "level": 2,
        "name": "Service Delivery Manager",
        "threshold_hours": 8,
        "priority_filter": ["P1", "P2"]
    },
    {
        "level": 3,
        "name": "Director",
        "threshold_hours": 12,
        "priority_filter": ["P1"]
    }
]

class EscalationContact(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    email: str
    role: str  # team_lead, sdm, director
    level: int
    organization_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class EscalationContactCreate(BaseModel):
    name: str
    email: str
    role: str
    level: int
