from fastapi import APIRouter

router = APIRouter()


@router.get("/graph/{patient_id}")
def get_graph(patient_id: str):
    return {
        "patient_id": patient_id,
        "nodes": [
            {
                "id": "APOE",
                "label": "APOE",
                "type": "gene"
            },
            {
                "id": "LDL",
                "label": "LDL",
                "type": "biomarker"
            }
        ],
        "edges": [
            {
                "source": "APOE",
                "target": "LDL",
                "relationship": "associated_with"
            }
        ]
    }
