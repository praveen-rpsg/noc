"""
Test suite for Autonomous AI Agent features
Tests:
- POST /api/agent-exec/run/{incident_id} - Run agent on incident
- GET /api/agent-exec/pending-actions - Get pending confirmations
- GET /api/agent-exec/pending-actions/count - Get pending count
- POST /api/agent-exec/actions/{id}/approve - Approve action
- POST /api/agent-exec/actions/{id}/reject - Reject action
- GET /api/agent-exec/settings - Get agent settings
- PUT /api/agent-exec/settings - Update agent settings
- GET /api/agent-exec/executions - Get all executions
"""

import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAutonomousAgent:
    """Test suite for Autonomous AI Agent endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get auth token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@noc.com",
            "password": "admin123"
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            self.user = login_response.json().get("user")
        else:
            pytest.skip("Authentication failed - skipping tests")
        
        yield
        
        # Cleanup - delete test incidents
        self.cleanup_test_data()
    
    def cleanup_test_data(self):
        """Clean up test-created data"""
        try:
            # Get all incidents and delete test ones
            incidents = self.session.get(f"{BASE_URL}/api/incidents").json()
            for incident in incidents:
                if incident.get('title', '').startswith('TEST_'):
                    self.session.delete(f"{BASE_URL}/api/incidents/{incident['id']}")
        except:
            pass
    
    def create_test_incident(self, title_suffix=""):
        """Helper to create a test incident"""
        incident_data = {
            "title": f"TEST_Agent_Incident_{title_suffix}_{uuid.uuid4().hex[:6]}",
            "description": "Test incident for autonomous agent testing - Network connectivity issue on core router",
            "priority": "P2",
            "category": "Network",
            "affected_devices": []
        }
        
        response = self.session.post(f"{BASE_URL}/api/incidents", json=incident_data)
        assert response.status_code == 200 or response.status_code == 201, f"Failed to create incident: {response.text}"
        return response.json()
    
    # ==================== Agent Settings Tests ====================
    
    def test_get_agent_settings(self):
        """Test GET /api/agent-exec/settings returns agent settings"""
        response = self.session.get(f"{BASE_URL}/api/agent-exec/settings")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify settings structure
        assert "id" in data, "Settings should have an id"
        assert "auto_trigger_on_incident" in data, "Settings should have auto_trigger_on_incident"
        assert "auto_trigger_priorities" in data, "Settings should have auto_trigger_priorities"
        assert "max_auto_actions_per_incident" in data, "Settings should have max_auto_actions_per_incident"
        assert "ssh_timeout" in data, "Settings should have ssh_timeout"
        assert "enable_real_ssh" in data, "Settings should have enable_real_ssh"
        
        print(f"✅ Agent settings retrieved: auto_trigger={data.get('auto_trigger_on_incident')}, ssh_enabled={data.get('enable_real_ssh')}")
    
    def test_update_agent_settings(self):
        """Test PUT /api/agent-exec/settings updates settings"""
        # Get current settings
        current = self.session.get(f"{BASE_URL}/api/agent-exec/settings").json()
        
        # Update settings
        new_settings = {
            "auto_trigger_on_incident": False,
            "auto_trigger_priorities": ["P1"],
            "max_auto_actions_per_incident": 5,
            "ssh_timeout": 45,
            "enable_real_ssh": False,
            "notification_on_action": True
        }
        
        response = self.session.put(f"{BASE_URL}/api/agent-exec/settings", json=new_settings)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, "Update should return success=True"
        
        # Verify settings were updated
        updated = self.session.get(f"{BASE_URL}/api/agent-exec/settings").json()
        assert updated.get("auto_trigger_priorities") == ["P1"], "Priorities should be updated"
        assert updated.get("max_auto_actions_per_incident") == 5, "Max actions should be updated"
        
        print("✅ Agent settings updated successfully")
    
    # ==================== Agent Execution Tests ====================
    
    def test_run_agent_on_incident(self):
        """Test POST /api/agent-exec/run/{incident_id} runs autonomous troubleshooting"""
        # Create a test incident
        incident = self.create_test_incident("run_agent")
        incident_id = incident.get("id")
        
        # Run agent on incident
        response = self.session.post(f"{BASE_URL}/api/agent-exec/run/{incident_id}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify execution response structure
        assert "id" in data, "Execution should have an id"
        assert "incident_id" in data, "Execution should have incident_id"
        assert data["incident_id"] == incident_id, "Incident ID should match"
        assert "status" in data, "Execution should have status"
        assert "execution_log" in data, "Execution should have execution_log"
        assert "triggered_by" in data, "Execution should have triggered_by"
        
        # Verify execution log has entries
        assert len(data.get("execution_log", [])) > 0, "Execution log should have entries"
        
        # Check for analysis results
        assert "root_cause" in data or "analysis" in data, "Execution should have analysis or root_cause"
        
        print(f"✅ Agent executed on incident. Status: {data.get('status')}, Log entries: {len(data.get('execution_log', []))}")
        print(f"   Root cause: {data.get('root_cause', 'N/A')[:100]}...")
    
    def test_run_agent_on_nonexistent_incident(self):
        """Test POST /api/agent-exec/run/{incident_id} returns 404 for non-existent incident"""
        fake_id = "nonexistent-incident-id-12345"
        
        response = self.session.post(f"{BASE_URL}/api/agent-exec/run/{fake_id}")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print("✅ Agent correctly returns 404 for non-existent incident")
    
    def test_get_all_executions(self):
        """Test GET /api/agent-exec/executions returns list of executions"""
        response = self.session.get(f"{BASE_URL}/api/agent-exec/executions")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        print(f"✅ Retrieved {len(data)} agent executions")
    
    def test_get_executions_by_incident(self):
        """Test GET /api/agent-exec/executions with incident_id filter"""
        # Create incident and run agent
        incident = self.create_test_incident("filter_test")
        incident_id = incident.get("id")
        
        # Run agent
        self.session.post(f"{BASE_URL}/api/agent-exec/run/{incident_id}")
        
        # Get executions filtered by incident
        response = self.session.get(f"{BASE_URL}/api/agent-exec/executions", params={"incident_id": incident_id})
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        # All executions should be for this incident
        for execution in data:
            assert execution.get("incident_id") == incident_id, "All executions should be for the specified incident"
        
        print(f"✅ Retrieved {len(data)} executions for incident {incident_id}")
    
    # ==================== Pending Actions Tests ====================
    
    def test_get_pending_actions(self):
        """Test GET /api/agent-exec/pending-actions returns pending confirmations"""
        response = self.session.get(f"{BASE_URL}/api/agent-exec/pending-actions")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        # Verify structure if there are pending actions
        if len(data) > 0:
            action = data[0]
            assert "id" in action, "Action should have id"
            assert "action_type" in action, "Action should have action_type"
            assert "status" in action, "Action should have status"
            assert action.get("status") == "pending", "Status should be pending"
        
        print(f"✅ Retrieved {len(data)} pending actions")
    
    def test_get_pending_actions_count(self):
        """Test GET /api/agent-exec/pending-actions/count returns count"""
        response = self.session.get(f"{BASE_URL}/api/agent-exec/pending-actions/count")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "count" in data, "Response should have count field"
        assert isinstance(data["count"], int), "Count should be an integer"
        assert data["count"] >= 0, "Count should be non-negative"
        
        print(f"✅ Pending actions count: {data['count']}")
    
    # ==================== Action Approval/Rejection Tests ====================
    
    def test_approve_nonexistent_action(self):
        """Test POST /api/agent-exec/actions/{id}/approve returns 404 for non-existent action"""
        fake_id = "nonexistent-action-id-12345"
        
        response = self.session.post(f"{BASE_URL}/api/agent-exec/actions/{fake_id}/approve")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print("✅ Approve correctly returns 404 for non-existent action")
    
    def test_reject_nonexistent_action(self):
        """Test POST /api/agent-exec/actions/{id}/reject returns 404 for non-existent action"""
        fake_id = "nonexistent-action-id-12345"
        
        response = self.session.post(f"{BASE_URL}/api/agent-exec/actions/{fake_id}/reject", params={"reason": "Test rejection"})
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print("✅ Reject correctly returns 404 for non-existent action")
    
    # ==================== Execution Log Tests ====================
    
    def test_get_execution_log_for_incident(self):
        """Test GET /api/agent-exec/execution-log/{incident_id} returns logs"""
        # Create incident and run agent
        incident = self.create_test_incident("log_test")
        incident_id = incident.get("id")
        
        # Run agent
        self.session.post(f"{BASE_URL}/api/agent-exec/run/{incident_id}")
        
        # Get execution log
        response = self.session.get(f"{BASE_URL}/api/agent-exec/execution-log/{incident_id}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        if len(data) > 0:
            execution = data[0]
            assert "execution_log" in execution, "Execution should have execution_log"
            assert len(execution.get("execution_log", [])) > 0, "Execution log should have entries"
        
        print(f"✅ Retrieved execution log with {len(data)} execution(s)")
    
    # ==================== Integration Test ====================
    
    def test_full_agent_workflow(self):
        """Test complete agent workflow: create incident -> run agent -> check results"""
        # 1. Create incident
        incident = self.create_test_incident("full_workflow")
        incident_id = incident.get("id")
        print(f"1. Created incident: {incident.get('ticket_number')}")
        
        # 2. Run agent
        exec_response = self.session.post(f"{BASE_URL}/api/agent-exec/run/{incident_id}")
        assert exec_response.status_code == 200, f"Agent execution failed: {exec_response.text}"
        
        execution = exec_response.json()
        print(f"2. Agent executed. Status: {execution.get('status')}")
        
        # 3. Verify execution has required fields
        assert execution.get("incident_id") == incident_id
        assert execution.get("triggered_by") is not None
        assert len(execution.get("execution_log", [])) > 0
        
        # 4. Check if incident was resolved or has pending actions
        if execution.get("incident_resolved"):
            print("3. Incident was auto-resolved by agent")
            
            # Verify incident status updated
            incident_check = self.session.get(f"{BASE_URL}/api/incidents/{incident_id}").json()
            assert incident_check.get("status") == "resolved", "Incident should be resolved"
            print("4. Verified incident status is 'resolved'")
        elif execution.get("pending_confirmations"):
            print(f"3. Agent created {len(execution.get('pending_confirmations', []))} pending action(s)")
            
            # Verify pending actions exist
            pending = self.session.get(f"{BASE_URL}/api/agent-exec/pending-actions").json()
            print(f"4. Verified {len(pending)} pending action(s) in queue")
        else:
            print("3. Agent completed with partial resolution or no actions needed")
        
        # 5. Verify execution log has meaningful entries
        log_entries = execution.get("execution_log", [])
        log_types = [entry.get("type") for entry in log_entries]
        print(f"5. Execution log types: {log_types}")
        
        assert "info" in log_types or "analysis" in log_types, "Log should have info or analysis entries"
        
        print("✅ Full agent workflow completed successfully")


class TestAgentExecutionDetails:
    """Test agent execution details and log structure"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@noc.com",
            "password": "admin123"
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip("Authentication failed")
        
        yield
    
    def test_execution_log_structure(self):
        """Test that execution log entries have correct structure"""
        # Create and run agent on incident
        incident_data = {
            "title": f"TEST_Log_Structure_{uuid.uuid4().hex[:6]}",
            "description": "Test incident for log structure verification",
            "priority": "P1",
            "category": "Network"
        }
        
        incident = self.session.post(f"{BASE_URL}/api/incidents", json=incident_data).json()
        execution = self.session.post(f"{BASE_URL}/api/agent-exec/run/{incident['id']}").json()
        
        # Verify log entry structure
        for entry in execution.get("execution_log", []):
            assert "timestamp" in entry, "Log entry should have timestamp"
            assert "message" in entry, "Log entry should have message"
            assert "type" in entry, "Log entry should have type"
            
            # Verify timestamp is valid ISO format
            assert "T" in entry["timestamp"], "Timestamp should be ISO format"
        
        print(f"✅ Verified {len(execution.get('execution_log', []))} log entries have correct structure")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/incidents/{incident['id']}")
    
    def test_execution_status_values(self):
        """Test that execution status is one of valid values"""
        valid_statuses = ["pending", "analyzing", "executing", "waiting_confirmation", "completed", "failed", "partially_resolved"]
        
        # Get all executions
        executions = self.session.get(f"{BASE_URL}/api/agent-exec/executions").json()
        
        for execution in executions:
            status = execution.get("status")
            assert status in valid_statuses, f"Invalid status: {status}"
        
        print(f"✅ All {len(executions)} executions have valid status values")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
