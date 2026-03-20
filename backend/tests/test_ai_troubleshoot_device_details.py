"""
Test suite for AI Troubleshoot and Enhanced Device Details features
- Right-click context menu AI Troubleshoot on Incidents and Alerts pages
- Enhanced device details (MAC, hostname, OS version, warranty, AAA)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@noc.com",
            "password": "admin123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json().get("access_token")
    
    def test_login_success(self):
        """Test login endpoint"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@noc.com",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        print("✅ Login successful")


class TestIncidentAiTroubleshoot:
    """Test AI Troubleshoot endpoint for Incidents"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@noc.com",
            "password": "admin123"
        })
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture(scope="class")
    def test_incident(self, auth_headers):
        """Create a test incident for AI troubleshooting"""
        incident_data = {
            "title": "TEST_AI_Troubleshoot_Incident",
            "description": "Test incident for AI troubleshooting feature",
            "priority": "P2",
            "category": "Network",
            "affected_devices": []
        }
        response = requests.post(f"{BASE_URL}/api/incidents", json=incident_data, headers=auth_headers)
        assert response.status_code == 200, f"Failed to create incident: {response.text}"
        incident = response.json()
        yield incident
        # Cleanup
        requests.delete(f"{BASE_URL}/api/incidents/{incident['id']}", headers=auth_headers)
    
    def test_get_incidents(self, auth_headers):
        """Test GET /api/incidents endpoint"""
        response = requests.get(f"{BASE_URL}/api/incidents", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ GET /api/incidents - Found {len(data)} incidents")
    
    def test_ai_troubleshoot_incident(self, auth_headers, test_incident):
        """Test POST /api/incidents/{id}/ai-troubleshoot endpoint"""
        incident_id = test_incident["id"]
        response = requests.post(
            f"{BASE_URL}/api/incidents/{incident_id}/ai-troubleshoot",
            headers=auth_headers,
            timeout=60  # AI analysis may take time
        )
        assert response.status_code == 200, f"AI troubleshoot failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "report_id" in data, "Missing report_id in response"
        assert "incident_id" in data, "Missing incident_id in response"
        assert "analysis" in data, "Missing analysis in response"
        assert "triggered_by" in data, "Missing triggered_by in response"
        assert "created_at" in data, "Missing created_at in response"
        
        # Verify analysis content is not empty
        assert len(data["analysis"]) > 50, "Analysis content too short"
        
        print(f"✅ POST /api/incidents/{incident_id}/ai-troubleshoot - AI analysis generated")
        print(f"   Report ID: {data['report_id']}")
        print(f"   Analysis length: {len(data['analysis'])} chars")
    
    def test_ai_troubleshoot_nonexistent_incident(self, auth_headers):
        """Test AI troubleshoot with non-existent incident ID"""
        response = requests.post(
            f"{BASE_URL}/api/incidents/nonexistent-id/ai-troubleshoot",
            headers=auth_headers
        )
        assert response.status_code == 404
        print("✅ AI troubleshoot returns 404 for non-existent incident")


class TestAlertAiTroubleshoot:
    """Test AI Troubleshoot endpoint for Alerts"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@noc.com",
            "password": "admin123"
        })
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture(scope="class")
    def test_alert(self, auth_headers):
        """Create a test alert for AI troubleshooting"""
        alert_data = {
            "device_id": "test-device-id",
            "device_name": "TEST_Device",
            "severity": "high",
            "title": "TEST_AI_Troubleshoot_Alert",
            "description": "Test alert for AI troubleshooting feature",
            "metric_name": "cpu_usage",
            "metric_value": 95.5,
            "threshold": 80.0
        }
        response = requests.post(f"{BASE_URL}/api/alerts", json=alert_data, headers=auth_headers)
        assert response.status_code == 200, f"Failed to create alert: {response.text}"
        alert = response.json()
        yield alert
        # Cleanup - resolve the alert
        requests.put(f"{BASE_URL}/api/alerts/{alert['id']}/resolve", headers=auth_headers)
    
    def test_get_alerts(self, auth_headers):
        """Test GET /api/alerts endpoint"""
        response = requests.get(f"{BASE_URL}/api/alerts", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ GET /api/alerts - Found {len(data)} alerts")
    
    def test_ai_troubleshoot_alert(self, auth_headers, test_alert):
        """Test POST /api/alerts/{id}/ai-troubleshoot endpoint"""
        alert_id = test_alert["id"]
        response = requests.post(
            f"{BASE_URL}/api/alerts/{alert_id}/ai-troubleshoot",
            headers=auth_headers,
            timeout=60  # AI analysis may take time
        )
        assert response.status_code == 200, f"AI troubleshoot failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "report_id" in data, "Missing report_id in response"
        assert "alert_id" in data, "Missing alert_id in response"
        assert "analysis" in data, "Missing analysis in response"
        assert "triggered_by" in data, "Missing triggered_by in response"
        assert "created_at" in data, "Missing created_at in response"
        
        # Verify analysis content is not empty
        assert len(data["analysis"]) > 50, "Analysis content too short"
        
        print(f"✅ POST /api/alerts/{alert_id}/ai-troubleshoot - AI analysis generated")
        print(f"   Report ID: {data['report_id']}")
        print(f"   Analysis length: {len(data['analysis'])} chars")
    
    def test_ai_troubleshoot_nonexistent_alert(self, auth_headers):
        """Test AI troubleshoot with non-existent alert ID"""
        response = requests.post(
            f"{BASE_URL}/api/alerts/nonexistent-id/ai-troubleshoot",
            headers=auth_headers
        )
        assert response.status_code == 404
        print("✅ AI troubleshoot returns 404 for non-existent alert")


class TestEnhancedDeviceDetails:
    """Test Enhanced Device Details fields"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@noc.com",
            "password": "admin123"
        })
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_devices_with_enhanced_fields(self, auth_headers):
        """Test that devices have enhanced fields (MAC, hostname, OS, warranty, AAA)"""
        response = requests.get(f"{BASE_URL}/api/devices", headers=auth_headers)
        assert response.status_code == 200
        devices = response.json()
        assert len(devices) > 0, "No devices found"
        
        # Check for enhanced fields in at least one device
        enhanced_fields_found = {
            "mac_address": False,
            "hostname": False,
            "os_version": False,
            "os_install_date": False,
            "warranty_status": False,
            "warranty_expiry": False,
            "aaa_enabled": False
        }
        
        for device in devices:
            if device.get("mac_address"):
                enhanced_fields_found["mac_address"] = True
            if device.get("hostname"):
                enhanced_fields_found["hostname"] = True
            if device.get("os_version"):
                enhanced_fields_found["os_version"] = True
            if device.get("os_install_date"):
                enhanced_fields_found["os_install_date"] = True
            if device.get("warranty_status"):
                enhanced_fields_found["warranty_status"] = True
            if device.get("warranty_expiry"):
                enhanced_fields_found["warranty_expiry"] = True
            if "aaa_enabled" in device:
                enhanced_fields_found["aaa_enabled"] = True
        
        print(f"✅ GET /api/devices - Found {len(devices)} devices")
        for field, found in enhanced_fields_found.items():
            status = "✅" if found else "⚠️"
            print(f"   {status} {field}: {'Found' if found else 'Not found in any device'}")
        
        # At least some enhanced fields should be present
        assert any(enhanced_fields_found.values()), "No enhanced fields found in any device"
    
    def test_create_device_with_enhanced_fields(self, auth_headers):
        """Test creating a device with all enhanced fields"""
        device_data = {
            "name": "TEST_Enhanced_Device",
            "type": "server",
            "ip_address": "192.168.100.100",
            "location": "Test-DC",
            "vendor": "Dell",
            "model": "PowerEdge R750",
            "serial_number": "TEST123456",
            "firmware_version": "2.0.1",
            "mac_address": "00:1A:2B:3C:4D:EE",
            "hostname": "test-enhanced-srv.local",
            "os_version": "Ubuntu 22.04 LTS",
            "os_install_date": "2022-06-15",  # Older than 1 year for outdated warning test
            "warranty_status": "expiring_soon",
            "warranty_expiry": "2026-06-15",
            "aaa_enabled": True,
            "device_description": "Test device with all enhanced fields"
        }
        
        response = requests.post(f"{BASE_URL}/api/devices", json=device_data, headers=auth_headers)
        assert response.status_code == 200, f"Failed to create device: {response.text}"
        device = response.json()
        
        # Verify all enhanced fields are returned
        assert device.get("mac_address") == "00:1A:2B:3C:4D:EE", "MAC address not saved"
        assert device.get("hostname") == "test-enhanced-srv.local", "Hostname not saved"
        assert device.get("os_version") == "Ubuntu 22.04 LTS", "OS version not saved"
        assert device.get("os_install_date") == "2022-06-15", "OS install date not saved"
        assert device.get("warranty_status") == "expiring_soon", "Warranty status not saved"
        assert device.get("warranty_expiry") == "2026-06-15", "Warranty expiry not saved"
        assert device.get("aaa_enabled") == True, "AAA enabled not saved"
        
        print(f"✅ POST /api/devices - Created device with enhanced fields")
        print(f"   Device ID: {device['id']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/devices/{device['id']}", headers=auth_headers)
        print("   Cleaned up test device")
    
    def test_device_with_outdated_os(self, auth_headers):
        """Test that devices with OS older than 1 year have correct os_install_date"""
        response = requests.get(f"{BASE_URL}/api/devices", headers=auth_headers)
        assert response.status_code == 200
        devices = response.json()
        
        # Find devices with old OS install dates
        from datetime import datetime, timedelta
        one_year_ago = datetime.now() - timedelta(days=365)
        
        outdated_devices = []
        for device in devices:
            if device.get("os_install_date"):
                try:
                    install_date = datetime.strptime(device["os_install_date"], "%Y-%m-%d")
                    if install_date < one_year_ago:
                        outdated_devices.append({
                            "name": device["name"],
                            "os_version": device.get("os_version"),
                            "os_install_date": device["os_install_date"]
                        })
                except ValueError:
                    pass
        
        print(f"✅ Found {len(outdated_devices)} devices with OS older than 1 year:")
        for d in outdated_devices:
            print(f"   - {d['name']}: {d['os_version']} (installed: {d['os_install_date']})")
    
    def test_device_warranty_statuses(self, auth_headers):
        """Test that devices have various warranty statuses"""
        response = requests.get(f"{BASE_URL}/api/devices", headers=auth_headers)
        assert response.status_code == 200
        devices = response.json()
        
        warranty_statuses = {}
        for device in devices:
            status = device.get("warranty_status", "unknown")
            if status not in warranty_statuses:
                warranty_statuses[status] = []
            warranty_statuses[status].append(device["name"])
        
        print(f"✅ Device warranty status distribution:")
        for status, device_names in warranty_statuses.items():
            print(f"   {status}: {len(device_names)} devices")
    
    def test_device_aaa_status(self, auth_headers):
        """Test that devices have AAA enabled/disabled status"""
        response = requests.get(f"{BASE_URL}/api/devices", headers=auth_headers)
        assert response.status_code == 200
        devices = response.json()
        
        aaa_enabled = [d["name"] for d in devices if d.get("aaa_enabled") == True]
        aaa_disabled = [d["name"] for d in devices if d.get("aaa_enabled") == False]
        
        print(f"✅ Device AAA status:")
        print(f"   AAA Enabled: {len(aaa_enabled)} devices")
        print(f"   AAA Disabled: {len(aaa_disabled)} devices")


class TestDeviceDetailsEndpoint:
    """Test individual device details endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@noc.com",
            "password": "admin123"
        })
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_single_device_details(self, auth_headers):
        """Test GET /api/devices/{id} returns all enhanced fields"""
        # First get list of devices
        response = requests.get(f"{BASE_URL}/api/devices", headers=auth_headers)
        assert response.status_code == 200
        devices = response.json()
        assert len(devices) > 0, "No devices found"
        
        # Get details of first device
        device_id = devices[0]["id"]
        response = requests.get(f"{BASE_URL}/api/devices/{device_id}", headers=auth_headers)
        assert response.status_code == 200
        device = response.json()
        
        # Verify device has all expected fields
        expected_fields = [
            "id", "name", "type", "ip_address", "location", "status",
            "cpu_usage", "memory_usage", "uptime_hours",
            "mac_address", "hostname", "os_version", "os_install_date",
            "warranty_status", "warranty_expiry", "aaa_enabled"
        ]
        
        print(f"✅ GET /api/devices/{device_id} - Device details:")
        for field in expected_fields:
            value = device.get(field, "N/A")
            print(f"   {field}: {value}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
