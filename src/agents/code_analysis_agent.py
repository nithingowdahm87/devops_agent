import os
import json
import logging
from typing import Any

logger = logging.getLogger("devops-agent")
from src.tools.file_ops import scan_directory, read_file, write_file
from src.tools.context_gatherer import ContextGatherer
from src.schemas import ProjectContext

class CodeAnalysisAgent:
    """
    Stage 1 Agent: Deeply analyzes the codebase and caches the results
    to .devops_context.json for all subsequent agents to use.
    """
    def __init__(self, project_path: str):
        self.project_path = project_path
        self.cache_file = os.path.join(project_path, ".devops_context.json")
    
    def analyze(self) -> ProjectContext:
        print(f"🕵️  Code Analysis Agent: Scanning {self.project_path}...")
        
        # 1. Gather raw context using our existing tool
        gatherer = ContextGatherer(self.project_path)
        raw_context = gatherer.get_context()
        
        # 2. Extract structured data
        analysis = {
            "project_name": os.path.basename(os.path.abspath(self.project_path)),
            "language": "unknown",
            "frameworks": [],
            "dependencies": [],
            "ports": [],
            "env_vars": [],
            "file_structure": scan_directory(self.project_path),
            "raw_context_summary": raw_context
        }
        
        # 3. specific heuristics
        self._detect_node(analysis)
        self._detect_python(analysis)
        self._detect_ports(analysis)
        self._detect_env_vars(analysis)
        self._detect_existing_files(analysis)
        self._detect_architecture(analysis)
        self._verify_db_detection(analysis)
        
        # 4. Create Pydantic model
        context = ProjectContext(**analysis)
        
        # 5. Save to Cache
        self._save_cache(context)
        print(f"✅ Analysis complete. Cached to {self.cache_file}")
        
        return context

    def _detect_node(self, analysis: dict):
        # Scan recursively
        for root, dirs, files in os.walk(self.project_path):
            if "node_modules" in dirs: 
                dirs.remove("node_modules")
            
            if "package.json" in files:
                analysis["language"] = "javascript/node" # At least one node app found
                pkg_path = os.path.join(root, "package.json")
                try:
                    data = json.loads(read_file(pkg_path))
                    deps = list(data.get("dependencies", {}).keys())
                    analysis["dependencies"].extend(deps)
                    
                    # Merge scripts (prefix with folder name to avoid collision?)
                    # For now just flat merge, last wins or maybe ignore scripts for deep files
                    if root == self.project_path:
                        analysis["scripts"] = data.get("scripts", {})
                        
                    if "express" in deps:
                        analysis["frameworks"].append("express")
                    if "react" in deps:
                        analysis["frameworks"].append("react")
                except Exception: pass
        
        # Deduplicate
        analysis["dependencies"] = list(set(analysis["dependencies"]))
        analysis["frameworks"] = list(set(analysis["frameworks"]))

    def _detect_python(self, analysis: dict):
        for root, dirs, files in os.walk(self.project_path):
            if "venv" in dirs: dirs.remove("venv")
            if "__pycache__" in dirs: dirs.remove("__pycache__")
            
            if "requirements.txt" in files:
                analysis["language"] = "python"
                req_path = os.path.join(root, "requirements.txt")
                try:
                    content = read_file(req_path)
                    deps = [line.split('==')[0].split('>=')[0].strip() for line in content.splitlines() if line and not line.startswith("#")]
                    analysis["dependencies"].extend(deps)
                    
                    content_lower = content.lower()
                    if "flask" in content_lower: analysis["frameworks"].append("flask")
                    if "django" in content_lower: analysis["frameworks"].append("django")
                    if "fastapi" in content_lower: analysis["frameworks"].append("fastapi")
                except Exception: pass
                
        # Deduplicate
        analysis["dependencies"] = list(set(analysis["dependencies"]))
        analysis["frameworks"] = list(set(analysis["frameworks"]))

    def _detect_ports(self, analysis: dict):
        # Naive scan for common port patterns
        import re
        full_text = analysis["raw_context_summary"] 
        likely_files = ["server.js", "app.py", "main.py", "index.js", "docker-compose.yml"]
        
        files_to_scan = []
        for root, _, files in os.walk(self.project_path):
            for file in files:
                if file in likely_files:
                    files_to_scan.append(os.path.join(root, file))
        
        found_ports = set()
        for fpath in files_to_scan: # Limit scanning
            content = read_file(fpath)
            # Look for 3000, 8000, 8080 or port=XXXX
            matches = re.findall(r'port\s*[:=]\s*(\d{4})', content, re.IGNORECASE)
            found_ports.update(matches)
            matches2 = re.findall(r'\.listen\(\s*(\d{4})', content)
            found_ports.update(matches2)
            
        if found_ports:
            analysis["ports"] = list(found_ports)
        # Default fallback if known framework
        elif "express" in analysis["frameworks"]:
            analysis["ports"].append("3000")
        elif "django" in analysis["frameworks"]:
            analysis["ports"].append("8000")

    def _detect_env_vars(self, analysis: dict):
        import re
        likely_files = ["server.js", "app.py", "main.py", "config.js", "settings.py"]
        files_to_scan = []
        for root, _, files in os.walk(self.project_path):
            for file in files:
                if file in likely_files:
                    files_to_scan.append(os.path.join(root, file))
        
        envs = set()
        for fpath in files_to_scan:
            content = read_file(fpath)
            # Node
            matches = re.findall(r'process\.env\.([A-Z_][A-Z0-9_]*)', content)
            envs.update(matches)
            # Python
            matches_py = re.findall(r'os\.environ\.get\([\'"]([A-Z_][A-Z0-9_]*)[\'"]\)', content)
            envs.update(matches_py)
            
        analysis["env_vars"] = list(envs)

    def _detect_existing_files(self, analysis: dict):
        """Scans for existing DevOps artifacts."""
        found = {}
        for root, dirs, files in os.walk(self.project_path):
            if ".git" in dirs: dirs.remove(".git")
            if "node_modules" in dirs: dirs.remove("node_modules")
            if "__pycache__" in dirs: dirs.remove("__pycache__")
            
            for file in files:
                fpath = os.path.join(root, file)
                rel_path = os.path.relpath(fpath, self.project_path)
                
                if file == "Dockerfile":
                    found["Dockerfile"] = rel_path
                elif file in ["docker-compose.yml", "docker-compose.yaml"]:
                    found["Compose"] = rel_path
                elif file in ["manifest.yaml", "deployment.yaml", "service.yaml"]:
                    found["K8s"] = rel_path
                elif file == "Chart.yaml":
                    found["Helm"] = rel_path
                elif file.endswith(".tf"):
                    found["Terraform"] = rel_path
            
            # Check for hidden .github
            if ".github" in dirs or ".github" in root:
                gh_path = os.path.join(root, ".github", "workflows")
                if os.path.exists(gh_path):
                    found["GitHub Actions"] = os.path.relpath(gh_path, self.project_path)

        analysis["existing_files"] = found

    def _detect_architecture(self, analysis: dict):
        """Detects architectural patterns, per-service details, categorized and annotated databases."""
        import re
        arch = set()

        # ─── Comprehensive Database Detection Maps ──────────────────────
        DB_RDBMS = {
            "pg": "PostgreSQL", "psycopg2": "PostgreSQL", "psycopg": "PostgreSQL",
            "postgres": "PostgreSQL", "pg-promise": "PostgreSQL",
            "mysql2": "MySQL", "mysql": "MySQL", "mysql-connector-python": "MySQL",
            "mariadb": "MariaDB",
            "sqlite3": "SQLite", "better-sqlite3": "SQLite",
            "sequelize": "Sequelize (ORM)", "typeorm": "TypeORM", "prisma": "Prisma (ORM)",
            "knex": "Knex (Query Builder)",
            "mssql": "MS SQL Server", "tedious": "MS SQL Server",
            "oracledb": "Oracle DB",
            "cockroachdb": "CockroachDB",
            "sqlalchemy": "SQLAlchemy (ORM)", "alembic": "Alembic (Migrations)",
        }
        DB_CACHE = {
            "redis": "Redis", "ioredis": "Redis", "redis-py": "Redis",
            "dragonfly": "Dragonfly", "dragonfly-db": "Dragonfly",
            "memcached": "Memcached", "pylibmc": "Memcached",
            "keydb": "KeyDB", "valkey": "Valkey",
        }
        DB_NOSQL = {
            "mongoose": "MongoDB", "pymongo": "MongoDB", "mongodb": "MongoDB",
            "motor": "MongoDB (async)",
            "cassandra-driver": "Cassandra", "cassandra": "Cassandra",
            "elasticsearch": "Elasticsearch", "opensearch-py": "OpenSearch",
            "@elastic/elasticsearch": "Elasticsearch",
            "dynamodb": "DynamoDB", "@aws-sdk/client-dynamodb": "DynamoDB",
            "firestore": "Firestore", "@google-cloud/firestore": "Firestore",
            "firebase-admin": "Firebase/Firestore",
            "nano": "CouchDB", "couchbase": "Couchbase",
            "neo4j-driver": "Neo4j (Graph DB)",
            "influxdb-client": "InfluxDB (Time-series)", "influxdb": "InfluxDB",
            "timescaledb": "TimescaleDB", "arangodb": "ArangoDB",
        }
        DB_BROKER = {
            "kafkajs": "Kafka", "kafka-node": "Kafka", "confluent-kafka-python": "Kafka",
            "amqplib": "RabbitMQ", "pika": "RabbitMQ",
            "nats": "NATS",
            "bull": "Bull (Redis Queue)", "bullmq": "BullMQ (Redis Queue)",
            "celery": "Celery (Task Queue)",
        }

        # Tracking: {db_name -> [service_names]}
        db_rdbms: dict  = {}
        db_cache: dict  = {}
        db_nosql: dict  = {}
        db_broker: dict = {}

        def _register_db(dep: str, svc_name: str) -> str | None:
            """Add dep to the correct category bucket, return human name."""
            for db_map, store in [
                (DB_RDBMS, db_rdbms), (DB_CACHE, db_cache),
                (DB_NOSQL, db_nosql), (DB_BROKER, db_broker)
            ]:
                if dep in db_map:
                    name = db_map[dep]
                    if name not in store:
                        store[name] = []
                    if svc_name not in store[name]:
                        store[name].append(svc_name)
                    return name
            return None

        def _infer_role(frameworks: list, deps: list, dev_deps: list, name: str) -> str:
            """Infer what this service actually does."""
            all_d = set(d.lower() for d in deps + dev_deps)
            fw    = set(f.lower() for f in frameworks)
            nm    = name.lower()
            if any(x in fw for x in ["react", "vue", "svelte", "next.js", "angular", "nuxt"]):
                return "Frontend Web App (SPA)"
            if "vite" in all_d and "react" in all_d:
                return "Frontend Web App (React + Vite)"
            if any(x in fw for x in ["express", "fastify", "koa", "hapi.js", "nestjs"]):
                if any(d in all_d for d in ["pg", "mongoose", "mysql2", "sequelize", "prisma", "typeorm"]):
                    return "REST API Server + DB Layer"
                return "REST API Server"
            if "fastapi" in fw: return "Python FastAPI Service"
            if "flask" in fw:   return "Python Flask API"
            if "django" in fw:  return "Django Web Application"
            if any(x in all_d for x in ["bull", "bullmq", "celery", "kafkajs", "amqplib"]):
                return "Background Worker / Message Consumer"
            if any(x in nm for x in ["worker", "job", "queue", "consumer", "cron"]):
                return "Background Worker / Scheduler"
            if any(x in nm for x in ["gateway", "proxy"]):
                return "API Gateway / Reverse Proxy"
            if any(x in nm for x in ["auth", "identity", "login"]):
                return "Authentication Service"
            if any(x in nm for x in ["notification", "email", "sms"]):
                return "Notification Service"
            return "Microservice"

        # ─── Per-service detection ──────────────────────────────────────
        microservice_dirs   = []
        microservice_details = {}

        for root, dirs, files in os.walk(self.project_path):
            dirs[:] = [d for d in dirs if d not in
                       ("node_modules", "venv", ".git", "__pycache__", "dist", "build", ".next")]
            rel_dir  = os.path.relpath(root, self.project_path)
            is_subdir = root != self.project_path

            # ── Node.js service ────────────────────────────────────────
            if "package.json" in files and is_subdir:
                microservice_dirs.append(rel_dir)
                pkg_path = os.path.join(root, "package.json")
                try:
                    data     = json.loads(read_file(pkg_path))
                    deps     = list(data.get("dependencies", {}).keys())
                    dev_deps = list(data.get("devDependencies", {}).keys())
                    all_deps = deps + dev_deps

                    svc_frameworks = []
                    for fw_dep, fw_name in [
                        ("express","Express"), ("fastify","Fastify"), ("koa","Koa"),
                        ("react","React"), ("next","Next.js"), ("vue","Vue"),
                        ("svelte","Svelte"), ("angular","Angular"), ("nuxt","Nuxt"),
                        ("hapi","Hapi.js"), ("@nestjs/core","NestJS"),
                        ("graphql","GraphQL"), ("apollo-server","Apollo Server"),
                    ]:
                        if fw_dep in all_deps: svc_frameworks.append(fw_name)
                    if "vite" in all_deps: svc_frameworks.append("Vite")

                    node_ver = "20"
                    if "engines" in data and "node" in data["engines"]:
                        m = re.search(r'(\d+)', data["engines"]["node"])
                        if m: node_ver = m.group(1)
                    nvmrc = os.path.join(root, ".nvmrc")
                    if os.path.exists(nvmrc):
                        node_ver = read_file(nvmrc).strip().lstrip("v").split(".")[0]

                    is_frontend = any(f in svc_frameworks for f in ["React","Vue","Svelte","Angular","Nuxt"]) or "vite" in all_deps
                    base_image = (f"node:{node_ver}-alpine → nginx:alpine (runtime)"
                                  if is_frontend else f"node:{node_ver}-alpine")

                    svc_ports = []
                    for fname in os.listdir(root):
                        fpath = os.path.join(root, fname)
                        if os.path.isfile(fpath) and fname.endswith((".js",".ts",".mjs",".cjs")):
                            svc_ports.extend(re.findall(r'(?:listen|PORT)\D{0,10}(\d{3,5})', read_file(fpath)))
                    vite_cfg = os.path.join(root, "vite.config.js")
                    if os.path.exists(vite_cfg):
                        svc_ports.extend(re.findall(r'port\s*:\s*(\d+)', read_file(vite_cfg)))
                    if not svc_ports:
                        defaults = {"Express":"3000","Fastify":"3000","NestJS":"3000",
                                    "React":"80","Next.js":"3000","Vue":"80","Vite":"5173"}
                        svc_ports = [defaults.get(svc_frameworks[0], "3000")] if svc_frameworks else ["3000"]

                    svc_dbs = []
                    for dep in deps:
                        name = _register_db(dep, rel_dir)
                        if name and name not in svc_dbs:
                            svc_dbs.append(name)

                    microservice_details[rel_dir] = {
                        "language": "Node.js", "frameworks": svc_frameworks,
                        "runtime_version": node_ver, "base_image": base_image,
                        "ports": list(dict.fromkeys(svc_ports)),
                        "key_deps": deps[:6], "role": _infer_role(svc_frameworks, deps, dev_deps, os.path.basename(root)),
                        "databases": svc_dbs,
                    }
                except Exception:
                    microservice_details[rel_dir] = {
                        "language": "Node.js", "frameworks": [], "ports": ["3000"],
                        "base_image": "node:20-alpine", "runtime_version": "20",
                        "role": "Microservice", "databases": [],
                    }

            # ── Python service ─────────────────────────────────────────
            elif "requirements.txt" in files and is_subdir:
                microservice_dirs.append(rel_dir)
                req_path = os.path.join(root, "requirements.txt")
                try:
                    content = read_file(req_path)
                    deps = [l.split("==")[0].split(">=")[0].split("~=")[0].strip().lower()
                            for l in content.splitlines() if l.strip() and not l.startswith("#")]

                    svc_frameworks = []
                    for fw_dep, fw_name in [
                        ("flask","Flask"), ("django","Django"), ("fastapi","FastAPI"),
                        ("tornado","Tornado"), ("aiohttp","aiohttp"), ("sanic","Sanic"),
                        ("starlette","Starlette"), ("uvicorn","Uvicorn"),
                    ]:
                        if fw_dep in deps: svc_frameworks.append(fw_name)

                    py_ver = "3.11"
                    pv = os.path.join(root, ".python-version")
                    if os.path.exists(pv): py_ver = read_file(pv).strip()

                    svc_dbs = []
                    for dep in deps:
                        name = _register_db(dep, rel_dir)
                        if name and name not in svc_dbs:
                            svc_dbs.append(name)

                    microservice_details[rel_dir] = {
                        "language": "Python", "frameworks": svc_frameworks,
                        "runtime_version": py_ver, "base_image": f"python:{py_ver}-slim",
                        "ports": ["8000"], "key_deps": deps[:6],
                        "role": _infer_role(svc_frameworks, deps, [], os.path.basename(root)),
                        "databases": svc_dbs,
                    }
                except Exception:
                    microservice_details[rel_dir] = {
                        "language": "Python", "frameworks": [], "ports": ["8000"],
                        "base_image": "python:3.11-slim", "runtime_version": "3.11",
                        "role": "Microservice", "databases": [],
                    }

            # ── Java/Spring Boot service ─────────────────────────────
            elif "pom.xml" in files and is_subdir:
                # Ensure it's a leaf service (contains src/main)
                if os.path.isdir(os.path.join(root, "src", "main")):
                    microservice_dirs.append(rel_dir)
                    try:
                        svc_ports = ["8080"]
                        svc_dbs = []
                        
                        # Scan common resources for port/DB
                        res_path = os.path.join(root, "src", "main", "resources")
                        if os.path.isdir(res_path):
                            for r_file in os.listdir(res_path):
                                if r_file.endswith((".properties", ".yml", ".yaml")):
                                    r_content = read_file(os.path.join(res_path, r_file))
                                    # Extract port
                                    p_match = re.search(r'(?:server\.port|port)\s*[:=]\s*(\d+)', r_content)
                                    if p_match: svc_ports = [p_match.group(1)]
                                    
                                    # Extract DB hints
                                    r_lower = r_content.lower()
                                    if "jdbc:postgresql" in r_lower: svc_dbs.append("PostgreSQL")
                                    if "jdbc:mysql" in r_lower: svc_dbs.append("MySQL")
                                    if "redis" in r_lower: svc_dbs.append("Redis")
                        
                        # Infer role
                        role = _infer_role(["Spring Boot"], [], [], os.path.basename(root))
                        if "gateway" in rel_dir.lower(): role = "API Gateway"
                        elif "auth" in rel_dir.lower(): role = "Authentication Service"
                        
                        microservice_details[rel_dir] = {
                            "language": "Java",
                            "frameworks": ["Spring Boot"],
                            "runtime_version": "21", # Semantic field for runtime version
                            "base_image": "maven:3.9-eclipse-temurin-21 → eclipse-temurin:21-jre-alpine",
                            "ports": svc_ports,
                            "key_deps": ["spring-boot-starter-web"],
                            "role": role,
                            "databases": svc_dbs,
                        }
                    except Exception:
                        microservice_details[rel_dir] = {
                            "language": "Java", "frameworks": ["Spring Boot"], "ports": ["8080"],
                            "base_image": "maven-openjdk", "runtime_version": "17",
                            "role": "Spring Boot Service", "databases": []
                        }

        if microservice_dirs:
            arch.add("microservices")
            analysis["microservice_dirs"]    = microservice_dirs
            analysis["microservice_details"] = microservice_details
        else:
            arch.add("monolith")

        # ─── Final categorized DB dict with service annotations ────────
        analysis["databases"] = {
            "rdbms":  db_rdbms,
            "cache":  db_cache,
            "nosql":  db_nosql,
            "broker": db_broker,
        }
        # Legacy fallback
        if not db_rdbms and "postgres" in str(analysis.get("architecture", [])):
            analysis["databases"]["rdbms"]["PostgreSQL"] = []

        # ─── Cloud SDKs ────────────────────────────────────────────────
        deps_all = analysis.get("dependencies", [])
        if any(d.startswith("aws-sdk") or d == "boto3" for d in deps_all): arch.add("aws")
        if any("google-cloud" in d for d in deps_all): arch.add("gcp")
        if "azure" in str(deps_all): arch.add("azure")

        analysis["architecture"] = list(arch)

    def _verify_db_detection(self, analysis: dict):
        """
        Deep scan for database hints in SQL files, properties, and specific drivers.
        """
        db_hints = {
            "rdbms": set(),
            "cache": set(),
            "nosql": set()
        }
        
        # 1. Scan for config/sql files
        for root, _, files in os.walk(self.project_path):
            for file in files:
                fpath = os.path.join(root, file)
                content = ""
                
                # Check .sql files
                if file.endswith(".sql"):
                    content = read_file(fpath).lower()
                    if "postgresql" in content or "pg_" in content: db_hints["rdbms"].add("PostgreSQL")
                    if "mysql" in content: db_hints["rdbms"].add("MySQL")
                
                # Check application.properties / .env
                if file in ["application.properties", ".env", "config.yaml", "config.yml"]:
                    content = read_file(fpath).lower()
                    if "jdbc:postgresql" in content: db_hints["rdbms"].add("PostgreSQL")
                    if "jdbc:mysql" in content: db_hints["rdbms"].add("MySQL")
                    if "redis_url" in content or "redis.host" in content: db_hints["cache"].add("Redis")
                    if "mongodb_uri" in content: db_hints["nosql"].add("MongoDB")

        # 2. Merge hints into existing analysis
        for cat in ["rdbms", "cache", "nosql"]:
            for db in db_hints[cat]:
                if db not in analysis["databases"][cat]:
                    analysis["databases"][cat][db] = ["detected_via_file_scan"]
                    logger.info(f"🔍 Discovery: Found {db} via file content scan.")

    def _save_cache(self, context: ProjectContext):
        write_file(self.cache_file, context.model_dump_json(indent=2))

    def get_cached_analysis(self) -> ProjectContext:
        """Reads from cache if exists, otherwise analyzes"""
        if os.path.exists(self.cache_file):
            print(f"⚡ Loading cached analysis from {self.cache_file}")
            try:
                content = read_file(self.cache_file)
                return ProjectContext.model_validate_json(content)
            except Exception:
                print("⚠️  Cache invalid, re-analyzing...")
                return self.analyze()
        return self.analyze()
