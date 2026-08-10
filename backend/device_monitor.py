import asyncio
from datetime import datetime, timezone
import uuid
import time
import traceback
import logging
#import autonomous_playbook 
import json 
from shared import db  # Ensure it shares the common database connection instance
logger = logging.getLogger(__name__)

# =====================================================================
# ALERT ALIGNMENT HELPERS
# =====================================================================
# Code Inserted 21/07/2026 - Vendor Agnostic telemetry Ingestion - 17-118
# Code Corrected 26/07/2026 

async def create_metric_incident(db, device, alert_title, alert_desc, metric_name, alert_id=None, ws_manager=None):
    """Automatically promote a critical alert to an active incident ticket with metrics context"""
    existing = await db.incidents.find_one({
        "device_id": device["id"],
        "title": f"Threshold Exception: {metric_name.upper()}",
        "status": {"$in": ["open", "in_progress", "awaiting_approval"]}
    })
    
    if existing:
        return

    latest_metrics = await db.performance_metrics.find_one(
        {"device_id": device["id"]},
        sort=[("timestamp", -1)]
    )
    metrics_output = latest_metrics.get("metrics_output", {}) if latest_metrics else {}

    incident_id = str(uuid.uuid4())
    incident = {
        "id": incident_id,
        "ticket_number": f"INC-{int(time.time())}",
        "title": f"Threshold Exception: {metric_name.upper()}",
        "description": f"Automated performance threshold exception. {alert_desc}",
        "priority": "P1",  
        "category": "Performance",
        "status": "open",
        "device_id": device["id"],
        "affected_devices": [device["id"]],
        "related_alerts": [alert_id] if alert_id else [],
        "metrics_context": metrics_output, 
        "created_by": "System Monitor",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.incidents.insert_one(incident)
    logger.info(f"Critical P1/P2 incident created for {device['name']}")

    # Broadcast sound trigger to frontend UI
    if ws_manager:
        await ws_manager.broadcast({
            "type": "critical_failure_sound",
            "data": {
                "incident_id": incident_id,
                "title": alert_title,
                "device": device['name']
            }
        })

async def check_metric_threshold(db, device, metric_name, current_value, warning_limit, critical_limit, units="", ws_manager=None):
    """Evaluate metric values against defined boundaries and manage active alert statuses"""
    target_severity = None
    alert_title = ""
    alert_desc = ""
    threshold_triggered = None
    
    if current_value >= critical_limit:
        target_severity = "critical"
        alert_title = f"Critical {metric_name.replace('_', ' ').title()} Exception"
        alert_desc = f"{metric_name.replace('_', ' ').title()} on device {device['name']} has reached {current_value}{units}, violating the critical limit of {critical_limit}{units}."
        threshold_triggered = critical_limit
    elif current_value >= warning_limit:
        target_severity = "high"
        alert_title = f"High {metric_name.replace('_', ' ').title()} Utilization"
        alert_desc = f"{metric_name.replace('_', ' ').title()} on device {device['name']} has reached {current_value}{units}, exceeding the warning limit of {warning_limit}{units}."
        threshold_triggered = warning_limit
        
    active_alert = await db.alerts.find_one({
        "device_id": device["id"],
        "metric_name": metric_name,
        "status": "active"
    })
    
    if target_severity:
        if active_alert:
            if active_alert.get("severity") != target_severity:
                await db.alerts.update_one(
                    {"id": active_alert["id"]},
                    {"$set": {
                        "severity": target_severity,
                        "title": alert_title,
                        "description": alert_desc,
                        "metric_value": current_value,
                        "threshold": threshold_triggered
                    }}
                )
                if target_severity == "critical":
                   await create_metric_incident(db, device, alert_title, alert_desc, metric_name, active_alert["id"], ws_manager)
        else:
            alert_id = str(uuid.uuid4())
            new_alert = {
                "id": alert_id,
                "device_id": device["id"],
                "device_name": device["name"],
                "severity": target_severity,
                "status": "active",
                "title": alert_title,
                "description": alert_desc,
                "metric_name": metric_name,
                "metric_value": current_value,
                "threshold": threshold_triggered,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.alerts.insert_one(new_alert)
            if target_severity == "critical":
                await create_metric_incident(db, device, alert_title, alert_desc, metric_name, alert_id, ws_manager)
    else:
        if active_alert:
            await db.alerts.update_one(
                {"id": active_alert["id"]},
                {"$set": {
                    "status": "resolved",
                    "resolved_by": "System Monitor",
                    "resolved_at": datetime.now(timezone.utc).isoformat()
                }}
            )



async def update_incident_approval_state(db, incident_id, tracking_status="awaiting_approval"):
    await db.incidents.update_one(
        {"id": incident_id},
        {"$set": {
            "monitor_override_lock": True,
            "last_monitor_check": datetime.now(timezone.utc).isoformat()
        }}
    )
    logger.info(f"Applied automated system operational lock tracking marker on incident: {incident_id}")


# =====================================================================
# BACKGROUND CORE MONITOR LOOP
# =====================================================================

async def monitor_devices(
    db,
    get_device_metrics,
    decrypt_password,
    create_offline_incident,
    resolve_device_incident,
    save_device_event,
    ws_manager=None 
    # added on 24th July 26 for alert Sound
):
    import traceback

    print("Device monitor started")

    while True:
        try:
            devices = await db.devices.find({}).to_list(1000)

            for device in devices:
                
                # CRITICAL FIX: Skip polling for this device if the AI has staged an incident 
                # fix and is actively waiting for human approval. This prevents duplicate alert generation.
                active_ai_lock = await db.incidents.find_one({
                    "device_id": device["id"], 
                    "status": "awaiting_approval"
                })
                
                if active_ai_lock:
                    logger.info(f"Skipping monitor polling for {device['name']} - currently locked for AI remediation approval.")
                    continue

                metrics = {}
                old_status = device.get("status", "offline")
                new_status = "offline"

                # Standard fallback state allocations
                cpu_usage = 0.0
                memory_usage = 0.0
                disk_usage = 0.0
                bandwidth_in = 0.0
                bandwidth_out = 0.0
                latency_ms = 0.0
                packet_loss = 100.0
                uptime_hours = 0
                link_status = "down"
                interfaces = device.get("interfaces", [])
                routing_table = device.get("routing_table", [])     
                mac_address = device.get("mac_address", "")
                stp_status = device.get("stp_status", "unknown")    
                memory_usage_percentage = device.get("memory_usage_percentage",0.0)
                switching_loop_detected = device.get("switching_loop_detected", False) 
                asymetric_routing_detected = device.get("asymmetric_routing_detected", False)
                hardware_health_status = device.get("hardware_health_status", "unknown")
                hardware_temperature_celsius = device.get("hardware_temperature_celsius", None)
                hardware_fan_status = device.get("hardware_fan_status", "unknown")
                hardware_fan_speed_rpm = device.get("hardware_fan_speed_rpm", None)
                hardware_power_supply_status = device.get("hardware_power_supply_status", "unknown")
                hardware_disk_health_status = device.get("hardware_disk_health_status", "unknown")
                hardware_disk_temperature_celsius = device.get("hardware_disk_temperature_celsius", None)
                hardware_disk_smart_status = device.get("hardware_disk_smart_status", "unknown")
                hardware_disk_smart_errors = device.get("hardware_disk_smart_errors", [])
                hardware_disk_smart_warnings = device.get("hardware_disk_smart_warnings", [])   
                hardware_memory_health_status = device.get("hardware_memory_health_status", "unknown")
                hardware_memory_temperature_celsius = device.get("hardware_memory_temperature_celsius", None)
                hardware_memory_ecc_errors = device.get("hardware_memory_ecc_errors", [])
                hardware_memory_ecc_warnings = device.get("hardware_memory_ecc_warnings", [])
                software_version = device.get("software_version", "unknown")
                software_patch_level = device.get("software_patch_level", "unknown")
                hardware_component_status = device.get("hardware_component_status", "unknown")
                hardware_motherboard_status = device.get("hardware_motherboard_status", "unknown")
                hardware_battery_status = device.get("hardware_battery_status", "unknown")
                hardware_asic_status = device.get("hardware_asic_status", "unknown")
                packet_drop_rate = device.get("packet_drop_rate", 0.0)
                ipaddress_conflicts_detected = device.get("ip_address_conflicts_detected", False)
                vtpm_status = device.get("vtpm_status", "unknown")
                stp_root_bridge_status = device.get("stp_root_bridge_status", "unknown")
                stp_port_roles = device.get("stp_port_roles", {})
                stp_port_states = device.get("stp_port_states", {})
                stp_port_costs = device.get("stp_port_costs", {})
                stp_loopback_interfaces = device.get("stp_loopback_interfaces", [])
                disk_io_errors = device.get("disk_io_errors", 0)
                disk_usage_percentage = device.get("disk_usage_percentage", 0.0)
                storage_controller_status = device.get("storage_controller_status", "unknown")
                raid_array_status = device.get("raid_array_status", "unknown")
                raid_array_health = device.get("raid_array_health", "unknown")
                raid_array_degraded_disks = device.get("raid_array_degraded_disks", [])
                raid_array_failed_disks = device.get("raid_array_failed_disks", [])
                storage_battery_status = device.get("storage_battery_status", "unknown")
                cache_memory_status = device.get("cache_memory_status", "unknown")
                cache_memory_errors = device.get("cache_memory_errors", [])
                neighbors = device.get("neighbors", [])
                vrfs = device.get("vrfs", [])
                vrf_interfaces = device.get("vrf_interfaces", [])
                vrf_routing_tables = device.get("vrf_routing_tables", [])
                vrf_bgp_neighbors = device.get("vrf_bgp_neighbors", [])
                vrf_ospf_neighbors = device.get("vrf_ospf_neighbors", [])
                vrf_eigrp_neighbors = device.get("vrf_eigrp_neighbors", [])
                vrf_rip_neighbors = device.get("vrf_rip_neighbors", [])
                vrf_static_routes = device.get("vrf_static_routes", [])
                access_lists = device.get("access_lists", [])
                access_list_entries = device.get("access_list_entries", [])
                access_list_statistics = device.get("access_list_statistics", [])
                route_maps = device.get("route_maps", [])
                route_map_entries = device.get("route_map_entries", [])
                route_map_statistics = device.get("route_map_statistics", [])
                routing_protocols = device.get("routing_protocols", [])
                routing_protocol_neighbors = device.get("routing_protocol_neighbors", [])
                ospf_errors = device.get("ospf_errors", [])
                bgp_errors = device.get("bgp_errors", [])
                eigrp_errors = device.get("eigrp_errors", [])
                static_route_errors = device.get("static_route_errors", [])
                spanning_tree_errors = device.get("spanning_tree_errors", [])
                spanning_tree_instances = device.get("spanning_tree_instances", [])
                mac_address_table = device.get("mac_address_table", [])
                mac_address_table_errors = device.get("mac_address_table_errors", [])

                os_version = device.get("os_version")
                mac_address = device.get("mac_address")
                routing_table = device.get("routing_table", [])
                model = device.get("model", "Unknown")
                hostname = device.get("hostname")
                serial_number = device.get("serial_number", "")

                try:
                    if device.get("username") and device.get("password"):

                        probe_payload = dict(device)
                        probe_payload["password"] = decrypt_password(
                            device["password"]
                        )
                        try:
                            metrics = await asyncio.wait_for(
                                get_device_metrics(probe_payload),
                                timeout=60.0
                            )
                        except asyncio.TimeoutError:
                            logger.warning(f"SSH Timeout reaching {device['name']} ({device['ip_address']}) - Marking as offline.")
                            metrics = {}

                        logger.info("=" * 80)
                        logger.info(f"Device: {device['name']} ({device['ip_address']})")
                        logger.info("=" * 80)
                        
                        if metrics is None:
                            metrics = {}

                        if metrics:
                            new_status = "online"
                        # ---------------------------------------------------------
                            # UNIVERSAL VENDOR-AGNOSTIC FAULT SENSOR
                            # Scans entire payload for any key indicating failure
                            # ---------------------------------------------------------
                            for key, value in metrics.items():
                                if isinstance(value, str) and value.lower() in ["failed", "critical", "alarm", "fault"]:
                                    logger.warning(f"Universal Sensor tripped on {device['name']} for metric: {key}")
                                    await check_metric_threshold(db, device, key, 100, 50, 100, "state", ws_manager)
                                elif isinstance(value, list) and key.endswith("_errors") and len(value) > 0:
                                    logger.warning(f"Universal Sensor tripped on list {key} for {device['name']}")
                                    await check_metric_threshold(db, device, key, len(value), 1, 5, "errors", ws_manager)


                        # metrics = await get_device_metrics(
                        #     probe_payload
                        # )
                        # logger.info("=" * 80)
                        # logger.info(f"Device: {device['name']} ({device['ip_address']})")
                        # logger.info(f"Metrics returned: {metrics}")
                        # logger.info("=" * 80)
                        
                        # if metrics is None:
                        #     metrics = {}

                        # if metrics:
                        #     new_status = "online"

                            cpu_usage = float(metrics.get("cpu_usage", 0.0))
                            for cpu_core in metrics.get("cpu_cores", []):
                                logger.info(
                                    f"CPU Core {cpu_core.get('core_id')}: "
                                    f"Usage={cpu_core.get('usage_percent')}%"
                                )
                                if cpu_core.get("usage_percent", 0.0) > 70.0:
                                    logger.warning(f"{device['name']} - CPU Core {cpu_core.get('core_id')} is above 70% usage")
                                    existing = await db.alerts.find_one({"device_id": device["id"],
                                                                         "metric_name": f"cpu_core_{cpu_core.get('core_id')}",
                                                                         "status": "active"})
                                    if not existing:
                                        alert_id = str(uuid.uuid4())
                                        alert = {
                                            "id": alert_id,
                                            "device_id": device["id"],
                                            "device_name": device["name"],
                                            "severity": "high",
                                            "status": "active",
                                            "metric_name": f"cpu_core_{cpu_core.get('core_id')}",
                                            "title": f"CPU Core {cpu_core.get('core_id')} High Usage",
                                            "description": f"CPU Core {cpu_core.get('core_id')} is above 70% usage.",
                                            "created_at": datetime.now(timezone.utc).isoformat()
                                        }
                                        await db.alerts.insert_one(alert)
                                        
                                    existing_incident = await db.incidents.find_one({
                                        "device_id": device["id"],
                                        "title": f"CPU Core {cpu_core.get('core_id')} High Usage",
                                        "status": {"$in": ["open", "in_progress", "awaiting_approval"]}
                                    })
                                    if not existing_incident:
                                        incident = {
                                            "id": str(uuid.uuid4()),
                                            "ticket_number": f"INC-{int(time.time())}",
                                            "title": f"CPU Core {cpu_core.get('core_id')} High Usage",
                                            "description": (
                                                f"CPU Core {cpu_core.get('core_id')} on device "
                                                f"{device['name']} has exceeded 70% utilization."
                                            ),
                                            "priority": "P2",
                                            "category": "Performance",
                                            "status": "in_progress",
                                            "device_id": device["id"],
                                            "affected_devices": [device["id"]],
                                            "related_alerts": [alert_id] if not existing else [],
                                            "created_by": "System Monitor",
                                            "created_at": datetime.now(timezone.utc).isoformat(),
                                            "updated_at": datetime.now(timezone.utc).isoformat()
                                        }
                                        await db.incidents.insert_one(incident)
                                        logger.info(f"Created incident for CPU Core {cpu_core.get('core_id')} high usage on {device['name']}")
                            
                            memory_usage = float(metrics.get("memory_usage", 0.0))
                            for mem_mod in metrics.get("memory_modules", []):
                                logger.info(
                                    f"Memory Module {mem_mod.get('module_id')}: "
                                    f"Usage={mem_mod.get('usage_percent')}%"
                                )
                                if mem_mod.get("usage_percent", 0.0) > 70.0:
                                    logger.warning(f"{device['name']} - Memory Module {mem_mod.get('module_id')} is above 70% usage")
                                    existing = await db.alerts.find_one({"device_id": device["id"],
                                                                         "metric_name": f"memory_module_{mem_mod.get('module_id')}",
                                                                         "status": "active"})
                                    if not existing:
                                        alert_id = str(uuid.uuid4())
                                        alert = {
                                            "id": alert_id,
                                            "device_id": device["id"],
                                            "device_name": device["name"],
                                            "severity": "high",
                                            "status": "active",
                                            "metric_name": f"memory_module_{mem_mod.get('module_id')}",
                                            "title": f"Memory Module {mem_mod.get('module_id')} High Usage",
                                            "description": f"Memory Module {mem_mod.get('module_id')} is above 70% usage.",
                                            "created_at": datetime.now(timezone.utc).isoformat()
                                        }
                                        await db.alerts.insert_one(alert)
                                        
                                    existing_incident = await db.incidents.find_one({
                                        "device_id": device["id"],
                                        "title": f"Memory Module {mem_mod.get('module_id')} High Usage",
                                        "status": {"$in": ["open", "in_progress", "awaiting_approval"]}
                                    })
                                    if not existing_incident:
                                        incident = {
                                            "id": str(uuid.uuid4()),
                                            "ticket_number": f"INC-{int(time.time())}",
                                            "title": f"Memory Module {mem_mod.get('module_id')} High Usage",
                                            "description": (
                                                f"Memory Module {mem_mod.get('module_id')} on device "
                                                f"{device['name']} has exceeded 70% utilization."
                                            ),
                                            "priority": "P2",
                                            "category": "Performance",
                                            "status": "in_progress",
                                            "device_id": device["id"],
                                            "affected_devices": [device["id"]],
                                            "related_alerts": [alert_id] if not existing else [],
                                            "created_by": "System Monitor",
                                            "created_at": datetime.now(timezone.utc).isoformat(),
                                            "updated_at": datetime.now(timezone.utc).isoformat()
                                        }
                                        await db.incidents.insert_one(incident)
                                        logger.info(f"Created incident for Memory Module {mem_mod.get('module_id')} high usage on {device['name']}")

                            disk_usage = float(metrics.get("disk_usage", 0.0))
                            bandwidth_in = float(metrics.get("bandwidth_in", 0.0))
                            bandwidth_out = float(metrics.get("bandwidth_out", 0.0))
                            latency_ms = float(metrics.get("latency_ms", 0.0))
                            packet_loss = float(metrics.get("packet_loss", 0.0))
                            uptime_hours = int(metrics.get("uptime_hours", 0))

                            neighbors = metrics.get("neighbors", neighbors)
                            os_version = metrics.get("os_version", os_version)
                            mac_address = metrics.get("mac_address", mac_address)
                            link_status = metrics.get("link_status", link_status)
                            interfaces = metrics.get("interfaces", interfaces)       

                            for interface in interfaces:
                                logger.info(
                                    f"{interface['interface']} | "
                                    f"Admin={interface.get('admin_status')} | "
                                    f"Link={interface.get('link_status')} | "
                                    f"Speed: {interface.get('speed', 'N/A')} | "
                                    f"Duplex: {interface.get('duplex', 'N/A')}"
                                )

                                admin_stat = str(interface.get('admin_status', '')).lower()
                                link_stat = str(interface.get('link_status', '')).lower()
                                proto_stat = str(interface.get('protocol', '')).lower()

                                # Fix on interface status 26/7/36 =
                                if "up" in admin_stat and ("down" in link_stat or "down" in proto_stat):
                                    logger.warning(f"{device['name']} - Interface {interface['interface']} dropped unexpectedly!")
                                    existing = await db.alerts.find_one({"device_id": device["id"],
                                                                         "metric_name": f"interface_{interface['interface']}",
                                                                         "status": "active"})
                                    if not existing:
                                        alert_id = str(uuid.uuid4())
                                        alert = {
                                            "id": alert_id,
                                            "device_id": device["id"],
                                            "device_name": device["name"],
                                            "severity": "critical",
                                            "status": "active",
                                            "metric_name": f"interface_{interface['interface']}",
                                            "title": f"Interface {interface['interface']} Down",
                                            "description": f"Interface {interface['interface']} is down.",
                                            "created_at": datetime.now(timezone.utc).isoformat()
                                        }
                                        await db.alerts.insert_one(alert)
                                        
                                    existing_incident = await db.incidents.find_one({
                                        "device_id": device["id"],
                                        "title": f"Interface {interface['interface']} Down",
                                        "status": {"$in": ["open", "in_progress", "awaiting_approval"]}
                                    })
                                    if not existing_incident:
                                        incident = {
                                            "id": str(uuid.uuid4()),
                                            "ticket_number": f"INC-{int(time.time())}",
                                            "title": f"Interface {interface['interface']} Down",
                                            "description": (
                                                f"Interface {interface['interface']} on device "
                                                f"{device['name']} ({device['ip_address']}) is down."
                                            ),
                                            "priority": "P1",
                                            "category": "Network",
                                            "status": "in_progress",
                                            "device_id": device["id"],
                                            "affected_devices": [device["id"]],
                                            "related_alerts": [alert_id] if not existing else [],
                                            "created_by": "System Monitor",
                                            "created_at": datetime.now(timezone.utc).isoformat(),
                                            "updated_at": datetime.now(timezone.utc).isoformat(),
                                            "diagnostic_payload": {
                                                "incident_type": "interface_down",
                                                "incident_interface": interface["interface"],
                                                "metrics": metrics,
                                                "performance": {
                                                    "cpu_usage": cpu_usage,
                                                    "memory_usage": memory_usage,
                                                    "disk_usage": disk_usage,
                                                    "bandwidth_in": bandwidth_in,
                                                    "bandwidth_out": bandwidth_out,
                                                    "latency_ms": latency_ms,
                                                    "packet_loss": packet_loss,
                                                    "uptime_hours": uptime_hours
                                                },
                                                "interfaces": interfaces,
                                                "routing_table": routing_table,
                                                "neighbors": neighbors,
                                                "device": {
                                                    "vendor": device.get("vendor"),
                                                    "model": model,
                                                    "hostname": hostname,
                                                    "serial_number": serial_number,
                                                    "os_version": os_version,
                                                    "ip_address": device["ip_address"]
                                                },
                                                "created_timestamp": datetime.now(timezone.utc).isoformat()
                                            }
                                        }
                                        await db.incidents.insert_one(incident)

                                        if ws_manager:
                                            await ws_manager.broadcast({
                                                "type": "critical_failure_sound",
                                                "data": {"incident_id": incident["id"], "title": incident["title"], "device": device['name']}
                                            })
                                        
                                        logger.info(f"Created incident for Interface {interface['interface']} down on {device['name']}")

                            model = metrics.get("model", model)
                            hostname = metrics.get("hostname", hostname)
                            serial_number = metrics.get("serial_number", serial_number)
                            routing_table = metrics.get("routing_table", routing_table)
                            
                            for route in routing_table:
                                if route.get("status") == "down":
                                    logger.warning(f"{device['name']} - Route to {route.get('destination')} is DOWN")
                                    existing = await db.alerts.find_one({"device_id": device["id"],
                                                                         "metric_name": f"route_{route['destination']}",
                                                                         "status": "active"})
                                    if not existing:
                                        alert_id = str(uuid.uuid4())
                                        alert = {
                                            "id": alert_id,
                                            "device_id": device["id"],
                                            "device_name": device["name"],
                                            "severity": "critical",
                                            "status": "active",
                                            "metric_name": f"route_{route['destination']}",
                                            "title": f"Route to {route['destination']} Down",
                                            "description": f"Route to {route['destination']} is down.",
                                            "created_at": datetime.now(timezone.utc).isoformat()
                                        }
                                        await db.alerts.insert_one(alert)
                                        
                                    existing_incident = await db.incidents.find_one({
                                        "device_id": device["id"],
                                        "title": f"Route to {route['destination']} Down",
                                        "status": {"$in": ["open", "in_progress", "awaiting_approval"]}
                                    })
                                    if not existing_incident:
                                        incident = {
                                            "id": str(uuid.uuid4()),
                                            "ticket_number": f"INC-{int(time.time())}",
                                            "title": f"Route to {route['destination']} Down",
                                            "description": (
                                                f"Route to {route['destination']} via "
                                                f"{route.get('next_hop')} on device "
                                                f"{device['name']} is down."
                                            ),
                                            "priority": "P1",
                                            "category": "Network",
                                            "status": "in_progress",
                                            "device_id": device["id"],
                                            "affected_devices": [device["id"]],
                                            "related_alerts": [alert_id] if not existing else [],
                                            "created_by": "System Monitor",
                                            "created_at": datetime.now(timezone.utc).isoformat(),
                                            "updated_at": datetime.now(timezone.utc).isoformat()
                                        }
                                        await db.incidents.insert_one(incident)
                                        logger.info(f"Created incident for Route {route['destination']} down on {device['name']}")

                            hardware_health_status = metrics.get("hardware_health_status", hardware_health_status)   
                            for hardware_health in metrics.get("hardware_components", []):
                                if hardware_health.get("status") != "healthy":
                                    logger.warning(f"{device['name']} - Hardware Component {hardware_health.get('component_name')} is in {hardware_health.get('status')} state")
                                    existing = await db.alerts.find_one({"device_id": device["id"],
                                                                         "metric_name": f"hardware_{hardware_health['component_name']}",
                                                                         "status": "active"})
                                    if not existing:
                                        await db.alerts.insert_one({
                                            "id": str(uuid.uuid4()),
                                            "device_id": device["id"],
                                            "device_name": device["name"],
                                            "severity": "high",
                                            "status": "active",
                                            "metric_name": f"hardware_{hardware_health['component_name']}",
                                            "title": f"Hardware Component {hardware_health['component_name']} Issue",
                                            "description": f"Hardware Component {hardware_health['component_name']} is in {hardware_health.get('status')} state.",
                                            "created_at": datetime.now(timezone.utc).isoformat()
                                        })

                            hardware_temperature_celsius = metrics.get("hardware_temperature_celsius", hardware_temperature_celsius)
                            for hardware_tempature in metrics.get("hardware_components", []):
                                if hardware_tempature.get("temperature_celsius") and hardware_tempature.get("temperature_celsius") > 80:
                                    existing = await db.alerts.find_one({"device_id": device["id"],
                                                                         "metric_name": f"hardware_{hardware_tempature['component_name']}_temperature",
                                                                         "status": "active"})
                                    if not existing:
                                        await db.alerts.insert_one({
                                            "id": str(uuid.uuid4()),
                                            "device_id": device["id"],
                                            "device_name": device["name"],
                                            "severity": "high",
                                            "status": "active",
                                            "metric_name": f"hardware_{hardware_tempature['component_name']}_temperature",
                                            "title": f"Hardware Component {hardware_tempature['component_name']} High Temperature",
                                            "description": f"Hardware Component {hardware_tempature['component_name']} temperature is above 80C.",
                                            "created_at": datetime.now(timezone.utc).isoformat()
                                        })

                            hardware_fan_status = metrics.get("hardware_fan_status", hardware_fan_status)       
                            for hardware_fan in metrics.get("hardware_components", []):
                                if hardware_fan.get("fan_status") != "operational":
                                    existing = await db.alerts.find_one({"device_id": device["id"],
                                                                         "metric_name": f"hardware_{hardware_fan['component_name']}_fan",
                                                                         "status": "active"})
                                    if not existing:
                                        await db.alerts.insert_one({
                                            "id": str(uuid.uuid4()),
                                            "device_id": device["id"],
                                            "device_name": device["name"],
                                            "severity": "high",
                                            "status": "active",
                                            "metric_name": f"hardware_{hardware_fan['component_name']}_fan",
                                            "title": f"Hardware Component {hardware_fan['component_name']} Fan Issue",
                                            "description": f"Hardware Component {hardware_fan['component_name']} fan is not operational.",
                                            "created_at": datetime.now(timezone.utc).isoformat()
                                        })

                            hardware_power_supply_status = metrics.get("hardware_power_supply_status", hardware_power_supply_status)
                            for hardware_power_supply in metrics.get("hardware_components", []):
                                if hardware_power_supply.get("power_supply_status") != "operational":
                                    existing = await db.alerts.find_one({"device_id": device["id"],
                                                                         "metric_name": f"hardware_{hardware_power_supply['component_name']}_power_supply",
                                                                         "status": "active"})
                                    if not existing:
                                        await db.alerts.insert_one({
                                            "id": str(uuid.uuid4()),
                                            "device_id": device["id"],
                                            "device_name": device["name"],
                                            "severity": "high",
                                            "status": "active",
                                            "metric_name": f"hardware_{hardware_power_supply['component_name']}_power_supply",
                                            "title": f"Hardware Component {hardware_power_supply['component_name']} Power Supply Issue",
                                            "description": f"Hardware Component {hardware_power_supply['component_name']} power supply is not operational.",
                                            "created_at": datetime.now(timezone.utc).isoformat()
                                        })

                            disk_usage_percentage = metrics.get("disk_usage_percentage", disk_usage_percentage)
                            for d_usage in metrics.get("disks", []):
                                if d_usage.get("usage_percentage") and d_usage.get("usage_percentage") > 90:
                                    existing = await db.alerts.find_one({"device_id": device["id"],
                                                                         "metric_name": f"disk_{d_usage['disk_name']}",
                                                                         "status": "active"})
                                    if not existing:
                                        await db.alerts.insert_one({
                                            "id": str(uuid.uuid4()),
                                            "device_id": device["id"],
                                            "device_name": device["name"],
                                            "severity": "high",
                                            "status": "active",
                                            "metric_name": f"disk_{d_usage['disk_name']}",
                                            "title": f"Disk {d_usage['disk_name']} High Usage",
                                            "description": f"Disk {d_usage['disk_name']} usage is above 90%.",
                                            "created_at": datetime.now(timezone.utc).isoformat()
                                        })   
                            
                            memory_usage_percentage = metrics.get("memory_usage_percentage", memory_usage_percentage)
                            hardware_disk_health_status = metrics.get("hardware_disk_health_status", hardware_disk_health_status)
                            for hardware_disk in metrics.get("disks", []):
                                if hardware_disk.get("health_status") != "healthy":
                                    existing = await db.alerts.find_one({"device_id": device["id"],
                                                                         "metric_name": f"disk_{hardware_disk['disk_name']}_health",
                                                                         "status": "active"})
                                    if not existing:
                                        await db.alerts.insert_one({
                                            "id": str(uuid.uuid4()),
                                            "device_id": device["id"],
                                            "device_name": device["name"],
                                            "severity": "high",
                                            "status": "active",
                                            "metric_name": f"disk_{hardware_disk['disk_name']}_health",
                                            "title": f"Disk {hardware_disk['disk_name']} Health Issue",
                                            "description": f"Disk {hardware_disk['disk_name']} health status is {hardware_disk.get('health_status')}.",
                                            "created_at": datetime.now(timezone.utc).isoformat()
                                        })
                                        
                            hardware_motherboard_status = metrics.get("hardware_motherboard_status", hardware_motherboard_status)
                            for hardware_motherboard in metrics.get("hardware_components", []):
                                if hardware_motherboard.get("motherboard_status") != "operational":
                                    existing = await db.alerts.find_one({"device_id": device["id"],
                                                                         "metric_name": f"hardware_{hardware_motherboard['component_name']}_motherboard",
                                                                         "status": "active"})
                                    if not existing:
                                        await db.alerts.insert_one({
                                            "id": str(uuid.uuid4()),
                                            "device_id": device["id"],
                                            "device_name": device["name"],
                                            "severity": "high",
                                            "status": "active",
                                            "metric_name": f"hardware_{hardware_motherboard['component_name']}_motherboard",
                                            "title": f"Hardware Component {hardware_motherboard['component_name']} Motherboard Issue",
                                            "description": f"Hardware Component {hardware_motherboard['component_name']} motherboard is not operational.",
                                            "created_at": datetime.now(timezone.utc).isoformat()
                                        })

                            hardware_battery_status = metrics.get("hardware_battery_status", hardware_battery_status)
                            for hardware_battery in metrics.get("hardware_components", []):
                                if hardware_battery.get("battery_status") != "operational":
                                    existing = await db.alerts.find_one({"device_id": device["id"],
                                                                         "metric_name": f"hardware_{hardware_battery['component_name']}_battery",
                                                                         "status": "active"})
                                    if not existing:
                                        await db.alerts.insert_one({
                                            "id": str(uuid.uuid4()),
                                            "device_id": device["id"],
                                            "device_name": device["name"],
                                            "severity": "high",
                                            "status": "active",
                                            "metric_name": f"hardware_{hardware_battery['component_name']}_battery",
                                            "title": f"Hardware Component {hardware_battery['component_name']} Battery Issue",
                                            "description": f"Hardware Component {hardware_battery['component_name']} battery is not operational.",
                                            "created_at": datetime.now(timezone.utc).isoformat()
                                        })

                            hardware_fan_speed_rpm = metrics.get("hardware_fan_speed_rpm", hardware_fan_speed_rpm)
                            for hardware_fan in metrics.get("hardware_components", []):
                                if hardware_fan.get("fan_speed_rpm") and hardware_fan.get("fan_speed_rpm") < 1000:
                                    existing = await db.alerts.find_one({"device_id": device["id"],
                                                                         "metric_name": f"hardware_{hardware_fan['component_name']}_fan_speed",
                                                                         "status": "active"})
                                    if not existing:
                                        await db.alerts.insert_one({
                                            "id": str(uuid.uuid4()),
                                            "device_id": device["id"],
                                            "device_name": device["name"],
                                            "severity": "high",
                                            "status": "active",
                                            "metric_name": f"hardware_{hardware_fan['component_name']}_fan_speed",
                                            "title": f"Hardware Component {hardware_fan['component_name']} Low Fan Speed",
                                            "description": f"Hardware Component {hardware_fan['component_name']} fan speed is below 1000 RPM.",
                                            "created_at": datetime.now(timezone.utc).isoformat()
                                        })

                            spanning_tree_instances = metrics.get("spanning_tree_instances", spanning_tree_instances)
                            for spanning_tree in metrics.get("spanning_tree_instances", []):
                                if spanning_tree.get("status") != "forwarding":
                                    existing = await db.alerts.find_one({"device_id": device["id"],
                                                                         "metric_name": f"spanning_tree_{spanning_tree['instance_id']}",
                                                                         "status": "active"})
                                    if not existing:
                                        await db.alerts.insert_one({
                                            "id": str(uuid.uuid4()),
                                            "device_id": device["id"],
                                            "device_name": device["name"],
                                            "severity": "high",
                                            "status": "active",
                                            "metric_name": f"spanning_tree_{spanning_tree['instance_id']}",
                                            "title": f"Spanning Tree Instance {spanning_tree['instance_id']} Issue",
                                            "description": f"Spanning Tree Instance {spanning_tree['instance_id']} is not in forwarding state.",
                                            "created_at": datetime.now(timezone.utc).isoformat()
                                        })

                            spanning_tree_errors = metrics.get("spanning_tree_errors", spanning_tree_errors)
                            for spanning_tree_error in metrics.get("spanning_tree_errors", []):
                                if spanning_tree_error.get("error_count") and spanning_tree_error.get("error_count") > 0:
                                    existing = await db.alerts.find_one({"device_id": device["id"],
                                                                         "metric_name": f"spanning_tree_{spanning_tree_error['instance_id']}_errors",
                                                                         "status": "active"})
                                    if not existing:
                                        await db.alerts.insert_one({
                                            "id": str(uuid.uuid4()),
                                            "device_id": device["id"],
                                            "device_name": device["name"],
                                            "severity": "high",
                                            "status": "active",
                                            "metric_name": f"spanning_tree_{spanning_tree_error['instance_id']}_errors",
                                            "title": f"Spanning Tree Instance {spanning_tree_error['instance_id']} Errors",
                                            "description": f"Spanning Tree Instance {spanning_tree_error['instance_id']} has {spanning_tree_error.get('error_count')} errors.",
                                            "created_at": datetime.now(timezone.utc).isoformat()
                                        })

                            storage_controller_status = metrics.get("storage_controller_status", storage_controller_status)
                            for ctrl_status in metrics.get("storage_controllers", []):
                                if ctrl_status.get("status") != "operational":
                                    existing = await db.alerts.find_one({"device_id": device["id"],
                                                                         "metric_name": f"storage_controller_{ctrl_status['controller_name']}",
                                                                         "status": "active"})
                                    if not existing:
                                        await db.alerts.insert_one({
                                            "id": str(uuid.uuid4()),
                                            "device_id": device["id"],
                                            "device_name": device["name"],
                                            "severity": "high",
                                            "status": "active",
                                            "metric_name": f"storage_controller_{ctrl_status['controller_name']}",
                                            "title": f"Storage Controller {ctrl_status['controller_name']} Issue",
                                            "description": f"Storage Controller {ctrl_status['controller_name']} is not operational.",
                                            "created_at": datetime.now(timezone.utc).isoformat()
                                        })

                            raid_array_status = metrics.get("raid_array_status", raid_array_status)
                            for raid_status in metrics.get("raid_arrays", []):
                                if raid_status.get("status") != "optimal":
                                    existing = await db.alerts.find_one({"device_id": device["id"],
                                                                         "metric_name": f"raid_array_{raid_status['array_name']}",
                                                                         "status": "active"})
                                    if not existing:
                                        await db.alerts.insert_one({
                                            "id": str(uuid.uuid4()),
                                            "device_id": device["id"],
                                            "device_name": device["name"],
                                            "severity": "high",
                                            "status": "active",
                                            "metric_name": f"raid_array_{raid_status['array_name']}",
                                            "title": f"RAID Array {raid_status['array_name']} Issue",
                                            "description": f"RAID Array {raid_status['array_name']} is not optimal.",
                                            "created_at": datetime.now(timezone.utc).isoformat()
                                        })

                            raid_array_health = metrics.get("raid_array_health", raid_array_health)
                            for raid_health in metrics.get("raid_arrays", []):
                                if raid_health.get("health_status") != "healthy":
                                    existing = await db.alerts.find_one({"device_id": device["id"],
                                                                         "metric_name": f"raid_array_{raid_health['array_name']}_health",
                                                                         "status": "active"})
                                    if not existing:
                                        await db.alerts.insert_one({
                                            "id": str(uuid.uuid4()),
                                            "device_id": device["id"],
                                            "device_name": device["name"],
                                            "severity": "high",
                                            "status": "active",
                                            "metric_name": f"raid_array_{raid_health['array_name']}_health",
                                            "title": f"RAID Array {raid_health['array_name']} Health Issue",
                                            "description": f"RAID Array {raid_health['array_name']} health status is {raid_health.get('health_status')}.",
                                            "created_at": datetime.now(timezone.utc).isoformat()
                                        })

                            raid_array_failed_disks = metrics.get("raid_array_failed_disks", raid_array_failed_disks)
                            for raid_failed in metrics.get("raid_arrays", []):
                                if raid_failed.get("failed_disks") and raid_failed.get("failed_disks") > 0:
                                    existing = await db.alerts.find_one({"device_id": device["id"],
                                                                         "metric_name": f"raid_array_{raid_failed['array_name']}_failed_disks",
                                                                         "status": "active"})
                                    if not existing:
                                        await db.alerts.insert_one({
                                            "id": str(uuid.uuid4()),
                                            "device_id": device["id"],
                                            "device_name": device["name"],
                                            "severity": "high",
                                            "status": "active",
                                            "metric_name": f"raid_array_{raid_failed['array_name']}_failed_disks",
                                            "title": f"RAID Array {raid_failed['array_name']} Failed Disks",
                                            "description": f"RAID Array {raid_failed['array_name']} has {raid_failed.get('failed_disks')} failed disks.",
                                            "created_at": datetime.now(timezone.utc).isoformat()
                                        })

                            raid_array_degraded_disks = metrics.get("raid_array_degraded_disks", raid_array_degraded_disks)
                            for raid_degraded in metrics.get("raid_arrays", []):
                                if raid_degraded.get("degraded_disks") and raid_degraded.get("degraded_disks") > 0:
                                    existing = await db.alerts.find_one({"device_id": device["id"],
                                                                         "metric_name": f"raid_array_{raid_degraded['array_name']}_degraded_disks",
                                                                         "status": "active"})
                                    if not existing:
                                        await db.alerts.insert_one({
                                            "id": str(uuid.uuid4()),
                                            "device_id": device["id"],
                                            "device_name": device["name"],
                                            "severity": "high",
                                            "status": "active",
                                            "metric_name": f"raid_array_{raid_degraded['array_name']}_degraded_disks",
                                            "title": f"RAID Array {raid_degraded['array_name']} Degraded Disks",
                                            "description": f"RAID Array {raid_degraded['array_name']} has {raid_degraded.get('degraded_disks')} degraded disks.",
                                            "created_at": datetime.now(timezone.utc).isoformat()
                                        })

                            ospf_errors = metrics.get("ospf_errors", ospf_errors)
                            for ospf_error in metrics.get("ospf_neighbors", []):
                                if ospf_error.get("state") != "Full":
                                    existing = await db.alerts.find_one({"device_id": device["id"],
                                                                         "metric_name": f"ospf_neighbor_{ospf_error['neighbor_ip']}",
                                                                         "status": "active"})
                                    if not existing:
                                        alert_id = str(uuid.uuid4())
                                        alert = {
                                            "id": alert_id,
                                            "device_id": device["id"],
                                            "device_name": device["name"],
                                            "severity": "high",
                                            "status": "active",
                                            "metric_name": f"ospf_neighbor_{ospf_error['neighbor_ip']}",
                                            "title": f"OSPF Neighbor {ospf_error['neighbor_ip']} Issue",
                                            "description": f"OSPF Neighbor {ospf_error['neighbor_ip']} is not in Full state.",
                                            "created_at": datetime.now(timezone.utc).isoformat()
                                        }
                                        await db.alerts.insert_one(alert)
                                        
                                        existing_incident = await db.incidents.find_one({
                                            "device_id": device["id"],
                                            "title": f"OSPF Neighbor {ospf_error['neighbor_ip']} Issue",
                                            "status": {"$in": ["open", "in_progress", "awaiting_approval"]}
                                        })
                                        if not existing_incident:
                                            incident = {
                                                "id": str(uuid.uuid4()),
                                                "ticket_number": f"INC-{int(time.time())}",
                                                "title": f"OSPF Neighbor {ospf_error['neighbor_ip']} Issue",
                                                "description": (
                                                    f"OSPF neighbor {ospf_error['neighbor_ip']} on device "
                                                    f"{device['name']} is in '{ospf_error.get('state')}' state "
                                                    f"instead of 'Full'."
                                                ),
                                                "priority": "P1",
                                                "category": "Network",
                                                "status": "in_progress",
                                                "device_id": device["id"],
                                                "affected_devices": [device["id"]],
                                                "related_alerts": [alert_id] if not existing else [],
                                                "created_by": "System Monitor",
                                                "created_at": datetime.now(timezone.utc).isoformat(),
                                                "updated_at": datetime.now(timezone.utc).isoformat()
                                            }
                                            await db.incidents.insert_one(incident)

                        mac_address_table_errors = metrics.get("mac_address_table_errors", mac_address_table_errors)
                        for mac_address_error in metrics.get("mac_address_table", []):
                            if mac_address_error.get("status") != "learned":
                                existing = await db.alerts.find_one({"device_id": device["id"],
                                                                         "metric_name": f"mac_address_{mac_address_error['mac_address']}",
                                                                         "status": "active"})
                                
                                if not existing:
                                        alert_id = str(uuid.uuid4())
                                        alert = {
                                            "id": alert_id,
                                            "device_id": device["id"],
                                            "device_name": device["name"],
                                            "severity": "high",
                                            "status": "active",
                                            "metric_name": f"mac_address_{mac_address_error['mac_address']}",
                                            "title": f"MAC Address {mac_address_error['mac_address']} Issue",
                                            "description": (
                                                f"MAC Address {mac_address_error['mac_address']} on interface "
                                                f"{mac_address_error.get('interface')} is not learned."
                                            ),
                                            "created_at": datetime.now(timezone.utc).isoformat()
                                        }
                                        await db.alerts.insert_one(alert)
                                        
                                        existing_incident = await db.incidents.find_one({
                                            "device_id": device["id"],
                                            "title": f"MAC Address {mac_address_error['mac_address']} Issue",
                                            "status": {"$in": ["open", "in_progress", "awaiting_approval"]}
                                        })
                                        if not existing_incident:
                                            incident = {
                                                "id": str(uuid.uuid4()),
                                                "ticket_number": f"INC-{int(time.time())}",
                                                "title": f"MAC Address {mac_address_error['mac_address']} Issue",
                                                "description": (
                                                    f"MAC Address {mac_address_error['mac_address']} was not learned "
                                                    f"on interface {mac_address_error.get('interface')} "
                                                    f"(VLAN: {mac_address_error.get('vlan')}) "
                                                    f"on device {device['name']}."
                                                ),
                                                "priority": "P2",
                                                "category": "Network",
                                                "status": "in_progress",
                                                "device_id": device["id"],
                                                "affected_devices": [device["id"]],
                                                "related_alerts": [alert_id] if not existing else [],
                                                "created_by": "System Monitor",
                                                "created_at": datetime.now(timezone.utc).isoformat(),
                                                "updated_at": datetime.now(timezone.utc).isoformat()
                                            }
                                            await db.incidents.insert_one(incident)
                            # =====================================================================
                            # ROBUST MULTI-VECTOR ERROR & FAULT SENSING ENGINE - INSERTION DATE 23/7/26
                            # =====================================================================

                            # 1. SWITCHING LOOP DETECTION
                            if metrics.get("switching_loop_detected") or device.get("switching_loop_detected"):
                                logger.warning(f"{device['name']} - Layer 2 Switching Loop Detected!")
                                existing = await db.alerts.find_one({"device_id": device["id"], "metric_name": "switching_loop", "status": "active"})
                                if not existing:
                                    alert_id = str(uuid.uuid4())
                                    await db.alerts.insert_one({
                                        "id": alert_id, "device_id": device["id"], "device_name": device["name"],
                                        "severity": "critical", "status": "active",
                                        "metric_name": "switching_loop",
                                        "title": "Layer 2 Switching Loop Detected",
                                        "description": f"Broadcast storm / switching loop active on device {device['name']}.",
                                        "created_at": datetime.now(timezone.utc).isoformat()
                                    })
                                    await create_metric_incident(db, device, "Layer 2 Switching Loop Detected", "Critical broadcast loop disrupting network stability.", "switching_loop")

                            # 2. SPANNING TREE (STP) ERRORS & BLOCKED PORTS
                            for stp_err in metrics.get("spanning_tree_errors", []):
                                if stp_err.get("error_count", 0) > 0 or stp_err.get("status") in ["blocking", "discarding_anomaly"]:
                                    inst_id = stp_err.get("instance_id", "default")
                                    logger.warning(f"{device['name']} - Spanning Tree Exception on Instance {inst_id}")
                                    existing = await db.alerts.find_one({"device_id": device["id"], "metric_name": f"stp_error_{inst_id}", "status": "active"})
                                    if not existing:
                                        alert_id = str(uuid.uuid4())
                                        await db.alerts.insert_one({
                                            "id": alert_id, "device_id": device["id"], "device_name": device["name"],
                                            "severity": "high", "status": "active",
                                            "metric_name": f"stp_error_{inst_id}",
                                            "title": f"Spanning Tree Anomaly: Instance {inst_id}",
                                            "description": f"STP loop guard or topology change violation on instance {inst_id}.",
                                            "created_at": datetime.now(timezone.utc).isoformat()
                                        })
                                        await create_metric_incident(db, device, f"Spanning Tree Anomaly: Instance {inst_id}", f"STP topology change violation on instance {inst_id}.", f"stp_error_{inst_id}")

                            # 3. INTERFACE LINK FLAPS
                            for iface in metrics.get("interfaces", []):
                                if iface.get("flapping") or iface.get("link_flaps_count", 0) > 3:
                                    ifname = iface["interface"]
                                    logger.warning(f"{device['name']} - Interface {ifname} Flapping")
                                    existing = await db.alerts.find_one({"device_id": device["id"], "metric_name": f"flap_{ifname}", "status": "active"})
                                    if not existing:
                                        alert_id = str(uuid.uuid4())
                                        await db.alerts.insert_one({
                                            "id": alert_id, "device_id": device["id"], "device_name": device["name"],
                                            "severity": "medium", "status": "active",
                                            "metric_name": f"flap_{ifname}",
                                            "title": f"Interface Flapping: {ifname}",
                                            "description": f"Interface {ifname} is experiencing frequent link state changes (flapping).",
                                            "created_at": datetime.now(timezone.utc).isoformat()
                                        })

                            # 4. HARDWARE FAN FAILURES & THERMAL ALARMS
                            fan_status = metrics.get("hardware_fan_status", "operational")
                            fan_rpm = metrics.get("hardware_fan_speed_rpm", 2000)
                            if fan_status != "operational" or (fan_rpm is not None and fan_rpm < 1000):
                                logger.warning(f"{device['name']} - Cooling Fan Failure / Low RPM")
                                existing = await db.alerts.find_one({"device_id": device["id"], "metric_name": "hardware_fan", "status": "active"})
                                if not existing:
                                    alert_id = str(uuid.uuid4())
                                    await db.alerts.insert_one({
                                        "id": alert_id, "device_id": device["id"], "device_name": device["name"],
                                        "severity": "critical", "status": "active",
                                        "metric_name": "hardware_fan",
                                        "title": "Cooling Fan Failure",
                                        "description": f"Fan unit on device {device['name']} is failing or running below safe RPM thresholds ({fan_rpm} RPM).",
                                        "created_at": datetime.now(timezone.utc).isoformat()
                                    })
                                    await create_metric_incident(db, device, "Cooling Fan Failure", f"Thermal risk: Fan speed reduced or failed ({fan_rpm} RPM).", "hardware_fan")

                            # 5. ASYMMETRIC ROUTING DETECTION
                            if metrics.get("asymetric_routing_detected") or device.get("asymmetric_routing_detected"):
                                logger.warning(f"{device['name']} - Asymmetric Routing Path Identified")
                                existing = await db.alerts.find_one({"device_id": device["id"], "metric_name": "asymmetric_routing", "status": "active"})
                                if not existing:
                                    alert_id = str(uuid.uuid4())
                                    await db.alerts.insert_one({
                                        "id": alert_id, "device_id": device["id"], "device_name": device["name"],
                                        "severity": "medium", "status": "active",
                                        "metric_name": "asymmetric_routing",
                                        "title": "Asymmetric Routing Detected",
                                        "description": f"Traffic path asymmetry observed on device {device['name']}, risking stateful firewall drops.",
                                        "created_at": datetime.now(timezone.utc).isoformat()
                                    })

                            # 6. ACCESS LIST (ACL) BLOCK ERRORS & DROPS
                            for acl in metrics.get("access_list_statistics", []):
                                if acl.get("drop_count", 0) > 1000 or acl.get("security_violation"):
                                    acl_name = acl.get("acl_name", "Standard-ACL")
                                    logger.warning(f"{device['name']} - Excessive ACL Drops on {acl_name}")
                                    existing = await db.alerts.find_one({"device_id": device["id"], "metric_name": f"acl_drop_{acl_name}", "status": "active"})
                                    if not existing:
                                        alert_id = str(uuid.uuid4())
                                        await db.alerts.insert_one({
                                            "id": alert_id, "device_id": device["id"], "device_name": device["name"],
                                            "severity": "high", "status": "active",
                                            "metric_name": f"acl_drop_{acl_name}",
                                            "title": f"Access List Drop Spike: {acl_name}",
                                            "description": f"Access list {acl_name} is blocking traffic and accumulating high drop counters.",
                                            "created_at": datetime.now(timezone.utc).isoformat()
                                        })

                            # 7. ROUTING PROTOCOL & NEXT-HOP ERRORS (OSPF, BGP, Static)
                            for proto_err in metrics.get("routing_protocol_neighbors", []):
                                if proto_err.get("state") not in ["Full", "Established", "Up"]:
                                    nbr_ip = proto_err.get("neighbor_ip", "Unknown")
                                    proto = proto_err.get("protocol", "Routing")
                                    logger.warning(f"{device['name']} - {proto} Adjacency Down with {nbr_ip}")
                                    existing = await db.alerts.find_one({"device_id": device["id"], "metric_name": f"routing_adj_{nbr_ip}", "status": "active"})
                                    if not existing:
                                        alert_id = str(uuid.uuid4())
                                        await db.alerts.insert_one({
                                            "id": alert_id, "device_id": device["id"], "device_name": device["name"],
                                            "severity": "critical", "status": "active",
                                            "metric_name": f"routing_adj_{nbr_ip}",
                                            "title": f"{proto} Adjacency Failure: {nbr_ip}",
                                            "description": f"{proto} neighbor session with {nbr_ip} dropped to state '{proto_err.get('state')}'.",
                                            "created_at": datetime.now(timezone.utc).isoformat()
                                        })
                                        await create_metric_incident(db, device, f"{proto} Adjacency Failure: {nbr_ip}", f"Routing protocol breakdown with neighbor {nbr_ip}.", f"routing_adj_{nbr_ip}")

                            metric_record = {
                                "id": str(uuid.uuid4()),   # modified till up time hours on 27-07-26 for performance page
                                "device_id": device["id"],
                                "device_name": device.get("name", "Unknown"),
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "cpu_usage": float(metrics.get("cpu_usage", 0.0)),
                                "memory_usage": float(metrics.get("memory_usage", 0.0)),
                                "disk_usage": float(metrics.get("disk_usage", 0.0)),
                                "bandwidth_in": float(metrics.get("bandwidth_in", 0.0)),
                                "bandwidth_out": float(metrics.get("bandwidth_out", 0.0)),
                                "latency_ms": float(metrics.get("latency_ms", 0.0)),
                                "packet_loss": float(metrics.get("packet_loss", 0.0)),
                                "uptime_hours": int(metrics.get("uptime_hours", 0)),
                                "link_status": link_status,
                                "interfaces": interfaces,
                                "routing_table": routing_table,
                                "mac_address": mac_address,
                                "stp_status": stp_status,
                                "switching_loop_detected": switching_loop_detected,
                                "hardware_memory_ecc_warnings": hardware_memory_ecc_warnings,
                                "hardware_memory_ecc_errors": hardware_memory_ecc_errors,
                                "hardware_memory_temperature_celsius": hardware_memory_temperature_celsius,
                                "hardware_memory_health_status": hardware_memory_health_status,
                                "hardware_disk_smart_warnings": hardware_disk_smart_warnings,
                                "hardware_disk_smart_errors": hardware_disk_smart_errors,
                                "hardware_disk_smart_status": hardware_disk_smart_status,
                                "hardware_disk_temperature_celsius": hardware_disk_temperature_celsius,
                                "hardware_disk_health_status": hardware_disk_health_status,
                                "hardware_power_supply_status": hardware_power_supply_status,
                                "hardware_fan_status": hardware_fan_status,
                                "hardware_temperature_celsius": hardware_temperature_celsius,
                                "hardware_health_status": hardware_health_status,
                                "asymetric_routing_detected": asymetric_routing_detected,
                                "asic_status": hardware_asic_status,
                                "battery_status": hardware_battery_status,
                                "motherboard_status": hardware_motherboard_status,
                                "component_status": hardware_component_status,
                                "software_patch_level": software_patch_level,
                                "software_version": software_version,
                                "cache_memory_errors": cache_memory_errors,
                                "cache_memory_status": cache_memory_status,
                                "storage_battery_status": storage_battery_status,
                                "raid_array_failed_disks": raid_array_failed_disks,
                                "raid_array_degraded_disks": raid_array_degraded_disks,
                                "raid_array_health": raid_array_health,
                                "raid_array_status": raid_array_status,
                                "storage_controller_status": storage_controller_status, 
                                "spanning_tree_errors": spanning_tree_errors,
                                "spanning_tree_instances": spanning_tree_instances,
                                "vrfs": vrfs,
                                "vrf_interfaces": vrf_interfaces,
                                "vrf_routing_tables": vrf_routing_tables,
                                "vrf_bgp_neighbors": vrf_bgp_neighbors,
                                "vrf_ospf_neighbors": vrf_ospf_neighbors,
                                "vrf_eigrp_neighbors": vrf_eigrp_neighbors,
                                "vrf_rip_neighbors": vrf_rip_neighbors,
                                "vrf_static_routes": vrf_static_routes,
                                "access_lists": access_lists,
                                "access_list_entries": access_list_entries,
                                "access_list_statistics": access_list_statistics,
                                "route_maps": route_maps,
                                "route_map_entries": route_map_entries,
                                "route_map_statistics": route_map_statistics,
                                "routing_protocols": routing_protocols,
                                "routing_protocol_neighbors": routing_protocol_neighbors,
                                "ospf_errors": ospf_errors,
                                "bgp_errors": bgp_errors,
                                "eigrp_errors": eigrp_errors,
                                "static_route_errors": static_route_errors,
                            }

                            await db.performance_metrics.insert_one(metric_record)

                            await check_metric_threshold(db, device, "cpu_usage", cpu_usage, 80.0, 95.0, "%")
                            await check_metric_threshold(db, device, "memory_usage", memory_usage, 85.0, 95.0, "%")
                            await check_metric_threshold(db, device, "disk_usage", disk_usage, 85.0, 95.0, "%")
                            await check_metric_threshold(db, device, "latency_ms", latency_ms, 150.0, 300.0, "ms")
                            await check_metric_threshold(db, device, "packet_loss", packet_loss, 2.0, 10.0, "%")

                except Exception as e:
                    print(f"Polling failure on {device['name']}: {e}")
                    print(traceback.format_exc())
                    new_status = "offline"

                # Incident lifecycle transitions
                if old_status == "online" and new_status == "offline":
                    logger.info(f"{device['name']} dropped offline.")
                    active_alert = await db.alerts.find_one({
                         "device_id": device["id"],
                         "title": "Device Offline",
                         "status": "active"})
                    alert_id = active_alert["id"] if active_alert else str(uuid.uuid4())
                    if not active_alert:
                        alert = {
                            "id": alert_id,
                            "device_id": device["id"],
                            "device_name": device["name"],
                            "severity": "critical",
                            "status": "active",
                            "title": "Device Offline",
                            "description": f"Device {device['name']} ({device['ip_address']}) is unreachable.",
                            "category": "Availability",
                            "created_at": datetime.now(timezone.utc).isoformat()
                        }
                        await db.alerts.insert_one(alert)
                    await create_offline_incident(device,alert_id) #-- pushed Alert ID

                elif old_status == "offline" and new_status == "online":
                    logger.info(f"{device['name']} restored connectivity lines.")
                    await db.alerts.update_many(
                        {
                            "device_id": device["id"],
                            "title": "Device Offline",
                            "status": "active"
                        },
                        {
                            "$set": {
                                "status": "resolved",
                                "resolved_by": "System Monitor",
                                "resolved_at": datetime.now(timezone.utc).isoformat()
                            }
                        }
                    )
                    await resolve_device_incident(device["id"])

                await db.devices.update_one(
                    {"id": device["id"]},
                    {
                        "$set": {
                            "status": new_status,
                            "cpu_usage": cpu_usage,
                            "memory_usage": memory_usage,
                            "disk_usage": disk_usage,
                            "bandwidth_in": bandwidth_in,
                            "bandwidth_out": bandwidth_out,
                            "latency_ms": latency_ms,
                            "packet_loss": packet_loss,
                            "uptime_hours": uptime_hours,
                            "os_version": os_version,
                            "mac_address": mac_address,
                            "model": model,
                            "hostname": hostname,
                            "serial_number": serial_number,
                            "neighbors": neighbors,
                            "interfaces": interfaces,  # Metric Added 24thJul26
                            "routing_table":routing_table, # Metric Added 24thJul26
                            "mac_address_table":mac_address_table, # Metric Added 24thJul26
                            "asymetric_routing_detected": asymetric_routing_detected,
                            "hardware_health_status": hardware_health_status,
                            "hardware_temperature_celsius": hardware_temperature_celsius,
                            "hardware_fan_status": hardware_fan_status,
                            "hardware_power_supply_status": hardware_power_supply_status,
                            "hardware_disk_health_status": hardware_disk_health_status,
                            "hardware_disk_temperature_celsius": hardware_disk_temperature_celsius,
                            "hardware_disk_smart_status": hardware_disk_smart_status,
                            "hardware_disk_smart_errors": hardware_disk_smart_errors,
                            "hardware_disk_smart_warnings": hardware_disk_smart_warnings,
                            "hardware_memory_health_status": hardware_memory_health_status,
                            "hardware_memory_temperature_celsius": hardware_memory_temperature_celsius,
                            "hardware_memory_ecc_errors": hardware_memory_ecc_errors,
                            "hardware_memory_ecc_warnings": hardware_memory_ecc_warnings,   
                            "stp_status": stp_status,
                            "switching_loop_detected": switching_loop_detected,
                            "packet_drop_rate": packet_drop_rate,
                            "ip_address_conflicts_detected": ipaddress_conflicts_detected,
                            "vtpm_status": vtpm_status,
                            "stp_root_bridge_status": stp_root_bridge_status,
                            "stp_port_roles": stp_port_roles,
                            "stp_port_states": stp_port_states,
                            "stp_port_costs": stp_port_costs,
                            "stp_loopback_interfaces": stp_loopback_interfaces,
                            "disk_io_errors": disk_io_errors,
                            "disk_usage_percentage": disk_usage_percentage,
                            "storage_controller_status": storage_controller_status,
                            "raid_array_status": raid_array_status,
                            "raid_array_health": raid_array_health,
                            "raid_array_degraded_disks": raid_array_degraded_disks,
                            "raid_array_failed_disks": raid_array_failed_disks,
                            "storage_battery_status": storage_battery_status,
                            "cache_memory_status": cache_memory_status,
                            "cache_memory_errors": cache_memory_errors,     
                            "software_version": software_version,
                            "software_patch_level": software_patch_level,
                            "hardware_component_status": hardware_component_status,
                            "hardware_motherboard_status": hardware_motherboard_status,
                            "hardware_battery_status": hardware_battery_status,
                            "hardware_asic_status": hardware_asic_status,   
                            "spanning_tree_errors": spanning_tree_errors,
                            "spanning_tree_instances": spanning_tree_instances,
                            "vrfs": vrfs,
                            "vrf_interfaces": vrf_interfaces,
                            "vrf_routing_tables": vrf_routing_tables,
                            "vrf_bgp_neighbors": vrf_bgp_neighbors,
                            "vrf_ospf_neighbors": vrf_ospf_neighbors,
                            "vrf_eigrp_neighbors": vrf_eigrp_neighbors,
                            "vrf_rip_neighbors": vrf_rip_neighbors,
                            "vrf_static_routes": vrf_static_routes,
                            "access_lists": access_lists,
                            "access_list_entries": access_list_entries,
                            "access_list_statistics": access_list_statistics,
                            "route_maps": route_maps,
                            "route_map_entries": route_map_entries,
                            "route_map_statistics": route_map_statistics,
                            "routing_protocols": routing_protocols,
                            "routing_protocol_neighbors": routing_protocol_neighbors,
                            "ospf_errors": ospf_errors,
                            "bgp_errors": bgp_errors,
                            "eigrp_errors": eigrp_errors,
                            "static_route_errors": static_route_errors,
                            "timestamp": datetime.now()
                        }
                    }
                )

                if old_status != new_status:
                    await save_device_event(device, new_status, cpu_usage, memory_usage)

        except Exception as e:
            print(f"Global Monitor Loop Error Context: {e}")
            print(traceback.format_exc())

        await asyncio.sleep(1)