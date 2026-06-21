#!/usr/bin/env python3
"""Generate architecture diagram PNG for README."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

fig, ax = plt.subplots(1, 1, figsize=(14, 10))
ax.set_xlim(0, 14)
ax.set_ylim(0, 10)
ax.axis("off")

# Colors
c_client = "#E3F2FD"
c_router = "#C8E6C9"
c_db = "#FFF3E0"
c_external = "#F3E5F5"
c_cli = "#FFEBEE"
c_title = "#1A237E"
edge_color = "#424242"

def box(ax, x, y, w, h, text, color, fontsize=9, bold=False):
    bbox = FancyBboxPatch((x - w/2, y - h/2), w, h,
                          boxstyle="round,pad=0.15,rounding_size=0.15",
                          facecolor=color, edgecolor=edge_color, linewidth=1.5)
    ax.add_patch(bbox)
    weight = "bold" if bold else "normal"
    ax.text(x, y, text, ha="center", va="center", fontsize=fontsize,
            fontweight=weight, color="#212121", wrap=True)

def arrow(ax, x1, y1, x2, y2, label=""):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color=edge_color, lw=1.5))
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mx, my + 0.15, label, ha="center", va="bottom", fontsize=7, color="#616161")

# Title
ax.text(7, 9.6, "DevOps Agent — SaaS Architecture", ha="center", va="center",
        fontsize=18, fontweight="bold", color=c_title)

# Clients
box(ax, 7, 8.6, 3.5, 0.6, "Clients\nWeb UI / CLI / HTTP", c_client, 10, bold=True)

# FastAPI Server
box(ax, 7, 7.3, 12, 0.9, "FastAPI Server (Uvicorn)", "#BBDEFB", 11, bold=True)

# Routers
router_y = 6.0
router_w, router_h = 1.5, 0.55
router_gap = 1.7
router_xs = [2.0, 3.7, 5.4, 7.1, 8.8, 10.5, 12.2]
router_labels = ["Auth", "Projects", "Runs", "Video", "Agents", "Eval", "Admin"]
router_colors = [c_router] * 7

for x, label in zip(router_xs, router_labels):
    box(ax, x, router_y, router_w, router_h, label, c_router, 8)

# CRUD Layer
box(ax, 7, 4.8, 12, 0.6, "SQLAlchemy ORM + CRUD Layer", "#DCEDC8", 10, bold=True)

# Database
box(ax, 7, 3.7, 8, 0.6, "SQLite (dev) / PostgreSQL (prod)", c_db, 10, bold=True)

# External boxes
box(ax, 2.5, 2.4, 2.8, 0.7, "Video Generation API\n(Replicate/Runway)", c_external, 8)
box(ax, 7.0, 2.4, 2.8, 0.7, "CLI Agent Workers\n(Typer)", c_cli, 8)
box(ax, 11.5, 2.4, 2.8, 0.7, "Cohen's Kappa\nEvaluation Engine", c_external, 8)

# Arrows: Clients → Server
arrow(ax, 7, 8.3, 7, 7.75, "REST API")

# Arrows: Server → Routers
for x in router_xs:
    arrow(ax, x, 7.3 - 0.45, x, 6.0 + 0.28)

# Arrows: Routers → CRUD
for x in router_xs:
    arrow(ax, x, 6.0 - 0.28, x, 4.8 + 0.3)

# Arrows: CRUD → DB
arrow(ax, 7, 4.5, 7, 4.0, "SQL")

# Arrows: Video → External
arrow(ax, 5.4, 5.73, 2.5, 2.75, "HTTP")

# Arrows: Agents → CLI
arrow(ax, 8.8, 5.73, 7.0, 2.75, "deploy")

# Arrows: Eval → Engine
arrow(ax, 10.5, 5.73, 11.5, 2.75, "compute")

# Footer
ax.text(7, 0.9, "Python 3.12  •  FastAPI  •  SQLAlchemy  •  JWT Auth  •  pytest", ha="center", va="center",
        fontsize=9, color="#757575")

ax.text(7, 0.5, "GitHub Integration  •  Background Tasks  •  Multi-Agent CLI  •  Evaluation Framework", ha="center", va="center",
        fontsize=9, color="#757575")

plt.tight_layout()
plt.savefig("docs/architecture.png", dpi=150, bbox_inches="tight", facecolor="white", edgecolor="none")
print("Generated docs/architecture.png")
