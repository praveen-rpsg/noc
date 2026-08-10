import os
from pathlib import Path
from dotenv import load_dotenv

# Load variables specifically for the receiver
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / 'dbvar.env', override=True)
import re
import asyncio
import logging
import uuid
import json
from datetime import datetime, timezone
from pysnmp.entity import engine, config
from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity.rfc3413 import ntfrcv
from litellm import acompletion
from shared import db

logger = logging.getLogger(__name__)

# The strict, vendor-agnostic prompt forcing the AI to classify and pause for human approval
SNMP_AI_PROMPT = """
You are an expert NOC AI for an enterprise data center and network. Analyze the following raw SNMP trap payload.
1. Classify the trap: Is this "info" (routine, informational) or an "alert" (failure, threshold crossed, requires action)?
2. If it is an "alert", write a brief analysis of the root cause.
3. Dynamically determine the hardware vendor from the trap context (e.g., Cisco, Juniper, Fortinet, Palo Alto, HP/Dell/Huawei/Supermicro/IBM servers, Cisco UCS, or HP/Dell/VMAX/IBM storage systems).
4. Propose the exact vendor-specific CLI commands or management console actions needed to remediate or investigate the issue based on the determined hardware.
5. You must return ONLY a valid JSON object matching this exact structure:
{
  "classification": "info" | "alert",
  "analysis": "Brief explanation of the trap...",
  "proposed_commands": ["command 1", "command 2"]
}
"""
async def analyze_trap_with_ai(trap_details):
    """Passes the SNMP payload to the Emergent LLM for immediate classification and remediation planning."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        emergent_llm_key = os.getenv("EMERGENT_LLM_KEY")
        if not emergent_llm_key:
            raise ValueError("EMERGENT_LLM_KEY missing from dbvar.env")

        # Initialize the chat using your platform's custom wrapper
        chat = LlmChat(
            api_key=emergent_llm_key,
            session_id=f"noc-trap-{str(uuid.uuid4())[:8]}",
            system_message=SNMP_AI_PROMPT
        ).with_model(provider="gemini", model="gemini-2.5-pro")
        
        user_message = UserMessage(
            text=f"SNMP Trap Payload: {json.dumps(trap_details)}"
        )
        
        response = await chat.send_message(user_message)
        
        # Clean the Markdown wrappers so it parses purely as JSON
        content = response.strip()
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()
            
        return json.loads(content)
        
    except Exception as e:
        logger.error(f"AI Trap Analysis failed: {e}")
        # Failsafe: if the AI fails to parse, default to a manual alert
        return {
            "classification": "alert", 
            "analysis": f"AI parsing failed. Manual review required. Error: {str(e)}", 
            "proposed_commands": []
        }
    
async def process_snmp_trap(source_ip, trap_details):
    """Processes the trap, invokes AI only for alerts, and stages for approval."""
    original_udp_ip = source_ip
    device = None
    extracted_ips = []
    
    # 1. Standard Explicit OIDs
    ip_oids = ["1.3.6.1.6.3.18.1.3.0", "SNMP-COMMUNITY-MIB::snmpTrapAddress.0"]
    for oid in ip_oids:
        if oid in trap_details:
            device = await db.devices.find_one({"ip_address": str(trap_details[oid])})
            if device:
                source_ip = str(trap_details[oid])
                break

    # 2. Aggressive Payload Scanning (Deep DB Search)
    if not device:
        ip_pattern = re.compile(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$")
        for val in trap_details.values():
            val_str = str(val).strip()
            if ip_pattern.match(val_str) and val_str not in ["0.0.0.0", "127.0.0.1", "255.255.255.255"]:
                extracted_ips.append(val_str)
                
        for ip in extracted_ips:
            potential_device = await db.devices.find_one({
                "$or": [
                    {"ip_address": ip},
                    {"routing_table.network": {"$regex": f"^{ip}"}},
                    {"routing_table.next_hop": ip}
                ]
            })
            if potential_device:
                device = potential_device
                source_ip = ip
                break

    # 3. Fallback to Hostname Matching
    if not device:
        sysname_oids = ["1.3.6.1.2.1.1.5.0", "SNMPv2-MIB::sysName.0"]
        for oid in sysname_oids:
            if oid in trap_details:
                hostname = str(trap_details[oid])
                device = await db.devices.find_one({"name": hostname})
                if not device:
                     device = await db.devices.find_one({"hostname": hostname})
                if device:
                    source_ip = device.get("ip_address", source_ip)
                    break

    # 4. Final Fallback: Raw UDP Packet IP
    if not device and source_ip != "192.168.65.1" and source_ip != original_udp_ip:
        device = await db.devices.find_one({"ip_address": original_udp_ip})
        if device:
            source_ip = original_udp_ip

    # 5. Virtual Device Fallback
    if not device:
        best_guess_ip = extracted_ips[0] if extracted_ips else original_udp_ip
        logger.warning(f"Trap from unmapped identity (OSPF/IPs: {extracted_ips}). Generating Virtual Alert context.")
        device = {
            "id": f"unmapped-{best_guess_ip.replace('.', '-')}",
            "name": f"Unmapped Router ({best_guess_ip})",
            "ip_address": best_guess_ip
        }

    logger.info(f"Processing SNMP Trap for {device['name']} ({source_ip})")

    # --- CONDITIONAL AI CHECK ---
    # Quick local heuristic check before burning API tokens/keys
    # OIDs indicating link downs, state changes, or protocol failures are flagged as potential alerts.
    trap_oid_string = str(trap_details.values()).lower()
    is_likely_alert = any(term in trap_oid_string for term in ["down", "fail", "error", "loss", "critical", "degard", "offline"])

    classification = "info"
    analysis = "Routine or informational network event logged."
    proposed_commands = []

    if is_likely_alert:
        logger.info("Trap heuristic matched alert criteria. Engaging AI for deep diagnostics...")
        ai_result = await analyze_trap_with_ai(trap_details)
        classification = ai_result.get("classification", "alert").lower()
        analysis = ai_result.get("analysis", analysis)
        proposed_commands = ai_result.get("proposed_commands", [])
    else:
        logger.info("Trap classified as routine info/warning. Skipping AI evaluation.")

    logger.info(f"Final Trap Classification: {classification.upper()}")
    
    # Log the raw trap data permanently
    trap_event = {
        "id": str(uuid.uuid4()),
        "device_id": device["id"],
        "device_name": device["name"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trap_data": trap_details,
        "ai_classification": classification,
        "ai_analysis": analysis
    }
    await db.snmp_traps.insert_one(trap_event)
    
    # Stage for approval ONLY if classified as an alert
    if classification == "alert":
        alert_id = str(uuid.uuid4())
        alert = {
            "id": alert_id,
            "device_id": device["id"],
            "device_name": device["name"],
            "severity": "high",
            "status": "pending_approval",
            "metric_name": "snmp_trap",
            "title": f"Action Required: {device['name']}",
            "description": analysis,
            "proposed_remediation": proposed_commands,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.alerts.insert_one(alert)
        logger.info(f"Remediation staged for {device['name']}. Awaiting human approval.")

def trap_callback(snmpEngine, stateReference, contextEngineId, contextName, varBinds, cbCtx):
    """High-level callback for PySNMP v7 NotificationReceiver."""
    source_ip = "unknown"
    
    try:
        transport_domain, transport_address = snmpEngine.msgAndPduDsp.get_transport_info(stateReference)
        source_ip = transport_address[0]
    except Exception as e:
        logger.error(f"Could not extract source IP from trap: {e}")
            
    trap_details = {}
    for oid, val in varBinds:
        trap_details[oid.prettyPrint()] = val.prettyPrint()
        
    # Dispatch to the FastAPI asyncio loop
    asyncio.create_task(process_snmp_trap(source_ip, trap_details))

async def start_snmp_trap_receiver():
    """Initializes the v7 SNMP engine and binds the UDP listener."""
    snmpEngine = engine.SnmpEngine()
    
    try:
        config.add_transport(
            snmpEngine,
            udp.DOMAIN_NAME,
            udp.UdpAsyncioTransport().open_server_mode(('0.0.0.0', 1162))
        )
    except AttributeError:
        config.addTransport(
            snmpEngine,
            udp.domainName,
            udp.UdpAsyncioTransport().openServerMode(('0.0.0.0', 1162))
        )
        
    try:
        config.add_v1_system(snmpEngine, 'my-area', 'cisco')
    except AttributeError:
        config.addV1System(snmpEngine, 'my-area', 'cisco')
        
    ntfrcv.NotificationReceiver(snmpEngine, trap_callback)
    
    logger.info("======================================================")
    logger.info("AI SNMP Trap Receiver started and listening on UDP 1162")
    logger.info("======================================================")