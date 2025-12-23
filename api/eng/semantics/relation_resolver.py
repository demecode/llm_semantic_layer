from typing import Any, Dict, Optional


def resolve_semantic_model_relation(semantic_model: Dict[str, Any], nodes: Dict[str, Any]) -> str:
    """
    Convert a semantic model's 'model' reference into a physical relation_name.
    Avoid returning ref('...') strings.
    """

    model_ref = semantic_model.get("model")

    # Case 1: semantic_model["model"] is already a node id like "model.llm_co.fct_po_spend"
    if isinstance(model_ref, str) and model_ref in nodes:
        rn = nodes[model_ref].get("relation_name")
        if rn:
            return rn

    # Case 2: semantic_model["model"] looks like "ref('fct_po_spend')" or "ref(\"fct_po_spend\")"
    if isinstance(model_ref, str) and "ref(" in model_ref:
        # naive extract between quotes
        name = None
        for quote in ("'", '"'):
            if quote in model_ref:
                parts = model_ref.split(quote)
                if len(parts) >= 3:
                    name = parts[1]
                    break

        if name:
            # find the model node by its "name"
            for node in nodes.values():
                if node.get("resource_type") == "model" and node.get("name") == name:
                    rn = node.get("relation_name")
                    if rn:
                        return rn

    # Case 3: semantic_model has a relation_name directly (some versions)
    rn = semantic_model.get("relation_name")
    if rn:
        return rn

    raise ValueError(
        f"Could not resolve physical relation for semantic model '{semantic_model.get('name')}'. "
        f"semantic_model.model={model_ref}"
    )