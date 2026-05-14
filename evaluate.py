#!/usr/bin/env python3
import os; os.environ.setdefault("PYTHONIOENCODING", "utf-8")
"""
Evaluation harness for PDF-to-DITA conversion pipeline.

Compares generated DITA output against ground-truth reference output
across seven metrics:

1. Topic classification accuracy (concept/task/reference)
2. XML well-formedness (lxml parse)
3. @class attribute coverage
4. Structural F1 (tree matching)
5. Semantic element richness (UI/PR domain elements)
6. Content faithfulness (word-level F1)
7. Ditamap correctness

Usage:
    python evaluate.py --expected sample_expected/ --actual test_output/
    python evaluate.py --actual test_output/   # XML-only checks if no reference
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from lxml import etree


# ── Helpers ──────────────────────────────────────────────────────────────────

def parse_dita(filepath: str):
    """Parse DITA/XML file, stripping DOCTYPE (no local DTD)."""
    content = Path(filepath).read_text(encoding="utf-8")
    clean = re.sub(r"<!DOCTYPE[^>]+>", "", content)
    return etree.fromstring(clean.encode("utf-8"))


def count_elements(root) -> Counter:
    counts = Counter()
    for elem in root.iter():
        counts[elem.tag] += 1
        cls = elem.get("class", "")
        for domain in ["ui-d", "pr-d", "hi-d", "sw-d"]:
            if f"{domain}/" in cls:
                m = re.search(rf"{domain}/(\w+)", cls)
                if m:
                    counts[f"{domain}:{m.group(1)}"] += 1
    return counts


def tree_signature(root, depth=0) -> list[tuple[int, str]]:
    """Flatten tree to (depth, tag) pairs for structural comparison."""
    sig = [(depth, root.tag)]
    for child in root:
        sig.extend(tree_signature(child, depth + 1))
    return sig


def extract_all_text(root) -> str:
    parts = []
    for elem in root.iter():
        if elem.text and elem.text.strip():
            parts.append(elem.text.strip())
        if elem.tail and elem.tail.strip():
            parts.append(elem.tail.strip())
    return " ".join(parts)


def word_set(text: str) -> set[str]:
    return set(re.findall(r"\b\w+\b", text.lower()))


def f1_score(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def structural_f1(expected_sig, actual_sig) -> float:
    """Compute F1 between two tree signatures (sets of (depth, tag) pairs)."""
    exp_set = Counter(expected_sig)
    act_set = Counter(actual_sig)
    # Intersection
    common = sum((exp_set & act_set).values())
    exp_total = sum(exp_set.values())
    act_total = sum(act_set.values())
    precision = common / max(act_total, 1)
    recall = common / max(exp_total, 1)
    return f1_score(precision, recall)


# ── Metric functions ─────────────────────────────────────────────────────────

def check_xml_validity(files: list[Path]) -> dict:
    """Metric 1: XML well-formedness."""
    results = {}
    for f in files:
        try:
            parse_dita(str(f))
            results[f.name] = {"valid": True, "error": None}
        except etree.XMLSyntaxError as e:
            results[f.name] = {"valid": False, "error": str(e)}
    valid_count = sum(1 for r in results.values() if r["valid"])
    return {
        "metric": "XML Well-formedness",
        "score": valid_count / max(len(results), 1),
        "valid": valid_count,
        "total": len(results),
        "details": results,
    }


def check_class_coverage(files: list[Path]) -> dict:
    """Metric 2: @class attribute coverage."""
    total_elements = 0
    elements_with_class = 0
    per_file = {}
    for f in files:
        root = parse_dita(str(f))
        n_total = sum(1 for _ in root.iter())
        n_class = sum(1 for e in root.iter() if e.get("class"))
        total_elements += n_total
        elements_with_class += n_class
        per_file[f.name] = {
            "coverage": n_class / max(n_total, 1),
            "with_class": n_class,
            "total": n_total,
        }
    return {
        "metric": "@class Attribute Coverage",
        "score": elements_with_class / max(total_elements, 1),
        "details": per_file,
    }


def check_topic_classification(expected_files: dict, actual_files: dict) -> dict:
    """Metric 3: Topic type classification accuracy."""
    results = {}
    correct = 0
    total = 0
    for key in expected_files:
        if key == "ditamap":
            continue
        exp_root = parse_dita(str(expected_files[key]))
        act_root = parse_dita(str(actual_files[key]))
        exp_type = exp_root.tag
        act_type = act_root.tag
        match = exp_type == act_type
        results[key] = {
            "expected": exp_type,
            "actual": act_type,
            "correct": match,
        }
        if match:
            correct += 1
        total += 1
    return {
        "metric": "Topic Classification Accuracy",
        "score": correct / max(total, 1),
        "correct": correct,
        "total": total,
        "details": results,
    }


def check_structural_f1(expected_files: dict, actual_files: dict) -> dict:
    """Metric 4: Structural tree F1."""
    results = {}
    scores = []
    for key in expected_files:
        if key == "ditamap":
            continue
        exp_sig = tree_signature(parse_dita(str(expected_files[key])))
        act_sig = tree_signature(parse_dita(str(actual_files[key])))
        score = structural_f1(exp_sig, act_sig)
        results[key] = {"f1": round(score, 4)}
        scores.append(score)
    return {
        "metric": "Structural F1",
        "score": sum(scores) / max(len(scores), 1),
        "details": results,
    }


def check_semantic_richness(expected_files: dict, actual_files: dict) -> dict:
    """Metric 5: Semantic domain element coverage."""
    semantic_elements = [
        "ui-d:uicontrol", "ui-d:menucascade", "ui-d:wintitle",
        "pr-d:codeblock", "pr-d:option",
    ]
    exp_counts = Counter()
    act_counts = Counter()
    for key in expected_files:
        if key == "ditamap":
            continue
        exp_counts.update(count_elements(parse_dita(str(expected_files[key]))))
        act_counts.update(count_elements(parse_dita(str(actual_files[key]))))

    results = {}
    matched = 0
    total = 0
    for elem in semantic_elements:
        exp = exp_counts.get(elem, 0)
        act = act_counts.get(elem, 0)
        if exp > 0:
            total += 1
            if act > 0:
                matched += 1
        results[elem] = {"expected": exp, "actual": act, "present": act > 0}

    return {
        "metric": "Semantic Element Coverage",
        "score": matched / max(total, 1),
        "matched": matched,
        "total_expected": total,
        "details": results,
    }


def check_content_faithfulness(expected_files: dict, actual_files: dict) -> dict:
    """Metric 6: Content preservation (word-level F1)."""
    results = {}
    scores = []
    for key in expected_files:
        if key == "ditamap":
            continue
        exp_text = extract_all_text(parse_dita(str(expected_files[key])))
        act_text = extract_all_text(parse_dita(str(actual_files[key])))
        exp_words = word_set(exp_text)
        act_words = word_set(act_text)
        overlap = exp_words & act_words
        precision = len(overlap) / max(len(act_words), 1)
        recall = len(overlap) / max(len(exp_words), 1)
        f1 = f1_score(precision, recall)
        results[key] = {
            "f1": round(f1, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
        }
        scores.append(f1)
    return {
        "metric": "Content Faithfulness (Word F1)",
        "score": sum(scores) / max(len(scores), 1),
        "details": results,
    }


def check_ditamap(expected_files: dict, actual_files: dict) -> dict:
    """Metric 7: Ditamap structure correctness."""
    exp_map = parse_dita(str(expected_files["ditamap"]))
    act_map = parse_dita(str(actual_files["ditamap"]))

    exp_refs = len([e for e in exp_map.iter() if e.tag == "topicref"])
    act_refs = len([e for e in act_map.iter() if e.tag == "topicref"])
    exp_keydefs = [e.get("keys") for e in exp_map.iter() if e.tag == "keydef"]
    act_keydefs = [e.get("keys") for e in act_map.iter() if e.tag == "keydef"]

    ref_match = exp_refs == act_refs
    keydef_match = set(exp_keydefs) == set(act_keydefs)
    has_title = any(e.tag == "title" for e in act_map.iter())

    score = (int(ref_match) + int(keydef_match) + int(has_title)) / 3

    return {
        "metric": "Ditamap Correctness",
        "score": score,
        "details": {
            "topicref_count": {"expected": exp_refs, "actual": act_refs, "match": ref_match},
            "keydefs": {"expected": exp_keydefs, "actual": act_keydefs, "match": keydef_match},
            "has_title": has_title,
        },
    }


# ── Report ───────────────────────────────────────────────────────────────────

def print_report(metrics: list[dict]):
    """Print a formatted evaluation report."""
    print()
    print("=" * 70)
    print("  PDF-to-DITA EVALUATION REPORT")
    print("=" * 70)

    overall_scores = []
    for m in metrics:
        score = m["score"]
        overall_scores.append(score)
        pct = score * 100
        bar = "#" * int(pct / 5) + "." * (20 - int(pct / 5))
        status = "✓" if pct >= 90 else ("~" if pct >= 70 else "✗")
        print(f"\n  {status} {m['metric']}")
        print(f"    Score: {bar} {pct:.1f}%")

        # Print relevant details
        details = m.get("details", {})
        if isinstance(details, dict):
            for k, v in details.items():
                if isinstance(v, dict):
                    if "correct" in v:
                        sym = "✓" if v["correct"] else "✗"
                        print(f"      {sym} {k}: expected={v['expected']}, actual={v['actual']}")
                    elif "f1" in v:
                        print(f"      {k}: F1={v['f1']:.3f}")
                    elif "present" in v:
                        sym = "✓" if v["present"] else "✗"
                        print(f"      {sym} {k}: expected={v['expected']}, actual={v['actual']}")
                    elif "valid" in v:
                        sym = "✓" if v["valid"] else "✗"
                        err = f" — {v['error']}" if v.get("error") else ""
                        print(f"      {sym} {k}{err}")
                    elif "coverage" in v:
                        print(f"      {k}: {v['coverage']*100:.0f}% ({v['with_class']}/{v['total']})")
                    elif "match" in v:
                        sym = "✓" if v["match"] else "✗"
                        print(f"      {sym} {k}: expected={v.get('expected')}, actual={v.get('actual')}")

    overall = sum(overall_scores) / max(len(overall_scores), 1)
    print(f"\n{'=' * 70}")
    pct = overall * 100
    bar = "#" * int(pct / 5) + "." * (20 - int(pct / 5))
    print(f"  OVERALL: {bar} {pct:.1f}%")
    print(f"{'=' * 70}")
    return overall


# ── File matching ────────────────────────────────────────────────────────────

def match_files(expected_dir: Path, actual_dir: Path) -> tuple[dict, dict]:
    """Match expected and actual files by topic type prefix."""
    expected = {}
    actual = {}

    for f in expected_dir.glob("*.dita"):
        if f.name.startswith("c_"):
            expected["concept"] = f
        elif f.name.startswith("t_"):
            expected["task"] = f
        elif f.name.startswith("r_"):
            expected["reference"] = f
    for f in expected_dir.glob("*.ditamap"):
        expected["ditamap"] = f

    for f in actual_dir.glob("*.dita"):
        if f.name.startswith("c_"):
            actual["concept"] = f
        elif f.name.startswith("t_"):
            actual["task"] = f
        elif f.name.startswith("r_"):
            actual["reference"] = f
    for f in actual_dir.glob("*.ditamap"):
        actual["ditamap"] = f

    return expected, actual


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Evaluate PDF-to-DITA output")
    parser.add_argument("--expected", "-e", default=None,
                        help="Directory with ground-truth DITA files")
    parser.add_argument("--actual", "-a", required=True,
                        help="Directory with generated DITA files")
    parser.add_argument("--json", "-j", default=None,
                        help="Write JSON report to file")
    args = parser.parse_args()

    actual_dir = Path(args.actual)
    actual_files = list(actual_dir.glob("*.dita")) + list(actual_dir.glob("*.ditamap"))

    if not actual_files:
        print(f"No .dita or .ditamap files found in {actual_dir}")
        sys.exit(1)

    metrics = []

    # Always run: XML validity and @class coverage
    metrics.append(check_xml_validity(list(actual_dir.glob("*.dita"))))
    metrics.append(check_class_coverage(list(actual_dir.glob("*.dita"))))

    # If expected dir provided, run comparison metrics
    if args.expected:
        expected_dir = Path(args.expected)
        expected, actual = match_files(expected_dir, actual_dir)

        # Check all required files exist
        for key in ["concept", "task", "reference", "ditamap"]:
            if key not in expected:
                print(f"⚠ Missing expected {key} file in {expected_dir}")
            if key not in actual:
                print(f"⚠ Missing actual {key} file in {actual_dir}")

        common_keys = set(expected.keys()) & set(actual.keys())
        exp_subset = {k: expected[k] for k in common_keys}
        act_subset = {k: actual[k] for k in common_keys}

        if "concept" in common_keys:
            metrics.append(check_topic_classification(exp_subset, act_subset))
            metrics.append(check_structural_f1(exp_subset, act_subset))
            metrics.append(check_semantic_richness(exp_subset, act_subset))
            metrics.append(check_content_faithfulness(exp_subset, act_subset))
        if "ditamap" in common_keys:
            metrics.append(check_ditamap(exp_subset, act_subset))

    overall = print_report(metrics)

    if args.json:
        report = {
            "overall_score": round(overall, 4),
            "metrics": [{k: v for k, v in m.items()} for m in metrics],
        }
        Path(args.json).write_text(json.dumps(report, indent=2, default=str))
        print(f"\n  JSON report: {args.json}")

    return overall


if __name__ == "__main__":
    main()
