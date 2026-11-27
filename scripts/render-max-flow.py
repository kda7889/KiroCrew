"""Render the descriptive MAX BPMN DI to SVG; stdout only, no dependencies.

Run: python3 scripts/render-max-flow.py > docs/architecture/max-owner.svg
This is a small DI renderer, not a BPMN execution engine.
"""

import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path

NS = {
    "b": "http://www.omg.org/spec/BPMN/20100524/MODEL",
    "d": "http://www.omg.org/spec/BPMN/20100524/DI",
    "c": "http://www.omg.org/spec/DD/20100524/DC",
    "i": "http://www.omg.org/spec/DD/20100524/DI",
}


def render(path):
    root = ET.parse(path).getroot()
    elements = {e.attrib["id"]: e for e in root.iter() if "id" in e.attrib}
    shapes = root.findall(".//d:BPMNShape", NS)
    edges = root.findall(".//d:BPMNEdge", NS)
    assert root.find("b:process", NS).get("isExecutable") == "false"
    shape_ids = {s.get("bpmnElement") for s in shapes}
    for edge in edges:
        flow = elements[edge.get("bpmnElement")]
        assert flow.get("sourceRef") in shape_ids and flow.get("targetRef") in shape_ids
        assert len(edge.findall("i:waypoint", NS)) >= 2
    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 445" role="img" aria-label="MAX owner pairing, descriptive BPMN">',
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0 0L7 3L0 6Z" fill="#334155"/></marker></defs>',
        '<rect width="1280" height="445" fill="white"/><g font-family="sans-serif" font-size="13" stroke="#334155" fill="#172554">',
    ]
    for shape in shapes:
        element = elements[shape.get("bpmnElement")]
        kind = element.tag.rsplit("}", 1)[1]
        bounds = shape.find("c:Bounds", NS)
        x, y, w, h = [float(bounds.get(k)) for k in ("x", "y", "width", "height")]
        assert w > 0 and h > 0
        cx, cy = x + w / 2, y + h / 2
        name = escape(element.get("name", ""))
        if kind == "lane":
            svg.append(
                f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#f8fafc"/><text x="{x + 8}" y="{y + 16}" stroke="none">{name}</text>'
            )
        elif kind.endswith("Event"):
            weight = 3 if kind == "endEvent" else 1
            svg.append(
                f'<circle cx="{cx}" cy="{cy}" r="{w / 2}" fill="white" stroke-width="{weight}"/><text x="{cx}" y="{y + h + 17}" text-anchor="middle" stroke="none">{name}</text>'
            )
        elif kind == "exclusiveGateway":
            svg.append(
                f'<polygon points="{cx},{y} {x + w},{cy} {cx},{y + h} {x},{cy}" fill="white"/><text x="{cx}" y="{y - 9}" text-anchor="middle" stroke="none">{name}</text><text x="{cx}" y="{cy + 5}" text-anchor="middle" stroke="none">×</text>'
            )
        else:
            svg.append(
                f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="white"/><text x="{cx}" y="{cy + 5}" text-anchor="middle" stroke="none">{name}</text>'
            )
    for edge in edges:
        points = [(p.get("x"), p.get("y")) for p in edge.findall("i:waypoint", NS)]
        pairs = " ".join(f"{x},{y}" for x, y in points)
        svg.append(f'<polyline points="{pairs}" fill="none" marker-end="url(#arrow)"/>')
        name = escape(elements[edge.get("bpmnElement")].get("name", ""))
        if name:
            x, y = map(float, points[0])
            svg.append(f'<text x="{x + 4}" y="{y + 16}" stroke="none">{name}</text>')
    return "\n".join(svg + ["</g></svg>"]) + "\n"


if __name__ == "__main__":
    print(
        render(Path(__file__).resolve().parents[1] / "docs/architecture/max-owner.bpmn"),
        end="",
    )
