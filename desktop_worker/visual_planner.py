"""Safe visual planning primitives for Ash's Visio-inspired diagram ability.

Generates Mermaid source, not a rendering or a remote image. View in a
Mermaid-compatible editor; no shell, browser, or network actions.
"""
from __future__ import annotations
import re
from typing import Any

NODE_LABEL_LIMIT=80
MAX_NODES=18
MAX_EDGES=30

def flow_diagram(title: str, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]):
    if not isinstance(nodes, list) or not (1<=len(nodes)<=MAX_NODES):
        raise ValueError("Provide 1-18 diagram nodes")
    if not isinstance(edges, list) or len(edges)>MAX_EDGES:
        raise ValueError("Too many diagram connections")
    seen=set()
    out=["flowchart TD"]
    for node in nodes:
        if not isinstance(node,dict):
            raise ValueError("Every diagram node must be an object")
        nid=str(node.get("id") or "")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,19}",nid) or nid in seen:
            raise ValueError("Diagram node IDs must be unique plain identifiers")
        seen.add(nid)
        label=str(node.get("label") or "").strip()
        if not label or len(label)>NODE_LABEL_LIMIT:
            raise ValueError("Diagram labels must be present and short")
        # Escape Mermaid's quote syntax and remove control characters/brackets.
        label=re.sub(r"[\r\n\t\[\]{}<>]", " ",label).replace('"',"'")
        out.append(f'    {nid}["{label}"]')
    for edge in edges:
        if not isinstance(edge,dict):
            raise ValueError("Every connection must be an object")
        a,b=str(edge.get("from") or ""),str(edge.get("to") or "")
        if a not in seen or b not in seen:
            raise ValueError("Connections must point to known diagram nodes")
        out.append(f"    {a} --> {b}")
    name=str(title or "Process diagram").strip()[:100]
    return {"title":name,"format":"mermaid","diagram":"\n".join(out),
            "rendered":False,"node_count":len(nodes),"edge_count":len(edges)}
