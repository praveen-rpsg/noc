"""
Test Network Diagnostics Feature
- POST /api/agent-exec/diagnostics/ping - Run ping diagnostic
- POST /api/agent-exec/diagnostics/traceroute - Run traceroute diagnostic
- GET /api/agent-exec/diagnostics/history - Get diagnostics history
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestNetworkDiagnostics:
    """Network Diagnostics endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get auth token"""
        # Login to get token
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@noc.com",
            "password": "admin123"
        })
        
        if login_response.status_code != 200:
            pytest.skip("Authentication failed - skipping tests")
        
        self.token = login_response.json().get("access_token")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    # ==================== PING TESTS ====================
    
    def test_ping_basic_target(self):
        """Test ping with basic IP target"""
        response = requests.post(
            f"{BASE_URL}/api/agent-exec/diagnostics/ping",
            json={"target": "8.8.8.8", "count": 4},
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify required fields in response
        assert "target" in data, "Response should contain 'target'"
        assert data["target"] == "8.8.8.8", "Target should match request"
        assert "packets_sent" in data, "Response should contain 'packets_sent'"
        assert "packets_received" in data, "Response should contain 'packets_received'"
        assert "packet_loss_percent" in data, "Response should contain 'packet_loss_percent'"
        assert "avg_latency_ms" in data, "Response should contain 'avg_latency_ms'"
        assert "min_latency_ms" in data, "Response should contain 'min_latency_ms'"
        assert "max_latency_ms" in data, "Response should contain 'max_latency_ms'"
        assert "ping_results" in data, "Response should contain 'ping_results'"
        assert "status" in data, "Response should contain 'status'"
        
        # Verify ping_results structure
        assert isinstance(data["ping_results"], list), "ping_results should be a list"
        assert len(data["ping_results"]) == 4, "Should have 4 ping results"
        
        for ping in data["ping_results"]:
            assert "seq" in ping, "Each ping should have 'seq'"
            assert "success" in ping, "Each ping should have 'success'"
            assert "timestamp" in ping, "Each ping should have 'timestamp'"
            if ping["success"]:
                assert "latency_ms" in ping, "Successful ping should have 'latency_ms'"
        
        print(f"✅ Ping test passed - Target: {data['target']}, Status: {data['status']}, Packet Loss: {data['packet_loss_percent']}%")
    
    def test_ping_with_hostname(self):
        """Test ping with hostname target"""
        response = requests.post(
            f"{BASE_URL}/api/agent-exec/diagnostics/ping",
            json={"target": "google.com", "count": 3},
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["target"] == "google.com"
        assert len(data["ping_results"]) == 3
        
        print(f"✅ Ping with hostname passed - Target: {data['target']}")
    
    def test_ping_with_device_id(self):
        """Test ping with device_id parameter"""
        # First get a device
        devices_response = requests.get(f"{BASE_URL}/api/devices", headers=self.headers)
        
        if devices_response.status_code == 200 and devices_response.json():
            device = devices_response.json()[0]
            device_id = device.get("id")
            
            response = requests.post(
                f"{BASE_URL}/api/agent-exec/diagnostics/ping",
                json={"target": "8.8.8.8", "count": 2, "device_id": device_id},
                headers=self.headers
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Should include device info if device exists
            if device.get("name"):
                assert "device_name" in data
            
            print(f"✅ Ping with device_id passed - Device: {data.get('device_name', 'N/A')}")
        else:
            print("⚠️ No devices found - skipping device_id test")
    
    def test_ping_max_count_limit(self):
        """Test that ping count is limited to max 10"""
        response = requests.post(
            f"{BASE_URL}/api/agent-exec/diagnostics/ping",
            json={"target": "8.8.8.8", "count": 20},  # Request 20, should be limited to 10
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should be limited to 10
        assert len(data["ping_results"]) <= 10, "Ping count should be limited to max 10"
        
        print(f"✅ Ping max count limit test passed - Got {len(data['ping_results'])} results")
    
    def test_ping_status_values(self):
        """Test that ping status is either 'reachable' or 'unreachable'"""
        response = requests.post(
            f"{BASE_URL}/api/agent-exec/diagnostics/ping",
            json={"target": "8.8.8.8", "count": 4},
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] in ["reachable", "unreachable"], f"Status should be 'reachable' or 'unreachable', got {data['status']}"
        
        print(f"✅ Ping status validation passed - Status: {data['status']}")
    
    # ==================== TRACEROUTE TESTS ====================
    
    def test_traceroute_basic_target(self):
        """Test traceroute with basic IP target"""
        response = requests.post(
            f"{BASE_URL}/api/agent-exec/diagnostics/traceroute",
            json={"target": "8.8.8.8", "max_hops": 15},
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify required fields
        assert "target" in data, "Response should contain 'target'"
        assert data["target"] == "8.8.8.8", "Target should match request"
        assert "hops" in data, "Response should contain 'hops'"
        assert "total_hops" in data, "Response should contain 'total_hops'"
        assert "total_latency_ms" in data, "Response should contain 'total_latency_ms'"
        assert "destination_reached" in data, "Response should contain 'destination_reached'"
        assert "path_quality" in data, "Response should contain 'path_quality'"
        
        # Verify hops structure
        assert isinstance(data["hops"], list), "hops should be a list"
        assert len(data["hops"]) > 0, "Should have at least one hop"
        
        for hop in data["hops"]:
            assert "hop" in hop, "Each hop should have 'hop' number"
            assert "status" in hop, "Each hop should have 'status'"
            if hop["status"] != "timeout":
                assert "hostname" in hop or "ip" in hop, "Non-timeout hop should have hostname or IP"
                assert "avg_latency" in hop, "Non-timeout hop should have 'avg_latency'"
        
        print(f"✅ Traceroute test passed - Target: {data['target']}, Total Hops: {data['total_hops']}, Path Quality: {data['path_quality']}")
    
    def test_traceroute_hop_details(self):
        """Test traceroute hop details include required fields"""
        response = requests.post(
            f"{BASE_URL}/api/agent-exec/diagnostics/traceroute",
            json={"target": "8.8.8.8"},
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check first hop details
        if data["hops"]:
            first_hop = data["hops"][0]
            assert "hop" in first_hop, "Hop should have number"
            assert first_hop["hop"] == 1, "First hop should be number 1"
            
            # Check for type field (gateway, router, etc.)
            if first_hop.get("status") != "timeout":
                assert "type" in first_hop, "Hop should have 'type' field"
        
        # Check last hop (destination)
        last_hop = data["hops"][-1]
        if data["destination_reached"]:
            assert last_hop.get("is_destination") == True, "Last hop should be marked as destination"
        
        print(f"✅ Traceroute hop details test passed - {len(data['hops'])} hops analyzed")
    
    def test_traceroute_path_quality_values(self):
        """Test that path_quality is one of expected values"""
        response = requests.post(
            f"{BASE_URL}/api/agent-exec/diagnostics/traceroute",
            json={"target": "8.8.8.8"},
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        valid_qualities = ["good", "degraded", "poor"]
        assert data["path_quality"] in valid_qualities, f"Path quality should be one of {valid_qualities}, got {data['path_quality']}"
        
        print(f"✅ Path quality validation passed - Quality: {data['path_quality']}")
    
    def test_traceroute_issues_detected(self):
        """Test that traceroute can detect and report issues"""
        response = requests.post(
            f"{BASE_URL}/api/agent-exec/diagnostics/traceroute",
            json={"target": "8.8.8.8"},
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # issues_detected should be a list (may be empty)
        assert "issues_detected" in data, "Response should contain 'issues_detected'"
        assert isinstance(data["issues_detected"], list), "issues_detected should be a list"
        
        print(f"✅ Issues detection test passed - {len(data['issues_detected'])} issues detected")
    
    def test_traceroute_max_hops_limit(self):
        """Test that max_hops is limited to 30"""
        response = requests.post(
            f"{BASE_URL}/api/agent-exec/diagnostics/traceroute",
            json={"target": "8.8.8.8", "max_hops": 50},  # Request 50, should be limited
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should be limited to 30 max
        assert data["total_hops"] <= 30, "Total hops should be limited to max 30"
        
        print(f"✅ Traceroute max hops limit test passed - Got {data['total_hops']} hops")
    
    def test_traceroute_latency_fields(self):
        """Test that traceroute includes individual latency measurements"""
        response = requests.post(
            f"{BASE_URL}/api/agent-exec/diagnostics/traceroute",
            json={"target": "8.8.8.8"},
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check for latency fields in hops
        for hop in data["hops"]:
            if hop.get("status") != "timeout":
                # Should have individual latency measurements
                assert "latency_1" in hop or "avg_latency" in hop, "Hop should have latency data"
        
        print(f"✅ Traceroute latency fields test passed")
    
    # ==================== HISTORY TESTS ====================
    
    def test_diagnostics_history_endpoint(self):
        """Test GET /api/agent-exec/diagnostics/history"""
        # First run a ping to ensure there's history
        requests.post(
            f"{BASE_URL}/api/agent-exec/diagnostics/ping",
            json={"target": "1.1.1.1", "count": 2},
            headers=self.headers
        )
        
        # Now get history
        response = requests.get(
            f"{BASE_URL}/api/agent-exec/diagnostics/history",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "History should be a list"
        
        if data:
            record = data[0]
            assert "id" in record, "Record should have 'id'"
            assert "type" in record, "Record should have 'type'"
            assert "target" in record, "Record should have 'target'"
            assert "created_at" in record, "Record should have 'created_at'"
        
        print(f"✅ Diagnostics history test passed - {len(data)} records found")
    
    def test_diagnostics_history_filter_by_type(self):
        """Test filtering history by diagnostic type"""
        # Run both ping and traceroute
        requests.post(
            f"{BASE_URL}/api/agent-exec/diagnostics/ping",
            json={"target": "8.8.8.8", "count": 2},
            headers=self.headers
        )
        requests.post(
            f"{BASE_URL}/api/agent-exec/diagnostics/traceroute",
            json={"target": "8.8.8.8"},
            headers=self.headers
        )
        
        # Filter by ping
        response = requests.get(
            f"{BASE_URL}/api/agent-exec/diagnostics/history?diagnostic_type=ping",
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        for record in data:
            assert record["type"] == "ping", "All records should be ping type"
        
        print(f"✅ History filter by type test passed - {len(data)} ping records")
    
    def test_diagnostics_history_limit(self):
        """Test history limit parameter"""
        response = requests.get(
            f"{BASE_URL}/api/agent-exec/diagnostics/history?limit=5",
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) <= 5, "Should return at most 5 records"
        
        print(f"✅ History limit test passed - Got {len(data)} records (limit 5)")
    
    # ==================== AUTHENTICATION TESTS ====================
    
    def test_ping_requires_auth(self):
        """Test that ping endpoint requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/agent-exec/diagnostics/ping",
            json={"target": "8.8.8.8"}
            # No auth header
        )
        
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        
        print("✅ Ping auth requirement test passed")
    
    def test_traceroute_requires_auth(self):
        """Test that traceroute endpoint requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/agent-exec/diagnostics/traceroute",
            json={"target": "8.8.8.8"}
            # No auth header
        )
        
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        
        print("✅ Traceroute auth requirement test passed")
    
    def test_history_requires_auth(self):
        """Test that history endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/agent-exec/diagnostics/history")
        
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        
        print("✅ History auth requirement test passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
