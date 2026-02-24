from src.agents.code_analysis_agent import CodeAnalysisAgent
from src.schemas import ProjectContext
import os

def load_or_run_analysis(project_path: str) -> ProjectContext:
    agent = CodeAnalysisAgent(project_path)
    context = agent.get_cached_analysis()
    
    # Print rich analysis summary
    is_mono = "microservices" not in context.architecture
    num_dockerfiles = len(context.microservice_dirs) if not is_mono else 1

    dbs = context.databases if context.databases else {}
    def _norm(d):
        if isinstance(d, list): return {k: [] for k in d}
        if isinstance(d, dict): return d
        return {}
        
    rdbms_dict  = _norm(dbs.get("rdbms", {}))
    cache_dict  = _norm(dbs.get("cache", {}))
    nosql_dict  = _norm(dbs.get("nosql", {}))
    broker_dict = _norm(dbs.get("broker", {}))

    if not rdbms_dict and "postgres" in context.architecture: rdbms_dict = {"PostgreSQL": []}
    if not cache_dict  and "redis"    in context.architecture: cache_dict  = {"Redis": []}

    svc_index = {svc: f"#{i+1}" for i, svc in enumerate(context.microservice_dirs)}

    all_ports = []
    for svc in context.microservice_dirs:
        for p in context.microservice_details.get(svc, {}).get("ports", []):
            if p not in all_ports:
                all_ports.append(p)

    def _db_tag(svcs: list) -> str:
        if not svcs: return ""
        parts = [f"{svc_index.get(s, s)} {s}" for s in svcs]
        return f"  ← {', '.join(parts)}"

    W = 64
    print("\n" + "=" * W)
    print("  📋  CODE ANALYSIS SUMMARY")
    print("=" * W)
    print(f"  📁  Project       : {context.project_name}")
    print(f"  🏛️   Architecture  : {'Microservices' if not is_mono else 'Monolith'}")
    print(f"  🐳  Dockerfiles   : {num_dockerfiles} file(s) will be generated")
    if all_ports:
        chain = "  →  ".join(f":{p}" for p in all_ports)
        print(f"  🔌  Port chain    : {chain}")
    print()

    if not is_mono and context.microservice_dirs:
        print("  ── MICROSERVICES " + "─" * (W - 18))
        for idx, svc in enumerate(context.microservice_dirs, start=1):
            detail     = context.microservice_details.get(svc, {})
            lang       = detail.get("language", "Node.js")
            frameworks = detail.get("frameworks", [])
            version    = detail.get("runtime_version", "?")
            base_img   = detail.get("base_image", "node:20-alpine")
            ports      = detail.get("ports", [])
            key_deps   = detail.get("key_deps", [])
            role       = detail.get("role", "Microservice")
            svc_dbs    = detail.get("databases", [])

            fw_str     = f" · {', '.join(frameworks)}" if frameworks else ""
            port_chain = "  →  ".join([f":{p}" for p in ports]) if ports else "auto"

            print(f"  #{idx}  {svc}/  —  {role}")
            print(f"       Language    : {lang}{fw_str}")
            print(f"       Runtime     : {lang} {version}")
            print(f"       Base image  : {base_img}")
            print(f"       Port chain  : {port_chain}")
            if key_deps:
                print(f"       Key deps    : {', '.join(key_deps)}")
            if svc_dbs:
                print(f"       Uses DBs    : {', '.join(svc_dbs)}")
            print()

    has_db = rdbms_dict or cache_dict or nosql_dict or broker_dict
    if has_db:
        print("  ── DATABASES " + "─" * (W - 14))
        for db_name, svcs in rdbms_dict.items():
            print(f"  🗄️   RDBMS   {db_name:<22}{_db_tag(svcs)}")
        for db_name, svcs in cache_dict.items():
            print(f"  ⚡  Cache   {db_name:<22}{_db_tag(svcs)}")
        for db_name, svcs in nosql_dict.items():
            print(f"  🍃  NoSQL   {db_name:<22}{_db_tag(svcs)}")
        for db_name, svcs in broker_dict.items():
            print(f"  📨  Broker  {db_name:<22}{_db_tag(svcs)}")
        print()

    print("=" * W + "\n")
    return context
