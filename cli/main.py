"""Multi-agent CLI using Typer."""
import typer

app = typer.Typer(help="DevOps Agent Multi-Agent CLI")

# Import subcommands
from cli.deploy import deploy_app
from cli.deploy import status_app
from cli.deploy import heartbeat_app


@app.command()
def deploy(
    config: str = typer.Option("cli/example-agent.yaml", "--config", "-c", help="Path to agent config YAML"),
):
    """
    Register a new agent with the API.
    
    Reads agent configuration from the specified YAML file.
    """
    deploy_app(config)


@app.command()
def status(
    api_base: str = typer.Option("http://localhost:8000", "--api-base", help="API base URL"),
    token: str = typer.Option(..., "--token", "-t", help="JWT authentication token"),
):
    """
    List all registered agents via API.
    """
    status_app(api_base, token)


@app.command()
def heartbeat(
    agent_id: int = typer.Argument(..., help="Agent ID to send heartbeat to"),
    api_base: str = typer.Option("http://localhost:8000", "--api-base", help="API base URL"),
    token: str = typer.Option(..., "--token", "-t", help="JWT authentication token"),
):
    """
    Send a heartbeat to keep agent alive.
    """
    heartbeat_app(agent_id, api_base, token)


if __name__ == "__main__":
    app()