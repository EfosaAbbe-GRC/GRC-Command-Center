import subprocess
import os

import re

class AgentRunner:
    def __init__(self):
        self.approved_agents = ["compliance_checker", "risk_assessor", "policy_analyzer", "network_scanner"]
        self.agent_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "agents")
        self.safe_path_pattern = re.compile(r'^[a-zA-Z0-9_\-./ ]+$')

    def sanitize_args(self, args: dict) -> dict:
        """Validate and sanitize agent arguments."""
        if not args:
            return {}
            
        for key, value in args.items():
            if isinstance(value, str):
                # 1. Block Path Traversal
                if ".." in value or value.startswith("/") or value.startswith("\\"):
                     raise ValueError(f"Security Alert: Path traversal attempt in argument '{key}'")
                
                # 2. Block Shell Injection
                if any(c in value for c in [';', '|', '&', '`', '$', '>', '<', '(', ')']):
                     raise ValueError(f"Security Alert: Shell metacharacters detected in argument '{key}'")

                # 3. Allow only safe characters
                if not self.safe_path_pattern.match(value):
                     raise ValueError(f"Security Alert: Invalid characters in argument '{key}'")
        
        return args

    def execute_agent(self, agent_name: str, args: dict = None):
        """
        Runs a compliance script and returns the output.
        Locked down to prevent arbitrary code execution (ACE).
        """
        if agent_name not in self.approved_agents:
            return {"error": f"Security Violation: Agent '{agent_name}' is not in the approved registry."}
        
        # Sanitize Inputs
        try:
            clean_args = self.sanitize_args(args)
        except ValueError as ve:
            return {"error": str(ve)}
            
        # Prevent directory traversal just in case
        # Ensure agent_name itself doesn't contain path components
        clean_agent_name = os.path.basename(agent_name)
        if clean_agent_name != agent_name:
            return {"error": f"Security Violation: Agent name '{agent_name}' contains invalid path components."}

        script_path = os.path.join(self.agent_dir, f"{clean_agent_name}.py")
        
        if not os.path.exists(script_path):
            return {"error": f"Agent script not found: {clean_agent_name}"}
        
        # Prepare command with sanitized arguments
        command = ["python", script_path]
        for key, value in clean_args.items():
            command.append(f"--{key}={value}")

        try:
            # Isolated execution
            result = subprocess.run(
                command, 
                capture_output=True, 
                text=True,
                timeout=30 # Prevent long-running process hang
            )
            return {
                "status": "success" if result.returncode == 0 else "failure",
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        except subprocess.TimeoutExpired:
            return {"error": "Agent execution timed out (30s limit)."}
        except Exception as e:
            return {"error": f"Internal Execution Error: {str(e)}"}

# Singleton Instance
agent_runner = AgentRunner()
