import os
import asyncio
import logging
from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks
from typing import List
from datetime import datetime, timezone
import uuid

# Assume db is imported from your database configuration
import network_services  # Your SSH execution module

router = APIRouter()
logger = logging.getLogger("upgrade_manager")
TFTP_DIR = "/app/tftpboot"
os.makedirs(TFTP_DIR, exist_ok=True)

# Vendor-Agnostic Upgrade Command Dictionary
UPGRADE_PROFILES = {
    "cisco_ios": {
        "copy_cmd": "copy tftp://{tftp_ip}/{filename} flash:{filename}",
        "boot_cmd": "boot system flash:{filename}",
        "write_cmd": "write memory"
    },
    "cisco_nxos": {
        "copy_cmd": "copy tftp://{tftp_ip}/{filename} bootflash:{filename} vrf management",
        "boot_cmd": "boot nxos bootflash:{filename}",
        "write_cmd": "copy running-config startup-config"
    },
    "cisco_switches": {
        "copy_cmd": "copy tftp://{tftp_ip}/{filename} flash:{filename}",
        "boot_cmd": "boot system flash:{filename}",
        "write_cmd": "write memory"
    },
    "cisco_routers": {
        "copy_cmd": "copy tftp://{tftp_ip}/{filename} flash:{filename}",
        "boot_cmd": "boot system flash:{filename}",
        "write_cmd": "write memory"
    },
    "cisco_ucs_server": {
        "copy_cmd": "scope firmware; download image tftp://{tftp_ip}/{filename}",
        "boot_cmd": "activate firmware {filename}",
        "write_cmd": "copy running-config startup-config"
    },
    "cisco_wlc": {
        "copy_cmd": "transfer upload mode tftp\ntransfer upload serverip {tftp_ip}\ntransfer upload filename {filename}\ntransfer upload start",
        "boot_cmd": "reset system",
        "write_cmd": "save config"
    },
    "aruba_switches": {
        "copy_cmd": "copy tftp flash {tftp_ip} {filename} primary",
        "boot_cmd": "boot system flash primary",
        "write_cmd": "write memory"
    },
    "aruba_wlc": {
        "copy_cmd": "image update tftp://{tftp_ip}/{filename}",
        "boot_cmd": "reload",
        "write_cmd": "write memory"
    },
    "palo_alto": {
        "copy_cmd": "request system software scp import from {tftp_ip} file {filename}",
        "boot_cmd": "request system software install version {filename}",
        "write_cmd": "save config"
    },
    "hpe_server": {
        "copy_cmd": "iLO firmware update via tftp://{tftp_ip}/{filename}",
        "boot_cmd": "hpcommit",
        "write_cmd": "save settings"
    },
    "hpe_storages": {
        "copy_cmd": "update-шина tftp://{tftp_ip}/{filename}",
        "boot_cmd": "restart controller",
        "write_cmd": "commit changes"
    },
    "dell_server": {
        "copy_cmd": "racadm update -g -u {tftp_ip} -f {filename}",
        "boot_cmd": "racadm serveraction powercycle",
        "write_cmd": "racadm racreset"
    },
    "super_micro": {
        "copy_cmd": "ipmitool -I lanplus -H {target_ip} -U {user} -P {pass} hpm update {filename}",
        "boot_cmd": "ipmitool -I lanplus -H {target_ip} -U {user} -P {pass} bmc reset cold",
        "write_cmd": "save"
    },
    "emc_servers": {
        "copy_cmd": "navicli -h {target_ip} updater -install -package {filename}",
        "boot_cmd": "reboot",
        "write_cmd": "commit"
    },
    "emc_storages": {
        "copy_cmd": "uemcli -d {target_ip} -u {user} -p {pass} /sys/softinst load -file {filename}",
        "boot_cmd": "uemcli -d {target_ip} -u {user} -p {pass} /sys/softinst install",
        "write_cmd": "commit"
    },
    "fortinet": {
        "copy_cmd": "execute restore image tftp {filename} {tftp_ip}",
        "boot_cmd": "y",
        "write_cmd": "exec backup config"
    }
}


async def execute_bulk_upgrade(job_id: str, filename: str, target_devices: list, tftp_server_ip: str):
    from server import db

    """Background task to push firmware to all selected devices asynchronously."""
    await db.upgrade_jobs.insert_one({
        "id": job_id,
        "filename": filename,
        "status": "in_progress",
        "start_time": datetime.now(timezone.utc).isoformat(),
        "targets": [{"ip": dev["ip_address"], "status": "pending"} for dev in target_devices]
    })

    for device in target_devices:
        ip = device["ip_address"]
        vendor = device.get("vendor_profile", "cisco_ios") # Default fallback
        profile = UPGRADE_PROFILES.get(vendor, UPGRADE_PROFILES["cisco_ios"])
        
        logger.info(f"[{job_id}] Initiating upgrade for {ip} using {vendor} profile.")
        
        try:
            # 1. Format the commands with the specific file and TFTP IP
            copy_command = profile["copy_cmd"].format(tftp_ip=tftp_server_ip, filename=filename)
            boot_command = profile["boot_cmd"].format(filename=filename)
            
            # 2. Push commands via your existing AsyncSSH execution engine
            # NOTE: File transfers take time. You will need to increase the SSH timeout here.
            await network_services.execute_shell_command(ip, copy_command, timeout=600)
            
            if boot_command:
                await network_services.execute_shell_command(ip, boot_command)
                
            if profile["write_cmd"]:
                await network_services.execute_shell_command(ip, profile["write_cmd"])
                
            # Update DB status
            await db.upgrade_jobs.update_one(
                {"id": job_id, "targets.ip": ip},
                {"$set": {"targets.$.status": "staged_for_reboot"}}
            )
            
        except Exception as e:
            logger.error(f"[{job_id}] Upgrade failed for {ip}: {e}")
            await db.upgrade_jobs.update_one(
                {"id": job_id, "targets.ip": ip},
                {"$set": {"targets.$.status": "failed", "targets.$.error": str(e)}}
            )

@router.post("/api/firmware/upload")
async def upload_firmware_and_upgrade(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    target_ips: str = Form(None),
    vendor_filter: str = Form(None),
    tftp_server_ip: str = Form(...) # The IP of your backend container facing the network
):
    from server import db

    """Receives the OS image and triggers the upgrade workflow."""
    file_path = os.path.join(TFTP_DIR, file.filename)
    
    # Save the file to the local TFTP directory
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
        
    # Build the MongoDB query to find target devices
    query = {}
    if target_ips:
        ip_list = [ip.strip() for ip in target_ips.split(",")]
        query["ip_address"] = {"$in": ip_list}
    if vendor_filter:
        query["vendor_profile"] = vendor_filter
        
    devices = await db.devices.find(query).to_list(100)
    
    if not devices:
        return {"error": "No matching devices found for the specified filters."}
        
    job_id = str(uuid.uuid4())
    
    # Hand off the long-running SSH transfers to a background task
    background_tasks.add_task(execute_bulk_upgrade, job_id, file.filename, devices, tftp_server_ip)
    
    return {"message": "File uploaded. Bulk upgrade job initiated.", "job_id": job_id, "devices_targeted": len(devices)}