"""CLI helper functions for HTTP API calls."""
import httpx
import yaml
import typer


def load_config(config_path: str) -> dict:
    """Load agent configuration from YAML file."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def deploy_app(config_path: str):
    """
    Register an agent via API.
    
    Reads config from YAML, calls POST /api/v1/agents, prints agent ID.
    """
    config = load_config(config_path)
    
    name = config.get("name")
    capabilities = config.get("capabilities", [])
    api_base = config.get("api_base_url", "http://localhost:8000")
    
    if not name:
        typer.echo("Error: 'name' is required in config file", err=True)
        raise typer.Exit(1)
    
    with httpx.Client() as client:
        # First, need to get auth token (simplified - assumes user has token)
        # In production, this would use proper auth flow
        try:
            response = client.post(
                f"{api_base}/api/v1/agents/",
                json={"name": name, "capabilities": capabilities},
                timeout=30.0,
            )
            response.raise_for_status()
            agent = response.json()
            typer.echo(f"Agent registered successfully!")
            typer.echo(f"Agent ID: {agent['id']}")
            typer.echo(f"Name: {agent['name']}")
            typer.echo(f"Status: {agent['status']}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                typer.echo(f"Error: Agent '{name}' already exists", err=True)
            else:
                typer.echo(f"Error: {e.response.text}", err=True)
            raise typer.Exit(1)
        except Exception as e:
            typer.echo(f"Error connecting to API: {e}", err=True)
            raise typer.Exit(1)


def status_app(api_base: str, token: str):
    """
    List all agents via API.
    """
    headers = {"Authorization": f"Bearer {token}"}
    
    with httpx.Client() as client:
        try:
            response = client.get(
                f"{api_base}/api/v1/agents/",
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            
            typer.echo(f"Total agents: {data['total']}")
            typer.echo("")
            for agent in data["items"]:
                typer.echo(f"  ID: {agent['id']}")
                typer.echo(f"  Name: {agent['name']}")
                typer.echo(f"  Status: {agent['status']}")
                typer.echo(f"  Capabilities: {agent.get('capabilities', [])}")
                typer.echo("")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                typer.echo("Error: Invalid or expired token", err=True)
            else:
                typer.echo(f"Error: {e.response.text}", err=True)
            raise typer.Exit(1)
        except Exception as e:
            typer.echo(f"Error connecting to API: {e}", err=True)
            raise typer.Exit(1)


def heartbeat_app(agent_id: int, api_base: str, token: str):
    """
    Send heartbeat to an agent via API.
    """
    headers = {"Authorization": f"Bearer {token}"}
    
    with httpx.Client() as client:
        try:
            response = client.post(
                f"{api_base}/api/v1/agents/{agent_id}/heartbeat",
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()
            agent = response.json()
            
            typer.echo(f"Heartbeat sent successfully!")
            typer.echo(f"Agent ID: {agent['id']}")
            typer.echo(f"Status: {agent['status']}")
            typer.echo(f"Last heartbeat: {agent['last_heartbeat']}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                typer.echo("Error: Invalid or expired token", err=True)
            elif e.response.status_code == 404:
                typer.echo(f"Error: Agent {agent_id} not found", err=True)
            else:
                typer.echo(f"Error: {e.response.text}", err=True)
            raise typer.Exit(1)
        except Exception as e:
            typer.echo(f"Error connecting to API: {e}", err=True)
            raise typer.Exit(1)