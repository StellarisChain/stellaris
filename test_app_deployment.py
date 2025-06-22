#!/usr/bin/env python3
"""
Test script for VoxaCommunications app deployment system.
"""

import asyncio
import json
import time
import requests
from typing import Dict, Any, Optional

BASE_URL = "http://localhost:9999"

def test_api_endpoint(endpoint: str, method: str = "GET", data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Test an API endpoint"""
    url = f"{BASE_URL}{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=30)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        print(f"[{method}] {endpoint} -> {response.status_code}")
        
        if response.status_code in [200, 201]:
            return {"success": True, "data": response.json()}
        else:
            return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}

def test_app_deployment():
    """Test deploying an application"""
    print("\\n=== Testing App Deployment ===")
    
    # Test deployment
    app_spec = {
        "name": "test-nginx",
        "version": "1.0.0",
        "image": "nginx:alpine",
        "replicas": 1,
        "resource_requirements": {
            "memory": "128m",
            "cpu": "0.1"
        },
        "network_config": {
            "ports": {"80/tcp": {"HostPort": "8080"}}
        }
    }
    
    print("Deploying test application...")
    result = test_api_endpoint("/api/apps/deploy_app", "POST", app_spec)
    
    if result["success"]:
        app_id = result["data"]["app_id"]
        print(f"✅ App deployed successfully! App ID: {app_id}")
        return app_id
    else:
        print(f"❌ Deployment failed: {result['error']}")
        return None

def test_app_listing():
    """Test listing applications"""
    print("\\n=== Testing App Listing ===")
    
    result = test_api_endpoint("/api/apps/list_apps")
    
    if result["success"]:
        apps = result["data"]["apps"]
        print(f"✅ Found {len(apps)} applications:")
        for app in apps:
            print(f"  - {app['name']} ({app['app_id'][:8]}...): {app['instances']} instances")
        return apps
    else:
        print(f"❌ Listing failed: {result['error']}")
        return []

def test_app_status(app_id: str):
    """Test getting app status"""
    print(f"\\n=== Testing App Status (ID: {app_id[:8]}...) ===")
    
    result = test_api_endpoint(f"/api/apps/get_app_status?app_id={app_id}")
    
    if result["success"]:
        status = result["data"]["app_status"]
        print(f"✅ App status retrieved:")
        print(f"  - Name: {status['app_spec']['name']}")
        print(f"  - Version: {status['app_spec']['version']}")
        print(f"  - Instances: {status['total_instances']}")
        print(f"  - Status Summary: {status['status_summary']}")
        return status
    else:
        print(f"❌ Status check failed: {result['error']}")
        return None

def test_app_scaling(app_id: str, replicas: int):
    """Test scaling an application"""
    print(f"\\n=== Testing App Scaling (ID: {app_id[:8]}..., Replicas: {replicas}) ===")
    
    scale_data = {
        "app_id": app_id,
        "replicas": replicas
    }
    
    result = test_api_endpoint("/api/apps/scale_app", "POST", scale_data)
    
    if result["success"]:
        print(f"✅ App scaled successfully!")
        print(f"  - Action: {result['data']['result']['action']}")
        return True
    else:
        print(f"❌ Scaling failed: {result['error']}")
        return False

def test_app_stopping(app_id: str):
    """Test stopping an application"""
    print(f"\\n=== Testing App Stopping (ID: {app_id[:8]}...) ===")
    
    stop_data = {
        "app_id": app_id
    }
    
    result = test_api_endpoint("/api/apps/stop_app", "POST", stop_data)
    
    if result["success"]:
        stop_result = result["data"]["result"]
        print(f"✅ App stopped successfully!")
        print(f"  - Stopped: {stop_result['stopped']}/{stop_result['total']} instances")
        return True
    else:
        print(f"❌ Stopping failed: {result['error']}")
        return False

def test_node_health():
    """Test that the node is healthy"""
    print("\\n=== Testing Node Health ===")
    
    try:
        response = requests.get(f"{BASE_URL}/status/health", timeout=5)
        if response.status_code == 200:
            print("✅ Node is healthy")
            return True
        else:
            print(f"❌ Node health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to node: {e}")
        return False

def wait_for_deployment(app_id: str, timeout: int = 60) -> bool:
    """Wait for app deployment to complete"""
    print(f"Waiting for deployment to complete (timeout: {timeout}s)...")
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        result = test_api_endpoint(f"/api/apps/get_app_status?app_id={app_id}")
        
        if result["success"]:
            status = result["data"]["app_status"]
            running_instances = status["status_summary"].get("running", 0)
            
            if running_instances > 0:
                print(f"✅ Deployment completed! {running_instances} instances running")
                return True
        
        print(".", end="", flush=True)
        time.sleep(2)
    
    print(f"\\n❌ Deployment timeout after {timeout}s")
    return False

def main():
    """Main test function"""
    print("🚀 VoxaCommunications App Deployment Test Suite")
    print("=" * 50)
    
    # Check node health first
    if not test_node_health():
        print("\\n❌ Node is not healthy. Cannot proceed with tests.")
        return
    
    # Test basic functionality
    apps = test_app_listing()
    
    # Deploy a test app
    app_id = test_app_deployment()
    if not app_id:
        print("\\n❌ Cannot proceed without successful deployment")
        return
    
    # Wait for deployment to complete
    if not wait_for_deployment(app_id):
        print("\\n❌ Deployment did not complete in time")
        return
    
    # Test app status
    status = test_app_status(app_id)
    if not status:
        print("\\n❌ Cannot get app status")
        return
    
    # Test scaling
    test_app_scaling(app_id, 2)
    time.sleep(5)  # Wait for scaling
    test_app_status(app_id)
    
    # Test scaling down
    test_app_scaling(app_id, 1)
    time.sleep(5)  # Wait for scaling
    test_app_status(app_id)
    
    # Clean up - stop the app
    test_app_stopping(app_id)
    
    # Final listing
    test_app_listing()
    
    print("\\n🎉 Test suite completed!")

if __name__ == "__main__":
    main()
