import json
import os
from collections import defaultdict
import networkx as nx

INPUT = "data/projects.json"
OUTPUT = "web/public/data/graph.json"

def main():
    print("🔗 Generating contributor graph...")
    
    with open(INPUT, "r") as f:
        payload = json.load(f)

    projects = payload.get("projects", [])

    # bipartite: contributor nodes + project nodes
    G = nx.Graph()

    # keep only GitHub items (HF lacks reliable contributor graph)
    gh_items = [p for p in projects if p.get("source") == "github" and p.get("contributors")]
    
    print(f"   Processing {len(gh_items)} GitHub projects with contributors...")

    # Build edges: contributor -> project
    for proj in gh_items:
        proj_id = f"proj:{proj['full_name']}"
        G.add_node(
            proj_id, 
            kind="project", 
            label=proj["name"],
            full_name=proj["full_name"],
            url=proj["url"], 
            score=proj.get("score", 0),
            topics=proj.get("topics", []),
            use_cases=proj.get("use_cases", []),
            stars=proj.get("stars", 0)
        )
        
        for contributor in proj.get("contributors", []):
            person_login = contributor.get("login")
            if not person_login:
                continue
                
            person_id = f"person:{person_login}"
            if not G.has_node(person_id):
                G.add_node(
                    person_id, 
                    kind="person", 
                    label=person_login,
                    url=contributor.get("url", f"https://github.com/{person_login}"),
                    avatar_url=contributor.get("avatar_url", "")
                )
            
            # Edge weight based on contributions and project score
            weight = contributor.get("contributions", 1) * (1 + proj.get("score", 0) / 100)
            G.add_edge(person_id, proj_id, weight=weight, contributions=contributor.get("contributions", 0))

    # Calculate person stats
    person_stats = defaultdict(lambda: {"project_count": 0, "total_score": 0, "total_contributions": 0})
    for node_id, node_data in G.nodes(data=True):
        if node_data.get("kind") == "person":
            neighbors = list(G.neighbors(node_id))
            project_neighbors = [n for n in neighbors if G.nodes[n].get("kind") == "project"]
            
            total_score = sum(G.nodes[n].get("score", 0) for n in project_neighbors)
            total_contribs = sum(G.edges[node_id, n].get("contributions", 0) for n in project_neighbors)
            
            person_stats[node_id] = {
                "project_count": len(project_neighbors),
                "total_score": total_score,
                "total_contributions": total_contribs
            }

    # Make it render-friendly
    nodes = []
    for n, attrs in G.nodes(data=True):
        node_obj = {
            "id": n,
            "kind": attrs.get("kind"),
            "label": attrs.get("label"),
            "url": attrs.get("url"),
        }
        
        if attrs.get("kind") == "project":
            node_obj.update({
                "full_name": attrs.get("full_name"),
                "score": attrs.get("score", 0),
                "topics": attrs.get("topics", []),
                "use_cases": attrs.get("use_cases", []),
                "stars": attrs.get("stars", 0)
            })
        elif attrs.get("kind") == "person":
            node_obj.update({
                "avatar_url": attrs.get("avatar_url", ""),
                "project_count": person_stats[n]["project_count"],
                "total_score": person_stats[n]["total_score"],
                "total_contributions": person_stats[n]["total_contributions"]
            })
        
        nodes.append(node_obj)

    links = []
    for a, b, attrs in G.edges(data=True):
        links.append({
            "source": a,
            "target": b,
            "weight": attrs.get("weight", 1),
            "contributions": attrs.get("contributions", 0)
        })

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump({
            "node_count": len(nodes),
            "link_count": len(links),
            "person_count": len([n for n in nodes if n["kind"] == "person"]),
            "project_count": len([n for n in nodes if n["kind"] == "project"]),
            "nodes": nodes,
            "links": links
        }, f, indent=2)

    print(f"✓ Wrote {OUTPUT}")
    print(f"   {len([n for n in nodes if n['kind'] == 'person'])} contributors")
    print(f"   {len([n for n in nodes if n['kind'] == 'project'])} projects")
    print(f"   {len(links)} connections")

if __name__ == "__main__":
    main()

