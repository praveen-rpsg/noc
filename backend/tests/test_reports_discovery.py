"""
Test suite for Enhanced Reports and Network Discovery features
- Daily Health Report with CPU, memory, traffic, interface metrics
- Incident Summary Report with suggested RCA, hardware replacement, IOS bugs
- Device Inventory Report with OEM, location, warranty status
- Network Discovery auto-add to devices and assets collections
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestReportGeneration:
    """Test enhanced report generation APIs"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authentication for all tests"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@noc.com",
            "password": "admin123"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        token = login_response.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    # ==================== DAILY HEALTH REPORT TESTS ====================
    
    def test_daily_health_report_generation(self):
        """Test daily_health report returns device_health array"""
        response = self.session.post(
            f"{BASE_URL}/api/reports/generate",
            params={
                "report_type": "daily_health",
                "period_start": "2026-01-01",
                "period_end": "2026-01-07"
            }
        )
        assert response.status_code == 200, f"Report generation failed: {response.text}"
        
        data = response.json()
        content = data.get("content", {})
        
        # Verify device_health array exists
        assert "device_health" in content, "device_health array missing from daily_health report"
        assert isinstance(content["device_health"], list), "device_health should be a list"
    
    def test_daily_health_cpu_metrics(self):
        """Test daily_health report contains CPU metrics"""
        response = self.session.post(
            f"{BASE_URL}/api/reports/generate",
            params={
                "report_type": "daily_health",
                "period_start": "2026-01-01",
                "period_end": "2026-01-07"
            }
        )
        assert response.status_code == 200
        
        content = response.json().get("content", {})
        device_health = content.get("device_health", [])
        
        if len(device_health) > 0:
            device = device_health[0]
            # Verify CPU metrics
            assert "cpu_usage_percent" in device, "cpu_usage_percent missing"
            assert "cpu_status" in device, "cpu_status missing"
            assert isinstance(device["cpu_usage_percent"], (int, float)), "cpu_usage_percent should be numeric"
            assert device["cpu_status"] in ["Normal", "Warning", "Critical"], f"Invalid cpu_status: {device['cpu_status']}"
    
    def test_daily_health_memory_metrics(self):
        """Test daily_health report contains memory metrics including dead memory"""
        response = self.session.post(
            f"{BASE_URL}/api/reports/generate",
            params={
                "report_type": "daily_health",
                "period_start": "2026-01-01",
                "period_end": "2026-01-07"
            }
        )
        assert response.status_code == 200
        
        content = response.json().get("content", {})
        device_health = content.get("device_health", [])
        
        if len(device_health) > 0:
            device = device_health[0]
            # Verify memory metrics
            assert "memory_usage_percent" in device, "memory_usage_percent missing"
            assert "memory_status" in device, "memory_status missing"
            assert "dead_memory_percent" in device, "dead_memory_percent missing"
            assert isinstance(device["memory_usage_percent"], (int, float)), "memory_usage_percent should be numeric"
            assert isinstance(device["dead_memory_percent"], (int, float)), "dead_memory_percent should be numeric"
    
    def test_daily_health_traffic_metrics(self):
        """Test daily_health report contains traffic metrics"""
        response = self.session.post(
            f"{BASE_URL}/api/reports/generate",
            params={
                "report_type": "daily_health",
                "period_start": "2026-01-01",
                "period_end": "2026-01-07"
            }
        )
        assert response.status_code == 200
        
        content = response.json().get("content", {})
        device_health = content.get("device_health", [])
        
        if len(device_health) > 0:
            device = device_health[0]
            # Verify traffic metrics
            assert "traffic_in_mbps" in device, "traffic_in_mbps missing"
            assert "traffic_out_mbps" in device, "traffic_out_mbps missing"
            assert "peak_traffic_mbps" in device, "peak_traffic_mbps missing"
            assert isinstance(device["traffic_in_mbps"], (int, float)), "traffic_in_mbps should be numeric"
            assert isinstance(device["traffic_out_mbps"], (int, float)), "traffic_out_mbps should be numeric"
    
    def test_daily_health_interface_status(self):
        """Test daily_health report contains interface status metrics"""
        response = self.session.post(
            f"{BASE_URL}/api/reports/generate",
            params={
                "report_type": "daily_health",
                "period_start": "2026-01-01",
                "period_end": "2026-01-07"
            }
        )
        assert response.status_code == 200
        
        content = response.json().get("content", {})
        device_health = content.get("device_health", [])
        
        if len(device_health) > 0:
            device = device_health[0]
            # Verify interface metrics
            assert "total_interfaces" in device, "total_interfaces missing"
            assert "interfaces_up" in device, "interfaces_up missing"
            assert "interfaces_down" in device, "interfaces_down missing"
            assert "interfaces_admin_down" in device, "interfaces_admin_down missing"
            assert "free_interfaces" in device, "free_interfaces missing"
            assert "interface_utilization_percent" in device, "interface_utilization_percent missing"
    
    # ==================== INCIDENT SUMMARY REPORT TESTS ====================
    
    def test_incident_summary_report_generation(self):
        """Test incident_summary report returns incidents array"""
        response = self.session.post(
            f"{BASE_URL}/api/reports/generate",
            params={
                "report_type": "incident_summary",
                "period_start": "2026-01-01",
                "period_end": "2026-01-07"
            }
        )
        assert response.status_code == 200, f"Report generation failed: {response.text}"
        
        data = response.json()
        content = data.get("content", {})
        
        # Verify incidents array exists
        assert "incidents" in content, "incidents array missing from incident_summary report"
        assert isinstance(content["incidents"], list), "incidents should be a list"
    
    def test_incident_summary_suggested_rca(self):
        """Test incident_summary report contains suggested_rca field"""
        response = self.session.post(
            f"{BASE_URL}/api/reports/generate",
            params={
                "report_type": "incident_summary",
                "period_start": "2026-01-01",
                "period_end": "2026-01-07"
            }
        )
        assert response.status_code == 200
        
        content = response.json().get("content", {})
        incidents = content.get("incidents", [])
        
        if len(incidents) > 0:
            incident = incidents[0]
            # Verify suggested_rca field
            assert "suggested_rca" in incident, "suggested_rca missing from incident"
            assert "rca_category" in incident, "rca_category missing from incident"
    
    def test_incident_summary_hardware_replacement(self):
        """Test incident_summary report contains hardware_replacement_required field"""
        response = self.session.post(
            f"{BASE_URL}/api/reports/generate",
            params={
                "report_type": "incident_summary",
                "period_start": "2026-01-01",
                "period_end": "2026-01-07"
            }
        )
        assert response.status_code == 200
        
        content = response.json().get("content", {})
        incidents = content.get("incidents", [])
        
        if len(incidents) > 0:
            incident = incidents[0]
            # Verify hardware_replacement_required field
            assert "hardware_replacement_required" in incident, "hardware_replacement_required missing"
            assert incident["hardware_replacement_required"] in ["Possible", "Not Required"], \
                f"Invalid hardware_replacement_required value: {incident['hardware_replacement_required']}"
    
    def test_incident_summary_ios_bug_report(self):
        """Test incident_summary report contains ios_bug_report field"""
        response = self.session.post(
            f"{BASE_URL}/api/reports/generate",
            params={
                "report_type": "incident_summary",
                "period_start": "2026-01-01",
                "period_end": "2026-01-07"
            }
        )
        assert response.status_code == 200
        
        content = response.json().get("content", {})
        incidents = content.get("incidents", [])
        
        if len(incidents) > 0:
            incident = incidents[0]
            # Verify ios_bug_report field
            assert "ios_bug_report" in incident, "ios_bug_report missing"
            assert incident["ios_bug_report"] in ["Check Cisco Bug Search", "N/A"], \
                f"Invalid ios_bug_report value: {incident['ios_bug_report']}"
    
    def test_incident_summary_summary_stats(self):
        """Test incident_summary report contains summary with hardware_issues and potential_ios_bugs"""
        response = self.session.post(
            f"{BASE_URL}/api/reports/generate",
            params={
                "report_type": "incident_summary",
                "period_start": "2026-01-01",
                "period_end": "2026-01-07"
            }
        )
        assert response.status_code == 200
        
        content = response.json().get("content", {})
        summary = content.get("summary", {})
        
        # Verify summary contains hardware and bug counts
        assert "hardware_issues" in summary, "hardware_issues missing from summary"
        assert "potential_ios_bugs" in summary, "potential_ios_bugs missing from summary"
        assert isinstance(summary["hardware_issues"], int), "hardware_issues should be integer"
        assert isinstance(summary["potential_ios_bugs"], int), "potential_ios_bugs should be integer"
    
    # ==================== DEVICE INVENTORY REPORT TESTS ====================
    
    def test_device_inventory_report_generation(self):
        """Test device_inventory report returns inventory array"""
        response = self.session.post(
            f"{BASE_URL}/api/reports/generate",
            params={
                "report_type": "device_inventory",
                "period_start": "2026-01-01",
                "period_end": "2026-01-07"
            }
        )
        assert response.status_code == 200, f"Report generation failed: {response.text}"
        
        data = response.json()
        content = data.get("content", {})
        
        # Verify inventory array exists
        assert "inventory" in content, "inventory array missing from device_inventory report"
        assert isinstance(content["inventory"], list), "inventory should be a list"
    
    def test_device_inventory_oem_vendor(self):
        """Test device_inventory report contains oem_vendor field"""
        response = self.session.post(
            f"{BASE_URL}/api/reports/generate",
            params={
                "report_type": "device_inventory",
                "period_start": "2026-01-01",
                "period_end": "2026-01-07"
            }
        )
        assert response.status_code == 200
        
        content = response.json().get("content", {})
        inventory = content.get("inventory", [])
        
        if len(inventory) > 0:
            item = inventory[0]
            # Verify OEM fields
            assert "oem_vendor" in item, "oem_vendor missing"
            assert "oem_details" in item, "oem_details missing"
            assert "oem_support_contract" in item, "oem_support_contract missing"
    
    def test_device_inventory_location(self):
        """Test device_inventory report contains location fields"""
        response = self.session.post(
            f"{BASE_URL}/api/reports/generate",
            params={
                "report_type": "device_inventory",
                "period_start": "2026-01-01",
                "period_end": "2026-01-07"
            }
        )
        assert response.status_code == 200
        
        content = response.json().get("content", {})
        inventory = content.get("inventory", [])
        
        if len(inventory) > 0:
            item = inventory[0]
            # Verify location fields
            assert "location" in item, "location missing"
            assert "rack_position" in item, "rack_position missing"
            assert "building" in item, "building missing"
            assert "floor" in item, "floor missing"
    
    def test_device_inventory_warranty_status(self):
        """Test device_inventory report contains warranty_status field"""
        response = self.session.post(
            f"{BASE_URL}/api/reports/generate",
            params={
                "report_type": "device_inventory",
                "period_start": "2026-01-01",
                "period_end": "2026-01-07"
            }
        )
        assert response.status_code == 200
        
        content = response.json().get("content", {})
        inventory = content.get("inventory", [])
        
        if len(inventory) > 0:
            item = inventory[0]
            # Verify warranty fields
            assert "warranty_status" in item, "warranty_status missing"
            assert "warranty_expiry" in item, "warranty_expiry missing"
            assert item["warranty_status"] in ["Active", "Expiring Soon", "Expired", "Unknown"], \
                f"Invalid warranty_status: {item['warranty_status']}"
    
    def test_device_inventory_by_vendor_breakdown(self):
        """Test device_inventory report contains by_vendor breakdown"""
        response = self.session.post(
            f"{BASE_URL}/api/reports/generate",
            params={
                "report_type": "device_inventory",
                "period_start": "2026-01-01",
                "period_end": "2026-01-07"
            }
        )
        assert response.status_code == 200
        
        content = response.json().get("content", {})
        
        # Verify by_vendor breakdown exists
        assert "by_vendor" in content, "by_vendor breakdown missing"
        assert isinstance(content["by_vendor"], dict), "by_vendor should be a dictionary"
    
    def test_device_inventory_by_location_breakdown(self):
        """Test device_inventory report contains by_location breakdown"""
        response = self.session.post(
            f"{BASE_URL}/api/reports/generate",
            params={
                "report_type": "device_inventory",
                "period_start": "2026-01-01",
                "period_end": "2026-01-07"
            }
        )
        assert response.status_code == 200
        
        content = response.json().get("content", {})
        
        # Verify by_location breakdown exists
        assert "by_location" in content, "by_location breakdown missing"
        assert isinstance(content["by_location"], dict), "by_location should be a dictionary"


class TestAssetDeviceLink:
    """Test that assets collection has device_id field for linking to monitoring devices"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authentication for all tests"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@noc.com",
            "password": "admin123"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        token = login_response.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_assets_have_device_id_field(self):
        """Test that assets collection includes device_id field"""
        response = self.session.get(f"{BASE_URL}/api/assets")
        assert response.status_code == 200, f"Failed to get assets: {response.text}"
        
        assets = response.json()
        if len(assets) > 0:
            asset = assets[0]
            # Verify device_id field exists (can be null for manually created assets)
            assert "device_id" in asset, "device_id field missing from asset"
    
    def test_assets_have_discovery_fields(self):
        """Test that assets collection includes discovery-related fields"""
        response = self.session.get(f"{BASE_URL}/api/assets")
        assert response.status_code == 200, f"Failed to get assets: {response.text}"
        
        assets = response.json()
        if len(assets) > 0:
            asset = assets[0]
            # Verify discovery fields exist
            assert "auto_discovered" in asset, "auto_discovered field missing from asset"
            assert "discovery_method" in asset, "discovery_method field missing from asset"
            assert "ip_address" in asset, "ip_address field missing from asset"
            assert "mac_address" in asset, "mac_address field missing from asset"


class TestNetworkDiscoveryEndpoints:
    """Test network discovery API endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authentication for all tests"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@noc.com",
            "password": "admin123"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        token = login_response.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_discovery_jobs_endpoint(self):
        """Test GET /api/network/discovery/jobs endpoint exists"""
        response = self.session.get(f"{BASE_URL}/api/network/discovery/jobs")
        # Should return 200 with list of jobs (may be empty)
        assert response.status_code == 200, f"Discovery jobs endpoint failed: {response.text}"
        assert isinstance(response.json(), list), "Discovery jobs should return a list"
    
    def test_discovery_pending_endpoint(self):
        """Test GET /api/network/discovery/pending endpoint exists"""
        response = self.session.get(f"{BASE_URL}/api/network/discovery/pending")
        # Should return 200 with list of pending requests (may be empty)
        assert response.status_code == 200, f"Discovery pending endpoint failed: {response.text}"
        assert isinstance(response.json(), list), "Discovery pending should return a list"
    
    def test_discovery_request_endpoint_exists(self):
        """Test POST /api/network/discovery/request endpoint exists"""
        # We don't actually run discovery (would need network access)
        # Just verify the endpoint exists and validates input
        response = self.session.post(
            f"{BASE_URL}/api/network/discovery/request",
            json={
                "network_ranges": ["192.168.1.0/24"],
                "snmp_communities": ["public"],
                "methods": ["ping_sweep"]
            }
        )
        # Should return 200 (request created) or 400/422 (validation error)
        # Not 404 (endpoint not found)
        assert response.status_code != 404, "Discovery request endpoint not found"


class TestReportsList:
    """Test reports list and retrieval"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authentication for all tests"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@noc.com",
            "password": "admin123"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        token = login_response.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_get_reports_list(self):
        """Test GET /api/reports returns list of reports"""
        response = self.session.get(f"{BASE_URL}/api/reports")
        assert response.status_code == 200, f"Failed to get reports: {response.text}"
        
        reports = response.json()
        assert isinstance(reports, list), "Reports should be a list"
    
    def test_report_generation_all_types(self):
        """Test that all expected report types can be generated"""
        expected_types = ["daily_health", "incident_summary", "device_inventory", "sla_compliance"]
        
        for report_type in expected_types:
            response = self.session.post(
                f"{BASE_URL}/api/reports/generate",
                params={
                    "report_type": report_type,
                    "period_start": "2026-01-01",
                    "period_end": "2026-01-07"
                }
            )
            assert response.status_code == 200, f"Failed to generate {report_type} report: {response.text}"
            data = response.json()
            assert "content" in data, f"Report {report_type} missing content"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
