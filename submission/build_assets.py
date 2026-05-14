#!/usr/bin/env python3
"""Build the presentation assets for the hackathon submission.

Renders every Mermaid diagram in this file to a PNG via mermaid.ink, plus
two matplotlib charts (TCO bar + scaling line) that the markdown deliverable
embeds. Run from repo root:

    python3 submission/build_assets.py

Outputs are written to submission/images/. The mermaid.ink endpoint
expects the source to be base64url-encoded in the URL path.
"""

from __future__ import annotations

import base64
import json
import time
import urllib.request
from pathlib import Path

import matplotlib.pyplot as plt

OUT = Path(__file__).parent / "images"
OUT.mkdir(parents=True, exist_ok=True)


# ─── Mermaid diagrams ────────────────────────────────────────────────────────

DIAGRAMS: dict[str, str] = {
    "01_three_way_tldr": r"""
flowchart LR
    classDef good fill:#22c55e22,stroke:#22c55e,color:#16a34a,stroke-width:2px
    classDef bad fill:#ef444422,stroke:#ef4444,color:#dc2626,stroke-width:2px
    classDef neutral fill:#3b82f622,stroke:#3b82f6,color:#2563eb,stroke-width:2px
    A["<b>Manual conversion</b><br/>4 FTE tech writers<br/>~$507k / yr<br/>~14 months for 10k pages"]:::bad
    B["<b>Self-hosted OSS LLM</b><br/>1 GPU node + MLOps + reviewer<br/>~$307k / yr<br/>~4 months once GPU is racked"]:::neutral
    C["<b>Our solution</b><br/>API + 1 reviewer<br/><b>~$104k / yr</b><br/><b>~2 hours</b> for 10k-page backfill"]:::good
    A --> B --> C
""",

    "02_architecture": r"""
flowchart TB
    subgraph Client["Client tier"]
        BROWSER["Web UI<br/>React + Tailwind<br/>drag-and-drop, live progress"]
        CLI["CLI / batch script<br/>main.py · batch.py"]
    end

    subgraph App["Application tier — stateless container"]
        FA["FastAPI<br/>uvicorn"]
        Q["ThreadPoolExecutor<br/>per-topic parallelism"]
        FA --> Q
    end

    subgraph Pipeline["Conversion pipeline (7 stages)"]
        direction LR
        P1[Parser<br/>pdfplumber+pypdf+Pillow]
        P2[Section grouper<br/>rules]
        P3[Topic planner<br/>LLM call 1]
        P4[Classifier<br/>LLM call 2..N<br/>parallel]
        P5[Emitter<br/>lxml + templates]
        P6[14 post-processors<br/>deterministic fixers]
        P7[Validator<br/>DITA-OT 4.3.1 strict HTML5]
        P1 --> P2 --> P3 --> P4 --> P5 --> P6 --> P7
    end

    subgraph External["External"]
        GEM["Gemini 3.1-flash-lite<br/>streamGenerateContent<br/>context-cached system prompt"]
        OCR["Gemini Vision<br/>scanned-PDF + multilingual OCR"]
        DOT["DITA-OT 4.3.1<br/>local subprocess + JDK 17+"]
    end

    subgraph Storage["Storage (ephemeral)"]
        TMP["/tmp/pdf2dita_uploads/<br/>deleted post-parse"]
        OUT["/tmp/pdf2dita_output/<br/>1h TTL"]
        CACHE[".cache/<br/>SHA-256 deterministic re-runs"]
    end

    BROWSER --> FA
    CLI --> Pipeline
    Q --> Pipeline
    P3 -. system+user prompt .-> GEM
    P4 -. per-topic prompt .-> GEM
    P1 -. scan fallback .-> OCR
    P7 -. subprocess .-> DOT
    FA --> TMP
    P5 --> OUT
    P4 -. SHA-256 key .-> CACHE
    OUT --> BROWSER
""",

    "03_pipeline_data_flow": r"""
flowchart LR
    PDF[(PDF input)] --> B1["Blocks<br/>heading, paragraph, list,<br/>code, table, image, note"]
    B1 --> SEC["Sections<br/>by heading levels"]
    SEC --> PLAN["Topic plan<br/>{title, type, section_indices}"]
    PLAN --> CLS["Classified topics<br/>{topic_type, shortdesc,<br/>keywords, body_xml}"]
    CLS --> WRAP["Wrapped DITA<br/>{topic, title, shortdesc,<br/>prolog, body}"]
    WRAP --> FIX["Post-processors<br/>14 deterministic fixers"]
    FIX --> DITA[(c_*.dita<br/>t_*.dita<br/>r_*.dita<br/>m_*.ditamap)]
    DITA --> HTML[(html5/<br/>index.html)]

    style PDF fill:#fef3c7,stroke:#f59e0b
    style DITA fill:#dbeafe,stroke:#3b82f6
    style HTML fill:#dcfce7,stroke:#22c55e
""",

    "04_scaling_path": r"""
flowchart LR
    subgraph T0["TODAY · Hackathon prototype"]
        T0A["1 container<br/>4-thread executor<br/>~30s / PDF<br/>~120 PDF / hour"]
    end
    subgraph T1["STAGE 1 · 1 product line<br/>(1-2 weeks)"]
        T1A["3 containers<br/>behind ALB<br/>~360 PDF / hour"]
    end
    subgraph T2["STAGE 2 · multi-product<br/>(1-2 months)"]
        T2A["Celery + Redis<br/>autoscale 1-20 workers<br/>~2400 PDF / hour peak"]
        T2B["Postgres for<br/>run history, audit"]
    end
    subgraph T3["STAGE 3 · enterprise<br/>(3-6 months)"]
        T3A["Per-tenant API quota<br/>cost attribution"]
        T3B["Pre-signed-URL<br/>direct from BNY S3"]
        T3C["Pluggable provider<br/>Gemini ↔ Claude ↔ on-prem"]
    end
    T0 --> T1 --> T2 --> T3

    classDef ready fill:#dcfce7,stroke:#22c55e,color:#15803d
    classDef plan fill:#e0e7ff,stroke:#6366f1,color:#4338ca
    class T0A ready
    class T1A,T2A,T2B,T3A,T3B,T3C plan
""",

    "05_manual_workflow": r"""
flowchart LR
    PDF[PDF input] --> W1[Writer 1]
    PDF --> W2[Writer 2]
    PDF --> W3[Writer 3]
    PDF --> W4[Writer 4]
    W1 --> Q[Quality check<br/>+ DITA-OT]
    W2 --> Q
    W3 --> Q
    W4 --> Q
    Q --> OUT[DITA portal]

    style PDF fill:#fef3c7,stroke:#f59e0b
    style OUT fill:#dcfce7,stroke:#22c55e
""",

    "06_self_hosted_workflow": r"""
flowchart LR
    PDF[PDF input] --> APP[FastAPI app]
    APP --> GPU["GPU node<br/>H100 80GB<br/>~$8k / mo"]
    GPU --> MLO["MLOps engineer<br/>fine-tune, eval, on-call"]
    APP --> R["Reviewer<br/>QA only"]
    R --> OUT[DITA portal]

    style GPU fill:#fee2e2,stroke:#ef4444
    style PDF fill:#fef3c7,stroke:#f59e0b
    style OUT fill:#dcfce7,stroke:#22c55e
""",

    "07_our_workflow": r"""
flowchart LR
    PDF[PDF input] --> APP["FastAPI app<br/>1 vCPU, 2 GB RAM<br/>$30 / mo"]
    APP --> API["Gemini 3.1-flash-lite<br/>~$0.012 / PDF"]
    APP --> R["Reviewer<br/>QA only<br/>~85% of topics need 0 edits"]
    R --> OUT[DITA portal]

    style APP fill:#dcfce7,stroke:#22c55e
    style API fill:#dcfce7,stroke:#22c55e
    style PDF fill:#fef3c7,stroke:#f59e0b
    style OUT fill:#dcfce7,stroke:#22c55e
""",

    "08_ci_workflow": r"""
flowchart LR
    DEV[Developer push] --> GH[GitHub Actions]
    GH --> SETUP[Install Python deps<br/>+ JDK 21<br/>+ DITA-OT 4.3.1]
    SETUP --> RUN["Run pipeline<br/>main.py test_data/sample.pdf"]
    RUN --> ASSERT[Assert artifacts<br/>m_*.ditamap exists]
    ASSERT --> OT["DITA-OT HTML5<br/>--processing-mode=strict"]
    OT --> ART[Upload artifacts<br/>output/ + html5/]
    ART --> BADGE[Green badge ✓]

    style DEV fill:#e0e7ff,stroke:#6366f1
    style BADGE fill:#dcfce7,stroke:#22c55e
""",

    "09_repository_layout": r"""
flowchart TB
    R[("repo root")] --> PY1["main.py · CLI entrypoint"]
    R --> PY2["parser.py · pdfplumber + OCR fallback"]
    R --> PY3["classifier.py · LLM prompts + caching"]
    R --> PY4["emitter.py · XML wrapping + DITA-OT"]
    R --> PY5["llm_providers.py · Gemini/Claude/Kimi abstraction"]
    R --> PY6["batch.py · directory mode"]
    R --> PY7["demo_server.py · FastAPI + /convert + /progress"]
    R --> UI["static/ · React UI<br/>Babel-standalone, no build step"]
    R --> MK["Makefile · demo / test / batch / html5 / ci"]
    R --> SH["run_demo.sh · jury-facing one-shot showcase"]
    R --> CI[".github/workflows/ci.yml · automated validation"]
    R --> DOC1["SOLUTION_OVERVIEW.md · technical architecture"]
    R --> DOC2["BUSINESS_CASE.md · cost + ROI + scaling"]
""",
}


def _mermaid_to_png(source: str, out_path: Path) -> None:
    """Send mermaid source to mermaid.ink → PNG, save to disk."""
    # mermaid.ink uses base64url (no padding, '-_' alphabet) in the URL.
    encoded = base64.urlsafe_b64encode(source.strip().encode("utf-8")).decode("ascii").rstrip("=")
    url = f"https://mermaid.ink/img/{encoded}?type=png&bgColor=FFFFFF&width=1600"
    req = urllib.request.Request(url, headers={"User-Agent": "pdf2dita-build/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        out_path.write_bytes(resp.read())


def _render_all_mermaid() -> None:
    for name, src in DIAGRAMS.items():
        target = OUT / f"{name}.png"
        print(f"  rendering {target.name} ...", end=" ", flush=True)
        try:
            _mermaid_to_png(src, target)
            print(f"OK ({target.stat().st_size // 1024} KB)")
        except Exception as ex:
            print(f"FAILED: {ex}")
        time.sleep(0.3)  # be polite to mermaid.ink


# ─── Matplotlib charts ───────────────────────────────────────────────────────

def _theme():
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": "#cbd5e1",
        "axes.labelcolor": "#334155",
        "xtick.color": "#475569",
        "ytick.color": "#475569",
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "figure.facecolor": "white",
    })


def chart_year1_tco() -> None:
    _theme()
    labels = ["Manual\nconversion", "Self-hosted\nLLM", "This tool"]
    values = [507, 307, 104]
    colors = ["#ef4444", "#3b82f6", "#22c55e"]
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=160)
    bars = ax.bar(labels, values, color=colors, width=0.55, edgecolor="white", linewidth=1.5)
    ax.set_ylabel("Year-1 cost (USD thousands)")
    ax.set_title("Year-1 TCO — 10,000-page documentation backfill")
    ax.set_ylim(0, max(values) * 1.18)
    ax.grid(axis="y", linestyle=":", color="#e2e8f0", linewidth=1)
    ax.set_axisbelow(True)
    for bar, v in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 12,
                f"${v}k", ha="center", va="bottom", fontweight=600, color="#0f172a", fontsize=12)
    # Savings vs manual under the green bar
    savings = values[0] - values[2]
    ax.text(2, -38, f"−${savings}k savings vs manual baseline",
            ha="center", color="#16a34a", fontweight=600, fontsize=11,
            transform=ax.transData)
    fig.tight_layout()
    fig.savefig(OUT / "chart_year1_tco.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  rendered chart_year1_tco.png")


def chart_per_pdf_cost() -> None:
    _theme()
    labels = ["Manual\n(writer-day fraction)", "Self-hosted LLM\n(amortised GPU+ops)", "This tool\n(pure API)"]
    values = [60.00, 0.40, 0.012]
    colors = ["#ef4444", "#3b82f6", "#22c55e"]
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=160)
    bars = ax.barh(labels[::-1], values[::-1], color=colors[::-1],
                   height=0.55, edgecolor="white", linewidth=1.5)
    ax.set_xscale("log")
    ax.set_xlabel("Marginal cost per PDF (USD, log scale)")
    ax.set_title("Marginal cost per PDF — 3-way comparison")
    ax.grid(axis="x", which="major", linestyle=":", color="#e2e8f0", linewidth=1)
    ax.set_axisbelow(True)
    for bar, v in zip(bars, values[::-1]):
        s = f"${v:.3f}" if v < 1 else f"${v:.0f}"
        ax.text(v * 1.08, bar.get_y() + bar.get_height() / 2,
                s, va="center", fontweight=600, color="#0f172a", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / "chart_per_pdf_cost.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  rendered chart_per_pdf_cost.png")


def chart_tco_vs_scale() -> None:
    _theme()
    pages = ["1k", "10k", "100k", "1M", "10M"]
    manual = [54, 507, 5070, 50700, 570000]
    self_h = [120, 307, 660, 1830, 4200]
    ours = [104, 105, 116, 165, 700]
    x = list(range(len(pages)))
    fig, ax = plt.subplots(figsize=(8.5, 4.5), dpi=160)
    ax.plot(x, manual, marker="o", linewidth=2.2, color="#ef4444", label="Manual conversion")
    ax.plot(x, self_h, marker="o", linewidth=2.2, color="#3b82f6", label="Self-hosted LLM")
    ax.plot(x, ours,   marker="o", linewidth=2.6, color="#22c55e", label="This tool")
    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels(pages)
    ax.set_xlabel("Workload (PDF pages converted per year)")
    ax.set_ylabel("Annual cost (USD k, log scale)")
    ax.set_title("Cost vs scale — log-log axes")
    ax.grid(linestyle=":", color="#e2e8f0", linewidth=1)
    ax.set_axisbelow(True)
    ax.legend(loc="upper left", frameon=False)
    # Annotate the rightmost ours point
    ax.annotate(f"${ours[-1]}k\nat 10M pages/yr",
                xy=(x[-1], ours[-1]), xytext=(x[-1] - 1.1, ours[-1] * 4),
                color="#15803d", fontweight=600, fontsize=11, ha="center",
                arrowprops=dict(arrowstyle="->", color="#22c55e"))
    fig.tight_layout()
    fig.savefig(OUT / "chart_tco_vs_scale.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  rendered chart_tco_vs_scale.png")


def chart_5yr_npv() -> None:
    _theme()
    labels = ["Manual", "Self-hosted\nLLM", "This tool"]
    yr1_color_bg = ["#fee2e2", "#dbeafe", "#dcfce7"]
    bars_color = ["#ef4444", "#3b82f6", "#22c55e"]
    yr1   = [507, 307, 104]
    yr2_5 = [4 * 108, 4 * 307, 4 * 104]
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=160)
    bottoms = [0, 0, 0]
    b1 = ax.bar(labels, yr1, color=bars_color, edgecolor="white", linewidth=1.5,
                width=0.55, label="Year 1")
    b2 = ax.bar(labels, yr2_5, bottom=yr1, color=yr1_color_bg, edgecolor="white", linewidth=1.5,
                width=0.55, label="Years 2-5 steady state")
    ax.set_ylabel("5-year cost of ownership (USD thousands)")
    ax.set_title("5-year cost of ownership")
    ax.grid(axis="y", linestyle=":", color="#e2e8f0", linewidth=1)
    ax.set_axisbelow(True)
    ax.legend(loc="upper right", frameon=False)
    for i, (a, b) in enumerate(zip(yr1, yr2_5)):
        total = a + b
        ax.text(i, total + 50, f"${total}k", ha="center", fontweight=700, color="#0f172a", fontsize=12)
    ax.set_ylim(0, max(yr1[i] + yr2_5[i] for i in range(3)) * 1.15)
    fig.tight_layout()
    fig.savefig(OUT / "chart_5yr_npv.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  rendered chart_5yr_npv.png")


def chart_quality_match() -> None:
    _theme()
    items = [
        "Topic count + types",
        "Document map structure",
        "<menucascade>",
        "<note>",
        "<fig> + image",
        "Cross-references",
        "Best-practice cleanup",
        "Product-name keyref",
        "DITA-OT strict HTML5",
        "<shortdesc> (3.2.1.6)",
        "<keywords> (3.2.2.18)",
        "<alt> per image (3.2.2.1)",
    ]
    # 1 = match, 2 = exceed
    status = [1] * 9 + [2] * 3
    colors = ["#22c55e" if s == 1 else "#3b82f6" for s in status]
    fig, ax = plt.subplots(figsize=(8.5, 5), dpi=160)
    ax.barh(items[::-1], [1] * 12, color=colors[::-1], edgecolor="white", linewidth=1.4)
    for i, s in enumerate(status[::-1]):
        ax.text(0.5, i, "MATCH" if s == 1 else "EXCEED",
                ha="center", va="center", color="white", fontweight=700, fontsize=11)
    ax.set_xlim(0, 1)
    ax.set_xticks([])
    ax.set_title("Output quality vs BNY gold sample — 12 dimensions")
    for spine in ("top", "right", "bottom", "left"):
        ax.spines[spine].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "chart_quality_match.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  rendered chart_quality_match.png")


def chart_stage_breakdown() -> None:
    _theme()
    stages = ["PDF parsing", "Section\ngrouping", "Topic\nplanning", "DITA\ngeneration",
              "File\nemission", "XML check", "DITA-OT\nHTML5"]
    times  = [0.5, 0.0, 5.3, 17.0, 0.0, 0.0, 4.7]
    colors = ["#60a5fa", "#a78bfa", "#f472b6", "#f472b6", "#fbbf24", "#34d399", "#34d399"]
    fig, ax = plt.subplots(figsize=(8.5, 4), dpi=160)
    bars = ax.bar(stages, times, color=colors, width=0.6, edgecolor="white", linewidth=1.5)
    ax.set_ylabel("Wall-clock seconds")
    ax.set_title("Per-stage timing on the BNY sample (gemini-3.1-flash-lite, paid tier)")
    for bar, t in zip(bars, times):
        ax.text(bar.get_x() + bar.get_width() / 2, t + 0.4, f"{t:.1f}s",
                ha="center", fontweight=600, color="#0f172a", fontsize=10)
    ax.grid(axis="y", linestyle=":", color="#e2e8f0", linewidth=1)
    ax.set_axisbelow(True)
    ax.set_ylim(0, max(times) * 1.18)
    # Total
    ax.text(len(stages) - 0.5, max(times) * 1.05, f"Total: {sum(times):.1f}s",
            ha="right", fontweight=700, color="#16a34a", fontsize=12)
    fig.tight_layout()
    fig.savefig(OUT / "chart_stage_breakdown.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  rendered chart_stage_breakdown.png")


def main() -> None:
    print("Rendering Mermaid diagrams via mermaid.ink ...")
    _render_all_mermaid()
    print("\nRendering matplotlib charts ...")
    chart_year1_tco()
    chart_per_pdf_cost()
    chart_tco_vs_scale()
    chart_5yr_npv()
    chart_quality_match()
    chart_stage_breakdown()
    print(f"\nDone. {len(list(OUT.glob('*.png')))} PNGs in {OUT}")


if __name__ == "__main__":
    main()
