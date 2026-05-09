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
        
    async def snmp_get(self, ip: str, community: str, oid: str, port: int = 161, timeout: int = 2) -> Optional[SNMPResult]:
        """Perform SNMP GET operation"""
        try:
            from pysnmp.hlapi.v1arch.asyncio import (
                SnmpEngine, CommunityData, UdpTransportTarget, 
                ObjectType, ObjectIdentity, get_cmd
            )
            
            snmp_engine = SnmpEngine()
            
            iterator = get_cmd(
                snmp_engine,
                CommunityData(community),
                await UdpTransportTarget.create((ip, port), timeout=timeout, retries=1),
                ObjectType(ObjectIdentity(oid))
            )
            
            errorIndication, errorStatus, errorIndex, varBinds = await iterator
            
            if errorIndication:
                logger.warning(f"SNMP error for {ip}: {errorIndication}")
                return None
            elif errorStatus:
                logger.warning(f"SNMP error for {ip}: {errorStatus.prettyPrint()}")
                return None
            else:
                for varBind in varBinds:
                    oid_str, value = varBind
                    return SNMPResult(
                        ip_address=ip,
                        oid=str(oid_str),
                        value=str(value),
                        value_type=type(value).__name__,
                        timestamp=datetime.now(timezone.utc).isoformat()
                    )
        except ImportError:
            logger.error("pysnmp not properly installed")
            return None
        except Exception as e:
            logger.error(f"SNMP GET failed for {ip}: {e}")
            return None
        
        return None
    
    async def snmp_walk(self, ip: str, community: str, oid: str, port: int = 161) -> List[SNMPResult]:
        """Perform SNMP WALK operation"""
        results = []
        try:
            from pysnmp.hlapi.v1arch.asyncio import (
                SnmpEngine, CommunityData, UdpTransportTarget,
                ObjectType, ObjectIdentity, bulk_walk_cmd
            )
            
            snmp_engine = SnmpEngine()
            
            async for errorIndication, errorStatus, errorIndex, varBinds in bulk_walk_cmd(
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
        except Exception as e:
            logger.error(f"SNMP WALK failed for {ip}: {e}")
            
        return results
    
    async def get_device_info(self, ip: str, community: str) -> Dict[str, Any]:
        """Get comprehensive device info via SNMP"""
        info = {'ip_address': ip, 'snmp_reachable': False}
        
        # Try to get system info
        for name, oid in [
            ('sysDescr', self.OIDS['sysDescr']),
            ('sysName', self.OIDS['sysName']),
            ('sysLocation', self.OIDS['sysLocation']),
            ('sysContact', self.OIDS['sysContact']),
            ('sysUpTime', self.OIDS['sysUpTime']),
        ]:
            result = await self.snmp_get(ip, community, oid)
            if result:
                info['snmp_reachable'] = True
                info[name] = result.value
                
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
        
    def get_local_subnets(self) -> List[str]:
        """Get all local network subnets"""
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
                            subnets.append(f"{network}/{cidr}")
        except Exception as e:
            logger.error(f"Failed to get local subnets: {e}")
            
        return subnets
    
    async def ping_host(self, ip: str, timeout: int = 1) -> bool:
        """Ping a host to check if it's alive"""
        try:
            # Use system ping command
            result = subprocess.run(
                ['ping', '-c', '1', '-W', str(timeout), ip],
                capture_output=True,
                timeout=timeout + 1
            )
            return result.returncode == 0
        except Exception:
            return False
    
    async def ping_sweep(self, subnet: str, progress_callback=None) -> List[DiscoveredDevice]:
        """Perform ping sweep on a subnet"""
        devices = []
        
        try:
            import ipaddress
            network = ipaddress.ip_network(subnet, strict=False)
            hosts = list(network.hosts())[:254]  # Limit to /24 or smaller
            
            total = len(hosts)
            completed = 0
            
            # Use thread pool for parallel pinging
            with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
                def ping_sync(ip):
                    try:
                        result = subprocess.run(
                            ['ping', '-c', '1', '-W', '1', str(ip)],
                            capture_output=True,
                            timeout=2
                        )
                        return str(ip) if result.returncode == 0 else None
                    except:
                        return None
                
                futures = {executor.submit(ping_sync, ip): ip for ip in hosts}
                
                for future in concurrent.futures.as_completed(futures):
                    completed += 1
                    if progress_callback:
                        progress_callback(int(completed / total * 100))
                        
                    ip = future.result()
                    if ip:
                        device = DiscoveredDevice(
                            ip_address=ip,
                            discovery_method=DiscoveryMethod.PING_SWEEP.value,
                            discovered_at=datetime.now(timezone.utc).isoformat()
                        )
                        # Try to get hostname
                        try:
                            hostname = socket.gethostbyaddr(ip)[0]
                            device.hostname = hostname
                        except:
                            pass
                        devices.append(device)
                        
        except Exception as e:
            logger.error(f"Ping sweep failed: {e}")
            
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
        }
        
        mac_prefix = mac[:8].lower()
        return vendors.get(mac_prefix)
    
    async def snmp_discovery(self, subnet: str, communities: List[str], progress_callback=None) -> List[DiscoveredDevice]:
        """Discover devices using SNMP"""
        devices = []
        snmp_service = SNMPService()
        
        try:
            import ipaddress
            network = ipaddress.ip_network(subnet, strict=False)
            hosts = list(network.hosts())[:254]
            
            total = len(hosts) * len(communities)
            completed = 0
            
            for ip in hosts:
                for community in communities:
                    completed += 1
                    if progress_callback:
                        progress_callback(int(completed / total * 100))
                        
                    info = await snmp_service.get_device_info(str(ip), community)
                    
                    if info.get('snmp_reachable'):
                        device = DiscoveredDevice(
                            ip_address=str(ip),
                            hostname=info.get('sysName'),
                            device_type=self._detect_device_type(info.get('sysDescr', '')),
                            discovery_method=DiscoveryMethod.SNMP_DISCOVERY.value,
                            snmp_info=info,
                            discovered_at=datetime.now(timezone.utc).isoformat()
                        )
                        devices.append(device)
                        break  # Found with this community, no need to try others
                        
        except Exception as e:
            logger.error(f"SNMP discovery failed: {e}")
            
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
        """Run full network discovery with all methods"""
        all_devices = {}
        
        if communities is None:
            communities = ['public', 'private']
            
        subnet = job.subnet
        methods = job.methods
        
        total_methods = len(methods)
        current_method = 0
        
        def update_progress(method_progress):
            overall = int((current_method * 100 + method_progress) / total_methods)
            if progress_callback:
                progress_callback(overall)
        
        # ARP Scan
        if DiscoveryMethod.ARP_SCAN.value in methods:
            logger.info(f"Starting ARP scan on {subnet}")
            arp_devices = await self.arp_scan(subnet, update_progress)
            for device in arp_devices:
                all_devices[device.ip_address] = device
            current_method += 1
            
        # Ping Sweep
        if DiscoveryMethod.PING_SWEEP.value in methods:
            logger.info(f"Starting ping sweep on {subnet}")
            ping_devices = await self.ping_sweep(subnet, update_progress)
            for device in ping_devices:
                if device.ip_address not in all_devices:
                    all_devices[device.ip_address] = device
                else:
                    # Merge info
                    existing = all_devices[device.ip_address]
                    if device.hostname and not existing.hostname:
                        existing.hostname = device.hostname
            current_method += 1
            
        # SNMP Discovery
        if DiscoveryMethod.SNMP_DISCOVERY.value in methods:
            logger.info(f"Starting SNMP discovery on {subnet}")
            snmp_devices = await self.snmp_discovery(subnet, communities, update_progress)
            for device in snmp_devices:
                if device.ip_address not in all_devices:
                    all_devices[device.ip_address] = device
                else:
                    # Merge SNMP info
                    existing = all_devices[device.ip_address]
                    existing.snmp_info = device.snmp_info
                    if device.hostname:
                        existing.hostname = device.hostname
                    if device.device_type:
                        existing.device_type = device.device_type
            current_method += 1
            
        # Port Scan (on discovered devices)
        if DiscoveryMethod.PORT_SCAN.value in methods:
            logger.info("Starting port scan on discovered devices")
            total_devices = len(all_devices)
            for i, (ip, device) in enumerate(all_devices.items()):
                update_progress(int((i + 1) / max(total_devices, 1) * 100))
                device.open_ports = await self.port_scan(ip)
                
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
                                device_type: str = 'cisco') -> Tuple[bool, str]:
        """Get running configuration from device"""
        success, msg, session_id = await self.connect(host, username, password)
        if not success:
            return False, msg
            
        try:
            # Determine command based on device type
            if device_type in ['cisco', 'cisco_ios', 'router', 'switch']:
                commands = ['terminal length 0', 'show running-config']
            elif device_type in ['juniper', 'junos']:
                commands = ['show configuration | display set']
            elif device_type in ['linux', 'linux_server']:
                commands = ['cat /etc/hostname', 'ip addr show', 'cat /etc/os-release']
            else:
                commands = ['show running-config']
                
            output = ""
            for cmd in commands:
                success, stdout, stderr = await self.execute_command(session_id, cmd)
                if success:
                    output += f"\n--- {cmd} ---\n{stdout}"
                    
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
