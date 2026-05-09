"""
Backend API Tests for Settings and Reports Endpoints
Tests for: Email, SNMP, OpenStack, Oracle, vCenter, AAA, Backup configurations
and Reports generation/download functionality
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://network-ops-ai.preview.emergentagent.com').rstrip('/')

# Test credentials from environment variables (secure)
TEST_EMAIL = os.environ.get('TEST_USER_EMAIL', 'admin@noc.com')
TEST_PASSWORD = os.environ.get('TEST_USER_PASSWORD', 'admin123')

class TestAuth:
    """Authentication tests to get token for subsequent tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        return data["access_token"]
    
    def test_login_success(self):
        """Test login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        print(f"✅ Login successful for {TEST_EMAIL}")


class TestEmailSettings:
    """Email (O365) configuration tests"""
    
    @pytest.fixture(scope="class")
    def auth_header(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_email_config(self, auth_header):
        """Test GET email configuration"""
        response = requests.get(f"{BASE_URL}/api/settings/email", headers=auth_header)
        assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}"
        print(f"✅ GET /api/settings/email - Status: {response.status_code}")
    
    def test_save_email_config(self, auth_header):
        """Test POST email configuration"""
        email_config = {
            "smtp_server": "smtp.office365.com",
            "smtp_port": 587,
            "username": "test@company.com",
            "password": "test_password",
            "sender_email": "noc-alerts@company.com",
            "sender_name": "ATECH NOC Commander",
            "use_tls": True
        }
        response = requests.post(f"{BASE_URL}/api/settings/email", json=email_config, headers=auth_header)
        assert response.status_code in [200, 201], f"Failed to save email config: {response.text}"
        print(f"✅ POST /api/settings/email - Status: {response.status_code}")


class TestSNMPSettings:
    """SNMP Community and v3 configuration tests"""
    
    @pytest.fixture(scope="class")
    def auth_header(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_snmp_community_configs(self, auth_header):
        """Test GET SNMP community strings"""
        response = requests.get(f"{BASE_URL}/api/settings/snmp/community", headers=auth_header)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ GET /api/settings/snmp/community - Found {len(data)} configs")
    
    def test_create_snmp_community_config(self, auth_header):
        """Test POST SNMP community string"""
        config = {
            "name": f"TEST_SNMP_Community_{uuid.uuid4().hex[:6]}",
            "community_string": "public_test",
            "version": "v2c",
            "ip_range": "192.168.1.0/24",
            "location": "Test DC"
        }
        response = requests.post(f"{BASE_URL}/api/settings/snmp/community", json=config, headers=auth_header)
        assert response.status_code in [200, 201], f"Failed: {response.text}"
        data = response.json()
        # API returns config inside nested object
        config_data = data.get("config", data)
        assert "id" in config_data
        print(f"✅ POST /api/settings/snmp/community - Created config ID: {config_data['id']}")
    
    def test_get_snmp_v3_configs(self, auth_header):
        """Test GET SNMP v3 configurations"""
        response = requests.get(f"{BASE_URL}/api/settings/snmp/v3", headers=auth_header)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ GET /api/settings/snmp/v3 - Found {len(data)} configs")


class TestOpenStackSettings:
    """OpenStack configuration tests"""
    
    @pytest.fixture(scope="class")
    def auth_header(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_openstack_configs(self, auth_header):
        """Test GET OpenStack configurations"""
        response = requests.get(f"{BASE_URL}/api/settings/openstack", headers=auth_header)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ GET /api/settings/openstack - Found {len(data)} configs")
    
    def test_create_openstack_config(self, auth_header):
        """Test POST OpenStack configuration with service toggles"""
        config = {
            "name": f"TEST_OpenStack_{uuid.uuid4().hex[:6]}",
            "auth_url": "http://openstack.test.com:5000/v3",
            "username": "admin",
            "password": "test_password",
            "project_name": "test_project",
            "user_domain_name": "Default",
            "project_domain_name": "Default",
            "region_name": "RegionOne",
            "monitor_nova": True,
            "monitor_neutron": True,
            "monitor_cinder": True,
            "monitor_keystone": True,
            "monitor_glance": True,
            "monitor_heat": False,
            "monitor_swift": False
        }
        response = requests.post(f"{BASE_URL}/api/settings/openstack", json=config, headers=auth_header)
        assert response.status_code in [200, 201], f"Failed: {response.text}"
        data = response.json()
        config_data = data.get("config", data)
        assert "id" in config_data
        assert config_data["monitor_nova"] == True
        assert config_data["monitor_heat"] == False
        print(f"✅ POST /api/settings/openstack - Created config with service toggles")


class TestOracleSettings:
    """Oracle DB configuration tests"""
    
    @pytest.fixture(scope="class")
    def auth_header(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_oracle_configs(self, auth_header):
        """Test GET Oracle configurations"""
        response = requests.get(f"{BASE_URL}/api/settings/oracle", headers=auth_header)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ GET /api/settings/oracle - Found {len(data)} configs")
    
    def test_create_oracle_config(self, auth_header):
        """Test POST Oracle configuration with metric toggles"""
        config = {
            "name": f"TEST_Oracle_{uuid.uuid4().hex[:6]}",
            "host": "oracle.test.com",
            "port": 1521,
            "service_name": "ORCL",
            "username": "sys",
            "password": "test_password",
            "monitor_tablespace": True,
            "monitor_sessions": True,
            "monitor_locks": True,
            "monitor_performance": True,
            "monitor_asm": False,
            "monitor_dataguard": False,
            "monitor_rman": True,
            "alert_threshold_tablespace": 80,
            "alert_threshold_sessions": 90
        }
        response = requests.post(f"{BASE_URL}/api/settings/oracle", json=config, headers=auth_header)
        assert response.status_code in [200, 201], f"Failed: {response.text}"
        data = response.json()
        config_data = data.get("config", data)
        assert "id" in config_data
        assert config_data["monitor_tablespace"] == True
        assert config_data["monitor_asm"] == False
        print(f"✅ POST /api/settings/oracle - Created config with metric toggles")


class TestVCenterSettings:
    """vCenter configuration tests"""
    
    @pytest.fixture(scope="class")
    def auth_header(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_vcenter_configs(self, auth_header):
        """Test GET vCenter configurations"""
        response = requests.get(f"{BASE_URL}/api/settings/vcenter", headers=auth_header)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ GET /api/settings/vcenter - Found {len(data)} configs")
    
    def test_create_vcenter_config(self, auth_header):
        """Test POST vCenter configuration"""
        config = {
            "name": f"TEST_vCenter_{uuid.uuid4().hex[:6]}",
            "host": "vcenter.test.com",
            "port": 443,
            "username": "administrator@vsphere.local",
            "password": "test_password",
            "monitor_vms": True,
            "monitor_esxi_hosts": True,
            "monitor_datastores": True,
            "monitor_clusters": True,
            "monitor_networks": False,
            "monitor_resource_pools": False,
            "alert_threshold_cpu": 80,
            "alert_threshold_memory": 85,
            "alert_threshold_datastore": 80
        }
        response = requests.post(f"{BASE_URL}/api/settings/vcenter", json=config, headers=auth_header)
        assert response.status_code in [200, 201], f"Failed: {response.text}"
        data = response.json()
        config_data = data.get("config", data)
        assert "id" in config_data
        assert config_data["monitor_vms"] == True
        print(f"✅ POST /api/settings/vcenter - Created config")


class TestAAASettings:
    """AAA Server (RADIUS/TACACS+) configuration tests"""
    
    @pytest.fixture(scope="class")
    def auth_header(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_aaa_configs(self, auth_header):
        """Test GET AAA configurations"""
        response = requests.get(f"{BASE_URL}/api/settings/aaa", headers=auth_header)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ GET /api/settings/aaa - Found {len(data)} configs")
    
    def test_create_radius_config(self, auth_header):
        """Test POST RADIUS configuration"""
        config = {
            "name": f"TEST_RADIUS_{uuid.uuid4().hex[:6]}",
            "server_type": "radius",
            "primary_host": "radius.test.com",
            "primary_port": 1812,
            "secondary_host": "radius-backup.test.com",
            "secondary_port": 1812,
            "shared_secret": "test_secret",
            "timeout": 5,
            "retries": 3,
            "use_for_login": True,
            "use_for_device_auth": True
        }
        response = requests.post(f"{BASE_URL}/api/settings/aaa", json=config, headers=auth_header)
        assert response.status_code in [200, 201], f"Failed: {response.text}"
        data = response.json()
        config_data = data.get("config", data)
        assert "id" in config_data
        assert config_data["server_type"] == "radius"
        print(f"✅ POST /api/settings/aaa - Created RADIUS config")
    
    def test_create_tacacs_config(self, auth_header):
        """Test POST TACACS+ configuration"""
        config = {
            "name": f"TEST_TACACS_{uuid.uuid4().hex[:6]}",
            "server_type": "tacacs",
            "primary_host": "tacacs.test.com",
            "primary_port": 49,
            "shared_secret": "test_secret",
            "timeout": 5,
            "retries": 3,
            "use_for_login": True,
            "use_for_device_auth": True
        }
        response = requests.post(f"{BASE_URL}/api/settings/aaa", json=config, headers=auth_header)
        assert response.status_code in [200, 201], f"Failed: {response.text}"
        data = response.json()
        config_data = data.get("config", data)
        assert "id" in config_data
        assert config_data["server_type"] == "tacacs"
        print(f"✅ POST /api/settings/aaa - Created TACACS+ config")


class TestBackupSettings:
    """Backup configuration tests"""
    
    @pytest.fixture(scope="class")
    def auth_header(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_backup_configs(self, auth_header):
        """Test GET Backup configurations"""
        response = requests.get(f"{BASE_URL}/api/settings/backup", headers=auth_header)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ GET /api/settings/backup - Found {len(data)} configs")
    
    def test_create_scp_backup_config(self, auth_header):
        """Test POST SCP backup configuration with schedule"""
        config = {
            "name": f"TEST_SCP_Backup_{uuid.uuid4().hex[:6]}",
            "backup_type": "scp",
            "server_host": "backup.test.com",
            "server_port": 22,
            "server_username": "backup_user",
            "server_password": "test_password",
            "server_path": "/backups/network",
            "schedule_enabled": True,
            "schedule_frequency": "daily",
            "schedule_time": "02:00",
            "retention_days": 30,
            "target_type": "device"
        }
        response = requests.post(f"{BASE_URL}/api/settings/backup", json=config, headers=auth_header)
        assert response.status_code in [200, 201], f"Failed: {response.text}"
        data = response.json()
        config_data = data.get("config", data)
        assert "id" in config_data
        assert config_data["backup_type"] == "scp"
        assert config_data["schedule_enabled"] == True
        print(f"✅ POST /api/settings/backup - Created SCP backup config with schedule")
    
    def test_create_tftp_backup_config(self, auth_header):
        """Test POST TFTP backup configuration"""
        config = {
            "name": f"TEST_TFTP_Backup_{uuid.uuid4().hex[:6]}",
            "backup_type": "tftp",
            "server_host": "tftp.test.com",
            "server_path": "/tftpboot/configs",
            "schedule_enabled": False,
            "retention_days": 14
        }
        response = requests.post(f"{BASE_URL}/api/settings/backup", json=config, headers=auth_header)
        assert response.status_code in [200, 201], f"Failed: {response.text}"
        data = response.json()
        config_data = data.get("config", data)
        assert "id" in config_data
        assert config_data["backup_type"] == "tftp"
        print(f"✅ POST /api/settings/backup - Created TFTP backup config")
    
    def test_create_api_backup_config(self, auth_header):
        """Test POST API-based backup configuration"""
        config = {
            "name": f"TEST_API_Backup_{uuid.uuid4().hex[:6]}",
            "backup_type": "api",
            "api_endpoint": "https://api.backup.test.com/v1/backup",
            "api_key": "test_api_key",
            "api_method": "POST",
            "schedule_enabled": True,
            "schedule_frequency": "weekly",
            "schedule_time": "03:00",
            "retention_days": 60
        }
        response = requests.post(f"{BASE_URL}/api/settings/backup", json=config, headers=auth_header)
        assert response.status_code in [200, 201], f"Failed: {response.text}"
        data = response.json()
        config_data = data.get("config", data)
        assert "id" in config_data
        assert config_data["backup_type"] == "api"
        print(f"✅ POST /api/settings/backup - Created API backup config")


class TestReports:
    """Reports generation and download tests"""
    
    @pytest.fixture(scope="class")
    def auth_header(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_reports(self, auth_header):
        """Test GET all reports"""
        response = requests.get(f"{BASE_URL}/api/reports", headers=auth_header)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ GET /api/reports - Found {len(data)} reports")
    
    def test_generate_daily_health_report(self, auth_header):
        """Test generate daily health report"""
        response = requests.post(
            f"{BASE_URL}/api/reports/generate",
            params={
                "report_type": "daily_health",
                "period_start": "2026-01-01",
                "period_end": "2026-01-07"
            },
            headers=auth_header
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "id" in data
        assert data["type"] == "daily_health"
        assert "content" in data
        print(f"✅ POST /api/reports/generate (daily_health) - Report ID: {data['id']}")
        return data["id"]
    
    def test_generate_incident_summary_report(self, auth_header):
        """Test generate incident summary report"""
        response = requests.post(
            f"{BASE_URL}/api/reports/generate",
            params={
                "report_type": "incident_summary",
                "period_start": "2026-01-01",
                "period_end": "2026-01-07"
            },
            headers=auth_header
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "id" in data
        assert data["type"] == "incident_summary"
        print(f"✅ POST /api/reports/generate (incident_summary) - Report ID: {data['id']}")
        return data["id"]
    
    def test_generate_sla_compliance_report(self, auth_header):
        """Test generate SLA compliance report"""
        response = requests.post(
            f"{BASE_URL}/api/reports/generate",
            params={
                "report_type": "sla_compliance",
                "period_start": "2026-01-01",
                "period_end": "2026-01-07"
            },
            headers=auth_header
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "id" in data
        assert data["type"] == "sla_compliance"
        print(f"✅ POST /api/reports/generate (sla_compliance) - Report ID: {data['id']}")
        return data["id"]
    
    def test_download_report_pdf(self, auth_header):
        """Test download report as PDF"""
        # First generate a report
        gen_response = requests.post(
            f"{BASE_URL}/api/reports/generate",
            params={
                "report_type": "daily_health",
                "period_start": "2026-01-01",
                "period_end": "2026-01-07"
            },
            headers=auth_header
        )
        report_id = gen_response.json()["id"]
        
        # Download as PDF
        response = requests.get(f"{BASE_URL}/api/reports/{report_id}/download/pdf", headers=auth_header)
        assert response.status_code == 200, f"Failed: {response.text}"
        assert "application/pdf" in response.headers.get("content-type", "")
        assert len(response.content) > 0
        print(f"✅ GET /api/reports/{report_id}/download/pdf - PDF size: {len(response.content)} bytes")
    
    def test_download_report_csv(self, auth_header):
        """Test download report as CSV"""
        # First generate a report
        gen_response = requests.post(
            f"{BASE_URL}/api/reports/generate",
            params={
                "report_type": "incident_summary",
                "period_start": "2026-01-01",
                "period_end": "2026-01-07"
            },
            headers=auth_header
        )
        report_id = gen_response.json()["id"]
        
        # Download as CSV
        response = requests.get(f"{BASE_URL}/api/reports/{report_id}/download/csv", headers=auth_header)
        assert response.status_code == 200, f"Failed: {response.text}"
        assert "text/csv" in response.headers.get("content-type", "")
        assert len(response.content) > 0
        print(f"✅ GET /api/reports/{report_id}/download/csv - CSV size: {len(response.content)} bytes")


class TestCleanup:
    """Cleanup test data"""
    
    @pytest.fixture(scope="class")
    def auth_header(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_cleanup_test_configs(self, auth_header):
        """Clean up TEST_ prefixed configurations"""
        endpoints = [
            "snmp/community",
            "snmp/v3",
            "openstack",
            "oracle",
            "vcenter",
            "aaa",
            "backup"
        ]
        
        deleted_count = 0
        for endpoint in endpoints:
            response = requests.get(f"{BASE_URL}/api/settings/{endpoint}", headers=auth_header)
            if response.status_code == 200:
                configs = response.json()
                for config in configs:
                    if config.get("name", "").startswith("TEST_"):
                        del_response = requests.delete(
                            f"{BASE_URL}/api/settings/{endpoint}/{config['id']}", 
                            headers=auth_header
                        )
                        if del_response.status_code in [200, 204]:
                            deleted_count += 1
        
        print(f"✅ Cleanup complete - Deleted {deleted_count} test configurations")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
