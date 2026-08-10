"""
ATECH NOC Commander - Network Services Module
Real-time network discovery, SNMP polling, SSH connections, and cloud integrations
"""

import asyncio
import socket
import struct
import subprocess
import threading
import time
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import json
import logging
import netifaces
import concurrent.futures
import platform

# ===================== VENDOR PROFILES (Extensible, No Hardcodes) =====================

class VendorProfile:
    """Dynamic vendor profile - loaded from DB or defaults with zero hardcoding"""
    def __init__(self, vendor_name: str, vendor_display_name: str, session_type: str, default_model: str, **kwargs):
        self.name = vendor_name.lower().strip()
        self.vendor_display_name = vendor_display_name
        self.session_type = session_type  # "exec" for server commands, "shell" for network interactive prompts
        self.default_model = default_model
        self.commands = kwargs.get('commands', {})
        self.snmp_patterns = kwargs.get('snmp_patterns', {})
        self.cli_patterns = kwargs.get('cli_patterns', {})
        self.device_types = kwargs.get('device_types', [])
        self.config_fetch_timeout = kwargs.get('config_fetch_timeout', 10)

# Seed configurations used if not overridden by the Database
VENDOR_PROFILES = {
    "cisco": VendorProfile(
    "Cisco",
    "Cisco Systems",
    "shell",
    "Cisco Nexus NX-OS",

    commands={
        "terminal_length":"terminal length 0",

        "fetch_shell_commands":[

            # ========= System =========
            ("ver","show version"),
            ("cpu","show system resources","show process cpu"),
            ("mem","show system resources","show memory summary"),

            # ========= Interfaces =========
            ("interfaces","show ip interface brief"),
            ("int","show interface"),

            # ========= Layer 2 =========
            ("mac_table","show mac address-table"),
            ("arp","show ip arp"),
            ("vlans","show vlan brief"),

            # ========= Layer 3 =========
            ("routing","show ip route"),

            # ========= Discovery =========
            ("neighbors","show cdp neighbors detail"),
            ("lldp","show lldp neighbors detail"),

            # ========= Environment =========
            ("environment","show environment"),
            ("inventory","show inventory"),

            # ========= Logs =========
            ("logs","show logging last 50")
        ],

        "fetch_config":"show running-config",

        "save_config":"copy running-config startup-config",

        "exit":"exit"
    },

    snmp_patterns={
        "vendor_keywords":[
            "cisco",
            "nexus",
            "nx-os"
        ],

        "model_regex":r"cisco\s+(\S+)",

        "version_regex":r"NXOS:\s+version\s+([^\s]+)"
    },

    cli_patterns={

        ##################################################################
        # CPU
        ##################################################################

        "cpu_usage":
        r"CPU states\s*:\s*([\d.]+)%\s+user",


        ##################################################################
        # Memory
        ##################################################################

        "mem_total":
        r"Memory usage:\s*(\d+)K total",

        "mem_used":
        r"Memory usage:\s*\d+K total,\s*(\d+)K used",


        ##################################################################
        # Version
        ##################################################################

        "os_version":
        r"NXOS:\s+version\s+([^\s]+)",


        ##################################################################
        # Hostname
        ##################################################################

        "hostname":
        r"Device name:\s*(\S+)",


        ##################################################################
        # Model
        ##################################################################

        "model":
        r"cisco\s+(Nexus\S*.*)",


        ##################################################################
        # Serial
        ##################################################################

        "serial_number":
        r"Processor Board ID\s+(\S+)",


        ##################################################################
        # MAC
        ##################################################################

        "mac_address":
        r"address is\s+([0-9a-fA-F\.]+)",


        ##################################################################
        # Uptime
        ##################################################################

        "uptime":
        r"Kernel uptime is\s*(.+)",


        ##################################################################
        # CDP Neighbors
        ##################################################################

        "neighbors":
        r"Device ID:\s*(.*?)\n.*?IP address:\s*([0-9.]+)",


        ##################################################################
        # Interfaces
        ##################################################################

        "interfaces":
        r"^(\S+)\s+\S+\s+\S+\s+\S+\s+(up|down|administratively down)\s+(up|down)",


        ##################################################################
        # Routes
        ##################################################################

        "routing":
        r"([A-Z])\s+([0-9./]+).*via\s+([0-9.]+)"
    },

    device_types=[
        "router",
        "switch",
        "firewall",
        "cisco ucs",
        "cisco asa"
    ]
),
    "juniper": VendorProfile(
        "Juniper", "Juniper Networks", "shell", "EX-Series Switch",
        commands={
            "terminal_length": "set cli screen-length 0",
            "fetch_shell_commands": [
                ("cpu", "show chassis routing-engine"),
                ("mem", "show chassis memory"),
                ("ver", "show version"),
                ("int", "show interfaces terse"),
                ("neighbors", "show lldp neighbors")
            ],
            "fetch_config": "show configuration | display set",
            "save_config": "commit",
            "exit": "exit"
        },
        snmp_patterns={"vendor_keywords": ["juniper", "junos"], "model_regex": r'model\s+(\S+)', "version_regex": r'junos\s+([^,\s]+)'},
        cli_patterns={
            "cpu_usage": r'Idle\s+(\d+)\s+percent',  # CPU Usage = 100 - Idle
            "mem_usage_pct": r'Memory utilization\s+(\d+)\s+percent',
            "os_version": r'JUNOS Software Release\s+([^,\s\n]+)',
            "model": r'Model:\s+(\S+)',
            "mac_address": r'Local MAC address:\s+([0-9a-fA-F:]+)',
            "hostname": r'Hostname:\s+(\S+)',
            "serial_number": r'Serial number\s+(\S+)',
            "neighbors": r'Local Interface\s+Parent Interface\s+Chassis Id\s+Port info\s+System Name\s*\n\S+\s+\S+\s+(\d+\.\d+\.\d+\.\d+)\s+\S+\s+(\S+)'
        },
        device_types=["router", "switch", "firewall"]
    ),
    "fortinet": VendorProfile(
        "Fortinet", "Fortinet", "shell", "FortiGate Firewall",
        commands={
            "terminal_length": "config system console\nset output standard\nend",
            "fetch_shell_commands": [
                ("cpu", "get system performance status"),
                ("mem", "get system performance status"),
                ("ver", "get system status"),
                ("int", "get system interface physical"),
                ("get", "get system status"),
                ("diagnose", "diagnose hardware deviceinfo nic"),
                ("diagnose", "diagnose sys top"),
                ("diagnose", "diagnose sys memory"),
                ("diagnose", "diagnose sys session list"),
                ("diagnose", "diagnose sys session stat"),
                ("diagnose", "diagnose sys session filter"),
                ("diagnose", "diagnose sys session clear"),
                ("diagnose", "diagnose hardware deviceinfo nic"),
                ("diagnose", "diagnose hardware deviceinfo memory"),
                ("diagnose", "diagnose hardware deviceinfo cpu"),
                ("diagnose", "diagnose hardware deviceinfo fan"),
                ("diagnose", "diagnose hardware deviceinfo temperature"),
                ("diagnose", "diagnose hardware deviceinfo power"),
                ("diagnose", "diagnose hardware deviceinfo voltage"),
                ("diagnose", "diagnose hardware deviceinfo disk"),
                ("diagnose", "diagnose hardware deviceinfo battery"),
                ("diagnose", "diagnose hardware deviceinfo sensor"),
                ("diagnose", "diagnose hardware deviceinfo environment"),
                ("get", "get routing status"),
                ("get", "get router info routing-table all"),
                ("get", "get router info routing-table static"),
                ("get", "get router info routing-table connected"),
                ("get", "get router info routing-table ospf"),
                ("get", "get router info routing-table bgp"),
                ("get", "get router info routing-table rip"),
                ("get", "get router info routing-table isis"),
                ("get", "get router info routing-table eigrp"),
                ("get", "get router info ospf neighbor"),
                ("execute", "execute ping"),
                ("execute", "execute traceroute"),
                ("diagnose", "vpn tunnel list"),
                ("diagnose", "vpn ike gateway list"),
                ("diagnose", "test authentication"),
                ("diagnose", "test vpn ike"),
                ("diagnose", "test vpn ipsec"),
                ("diagnose", "test vpn ssl"),
                ("diagnose", "test vpn l2tp"),
                ("diagnose", "test vpn pptp"),
                ("diagnose", "test vpn gre"),
                ("diagnose", "test vpn ipip"),
                ("diagnose", "test vpn vti"),
                ("diagnose", "test vpn vxlan"),
                ("diagnose", "test vpn wireguard"),
                ("diagnose", "authserver ldap list"),
                ("diagnose", "authserver radius list"),
                ("diagnose", "authserver tacacs list"),
                ( "diagnose", "autoupdate status"),
                ("diagnose", "sys session list")

            ],
            "fetch_config": "show full-configuration",
            "save_config": "execute backup config flash",
            "exit": "exit"
        },
        snmp_patterns={"vendor_keywords": ["fortigate", "cisco"], "model_regex": r'fortigate-(\S+)', "version_regex": r'v(\d+\.\d+\.\d+)'},
        cli_patterns={
            "cpu_usage": r'CPU states:\s*(\d+)% user',
            "mem_total": r'Memory:\s+(\d+)k total',
            "mem_used": r'Memory:\s+\d+k total,\s+(\d+)k used',
            "os_version": r'v([\d.]+)',
            "model": r'Version:\s+(FortiGate-\S+)',
            "uptime": r'Uptime:\s*(.+)',
            "mac_address": r'Permanent\s+MAC\s+address:\s+([0-9a-fA-F:]+)',
            "hostname": r'Hostname:\s+(\S+)',
            "serial_number": r'Serial-Number:\s+(\S+)'
        },
        device_types=["firewall", "switch"]
    ),
    "paloalto": VendorProfile(
        "Palo Alto", "Palo Alto Networks", "shell", "PA-Series Firewall",
        commands={
            "terminal_length": "set cli pager off",
            "fetch_shell_commands": [
                # --- System & Hardware Sanity ---
                ("cpu", "show system resources"),
                ("mem", "show system resources"),
                ("ver", "show system info"),
                ("environment", "show system environment"),
                ("disk_space", "show system disk-space"),
                ("high_availability", "show high-availability state"),
                ("system_logs", "show log system direction equal backward limit 50"),
                
                # --- Interface & Layer 2/3 Status ---
                ("int", "show interface all"),
                ("int_errors", "show interface hardware all"),
                ("arp_table", "show arp all"),
                ("routing_table", "show routing route"),
                ("bgp_summary", "show routing protocol bgp summary"),
                ("ospf_neighbor", "show routing protocol ospf neighbor"),
                
                # --- Data Plane & Session Analytics ---
                ("session_stats", "show session info"),
                ("session_meters", "show session meter"),
                ("active_sessions", "show session all filter state active"),
                ("packet_drops", "show counter global filter category flow delta yes"), # Shows real-time drop counters
                
                # --- Security & Policy Performance ---
                ("rule_hits", "show running security-policy"), # Useful to parse rule usage
                ("vpn_ike_peers", "show vpn ike-sa detail"),
                ("vpn_ipsec_tunnels", "show vpn tunnel"),
                ("license_status", "request license info")
            ],
            "fetch_config": "show config running",
            "save_config": "commit",
            "exit": "exit"
        },
        snmp_patterns={"vendor_keywords": ["palo alto", "pan-os"], "model_regex": r'PA-', "version_regex": r'pan-os\s+(\S+)'},
        cli_patterns={
            "cpu_usage": r'cpu\(s\):\s+(\d+\.\d+)%\s*us',
            "mem_usage_pct": r'Mem:\s+\d+k\s+total,\s+(\d+)k\s+used',
            "os_version": r'sw-version:\s+(\S+)',
            "model": r'model:\s+(\S+)',
            "mac_address": r'Mac\s+address\s+([0-9a-fA-F:]+)',
            "hostname": r'hostname:\s+(\S+)',
            "serial_number": r'serial:\s+(\S+)',
            # --- Added Regex Patterns for AI Parsing ---
            "ha_state": r'State:\s+(\S+)',
            "session_count": r'Number of allocated sessions:\s+(\d+)',
            "throughput": r'Total throughput:\s+(\d+)\s+kbps',
            "disk_root_util": r'/dev/sda\d+\s+\d+\s+\d+\s+(\d+)%\s+/'
        },
        device_types=["firewall"]
    ),
    "dell_idrac": VendorProfile(
        "Dell", "Dell Technologies", "shell", "PowerEdge Server (iDRAC)",
        commands={
            "terminal_length": "set iwrap 0", # Disables pagination wrapping in iDRAC CLI
            "fetch_shell_commands": [
                # --- System & Hardware Sanity ---
                ("sys_info", "racadm serverinfo"),
                ("health_status", "racadm getsysinfo"),
                ("hardware_inventory", "racadm hwinventory"),
                ("sel_logs", "racadm lclog view"), # Lifecycle/System Event Log (SEL) - critical for failures
                
                # --- Power & Environment ---
                ("power_status", "racadm serveraction powerstatus"),
                ("power_consumption", "racadm getssninfo"),
                ("temps_and_fans", "racadm getsensorinfo"), # Reads RPMs, ambient, and CPU temperatures
                ("power_supplies", "racadm getpwrsupplies"),
                
                # --- Storage & RAID Diagnostics ---
                ("raid_controllers", "racadm storage get controllers"),
                ("physical_disks", "racadm storage get pdisks"),
                ("logical_disks", "racadm storage get vdisks"),
                
                # --- Network & Management Interface ---
                ("idrac_network", "racadm getniccfg"),
                ("mac_addresses", "racadm getmacaddress")
            ],
            "fetch_config": "racadm getconfig -g cfgLanNetworking", # Fetches base management config
            "save_config": "racadm racreset soft", # Reboots management plane to apply pending changes safely
            "exit": "exit"
        },
        snmp_patterns={"vendor_keywords": ["dell", "idrac", "poweredge"], "model_regex": r'PowerEdge\s+(\S+)', "version_regex": r'iDRAC\s+(\S+)'},
        cli_patterns={
            "cpu_usage": r'CPU\s+Usage\s*:\s*(\d+)%', # Dependent on OS-to-iDRAC pass-through configuration
            "os_version": r'OS\s+Name\s*:\s*(.*)', 
            "model": r'System\s+Model\s*:\s*(.*)',
            "mac_address": r'NIC\s+Ethernet\s+Port\s+\d+\s+MAC\s+Address\s*=\s*([0-9a-fA-F:]+)',
            "hostname": r'DNS\s+RAC\s+Name\s*:\s*(\S+)',
            "serial_number": r'Service\s+Tag\s*:\s*(\S+)',
            # --- Added Regex Patterns for AI Parsing ---
            "power_state": r'Server\s+Power\s+State\s*:\s*(\S+)',
            "overall_health": r'RollupStatus\s*=\s*(\S+)', # Returns 'OK', 'Critical', or 'Warning'
            "psu_status": r'Status\s*=\s*(\S+)'
        },
        device_types=["server"]
    ),  
        "hpe_3par": VendorProfile(
        "HPE", "Hewlett Packard Enterprise", "shell", "3PAR StoreServ Storage",
        commands={
            "terminal_length": "setclienv rows 0", # Disables paging on the 3PAR CLI session
            "fetch_shell_commands": [
                # --- System Hardware & Cluster Sanity ---
                ("sys_info", "showsys"), # System name, serial number, total capacity, model
                ("node_health", "shownode -d"), # Status of internal controller nodes, CPU, and memory
                ("hardware_env", "showenv"), # Power supplies, fans, temperatures, and battery module (PCM/BBU) health
                ("system_alerts", "showalert"), # Active system alerts requiring immediate attention
                ("event_log", "showeventlog -d -m 50"), # Captures last 50 diagnostic events backwards
                
                # --- Physical and Logical Storage Health ---
                ("physical_disks", "showpd -state"), # Checks for degraded, failed, or initializing physical disks
                ("disk_errors", "showpd -e"), # Displays hardware-level read/write error counters on loops
                ("ld_status", "showld -d"), # Checks status of logical disks underlying the volume structures
                ("cpg_health", "showcpg -d"), # Evaluates allocation states of Common Provisioning Groups
                
                # --- Virtual Volumes & Provisioning ---
                ("vv_status", "showvv -d"), # Verifies state of Virtual Volumes (Online, Degraded, Stale)
                ("vv_alerts", "showvv -alert"), # Flags volumes that have hit space thresholds or limits
                
                # --- San / Host Connectivity & Port Diagnostics ---
                ("fc_iscsi_ports", "showport -d"), # Link state, SFP tx/rx power, speed, and protocol for host/disk ports
                ("host_visibility", "showhost -d"), # Verifies WWN/iSCSI paths and logging states of attached servers
                ("vlun_mappings", "showvlun"), # Confirms active active/optimized paths exposed to hosts
                
                # --- Performance Monitoring ---
                ("port_performance", "statport -iter 1"), # Real-time bandwidth and IOPS per frontend/backend port
                ("node_performance", "statcpu -iter 1") # Detailed CPU usage broken down per controller node
            ],
            "fetch_config": "showconfig", # Dumps current system configuration rules
            "save_config": "setsys -list", # 3PAR commits changes automatically, but checking systems vars serves as a placeholder
            "exit": "exit"
        },
        snmp_patterns={"vendor_keywords": ["3par", "storeserv", "hpe 3par"], "model_regex": r'3PAR\s+(\S+)', "version_regex": r'Release\s+(\S+)'},
        cli_patterns={
            "cpu_usage": r'node\s+\d+\s+avg\s+(\d+)%', # Parsed from statcpu
            "os_version": r'System\s+version:\s+(\S+)',
            "model": r'Model:\s+(.*)',
            "mac_address": r'MAC\s+address\s+([0-9a-fA-F:]+)',
            "hostname": r'System\s+name:\s+(\S+)',
            "serial_number": r'System\s+serial\s+number:\s+(\S+)',
            # --- Added Regex Patterns for AI Parsing ---
            "node_status": r'Node\s+\d+\s+(\S+)', # Checks if active/failed
            "pd_fail_count": r'(\d+)\s+failed', # Looks for physical disk failures
            "alert_count": r'(\d+)\s+active alerts'
        },
        device_types=["storage"]
    ),
    "dell_emc_vmax": VendorProfile(
        "Dell EMC", "Dell Technologies", "shell", "VMAX / PowerMax Storage",
        commands={
            "terminal_length": "symcli -noprompt", # Bypasses interactive confirmation prompts
            "fetch_shell_commands": [
                # --- System Discovery & Array Sanity ---
                ("array_list", "symcfg list"), # Discovers all attached Symmetrix IDs (SIDs) and status
                ("sys_info", "symcfg list -v"), # Detailed global environmentals, cache sizes, and model type
                ("director_health", "symcfg list -dir all"), # Checks CPU, memory, and online status of all Front-End/Back-End Directors
                ("disk_health", "symdisk list -failed"), # Instantly returns any failed physical disk drives across loops
                ("environmental_status", "symcfg list -envstatus"), # Queries power supply, standby power supplies (SPS/BBU), and fan states
                
                # --- Storage Provisioning & SRP Pools ---
                ("srp_health", "symcfg list -srp"), # Evaluates Storage Resource Pool health, subscribed capacity, and free space
                ("thin_pools", "symcfg list -pool -thin"), # Checks thin provisioning pool allocation states
                
                # --- Front-End Connectivity & Storage Masking ---
                ("fa_ports", "symcfg list -connections"), # Displays FC/iSCSI target ports, speeds, and link states
                ("masking_views", "symaccess list view"), # Validates host to Storage Group mappings (Masking Views)
                ("login_history", "symaccess list logins"), # Checks active WWN/iSCSI logins from fabric switches to the array
                
                # --- Data Replication & Protection ---
                ("srdf_status", "symrdf list"), # Monitors SRDF remote replication state (Synchronous/Asynchronous health)
                ("snapvx_status", "symsnapvx list"), # Checks local snapshot states and generation tracks
                
                # --- Real-Time Performance Triggers ---
                ("array_perf", "symstat -type array -interval 1 -count 1"), # Captures current IOPS, throughput, and cache hit ratios
                ("director_perf", "symstat -type dir -interval 1 -count 1") # Checks for imbalanced workload over individual director engines
            ],
            "fetch_config": "symcfg export -f -", # Dumps physical topology database (Symmetrix Configuration File)
            "save_config": "symconfigure verify", # Place-holder behavior for checking configuration change scripts
            "exit": "exit"
        },
        snmp_patterns={"vendor_keywords": ["symmetrix", "vmax", "powermax", "emc"], "model_regex": r'(VMAX|PowerMax)\s+(\d+)', "version_regex": r'Microcode\s+Version\s+(\S+)'},
        cli_patterns={
            "cpu_usage": r'Director\s+CPU\s+Busy\s*:\s*(\d+)%', # Parsed from symstat engine traces
            "os_version": r'Enginuity\s+Version\s*:\s*(\S+)|Solutions\s+Enabler\s+Version\s*:\s*(\S+)',
            "model": r'Symmetrix\s+Model\s*:\s*(.*)',
            "mac_address": r'WWN\s*:\s*([0-9a-fA-F:]+)',
            "hostname": r'Local\s+Host\s+Name\s*:\s*(\S+)',
            "serial_number": r'Symm\s+ID\s*:\s*(\d+)', # Grabs the crucial 12-digit Symmetrix ID
            # --- Added Regex Patterns for AI Parsing ---
            "dir_status": r'(Online|Offline|Failed|Dead)', # Tracks individual director card health
            "srp_free_pct": r'Free\s+SRP\s+Capacity\s+\(%崩\)\s*:\s*(\d+)',
            "failed_disks_count": r'Total\s+number\s+of\s+failed\s+disks\s*:\s*(\d+)'
        },
        device_types=["storage"]

    ),
    "emc_vnx": VendorProfile(
        "EMC", "Dell Technologies", "shell", "VNX Hybrid Storage",
        commands={
            "terminal_length": "naviseccli -noprompt", # Bypasses pagination and interactive confirmations
            "fetch_shell_commands": [
                # --- Block Storage Architecture & SP Sanity ---
                ("sp_health", "naviseccli -h {target_ip} faults -list"), # Fast-path health assessment for hardware components
                ("sys_info", "naviseccli -h {target_ip} getagent"), # Retrieves firmware (FLARE) OE versions, serial numbers, and SP status
                ("hardware_env", "naviseccli -h {target_ip} environment -list"), # Queries power supplies, SPS (Battery modules), and fan speeds
                ("disk_health", "naviseccli -h {target_ip} getdisk -state -failed"), # Targets and isolated failed physical disk drives
                ("crst_logs", "naviseccli -h {target_ip} getlog -20"), # Ingests last 20 SP Event Log messages for error parsing
                
                # --- Storage Pools, LUNs & Cache Status ---
                ("storage_pools", "naviseccli -h {target_ip} storagepool -list"), # Checks pool status (OK, Degraded, Full) and consumption tiers
                ("lun_status", "naviseccli -h {target_ip} lun -list -status"), # Displays degraded LUN states or unowned LUN configurations
                ("cache_state", "naviseccli -h {target_ip} cache -sp -status"), # Verifies if Write Cache is disabled (often triggered by SPS battery faults)
                
                # --- Connectivity, Masking & Registration ---
                ("hba_logins", "naviseccli -h {target_ip} port -list"), # Lists target FC/iSCSI ports, link states, and speed parameters
                ("storage_groups", "naviseccli -h {target_ip} storagegroup -list"), # Evaluates host masking allocations and connectivity maps
                ("initiator_records", "naviseccli -h {target_ip} connection -list"), # Verifies host HBA initiator registration states on SPA/SPB
                
                # --- File / NAS Components (Executed if Unified/File config exists via Control Station) ---
                ("nas_blade_health", "nas_checkup"), # Runs the comprehensive integrated diagnostic suite on File Datamovers
                ("datamover_status", "server_status ALL"), # Monitors state of active/standby File blades (Data Movers)
                ("nas_fs_status", "nas_fs -info -all") # Analyzes File System states, mount errors, and capacity thresholds
            ],
            "fetch_config": "naviseccli -h {target_ip} arrayconfig -capture -output -", # Generates an XML/Text profile dump of the allocation matrix
            "save_config": "naviseccli -h {target_ip} getresume", # Placeholder safely querying FRU status strings without committing state changes
            "exit": "exit"
        },
        snmp_patterns={"vendor_keywords": ["vnx", "clariion", "celerra", "emc vnx"], "model_regex": r'VNX(\d+)', "version_regex": r'Revision\s+(\S+)'},
        cli_patterns={
            "cpu_usage": r'SP\s+CPU\s+Utilization\s*:\s*(\d+)%', # Retrieved from tracking performance profiling
            "os_version": r'FLARE-Operating-Environment\s*:\s*(\S+)|NAS\s+Software\s+Version\s*:\s*(\S+)',
            "model": r'Model\s*:\s*(.*)',
            "mac_address": r'HBA\s+WWN\s*:\s*([0-9a-fA-F:]+)',
            "hostname": r'Server\s+Name\s*:\s*(\S+)',
            "serial_number": r'Serial\s+Number\s*:\s*(\S+)', # Parses the enclosure-level array serial number
            # --- Added Regex Patterns for AI Parsing ---
            "sp_fault_state": r'Faulted\s*:\s*([yY]es|[nN]o)', # Directly captures boolean flag of subsystem component degradation
            "write_cache_status": r'Write\s+Cache\s+State\s*:\s*(\S+)', # Flags if write-cache dropped down to "Disabled"
            "failed_disk_count": r'Total\s+Failed\s+Disks\s*:\s*(\d+)'
        },
        device_types=["storage"]
    ),
"supermicro_ipmi": VendorProfile(
        "Supermicro", "Supermicro Computer Inc.", "shell", "SuperServer (IPMI/BMC)",
        commands={
            "terminal_length": "", # ipmitool does not natively page output blocks
            "fetch_shell_commands": [
                # --- System Discovery & Global Health ---
                ("sys_info", "ipmitool fru print"), # Dumps Field Replaceable Unit data (chassis, board, asset tags, serials)
                ("bmc_info", "ipmitool bmc info"), # Retrieves BMC firmware revision, IPMI version, and device ID
                ("chassis_status", "ipmitool chassis status"), # Verifies physical power control state, faults, and button locks
                ("sel_logs", "ipmitool sel elist"), # Detailed System Event Log (SEL) - parses critical hardware alerts
                ("sel_info", "ipmitool sel info"), # Tracks log utilization to ensure the AI clears it before overflow
                
                # --- Sensors & Environmentals ---
                ("sensor_dump", "ipmitool sensor list"), # Comprehensive list of real-time voltage, fan RPM, and thermal readouts
                ("sdr_status", "ipmitool sdr elist compact"), # Aggregates Sensor Data Records with status flags (ok, ns, cr)
                ("fan_mode", "ipmitool raw 0x30 0x70 0x66 0x00"), # Supermicro OEM Raw command: queries the fan speed mode
                
                # --- Power Control & Monitoring ---
                ("power_status", "ipmitool chassis power status"), # Reports binary state (Power is on / Power is off)
                ("pwr_consumption", "ipmitool dcmi power reading"), # Retrieves real-time and historical wattage consumption metrics
                
                # --- Network Configuration ---
                ("lan_config", "ipmitool lan print 1"), # Displays dedicated BMC management IP, subnet, MAC, and VLAN states
                ("user_list", "ipmitool user list 1") # Checks local IPMI user permissions to flag potential access privilege issues
            ],
            "fetch_config": "ipmitool lan print 1", # Standard fall-back configuration map
            "save_config": "ipmitool bmc reset cold", # Safe non-destructive operation to restart hung management controllers
            "exit": "exit"
        },
        snmp_patterns={"vendor_keywords": ["supermicro", "smc"], "model_regex": r'SYS-(\S+)', "version_regex": r'IPMI\s+Firmware\s+Revision\s+(\S+)'},
        cli_patterns={
            "cpu_usage": r'CPU\s+Temp\d+\s*\|\s*(\d+)\s*\|\s*degrees\s+C', # Monitored via baseline CPU edge temps instead of OS metrics
            "os_version": r'Firmware\s+Revision\s*:\s*(\S+)', # Maps to BMC OS
            "model": r'Product\s+Name\s*:\s*(.*)', # Extracted via FRU print
            "mac_address": r'MAC\s+Address\s*:\s*([0-9a-fA-F:]+)',
            "hostname": r'Core\s+BMC\s+Name\s*:\s*(\S+)',
            "serial_number": r'Product\s+Serial\s*:\s*(\S+)', # Grabs system motherboard chassis serial identifier
            # --- Added Regex Patterns for AI Parsing ---
            "chassis_fault": r'Chassis\s+Fault\s*:\s*([tT]rue|[fF]alse)',
            "sel_critical_flag": r'\|\s*Critical\s*\|\s*(\d+)\s*\|', # Counts critical events in SEL

        },
        device_types=["server"]
    ),  

    "huawei_ibmc": VendorProfile(
        "Huawei", "Huawei Technologies Co., Ltd.", "shell", "FusionServer (iBMC)",
        commands={
            "terminal_length": "", # iBMC CLI automatically bypasses paging for non-interactive sessions
            "fetch_shell_commands": [
                # --- System Discovery & Global Health ---
                ("sys_info", "ipmcget -d productinfo"), # Dumps server name, model, serial number, and asset tags
                ("bmc_info", "ipmcget -d version"), # Retrieves iBMC firmware version, BIOS version, and CPLD state
                ("health_status", "ipmcget -d health"), # Fast-path status query (returns overall system health)
                ("active_alarms", "ipmcget -d alarms"), # Instantly extracts all unacknowledged active hardware faults
                ("sel_logs", "ipmcget -d sel -v list"), # Comprehensive System Event Log (SEL) dump for historical failures
                
                # --- Power & Environmentals ---
                ("power_status", "ipmcget -d powerstatus"), # Verifies server power state (ON/OFF)
                ("pwr_consumption", "ipmcget -d powerinfo"), # Tracks current wattage consumption and power limits
                ("temps_and_fans", "ipmcget -d sensor"), # High-density sensor dump (temperatures, voltages, fan RPMs)
                ("psu_status", "ipmcget -d psuinfo"), # Queries individual power supply states and redundancy flags
                
                # --- Storage & Components ---
                ("hdd_status", "ipmcget -d hddinfo"), # Inspects local hard drive health and physical slot alignment
                ("mac_addresses", "ipmcget -d macaddr"), # Queries MAC addresses of onboard LOM/NIC ports
                ("cpu_mem_status", "ipmcget -d componentinfo") # Evaluates raw visibility status of DIMMs and CPUs
            ],
            "fetch_config": "ipmcget -d networkcfg", # Gathers iBMC management plane network rules
            "save_config": "ipmcrest -d bmc", # Reboots the management controller safely without dropping host server power
            "exit": "exit"
        },
        snmp_patterns={"vendor_keywords": ["huawei", "ibmc", "imana", "fusionserver"], "model_regex": r'(FusionServer|RH\d+)\s+(\S+)', "version_regex": r'iBMC\s+Version\s+(\S+)'},
        cli_patterns={
            "cpu_usage": r'CPU\d+\s+Temp\s*\|\s*(\d+)\s*\|\s*degrees\s+C', # Monitored via direct hardware junction temperatures
            "os_version": r'iBMC\s+Firmware\s+Version\s*:\s*(\S+)',
            "model": r'Product\s+Name\s*:\s*(.*)',
            "mac_address": r'MAC\s+Address\s*:\s*([0-9a-fA-F:]+)',
            "hostname": r'Host\s+Name\s*:\s*(\S+)',
            "serial_number": r'Product\s+Serial\s+Number\s*:\s*(\S+)', # Maps to the chassis product serial string
            # --- Added Regex Patterns for AI Parsing ---
            "system_health": r'Health\s+Status\s*:\s*(\S+)', # Typically yields 'OK', 'Minor', 'Major', or 'Critical'
            "alarm_criticality": r'\|\s*(Critical|Major)\s*\|', # Allows the AI to spot high-priority failure steps
            "total_power": r'Current\s+Power\s*:\s*(\d+)\s*Watts'
        },
        device_types=["server"]
    ),
    "huawei_oceanstor": VendorProfile(
        "Huawei", "Huawei Technologies Co., Ltd.", "shell", "OceanStor / Dorado Storage",
        commands={
            "terminal_length": "change cli refresh off", # Disables pagination and continuous output scrolling
            "fetch_shell_commands": [
                # --- System & Enclosure Sanity ---
                ("sys_info", "show system general"), # System name, serial number, health, and running status
                ("controller_health", "show controller general"), # State, CPU, memory usage, and operational status of each controller node
                ("hardware_env", "show enclosure general"), # Real-time state of fans, power supplies, BBUs, and temps
                ("active_alarms", "show alarm active"), # Instantly yields all current active faults on the array
                ("system_time", "show system time"), # Crucial for aligning event logs with external log aggregators
                
                # --- Storage Layer Disks & Pools ---
                ("disk_domains", "show disk_domain general"), # Checks the integrity of disk groups and free capacity
                ("storage_pools", "show storage_pool general"), # Displays health status, encryption, and thin provisioning tiers
                ("disk_health", "show disk general"), # Scans for failed, degraded, or isolating physical disk drives
                
                # --- Block Provisioning & Virtual Volumes ---
                ("lun_health", "show lun general"), # Status (Online/Offline/Fault), mapping indicators, and sizes of LUNs
                ("lun_group", "show lun_group general"), # Checks structural grouping assignments
                ("snapshot_status", "show snapshot general"), # Monitors storage snapshots and rollback states
                
                # --- Host Connectivity & SAN Ports ---
                ("host_ports", "show port fibre_channel"), # For FC SAN: displays link speed, WWN status, and transceiver health
                ("iscsi_ports", "show port iscsi"), # For IP SAN: status, link speed, IP configurations, and MTU bounds
                ("host_logins", "show host general"), # Confirms active host OS mapping paths and software initiators
                ("mapping_views", "show mapping_view general"), # Verifies logic structures linking hosts to LUN groups
                
                # --- Performance Telemetry ---
                ("iop_performance", "show performance system"), # Instantly polls global system IOPS, throughput, and latency
                ("controller_perf", "show performance controller controller_id=0A") # Measures metrics across explicit paths
            ],
            "fetch_config": "show configuration general", # Dumps system logic rules and metadata topology maps
            "save_config": "save configuration", # Commits pending internal volatile modifications safely to storage
            "exit": "exit"
        },
        snmp_patterns={"vendor_keywords": ["oceanstor", "dorado", "huawei storage"], "model_regex": r'(Dorado|OceanStor)\s+(\S+)', "version_regex": r'V\d+R\d+C\d+'},
        cli_patterns={
            "cpu_usage": r'CPU\s+Usage\s*\(%\)\s*:\s*(\d+)', # Parsed out via performance outputs
            "os_version": r'Product\s+Version\s*:\s*(\S+)',
            "model": r'Product\s+Model\s*:\s*(.*)',
            "mac_address": r'MAC\s+Address\s*:\s*([0-9a-fA-F:]+)',
            "hostname": r'System\s+Name\s*:\s*(\S+)',
            "serial_number": r'Product\s+Serial\s+Number\s*:\s*(\S+)', # Grabs the core array SN
            # --- Added Regex Patterns for AI Parsing ---
            "health_status": r'Health\s+Status\s*:\s*(\S+)', # Returns clean values like 'Normal' or 'Fault'
            "running_status": r'Running\s+Status\s*:\s*(\S+)', # Returns values like 'Online', 'Offline', or 'Degraded'
            "active_faults": r'Total\s+Alarms\s*:\s*(\d+)'
        },
        device_types=["storage"]
    ),
    "hpe_ilo": VendorProfile(
        "HPE", "Hewlett Packard Enterprise", "shell", "ProLiant Server (iLO)",
        commands={
            "terminal_length": "set /system1oem/hpilo1 session_timeout=0", # Bypasses session disconnects during long diagnostic cycles
            "fetch_shell_commands": [
                # --- System Discovery & Global Sanity ---
                ("sys_info", "show /system1"), # Retrieves system product name, serial number, and UUID
                ("ilo_info", "show /map1"), # Returns iLO firmware revisions, MAC, and network configuration
                ("overall_health", "show /system1/oem/hpilo/healthsummary"), # Fast-path triage: gives the global status of all subcomponents
                ("sel_logs", "show /system1/log1/records"), # Ingests Integrated Management Log (IML) — HPE's crucial hardware event logs
                
                # --- Power & Environmentals ---
                ("power_status", "show /system1 power_state"), # Confirms physical power state (On/Off)
                ("power_supplies", "show /system1/powersupply*"), # Checks input AC, redundancy state, and status of all PSUs
                ("temps_and_fans", "show /system1/sensor*"), # Extracts real-time RPMs, ambient, and structural component temperatures
                ("power_consumption", "show /system1/oem/hpilo/power_summary"), # Monitors current and peak wattage consumption
                
                # --- Storage & Compute Fabric ---
                ("storage_health", "show /system1/oem/hpilo/storage*"), # Scans Smart Array controllers and logical/physical drive array maps
                ("cpu_status", "show /system1/processor*"), # Evaluates CPU health, stepping, and configuration status
                ("memory_status", "show /system1/memory*"), # Analyzes DIMM health, speed, and isolates locations of ECC/advanced faults
                ("network_adapters", "show /system1/network*") # Maps physical LOM/FlexibleLOM/PCIe NIC ports and status
            ],
            "fetch_config": "show /system1/oem/hpilo/networksettings", # Gathers iLO management plane network configurations
            "save_config": "reset /system1/oem/hpilo1", # Safe non-destructive command to reboot a hung iLO management controller without affecting the running host OS
            "exit": "exit"
        },
        snmp_patterns={"vendor_keywords": ["hpe", "hp", "ilo", "proliant"], "model_regex": r'ProLiant\s+(\S+)', "version_regex": r'iLO\s+(\d+)'},
        cli_patterns={
            "cpu_usage": r'Current\s+Reading\s*:\s*(\d+)\s*C', # Monitored via direct CPU hardware junction temperatures
            "os_version": r'iLO\s+Firmware\s+Version\s*:\s*(\S+)',
            "model": r'Product\s+Name\s*:\s*(.*)',
            "mac_address": r'MAC\s+Address\s*:\s*([0-9a-fA-F:]+)',
            "hostname": r'Server\s+Name\s*:\s*(\S+)',
            "serial_number": r'Serial\s+Number\s*:\s*(\S+)', # Maps to the chassis product serial string
            # --- Added Regex Patterns for AI Parsing ---
            "health_status": r'Status\s*=\s*(\S+)', # Typically yields 'OK', 'Degraded', or 'Critical'
            "iml_critical_flag": r'\[CRITICAL\]|\[ACTION REQUIRED\]', # Detects actionable alerts in the IML logs
            "redundancy_state": r'Redundancy\s*:\s*(\S+)' # Captures power or fan redundancy states (e.g., 'Redundant')
        },
        device_types=["server"]
    ),
    "lenovo_thinksystem_storage": VendorProfile(
        "Lenovo", "Lenovo", "shell", "ThinkSystem DM/DE Storage",
        commands={
            "terminal_length": "rows 0", # Disables command-line pagination for automated data ingestion
            "fetch_shell_commands": [
                # --- Cluster & Storage Node Sanity ---
                ("sys_info", "cluster show"), # Checks identity, health, and availability status of the system cluster
                ("node_health", "node run -node * sysconfig -v"), # Detailed hardware overview (slots, controller modules, memory)
                ("hardware_env", "system node environment sensors show"), # Evaluates fan speeds, power supplies, voltages, and temps
                ("active_alerts", "system health alert show"), # Pulls actionable active degraded subsystem alerts 
                ("event_log", "event log show -count 50"), # Captures the last 50 system log occurrences chronologically
                
                # --- Storage Aggregates & Physical Disks ---
                ("aggregates_status", "storage aggregate show -state !online"), # Instantly checks for degraded or failed disk pools
                ("disk_health", "storage disk show -state broken,failed,unusable"), # Isolates and scans for physically bad disk drives
                ("spare_disks", "storage disk show -container-type spare"), # Verifies if pool has active zeroed hot-spares available
                
                # --- Volumes & Logical Structures ---
                ("volume_health", "volume show -state !online"), # Flags if any volumes dropped offline or became stale
                ("volume_efficiency", "volume efficiency show"), # Checks deduplication and compression engine states
                
                # --- SAN/NAS Front-End Connectivity ---
                ("fc_ports", "network fcp adapter show"), # Checks state, WWN profile, and connectivity speeds of FC host cards
                ("iscsi_targets", "iscsi show -interface"), # Verifies network target configurations for IP SAN structures
                ("iscsi_logins", "iscsi session show"), # Confirms host initiator registrations and path configurations
                ("lif_status", "network interface show"), # Monitors active logical interface paths, failover status, and home nodes
                
                # --- High Availability & Failover ---
                ("ha_status", "storage failover show"), # Validates cluster partner node takeover availability (failover capability)
                
                # --- DE Series Alternative Safe Fallbacks (SAN OS) ---
                ("de_array_health", "show storageArray healthStatus;"), # Fallback block parsed if executing scripts on a DE platform
                ("de_profile", "show storageArray profile;") # Full internal structural dump for DE SAN OS arrays
            ],
            "fetch_config": "system configuration backup show", # Locates node configuration system files
            "save_config": "system configuration backup create -node * -backup-name AI_Diag_Snap", # Generates an ad-hoc safety backup snapshot
            "exit": "exit"
        },
        snmp_patterns={"vendor_keywords": ["lenovo", "thinksystem", "ontap"], "model_regex": r'(DM\d+|DE\d+)[HFS]', "version_regex": r'(Data\s+Ontap|SAN\s+OS)\s+(\S+)'},
        cli_patterns={
            "cpu_usage": r'CPU\s+utilization\s*:\s*(\d+)%', 
            "os_version": r'Software\s+Version\s*:\s*(\S+)',
            "model": r'System\s+Model\s*:\s*(\S+)',
            "mac_address": r'MAC\s+Address\s*:\s*([0-9a-fA-F:]+)',
            "hostname": r'Cluster\s+Name\s*:\s*(\S+)',
            "serial_number": r'System\s+Serial\s+Number\s*:\s*(\S+)', # Pulls backplane controller chassis tag
            # --- Added Regex Patterns for AI Parsing ---
            "node_status": r'Health\s+Status\s*:\s*(\S+)',
            "failover_possible": r'Takeover\s+Possible\s*:\s*true', # Verifies cluster node partner is safely cross-protected
            "failed_disk_count": r'(\d+)\s+broken'
        },
        device_types=["storage"]
    ),
    "lenovo_xcc": VendorProfile(
        "Lenovo", "Lenovo", "shell", "ThinkSystem Server (XClarity Controller)",
        commands={
            "terminal_length": "set -v columns 0 rows 0", # Disables CLI pagination for seamless automated string ingestion
            "fetch_shell_commands": [
                # --- System Identity & Global Sanity ---
                ("sys_info", "sysinfo"), # Comprehensive system dump: model, machine type, serial number, and UUID
                ("xcc_info", "version"), # Retrieves XCC firmware variants, boot block, and active uEFI code layers
                ("overall_health", "health"), # Fast-path health sweep: summarizes active system warnings or faults
                ("sel_logs", "syslog -fetch 50"), # Ingests last 50 entries from the XCC hardware event log
                
                # --- Power & Environmental Health ---
                ("power_status", "power state"), # Evaluates whether host system power is On, Off, or Resetting
                ("power_supplies", "fuelgauge status"), # Displays power metrics, input line voltage, and PSU health status
                ("temps_and_fans", "temp -list; fan -list"), # Aggregates temperature thresholds and fan RPM percentages
                ("power_history", "fuelgauge allocation"), # Captures current and capped wattage draws
                
                # --- Compute & Memory Arrays ---
                ("cpu_status", "cpu -list"), # Inspects CPU thermal margins, models, and socket population states
                ("memory_status", "dimm -list"), # Maps memory configuration and flags slots reporting PFA (Predictive Failure Analysis)
                
                # --- Storage & PCIE Adapters ---
                ("raid_health", "raid show controllers"), # Diagnoses ThinkSystem RAID adapter configurations and battery health
                ("physical_disks", "raid show drives"), # Lists physical storage states (Online, Failed, Rebuilding)
                ("pcie_inventory", "adapter -list") # Scans inventory of installed PCIe expansion cards and network cards
            ],
            "fetch_config": "ifconfig eth0", # Pulls dedicated XCC management interface configurations
            "save_config": "resetsp", # Safe non-destructive command to reboot the XCC management plane without dropping the host server's workload
            "exit": "exit"
        },
        snmp_patterns={"vendor_keywords": ["lenovo", "xcc", "imm", "thinksystem"], "model_regex": r'SR\d+|ST\d+|SD\d+', "version_regex": r'XCC\s+Firmware\s+Version\s+(\S+)'},
        cli_patterns={
            "cpu_usage": r'CPU\d+\s+Temp\s*:\s*(\d+)\s*C', # Monitored via direct CPU core junction temperatures
            "os_version": r'Firmware\s+Revision\s*:\s*(\S+)', # Maps to the XCC operating engine
            "model": r'Product\s+Name\s*:\s*(.*)', # Scraped from sysinfo
            "mac_address": r'MAC\s+Address\s*:\s*([0-9a-fA-F:]+)',
            "hostname": r'Host\s+Name\s*:\s*(\S+)',
            "serial_number": r'Serial\s+Number\s*:\s*(\S+)', # Maps directly to the Lenovo 7-digit alphanumeric serial identifier
            # --- Added Regex Patterns for AI Parsing ---
            "health_status": r'System\s+Health\s*:\s*(\S+)', # Typically yields 'Normal', 'Warning', or 'Non-Critical'
            "pfa_flag": r'\[PFA\s+Alert\]', # Instantly catches predictive failures in memory or storage elements
            "psu_redundancy": r'Redundancy\s*Status\s*:\s*(\S+)'
        },
        device_types=["server"]
    ),
    "ibm_aix": VendorProfile(
        "IBM", "IBM Corporation", "shell", "Power Systems (AIX OS)",
        commands={
            "terminal_length": "export TERM=vt100; stty rows 0 cols 0 2>/dev/null || true", # Disables terminal paging wrappers in AIX shell
            "fetch_shell_commands": [
                # --- System Environment & Global Sanity ---
                ("sys_info", "uname -Mu"), # Returns the specific hardware Machine Type, Model, and Partition Serial ID
                ("os_level", "oslevel -s"), # Returns exact AIX Service Pack level (e.g., 7300-01-02-2314)
                ("cpu_cnt", "bindprocessor -q"), # Identifies the number of active logical and physical SMT processors available
                ("mem_info", "bootinfo -r"), # Queries the exact physical memory size configured in the system baseline
                
                # --- Hardware Errors & Event Log (Critical Triage) ---
                ("hardware_faults", "errpt -T H -t -s 24h"), # Isolates critical Hardware errors (H) from the last 24 hours
                ("software_faults", "errpt -T S -t -s 24h"), # Isolates Software crashes/core dumps (S) from the last 24 hours
                ("errpt_summary", "errpt | head -n 30"), # High-level chronological overview of system-wide log issues
                
                # --- Logical Volume Manager (LVM) & Storage Health ---
                ("volume_groups", "lsvg"), # Lists all active Volume Groups (e.g., rootvg)
                ("rootvg_health", "lsvg -l rootvg"), # Confirms logical volume status (open/synced vs stale) across operating mirrors
                ("physical_volumes", "lspv"), # Lists physical disks, their PVIDs, and parent Volume Group states
                ("disk_errors", "lsdev -Cc disk"), # Scans operational status (Available/Defined) of all physical disk paths
                
                # --- Network and Device Management ---
                ("network_interfaces", "netstat -in"), # Lists physical and logical adapter configurations, MTUs, and IP mappings
                ("routing_table", "netstat -rn"), # Displays active kernel routing destinations and gate metrics
                ("device_inventory", "lscfg -vp"), # Deep dive Vital Product Data (VPD): lists part numbers and microcode of all parts
                
                # --- Performance and Resource Bottlenecks ---
                ("cpu_mem_top", "vmstat 1 5"), # Captures virtual memory manager stats, runnable kernel threads, and CPU states
                ("io_bottlenecks", "iostat 1 5") # Isolates physical disk busy percentages and throughput delays per path
            ],
            "fetch_config": "cat /etc/rc.net", # Retrieves primary core network configuration maps
            "save_config": "sync; sync", # Flushes filesystem unwritten structural cache blocks safely to physical media
            "exit": "exit"
        },
        snmp_patterns={"vendor_keywords": ["ibm", "aix", "powerpc"], "model_regex": r'IBM,(\S+)', "version_regex": r'AIX\s+(\d+\.\d+)'},
        cli_patterns={
            "cpu_usage": r'\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$\s*$', # Maps us, sy, id, wa from vmstat trailing loops
            "os_version": r'^(\d{4}-\d{2}-\d{2})', # Captures maintenance levels cleanly from oslevel strings
            "model": r'Machine\s+Hardware\s+Name\s*:\s*(.*)|IBM,(\S+)',
            "mac_address": r'Hardware\s+Address\s*:\s*([0-9a-fA-F\.]+)', # Maps AIX dot-notation MAC addresses
            "hostname": r'^(\S+)', # Scraped straight out of standalone hostname execution
            "serial_number": r'Processor\s+Chassis\s+Serial\s+Number\s*:\s*(\S+)', # Maps LPAR machine deployment tag
            # --- Added Regex Patterns for AI Parsing ---
            "errpt_critical_flag": r'\s+([P12])\s+[HS]\s+', # Catches Permanent (P) errors or Class 1/2 faults in errpt
            "vg_stale_flag": r'stale', # Quickly flags synchronization faults on LVM mirror paths
            "device_status": r'(\S+)\s+Available' # Verifies a driver path is online and working
        },
        device_types=["server"]
    ),
    "openstack_cloud": VendorProfile(
        "OpenStack", "OpenStack Foundation", "shell", "OpenStack Cloud Infrastructure",
        commands={
            "terminal_length": "export OS_OUTPUT_DECODE=utf-8; unset PAGERS", # Forces unpaged raw output blocks
            "fetch_shell_commands": [
                # --- Identity & Global API Control Plane Sanity ---
                ("keystone_endpoints", "openstack endpoint list"), # Verifies that service endpoints are active and exposed
                ("api_services", "openstack service list"), # Lists registered core catalog daemons
                ("compute_services", "openstack compute service list"), # Nova: monitors state (up/down) of scheduler and compute nodes
                ("network_agents", "openstack network agent list"), # Neutron: tracks Layer 2, DHCP, Metadata, and L3 router health
                ("volume_services", "openstack volume service list"), # Cinder: checks volume backend agent availability
                
                # --- Hypervisor & Resource Sizing Metrics ---
                ("hypervisor_stats", "openstack hypervisor stats show"), # Aggregates global vCPU, Memory, and Disk allocations
                ("hypervisor_nodes", "openstack hypervisor list --long"), # Pinpoints exact hypervisor nodes that may be offline or disabled
                ("compute_limits", "openstack limits show --absolute"), # Tracks cloud-wide quota exhaustion ceilings
                
                # --- Instance Layer Triage (Nova) ---
                ("failed_instances", "openstack server list --all-projects --status ERROR"), # Isolates VMs stuck in an explicit ERROR state
                ("server_migrations", "openstack server migration list"), # Tracks active, hung, or failed cold/live migrations
                
                # --- Network Plane Diagnostics (Neutron) ---
                ("network_failures", "openstack network list --long"), # Validates status and operational visibility of tenant nets
                ("router_status", "openstack router list --long"), # Checks if distributed or centralized routers are active
                ("floating_ips", "openstack floating ip list"), # Maps external public IP mappings to internal ports
                
                # --- Storage Layer Diagnostics (Cinder & Glance) ---
                ("volume_failures", "openstack volume list --all-projects --status error"), # Pinpoints block storage attachment failures
                ("image_visibility", "openstack image list --long") # Validates image store states (active, queued, killed)
            ],
            "fetch_config": "openstack configuration show", # Outputs full active environmental authentication parameters
            "save_config": "openstack token issue", # Safe non-destructive operation verifying that the credentials/tokens are functional
            "exit": "exit"
        },
        snmp_patterns={"vendor_keywords": ["openstack", "nova", "neutron", "keystone"], "model_regex": r'OpenStack\s+(\S+)', "version_regex": r'(\d+\.\d+\.\d+)'},
        cli_patterns={
            "cpu_usage": r'vcpus_used\s*\|\s*(\d+)', # Parsed directly from hypervisor global stats metrics
            "os_version": r'OpenStack\s+Release\s*:\s*(\S+)', # Maps to the current structural release moniker (e.g., Caracal, Bobcat)
            "model": r'Deployment\s+Type\s*:\s*(.*)', # e.g., Kolla-Ansible, OpenStack-Ansible, TripleO
            "mac_address": r'mac_address\s*\|\s*([0-9a-fA-F:]+)', # Matches instances or network ports
            "hostname": r'Hypervisor\s+Hostname\s*\|\s*(\S+)',
            "serial_number": r'Project\s+ID\s*\|\s*(\S+)', # Pulls structural admin tenant uuid
            # --- Added Regex Patterns for AI Parsing ---
            "agent_state": r'\|\s*(\S+)\s*\|\s*up\s*\|', # Validates that a core framework scheduler agent is "up"
            "service_disabled": r'\|\s*disabled\s*\|', # Flags if a compute hypervisor has been placed in maintenance mode
            "instance_error_msg": r'Fault\s*:\s*(.*)' # Extracts the precise deployment error block from a VM instance trace
        },
        device_types=["cloud"]
    ),
    "linux_os": VendorProfile(
        "Linux", "Open Source", "shell", "Linux Operating System",
        commands={
            "terminal_length": "export TERM=vt100; export LANG=C; unset PAGER", # Prevents terminal paging, disables interactive color codes, forces predictable language strings
            "fetch_shell_commands": [
                # --- System Identity & Global Resource Sanity ---
                ("sys_info", "uname -a"), # Identifies kernel release, hardware architecture, and hostname
                ("os_release", "cat /etc/os-release"), # Parses distribution specific details (e.g., RHEL vs Ubuntu)
                ("uptime_load", "uptime"), # High-level sanity check for system uptime and 1/5/15 minute load averages
                ("cpu_profile", "lscpu"), # Inventory of physical sockets, cores, threads, and hypervisor flags
                
                # --- Advanced Log Analysis & Kernel Traps ---
                ("kernel_faults", "dmesg -T --level=err,crit,alert,emerg | tail -n 50"), # Captures the last 50 human-readable kernel ring buffer errors
                ("systemd_failures", "journalctl -p 3 -n 50 --no-pager"), # Ingests last 50 system-wide priority 3 (Error) and above logs
                ("failed_services", "systemctl --failed --type=service"), # Instantly lists any systemd daemons that crashed or failed to start
                
                # --- Memory & Compute Bottlenecks ---
                ("mem_stats", "free -m"), # Breaks down physical RAM and Swap usage in Megabytes
                ("oom_killer_check", "grep -i -E 'oom[-_]killer|out of memory' /var/log/messages /var/log/syslog 2>/dev/null | tail -n 10"), # Tracks if the kernel is dynamically killing processes due to memory starvation
                ("process_top", "ps -eo pid,ppid,%cpu,%mem,stat,comm --sort=-%cpu | head -n 20"), # Targets the top 20 processes actively consuming CPU cycles
                
                # --- Storage Array & I/O Diagnostics ---
                ("disk_space", "df -hT"), # Displays mounted file systems, types, capacity utilization, and exhaustion points
                ("disk_inodes", "df -iT"), # Tracks inode depletion (which stops file creation even if disk space is available)
                ("io_throttling", "vmstat 1 5"), # 5-second sampling loop checking block device queues ('b') and context switches
                ("io_device_perf", "iostat -xz 1 3 2>/dev/null || sar -d 1 3"), # Isolates individual storage drive saturation, wait times, and percent utilization
                
                # --- Networking & Socket Telemetry ---
                ("network_interfaces", "ip -br addr show"), # Brief format table displaying interface names, link states, and assigned IPs
                ("routing_table", "ip route show"), # Inspects the kernel routing table and default gateways
                ("listening_ports", "ss -tulpn"), # Identifies active listening sockets, protocols (TCP/UDP), and their associated process PIDs
                ("socket_drops", "netstat -s | grep -i -E 'drop|overflow|timeout'") # Searches network stack counter histories for buffer drops
            ],
            "fetch_config": "cat /etc/sysctl.conf /etc/sysctl.d/*.conf 2>/dev/null", # Dumps core runtime kernel parameters
            "save_config": "sync; sysctl -p 2>/dev/null || true", # Flushes volatile dirty pages to physical disk and reloads kernel parameters safely
            "exit": "exit"
        },
        snmp_patterns={"vendor_keywords": ["linux", "gnu"], "model_regex": r'Linux\s+(\S+)', "version_regex": r'#\d+\s+SMP\s+(.*)'},
        cli_patterns={
            "cpu_usage": r'\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$\s*$', # Parses processor consumption dynamics dynamically from vmstat loops
            "os_version": r'PRETTY_NAME="([^"]+)"', # Extractable direct string match from /etc/os-release
            "model": r'Hardware\s+Model\s*:\s*(.*)|System\s+Product\s+Name\s*:\s*(.*)', # Scrapers targeted at dmi/lshw baselines
            "mac_address": r'link/ether\s+([0-9a-fA-F:]+)', # Perfectly aligns with modern iproute2 link syntax mapping
            "hostname": r'^(\S+)', # Instantly matched from individual standalone hostname execution outputs
            "serial_number": r'Chassis\s+Serial\s+Number\s*:\s*(\S+)|Serial\s+Number\s*:\s*(\S+)', # Targets DMI decode serial identifiers
            # --- Added Regex Patterns for AI Parsing ---
            "oom_event_detected": r'Killed\s+process\s+(\d+)', # Triggers immediate priority alerting for memory exhaustion runs
            "disk_full_pct": r'\s+(\d+)%\s+/', # Catches root filesystem percentage utilization flags
            "service_state": r'(\S+)\.service\s+loaded\s+failed' # Targets and parses systemd runtime crashes
        },
        device_types=["os"]
    ),
    "windows_os": VendorProfile(
        "Windows", "Microsoft Corporation", "powershell", "Windows Operating System",
        commands={
            "terminal_length": "$FormatEnumerationLimit=-1; $ProgressPreference='SilentlyContinue'", # Disables output truncation and suppresses visual progress bars for clean API scraping
            "fetch_shell_commands": [
                # --- System Identity & Global OS Sanity ---
                ("sys_info", "Get-CimInstance -ClassName Win32_OperatingSystem | Select-Object Caption, Version, OSArchitecture, LastBootUpTime"), # Retrieves exact Windows variant, version, and architecture bounds
                ("computer_system", "Get-CimInstance -ClassName Win32_ComputerSystem | Select-Object Model, Manufacturer, TotalPhysicalMemory, PartOfDomain, Domain"), # Evaluates hardware model, RAM capacity, and active Domain membership states
                ("uptime_check", "(Get-Date) - (Get-CimInstance -ClassName Win32_OperatingSystem).LastBootUpTime | Select-Object Days, Hours, Minutes"), # Computes system uptime duration
                ("cpu_profile", "Get-CimInstance -ClassName Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors"), # Inventory of physical CPU infrastructure
                
                # --- Advanced Event Log Analysis & Traps (Critical Triage) ---
                ("blue_screen_check", "Get-WinEvent -FilterHashtable @{LogName='System'; Id=1001, 6008} -MaxEvents 10 -ErrorAction SilentlyContinue | Select-Object TimeCreated, Message"), # Captures unexpected dirty shutdowns and BugCheck (BSOD) events
                ("system_errors", "Get-WinEvent -FilterHashtable @{LogName='System'; Level=1,2} -MaxEvents 50 -ErrorAction SilentlyContinue | Select-Object TimeCreated, ProviderName, Id, Message"), # Extracts last 50 System Critical (1) and Error (2) events
                ("application_crashes", "Get-WinEvent -FilterHashtable @{LogName='Application'; Level=1,2; ProviderName='Application Error'} -MaxEvents 20 -ErrorAction SilentlyContinue | Select-Object TimeCreated, Message"), # Targets explicitly crashing application processes
                ("failed_services", "Get-Service | Where-Object {$_.Status -eq 'Stopped' -and $_.StartType -eq 'Automatic'} | Select-Object Name, DisplayName"), # Identifies services that should be running but crashed or failed to initialize
                
                # --- Memory & Compute Bottlenecks ---
                ("mem_stats", "Get-CimInstance -ClassName Win32_OperatingSystem | Select-Object TotalVisibleMemorySize, FreePhysicalMemory, TotalVirtualMemorySize, FreeVirtualMemory"), # Detailed breakdown of physical and paging memory allocations (in KB)
                ("process_top", "Get-Process | Sort-Object -Property CPU -Descending | Select-Object -First 20 -Property Id, ProcessName, CPU, WorkingSet64"), # Targets the top 20 processes actively consuming computing and memory allocations
                
                # --- Storage & File System Diagnostics ---
                ("disk_space", "Get-Volume | Where-Object {$_.DriveType -eq 'Fixed'} | Select-Object DriveLetter, FileSystemLabel, FileSystem, Size, SizeRemaining"), # High-level logical volume space tracking
                ("disk_health", "Get-PhysicalDisk | Select-Object DeviceId, FriendlyName, OperationalStatus, HealthStatus"), # Validates physical hardware disk infrastructure health underneath storage pools
                
                # --- Networking & Socket Telemetry ---
                ("network_interfaces", "Get-NetIPAddress -AddressFamily IPv4 | Select-Object InterfaceAlias, IPAddress, InterfaceIndex"), # Tables out active physical interface names and their associated internal IPs
                ("routing_table", "Get-NetRoute -AddressFamily IPv4 | Select-Object DestinationPrefix, NextHop, RouteMetric, InterfaceAlias"), # Inspects the Windows kernel IP routing engine paths
                ("listening_ports", "Get-NetTCPConnection -State Listen | Select-Object LocalAddress, LocalPort, OwningProcess") # Identifies listening TCP sockets and the explicit backend Process PIDs binding them
            ],
            "fetch_config": "Get-NetIPInterface -AddressFamily IPv4 | Select-Object InterfaceAlias, Dhcp, ConnectionState", # Pulls basic network transport structural behaviors
            "save_config": "[System.GC]::Collect(); ipconfig /flushdns", # Safe operation to clear resource foot-printing and flush local DNS resolver caches
            "exit": "exit"
        },
        snmp_patterns={"vendor_keywords": ["windows", "microsoft"], "model_regex": r'Windows\s+(\S+)', "version_regex": r'Build\s+(\d+)'},
        cli_patterns={
            "cpu_usage": r'PercentProcessorTime\s*:\s*(\d+)', # Parsed if leveraging direct background performance counter pools
            "os_version": r'Version\s*:\s*(\S+)', # Extracted cleanly from system information captures
            "model": r'Model\s*:\s*(.*)', # Scraped directly via computer system lookups
            "mac_address": r'([0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2})', # Standard Windows dash-notation MAC address configuration regex
            "hostname": r'HostName\s*:\s*(\S+)', 
            "serial_number": r'SerialNumber\s*:\s*(\S+)', # Gathers motherboard BIOS serial string metadata
            # --- Added Regex Patterns for AI Parsing ---
            "bsod_event_detected": r'BugCheck', # Instantly flags system core blue-screen failure trajectories
            "disk_full_pct": r'SizeRemaining\s*:\s*0', # Targets system storage capacity depletion markers
            "service_state": r'Status\s*:\s*Stopped' # Identifies service runtime crashes
        },
        device_types=["os"]
    ),
    "citrix_cvad": VendorProfile(
        "Citrix", "Citrix Systems, Inc.", "powershell", "Citrix Virtual Apps and Desktops",
        commands={
            "terminal_length": "$FormatEnumerationLimit=-1; Add-PSSnapin Citrix.*.Admin.V1 -ErrorAction SilentlyContinue; Import-Module Citrix.*.PowerShell.Sdk -ErrorAction SilentlyContinue", # Auto-loads the Citrix orchestration engine SDK modules and prevents text clipping
            "fetch_shell_commands": [
                # --- Site Configuration & Controller Health ---
                ("site_status", "Get-CitrixSite"), # High-level sanity check tracking Site naming conventions and database connection health
                ("broker_service_status", "Get-BrokerController | Select-Object DNSName, ControllerVersion, State, ActiveSessionCount"), # Monitors status of site delivery controllers (Brokers) to find offline instances
                ("licensing_status", "Get-LicensingServerStatus | Select-Object ServerName, LicensingStatus, LicenseExpirationDate"), # Verifies the critical link to the Citrix License Server
                
                # --- Machine Catalog & VDA Registration (The Core Failure Matrix) ---
                ("unregistered_vdas", "Get-BrokerMachine -RegistrationState Unregistered | Select-Object MachineName, DeliveryGroupName, HostingServerName, LastDeregistrationReason"), # Direct triage for VDAs that cannot register with delivery controllers
                ("vda_maintenance_mode", "Get-BrokerMachine -InMaintenanceMode $true | Select-Object MachineName, DeliveryGroupName, AssociatedUserNames"), # Flags servers blocked from users via explicit maintenance lockouts
                ("failed_power_actions", "Get-BrokerHostingPowerAction -State Failed | Select-Object MachineName, Action, FailureReason, Time"), # Identifies hypervisor orchestration VM boot/reboot errors
                
                # --- Delivery Groups & Session Analytics ---
                ("delivery_group_health", "Get-BrokerDesktopGroup | Select-Object Name, DesktopsAvailable, DesktopsDisconnected, DesktopsFaulted, DesktopsUnregistered"), # High-level operational balance sheet for user access pools
                ("active_sessions", "Get-BrokerSession -SessionState Active | Select-Object UserName, MachineName, StartTime, ClientName, Protocol"), # Maps runtime active connections
                ("hung_disconnected_sessions", "Get-BrokerSession -SessionState Disconnected | Where-Object {((Get-Date) - $_.SessionStateChangeTime).TotalHours -gt 24} | Select-Object UserName, MachineName, SessionStateChangeTime"), # Isolates phantom/stuck worker sessions leaking machine resources
                
                # --- Desktop & Application Launch Troubleshooting ---
                ("session_launch_failures", "Get-BrokerSessionDiagnosticInfo -MaxEvents 50 -ErrorAction SilentlyContinue"), # Gathers launch failure codes (e.g., ICA file generation errors, connection timeouts)
                ("app_inventory_issues", "Get-BrokerApplication | Where-Object {$_.Enabled -eq $false} | Select-Object Name, BrowserName") # Tracks applications disabled by admins or corrupted via path drift
            ],
            "fetch_config": "Get-BrokerDBConnection", # Outputs connection strings targeting the active Citrix Datastore SQL database
            "save_config": "Clear-BrokerSessionDiagnosticInfo -ErrorAction SilentlyContinue", # Non-destructive logging maintenance flush placeholder
            "exit": "exit"
        },
        snmp_patterns={"vendor_keywords": ["citrix", "xenapp", "xendesktop", "vda"], "model_regex": r'CVAD\s+(\d+)', "version_regex": r'ProductVersion\s*:\s*(\S+)'},
        cli_patterns={
            "cpu_usage": r'LoadIndex\s*:\s*(\d+)', # Citrix maps machine resource exhaustion through a dynamic "Load Index" metric from 0 to 10,000
            "os_version": r'ControllerVersion\s*:\s*(\S+)', # Correlates with the core environment functional baseline (e.g., 1912 LTSR, 2402)
            "model": r'CatalogName\s*:\s*(.*)', # Grabs parent provisioning template types
            "mac_address": r'([0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2})',
            "hostname": r'MachineName\s*:\s*(\S+)',
            "serial_number": r'LicenseServer\s*:\s*(\S+)', # Tracks core deployment licensing identifier links
            # --- Added Regex Patterns for AI Parsing ---
            "vda_fault": r'RegistrationState\s*:\s*Unregistered', # Instantly isolates broken session host endpoints
            "dereg_reason": r'LastDeregistrationReason\s*:\s*(\S+)', # Captures values like AgentCrashing, ControllerBlocked, or ConnectionTimeout
            "load_index_full": r'LoadIndex\s*:\s*10000' # Flags a VDA that is completely saturated and rejecting new user logons
        },
        device_types=["infrastructure"]
    ),
    "vmware_vcenter": VendorProfile(
        "VMware", "Broadcom / VMware", "powershell", "vCenter Server Appliance (vCSA)",
        commands={
            "terminal_length": "$FormatEnumerationLimit=-1; Set-PowerCLIConfiguration -InvalidCertificateAction Ignore -Confirm:$false | Out-Null", # Forces non-interactive script execution and suppresses SSL verification alerts
            "fetch_shell_commands": [
                # --- vCenter Site & Cluster Sanity ---
                ("vcenter_info", "Get-VIServer | Select-Object Name, Version, Build"), # Identifies the vCenter appliance baseline release and build tracks
                ("cluster_health", "Get-Cluster | Select-Object Name, HAEnabled, DRSEnabled, DRSAutomationLevel"), # Evaluates whether core high-availability orchestration services are enabled and running
                ("vcenter_alarms", "Get-AlarmTriggered | Where-Object {$_.Status -eq 'Red'} | Select-Object Entity, Alarm, Status"), # Pulls all active infrastructure entity alarms currently in a critical/red state
                
                # --- ESXi Host Layer Triage (Compute Fabric) ---
                ("host_status", "Get-VMHost | Select-Object Name, ConnectionState, PowerState, MaxEVCMode"), # Direct health assessment mapping disconnected or crashed hypervisor nodes
                ("host_hardware_faults", "Get-VMHost | Get-VMHostHardware | Select-Object VMHost, Manufacturer, Model, SerialNumber"), # Extracts chassis hardware identity
                ("host_resource_saturation", "Get-VMHost | Select-Object Name, CpuUsageMhz, CpuTotalMhz, MemoryUsageGB, MemoryTotalGB"), # Evaluates real-time hardware overcommit thresholds across ESXi blades
                
                # --- Storage Layer Datastore Diagnostics ---
                ("datastore_space", "Get-Datastore | Select-Object Name, FileSystemType, CapacityGB, FreeSpaceGB"), # Tracks VMFS/vSAN capacity depletion, thin-provisioning overcommitments, and exhaustion boundaries
                ("datastore_accessibility", "Get-Datastore | Where-Object {$_.Accessible -eq $false} | Select-Object Name, ExtensionData"), # Flags storage paths that dropped offline or suffered All-Paths-Down (APD) events
                
                # --- Virtual Machine Layer Isolation ---
                ("failed_vms", "Get-VM | Where-Object {$_.PowerState -eq 'PoweredOn' -and $_.ExtensionData.Runtime.ConnectionState -ne 'connected'} | Select-Object Name, PowerState"), # Isolates orphaned VMs or instances stuck in inconsistent runtime execution
                ("snapshot_bloat", "Get-VM | Get-Snapshot | Where-Object {$_.Created -lt (Get-Date).AddDays(-7)} | Select-Object VM, Name, SizeGB, Created") # Captures stale snapshots that degrade disk arrays and lock virtual execution lines
            ],
            "fetch_config": "Get-AdvancedSetting -Entity (Get-VIServer) -Name *", # Dumps global underlying system performance advanced parameters
            "save_config": "Disconnect-VIServer -Confirm:$false", # Non-destructive connection closure behavior to clean up API resource sessions
            "exit": "exit"
        },
        snmp_patterns={"vendor_keywords": ["vmware", "vcenter", "esxi", "vsphere"], "model_regex": r'vCenter\s+Server', "version_regex": r'Version\s+(\d+\.\d+\.\d+)'},
        cli_patterns={
            "cpu_usage": r'CpuUsageMhz\s*:\s*(\d+)', # Evaluated relative to CpuTotalMhz for real-time compute tracking
            "os_version": r'Version\s*:\s*(\S+)', # Maps directly to the appliance build framework (e.g., 8.0.x)
            "model": r'Model\s*:\s*(.*)', # Extracted straight from hypervisor hardware queries
            "mac_address": r'([0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2})',
            "hostname": r'Name\s*:\s*(\S+)',
            "serial_number": r'SerialNumber\s*:\s*(\S+)', # Captures the primary ESXi hardware host asset configuration tags
            # --- Added Regex Patterns for AI Parsing ---
            "alarm_critical": r'Status\s*:\s*Red', # Targets immediate operational escalations
            "host_disconnected": r'ConnectionState\s*:\s*(NotResponding|Disconnected)', # Identifies frozen or dead ESXi bare-metal engines
            "storage_full": r'FreeSpaceGB\s*:\s*0' # Instantly alerts for VMFS volumes experiencing runtime write freezes
        },
        device_types=["hypervisor"]
    ),
    "oracle_cloud_oci": VendorProfile(
        "Oracle Cloud", "Oracle Corporation", "shell", "Oracle Cloud Infrastructure (OCI)",
        commands={
            "terminal_length": "export OCI_CLI_SUPPRESS_FILE_PERMISSIONS_WARNING=1", # Forces non-interactive CLI scripting behaviors
            "fetch_shell_commands": [
                # --- Tenant Identity & Service Limits Sanity ---
                ("tenancy_info", "oci iam tenancy get --tenancy-id $OCI_TENANCY_ID"), # Retrieves core home region, metadata, and corporate entity identities
                ("compartment_list", "oci iam compartment list --all"), # Maps out structural sub-tenancy organization hierarchies
                ("quota_limits", "oci limits value list --compartment-id $OCI_TENANCY_ID --all"), # Tracks real-time OCI shape allocation exhaustion ceilings
                
                # --- Compute Instance Layer Triage (Core / Nova equivalent) ---
                ("failed_instances", "oci compute instance list --all --lifecycle-state CRASHED"), # Isolates bare-metal or VM instances that failed unexpectedly
                ("stopped_instances", "oci compute instance list --all --lifecycle-state STOPPED"), # Lists VMs sitting in a stopped state to identify unexecuted automation paths
                ("instance_work_requests", "oci compute work-request list --compartment-id $OCI_TENANCY_ID --all"), # Tracks provisioning failures, timeouts, and orchestration faults
                
                # --- Networking Layer Diagnostics (VCN / Edge) ---
                ("vcn_failures", "oci network vcn list --compartment-id $OCI_TENANCY_ID --all"), # Validates health, configuration states, and CIDR block parameters of virtual clouds
                ("drg_routing", "oci network drg list --compartment-id $OCI_TENANCY_ID --all"), # Inspects Dynamic Routing Gateways handling multi-cloud or on-premise IPsec/FastConnect transitions
                ("security_lists", "oci network security-list list --compartment-id $OCI_TENANCY_ID --all"), # Captures edge stateless/stateful packet inspection firewalls to trace drop trajectories
                
                # --- Storage Layer Diagnostics (Block / Object) ---
                ("block_volume_faults", "oci bv volume list --compartment-id $OCI_TENANCY_ID --all"), # Validates detachment errors or lifecycle states of block devices
                ("object_storage_health", "oci os bucket list --compartment-id $OCI_TENANCY_ID"), # Sweeps object buckets to verify connectivity availability
                
                # --- Tenant Auditing & Performance Triggers ---
                ("audit_critical_events", "oci audit event list --compartment-id $OCI_TENANCY_ID --start-time (date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ) --all") # Ingests last 1 hour of structural IAM or network state modification logs
            ],
            "fetch_config": "oci setup config", # Dumps profile configurations, active user OCIDs, and fingerprinted API key paths
            "save_config": "oci session validate --session-id local", # Safe operation to verify that token credentials or API signatures are structurally functional
            "exit": "exit"
        },
        snmp_patterns={"vendor_keywords": ["oracle", "oci", "oracle cloud"], "model_regex": r'OCI\s+(\S+)', "version_regex": r'(\d+\.\d+\.\d+)'},
        cli_patterns={
            "cpu_usage": r'Compute\s+Utilization\s*:\s*(\d+)%', # Parsed if matching metrics out of OCI Monitoring queries
            "os_version": r'OCI\s+Release\s*:\s*(\S+)', # Correlates with base CLI build parameters
            "model": r'Shape\s*:\s*(\S+)', # Captures specific processor layouts (e.g., VM.Standard.E4.Flex, BM.Optimized3.36)
            "mac_address": r'mac-address\s*:\s*"([0-9a-fA-F:]+)"', # Matches specific Virtual Network Interface Cards (VNICs)
            "hostname": r'display-name\s*:\s*"([^"]+)"', # Grabs explicit friendly or system asset resource names
            "serial_number": r'id\s*:\s*"([^"]+)"', # Captures unique Oracle Cloud Identifier (OCID) structural signature strings
            # --- Added Regex Patterns for AI Parsing ---
            "lifecycle_fault": r'"lifecycle-state"\s*:\s*"(CRASHED|FAULTED)"', # Identifies infrastructure hardware components dropped offline by the hypervisor
            "quota_exhausted": r'"message"\s*:\s*"([^"]*LimitExceeded[^"]*)"', # Automatically identifies failed resource scale-ups caused by tenancy exhaustion bounds
            "audit_action_fail": r'"status"\s*:\s*(\d{3})' # Pinpoints explicit API authorization drops (e.g., 401, 403 HTTP status responses)
        },
        device_types=["cloud"]
    ),
    "oracle_database": VendorProfile(
        "Oracle Database", "Oracle Corporation", "sql", "Oracle Relational Database Management System",
        commands={
            "terminal_length": "SET PAGESIZE 0; SET LINESIZE 32767; SET FEEDBACK OFF; SET HEADING OFF; SET TRIMSPOOL ON; ALTER SESSION SET ISOLATION_LEVEL = READ COMMITTED;", # Disables SQL*Plus pagination, page formatting rules, and visual decoration for raw tabular scraping
            "fetch_shell_commands": [
                # --- Database Instance & Global Sanity ---
                ("instance_status", "SELECT instance_name, host_name, version, status, database_status, archiver FROM v$instance;"), # Checks if the instance is Open, Mounted, or experiencing an Archiver hang
                ("database_health", "SELECT name, log_mode, open_mode, protection_mode FROM v$database;"), # Identifies Read/Write capability and standby configuration states
                ("rac_cluster_health", "SELECT inst_id, instance_name, status FROM gv$instance;"), # For Real Application Clusters (RAC): monitors cross-node survival states
                
                # --- Session Performance & Lock Contention (Critical Triage) ---
                ("blocked_sessions", "SELECT blocking_session, sid, serial#, wait_class, seconds_in_wait FROM v$session WHERE blocking_session IS NOT NULL;"), # Instantly isolates deadlocks and application locking chains
                ("top_wait_events", "SELECT event, total_waits, time_waited_micro FROM (SELECT event, total_waits, time_waited_micro FROM v$system_event WHERE wait_class <> 'Idle' ORDER BY time_waited_micro DESC) WHERE ROWNUM <= 10;"), # Pinpoints underlying system bottlenecks (e.g., db file sequential read, log file sync)
                ("active_session_count", "SELECT status, count(*) FROM v$session GROUP BY status;"), # Tracks active user connection spikes causing listener or thread saturation
                
                # --- Storage Subsystem & Tablespace Capacity ---
                ("tablespace_exhaustion", "SELECT df.tablespace_name, ROUND(((df.bytes - fs.bytes) / df.bytes) * 100, 2) AS pct_used FROM (SELECT tablespace_name, SUM(bytes) bytes FROM dba_data_files GROUP BY tablespace_name) df, (SELECT tablespace_name, SUM(bytes) bytes FROM dba_free_space GROUP BY tablespace_name) fs WHERE df.tablespace_name = fs.tablespace_name AND ROUND(((df.bytes - fs.bytes) / df.bytes) * 100, 2) > 85;"), # Flags any storage layer approaching absolute boundary exhaustion (>85%)
                ("asm_disk_faults", "SELECT name, state, type, total_mb, free_mb FROM v$asm_diskgroup WHERE state <> 'MOUNTED';"), # Isolates Automated Storage Management array errors dropouts
                ("fra_space_check", "SELECT name, space_limit, space_used, space_reclaimable FROM v$recovery_file_dest;"), # Verifies Flash Recovery Area status to prevent database freezes when archive logs saturate local space
                
                # --- Multitenant Architecture (PDB Layer) ---
                ("pdb_lifecycle_states", "SELECT con_id, name, open_mode FROM v$pdbs;"), # For Container environments: validates pluggable database operational availability
                
                # --- Background Infrastructure Health ---
                ("invalid_objects", "SELECT owner, object_type, COUNT(*) FROM dba_objects WHERE status = 'INVALID' GROUP BY owner, object_type;") # Identifies dictionary structural corruption or broken procedural packages
            ],
            "fetch_config": "SELECT name, value FROM v$parameter WHERE isdefault = 'FALSE';", # Dumps modified init.ora/spfile runtime operational environment parameters
            "save_config": "ALTER SYSTEM FLUSH BUFFER_CACHE; ALTER SYSTEM FLUSH SHARED_POOL;", # Non-destructive performance maintenance operations to remediate dynamic memory latch contention safely
            "exit": "EXIT;"
        },
        snmp_patterns={"vendor_keywords": ["oracle database", "rdbms", "sqlplus"], "model_regex": r'Oracle\s+Database', "version_regex": r'Release\s+(\d+\.\d+\.\d+)'},
        cli_patterns={
            "cpu_usage": r'CPU\s+used\s+by\s+this\s+session\s*:\s*(\d+)', # Parsed from v$sysstat metrics evaluations
            "os_version": r'Version\s*:\s*(\S+)', # Maps engine structural release level (e.g., 19.0.0.0.0)
            "model": r'Edition\s*:\s*(.*)', # Distinguishes between Enterprise Edition, Standard Edition, or Express
            "mac_address": r'([0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2})',
            "hostname": r'host_name\s*:\s*(\S+)',
            "serial_number": r'dbid\s*:\s*(\d+)', # Captures unique Oracle Database Identifier (DBID) signature tags
            # --- Added Regex Patterns for AI Parsing ---
            "archiver_failed": r'FAILED', # Matches if the instance's archiver process drops offline (halting all transaction processing)
            "tablespace_critical": r'(\d{2}\.\d{2})', # Parses out dynamic percentage markers indicating a volume is dangerously full
            "session_deadlock": r'blocking_session\s*:\s*(\d+)' # Captures lock progression indices to spin off dynamic process termination actions
        },
        device_types=["database"]
    ),
    "aws_ec2_cloud": VendorProfile(
        "AWS Cloud", "Amazon Web Services, Inc.", "shell", "AWS EC2 Cloud Infrastructure",
        commands={
            "terminal_length": "export AWS_DEFAULT_OUTPUT=text; export AWS_PAGER=''", # Forces unpaged text streams for seamless automated regex scraping
            "fetch_shell_commands": [
                # --- Global Tenancy & API Validation ---
                ("account_identity", "aws sts get-caller-identity"), # Verifies IAM access credentials, account number, and assumed role configurations
                ("region_az_status", "aws ec2 describe-availability-zones --region $AWS_DEFAULT_REGION"), # Validates that target cloud infrastructure centers are online
                
                # --- EC2 Instance Layer Triage (Compute Fabric) ---
                ("failed_instances", "aws ec2 describe-instances --filters 'Name=instance-state-name,Values=stopped,terminated' --query 'Reservations[*].Instances[*].[InstanceId,State.Name,InstanceType,LaunchTime]'"), # Pinpoints instances stuck in non-operational states
                ("host_status_checks", "aws ec2 describe-instance-status --filters 'Name=instance-status.status,Values=impaired' 'Name=system-status.status,Values=impaired'"), # Captures failures where instances failed underlying bare-metal hardware handshakes
                ("cloud_init_console", "aws ec2 get-console-output --instance-id {instance_id}"), # Dynamically fetches kernel boot strings to trace OS kernel panics or blue screen loops
                
                # --- Networking Layer & Security Traps (VPC Engine) ---
                ("network_interfaces", "aws ec2 describe-network-interfaces --filters 'Name=status,Values=in-use' --query 'NetworkInterfaces[*].[NetworkInterfaceId,VpcId,PrivateIpAddress,Association.PublicIp]'"), # Maps out virtual network infrastructure alignments
                ("security_group_rules", "aws ec2 describe-security-group-rules --query 'SecurityGroupRules[*].[SecurityGroupId,Protocol,FromPort,ToPort,CidrIpv4,IsEgress]'"), # Dumps active firewall tables to track traffic drop vectors
                ("routing_tables", "aws ec2 describe-route-tables --query 'RouteTables[*].[RouteTableId,VpcId,Routes[*].DestinationCidrBlock]'"), # Validates Internet Gateway and NAT routing topologies
                
                # --- Storage Layer Diagnostics (EBS Matrix) ---
                ("ebs_volume_faults", "aws ec2 describe-volumes --filters 'Name=status,Values=error,impairing' --query 'Volumes[*].[VolumeId,Size,AvailabilityZone,Status]'"), # Isolates block storage attachment errors
                ("ebs_stuck_attaching", "aws ec2 describe-volumes --filters 'Name=attachment.status,Values=attaching,detaching'"), # Flags block volumes experiencing system lockouts
                
                # --- CloudWatch Resource Utilization Prompts ---
                ("cpu_saturation_metric", "aws cloudwatch get-metric-statistics --namespace AWS/EC2 --metric-name CPUUtilization --period 300 --statistics Average --dimensions Name=InstanceId,Value={instance_id} --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ) --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ)") # Retrospectively pulls 1 hour of CPU trends to analyze throttling
            ],
            "fetch_config": "aws configure list", # Dumps profile initialization scopes, access keys, and active default fallback regions
            "save_config": "aws sts get-session-token --duration-seconds 900", # Safe operation to validate that the local programmatic token session remains active
            "exit": "exit"
        },
        snmp_patterns={"vendor_keywords": ["aws", "ec2", "amazon web services", "amazon"], "model_regex": r'([a-z]\d[a-z]?)\.(nano|micro|small|medium|large|xlarge|\d+xlarge)', "version_regex": r'aws-cli\/(\d+\.\d+\.\d+)'},
        cli_patterns={
            "cpu_usage": r'AVERAGE\s+(\d+\.\d+)', # Scraped directly from stdout tracking streams on metric blocks
            "os_version": r'aws-cli\/(\S+)', # Maps AWS engine tools baseline version
            "model": r'([a-z]\d[a-z]?\.\S+)', # Matches instance shape sizes (e.g., t3.medium, m5.2xlarge, c6i.metal)
            "mac_address": r'MacAddress\s*:\s*([0-9a-fA-F:]+)', # Extracted via instance metadata lookups
            "hostname": r'PrivateDnsName\s*:\s*(\S+)',
            "serial_number": r'(i-[0-9a-fA-F]{17})', # Perfectly captures AWS unique structural 17-digit Instance ID signatures
            # --- Added Regex Patterns for AI Parsing ---
            "instance_impaired": r'(impaired|failed)', # Flags instance health check failures
            "volume_detached": r'available', # Identifies EBS storage drives orphaned from processing loops
            "api_auth_block": r'(AccessDenied|SignatureDoesNotMatch)' # Spots permission and structural credential breakdowns instantly
        },
        device_types=["cloud"]
    ),
    "azure_cloud": VendorProfile(
        "Azure Cloud", "Microsoft Corporation", "shell", "Azure Cloud Infrastructure",
        commands={
            "terminal_length": "az config set core.no_color=true; export AZURE_CORE_OUTPUT=table", # Eliminates ANSI visual decoration and forces tabular layout parsing
            "fetch_shell_commands": [
                # --- Tenant Subscription & API Gateway Sanity ---
                ("account_identity", "az account show"), # Displays active Subscription ID, tenant identity, and environment configurations
                ("provider_health", "az provider list --query \"[?registrationState!='Registered'].{Provider:namespace,Status:registrationState}\""), # Flags if any required API resource providers dropped offline or unregistered
                
                # --- Azure Virtual Machine Layer Triage (Compute Fabric) ---
                ("failed_vms", "az vm list --query \"[?instanceView.statuses[?code=='PowerState/deallocated'||code=='PowerState/stopped']].{Name:name,ResourceGroup:resourceGroup}\""), # Isolates VMs in unexpected dead execution tracks
                ("vm_statuses", "az vm list-ip-addresses --query \"[*].virtualMachine.{Name:name,ResourceGroup:resourceGroup}\""), # Cross-references compute asset locations across resource boundaries
                ("serial_console_log", "az vm boot-diagnostics get-boot-log --name {vm_name} --resource-group {rg_name}"), # Grabs virtual physical boot screen streams to diagnose kernel panics or BSOD errors
                
                # --- Networking Layer & Firewall Traps (VNet / NSG) ---
                ("network_interfaces", "az network nic list --query \"[*].{Name:name,Vnet:virtualMachine.id,PrivateIp:ipConfigurations[0].privateIpAddress}\""), # Maps private IP allocations and parent hardware assignments
                ("nsg_drop_rules", "az network nsg rule list --nsg-name {nsg_name} --resource-group {rg_name} --query \"[?access=='Deny'].{Name:name,Port:destinationPortRange,Source:sourceAddressPrefix}\""), # Isolates firewall drop trajectories causing application blocks
                ("vpn_gateway_status", "az network vpn-gateway list --query \"[*].{Name:name,Status:provisioningState}\""), # Monitors status of hybrid on-premise infrastructure corridors
                
                # --- Storage Layer Diagnostics (Managed Disks) ---
                ("disk_detachment_faults", "az disk list --query \"[?diskState=='Unattached'].{Name:name,SizeGB:diskSizeGb,ResourceGroup:resourceGroup}\""), # Identifies orphaned block storage assets detached from processing systems
                ("storage_account_faults", "az storage account list --query \"[?statusOfPrimary!='available'].{Name:name,Status:statusOfPrimary}\""), # Tracks cloud blob or file share availability drops
                
                # --- Azure Monitor Logs & Performance Triggers ---
                ("vm_cpu_saturation", "az monitor metrics list --resource {vm_resource_id} --metric \"Percentage CPU\" --interval PT5M --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ) --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ)") # Extracts rolling resource trends directly from Azure Monitor metrics
            ],
            "fetch_config": "az config get", # Dumps global CLI authentication defaults and target operational environments
            "save_config": "az account clear; az login --service-principal -u $AZ_CLIENT_ID -p $AZ_CLIENT_SECRET --tenant $AZ_TENANT_ID", # Non-destructive re-authentication to refresh expiring session tokens safely
            "exit": "exit"
        },
        snmp_patterns={"vendor_keywords": ["azure", "microsoft azure", "virtualmachine"], "model_regex": r'Standard_([A-Z]\d+[a-z]?_v\d+)', "version_regex": r'azure-cli\s*\((\d+\.\d+\.\d+)\)'},
        cli_patterns={
            "cpu_usage": r'Average\s*:\s*(\d+\.\d+)', # Parsed straight from az monitor metric logs
            "os_version": r'azure-cli\s*\((\S+)\)', # Maps system command line utility engine versions
            "model": r'Standard_([A-Z]\d+\S*)', # Matches size shapes (e.g., Standard_D4s_v5, Standard_E16s_v5, Standard_B2s)
            "mac_address": r'"macAddress"\s*:\s*"([0-9a-fA-F:]+)"', # Captured from JSON telemetry properties blocks
            "hostname": r'"computerName"\s*:\s*"([^"]+)"',
            "serial_number": r'("\/subscriptions\/[0-9a-fA-F-]{36}\/[^"\s\>]+")', # Captures unique Azure Resource ID signature tags
            # --- Added Regex Patterns for AI Parsing ---
            "provisioning_failed": r'"provisioningState"\s*:\s*"Failed"', # Flags internal Azure Resource Manager (ARM) infrastructure build crashes
            "nsg_blocked": r'DenyAll', # Catches default or targeted network security blocks instantly
            "token_expired": r'(ExpiredToken|AuthenticationFailed)' # Isolates API access credentials breakdowns immediately
        },
        device_types=["cloud"]
    ),
    "hitachi_vsp": VendorProfile(
        "Hitachi", "Hitachi Vantara", "shell", "Virtual Storage Platform (VSP)",
        commands={
            "terminal_length": "raidcom -login maintenance maint_password || true", # Initializes CCI session mapping parameters and bypasses pagination hooks
            "fetch_shell_commands": [
                # --- System Identity & Component Health ---
                ("sys_info", "raidcom get subsystem"), # Retrieves model array serial numbers, microcode levels, and controller cluster status
                ("component_health", "raidcom get component"), # Fast-path triage: returns status of power supplies, fans, and batteries
                ("cu_free_slots", "raidcom get cu"), # Identifies logical control unit structural mapping properties

                # --- Physical Drive & Storage Pool Layers ---
                ("parity_groups", "raidcom get parity_group"), # Evaluates hardware parity structures and underlying RAID configurations
                ("hdp_pools", "raidcom get pool"), # Hitachi Dynamic Provisioning: tracks health, subscription percent, and thin resource exhaustion
                ("disk_health", "raidcom get drive"), # Scans for bad physical disk media drives or predictive maintenance alerts

                # --- Logical Volumes & Storage Mapping ---
                ("ldev_status", "raidcom get ldev -ldev_id 00:00:00 -cnt 100"), # Pulls physical and block provisioning health properties of logical devices
                ("host_groups", "raidcom get host_group"), # Monitors WWN target mapping abstractions across the fabric
                ("port_status", "raidcom get port"), # Checks physical Fibre Channel/iSCSI link status, speeds, and topology properties
                
                # --- High Availability & Local Replication ---
                ("snapshot_status", "raidcom get snapshot"), # Tracks active local point-in-time image snapshots
                ("gad_pairs", "raidcom get pair -ldev_id 00:00:00 -pvol") # Global-Active Device: validates synchronous storage virtualization mirroring
            ],
            "fetch_config": "raidcom get resource", # Dumps physical and logical engine hardware resource lock partitions
            "save_config": "raidcom -logout", # Gracefully terminates the CCI communication instance session safely
            "exit": "exit"
        },
        snmp_patterns={"vendor_keywords": ["hitachi", "vsp", "hds", "vantara"], "model_regex": r'VSP\s+([5EFG]\d+00?)', "version_regex": r'Microcode\s+(\d+\.\d+\.\d+)'},
        cli_patterns={
            "cpu_usage": r'Processor\s+Busy\s*:\s*(\d+)%', # Parsed out via explicit array performance logs
            "os_version": r'Microcode\s+Version\s*:\s*(\S+)',
            "model": r'Model\s*:\s*(.*)',
            "mac_address": r'MAC\s+Address\s*:\s*([0-9a-fA-F:]+)',
            "hostname": r'Storage\s+Name\s*:\s*(\S+)',
            "serial_number": r'Serial\s+Number\s*:\s*(\d+)', # Grabs the core hardware array backplane SN
            # --- Added Regex Patterns for AI Parsing ---
            "health_status": r'Status\s*:\s*(Normal|Block|Degraded)', # Hitachi flags bad components as 'Block' or 'Degraded'
            "pool_overcommit": r'Subscription\s*\(%\)\s*:\s*(\d+)', # Targets overprovisioning risk thresholds
            "gad_split": r'PairStatus\s*:\s*(PSUS|PDOS)' # Identifies Global-Active Device replication splits or data loss path states
        },
        device_types=["storage"]
    ),
    "netapp_ontap": VendorProfile(
        "NetApp", "NetApp, Inc.", "shell", "ONTAP Storage (AFF/FAS)",
        commands={
            "terminal_length": "rows 0; set -privilege advanced -confirm off", # Bypasses CLI pagination and enters non-interactive advanced privilege mode
            "fetch_shell_commands": [
                # --- Cluster Topology & Engine Sanity ---
                ("cluster_health", "cluster show"), # Checks identity, communication health, and quorum status of the cluster nodes
                ("node_hardware", "system node show -fields model,serial-number,version,health"), # Identifies individual node health, OS releases, and serial configurations
                ("hardware_env", "system node environment sensors show"), # Monitors physical fans, power supplies, voltages, and thermal states
                ("active_alerts", "system health alert show"), # Fast-path triage: immediately captures any degraded subsystem alerts
                ("event_log", "event log show -severity ERROR,CRITICAL -count 50"), # Collects the last 50 high-priority system event log entries
                
                # --- Storage Tiers (Aggregates & Physical Media) ---
                ("aggregate_status", "storage aggregate show -state !online"), # Instantly catches faulted, degraded, or offline storage pools
                ("disk_health", "storage disk show -state broken,failed,unusable"), # Directly targets and lists physically bad storage media
                ("spare_disks", "storage disk show -container-type spare"), # Verifies if active zeroed hot-spares exist to sustain disk failures
                
                # --- Logical Volumes & Thin Provisioning ---
                ("volume_faults", "volume show -state !online"), # Pinpoints data volumes that have dropped offline or become unavailable
                ("volume_space", "volume show -percent-used >85 -fields percent-used,available"), # Identifies filesystems approaching absolute capacity depletion
                ("efficiency_status", "volume efficiency show"), # Tracks deduplication and compression engine execution logs
                
                # --- Logical Interfaces & Multipathing ---
                ("lif_status", "network interface show"), # Monitors logical data paths (LIFs), link operational states, and home-node alignment
                ("failover_groups", "network interface failover-groups show"), # Validates data path routing options during link failures
                ("fc_adapters", "network fcp adapter show"), # Checks speed, WWN addresses, and connection metrics for Fibre Channel fabrics
                ("iscsi_sessions", "iscsi session show"), # Verifies software initiator logins from external SAN host systems
                
                # --- High Availability & Clustering ---
                ("failover_status", "storage failover show") # Confirms if cluster nodes are capable of taking over for their HA partner
            ],
            "fetch_config": "system configuration backup show", # Locates operational node configuration system metadata files
            "save_config": "system configuration backup create -node * -backup-name AI_Diag_Safe", # Generates an on-demand cluster configuration backup snapshot
            "exit": "exit"
        },
        snmp_patterns={"vendor_keywords": ["netapp", "ontap", "dataontap"], "model_regex": r'(AFF|FAS)\d+', "version_regex": r'NetApp\s+Release\s+(\S+)'},
        cli_patterns={
            "cpu_usage": r'Average\s+CPU\s+utilization\s*:\s*(\d+)%', # Parsed if pulling from statistical node metrics
            "os_version": r'Release\s*:\s*(\S+)', # Maps the exact ONTAP release track (e.g., 9.14.1)
            "model": r'Model\s*:\s*(\S+)', # Scraped directly from node properties
            "mac_address": r'MAC\s+Address\s*:\s*([0-9a-fA-F:]+)',
            "hostname": r'Cluster\s+Name\s*:\s*(\S+)',
            "serial_number": r'Serial\s+Number\s*:\s*(\S+)', # Targets the system backplane controller chassis asset tag
            # --- Added Regex Patterns for AI Parsing ---
            "alert_triggered": r'Severity\s*:\s*(ERROR|CRITICAL)', # Triggers immediate parsing escalations on the active alerts table
            "failover_blocked": r'Takeover\s+Possible\s*:\s*false', # Flags if an active node cannot safely absorb its partner's workload
            "disk_failed": r'(\d+)\s+broken' # Catches physical hardware disk failures instantly
        },
        device_types=["storage"]
    ),
    "cisco_ucs": VendorProfile(
        "Cisco", "Cisco Systems, Inc.", "shell", "Cisco UCS Server (UCSM CLI)",
        commands={
            "terminal_length": "terminal length 0", # Disables CLI pagination for seamless automated block ingestion
            "fetch_shell_commands": [
                # --- Infrastructure & Fabric Interconnect Sanity ---
                ("cluster_status", "show cluster state"), # Verifies the high-availability and quorum status of Fabric Interconnects A and B
                ("overall_faults", "show fault"), # Fast-path triage: captures all active critical and major system alerts across the chassis environment
                ("firmware_inventory", "show firmware pack-image"), # Audits running firmware images against catalog guidelines
                
                # --- Blade & Rack Server Hardware Layer ---
                ("chassis_inventory", "show chassis"), # Maps out physical chassis frames, power distribution networks, and fan module states
                ("server_status", "show server status"), # Lists the hardware operability state and discovery phase of all blades/nodes
                ("server_inventory", "show server inventory"), # Detailed hardware specification overview (CPUs, DIMM slots, motherboard layouts)
                ("memory_health", "show server memory"), # Isolates single-bit and multi-bit ECC memory faults per DIMM slot location
                
                # --- Logical Abstraction Layer (Service Profiles) ---
                ("service_profiles", "show service-profile brief"), # Tracks all logical server identities and their current operational health
                ("sp_association_faults", "show service-profile circuit"), # Identifies exact structural failure points when a profile fails to bind to physical hardware
                
                # --- Network and Storage Fabric Multi-Pathing ---
                ("fcoe_san_links", "show fcoe-uplink"), # Evaluates Fibre Channel over Ethernet edge interfaces running toward core storage arrays
                ("vif_paths", "show server vif"), # Inspects Virtual Interface (VIF) pathways mapping physical vNICs to Fabric Interconnect backplanes
                ("interface_errors", "show interface brief") # Monitors underlying 10/25/40/100GbE physical link drops or CRC error bottlenecks
            ],
            "fetch_config": "show configuration", # Exports complete active UCS system profile definitions and environmental matrices
            "save_config": "copy running-config startup-config", # Non-destructive structural command to commit runtime state profiles safely
            "exit": "exit"
        },
        snmp_patterns={"vendor_keywords": ["cisco", "ucs", "fabric interconnect"], "model_regex": r'UCS-\d{4}\S*', "version_regex": r'UCSM\s+Release\s+(\S+)'},
        cli_patterns={
            "cpu_usage": r'Load\s+Average\s*:\s*(\d+\.\d+)', # Parsed directly from underlying fabric supervisor nodes
            "os_version": r'Infrastructure\s+Software\s+Bundle\s*:\s*(\S+)', # Correlates with the global UCS running release track (e.g., 4.2(3b))
            "model": r'Product\s+Name\s*:\s*(.*)|Model\s*:\s*(\S+)', # Distinguishes between UCS B-Series, C-Series, or X-Series frames
            "mac_address": r'([0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2})',
            "hostname": r'System\s+Name\s*:\s*(\S+)',
            "serial_number": r'Serial\s+\(A\)\s*:\s*(\S+)|Chassis\s+Serial\s*:\s*(\S+)', # Pulls the hardware backplane tracking asset label
            # --- Added Regex Patterns for AI Parsing ---
            "fault_severity": r'Severity\s*:\s*(Critical|Major)', # Flags actionable hardware exceptions requiring field dispatching
            "association_state": r'Assoc\s+State\s*:\s*(Failed|Throttled)', # Catches service profile instantiation breaks immediately
            "link_down": r'(\S+)\s+is\s+down' # Catches physical connectivity disruptions directly inside the fabric plane
        },
        device_types=["server"]
    ),
    "f5_bigip": VendorProfile(
        "F5", "F5 Networks, Inc.", "shell", "BIG-IP Load Balancer (TMSH)",
        commands={
            "terminal_length": "modify cli preference display-threshold 0 pager disabled", # Completely disables screen paging and line-count thresholds for raw string parsing
            "fetch_shell_commands": [
                # --- System Identity & Global Plane Sanity ---
                ("sys_info", "show sys hardware"), # Extracts platform model, CPU components, chassis serials, and fan/PSU states
                ("os_version", "show sys version"), # Returns current TMOS software version, build tracks, and hotfix history
                ("failover_status", "show sys cm failover-status"), # Verifies HA state (Active, Standby, Sync-Failed) across the device group
                ("tmm_performance", "show sys performance system"), # Captures deep real-time TMM CPU and memory allocation metrics
                
                # --- Network Layer & Virtual Wire Diagnostics ---
                ("interface_status", "show net interface brief"), # Checks physical link availability, line speeds, and media settings
                ("vlan_mappings", "show net vlan"), # Maps structural internal/external tag properties to physical trunks
                ("arp_table", "show net arp"), # Displays network layer address resolutions to pinpoint gateway issues
                ("routing_table", "show net route"), # Inspects the underlying TMM routing matrix
                
                # --- Application Delivery Layer (The Core Traffic Plane) ---
                ("virtual_servers", "show ltm virtual brief"), # High-level inventory: returns status of all Virtual Servers (VIPs)
                ("pools_status", "show ltm pool"), # Breaks down server pool operational states and active load-balancing algorithms
                ("pool_members", "show ltm pool members field-fmt"), # Generates flat structural layouts of backend nodes, ports, and health checks
                ("node_health", "show ltm node brief"), # Identifies global server node reachability states across all pools
                
                # --- Connection Telemetry & Health Monitor Traces ---
                ("active_connections", "show sys connection"), # Dumps active stateful connection tables (Warning: can be dense)
                ("monitor_status", "show sys log ltm lines 50") # Ingests last 50 local traffic log lines to find health monitor flapping errors
            ],
            "fetch_config": "list ltm virtual", # Exports the active declarative application delivery architecture maps
            "save_config": "save sys config", # Safely commits runtime memory profiles into the permanent system boot files
            "exit": "quit"
        },
        snmp_patterns={"vendor_keywords": ["f5", "big-ip", "tmos", "bigip"], "model_regex": r'BIG-IP\s+(\d+)', "version_regex": r'BIG-IP\s+Version\s+(\d+\.\d+\.\d+)'},
        cli_patterns={
            "cpu_usage": r'TMM\s+CPU\s+Usage\s*\|\s*(\d+)', # Specifically targets Data Plane CPU allocation metrics
            "os_version": r'Version\s*:\s*(\S+)', # Extracted cleanly out of show sys version blocks
            "model": r'Marketing\s+Name\s*:\s*(.*)', # e.g., BIG-IP i4600, BIG-IP 15000VS
            "mac_address": r'([0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2})',
            "hostname": r'Sys\s+::\s*(\S+)', # Strips local management host mapping parameters
            "serial_number": r'Chassis\s+Serial\s*:\s*(\S+)', # Captures the primary hardware platform license/asset tag
            # --- Added Regex Patterns for AI Parsing ---
            "vip_status": r'Availability\s*:\s*(offline|unavailable|unknown)', # Immediately isolates broken frontend endpoints
            "ha_state": r'Status\s*:\s*(\S+)', # Yields 'ACTIVE', 'STANDBY', or 'CHANGING'
            "monitor_down": r'Node\s+(\S+)\s+monitor\s+status\s+down' # Catches failing backend server nodes inside log streams
        },
        device_types=["loadbalancer"]
    ),

    "aruba_aos": VendorProfile(
        "Aruba",
        "Aruba Networks",
        "shell",
        "ArubaOS-Switch",

        commands={
            "terminal_length": "no page",

            "fetch_shell_commands": [
                ("ver", "show system"),
                ("cpu", "show system"),
                ("mem", "show system"),
                ("interfaces", "show interface brief"),
                ("routing", "show ip route"),
                ("neighbors", "show lldp neighbors"),
                ("mac_table", "show mac-address-table"),
                ("arp", "show arp"),
                ("config", "show running-config")
            ],

            "fetch_config":"show running-config",

            "save_config":"write memory",

            "exit":"exit"
        },
        snmp_patterns={

            "vendor_keywords":[
                "aruba",
                "procurve",
                "hewlett packard",
                "hewlett-packard",
                "hpe"
            ],

            "model_regex":[
                r'Aruba\s+(\S+)',
                r'JL\d+[A-Z]?',
                r'J\d+[A-Z]?'
            ],

            "version_regex":[
                r'Revision\s+(\S+)',
                r'Firmware\s+(\S+)'
            ]
        },
        cli_patterns={

            "cpu_usage": r"CPU Util \(%\)\s*:\s*(\d+)",

            "mem_usage_pct": r"Memory Usage \(%\)\s*:\s*(\d+)",

            "hostname": r"Hostname\s*:\s*(.+)",

            "model": r"Product Name\s*:\s*(.+)",

            "serial_number": r"Chassis Serial Nbr\s*:\s*(\S+)",

            "mac_address": r"Base MAC Address\s*:\s*([0-9A-Fa-f-]+)",

            "os_version": r"ArubaOS-CX Version\s*:\s*(.+)",

            "uptime": r"Up Time\s*:\s*(.+)"
        },
        device_types=["switch", "router"]
    ),        
    
    "linux_server": VendorProfile(
        "Linux Server", "Enterprise Linux Engine", "exec", "Generic Server Rack",
        commands={
            "fetch_exec_commands": {
                "cpu": "top -bn1 | grep 'Cpu(s)'",
                "mem": "free -m",
                "disk": "df / --output=pcent | tail -n 1",
                "uptime": "cat /proc/uptime",
                "os": "uname -sr",
                "mac": "cat /sys/class/net/$(ip route show | grep default | awk '{print $5}')/address 2>/dev/null || cat /sys/class/net/eth0/address 2>/dev/null",
                "hostname": "hostname",
                "serial": "cat /etc/machine-id 2>/dev/null"
            }
        },
        cli_patterns={
            "cpu_idle": r'(\d+\.\d+)\s*id',
            "mem_total": r'Mem:\s+(\d+)',
            "mem_used": r'Mem:\s+\d+\s+(\d+)',
            "disk_usage": r'(\d+)%',
            "uptime_seconds": r'^([\d\.]+)'
        },
        device_types=["server", "storage"]
    )
}

# def get_vendor_profile(vendor: str) -> VendorProfile:
    # try:
    #     logger.info(f"get_vendor_profile() called with vendor={vendor}")
    #     key = vendor.lower().strip() if vendor else "generic"
    #     if key in ["dell", "hp", "neutanics", "huwaei", "lenovo", "supermicro"]:
    #         key = "linux_server"
    #     elif key in ["hpe", "hp", "ilo", "proliant"]:
    #         key = "hpe_ilo"
    #     elif key in ["huawei", "ibmc", "imana", "fusionserver"]:
    #         key = "huawei_ibmc"
    #     elif key in ["huawei", "oceanstor", "dorado"]:
    #         key = "huawei_oceanstor"       
    #     elif key in ["cisco", "catalyst", "nexus", "ios", "ios-xe", "ios-xr"]:
    #         key = "cisco"
    #     elif key in ["juniper", "junos", "ex-series", "mx-series", "srx-series"]:
    #         key = "juniper"
    #     elif key in ["arista", "eos", "cEOS"]:
    #         key = "arista"
    #     elif key in ["vmware", "vcenter", "esxi", "vsphere"]:
    #         key = "vmware_vcenter"
    #     elif key in ["oracle", "oci", "oracle cloud"]:
    #         key = "oracle_cloud_oci"
    #     elif key in ["oracle database", "rdbms", "sqlplus"]:
    #         key = "oracle_database"
    #     elif key in ["aws", "ec2", "amazon web services", "amazon"]:
    #         key = "aws_ec2_cloud"
    #     elif key in ["azure", "microsoft azure", "virtualmachine"]:
    #         key = "azure_cloud"
    #     elif key in ["linux", "ubuntu", "centos", "debian", "redhat", "rhel"]:
    #         key = "linux_server"
    #     elif key in ["windows", "winserver", "win"]:
    #         key = "windows_server"
    #     elif key in ["supermicro", "supermicro"]:
    #         key = "linux_server"
    #     elif key in ["emc", "dell emc", "powermax", "vmax","unity", "isilon", "vplex", "powerstore", "xtremio", "ecs", "vblock", "vscaleio", "vxrail", "vxdirector", "vxdirector", "vxdirector", "vxdirector"]:
    #         key = "dell_emc"
    #     elif key in ["netapp", "ontap", "filer", "c-mode", "e-series"]:
    #         key = "netapp"
    #     elif key in ["huawei", "oceanstor", "dorado"]:
    #         key = "huawei_oceanstor"
    #     elif key in ["hpe", "3par", "nimble", "primera"]:
    #         key = "hpe_storage"
    #     elif key in ["hitachi", "vantara", "vsp", "vsp-f", "vsp-g"]:
    #         key = "hitachi_storage" 
    #     elif key in ["cisco", "ucs", "unified computing system"]:
    #         key = "cisco_ucs"
    #     elif key in ["f5", "big-ip", "tmos"]:
    #         key = "f5_bigip"
    #     elif key in ["fortigate", "fortinet"]:
    #         key = "fortinet"
    #     elif key in ["aruba switch", "aruba"]:
    #          key = "aruba_aos"
    #     elif key in ["paloalto", "palo alto", "pan-os"]:
    #         key = "paloalto"
    #     else:
    #         key = "generic" 
    #     base_profile = VENDOR_PROFILES.get(key)
    #     base_profile.vendor_display_name = vendor.upper()
    #     return base_profile
    # except Exception:
    #     logger.exception("Exception inside get_vendor_profile()")
    #     raise    
# Insertion Date : 21/07/2026 - Modified Vendor Profiling 

def get_vendor_profile(vendor: str) -> VendorProfile:
    try:
        logger.info(f"get_vendor_profile() called with vendor={vendor}")
        if not vendor:
            vendor = "GENERIC"
            
        key = str(vendor).lower().strip()
        
        # Map dynamic inputs to strict vendor profile schemas
        if key in ["dell", "hp", "lenovo", "supermicro"]: key = "linux_server"
        elif key in ["cisco", "catalyst", "nexus", "ios"]: key = "cisco"
        elif key in ["juniper", "junos", "ex-series"]: key = "juniper"
        elif key in ["fortigate", "fortinet"]: key = "fortinet"
        elif key in ["paloalto", "palo alto", "pan-os"]: key = "paloalto"
        elif key in ["aruba switch", "aruba", "aruba_aos"]: key = "aruba_aos"
        elif key in ["windows", "winserver", "win"]: key = "windows_os"
        else: key = "linux_server" # Default robust fallback
            
        base_profile = VENDOR_PROFILES.get(key)
        if base_profile is None:
            base_profile = VENDOR_PROFILES.get("linux_server")

        import copy
        profile_copy = copy.deepcopy(base_profile)
        profile_copy.vendor_display_name = str(vendor).upper()
        return profile_copy
    except Exception:
        logger.exception("Exception inside get_vendor_profile()")
        raise

# def get_vendor_profile(vendor: str) -> VendorProfile:
#     try:
#         logger.info(f"get_vendor_profile() called with vendor={vendor}")
#         if not vendor:
#             vendor = "GENERIC"
            
#         key = str(vendor).lower().strip()
        
#         if key in ["dell", "hp", "neutanics", "huwaei", "lenovo", "supermicro"]:
#             key = "linux_server"
#         elif key in ["hpe", "ilo", "proliant"]:
#             key = "hpe_ilo"
#         elif key in ["huawei", "ibmc", "imana", "fusionserver"]:
#             key = "huawei_ibmc"
#         elif key in ["huawei_oceanstor", "oceanstor", "dorado"]:
#             key = "huawei_oceanstor"       
#         elif key in ["csico", "cisco", "catalyst", "nexus", "ios", "ios-xe", "ios-xr"]:
#             key = "cisco"
#         elif key in ["juniper", "junos", "ex-series", "mx-series", "srx-series"]:
#             key = "juniper"
#         elif key in ["arista", "eos", "ceos"]:
#             key = "arista"
#         elif key in ["vmware", "vcenter", "esxi", "vsphere"]:
#             key = "vmware_vcenter"
#         elif key in ["oracle", "oci", "oracle cloud"]:
#             key = "oracle_cloud_oci"
#         elif key in ["oracle database", "rdbms", "sqlplus"]:
#             key = "oracle_database"
#         elif key in ["aws", "ec2", "amazon web services", "amazon"]:
#             key = "aws_ec2_cloud"
#         elif key in ["azure", "microsoft azure", "virtualmachine"]:
#             key = "azure_cloud"
#         elif key in ["linux", "ubuntu", "centos", "debian", "redhat", "rhel"]:
#             key = "linux_server"
#         elif key in ["windows", "winserver", "win"]:
#             key = "windows_os"
#         elif key in ["emc", "dell emc", "powermax", "vmax", "unity"]:
#             key = "dell_emc_vmax"
#         elif key in ["netapp", "ontap", "filer"]:
#             key = "netapp_ontap"
#         elif key in ["hitachi", "vantara", "vsp"]:
#             key = "hitachi_vsp" 
#         elif key in ["ucs", "cisco_ucs"]:
#             key = "cisco_ucs"
#         elif key in ["f5", "big-ip", "tmos", "f5_bigip"]:
#             key = "f5_bigip"
#         elif key in ["fortigate", "fortinet"]:
#             key = "fortinet"
#         elif key in ["aruba switch", "aruba", "aruba_aos"]:
#             key = "aruba_aos"
#         elif key in ["paloalto", "palo alto", "pan-os"]:
#             key = "paloalto"
#         else:
#             key = "linux_server" # Default robust fallback
            
#         base_profile = VENDOR_PROFILES.get(key)
#         if base_profile is None:
#             base_profile = VENDOR_PROFILES.get("linux_server")

#         import copy
#         profile_copy = copy.deepcopy(base_profile)
#         profile_copy.vendor_display_name = str(vendor).upper()
#         return profile_copy
#     except Exception:
#         logger.exception("Exception inside get_vendor_profile()")
#         raise

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===================== DATA MODELS =====================

class DiscoveryMethod(str, Enum):
    ARP_SCAN = "arp_scan"
    SNMP_DISCOVERY = "snmp_discovery"
    PING_SWEEP = "ping_sweep"
    PORT_SCAN = "port_scan"
    

class DeviceStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"

@dataclass
class DiscoveredDevice:
    ip_address: str
    mac_address: Optional[str] = None
    hostname: Optional[str] = None
    device_type: Optional[str] = None
    vendor: Optional[str] = None
    discovery_method: Optional[str] = None
    snmp_info: Optional[Dict] = None
    open_ports: Optional[List[int]] = None
    discovered_at: Optional[str] = None
    status: str = "online"

@dataclass
class SNMPResult:
    ip_address: str
    oid: str
    value: Any
    value_type: str
    timestamp: str

@dataclass
class DiscoveryJob:
    id: str
    status: str  # pending, running, completed, failed, cancelled
    methods: List[str]
    subnet: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    devices_found: int = 0
    progress: int = 0
    error: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None

# ===================== SNMP SERVICE =====================
import re
class SNMPService:
    """Real SNMP polling service using pysnmp"""
    
    # Common SNMP OIDs
    OIDS = {
        'sysDescr': '1.3.6.1.2.1.1.1.0',
        'sysObjectID': '1.3.6.1.2.1.1.2.0',
        'sysUpTime': '1.3.6.1.2.1.1.3.0',
        'sysContact': '1.3.6.1.2.1.1.4.0',
        'sysName': '1.3.6.1.2.1.1.5.0',
        'sysLocation': '1.3.6.1.2.1.1.6.0',
        'ifNumber': '1.3.6.1.2.1.2.1.0',
        'ifDescr': '1.3.6.1.2.1.2.2.1.2',
        'ifOperStatus': '1.3.6.1.2.1.2.2.1.8',
        'ifInOctets': '1.3.6.1.2.1.2.2.1.10',
        'ifOutOctets': '1.3.6.1.2.1.2.2.1.16',
        'hrSystemUptime': '1.3.6.1.2.1.25.1.1.0',
        'hrMemorySize': '1.3.6.1.2.1.25.2.2.0',
    }
    
    def __init__(self):
        self.polling_active = False
        self.poll_interval = 30  # seconds
        self.poll_thread = None
    
    def _extract_model(self, sys_descr: str, profile: VendorProfile) -> str:
        """Dynamically extract hardware model using the profile's patterns."""
        patterns = profile.snmp_patterns.get("model_regex", [])
        # Support both a single string pattern or a collection of patterns
        if isinstance(patterns, str):
            patterns = [patterns]
            
        for pattern in patterns:
            match = re.search(pattern, sys_descr, re.IGNORECASE)
            if match:
                # Return the first captured group that isn't empty, or the full match
                captured = next((g for g in match.groups() if g), match.group(0))
                return f"{profile.name} {captured.strip()}"
        return f"{profile.name} Generic"

    def _extract_version(self, sys_descr: str, profile: VendorProfile) -> str:
        """Dynamically extract firmware/OS version using profile patterns."""
        patterns = profile.snmp_patterns.get("version_regex", [])
        if isinstance(patterns, str):
            patterns = [patterns]
            
        for pattern in patterns:
            match = re.search(pattern, sys_descr, re.IGNORECASE)
            if match:
                captured = next((g for g in match.groups() if g), match.group(0))
                return captured.strip()
        return "Unknown Version"

    def _detect_device_type(self, sys_descr: str, profile: VendorProfile) -> str:
        """Cross-reference device type categories against profile keywords."""
        sys_descr_lower = sys_descr.lower()
        
        # Priority mapping loop matching keywords array defined inside profile
        for device_type in profile.device_types:
            if device_type in sys_descr_lower:
                return device_type
                
        # Structural structural fallback loops
        if "switch" in sys_descr_lower: return "switch"
        if "router" in sys_descr_lower: return "router"
        if "firewall" in sys_descr_lower or "asa" in sys_descr_lower: return "firewall"
        if "storage" in sys_descr_lower or "san" in sys_descr_lower: return "storage"
        if "server" in sys_descr_lower: return "server"
        
        return "other"

    async def snmp_get(self, ip: str, community: str, oid: str, port: int = 161, timeout: int = 2) -> Optional[SNMPResult]:
        """Perform SNMP GET operation safely across modern PySNMP structures."""
        try:
            try:
                from pysnmp.hlapi.asyncio import (
                    SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
                    ObjectType, ObjectIdentity, get_cmd
                )
                asyncio_variant = True
            except Exception:
                # Fallback to synchronous API if asyncio variant is unavailable
                from pysnmp.hlapi import (
                    SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
                    ObjectType, ObjectIdentity, getCmd as get_cmd
                )
                asyncio_variant = False
            
            snmp_engine = SnmpEngine()
            object_type = ObjectType(ObjectIdentity(oid))

            # Added ContextData() into the positional argument chain to bypass contextName errors
            if asyncio_variant:
                iterator = await get_cmd(
                    snmp_engine,
                    CommunityData(community),
                    await UdpTransportTarget.create((ip, port), timeout=5, retries=2),
                    ContextData(),
                    object_type
                )
            else:
                # run synchronous get in executor to avoid blocking
                loop = asyncio.get_event_loop()
                def sync_call():
                    errorIndication, errorStatus, errorIndex, varBinds = next(
                        get_cmd(
                            snmp_engine,
                            CommunityData(community),
                            UdpTransportTarget((ip, port), timeout=5, retries=2),
                            ContextData(),
                            object_type
                        )
                    )
                    return (errorIndication, errorStatus, errorIndex, varBinds)

                iterator = await loop.run_in_executor(None, sync_call)

            errorIndication, errorStatus, errorIndex, varBinds = iterator
            logger.info(f"{ip} " f"errorIndication={errorIndication} " f"errorStatus={errorStatus}")
            logger.info(f"SNMP GET {ip} oid={oid}")
            if errorIndication or errorStatus:
                return None
                
            for varBind in varBinds:
                oid_str, value = varBind
                logger.info(f"{ip} SUCCESS {value}")
                return SNMPResult(
                    ip_address=ip,
                    oid=str(oid_str),
                    value=str(value),
                    value_type=type(value).__name__,
                    timestamp=datetime.now(timezone.utc).isoformat()
                )
            logger.info(f"SNMP GET {ip} oid={oid}")
        except Exception as e:
            logger.exception(f"SNMP GET failed for {ip}: {e}")
            return None

    async def snmp_walk(self, ip: str, community: str, oid: str, port: int = 161) -> List[SNMPResult]:
        """Perform SNMP WALK operation"""
        results = []
        try:
            
            try:
                from pysnmp.hlapi.asyncio import (
                    SnmpEngine, CommunityData, UdpTransportTarget,
                    ObjectType, ObjectIdentity, bulk_walk_cmd
                )
                bulk_walk_command = bulk_walk_cmd
                snmp_engine = SnmpEngine()

                async for errorIndication, errorStatus, errorIndex, varBinds in bulk_walk_command(
                    snmp_engine,
                    CommunityData(community),
                    await UdpTransportTarget.create((ip, port), timeout=2, retries=1),
                    0, 25,  # non-repeaters, max-repetitions
                    ObjectType(ObjectIdentity(oid)),
                    lexicographicMode=False
                ):
                    if errorIndication or errorStatus:
                        break

                    for varBind in varBinds:
                        oid_str, value = varBind
                        results.append(SNMPResult(
                            ip_address=ip,
                            oid=str(oid_str),
                            value=str(value),
                            value_type=type(value).__name__,
                            timestamp=datetime.now(timezone.utc).isoformat()
                        ))
            except Exception:
                # Fallback to synchronous walk using hlapi if asyncio variant missing
                try:
                    from pysnmp.hlapi import (
                        SnmpEngine, CommunityData, UdpTransportTarget,
                        ObjectType, ObjectIdentity, nextCmd
                    )
                    snmp_engine = SnmpEngine()
                    loop = asyncio.get_event_loop()

                    def sync_walk():
                        res = []
                        for (errorIndication, errorStatus, errorIndex, varBinds) in nextCmd(
                            snmp_engine,
                            CommunityData(community),
                            UdpTransportTarget((ip, port), timeout=2, retries=1),
                            ObjectType(ObjectIdentity(oid)),
                            lexicographicMode=False
                        ):
                            if errorIndication or errorStatus:
                                break
                            for varBind in varBinds:
                                oid_str, value = varBind
                                res.append((oid_str, value))
                        return res

                    walk_result = await loop.run_in_executor(None, sync_walk)
                    for oid_str, value in walk_result:
                        results.append(SNMPResult(
                            ip_address=ip,
                            oid=str(oid_str),
                            value=str(value),
                            value_type=type(value).__name__,
                            timestamp=datetime.now(timezone.utc).isoformat()
                        ))
                except Exception as e:
                    logger.error(f"SNMP WALK fallback failed for {ip}: {e}")
        except Exception as e:
            logger.error(f"SNMP WALK failed for {ip}: {e}")

        return results
    
    # Inside SNMPService class:
    async def get_device_info(self, ip: str, community: str) -> Dict[str, Any]:
        info = {'ip_address': ip, 'snmp_reachable': False}
        
        # Basic system info
        for name, oid in [('sysDescr', self.OIDS['sysDescr']), ('sysObjectID', self.OIDS['sysObjectID']), ('sysName', self.OIDS['sysName']),('sysLocation', self.OIDS['sysLocation']),]:
            result = await self.snmp_get(ip, community, oid)
            if result:
                info['snmp_reachable'] = True
                info[name] = result.value

        if not info.get('snmp_reachable'):
            return info

        sys_descr = info.get('sysDescr', '').lower()
        
        # Detect vendor dynamically
        detected_vendor = "unknown"
        for vname, profile in VENDOR_PROFILES.items():
            if any(kw in sys_descr for kw in profile.snmp_patterns.get('vendor_keywords', [])):
                detected_vendor = vname
                break
        logger.info(f"Detected vendor: {detected_vendor}")
        logger.info("Before get_vendor_profile")
        profile = get_vendor_profile(detected_vendor)
        logger.info("After get_vendor_profile")
        logger.info(f"Profile.name = {profile.name}")
        logger.info(f"Profile.display = {profile.vendor_display_name}")
        info['vendor'] = profile.name
        info['model'] = self._extract_model(sys_descr, profile)
        info['os_version'] = self._extract_version(sys_descr, profile)
        info['device_type'] = self._detect_device_type(sys_descr, profile)
        logger.info(f"SNMP INFO RETURN: {info}")
        return info
    
    async def poll_device(self, ip: str, community: str, oids: List[str] = None) -> Dict[str, Any]:
        """Poll a single device for metrics"""
        if oids is None:
            oids = list(self.OIDS.values())[:6]  # Basic system OIDs
            
        results = {}
        for oid in oids:
            result = await self.snmp_get(ip, community, oid)
            if result:
                results[oid] = asdict(result)
                
        return {
            'ip_address': ip,
            'polled_at': datetime.now(timezone.utc).isoformat(),
            'results': results,
            'success': len(results) > 0
        }


# ===================== NETWORK DISCOVERY SERVICE =====================

class NetworkDiscoveryService:
    """Real-time network device discovery using multiple methods"""
    
    def __init__(self):
        self.active_jobs: Dict[str, DiscoveryJob] = {}
        self.discovered_devices: Dict[str, DiscoveredDevice] = {}
        
        # Determine operating system parameters once during initialization
        self.current_os = platform.system().lower()
        self._set_ping_flags()
    
    def _set_ping_flags(self):
        """Configure native ping binary flags dynamically based on host OS."""
        if "windows" in self.current_os:
            # -n: count, -w: timeout in milliseconds
            self.ping_cmd_base = ['ping', '-n', '1', '-w', '1000']
        elif "darwin" in self.current_os:  # macOS
            # -c: count, -t: timeout in seconds
            self.ping_cmd_base = ['ping', '-c', '1', '-t', '1']
        else:
            # Linux fallback
            self.ping_cmd_base = ['ping', '-c', '1', '-W', '1']
        
    def get_local_subnets(self) -> List[str]:
        """Get all local network subnets with validation against broken /0 masks"""
        subnets = []
        try:
            for iface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(iface)
                if netifaces.AF_INET in addrs:
                    for addr in addrs[netifaces.AF_INET]:
                        ip = addr.get('addr')
                        netmask = addr.get('netmask')
                        if ip and netmask and not ip.startswith('127.'):
                            # Calculate subnet
                            ip_parts = [int(x) for x in ip.split('.')]
                            mask_parts = [int(x) for x in netmask.split('.')]
                            network = '.'.join(str(ip_parts[i] & mask_parts[i]) for i in range(4))
                            
                            # Determine CIDR
                            cidr = sum(bin(x).count('1') for x in mask_parts)
                            
                            # --- ENFORCED DOCKER SANITY CHECK ---
                            # If a mask resolves to a broken /0, safely force a fallback /24 context
                            if cidr == 0:
                                logger.warning(f"Detected invalid /0 CIDR mask on interface {iface}. Adjusting to standard /24 block.")
                                cidr = 24
                                # Correct the base alignment representation block
                                ip_split = ip.split('.')
                                network = f"{ip_split[0]}.{ip_split[1]}.{ip_split[2]}.0"
                            
                            subnets.append(f"{network}/{cidr}")
        except Exception as e:
            logger.error(f"Failed to get local subnets safely: {e}")     
        return subnets
    
    async def ping_host(self, ip: str, timeout: int = 1) -> bool:
        """Ping a host to check if it's alive (Cross-Platform)"""
        try:
            cmd = self.ping_cmd_base + [str(ip)]
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=timeout + 1
            )
            return result.returncode == 0
        except Exception:
            return False
    
    async def ping_sweep(self, subnet: str, progress_callback=None) -> List[DiscoveredDevice]:
        """Perform a cross-platform ping sweep optimized against DNS timeout leaks"""
        devices = []
        
        try:
            import ipaddress
            network = ipaddress.ip_network(subnet, strict=False)
            hosts = list(network.hosts())
            
            total = len(hosts)
            if total == 0:
                return devices
                
            completed = 0
            max_workers = 5
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                def ping_sync(ip):
                    try:
                        # Cross-platform safe execution command array
                        logger.info(f"Ping command base: {self.ping_cmd_base}")
                        cmd = self.ping_cmd_base + [str(ip)]
                        result = subprocess.run(
                            cmd,
                            capture_output=True,
                            timeout=2  # Snappy timeout constraint
                        )
                        logger.info(f"{ip} -> rc={result.returncode}\n"
                                    f"stdout:\n{result.stdout.decode(errors='ignore')}\n"
                                    f"stderr:\n{result.stderr.decode(errors='ignore')}"
                                    )
                        return str(ip) if result.returncode == 0 else None
                    except Exception as e:
                        logger.exception(f"Ping failed for {ip}: {e}")
                        return None
                
                futures = {executor.submit(ping_sync, ip): ip for ip in hosts}
                
                for future in concurrent.futures.as_completed(futures):
                    completed += 1
                    if progress_callback and completed % max(1, total // 100) == 0:
                        progress_callback(int(completed / total * 100))
                        
                    ip = future.result()
                    logger.info(f"Future completed -> {ip}")
                    if ip:
                        device = DiscoveredDevice(
                            ip_address=ip,
                            discovery_method=DiscoveryMethod.PING_SWEEP.value,
                            discovered_at=datetime.now(timezone.utc).isoformat()
                        )
                        devices.append(device)
            
            # --- DECOUPLED DELAY-FREE DNS RESOLUTION ---
            # Resolve hostnames *after* finding alive targets, keeping core sweeps blazing fast
            for dev in devices:
                try:
                    # Provide a very short socket timeout for the lookup
                    socket.setdefaulttimeout(0.5)
                    hostname_info = socket.gethostbyaddr(dev.ip_address)
                    dev.hostname = hostname_info[0]
                except:
                    dev.hostname = f"Host-{dev.ip_address.replace('.', '-')}"
                        
            if progress_callback:
                progress_callback(100)
                        
        except Exception as e:
            logger.error(f"Ping sweep optimization breakdown: {e}")
            
        return devices
    
    async def arp_scan(self, subnet: str, progress_callback=None) -> List[DiscoveredDevice]:
        """Perform ARP scan using scapy"""
        devices = []
        
        try:
            from scapy.all import ARP, Ether, srp, conf
            conf.verb = 0  # Suppress scapy output
            
            # Create ARP request
            arp = ARP(pdst=subnet)
            ether = Ether(dst="ff:ff:ff:ff:ff:ff")
            packet = ether/arp
            
            # Send and receive
            result = srp(packet, timeout=3, verbose=0)[0]
            
            total = len(result)
            for i, (sent, received) in enumerate(result):
                if progress_callback:
                    progress_callback(int((i + 1) / max(total, 1) * 100))
                    
                device = DiscoveredDevice(
                    ip_address=received.psrc,
                    mac_address=received.hwsrc,
                    discovery_method=DiscoveryMethod.ARP_SCAN.value,
                    discovered_at=datetime.now(timezone.utc).isoformat()
                )
                
                # Try to get vendor from MAC
                device.vendor = self._get_mac_vendor(received.hwsrc)
                
                # Try to get hostname
                try:
                    hostname = socket.gethostbyaddr(received.psrc)[0]
                    device.hostname = hostname
                except:
                    pass
                    
                devices.append(device)
                
        except PermissionError:
            logger.error("ARP scan requires root/admin privileges")
        except ImportError:
            logger.error("scapy not installed")
        except Exception as e:
            logger.error(f"ARP scan failed: {e}")
            
        return devices
    
    def _get_mac_vendor(self, mac: str) -> Optional[str]:
        """Get vendor name from MAC address prefix"""
        # Common MAC vendor prefixes
        vendors = {
            '00:00:0c': 'Cisco',
            '00:1a:2b': 'Cisco',
            '00:50:56': 'VMware',
            '00:0c:29': 'VMware',
            '00:15:5d': 'Microsoft Hyper-V',
            '08:00:27': 'VirtualBox',
            '52:54:00': 'QEMU/KVM',
            'b8:27:eb': 'Raspberry Pi',
            'dc:a6:32': 'Raspberry Pi',
            '00:1e:68': 'Quanta',
            'f0:1f:af': 'Dell',
            '00:25:b5': 'Dell',
            '00:14:22': 'Dell',
            '00:1a:4a': 'HP',
            '00:21:5a': 'HP',
            '3c:d9:2b': 'HP',
            '00:1c:c4': 'Juniper',
            '00:05:85': 'Juniper',
            '00:17:cb': 'Juniper',
            '00:1b:21': 'Intel',
            '00:1e:67': 'Intel',
            '3c:97:0e': 'Intel',
            '00:0f:53': 'Intel',
            '00:1b:21': 'Intel',
            '00:1e:67': 'Intel',
            '00:1f:29': 'Intel',
            "   " : 'NVidia',       
           
        }
        
        mac_prefix = mac[:8].lower()
        return vendors.get(mac_prefix)
    
    # Inside NetworkDiscoveryService class:
    # async def snmp_discovery(self, subnet: str, communities: List[str], progress_callback=None) -> List[DiscoveredDevice]:
    #     """Discover any IP Class category using clean, adaptive structural sweeps"""
    #     devices = []
    #     snmp_service = SNMPService()
        
    #     try:
    #         import ipaddress
    #         network = ipaddress.ip_network(subnet, strict=False)
    #         hosts = list(network.hosts())
            
    #         total_hosts = len(hosts)
    #         if total_hosts == 0:
    #             return devices
                
    #         total_operations = total_hosts * len(communities)
    #         completed = 0
            
    #         # Use an internal semaphore to prevent overwhelming socket descriptors on broad network blocks
    #         semaphore = asyncio.Semaphore(50)

    #         async def check_host(ip_obj, community_str):
    #             nonlocal completed
    #             async with semaphore:
    #                 ip_str = str(ip_obj)
    #                 info = await snmp_service.get_device_info(ip_str, community_str)
                    
    #                 completed += 1
    #                 if progress_callback and completed % max(1, total_operations // 100) == 0:
    #                     progress_callback(int(completed / total_operations * 100))
                        
    #                 if info.get('snmp_reachable'):
    #                     return DiscoveredDevice(
    #                         ip_address=ip_str,
    #                         hostname=info.get('sysName') or f"SNMP-{ip_str.replace('.', '-')}",
    #                         device_type=self._detect_device_type(info.get('sysDescr', '')),
    #                         vendor=info.get('vendor'), 
    #                         discovery_method=DiscoveryMethod.SNMP_DISCOVERY.value,
    #                         snmp_info=info,
    #                         discovered_at=datetime.now(timezone.utc).isoformat()
    #                     )
    #             return None

    #         # Schedule all network probes concurrently
    #         tasks = []
    #         for ip in hosts:
    #             for community in communities:
    #                 tasks.append(check_host(ip, community))

    #         results = await asyncio.gather(*tasks)
    #         # Filter out None results and remove duplicates by IP address
    #         seen_ips = set()
    #         for dev in results:
    #             if dev and dev.ip_address not in seen_ips:
    #                 seen_ips.add(dev.ip_address)
    #                 devices.append(dev)
            
    #         if progress_callback:
    #             progress_callback(100)
                        
    #     except Exception as e:
    #         logger.error(f"SNMP network class discovery failed for scope {subnet}: {e}")
            
    #     return devices
    async def snmp_discovery(self, target_ips: List[str], communities: List[str], progress_callback=None) -> List[DiscoveredDevice]:
        """Discover any IP Class category concurrently without unpacking crashes."""
        devices = []
        snmp_service = SNMPService()
        
        try:
            hosts=target_ips
            # total_hosts = len(hosts)
            # if total_hosts == 0:
            #     return devices
            # import ipaddress
            # network = ipaddress.ip_network(subnet, strict=False)
            # hosts = list(network.hosts())
            
            total_hosts = len(hosts)
            logger.info(f"SNMP will scan {len(hosts)} hosts: {hosts}")
            if total_hosts == 0:
                return devices
                
            total_operations = total_hosts * len(communities)
            completed = 0
            semaphore = asyncio.Semaphore(10)

            async def check_host(ip_obj, community_str):
                try:
                    logger.info("Inside check_host method")
                    nonlocal completed
                    async with semaphore:
                        ip_str = str(ip_obj)
                        info = await snmp_service.get_device_info(ip_str, community_str)
                        logger.info(f"{ip_str} -> {info}")
                        completed += 1
                        if progress_callback and completed % max(1, total_operations // 100) == 0:
                            progress_callback(int(completed / total_operations * 100))
                            
                        if info and info.get('snmp_reachable'):
                            raw_type = str(info.get('device_type', 'switch')).lower().strip()
                            if "switch" in raw_type: mapped_type = "switch"
                            elif "router" in raw_type: mapped_type = "router"
                            elif "firewall" in raw_type or "asa" in raw_type: mapped_type = "firewall"
                            elif "server" in raw_type: mapped_type = "server"
                            elif "storage" in raw_type or "san" in raw_type: mapped_type = "storage"
                            elif "loadbalancer" in raw_type or "f5" in raw_type: mapped_type = "loadbalancer" 
                            elif "printer" in raw_type: mapped_type = "printer"
                            elif "vmware" in raw_type or "esxi" in raw_type: mapped_type = "virtualization_host"
                            elif "linux" in raw_type: mapped_type = "linux_server"
                            elif "windows" in raw_type: mapped_type = "windows_server"
                            elif "juniper" in raw_type: mapped_type = "juniper_device"
                            elif "cisco" in raw_type: mapped_type = "cisco_device"
                            elif "oracle" in raw_type: mapped_type = "oracle_device"
                            elif "azure" in raw_type: mapped_type = "azure_device"
                            elif "Hpe_3par" in raw_type or "hpe_storage" in raw_type: mapped_type = "hpe_storage"
                            elif "netapp" in raw_type: mapped_type = "netapp_storage"
                            elif "huawei" in raw_type: mapped_type = "huawei_device"
                            elif "dell" in raw_type: mapped_type = "dell_device"
                            elif "hitachi" in raw_type: mapped_type = "hitachi_device"
                            elif "f5" in raw_type: mapped_type = "loadbalancer"
                            elif "arista" in raw_type: mapped_type = "arista_device"
                            elif "vmware" in raw_type: mapped_type = "virtualization_host"
                            elif "emc" in raw_type or "dell_emc" in raw_type: mapped_type = "dell_emc_storage"
                            elif "ucs" in raw_type or "cisco_ucs" in raw_type: mapped_type = "cisco_ucs"
                            else: mapped_type = "Generic Device"
                            logger.info(
                                f"Returning SNMP device "
                                f"{ip_str} "
                                f"vendor={info.get('vendor')} "
                                f"hostname={info.get('sysName')}"
                            )
                            return DiscoveredDevice(
                                ip_address=ip_str,
                                hostname=info.get('sysName') or f"Host-{ip_str.replace('.', '-')}",
                                device_type=mapped_type,  
                                vendor=str(info.get('vendor', 'Generic')).upper(),
                                discovery_method=DiscoveryMethod.SNMP_DISCOVERY.value,
                                snmp_info=info,
                                discovered_at=datetime.now(timezone.utc).isoformat()
                            )
                except Exception:
                    logger.exception(f"check_host failed for {ip_obj}")
                    raise

            tasks = []
            for ip in hosts:
                for community in communities:
                    tasks.append(check_host(ip, community))

            # return_exceptions=True intercepts engine crashes, stopping the ellipsis unpack break
            results = await asyncio.gather(*tasks, return_exceptions=True)
            logger.info(f"Results length = {len(results)}")
            for r in results:
                if isinstance(r, Exception):
                    logger.exception(r)
            
            seen_ips = set()
            for dev in results:
                if dev and not isinstance(dev, Exception) and dev.ip_address not in seen_ips:
                    seen_ips.add(dev.ip_address)
                    devices.append(dev)
            
            if progress_callback:
                progress_callback(100)
                        
        except Exception as e:
            logger.error(f"SNMP concurrent class discovery exception: {e}")
            
        return devices
    
    def _detect_device_type(self, sys_descr: str) -> str:
        """Detect device type from sysDescr"""
        sys_descr = sys_descr.lower()
        
        if 'cisco' in sys_descr:
            if 'router' in sys_descr or 'isr' in sys_descr:
                return 'router'
            elif 'switch' in sys_descr or 'catalyst' in sys_descr:
                return 'switch'
            elif 'asa' in sys_descr or 'firewall' in sys_descr:
                return 'firewall'
            return 'cisco_device'
        elif 'juniper' in sys_descr:
            return 'juniper_device'
        elif 'linux' in sys_descr:
            return 'linux_server'
        elif 'windows' in sys_descr:
            return 'windows_server'
        elif 'vmware' in sys_descr:
            return 'vmware_host'
        elif 'printer' in sys_descr or 'hp laserjet' in sys_descr:
            return 'printer'
        elif 'huawei' in sys_descr:
            return 'huawei_device'  
        elif 'dell' in sys_descr:
            return 'dell_device'
        elif 'hpe' in sys_descr or '3par' in sys_descr:
            return 'hpe_storage'
        elif 'netapp' in sys_descr:
            return 'netapp_storage'
        elif 'hitachi' in sys_descr:
            return 'hitachi_device'
        elif 'f5' in sys_descr:
            return 'loadbalancer'
        elif 'arista' in sys_descr:
            return 'arista_device'
        elif 'ucs' in sys_descr or 'cisco_ucs' in sys_descr:
            return 'cisco_ucs'
        elif 'emc' in sys_descr or 'dell_emc' in sys_descr:
            return 'dell_emc_storage'
        elif 'oracle' in sys_descr:
            return 'oracle_device'
        elif 'azure' in sys_descr:
            return 'azure_device'
        elif 'storage' in sys_descr or 'san' in sys_descr:
            return 'storage'    
        elif 'server' in sys_descr:
            return 'server' 
        elif 'loadbalancer' in sys_descr:
            return 'loadbalancer'
        elif 'virtualization' in sys_descr or 'hypervisor' in sys_descr:
            return 'virtualization_host'
        else:
            return 'unknown'
    
    async def port_scan(self, ip: str, ports: List[int] = None) -> List[int]:
        """Scan common ports on a host"""
        if ports is None:
            ports = [22, 23, 80, 443, 161, 162, 3389, 8080, 8443, 3306, 5432, 1521, 27017]
            
        open_ports = []
        
        for port in ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.5)
                result = sock.connect_ex((ip, port))
                if result == 0:
                    open_ports.append(port)
                sock.close()
            except:
                pass
                
        return open_ports
    
    async def run_discovery(self, job: DiscoveryJob, communities: List[str] = None, 
                           progress_callback=None) -> List[DiscoveredDevice]:
        """Run full network discovery with absolute multi-vendor validation checks"""
        all_devices = {}
        
        if communities is None:
            communities = ['public', 'private']
            
        subnet = job.subnet
        methods = job.methods
        logger.info(f"Methods received: {methods}")
        logger.info(f"Subnet: {subnet}")
        total_methods = len(methods)
        current_method = 0
        
        def update_progress(method_progress):
            overall = int((current_method * 100 + method_progress) / total_methods)
            if progress_callback:
                progress_callback(overall)
        
        # 1. ARP Scan
        if DiscoveryMethod.ARP_SCAN.value in methods:
            logger.info(f"Starting ARP scan on {subnet}")
            arp_devices = await self.arp_scan(subnet, update_progress)
            logger.info(f"ARP Scan completed. Found {len(arp_devices)} devices")
            for device in arp_devices:
                all_devices[device.ip_address] = device
            logger.info(f"Total unique devices after ARP: {len(all_devices)}")
            logger.info(f"ARP IPs: {[d.ip_address for d in arp_devices]}")
            current_method += 1
            
        # 2. Ping Sweep
        if DiscoveryMethod.PING_SWEEP.value in methods:
            logger.info(f"Starting ping sweep on {subnet}")
            ping_devices = await self.ping_sweep(subnet, update_progress)
            logger.info(f"Ping Sweep completed. Found {len(ping_devices)} devices")
            for device in ping_devices:
                if device.ip_address not in all_devices:
                    all_devices[device.ip_address] = device
                else:
                    existing = all_devices[device.ip_address]
                    if device.hostname and not existing.hostname:
                        existing.hostname = device.hostname
            logger.info(f"Total unique devices after Ping: {len(all_devices)}")
            logger.info(f"PING IPs: {[d.ip_address for d in ping_devices]}")
            current_method += 1
        target_ips = list(all_devices.keys())
        # 3. SNMP Discovery (UNCONDITIONAL SWEEP FALLBACK)
        # Even if devices dropped pings or ARP packets earlier, since they are all explicitly
        # SNMP enabled, our concurrent scanner loop will sweep them into view here.
        if DiscoveryMethod.SNMP_DISCOVERY.value in methods:
            logger.info(f"Starting SNMP discovery for {len(target_ips)} discovered hosts")
            #snmp_devices = await self.snmp_discovery(subnet, communities, update_progress)
            snmp_devices = await self.snmp_discovery(target_ips,communities,update_progress)
            logger.info(f"SNMP Discovery completed. Found {len(snmp_devices)} devices")
            for device in snmp_devices:
                if device.ip_address not in all_devices:
                    # Captured a firewalled device!
                    all_devices[device.ip_address] = device
                else:
                    # Enhance existing basic node data with parsed deep SNMP telemetry
                    existing = all_devices[device.ip_address]
                    existing.snmp_info = device.snmp_info
                    if device.hostname:
                        existing.hostname = device.hostname
                    if device.device_type:
                        existing.device_type = device.device_type
                    if device.vendor:
                        existing.vendor = device.vendor
            logger.info(f"Total unique devices after SNMP: {len(all_devices)}")
            logger.info(f"SNMP IPs: {[d.ip_address for d in snmp_devices]}")
            current_method += 1
            
        # 4. Port Scan (on discovered targets matrix)
        if DiscoveryMethod.PORT_SCAN.value in methods:
            logger.info("Starting port metrics scan on discovered device array layout")
            total_devices = len(all_devices)
            for i, (ip, device) in enumerate(all_devices.items()):
                update_progress(int((i + 1) / max(total_devices, 1) * 100))
                device.open_ports = await self.port_scan(ip)
            logger.info(f"Port Scan completed for {len(all_devices)} devices")
        logger.info("=" * 60)
        logger.info(f"Discovery finished")
        logger.info(f"Subnet: {subnet}")
        logger.info(f"Total devices discovered: {len(all_devices)}")
        logger.info(f"Discovered IPs: {list(all_devices.keys())}")
        logger.info("=" * 60)

        return list(all_devices.values())


# ===================== SSH SERVICE =====================

class SSHService:
    """Real SSH connection service using paramiko"""
    
    def __init__(self):
        self.active_sessions: Dict[str, Any] = {}
        
    async def connect(self, host: str, username: str, password: str, 
                     port: int = 22, timeout: int = 10) -> Tuple[bool, str, Optional[str]]:
        """Establish SSH connection"""
        try:
            import paramiko 
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Run in thread pool to not block
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: client.connect(
                    hostname=host,
                    port=port,
                    username=username,
                    password=password,
                    timeout=timeout,
                    allow_agent=False,
                    look_for_keys=False
                )
            )
            
            session_id = f"{host}_{int(time.time())}"
            self.active_sessions[session_id] = {
                'client': client,
                'host': host,
                'username': username,
                'connected_at': datetime.now(timezone.utc).isoformat()
            }
            
            return True, "Connected successfully", session_id
            
        except paramiko.AuthenticationException:
            return False, "Authentication failed", None
        except paramiko.SSHException as e:
            return False, f"SSH error: {str(e)}", None
        except socket.timeout:
            return False, "Connection timed out", None
        except Exception as e:
            return False, f"Connection failed: {str(e)}", None
    
    async def execute_command(self, session_id: str, command: str, timeout: int = 30) -> Tuple[bool, str, str]:
        """Execute command on SSH session"""
        if session_id not in self.active_sessions:
            return False, "Session not found", ""
            
        try:
            client = self.active_sessions[session_id]['client']
            
            loop = asyncio.get_event_loop()
            stdin, stdout, stderr = await loop.run_in_executor(
                None,
                lambda: client.exec_command(command, timeout=timeout)
            )
            
            output = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')
            
            return True, output, error
            
        except Exception as e:
            return False, "", str(e)
    
    async def disconnect(self, session_id: str) -> bool:
        """Close SSH session"""
        if session_id not in self.active_sessions:
            return False
            
        try:
            client = self.active_sessions[session_id]['client']
            client.close()
            del self.active_sessions[session_id]
            return True
        except:
            return False
    
    async def get_device_config(self, host: str, username: str, password: str, 
                           vendor: str = None, device_type: str = None) -> Tuple[bool, str]:
        profile = get_vendor_profile(vendor or "generic")
        commands = profile.commands
        
        success, msg, session_id = await self.connect(host, username, password)
        if not success:
            return False, msg
        
        try:
            output = ""
            # Terminal setup
            if commands.get("terminal_length"):
                await self.execute_command(session_id, commands["terminal_length"])
            
            # Fetch
            fetch_success, stdout, _ = await self.execute_command(session_id, commands["fetch_config"])
            if fetch_success:
                output = stdout
            
            await self.disconnect(session_id)
            return True, output
        except Exception as e:
            await self.disconnect(session_id)
            return False, str(e)


# ===================== CLOUD CONNECTORS =====================

class OpenStackConnector:
    """Real OpenStack API connector"""
    
    def __init__(self, auth_url: str, username: str, password: str, 
                 project_name: str, domain: str = 'default'):
        self.auth_url = auth_url
        self.username = username
        self.password = password
        self.project_name = project_name
        self.domain = domain
        self.connection = None
        
    async def connect(self) -> Tuple[bool, str]:
        """Establish connection to OpenStack"""
        try:
            import openstack
            
            self.connection = openstack.connect(
                auth_url=self.auth_url,
                username=self.username,
                password=self.password,
                project_name=self.project_name,
                user_domain_name=self.domain,
                project_domain_name=self.domain
            )
            
            # Test connection
            list(self.connection.compute.servers(limit=1))
            return True, "Connected to OpenStack"
            
        except Exception as e:
            return False, f"OpenStack connection failed: {str(e)}"
    
    async def get_servers(self) -> List[Dict]:
        """Get all compute instances"""
        if not self.connection:
            return []
            
        try:
            servers = []
            for server in self.connection.compute.servers():
                servers.append({
                    'id': server.id,
                    'name': server.name,
                    'status': server.status,
                    'addresses': server.addresses,
                    'flavor': server.flavor,
                    'created': str(server.created_at),
                    'updated': str(server.updated_at)
                })
            return servers
        except Exception as e:
            logger.error(f"Failed to get OpenStack servers: {e}")
            return []
    
    async def get_networks(self) -> List[Dict]:
        """Get all networks"""
        if not self.connection:
            return []
            
        try:
            networks = []
            for network in self.connection.network.networks():
                networks.append({
                    'id': network.id,
                    'name': network.name,
                    'status': network.status,
                    'subnets': network.subnet_ids
                })
            return networks
        except Exception as e:
            logger.error(f"Failed to get OpenStack networks: {e}")
            return []


class OracleDBConnector:
    """Real Oracle Database connector"""
    
    def __init__(self, host: str, port: int, service_name: str, 
                 username: str, password: str):
        self.host = host
        self.port = port
        self.service_name = service_name
        self.username = username
        self.password = password
        self.connection = None
        
    async def connect(self) -> Tuple[bool, str]:
        """Establish connection to Oracle DB"""
        try:
            import oracledb
            
            dsn = f"{self.host}:{self.port}/{self.service_name}"
            
            loop = asyncio.get_event_loop()
            self.connection = await loop.run_in_executor(
                None,
                lambda: oracledb.connect(
                    user=self.username,
                    password=self.password,
                    dsn=dsn
                )
            )
            
            return True, "Connected to Oracle Database"
            
        except Exception as e:
            return False, f"Oracle connection failed: {str(e)}"
    
    async def get_instance_info(self) -> Dict:
        """Get database instance information"""
        if not self.connection:
            return {}
            
        try:
            cursor = self.connection.cursor()
            
            # Get instance info
            cursor.execute("SELECT instance_name, host_name, version, status FROM v$instance")
            row = cursor.fetchone()
            
            info = {
                'instance_name': row[0] if row else None,
                'host_name': row[1] if row else None,
                'version': row[2] if row else None,
                'status': row[3] if row else None
            }
            
            # Get SGA info
            cursor.execute("SELECT name, value FROM v$sga")
            info['sga'] = {row[0]: row[1] for row in cursor.fetchall()}
            
            cursor.close()
            return info
            
        except Exception as e:
            logger.error(f"Failed to get Oracle instance info: {e}")
            return {}
    
    async def get_tablespace_usage(self) -> List[Dict]:
        """Get tablespace usage"""
        if not self.connection:
            return []
            
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT tablespace_name, 
                       ROUND(used_space * 8192 / 1024 / 1024, 2) as used_mb,
                       ROUND(tablespace_size * 8192 / 1024 / 1024, 2) as total_mb,
                       ROUND(used_percent, 2) as used_percent
                FROM dba_tablespace_usage_metrics
            """)
            
            tablespaces = []
            for row in cursor.fetchall():
                tablespaces.append({
                    'name': row[0],
                    'used_mb': row[1],
                    'total_mb': row[2],
                    'used_percent': row[3]
                })
                
            cursor.close()
            return tablespaces
            
        except Exception as e:
            logger.error(f"Failed to get tablespace usage: {e}")
            return []


class VCenterConnector:
    """Real VMware vCenter connector"""
    
    def __init__(self, host: str, username: str, password: str, port: int = 443):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.service_instance = None
        
    async def connect(self) -> Tuple[bool, str]:
        """Establish connection to vCenter"""
        try:
            from pyVim.connect import SmartConnect, Disconnect
            from pyVmomi import vim
            import ssl
            
            # Disable SSL verification for self-signed certs
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            loop = asyncio.get_event_loop()
            self.service_instance = await loop.run_in_executor(
                None,
                lambda: SmartConnect(
                    host=self.host,
                    user=self.username,
                    pwd=self.password,
                    port=self.port,
                    sslContext=context
                )
            )
            
            return True, "Connected to vCenter"
            
        except Exception as e:
            return False, f"vCenter connection failed: {str(e)}"
    
    async def get_vms(self) -> List[Dict]:
        """Get all virtual machines"""
        if not self.service_instance:
            return []
            
        try:
            from pyVmomi import vim
            
            content = self.service_instance.RetrieveContent()
            container = content.viewManager.CreateContainerView(
                content.rootFolder, [vim.VirtualMachine], True
            )
            
            vms = []
            for vm in container.view:
                vms.append({
                    'name': vm.name,
                    'power_state': vm.runtime.powerState,
                    'guest_os': vm.config.guestFullName if vm.config else None,
                    'num_cpu': vm.config.hardware.numCPU if vm.config else None,
                    'memory_mb': vm.config.hardware.memoryMB if vm.config else None,
                    'ip_address': vm.guest.ipAddress if vm.guest else None
                })
                
            container.Destroy()
            return vms
            
        except Exception as e:
            logger.error(f"Failed to get vCenter VMs: {e}")
            return []
    
    async def get_hosts(self) -> List[Dict]:
        """Get all ESXi hosts"""
        if not self.service_instance:
            return []
            
        try:
            from pyVmomi import vim
            
            content = self.service_instance.RetrieveContent()
            container = content.viewManager.CreateContainerView(
                content.rootFolder, [vim.HostSystem], True
            )
            
            hosts = []
            for host in container.view:
                summary = host.summary
                hosts.append({
                    'name': host.name,
                    'connection_state': summary.runtime.connectionState,
                    'power_state': summary.runtime.powerState,
                    'model': summary.hardware.model if summary.hardware else None,
                    'cpu_mhz': summary.hardware.cpuMhz if summary.hardware else None,
                    'memory_size': summary.hardware.memorySize if summary.hardware else None,
                    'num_cpu_cores': summary.hardware.numCpuCores if summary.hardware else None
                })
                
            container.Destroy()
            return hosts
            
        except Exception as e:
            logger.error(f"Failed to get vCenter hosts: {e}")
            return []


# ===================== BACKGROUND POLLING SERVICE =====================

class BackgroundPollingService:
    """Background service for continuous device polling"""
    
    def __init__(self, db, poll_interval: int = 30):
        self.db = db
        self.poll_interval = poll_interval
        self.running = False
        self.snmp_service = SNMPService()
        self.poll_thread = None

    # In network_services.py (Inside BackgroundPollingService or as a standalone collector)
    async def poll_device_metrics(self, device: dict):
        """Collects performance metrics from a device using SNMP/SSH 
        and saves them explicitly into the telemetry database cache.
        """
        try:
            # Example collection logic calling SNMP / Vendor profile parsing
            result = await self.snmp_service.get_metrics(device["ip_address"])
            metrics_data = {
                "device_id": device["id"],
                "device_name": device["name"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "cpu_usage": result.get("cpu", 0.0),
                "memory_usage": result.get("mem", 0.0),
                "disk_usage": result.get("disk", 0.0),
                "metrics_output": result  # Full output dump for AI context
            }
            
            # Save to database cache
            await self.db.performance_metrics.insert_one(metrics_data)
            return metrics_data
        except Exception as e:
            logger.error(f"Failed to collect metrics for {device['name']}: {e}")
            return None
    
    async def start(self):
        """Start background polling"""
        if self.running:
            return
            
        self.running = True
        logger.info(f"Starting background polling service (interval: {self.poll_interval}s)")
        
        while self.running:
            try:
                await self._poll_all_devices()
            except Exception as e:
                logger.error(f"Polling error: {e}")
                
            await asyncio.sleep(self.poll_interval)
    
    def stop(self):
        """Stop background polling"""
        self.running = False
        logger.info("Stopping background polling service")
        
    async def _poll_all_devices(self):
        """Poll all devices in database"""
        try:
            # Get SNMP settings
            snmp_configs = await self.db.settings_snmp_community.find({}).to_list(100)
            communities = [c.get('community_string', 'public') for c in snmp_configs] or ['public']
            
            # Get devices
            devices = await self.db.devices.find({'snmp_enabled': True}).to_list(1000)
            
            for device in devices:
                ip = device.get('ip_address')
                if not ip:
                    continue
                    
                # Poll device
                for community in communities:
                    result = await self.snmp_service.poll_device(ip, community)
                    if result.get('success'):
                        # Update device status
                        await self.db.devices.update_one(
                            {'_id': device['_id']},
                            {'$set': {
                                'last_polled': datetime.now(timezone.utc).isoformat(),
                                'status': 'online',
                                'snmp_data': result.get('results', {})
                            }}
                        )
                        
                        # Store metrics
                        await self.db.performance.insert_one({
                            'device_id': str(device['_id']),
                            'device_name': device.get('hostname', ip),
                            'timestamp': datetime.now(timezone.utc).isoformat(),
                            'snmp_metrics': result.get('results', {})
                        })
                        break
                else:
                    # Device unreachable
                    await self.db.devices.update_one(
                        {'_id': device['_id']},
                        {'$set': {
                            'last_polled': datetime.now(timezone.utc).isoformat(),
                            'status': 'offline'
                        }}
                    )
                        
        except Exception as e:
            logger.error(f"Failed to poll devices: {e}")


# Export all services
__all__ = [
    'SNMPService',
    'NetworkDiscoveryService', 
    'SSHService',
    'OpenStackConnector',
    'OracleDBConnector',
    'VCenterConnector',
    'BackgroundPollingService',
    'DiscoveryMethod',
    'DiscoveredDevice',
    'DiscoveryJob',
    'SNMPResult'
]
