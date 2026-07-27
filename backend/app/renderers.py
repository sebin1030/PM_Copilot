def prd_to_markdown(prd: dict) -> str:
    lines = [f"# {prd['title']}", "", prd["summary"], "", "## 문제 정의", "", prd["problem"], ""]

    sections = [
        ("목표 사용자", prd["targetUsers"]),
        ("목표", prd["goals"]),
        ("성공 지표", prd["successMetrics"]),
        ("범위 제외", prd["outOfScope"]),
        ("가정", prd["assumptions"]),
        ("추가 확인 사항", prd["questions"]),
    ]
    for title, items in sections:
        lines.extend([f"## {title}", ""])
        lines.extend([f"- {item}" for item in items] or ["- 없음"])
        lines.append("")

    lines.extend(["## 핵심 기능", ""])
    for feature in prd["features"]:
        lines.extend([f"### {feature['id']} · {feature['name']} ({feature['priority']})", "", feature["description"], ""])

    lines.extend(["## 요구사항", ""])
    for requirement in prd["requirements"]:
        lines.extend([f"### {requirement['id']} · {requirement['title']}", "", requirement["description"], ""])
        lines.extend([f"- {item}" for item in requirement["acceptanceCriteria"]])
        lines.append("")
    return "\n".join(lines)

