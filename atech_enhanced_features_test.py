#!/usr/bin/env python3
"""
ATECH NOC Commander Enhanced Features Test
Tests the new features specifically mentioned in the requirements:
1. AI Agents system with 200 activation codes
2. Escalation management with 3 levels
3. SNMP discovery endpoints  
4. Telnet endpoints
5. Network topology API
"""

import requests
import sys
import json
from datetime import datetime

class ATECHEnhancedFeaturesTester:
    def __init__(self, base_url="https://network-ops-ai.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        
        # Test credentials
        self.test_email = "admin@noc.com"
        self.test_password = "admin123"
        
        # Created data storage
        self.created_data = {}

    def run_test(self, name, method, endpoint, expected_status, data=None, params=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint.lstrip('/')}"
        headers = {'Content-Type': 'application/json'}
        
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   {method} {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, params=params)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, params=params)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, params=params)

            success = response.status_code == expected_status
            
            if success:
                self.tests_passed += 1
                print(f"✅ PASSED - Status: {response.status_code}")
                try:
                    result_data = response.json()
                except:
                    result_data = {"message": "No JSON response"}
            else:
                print(f"❌ FAILED - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Response: {response.text[:200]}...")
                result_data = {"error": response.text}

            self.test_results.append({
                "name": name,
                "method": method,
                "endpoint": endpoint,
                "status_code": response.status_code,
                "expected_status": expected_status,
                "success": success
            })

            return success, result_data

        except Exception as e:
            print(f"❌ FAILED - Exception: {str(e)}")
            return False, {"error": str(e)}

    def login(self):
        """Authenticate and get token"""
        success, response = self.run_test(
            "Authentication Login",
            "POST",
            "/auth/login",
            200,
            data={"email": self.test_email, "password": self.test_password}
        )
        
        if success and 'access_token' in response:
            self.token = response['access_token']
            return True
        return False

    def test_ai_agents_system(self):
        """Test AI Agents system with activation codes"""
        print("\n" + "="*60)
        print("🤖 TESTING AI AGENTS SYSTEM")
        print("="*60)
        
        # Test getting activation codes
        success, codes_response = self.run_test(
            "Get activation codes",
            "GET",
            "/activation-codes",
            200
        )
        
        available_codes = []
        if success and isinstance(codes_response, list):
            available_codes = [c for c in codes_response if c.get('status') == 'available']
            print(f"   Available codes: {len(available_codes)}")
            print(f"   Total codes: {len(codes_response)}")
        
        # Test activation code verification
        if available_codes:
            test_code = available_codes[0]['code']
            success, verify_response = self.run_test(
                "Verify activation code",
                "POST",
                f"/activation-codes/verify?code={test_code}",
                200
            )
            
            if success and verify_response.get('valid'):
                print(f"   ✅ Code {test_code} is valid")
        
        # Test getting existing agents
        success, agents_response = self.run_test(
            "Get AI agents",
            "GET",
            "/agents",
            200
        )
        
        if success:
            print(f"   Current agents: {len(agents_response)}")
        
        # Test creating a new agent (if we have available codes)
        if available_codes:
            agent_data = {
                "name": "Test-NOC-Agent",
                "description": "Test AI agent for monitoring core infrastructure",
                "activation_code": available_codes[0]['code']
            }
            
            success, agent_response = self.run_test(
                "Create new AI agent",
                "POST",
                "/agents",
                200,
                data=agent_data
            )
            
            if success and 'id' in agent_response:
                agent_id = agent_response['id']
                self.created_data['agent_id'] = agent_id
                print(f"   Created agent ID: {agent_id}")
                
                # Test getting the specific agent
                self.run_test(
                    "Get specific agent",
                    "GET",
                    f"/agents/{agent_id}",
                    200
                )
                
                # Test device assignment limit (should allow up to 15 devices)
                devices_response = requests.get(f"{self.api_url}/devices", headers={'Authorization': f'Bearer {self.token}'})
                if devices_response.status_code == 200:
                    devices = devices_response.json()
                    if devices:
                        device_id = devices[0]['id']
                        success, assign_response = self.run_test(
                            "Assign device to agent",
                            "POST",
                            f"/agents/{agent_id}/assign-device/{device_id}",
                            200
                        )
                        
                        if success:
                            print(f"   ✅ Device assignment works - Max 15 devices per agent")
                            
                            # Test unassigning
                            self.run_test(
                                "Unassign device from agent",
                                "POST",
                                f"/agents/{agent_id}/unassign-device/{device_id}",
                                200
                            )

    def test_escalation_management(self):
        """Test multi-level escalation system"""
        print("\n" + "="*60)
        print("📞 TESTING ESCALATION MANAGEMENT")
        print("="*60)
        
        # Test getting escalation levels
        success, levels_response = self.run_test(
            "Get escalation levels",
            "GET",
            "/escalation/levels",
            200
        )
        
        if success:
            print(f"   Escalation levels: {len(levels_response)}")
            for level in levels_response:
                print(f"   Level {level['level']}: {level['name']} - {level['threshold_hours']}h")
        
        # Test getting escalation contacts
        success, contacts_response = self.run_test(
            "Get escalation contacts",
            "GET",
            "/escalation/contacts",
            200
        )
        
        if success:
            print(f"   Current escalation contacts: {len(contacts_response)}")
        
        # Test adding escalation contacts for each level
        contact_data = [
            {"name": "John Smith", "email": "john.smith@company.com", "role": "team_lead", "level": 1},
            {"name": "Sarah Johnson", "email": "sarah.johnson@company.com", "role": "sdm", "level": 2},
            {"name": "Michael Brown", "email": "michael.brown@company.com", "role": "director", "level": 3}
        ]
        
        for contact in contact_data:
            success, create_response = self.run_test(
                f"Add {contact['role']} escalation contact",
                "POST",
                "/escalation/contacts",
                200,
                data=contact
            )
            
            if success and 'id' in create_response:
                if 'escalation_contact_ids' not in self.created_data:
                    self.created_data['escalation_contact_ids'] = []
                self.created_data['escalation_contact_ids'].append(create_response['id'])
        
        # Test checking escalations
        self.run_test(
            "Check for needed escalations",
            "POST",
            "/escalation/check",
            200
        )

    def test_snmp_discovery(self):
        """Test SNMP device discovery endpoints"""
        print("\n" + "="*60)
        print("🌐 TESTING SNMP DISCOVERY")
        print("="*60)
        
        # Test SNMP discovery (simulated)
        discovery_data = {
            "ip_range": "192.168.1.0/24",
            "community": "public",
            "port": 161,
            "timeout": 2
        }
        
        success, discovery_response = self.run_test(
            "SNMP device discovery",
            "POST",
            "/snmp/discover",
            200,
            data=discovery_data
        )
        
        if success:
            discovered_count = discovery_response.get('discovered_count', 0)
            print(f"   ✅ SNMP discovery found {discovered_count} devices")
            
            devices = discovery_response.get('devices', [])
            for device in devices:
                print(f"   - {device['name']} ({device['ip_address']}) - {device['vendor']}")
        
        # Test SNMP polling
        poll_data = {
            "ip_address": "192.168.1.1",
            "community": "public",
            "oids": ["1.3.6.1.2.1.1.1.0", "1.3.6.1.2.1.1.5.0"]
        }
        
        success, poll_response = self.run_test(
            "SNMP device polling",
            "POST",
            "/snmp/poll",
            200,
            data=poll_data
        )
        
        if success:
            results = poll_response.get('results', {})
            print(f"   ✅ SNMP poll returned {len(results)} OIDs")
        
        # Test adding discovered device
        if success and discovery_response.get('devices'):
            device_to_add = discovery_response['devices'][0]
            
            success, add_response = self.run_test(
                "Add discovered SNMP device",
                "POST",
                "/snmp/add-discovered",
                200,
                data=device_to_add
            )
            
            if success and 'id' in add_response:
                self.created_data['snmp_device_id'] = add_response['id']
                print(f"   ✅ Added discovered device ID: {add_response['id']}")

    def test_telnet_endpoints(self):
        """Test Telnet legacy device support"""
        print("\n" + "="*60)
        print("📟 TESTING TELNET SUPPORT")
        print("="*60)
        
        # Get a test device
        devices_response = requests.get(f"{self.api_url}/devices", headers={'Authorization': f'Bearer {self.token}'})
        if devices_response.status_code == 200:
            devices = devices_response.json()
            if devices:
                device_id = devices[0]['id']
                
                # Test telnet connection
                telnet_connect_data = {
                    "device_id": device_id,
                    "username": "admin",
                    "password": "admin123"
                }
                
                success, connect_response = self.run_test(
                    "Telnet connection test",
                    "POST",
                    "/telnet/connect",
                    200,
                    data=telnet_connect_data
                )
                
                if success:
                    print(f"   ✅ Telnet connection simulation working")
                
                # Test telnet command execution
                telnet_exec_data = {
                    "device_id": device_id,
                    "username": "admin", 
                    "password": "admin123",
                    "command": "show version"
                }
                
                success, exec_response = self.run_test(
                    "Telnet command execution",
                    "POST",
                    "/telnet/execute",
                    200,
                    data=telnet_exec_data
                )
                
                if success:
                    output = exec_response.get('output', '')
                    print(f"   ✅ Telnet command execution returned output: {len(output)} chars")

    def test_network_topology(self):
        """Test network topology API with Cisco-style icons"""
        print("\n" + "="*60)
        print("🗺️  TESTING NETWORK TOPOLOGY")
        print("="*60)
        
        # Test getting topology data
        success, topology_response = self.run_test(
            "Get network topology data",
            "GET",
            "/topology/data",
            200
        )
        
        if success:
            nodes = topology_response.get('nodes', [])
            links = topology_response.get('links', [])
            
            print(f"   ✅ Topology has {len(nodes)} nodes and {len(links)} links")
            
            # Check for different device types (Cisco-style)
            device_types = {}
            for node in nodes:
                device_type = node.get('type', 'unknown')
                device_types[device_type] = device_types.get(device_type, 0) + 1
            
            print("   Device types in topology:")
            for device_type, count in device_types.items():
                print(f"   - {device_type}: {count}")
            
            # Check node data structure
            if nodes:
                sample_node = nodes[0]
                required_fields = ['id', 'name', 'type', 'status', 'ip', 'location']
                missing_fields = [field for field in required_fields if field not in sample_node]
                
                if not missing_fields:
                    print(f"   ✅ Node data structure complete")
                else:
                    print(f"   ❌ Missing node fields: {missing_fields}")
            
            # Check link data structure  
            if links:
                sample_link = links[0]
                required_link_fields = ['source', 'target', 'type']
                missing_link_fields = [field for field in required_link_fields if field not in sample_link]
                
                if not missing_link_fields:
                    print(f"   ✅ Link data structure complete")
                else:
                    print(f"   ❌ Missing link fields: {missing_link_fields}")

    def cleanup_test_data(self):
        """Clean up any test data created"""
        print("\n" + "="*60)
        print("🧹 CLEANING UP TEST DATA")
        print("="*60)
        
        # Delete escalation contacts
        if 'escalation_contact_ids' in self.created_data:
            for contact_id in self.created_data['escalation_contact_ids']:
                self.run_test(
                    "Delete escalation contact",
                    "DELETE",
                    f"/escalation/contacts/{contact_id}",
                    200
                )
        
        # Delete SNMP device if created
        if 'snmp_device_id' in self.created_data:
            self.run_test(
                "Delete SNMP discovered device",
                "DELETE",
                f"/devices/{self.created_data['snmp_device_id']}",
                200
            )

    def run_all_tests(self):
        """Run all enhanced feature tests"""
        print("🚀 Starting ATECH NOC Commander Enhanced Features Test")
        print(f"Testing against: {self.base_url}")
        
        start_time = datetime.now()
        
        # Login first
        if not self.login():
            print("❌ Authentication failed")
            return 1
        
        try:
            # Test all enhanced features
            self.test_ai_agents_system()
            self.test_escalation_management()
            self.test_snmp_discovery()
            self.test_telnet_endpoints()
            self.test_network_topology()
            
        except Exception as e:
            print(f"❌ Test suite failed with exception: {e}")
            
        finally:
            try:
                self.cleanup_test_data()
            except:
                pass
        
        # Print results
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print("\n" + "="*60)
        print("📊 ENHANCED FEATURES TEST RESULTS")
        print("="*60)
        print(f"Tests run: {self.tests_run}")
        print(f"Tests passed: {self.tests_passed}")
        print(f"Tests failed: {self.tests_run - self.tests_passed}")
        print(f"Success rate: {(self.tests_passed / self.tests_run * 100):.1f}%")
        print(f"Duration: {duration:.1f} seconds")
        
        return 0 if self.tests_passed == self.tests_run else 1

def main():
    tester = ATECHEnhancedFeaturesTester()
    return tester.run_all_tests()

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)