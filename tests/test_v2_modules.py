import sys
import os

# Ensure src is in path
sys.path.append(os.getcwd())

from src.schemas import ProjectContext
from src.utils.prompt_loader import load_prompt
from src.decision_engine.contracts.infra_spec import InfraSpec
from src.decision_engine.planner.architecture_planner import ArchitecturePlanner
from src.decision_engine.scoring.scorecard import weighted_score

def test_prompt_loader():
    print("Testing PromptLoader...")
    # Stage=docker, role=writer_a matches configs/prompts/docker/writer_a.md
    p = load_prompt("docker", "writer_a")
    assert "Senior DevOps Engineer" in p
    print("✅ PromptLoader passed")

def test_planner():
    print("Testing ArchitecturePlanner...")
    ctx = ProjectContext(
        project_name="test-project",
        language="python",
        frameworks=["fastapi"],
        dependencies=["fastapi", "uvicorn", "redis", "sqlalchemy", "psycopg2"],
        ports=["8000"]
    )
    planner = ArchitecturePlanner()
    plan = planner.create_plan(ctx)
    print(f"  Plan: {plan}")
    assert plan.service_type == "api"
    assert plan.requires_cache == True
    assert plan.requires_database == True
    print("✅ Planner passed")

def test_scoring():
    print("Testing Scoring...")
    spec = InfraSpec(
        file_content="FROM python:3.9",
        model_name="test",
        security_score=80,
        best_practice_score=90,
        complexity_score=20, # Simplicity = 80
        performance_score=70,
        violations=["warning-1"]
    )
    # Score: 80*0.4(32) + 90*0.3(27) + 80*0.2(16) + 70*0.1(7) = 32+27+16+7 = 82
    # Penalty: 1 violation * 15 = 15
    # Final: 82 - 15 = 67
    score = weighted_score(spec)
    print(f"  Score: {score}")
    assert score == 67.0
    print("✅ Scoring passed")


if __name__ == "__main__":
    test_prompt_loader()
    test_planner()
    test_scoring()

    print("\n🎉 ALL V2 MODULES VERIFIED 🎉")
