"""
Test suite for new features:
1. Voice Alert Settings (frontend only - uses Web Speech API)
2. Routing AI tab with POST /api/agent-exec/routing/optimize
3. Show Path on Network Topology button
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://network-ops-ai.preview.emergentagent.com').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@noc.com"
TEST_PASSWORD = "admin123"


class TestAuthentication:
    """Test authentication for API access"""
    
    def test_login_success(self):
        """Test successful login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        assert "user" in data, "No user in response"
        print(f"✅ Login successful for {TEST_EMAIL}")
        return data["access_token"]


class TestRoutingOptimization:
    """Test Routing AI optimization endpoint"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    @pytest.fixture
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_routing_optimize_requires_auth(self):
        """Test that routing optimization requires authentication"""
        response = requests.post(f"{BASE_URL}/api/agent-exec/routing/optimize")
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print("✅ Routing optimization requires authentication (403)")
    
    def test_routing_optimize_returns_data(self, auth_headers):
        """Test that routing optimization returns proper data structure"""
        response = requests.post(
            f"{BASE_URL}/api/agent-exec/routing/optimize",
            headers=auth_headers,
            timeout=60  # AI analysis may take time
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Check required fields
        assert "id" in data, "Missing 'id' field"
        assert "network_summary" in data, "Missing 'network_summary' field"
        assert "optimization" in data, "Missing 'optimization' field"
        assert "generated_at" in data, "Missing 'generated_at' field"
        
        # Check network_summary structure
        summary = data["network_summary"]
        assert "total_devices" in summary, "Missing 'total_devices' in network_summary"
        assert "routers" in summary, "Missing 'routers' in network_summary"
        assert "switches" in summary, "Missing 'switches' in network_summary"
        assert "locations" in summary, "Missing 'locations' in network_summary"
        
        print(f"✅ Routing optimization returned valid data")
        print(f"   - Total devices: {summary.get('total_devices', 0)}")
        print(f"   - Routers: {summary.get('routers', 0)}")
        print(f"   - Switches: {summary.get('switches', 0)}")
        
        # Check optimization data
        optimization = data["optimization"]
        if "recommended_protocol" in optimization:
            print(f"   - Recommended protocol: {optimization['recommended_protocol'].get('primary', 'N/A')}")
        elif "raw_analysis" in optimization:
            print(f"   - Raw analysis received (AI response)")
        
        return data
    
    def test_routing_history_endpoint(self, auth_headers):
        """Test routing optimization history endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/agent-exec/routing/history",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list response"
        print(f"✅ Routing history returned {len(data)} records")


class TestNetworkDiagnostics:
    """Test Network Diagnostics endpoints (ping, traceroute)"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    @pytest.fixture
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_ping_endpoint(self, auth_headers):
        """Test ping diagnostic endpoint"""
        response = requests.post(
            f"{BASE_URL}/api/agent-exec/diagnostics/ping",
            headers=auth_headers,
            json={"target": "8.8.8.8", "count": 4}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "target" in data, "Missing 'target' field"
        assert "packets_sent" in data, "Missing 'packets_sent' field"
        assert "packets_received" in data, "Missing 'packets_received' field"
        assert "status" in data, "Missing 'status' field"
        assert "ping_results" in data, "Missing 'ping_results' field"
        
        print(f"✅ Ping diagnostic returned valid data")
        print(f"   - Target: {data['target']}")
        print(f"   - Status: {data['status']}")
        print(f"   - Packets: {data['packets_received']}/{data['packets_sent']}")
    
    def test_traceroute_endpoint(self, auth_headers):
        """Test traceroute diagnostic endpoint"""
        response = requests.post(
            f"{BASE_URL}/api/agent-exec/diagnostics/traceroute",
            headers=auth_headers,
            json={"target": "8.8.8.8", "max_hops": 15}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "target" in data, "Missing 'target' field"
        assert "hops" in data, "Missing 'hops' field"
        assert "total_hops" in data, "Missing 'total_hops' field"
        assert "path_quality" in data, "Missing 'path_quality' field"
        
        print(f"✅ Traceroute diagnostic returned valid data")
        print(f"   - Target: {data['target']}")
        print(f"   - Total hops: {data['total_hops']}")
        print(f"   - Path quality: {data['path_quality']}")
        
        # Check hops structure
        if data['hops']:
            hop = data['hops'][0]
            assert "hop" in hop, "Missing 'hop' number in hop data"
            assert "ip" in hop or "hostname" in hop, "Missing IP or hostname in hop data"


class TestTopologyEndpoint:
    """Test Topology data endpoint"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    @pytest.fixture
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_topology_data_endpoint(self, auth_headers):
        """Test topology data endpoint returns nodes and links"""
        response = requests.get(
            f"{BASE_URL}/api/topology/data",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "nodes" in data, "Missing 'nodes' field"
        assert "links" in data, "Missing 'links' field"
        
        print(f"✅ Topology data returned valid structure")
        print(f"   - Nodes: {len(data['nodes'])}")
        print(f"   - Links: {len(data['links'])}")
        
        # Check node structure if nodes exist
        if data['nodes']:
            node = data['nodes'][0]
            assert "id" in node, "Missing 'id' in node"
            assert "name" in node, "Missing 'name' in node"
            assert "type" in node, "Missing 'type' in node"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
