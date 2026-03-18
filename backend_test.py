#!/usr/bin/env python3
"""
NOC Commander Backend API Test Suite
Tests all API endpoints with proper authentication
"""

import requests
import sys
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

class NOCCommanderAPITester:
    def __init__(self, base_url: str = "https://network-ops-ai.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.token = None
        self.user_data = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        
        # Test credentials
        self.test_email = "admin@noc.com"
        self.test_password = "admin123"
        
        # Test data storage
        self.created_ids = {
            'device': None,
            'alert': None,
            'incident': None,
            'asset': None,
            'config': None,
        }

    def run_test(self, name: str, method: str, endpoint: str, expected_status: int, 
                 data: Optional[Dict] = None, params: Optional[Dict] = None) -> tuple[bool, Dict]:
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
            else:
                raise ValueError(f"Unsupported method: {method}")

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
            self.test_results.append({
                "name": name,
                "method": method,
                "endpoint": endpoint,
                "status_code": 0,
                "expected_status": expected_status,
                "success": False,
                "error": str(e)
            })
            return False, {"error": str(e)}

    def test_authentication(self) -> bool:
        """Test authentication endpoints"""
        print("\n" + "="*60)
        print("🔐 TESTING AUTHENTICATION")
        print("="*60)
        
        # Test login with valid credentials
        success, response = self.run_test(
            "Login with valid credentials",
            "POST",
            "/auth/login",
            200,
            data={
                "email": self.test_email,
                "password": self.test_password
            }
        )
        
        if success and 'access_token' in response:
            self.token = response['access_token']
            self.user_data = response.get('user', {})
            print(f"   Token received: {self.token[:20]}...")
        else:
            print("❌ Failed to get authentication token")
            return False
            
        # Test getting current user profile
        self.run_test(
            "Get current user profile",
            "GET",
            "/auth/me",
            200
        )
        
        return self.token is not None

    def test_dashboard_endpoints(self) -> None:
        """Test dashboard API endpoints"""
        print("\n" + "="*60)
        print("📊 TESTING DASHBOARD ENDPOINTS")
        print("="*60)
        
        self.run_test("Get dashboard stats", "GET", "/dashboard/stats", 200)
        self.run_test("Get recent alerts", "GET", "/dashboard/recent-alerts", 200, params={"limit": 5})
        self.run_test("Get recent incidents", "GET", "/dashboard/recent-incidents", 200, params={"limit": 5})

    def test_device_management(self) -> None:
        """Test device CRUD operations"""
        print("\n" + "="*60)
        print("🖥️  TESTING DEVICE MANAGEMENT")
        print("="*60)
        
        # Get all devices
        self.run_test("Get all devices", "GET", "/devices", 200)
        
        # Create a new device
        device_data = {
            "name": "Test-Router-01",
            "type": "router",
            "ip_address": "192.168.1.1",
            "location": "Test-DC",
            "vendor": "Cisco",
            "model": "Test Router",
            "serial_number": "TEST123456",
            "firmware_version": "v1.0",
            "tags": ["test", "automation"]
        }
        
        success, response = self.run_test("Create device", "POST", "/devices", 200, data=device_data)
        if success and 'id' in response:
            self.created_ids['device'] = response['id']
            print(f"   Created device ID: {self.created_ids['device']}")
            
            # Get specific device
            self.run_test("Get specific device", "GET", f"/devices/{self.created_ids['device']}", 200)
            
            # Update device
            update_data = device_data.copy()
            update_data['location'] = "Updated-DC"
            self.run_test("Update device", "PUT", f"/devices/{self.created_ids['device']}", 200, data=update_data)

    def test_alert_management(self) -> None:
        """Test alert management operations"""
        print("\n" + "="*60)
        print("🚨 TESTING ALERT MANAGEMENT")
        print("="*60)
        
        # Get all alerts
        self.run_test("Get all alerts", "GET", "/alerts", 200)
        
        # Create alert (need device ID first)
        if self.created_ids['device']:
            alert_data = {
                "device_id": self.created_ids['device'],
                "device_name": "Test-Router-01",
                "severity": "high",
                "title": "Test Alert - High CPU Usage",
                "description": "CPU usage exceeded 85% threshold",
                "metric_name": "cpu_usage",
                "metric_value": 90.5,
                "threshold": 85.0
            }
            
            success, response = self.run_test("Create alert", "POST", "/alerts", 200, data=alert_data)
            if success and 'id' in response:
                self.created_ids['alert'] = response['id']
                print(f"   Created alert ID: {self.created_ids['alert']}")
                
                # Acknowledge alert
                self.run_test("Acknowledge alert", "PUT", f"/alerts/{self.created_ids['alert']}/acknowledge", 200)
                
                # Resolve alert
                self.run_test("Resolve alert", "PUT", f"/alerts/{self.created_ids['alert']}/resolve", 200)

    def test_incident_management(self) -> None:
        """Test incident management with AI analysis"""
        print("\n" + "="*60)
        print("🔧 TESTING INCIDENT MANAGEMENT")
        print("="*60)
        
        # Get all incidents
        self.run_test("Get all incidents", "GET", "/incidents", 200)
        
        # Create incident
        incident_data = {
            "title": "Test Incident - Network Connectivity Issue",
            "description": "Users reporting intermittent network connectivity issues in Test-DC",
            "priority": "P2",
            "category": "Network",
            "affected_devices": [self.created_ids['device']] if self.created_ids['device'] else [],
            "related_alerts": [self.created_ids['alert']] if self.created_ids['alert'] else []
        }
        
        success, response = self.run_test("Create incident", "POST", "/incidents", 200, data=incident_data)
        if success and 'id' in response:
            self.created_ids['incident'] = response['id']
            print(f"   Created incident ID: {self.created_ids['incident']}")
            
            # Get specific incident
            self.run_test("Get specific incident", "GET", f"/incidents/{self.created_ids['incident']}", 200)
            
            # Test AI analysis (this might take longer)
            print("   Testing AI analysis (may take 10+ seconds)...")
            self.run_test("Get AI analysis for incident", "POST", f"/incidents/{self.created_ids['incident']}/ai-analysis", 200)
            
            # Update incident status
            self.run_test("Update incident status", "PUT", f"/incidents/{self.created_ids['incident']}", 200, 
                         data={"status": "in_progress"})

    def test_asset_management(self) -> None:
        """Test asset management operations"""
        print("\n" + "="*60)
        print("📦 TESTING ASSET MANAGEMENT")
        print("="*60)
        
        # Get all assets
        self.run_test("Get all assets", "GET", "/assets", 200)
        
        # Create asset
        asset_data = {
            "name": "Test Network Device",
            "asset_tag": "TEST-001",
            "type": "Network",
            "vendor": "Test Vendor",
            "model": "Test Model",
            "serial_number": "SN-TEST-12345",
            "location": "Test Location",
            "owner": "Test Team",
            "purchase_date": "2024-01-15",
            "warranty_expiry": "2027-01-15",
            "eol_date": "2029-01-15"
        }
        
        success, response = self.run_test("Create asset", "POST", "/assets", 200, data=asset_data)
        if success and 'id' in response:
            self.created_ids['asset'] = response['id']
            print(f"   Created asset ID: {self.created_ids['asset']}")
            
            # Get specific asset
            self.run_test("Get specific asset", "GET", f"/assets/{self.created_ids['asset']}", 200)
            
            # Update asset
            update_data = asset_data.copy()
            update_data['status'] = 'maintenance'
            self.run_test("Update asset", "PUT", f"/assets/{self.created_ids['asset']}", 200, data=update_data)

    def test_performance_metrics(self) -> None:
        """Test performance metrics endpoints"""
        print("\n" + "="*60)
        print("📈 TESTING PERFORMANCE METRICS")
        print("="*60)
        
        # Get performance metrics
        self.run_test("Get performance metrics", "GET", "/performance", 200, params={"hours": 24})
        
        # Create performance metric
        if self.created_ids['device']:
            metric_data = {
                "device_id": self.created_ids['device'],
                "device_name": "Test-Router-01",
                "cpu_usage": 65.5,
                "memory_usage": 45.2,
                "disk_usage": 30.8,
                "bandwidth_in": 450.2,
                "bandwidth_out": 280.5,
                "latency_ms": 15.3,
                "packet_loss": 0.1,
                "uptime_hours": 2400
            }
            
            self.run_test("Create performance metric", "POST", "/performance", 200, data=metric_data)

    def test_reports_generation(self) -> None:
        """Test reports generation"""
        print("\n" + "="*60)
        print("📋 TESTING REPORTS GENERATION")
        print("="*60)
        
        # Get existing reports
        self.run_test("Get all reports", "GET", "/reports", 200)
        
        # Generate different types of reports
        today = datetime.now().strftime('%Y-%m-%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        report_types = ["daily_health", "incident_summary", "sla_compliance"]
        for report_type in report_types:
            self.run_test(f"Generate {report_type} report", "POST", "/reports/generate", 200,
                         params={"report_type": report_type, "period_start": yesterday, "period_end": today})

    def test_configuration_backup(self) -> None:
        """Test configuration backup operations"""
        print("\n" + "="*60)
        print("⚙️  TESTING CONFIGURATION BACKUP")
        print("="*60)
        
        # Get configurations
        self.run_test("Get all configurations", "GET", "/config", 200)
        
        # Create config backup
        if self.created_ids['device']:
            config_data = """
interface GigabitEthernet0/1
 ip address 192.168.1.1 255.255.255.0
 no shutdown
!
router ospf 1
 network 192.168.1.0 0.0.0.255 area 0
!
"""
            self.run_test("Create config backup", "POST", "/config/backup", 200,
                         params={"device_id": self.created_ids['device'], 
                                "config_type": "running-config",
                                "config_data": config_data})

    def test_sla_tracking(self) -> None:
        """Test SLA tracking endpoints"""
        print("\n" + "="*60)
        print("📊 TESTING SLA TRACKING")
        print("="*60)
        
        # Get SLA records
        self.run_test("Get SLA records", "GET", "/sla", 200)
        
        # Get SLA metrics
        self.run_test("Get SLA metrics", "GET", "/sla/metrics", 200)

    def test_ai_services(self) -> None:
        """Test AI analysis services"""
        print("\n" + "="*60)
        print("🤖 TESTING AI SERVICES")
        print("="*60)
        
        # Test general AI analysis
        ai_data = {
            "context": "Network device showing high CPU usage and packet loss",
            "query": "What could be causing this issue and how to resolve it?",
            "incident_id": self.created_ids.get('incident')
        }
        self.run_test("General AI analysis", "POST", "/ai/analyze", 200, data=ai_data)
        
        # Test traceroute analysis
        traceroute_data = {
            "target": "8.8.8.8",
            "traceroute_output": """
traceroute to 8.8.8.8 (8.8.8.8), 30 hops max, 60 byte packets
1  192.168.1.1 (192.168.1.1)  1.234 ms  1.123 ms  1.056 ms
2  * * *
3  10.0.0.1 (10.0.0.1)  45.678 ms  47.890 ms  46.123 ms
"""
        }
        self.run_test("Traceroute AI analysis", "POST", "/ai/traceroute-analysis", 200, data=traceroute_data)
        
        # Test log analysis
        log_data = {
            "logs": """
2024-01-20 10:15:30 ERROR: Interface GigabitEthernet0/1 down
2024-01-20 10:15:31 WARNING: CPU usage high: 95%
2024-01-20 10:15:32 INFO: OSPF neighbor 192.168.1.2 down
"""
        }
        self.run_test("Log AI analysis", "POST", "/ai/log-analysis", 200, data=log_data)

    def test_seed_demo_data(self) -> None:
        """Test seeding demo data"""
        print("\n" + "="*60)
        print("🌱 TESTING SEED DEMO DATA")
        print("="*60)
        
        self.run_test("Seed demo data", "POST", "/seed", 200)

    def cleanup_test_data(self) -> None:
        """Clean up created test data"""
        print("\n" + "="*60)
        print("🧹 CLEANING UP TEST DATA")
        print("="*60)
        
        # Delete in reverse order of creation to handle dependencies
        if self.created_ids['asset']:
            self.run_test("Delete test asset", "DELETE", f"/assets/{self.created_ids['asset']}", 200)
            
        if self.created_ids['device']:
            self.run_test("Delete test device", "DELETE", f"/devices/{self.created_ids['device']}", 200)

    def run_all_tests(self) -> int:
        """Run all test suites"""
        print("🚀 Starting NOC Commander API Test Suite")
        print(f"Testing against: {self.base_url}")
        
        start_time = datetime.now()
        
        # Authentication is required for all other tests
        if not self.test_authentication():
            print("❌ Authentication failed, stopping tests")
            return 1
        
        # Run all test suites
        try:
            self.test_dashboard_endpoints()
            self.test_seed_demo_data()  # Seed data first for better testing
            self.test_device_management()
            self.test_alert_management()
            self.test_incident_management()
            self.test_asset_management()
            self.test_performance_metrics()
            self.test_reports_generation()
            self.test_configuration_backup()
            self.test_sla_tracking()
            self.test_ai_services()
            
        except Exception as e:
            print(f"❌ Test suite failed with exception: {e}")
            
        finally:
            # Always try to clean up
            try:
                self.cleanup_test_data()
            except:
                pass
        
        # Print final results
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print("\n" + "="*60)
        print("📊 FINAL TEST RESULTS")
        print("="*60)
        print(f"Tests run: {self.tests_run}")
        print(f"Tests passed: {self.tests_passed}")
        print(f"Tests failed: {self.tests_run - self.tests_passed}")
        print(f"Success rate: {(self.tests_passed / self.tests_run * 100):.1f}%")
        print(f"Duration: {duration:.1f} seconds")
        
        # Return appropriate exit code
        if self.tests_passed == self.tests_run:
            print("🎉 ALL TESTS PASSED!")
            return 0
        else:
            print("❌ Some tests failed")
            return 1

def main():
    """Main test runner"""
    tester = NOCCommanderAPITester()
    return tester.run_all_tests()

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)