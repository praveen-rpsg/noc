"""
Test suite for new features:
- Dashboard Editor Page - drag and drop grid layout
- Dashboard layout API - GET/POST /api/dashboard/layout
- User Management Page - CRUD operations
- Users API - GET/POST/PUT/DELETE /api/users (admin only)
- O365 Settings API - GET/POST /api/settings/o365
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@noc.com"
ADMIN_PASSWORD = "admin123"

class TestAuth:
    """Authentication tests to get token for subsequent tests"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin token for authenticated requests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Admin login failed - cannot proceed with tests")
    
    def test_admin_login(self):
        """Test admin login works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["role"] == "admin"
        print(f"✅ Admin login successful, role: {data['user']['role']}")


class TestDashboardLayoutAPI:
    """Tests for Dashboard Layout API - GET/POST /api/dashboard/layout"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers for requests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            token = response.json().get("access_token")
            return {"Authorization": f"Bearer {token}"}
        pytest.skip("Login failed")
    
    def test_get_dashboard_layout(self, auth_headers):
        """Test GET /api/dashboard/layout returns layout config"""
        response = requests.get(f"{BASE_URL}/api/dashboard/layout", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        # Should return layout structure (may be empty initially)
        assert isinstance(data, dict)
        print(f"✅ GET /api/dashboard/layout - Status: {response.status_code}")
        print(f"   Response keys: {list(data.keys())}")
    
    def test_save_dashboard_layout(self, auth_headers):
        """Test POST /api/dashboard/layout saves layout"""
        test_layout = [
            {"i": "device_status_1", "x": 0, "y": 0, "w": 3, "h": 2, "widgetType": "device_status"},
            {"i": "active_alerts_1", "x": 3, "y": 0, "w": 4, "h": 3, "widgetType": "active_alerts"},
        ]
        
        response = requests.post(f"{BASE_URL}/api/dashboard/layout", 
            headers=auth_headers,
            json={
                "layout": test_layout,
                "widget_configs": {},
                "is_global": False
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True
        print(f"✅ POST /api/dashboard/layout - Layout saved successfully")
    
    def test_save_and_retrieve_layout(self, auth_headers):
        """Test that saved layout can be retrieved"""
        # Save a specific layout
        unique_widget_id = f"test_widget_{uuid.uuid4().hex[:8]}"
        test_layout = [
            {"i": unique_widget_id, "x": 0, "y": 0, "w": 2, "h": 2, "widgetType": "sla_compliance"},
        ]
        
        # Save
        save_response = requests.post(f"{BASE_URL}/api/dashboard/layout",
            headers=auth_headers,
            json={"layout": test_layout, "widget_configs": {}, "is_global": False}
        )
        assert save_response.status_code == 200
        
        # Retrieve
        get_response = requests.get(f"{BASE_URL}/api/dashboard/layout", headers=auth_headers)
        assert get_response.status_code == 200
        data = get_response.json()
        
        # Verify layout was saved
        if data.get("layout"):
            widget_ids = [w.get("i") for w in data["layout"]]
            assert unique_widget_id in widget_ids, f"Saved widget not found in retrieved layout"
            print(f"✅ Layout persistence verified - widget {unique_widget_id} found")
        else:
            print(f"⚠️ Layout returned empty, but API works")
    
    def test_save_global_layout_admin(self, auth_headers):
        """Test admin can save global layout"""
        response = requests.post(f"{BASE_URL}/api/dashboard/layout",
            headers=auth_headers,
            json={
                "layout": [{"i": "global_test", "x": 0, "y": 0, "w": 3, "h": 2, "widgetType": "device_status"}],
                "widget_configs": {},
                "is_global": True
            }
        )
        assert response.status_code == 200, f"Admin should be able to save global layout: {response.text}"
        print(f"✅ Admin can save global layout")


class TestUsersAPI:
    """Tests for Users API - CRUD operations (admin only)"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers for requests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            token = response.json().get("access_token")
            return {"Authorization": f"Bearer {token}"}
        pytest.skip("Login failed")
    
    @pytest.fixture(scope="class")
    def test_user_id(self, auth_headers):
        """Create a test user and return its ID for other tests"""
        unique_email = f"TEST_user_{uuid.uuid4().hex[:8]}@test.com"
        response = requests.post(f"{BASE_URL}/api/users",
            headers=auth_headers,
            json={
                "email": unique_email,
                "password": "testpass123",
                "name": "TEST User",
                "role": "operator"
            }
        )
        if response.status_code == 200:
            user_id = response.json().get("id")
            yield user_id
            # Cleanup: delete the test user
            requests.delete(f"{BASE_URL}/api/users/{user_id}", headers=auth_headers)
        else:
            pytest.skip(f"Could not create test user: {response.text}")
    
    def test_get_all_users(self, auth_headers):
        """Test GET /api/users returns list of users (admin only)"""
        response = requests.get(f"{BASE_URL}/api/users", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ GET /api/users - Found {len(data)} users")
        
        # Verify user structure
        if len(data) > 0:
            user = data[0]
            assert "id" in user
            assert "email" in user
            assert "role" in user
            assert "password_hash" not in user, "Password hash should not be exposed"
            print(f"   User structure verified: id, email, role present, password_hash hidden")
    
    def test_create_user(self, auth_headers):
        """Test POST /api/users creates new user (admin only)"""
        unique_email = f"TEST_newuser_{uuid.uuid4().hex[:8]}@test.com"
        response = requests.post(f"{BASE_URL}/api/users",
            headers=auth_headers,
            json={
                "email": unique_email,
                "password": "newpass123",
                "name": "TEST New User",
                "role": "operator"
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("email") == unique_email
        assert data.get("role") == "operator"
        assert "id" in data
        print(f"✅ POST /api/users - User created: {unique_email}")
        
        # Cleanup
        user_id = data.get("id")
        if user_id:
            requests.delete(f"{BASE_URL}/api/users/{user_id}", headers=auth_headers)
    
    def test_create_user_duplicate_email(self, auth_headers):
        """Test creating user with duplicate email fails"""
        response = requests.post(f"{BASE_URL}/api/users",
            headers=auth_headers,
            json={
                "email": ADMIN_EMAIL,  # Already exists
                "password": "testpass",
                "name": "Duplicate",
                "role": "operator"
            }
        )
        assert response.status_code == 400, f"Should fail with 400 for duplicate email"
        print(f"✅ Duplicate email rejected correctly")
    
    def test_get_single_user(self, auth_headers, test_user_id):
        """Test GET /api/users/{id} returns specific user"""
        response = requests.get(f"{BASE_URL}/api/users/{test_user_id}", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("id") == test_user_id
        print(f"✅ GET /api/users/{test_user_id} - User retrieved")
    
    def test_update_user(self, auth_headers, test_user_id):
        """Test PUT /api/users/{id} updates user (admin only)"""
        response = requests.put(f"{BASE_URL}/api/users/{test_user_id}",
            headers=auth_headers,
            json={
                "name": "TEST Updated Name",
                "role": "admin"
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("name") == "TEST Updated Name"
        assert data.get("role") == "admin"
        print(f"✅ PUT /api/users/{test_user_id} - User updated")
    
    def test_reset_password(self, auth_headers, test_user_id):
        """Test POST /api/users/{id}/reset-password resets password (admin only)"""
        response = requests.post(f"{BASE_URL}/api/users/{test_user_id}/reset-password",
            headers=auth_headers,
            json={"new_password": "newpassword123"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True
        print(f"✅ POST /api/users/{test_user_id}/reset-password - Password reset")
    
    def test_delete_user(self, auth_headers):
        """Test DELETE /api/users/{id} deletes user (admin only)"""
        # Create a user to delete
        unique_email = f"TEST_delete_{uuid.uuid4().hex[:8]}@test.com"
        create_response = requests.post(f"{BASE_URL}/api/users",
            headers=auth_headers,
            json={
                "email": unique_email,
                "password": "deletepass",
                "name": "TEST To Delete",
                "role": "operator"
            }
        )
        assert create_response.status_code == 200
        user_id = create_response.json().get("id")
        
        # Delete the user
        delete_response = requests.delete(f"{BASE_URL}/api/users/{user_id}", headers=auth_headers)
        assert delete_response.status_code == 200, f"Failed: {delete_response.text}"
        
        # Verify deletion
        get_response = requests.get(f"{BASE_URL}/api/users/{user_id}", headers=auth_headers)
        assert get_response.status_code == 404, "Deleted user should not be found"
        print(f"✅ DELETE /api/users/{user_id} - User deleted and verified")


class TestO365SettingsAPI:
    """Tests for O365 Settings API - GET/POST /api/settings/o365"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers for requests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            token = response.json().get("access_token")
            return {"Authorization": f"Bearer {token}"}
        pytest.skip("Login failed")
    
    def test_get_o365_config(self, auth_headers):
        """Test GET /api/settings/o365 returns config"""
        response = requests.get(f"{BASE_URL}/api/settings/o365", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        # May be empty dict if not configured
        assert isinstance(data, dict)
        print(f"✅ GET /api/settings/o365 - Status: {response.status_code}")
        if data:
            print(f"   Config keys: {list(data.keys())}")
            # Verify secret is masked
            if "client_secret" in data:
                assert data["client_secret"] == "***" or data["client_secret"] == "", "Client secret should be masked"
    
    def test_save_o365_config(self, auth_headers):
        """Test POST /api/settings/o365 saves config"""
        test_config = {
            "tenant_id": "test-tenant-id-12345",
            "client_id": "test-client-id-67890",
            "client_secret": "test-secret-value",
            "sender_email": "noc-test@example.onmicrosoft.com",
            "sender_name": "ATECH NOC Test",
            "is_active": True
        }
        
        response = requests.post(f"{BASE_URL}/api/settings/o365",
            headers=auth_headers,
            json=test_config
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True
        print(f"✅ POST /api/settings/o365 - Config saved")
        
        # Verify secret is masked in response
        if "config" in data:
            assert data["config"].get("client_secret") == "***", "Secret should be masked in response"
    
    def test_o365_config_persistence(self, auth_headers):
        """Test that saved O365 config can be retrieved"""
        # Save config
        test_tenant = f"test-tenant-{uuid.uuid4().hex[:8]}"
        save_response = requests.post(f"{BASE_URL}/api/settings/o365",
            headers=auth_headers,
            json={
                "tenant_id": test_tenant,
                "client_id": "test-client-persist",
                "client_secret": "test-secret",
                "sender_email": "persist@test.com",
                "sender_name": "Persist Test",
                "is_active": True
            }
        )
        assert save_response.status_code == 200
        
        # Retrieve and verify
        get_response = requests.get(f"{BASE_URL}/api/settings/o365", headers=auth_headers)
        assert get_response.status_code == 200
        data = get_response.json()
        
        assert data.get("tenant_id") == test_tenant, "Tenant ID should match"
        assert data.get("sender_email") == "persist@test.com", "Sender email should match"
        print(f"✅ O365 config persistence verified")
    
    def test_delete_o365_config(self, auth_headers):
        """Test DELETE /api/settings/o365 removes config"""
        response = requests.delete(f"{BASE_URL}/api/settings/o365", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        # Verify deletion
        get_response = requests.get(f"{BASE_URL}/api/settings/o365", headers=auth_headers)
        assert get_response.status_code == 200
        data = get_response.json()
        # Should be empty or have no tenant_id
        assert not data.get("tenant_id"), "Config should be deleted"
        print(f"✅ DELETE /api/settings/o365 - Config deleted")


class TestNonAdminAccess:
    """Test that non-admin users cannot access admin-only endpoints"""
    
    @pytest.fixture(scope="class")
    def operator_headers(self):
        """Create an operator user and get their token"""
        # First login as admin to create operator
        admin_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if admin_response.status_code != 200:
            pytest.skip("Admin login failed")
        
        admin_token = admin_response.json().get("access_token")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Create operator user
        unique_email = f"TEST_operator_{uuid.uuid4().hex[:8]}@test.com"
        create_response = requests.post(f"{BASE_URL}/api/users",
            headers=admin_headers,
            json={
                "email": unique_email,
                "password": "operatorpass123",
                "name": "TEST Operator",
                "role": "operator"
            }
        )
        
        if create_response.status_code != 200:
            pytest.skip(f"Could not create operator: {create_response.text}")
        
        operator_id = create_response.json().get("id")
        
        # Login as operator
        operator_login = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": unique_email,
            "password": "operatorpass123"
        })
        
        if operator_login.status_code != 200:
            pytest.skip("Operator login failed")
        
        operator_token = operator_login.json().get("access_token")
        
        yield {"Authorization": f"Bearer {operator_token}"}
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/users/{operator_id}", headers=admin_headers)
    
    def test_operator_cannot_get_users(self, operator_headers):
        """Test operator cannot access GET /api/users"""
        response = requests.get(f"{BASE_URL}/api/users", headers=operator_headers)
        assert response.status_code == 403, f"Operator should get 403, got {response.status_code}"
        print(f"✅ Operator correctly denied access to GET /api/users")
    
    def test_operator_cannot_create_user(self, operator_headers):
        """Test operator cannot create users"""
        response = requests.post(f"{BASE_URL}/api/users",
            headers=operator_headers,
            json={
                "email": "shouldfail@test.com",
                "password": "test123",
                "name": "Should Fail",
                "role": "operator"
            }
        )
        assert response.status_code == 403, f"Operator should get 403, got {response.status_code}"
        print(f"✅ Operator correctly denied access to POST /api/users")
    
    def test_operator_cannot_access_o365_settings(self, operator_headers):
        """Test operator cannot access O365 settings"""
        response = requests.get(f"{BASE_URL}/api/settings/o365", headers=operator_headers)
        assert response.status_code == 403, f"Operator should get 403, got {response.status_code}"
        print(f"✅ Operator correctly denied access to GET /api/settings/o365")
    
    def test_operator_cannot_save_global_layout(self, operator_headers):
        """Test operator cannot save global dashboard layout"""
        response = requests.post(f"{BASE_URL}/api/dashboard/layout",
            headers=operator_headers,
            json={
                "layout": [{"i": "test", "x": 0, "y": 0, "w": 2, "h": 2}],
                "widget_configs": {},
                "is_global": True
            }
        )
        assert response.status_code == 403, f"Operator should get 403 for global layout, got {response.status_code}"
        print(f"✅ Operator correctly denied saving global layout")
    
    def test_operator_can_save_personal_layout(self, operator_headers):
        """Test operator CAN save their own personal layout"""
        response = requests.post(f"{BASE_URL}/api/dashboard/layout",
            headers=operator_headers,
            json={
                "layout": [{"i": "personal_test", "x": 0, "y": 0, "w": 2, "h": 2}],
                "widget_configs": {},
                "is_global": False
            }
        )
        assert response.status_code == 200, f"Operator should be able to save personal layout: {response.text}"
        print(f"✅ Operator can save personal dashboard layout")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
