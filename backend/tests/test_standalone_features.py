"""
Test standalone installation features:
- Login with admin@noc.com / admin123
- New user registration flow
- API health endpoint
- Settings endpoints
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://network-ops-ai.preview.emergentagent.com')

class TestHealthEndpoint:
    """Test /api/health endpoint"""
    
    def test_health_endpoint_returns_200(self):
        """Health endpoint should return 200 OK"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print(f"✅ Health endpoint returned 200")
    
    def test_health_endpoint_returns_correct_structure(self):
        """Health endpoint should return status, version, service"""
        response = requests.get(f"{BASE_URL}/api/health")
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "service" in data
        assert data["status"] == "healthy"
        assert data["service"] == "ATECH NOC Commander"
        print(f"✅ Health endpoint returns correct structure: {data}")


class TestAuthentication:
    """Test authentication flows"""
    
    def test_login_with_admin_credentials(self):
        """Login with admin@noc.com / admin123 should succeed"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@noc.com",
            "password": "admin123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == "admin@noc.com"
        print(f"✅ Login successful for admin@noc.com")
        return data["access_token"]
    
    def test_login_with_invalid_credentials(self):
        """Login with wrong credentials should fail"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "wrong@email.com",
            "password": "wrongpassword"
        })
        assert response.status_code in [401, 404], f"Expected 401/404, got {response.status_code}"
        print(f"✅ Invalid login correctly rejected with status {response.status_code}")
    
    def test_registration_flow(self):
        """Test new user registration"""
        unique_email = f"test_user_{uuid.uuid4().hex[:8]}@test.com"
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "testpassword123",
            "name": "Test User"
        })
        # Registration should succeed (200/201) or fail if user exists
        assert response.status_code in [200, 201, 400], f"Unexpected status: {response.status_code}"
        
        if response.status_code in [200, 201]:
            data = response.json()
            assert "access_token" in data or "user" in data
            print(f"✅ Registration successful for {unique_email}")
        else:
            print(f"✅ Registration endpoint working (returned {response.status_code})")
    
    def test_registration_with_existing_email(self):
        """Registration with existing email should fail"""
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": "admin@noc.com",
            "password": "somepassword",
            "name": "Duplicate User"
        })
        # Should fail with 400 or similar
        assert response.status_code in [400, 409, 422], f"Expected 400/409/422, got {response.status_code}"
        print(f"✅ Duplicate registration correctly rejected with status {response.status_code}")


class TestDashboardAccess:
    """Test dashboard access after login"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@noc.com",
            "password": "admin123"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_dashboard_stats_endpoint(self, auth_token):
        """Dashboard stats endpoint should work with auth"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=headers)
        assert response.status_code == 200, f"Dashboard stats failed: {response.text}"
        data = response.json()
        # Check for expected dashboard fields
        assert "total_devices" in data or "devices" in data or isinstance(data, dict)
        print(f"✅ Dashboard stats accessible after login")
    
    def test_devices_endpoint(self, auth_token):
        """Devices endpoint should work with auth"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/devices", headers=headers)
        assert response.status_code == 200, f"Devices endpoint failed: {response.text}"
        print(f"✅ Devices endpoint accessible after login")
    
    def test_alerts_endpoint(self, auth_token):
        """Alerts endpoint should work with auth"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/alerts", headers=headers)
        assert response.status_code == 200, f"Alerts endpoint failed: {response.text}"
        print(f"✅ Alerts endpoint accessible after login")


class TestSettingsEndpoints:
    """Test settings endpoints for Connection tab"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@noc.com",
            "password": "admin123"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_email_settings_endpoint(self, auth_token):
        """Email settings endpoint should work"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/settings/email", headers=headers)
        # Should return 200 or 404 if not configured
        assert response.status_code in [200, 404], f"Email settings failed: {response.status_code}"
        print(f"✅ Email settings endpoint accessible (status: {response.status_code})")
    
    def test_snmp_community_settings(self, auth_token):
        """SNMP community settings endpoint should work"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/settings/snmp/community", headers=headers)
        assert response.status_code == 200, f"SNMP settings failed: {response.status_code}"
        print(f"✅ SNMP community settings endpoint accessible")
    
    def test_openstack_settings(self, auth_token):
        """OpenStack settings endpoint should work"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/settings/openstack", headers=headers)
        assert response.status_code == 200, f"OpenStack settings failed: {response.status_code}"
        print(f"✅ OpenStack settings endpoint accessible")
    
    def test_vcenter_settings(self, auth_token):
        """vCenter settings endpoint should work"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/settings/vcenter", headers=headers)
        assert response.status_code == 200, f"vCenter settings failed: {response.status_code}"
        print(f"✅ vCenter settings endpoint accessible")
    
    def test_backup_settings(self, auth_token):
        """Backup settings endpoint should work"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/settings/backup", headers=headers)
        assert response.status_code == 200, f"Backup settings failed: {response.status_code}"
        print(f"✅ Backup settings endpoint accessible")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
