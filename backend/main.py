from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import os
from openai import OpenAI
from io import StringIO

app = FastAPI(title="J Thrust Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STORE = {"variants": []}

REQUIRED_COLUMNS = [
    "variant_id",
    "gene",
    "variant_hgvs",
    "current_classification",
    "condition",
    "patient_ancestry_group",
    "patient_impact_level",
    "ancestry_data_gap",
    "affected_relative_available",
    "splice_suspected",
    "literature_evidence_level",
    "functional_assay_available",
    "clinvar_snapshot",
    "clingen_snapshot",
    "gnomad_snapshot",
    "splice_prediction_snapshot",
    "mavedb_snapshot",
    "last_review_date",
]

def clean(x):
    if pd.isna(x):
        return ""
    return str(x).strip()

def actor_for_path(path):
    return {
        "RNA/splicing evidence needed": "RNA/splicing assay team",
        "Family evidence needed": "Family-data coordinator",
        "Population evidence needed": "Lab researcher",
        "Literature review needed": "Variant curator",
        "Functional evidence needed": "Functional assay team",
        "Reanalysis later": "Reanalysis system",
    }.get(path, "Variant curator")

def triage(row):
    record = {col: clean(row[col]) for col in REQUIRED_COLUMNS}
    record["gene"] = record["gene"].replace("-", "").replace(" ", "").upper()

    gaps = []

    if record["splice_suspected"] == "Yes":
        gaps.append("RNA/splicing evidence needed")

    if record["affected_relative_available"] == "Yes":
        gaps.append("Family evidence needed")

    if record["ancestry_data_gap"] in ["High", "Medium"]:
        gaps.append("Population evidence needed")

    if record["literature_evidence_level"] in ["Limited", "None found", "Unknown"]:
        gaps.append("Literature review needed")

    if record["functional_assay_available"] in ["Yes", "Potentially relevant"]:
        gaps.append("Functional evidence needed")

    if "RNA/splicing evidence needed" in gaps:
        primary_path = "RNA/splicing evidence needed"
        main_reason = "Splice-suspected variant missing RNA/splicing evidence."
    elif "Family evidence needed" in gaps:
        primary_path = "Family evidence needed"
        main_reason = "Affected relative availability suggests family evidence may help."
    elif "Population evidence needed" in gaps:
        primary_path = "Population evidence needed"
        main_reason = "Limited ancestry-matched population evidence appears to be a key gap."
    elif "Literature review needed" in gaps:
        primary_path = "Literature review needed"
        main_reason = "Literature evidence appears limited or unknown."
    elif "Functional evidence needed" in gaps:
        primary_path = "Functional evidence needed"
        main_reason = "Functional evidence may be relevant but unresolved."
    else:
        primary_path = "Reanalysis later"
        main_reason = "No useful immediate evidence path is visible in the current snapshot."

    secondary_paths = [g for g in gaps if g != primary_path]

    if primary_path == "Reanalysis later":
        priority = "Reanalysis later"
    elif record["splice_suspected"] == "Yes":
        priority = "High priority"
    elif record["patient_impact_level"] == "High":
        priority = "High priority"
    elif record["ancestry_data_gap"] == "High":
        priority = "High priority"
    elif record["patient_impact_level"] == "Medium":
        priority = "Medium priority"
    else:
        priority = "Low priority"

    return {
        **record,
        "priority_category": priority,
        "main_reason": main_reason,
        "primary_evidence_path": primary_path,
        "secondary_evidence_paths": secondary_paths,
        "primary_actor": actor_for_path(primary_path),
        "secondary_actors": [actor_for_path(p) for p in secondary_paths],
        "safety_boundary": "J Thrust does not classify variants, determine benign/pathogenic status, or make medical recommendations. It only routes uncertain variants toward missing evidence paths for lab/research triage.",
    }

def priority_rank(v):
    order = {
        "High priority": 1,
        "Medium priority": 2,
        "Low priority": 3,
        "Reanalysis later": 4,
    }
    return order.get(v["priority_category"], 99)

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "J Thrust Backend"}

@app.post("/api/upload")
async def upload_csv(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a CSV file.")

    raw = await file.read()
    text = raw.decode("utf-8")
    df = pd.read_csv(StringIO(text))

    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        return {
            "status": "error",
            "variant_count": 0,
            "errors": [f"Missing required column: {col}" for col in missing],
        }

    variants = [triage(row) for _, row in df.iterrows()]
    variants = sorted(variants, key=priority_rank)
    STORE["variants"] = variants

    return {
        "status": "success",
        "variant_count": len(variants),
        "errors": [],
    }

@app.get("/api/variants")
def get_variants():
    return {"variants": STORE["variants"]}

@app.get("/api/variants/{variant_id}")
def get_variant(variant_id: str):
    for variant in STORE["variants"]:
        if variant["variant_id"] == variant_id:
            return {"variant": variant}
    raise HTTPException(status_code=404, detail="Variant not found.")


@app.get("/api/variants/{variant_id}/map")
def get_variant_map(variant_id: str):
    for variant in STORE["variants"]:
        if variant["variant_id"] == variant_id:
            nodes = [
                {"id": "variant", "label": variant["gene"] + " " + variant["variant_hgvs"], "type": "Variant"},
                {"id": "classification", "label": variant["current_classification"], "type": "Classification"},
                {"id": "path", "label": variant["primary_evidence_path"], "type": "Evidence Path"},
                {"id": "actor", "label": variant["primary_actor"], "type": "Actor"},
            ]

            edges = [
                {"from": "variant", "to": "classification"},
                {"from": "variant", "to": "path"},
                {"from": "path", "to": "actor"},
            ]

            for i, path in enumerate(variant["secondary_evidence_paths"]):
                node_id = f"secondary_{i}"
                nodes.append({"id": node_id, "label": path, "type": "Secondary Path"})
                edges.append({"from": "variant", "to": node_id})

            return {"nodes": nodes, "edges": edges}

    raise HTTPException(status_code=404, detail="Variant not found.")


FORBIDDEN_AI_PHRASES = [
    "this variant is pathogenic",
    "this variant is benign",
    "this variant causes cancer",
    "cancer-causing",
    "medically actionable",
    "change medical management",
    "the patient should",
    "diagnosis",
    "diagnostic",
]

def safe_fallback_ai_explanation(variant):
    secondary = variant.get("secondary_evidence_paths", [])
    secondary_text = ", ".join(secondary) if secondary else "no secondary paths listed"

    return (
        f"This variant remains uncertain in the demo evidence snapshot. "
        f"The rule-based system routed it to {variant.get('primary_evidence_path')} "
        f"because: {variant.get('main_reason')} "
        f"The assigned next actor is {variant.get('primary_actor')}. "
        f"Secondary evidence paths include: {secondary_text}. "
        f"J Thrust does not reclassify the variant, determine benign/pathogenic status, "
        f"or make medical recommendations."
    )

def run_safety_check(text):
    lowered = text.lower()
    blocked = []
    for phrase in FORBIDDEN_AI_PHRASES:
        if phrase in lowered:
            blocked.append(phrase)
    return blocked

@app.get("/api/variants/{variant_id}/ai-explanation")
def get_ai_explanation(variant_id: str):
    variant = None
    for item in STORE["variants"]:
        if item["variant_id"] == variant_id:
            variant = item
            break

    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found.")

    if not os.getenv("OPENAI_API_KEY"):
        return {
            "mode": "fallback_template",
            "explanation": safe_fallback_ai_explanation(variant),
            "safety_warnings": ["OPENAI_API_KEY not set; used safe fallback template."]
        }

    system_instructions = """
You are writing a safe internal lab/research explanation for a VUS triage prototype.

Critical rules:
- Do not classify the variant.
- Do not say the variant is benign or pathogenic.
- Do not say the variant causes cancer.
- Do not make patient-care recommendations.
- Do not tell anyone to change medical management.
- Do not invent evidence.
- Use only the structured fields provided.
- Treat the rule-based priority, evidence path, and actor as fixed.
- Explain why the routing makes sense.
- Keep the explanation concise and lab-facing.
- End with a safety sentence saying J Thrust identifies missing evidence paths only.
"""

    user_input = {
        "variant_id": variant.get("variant_id"),
        "gene": variant.get("gene"),
        "variant_hgvs": variant.get("variant_hgvs"),
        "current_classification": variant.get("current_classification"),
        "condition": variant.get("condition"),
        "priority_category": variant.get("priority_category"),
        "main_reason": variant.get("main_reason"),
        "primary_evidence_path": variant.get("primary_evidence_path"),
        "secondary_evidence_paths": variant.get("secondary_evidence_paths"),
        "primary_actor": variant.get("primary_actor"),
        "secondary_actors": variant.get("secondary_actors"),
        "clinvar_snapshot": variant.get("clinvar_snapshot"),
        "clingen_snapshot": variant.get("clingen_snapshot"),
        "gnomad_snapshot": variant.get("gnomad_snapshot"),
        "splice_prediction_snapshot": variant.get("splice_prediction_snapshot"),
        "mavedb_snapshot": variant.get("mavedb_snapshot"),
        "safety_boundary": variant.get("safety_boundary"),
    }

    try:
        client = OpenAI()
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-5"),
            instructions=system_instructions,
            input=f"Write the internal lab/research explanation from these structured fields only: {user_input}",
        )

        explanation = response.output_text.strip()
        blocked = run_safety_check(explanation)

        if blocked:
            return {
                "mode": "blocked_and_replaced",
                "explanation": safe_fallback_ai_explanation(variant),
                "safety_warnings": [f"AI output contained blocked phrase: {phrase}" for phrase in blocked]
            }

        return {
            "mode": "openai_generated",
            "explanation": explanation,
            "safety_warnings": []
        }

    except Exception as e:
        return {
            "mode": "error_fallback_template",
            "explanation": safe_fallback_ai_explanation(variant),
            "safety_warnings": [str(e)]
        }

@app.get("/api/variants/{variant_id}/ai-smart-v2")
def get_ai_smart_v2(variant_id: str):
    variant = None

    for item in STORE["variants"]:
        if item["variant_id"] == variant_id:
            variant = item
            break

    if not variant:
        raise HTTPException(
            status_code=404,
            detail="Variant not found. Upload the CSV again after restarting backend."
        )

    secondary = variant.get("secondary_evidence_paths", [])
    secondary_text = ", ".join(secondary) if secondary else "no secondary evidence paths listed"

    fallback = (
        f"This AI-assisted explanation is based only on J Thrust's structured routing output. "
        f"{variant.get('gene')} {variant.get('variant_hgvs')} remains uncertain in the demo snapshot. "
        f"The rule-based engine routed this variant to {variant.get('primary_evidence_path')} "
        f"because {variant.get('main_reason')} "
        f"The assigned next actor is {variant.get('primary_actor')}. "
        f"Secondary evidence paths include: {secondary_text}. "
        f"J Thrust identifies missing evidence paths only and does not classify variants or make clinical recommendations."
    )

    import os

    if not os.getenv("OPENAI_API_KEY"):
        return {
            "mode": "safe_template_no_api_key",
            "explanation": fallback,
            "safety_warnings": ["No OPENAI_API_KEY found, so the safe local template was used."]
        }

    try:
        from openai import OpenAI

        client = OpenAI()

        prompt = f"""
You are helping write a safe internal lab/research explanation for a VUS evidence-routing prototype.

Use only the structured data below. Do not invent evidence.

Variant ID: {variant.get("variant_id")}
Gene: {variant.get("gene")}
HGVS: {variant.get("variant_hgvs")}
Classification snapshot: {variant.get("current_classification")}
Condition: {variant.get("condition")}
Priority: {variant.get("priority_category")}
Main reason: {variant.get("main_reason")}
Primary evidence path: {variant.get("primary_evidence_path")}
Secondary evidence paths: {variant.get("secondary_evidence_paths")}
Primary actor: {variant.get("primary_actor")}
ClinVar snapshot: {variant.get("clinvar_snapshot")}
ClinGen snapshot: {variant.get("clingen_snapshot")}
gnomAD snapshot: {variant.get("gnomad_snapshot")}
Splice snapshot: {variant.get("splice_prediction_snapshot")}
Functional snapshot: {variant.get("mavedb_snapshot")}

Safety rules:
- Do not classify the variant.
- Do not say the variant is benign or pathogenic.
- Do not say the variant causes cancer.
- Do not make medical recommendations.
- Do not tell anyone to change patient management.
- Explain only why the evidence-routing result makes sense.
- End by saying J Thrust identifies missing evidence paths only.
"""

        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            input=prompt,
        )

        explanation = response.output_text.strip()

        blocked_phrases = [
            "this variant is pathogenic",
            "this variant is benign",
            "causes cancer",
            "cancer-causing",
            "change medical management",
            "the patient should",
            "diagnosis confirmed",
        ]

        lowered = explanation.lower()
        blocked = [phrase for phrase in blocked_phrases if phrase in lowered]

        if blocked:
            return {
                "mode": "ai_blocked_used_safe_template",
                "explanation": fallback,
                "safety_warnings": [f"Blocked unsafe phrase: {phrase}" for phrase in blocked]
            }

        return {
            "mode": "openai_generated",
            "explanation": explanation,
            "safety_warnings": []
        }

    except Exception as e:
        return {
            "mode": "openai_error_used_safe_template",
            "explanation": fallback,
            "safety_warnings": [str(e)]
        }
