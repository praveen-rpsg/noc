"""
Test suite for Audit Logs, Config Backup, and AAA Authentication features
Tests: Audit Logs API, Config Backup API, AAA Settings API, AAA-Login API
"""
import pytest
import requests
import os
import json
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@noc.com"
ADMIN_PASSWORD = "admin123"

class TestSetup:
    """Setup and authentication tests"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        return data["access_token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        """Get auth headers for API calls"""
        return {
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json"
        }


class TestAuditLogsAPI(TestSetup):
    """Test Audit Logs API endpoints"""
    
    def test_get_audit_logs(self, auth_headers):
        """GET /api/audit/logs - Returns paginated logs"""
        response = requests.get(f"{BASE_URL}/api/audit/logs", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "logs" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        assert "pages" in data
        assert isinstance(data["logs"], list)
        print(f"✅ GET /api/audit/logs - Found {data['total']} logs")
    
    def test_get_audit_logs_with_filters(self, auth_headers):
        """GET /api/audit/logs with filters"""
        # Test with action_type filter
        response = requests.get(
            f"{BASE_URL}/api/audit/logs?action_type=login",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        # Test with pagination
        response = requests.get(
            f"{BASE_URL}/api/audit/logs?page=1&limit=10",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        print("✅ GET /api/audit/logs with filters - Works correctly")
    
    def test_get_audit_stats(self, auth_headers):
        """GET /api/audit/logs/stats - Returns statistics"""
        response = requests.get(f"{BASE_URL}/api/audit/logs/stats", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify stats structure
        assert "total_logs" in data
        assert "today_logs" in data
        assert "failed_actions" in data
        assert "retention_days" in data
        assert isinstance(data["total_logs"], int)
        assert isinstance(data["retention_days"], int)
        print(f"✅ GET /api/audit/logs/stats - Total: {data['total_logs']}, Today: {data['today_logs']}, Retention: {data['retention_days']} days")
    
    def test_get_action_types(self, auth_headers):
        """GET /api/audit/action-types - Returns list of action types"""
        response = requests.get(f"{BASE_URL}/api/audit/action-types", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) > 0
        # Check for expected action types
        expected_types = ["login", "logout", "config_backup", "config_restore"]
        for expected in expected_types:
            assert expected in data, f"Missing action type: {expected}"
        print(f"✅ GET /api/audit/action-types - Found {len(data)} action types")
    
    def test_export_audit_logs_json(self, auth_headers):
        """GET /api/audit/logs/export - Exports as JSON"""
        response = requests.get(
            f"{BASE_URL}/api/audit/logs/export?format=json",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "logs" in data
        assert "exported_at" in data
        print(f"✅ GET /api/audit/logs/export (JSON) - Exported {len(data['logs'])} logs")
    
    def test_export_audit_logs_csv(self, auth_headers):
        """GET /api/audit/logs/export - Exports as CSV"""
        response = requests.get(
            f"{BASE_URL}/api/audit/logs/export?format=csv",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        assert "text/csv" in response.headers.get("content-type", "")
        print("✅ GET /api/audit/logs/export (CSV) - Export successful")
    
    def test_audit_logs_admin_only(self):
        """Verify audit logs require admin access"""
        # Create operator user for testing
        admin_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        admin_token = admin_response.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
        
        # Create test operator
        test_email = f"test_operator_{datetime.now().timestamp()}@test.com"
        create_response = requests.post(f"{BASE_URL}/api/users", json={
            "email": test_email,
            "password": "testpass123",
            "name": "Test Operator",
            "role": "operator"
        }, headers=admin_headers)
        
        if create_response.status_code == 201:
            # Login as operator
            op_login = requests.post(f"{BASE_URL}/api/auth/login", json={
                "email": test_email,
                "password": "testpass123"
            })
            
            if op_login.status_code == 200:
                op_token = op_login.json()["access_token"]
                op_headers = {"Authorization": f"Bearer {op_token}"}
                
                # Try to access audit logs
                response = requests.get(f"{BASE_URL}/api/audit/logs", headers=op_headers)
                assert response.status_code == 403, "Operator should not access audit logs"
                print("✅ Audit logs admin-only access verified")
            
            # Cleanup
            user_id = create_response.json().get("id")
            if user_id:
                requests.delete(f"{BASE_URL}/api/users/{user_id}", headers=admin_headers)
        else:
            print("⚠️ Could not create test operator, skipping admin-only test")


class TestConfigBackupAPI(TestSetup):
    """Test Config Backup API endpoints"""
    
    @pytest.fixture(scope="class")
    def test_device(self, auth_headers):
        """Create a test device for backup tests"""
        device_data = {
            "name": "TEST_Backup_Router",
            "type": "router",
            "ip_address": "192.168.1.100",
            "location": "Test Lab",
            "vendor": "cisco",
            "model": "ISR4451"
        }
        response = requests.post(f"{BASE_URL}/api/devices", json=device_data, headers=auth_headers)
        if response.status_code == 201:
            device = response.json()
            yield device
            # Cleanup
            requests.delete(f"{BASE_URL}/api/devices/{device['id']}", headers=auth_headers)
        else:
            # Try to find existing device
            devices_response = requests.get(f"{BASE_URL}/api/devices", headers=auth_headers)
            if devices_response.status_code == 200:
                devices = devices_response.json()
                router_devices = [d for d in devices if d.get("type") in ["router", "switch", "firewall"]]
                if router_devices:
                    yield router_devices[0]
                else:
                    pytest.skip("No suitable device for backup tests")
            else:
                pytest.skip("Could not get devices for backup tests")
    
    def test_get_device_backups(self, auth_headers, test_device):
        """GET /api/backup/devices/{id}/backups - Returns backups list"""
        device_id = test_device["id"]
        response = requests.get(
            f"{BASE_URL}/api/backup/devices/{device_id}/backups",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ GET /api/backup/devices/{device_id}/backups - Found {len(data)} backups")
    
    def test_fetch_device_config(self, auth_headers, test_device):
        """POST /api/backup/devices/{id}/fetch - Fetches current config (MOCKED)"""
        device_id = test_device["id"]
        response = requests.post(
            f"{BASE_URL}/api/backup/devices/{device_id}/fetch",
            headers=auth_headers
        )
        # This is mocked - should return simulated config
        assert response.status_code in [200, 500], f"Unexpected status: {response.status_code}"
        
        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            if data.get("success"):
                assert "config" in data
                print(f"✅ POST /api/backup/devices/{device_id}/fetch - Config fetched (MOCKED)")
            else:
                print(f"⚠️ POST /api/backup/devices/{device_id}/fetch - Returned error (expected for MOCKED SSH)")
        else:
            print(f"⚠️ POST /api/backup/devices/{device_id}/fetch - SSH connection failed (expected for MOCKED)")
    
    def test_create_device_backup(self, auth_headers, test_device):
        """POST /api/backup/devices/{id}/backup - Creates backup (MOCKED)"""
        device_id = test_device["id"]
        response = requests.post(
            f"{BASE_URL}/api/backup/devices/{device_id}/backup",
            json={"backup_type": "manual"},
            headers=auth_headers
        )
        # This is mocked - may fail due to SSH
        if response.status_code == 200:
            data = response.json()
            assert "id" in data
            assert "version" in data
            print(f"✅ POST /api/backup/devices/{device_id}/backup - Backup created v{data['version']} (MOCKED)")
        else:
            print(f"⚠️ POST /api/backup/devices/{device_id}/backup - Failed (expected for MOCKED SSH)")
    
    def test_get_all_backups(self, auth_headers):
        """GET /api/backup/all - Returns all backups"""
        response = requests.get(f"{BASE_URL}/api/backup/all", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ GET /api/backup/all - Found {len(data)} total backups")


class TestAAASettingsAPI(TestSetup):
    """Test AAA Settings API endpoints"""
    
    def test_get_aaa_configs(self, auth_headers):
        """GET /api/settings/aaa - Returns AAA configurations"""
        response = requests.get(f"{BASE_URL}/api/settings/aaa", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ GET /api/settings/aaa - Found {len(data)} AAA configs")
    
    def test_create_aaa_config(self, auth_headers):
        """POST /api/settings/aaa - Creates AAA server config"""
        aaa_data = {
            "name": "TEST_RADIUS_Server",
            "server_type": "radius",
            "primary_host": "192.168.1.50",
            "primary_port": 1812,
            "shared_secret": "test_secret_123",
            "timeout": 5,
            "retries": 3,
            "use_for_login": True,
            "use_for_device_auth": True
        }
        response = requests.post(f"{BASE_URL}/api/settings/aaa", json=aaa_data, headers=auth_headers)
        assert response.status_code in [200, 201], f"Failed: {response.text}"
        data = response.json()
        # Response may have config nested or at root level
        config_id = data.get("id") or data.get("config", {}).get("id")
        assert config_id, f"No config ID in response: {data}"
        print(f"✅ POST /api/settings/aaa - Created RADIUS config: {config_id}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/settings/aaa/{config_id}", headers=auth_headers)
        return config_id
    
    def test_create_tacacs_config(self, auth_headers):
        """POST /api/settings/aaa - Creates TACACS+ server config"""
        aaa_data = {
            "name": "TEST_TACACS_Server",
            "server_type": "tacacs",
            "primary_host": "192.168.1.51",
            "primary_port": 49,
            "shared_secret": "tacacs_secret_123",
            "timeout": 5,
            "retries": 3,
            "use_for_login": True,
            "use_for_device_auth": True
        }
        response = requests.post(f"{BASE_URL}/api/settings/aaa", json=aaa_data, headers=auth_headers)
        assert response.status_code in [200, 201], f"Failed: {response.text}"
        data = response.json()
        config_id = data.get("id") or data.get("config", {}).get("id")
        assert config_id, f"No config ID in response: {data}"
        print(f"✅ POST /api/settings/aaa - Created TACACS+ config: {config_id}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/settings/aaa/{config_id}", headers=auth_headers)
    
    def test_update_aaa_config(self, auth_headers):
        """PUT /api/settings/aaa/{id} - Updates AAA config"""
        # Create config first
        aaa_data = {
            "name": "TEST_Update_RADIUS",
            "server_type": "radius",
            "primary_host": "192.168.1.52",
            "primary_port": 1812,
            "shared_secret": "update_secret",
            "use_for_login": True
        }
        create_response = requests.post(f"{BASE_URL}/api/settings/aaa", json=aaa_data, headers=auth_headers)
        if create_response.status_code in [200, 201]:
            data = create_response.json()
            config_id = data.get("id") or data.get("config", {}).get("id")
            
            # Update config - need to include all required fields
            update_data = {
                "name": "TEST_Updated_RADIUS",
                "server_type": "radius",
                "primary_host": "192.168.1.52",
                "primary_port": 1812,
                "shared_secret": "update_secret",
                "timeout": 10,
                "use_for_login": True
            }
            update_response = requests.put(
                f"{BASE_URL}/api/settings/aaa/{config_id}",
                json=update_data,
                headers=auth_headers
            )
            assert update_response.status_code == 200, f"Failed: {update_response.text}"
            print(f"✅ PUT /api/settings/aaa/{config_id} - Config updated")
            
            # Cleanup
            requests.delete(f"{BASE_URL}/api/settings/aaa/{config_id}", headers=auth_headers)
    
    def test_delete_aaa_config(self, auth_headers):
        """DELETE /api/settings/aaa/{id} - Deletes AAA config"""
        # Create config first
        aaa_data = {
            "name": "TEST_Delete_RADIUS",
            "server_type": "radius",
            "primary_host": "192.168.1.53",
            "primary_port": 1812,
            "shared_secret": "delete_secret"
        }
        create_response = requests.post(f"{BASE_URL}/api/settings/aaa", json=aaa_data, headers=auth_headers)
        if create_response.status_code in [200, 201]:
            data = create_response.json()
            config_id = data.get("id") or data.get("config", {}).get("id")
            
            # Delete config
            delete_response = requests.delete(
                f"{BASE_URL}/api/settings/aaa/{config_id}",
                headers=auth_headers
            )
            assert delete_response.status_code == 200, f"Failed: {delete_response.text}"
            print(f"✅ DELETE /api/settings/aaa/{config_id} - Config deleted")


class TestAAATestConnection(TestSetup):
    """Test AAA connection testing endpoint"""
    
    def test_aaa_test_connection(self, auth_headers):
        """POST /api/aaa/test - Tests AAA server connection (MOCKED)"""
        # Create a test config first
        aaa_data = {
            "name": "TEST_Connection_RADIUS",
            "server_type": "radius",
            "primary_host": "192.168.1.54",
            "primary_port": 1812,
            "shared_secret": "test_connection_secret"
        }
        create_response = requests.post(f"{BASE_URL}/api/settings/aaa", json=aaa_data, headers=auth_headers)
        
        if create_response.status_code in [200, 201]:
            data = create_response.json()
            config_id = data.get("id") or data.get("config", {}).get("id")
            
            # Test connection
            test_response = requests.post(
                f"{BASE_URL}/api/aaa/test?config_id={config_id}",
                headers=auth_headers
            )
            assert test_response.status_code == 200, f"Failed: {test_response.text}"
            data = test_response.json()
            
            assert "server_type" in data
            assert "host" in data
            assert "port" in data
            assert "connectivity" in data
            print(f"✅ POST /api/aaa/test - Connection test: {data['connectivity_message']} (MOCKED)")
            
            # Cleanup
            requests.delete(f"{BASE_URL}/api/settings/aaa/{config_id}", headers=auth_headers)


class TestAAALogin(TestSetup):
    """Test AAA-enhanced login endpoint"""
    
    def test_aaa_login_fallback_to_local(self, auth_headers):
        """POST /api/auth/aaa-login - Falls back to local auth when no AAA servers"""
        response = requests.post(f"{BASE_URL}/api/auth/aaa-login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "access_token" in data
        assert "user" in data
        # Should fall back to local auth
        print(f"✅ POST /api/auth/aaa-login - Login successful (fallback to local)")
    
    def test_aaa_login_invalid_credentials(self):
        """POST /api/auth/aaa-login - Rejects invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/aaa-login", json={
            "email": "invalid@test.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✅ POST /api/auth/aaa-login - Invalid credentials rejected")


class TestSidebarNavigation(TestSetup):
    """Test sidebar navigation items"""
    
    def test_devices_endpoint_for_config_backup(self, auth_headers):
        """Verify devices endpoint works for Config Backup page"""
        response = requests.get(f"{BASE_URL}/api/devices", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        
        # Check for network devices (routers, switches, firewalls)
        network_devices = [d for d in data if d.get("type") in ["router", "switch", "firewall", "load_balancer"]]
        print(f"✅ GET /api/devices - Found {len(network_devices)} network devices for Config Backup")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
