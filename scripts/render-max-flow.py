"""Render descriptive MAX BPMN DI to SVG; stdout only, no dependencies.

Run: python3 scripts/render-max-flow.py > docs/architecture/max-owner.svg
This renders every diagram; it is not a BPMN execution engine.
"""

import textwrap
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
    assert all(p.get("isExecutable") == "false" for p in root.findall("b:process", NS))
    parts, width, offset = [], 0, 45
    for plane in root.findall("d:BPMNDiagram/d:BPMNPlane", NS):
        shapes = plane.findall("d:BPMNShape", NS)
        edges = plane.findall("d:BPMNEdge", NS)
        shape_ids = {s.get("bpmnElement") for s in shapes}
        title = escape(elements[plane.get("bpmnElement")].get("name", "MAX"))
        parts.append(f'<text x="20" y="{offset - 12}" font-size="20">{title}</text>')
        parts.append(f'<g transform="translate(0 {offset})">')
        bottom = 0.0
        for shape in shapes:
            b = shape.find("c:Bounds", NS)
            x, y, w, h = [float(b.get(k)) for k in ("x", "y", "width", "height")]
            assert w > 0 and h > 0
            width, bottom = max(width, x + w + 80), max(bottom, y + h + 55)
            e = elements[shape.get("bpmnElement")]
            if e.tag.endswith("}lane"):
                parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#f8fafc"/>')
                parts.append(f'<text x="{x + 8}" y="{y + 18}">{escape(e.get("name", ""))}</text>')
        for edge in edges:
            flow = elements[edge.get("bpmnElement")]
            assert flow.get("sourceRef") in shape_ids and flow.get("targetRef") in shape_ids
            points = [
                (float(p.get("x")), float(p.get("y"))) for p in edge.findall("i:waypoint", NS)
            ]
            assert len(points) >= 2
            width = max(width, max(x for x, _ in points) + 80)
            bottom = max(bottom, max(y for _, y in points) + 55)
            pairs = " ".join(f"{x},{y}" for x, y in points)
            parts.append(f'<polyline points="{pairs}" fill="none" marker-end="url(#arrow)"/>')
            name = flow.get("name", "")
            if name:
                b = edge.find("d:BPMNLabel/c:Bounds", NS)
                x, y = (float(b.get("x")), float(b.get("y"))) if b is not None else points[0]
                parts.append(f'<text x="{x + 4}" y="{y + 14}">{escape(name)}</text>')
        for shape in shapes:
            e = elements[shape.get("bpmnElement")]
            kind = e.tag.rsplit("}", 1)[1]
            if kind == "lane":
                continue
            b = shape.find("c:Bounds", NS)
            x, y, w, h = [float(b.get(k)) for k in ("x", "y", "width", "height")]
            cx, cy = x + w / 2, y + h / 2
            name = e.get("name", "")
            if kind.endswith("Event"):
                weight = 3 if kind == "endEvent" else 1
                parts.append(
                    f'<circle cx="{cx}" cy="{cy}" r="{w / 2}" fill="white" stroke-width="{weight}"/>'
                )
                if kind == "boundaryEvent":
                    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{w / 2 - 4}" fill="none"/>')
                ty = y + h + 17
            elif kind == "exclusiveGateway":
                parts.append(
                    f'<polygon points="{cx},{y} {x + w},{cy} {cx},{y + h} {x},{cy}" fill="white"/>'
                )
                ty = y - 12
            else:
                parts.append(
                    f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="white"/>'
                )
                ty = cy - 6
            for index, line in enumerate(textwrap.wrap(name, width=25)):
                parts.append(
                    f'<text x="{cx}" y="{ty + index * 16}" text-anchor="middle">{escape(line)}</text>'
                )
        parts.append("</g>")
        offset += bottom + 50
    header = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {offset}" role="img" aria-label="MAX owner pairing and conversation workflow, descriptive BPMN">'
    style = "<style>text{stroke:none;fill:#172554}polyline,rect,circle,polygon{stroke:#334155;stroke-width:1.5}</style>"
    defs = '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0 0L7 3L0 6Z" fill="#334155"/></marker></defs>'
    return (
        "\n".join(
            [
                header,
                style,
                defs,
                '<rect width="100%" height="100%" fill="white"/>',
                '<g font-family="sans-serif" font-size="13">',
                *parts,
                "</g></svg>",
            ]
        )
        + "\n"
    )


if __name__ == "__main__":
    print(render(Path(__file__).resolve().parents[1] / "docs/architecture/max-owner.bpmn"), end="")
