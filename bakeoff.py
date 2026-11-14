# ai-generated: 90% - implementation of SARIF confusion matrix matching according to CI-SPEC P-14..P-22
"""bakeoff.py - scanner SARIF + a labels file -> a per-tool confusion matrix (CI-SPEC.md P-23).

This script turns scanner SARIF documents and a labels file into a per-tool confusion matrix.
Standard library only - runs as `python3 -S -E bakeoff.py`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from typing import Any

TABLE_CLASSES = {
    "secret",
    "injection",
    "deserialization",
    "weak-crypto",
    "insecure-transport",
    "path-traversal",
    "ssrf",
    "vulnerable-dependency",
    "misconfiguration",
    "access-control",
}

CWE_TABLE: dict[str, set[int]] = {
    "secret": {259, 260, 321, 798},
    "injection": {74, 77, 78, 79, 80, 88, 89, 90, 91, 94, 95, 96, 611, 776, 917, 943, 1336},
    "deserialization": {502},
    "weak-crypto": {261, 326, 327, 328, 330, 331, 338, 759, 760, 916},
    "insecure-transport": {295, 297, 319, 322, 757},
    "path-traversal": {22, 23, 35, 36, 73},
    "ssrf": {918},
    "vulnerable-dependency": {937, 1035, 1104, 1395},
    "misconfiguration": {16, 215, 250, 489, 668, 732, 1188},
    "access-control": {284, 285, 639, 862, 863},
}

KNOWN_TOOLS = {"trivy", "grype", "osv-scanner", "gitleaks"}
SEMGREP_NAMES = {"semgrep", "semgrep oss", "semgrep ce", "semgrep community edition", "semgrep pro"}


def get_tool_id(driver: Any) -> str:
    """Derive tool id according to P-15."""
    if not isinstance(driver, dict):
        return "unknown"
    raw_name = driver.get("name")
    if not isinstance(raw_name, str):
        return "unknown"
    name_strip = raw_name.strip()
    if not name_strip:
        return "unknown"
    name_lower = name_strip.lower()
    if name_lower in KNOWN_TOOLS:
        return name_lower
    if name_lower in SEMGREP_NAMES:
        return "semgrep"
    cleaned = re.sub(r"[^a-z0-9]+", "-", name_lower).strip("-")
    return cleaned if cleaned else "unknown"


def normalize_pep503(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def extract_pep503_tokens(text: str) -> list[str]:
    raw_tokens = re.findall(r"[A-Za-z0-9._-]+", text)
    tokens = []
    for tok in raw_tokens:
        clean = tok.strip("._-")
        if clean:
            tokens.append(normalize_pep503(clean))
    return tokens


def parse_path(uri: str, set_root: str) -> str | None:
    """Parse URI according to P-17. Returns file path if in set, else None."""
    decoded = urllib.parse.unquote(uri)
    if decoded.lower().startswith("file://"):
        decoded = decoded[7:]
    if decoded.startswith("./"):
        decoded = decoded[2:]
    parts = decoded.split("/")
    if set_root not in parts:
        return None
    last_idx = len(parts) - 1 - parts[::-1].index(set_root)
    return "/".join(parts[last_idx:])


def extract_classes(result: dict, tool_id: str, rule: dict | None) -> set[str]:
    """Extract result classes according to P-19."""
    props = result.get("properties")
    if isinstance(props, dict):
        cls_prop = props.get("class")
        if isinstance(cls_prop, str) and cls_prop in TABLE_CLASSES:
            return {cls_prop}

    # (b) by tool
    if tool_id == "gitleaks":
        return {"secret"}
    if tool_id in ("grype", "osv-scanner"):
        return {"vulnerable-dependency"}
    if tool_id == "trivy":
        rule_props = rule.get("properties") if isinstance(rule, dict) else None
        rule_tags = rule_props.get("tags") if isinstance(rule_props, dict) else None
        if isinstance(rule_tags, list):
            trivy_classes = set()
            for tag in rule_tags:
                if isinstance(tag, str):
                    t_low = tag.lower()
                    if t_low == "vulnerability":
                        trivy_classes.add("vulnerable-dependency")
                    elif t_low == "secret":
                        trivy_classes.add("secret")
                    elif t_low == "misconfiguration":
                        trivy_classes.add("misconfiguration")
            if trivy_classes:
                return trivy_classes

    # (c) CWE in tags of result or rule
    all_tags = []
    if isinstance(props, dict) and isinstance(props.get("tags"), list):
        all_tags.extend([t for t in props["tags"] if isinstance(t, str)])
    rule_props = rule.get("properties") if isinstance(rule, dict) else None
    if isinstance(rule_props, dict) and isinstance(rule_props.get("tags"), list):
        all_tags.extend([t for t in rule_props["tags"] if isinstance(t, str)])

    cwe_classes = set()
    for tag in all_tags:
        for m in re.finditer(r"(?<![A-Za-z0-9])cwe-(\d+)", tag, re.IGNORECASE):
            cwe_num = int(m.group(1))
            for cls_name, cwe_set in CWE_TABLE.items():
                if cwe_num in cwe_set:
                    cwe_classes.add(cls_name)
    if cwe_classes:
        return cwe_classes

    # (d) otherwise other
    return {"other"}


def match_result_to_defect(res: dict, defect: dict) -> bool:
    """Check if result matches defect according to P-20."""
    if res["file"] != defect["file"]:
        return False
    if defect["class"] not in res["classes"]:
        return False

    if defect["class"] == "vulnerable-dependency":
        norm_pkg = normalize_pep503(defect["package"])
        msg = res["raw"].get("message")
        if not isinstance(msg, dict):
            return False
        text = msg.get("text")
        if not isinstance(text, str):
            return False
        tokens = extract_pep503_tokens(text)
        return norm_pkg in tokens
    else:
        if res["start_line"] is None:
            return False
        return (res["start_line"] <= defect["end_line"]) and (defect["start_line"] <= res["end_line"])


def confusion_matrix(labels: dict, sarif_documents: list[dict]) -> dict:
    """The matrix of P-21 and P-22 for the labels (P-14) and the parsed SARIF documents."""
    set_root = labels["set"]
    defects = labels.get("defects") or []
    defects_by_id = {d["id"]: d for d in defects if isinstance(d, dict) and "id" in d}

    # Map tool_id -> list of results in set
    tool_results: dict[str, list[dict]] = {}

    for doc in sarif_documents:
        if not isinstance(doc, dict):
            continue
        runs = doc.get("runs")
        if not isinstance(runs, list):
            continue

        for run in runs:
            if not isinstance(run, dict):
                continue
            driver = run.get("tool", {}).get("driver", {}) if isinstance(run.get("tool"), dict) else None
            tool_id = get_tool_id(driver)
            if tool_id not in tool_results:
                tool_results[tool_id] = []

            # Index rules
            rules_map: dict[str, dict] = {}
            if isinstance(driver, dict):
                rules_list = driver.get("rules")
                if isinstance(rules_list, list):
                    for r in rules_list:
                        if isinstance(r, dict):
                            rid = r.get("id")
                            if isinstance(rid, str) and rid not in rules_map:
                                rules_map[rid] = r

            results = run.get("results")
            if not isinstance(results, list):
                continue

            for res in results:
                if not isinstance(res, dict):
                    continue

                # P-16: kind
                kind = res.get("kind")
                if kind is not None and kind != "fail":
                    continue

                # P-16: suppressions
                supp = res.get("suppressions")
                if supp is not None and supp not in ([], {}, False, 0, ""):
                    continue

                # P-16: location
                locations = res.get("locations")
                if not isinstance(locations, list) or not locations:
                    continue
                first_loc = locations[0]
                if not isinstance(first_loc, dict):
                    continue
                phys_loc = first_loc.get("physicalLocation")
                if not isinstance(phys_loc, dict):
                    continue
                art_loc = phys_loc.get("artifactLocation")
                if not isinstance(art_loc, dict):
                    continue
                uri = art_loc.get("uri")
                if not isinstance(uri, str) or not uri:
                    continue

                # P-17: path and scope
                file_path = parse_path(uri, set_root)
                if file_path is None:
                    continue

                # P-18: lines
                start_line = None
                end_line = None
                region = phys_loc.get("region")
                if isinstance(region, dict):
                    sl = region.get("startLine")
                    if type(sl) is int and sl >= 1 and not isinstance(sl, bool):
                        start_line = sl
                        el = region.get("endLine")
                        if type(el) is int and el >= sl and not isinstance(el, bool):
                            end_line = el
                        else:
                            end_line = sl

                # Rule & classes
                rule_id = res.get("ruleId")
                rule = rules_map.get(rule_id) if isinstance(rule_id, str) else None
                classes = extract_classes(res, tool_id, rule)

                tool_results[tool_id].append({
                    "raw": res,
                    "file": file_path,
                    "start_line": start_line,
                    "end_line": end_line,
                    "ruleId": rule_id if isinstance(rule_id, str) else None,
                    "classes": classes,
                })

    tools_out: dict[str, dict] = {}
    for tool_id in sorted(tool_results.keys()):
        results_in_set = tool_results[tool_id]
        matched_defects: set[str] = set()
        unmatched_results: list[dict] = []

        for res in results_in_set:
            res_matched = False
            for did, d in defects_by_id.items():
                if match_result_to_defect(res, d):
                    matched_defects.add(did)
                    res_matched = True
            if not res_matched:
                unmatched_results.append(res)

        tp = len(matched_defects)
        fn = len(defects_by_id) - tp

        # FP: distinct (ruleId, file, start_line, end_line) among unmatched results
        distinct_fps = set()
        for res in unmatched_results:
            key = (res["ruleId"], res["file"], res["start_line"], res["end_line"])
            distinct_fps.add(key)
        fp = len(distinct_fps)

        # Scores
        precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else None
        recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else None
        f1 = round(2 * tp / (2 * tp + fp + fn), 4) if (2 * tp + fp + fn) > 0 else None

        tools_out[tool_id] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }

    return {"set": set_root, "defects": len(defects), "tools": tools_out}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="per-tool confusion matrix of SARIF against labels (CI-SPEC.md P-23)")
    parser.add_argument("--labels", required=True, help="the labels file (P-14)")
    parser.add_argument("sarif", nargs="+", help="SARIF 2.1.0 files")
    args = parser.parse_args(argv)
    with open(args.labels, encoding="utf-8") as fh:
        labels = json.load(fh)
    documents = []
    for path in args.sarif:
        with open(path, encoding="utf-8") as fh:
            documents.append(json.load(fh))
    json.dump(confusion_matrix(labels, documents), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
