"""v12 Matching Engine API routes — buyer-supplier matching, quotes, contracts."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from backend.models.matching import (
    BuyerRequirement,
    Incoterm,
    MatchStatus,
    PaymentTerm,
    SupplierProfile,
)
from backend.services.matching_engine_service import (
    compare_quotes,
    generate_contract,
    generate_quote,
    match_supplier,
    search_matches,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/matching", tags=["matching"])

# In-memory registries (production: use database)
_suppliers: dict[str, SupplierProfile] = {}
_requirements: dict[str, BuyerRequirement] = {}


@router.post("/suppliers/register")
async def register_supplier(request: Request) -> dict[str, Any]:
    body = await request.json()
    supplier = SupplierProfile(
        id=f"sup_{body['supplier_id']}",
        supplier_id=body["supplier_id"],
        company_name=body["company_name"],
        country=body.get("country", ""),
        product_categories=body.get("product_categories", []),
        certifications=body.get("certifications", []),
        annual_capacity=body.get("annual_capacity", {}),
        export_history=body.get("export_history", []),
        quality_rating=body.get("quality_rating", 0.0),
        verified=body.get("verified", False),
    )
    _suppliers[supplier.supplier_id] = supplier
    return {"ok": True, "supplier_id": supplier.supplier_id, "name": supplier.company_name}


@router.post("/search")
async def search_matching(request: Request) -> dict[str, Any]:
    """Search for suppliers matching a buyer requirement."""
    body = await request.json()

    requirement = BuyerRequirement(
        id=f"req_{body.get('buyer_id', 'unknown')}",
        buyer_id=body.get("buyer_id", ""),
        title=body.get("title", body.get("product_category", "")),
        product_category=body.get("product_category", ""),
        hs_code=body.get("hs_code", ""),
        specifications=body.get("specifications", {}),
        quantity=body.get("quantity", {}),
        target_price=body.get("target_price", {}),
        preferred_incoterm=Incoterm(body.get("incoterm", "FOB")),
        preferred_payment=PaymentTerm(body.get("payment_term", "T/T")),
        delivery_port=body.get("delivery_port", ""),
        target_countries=body.get("target_countries", []),
        certifications_required=body.get("certifications_required", []),
    )

    all_suppliers = list(_suppliers.values())
    if not all_suppliers:
        # Provide demo suppliers for testing
        all_suppliers = [
            SupplierProfile(
                id="sup_demo_1", supplier_id="demo_1", company_name="Demo Supplier A",
                country="CN", product_categories=[requirement.product_category],
                certifications=requirement.certifications_required[:2],
                quality_rating=4.5, verified=True,
            ),
            SupplierProfile(
                id="sup_demo_2", supplier_id="demo_2", company_name="Demo Supplier B",
                country="CN", product_categories=[requirement.product_category],
                certifications=requirement.certifications_required[:1],
                quality_rating=4.0, verified=True,
            ),
        ]

    results = search_matches(requirement, all_suppliers, top_k=body.get("top_k", 10))
    return {
        "requirement_id": requirement.id,
        "total_matches": len(results),
        "results": [
            {
                "match_id": r.id,
                "supplier_id": r.supplier_id,
                "score": r.score,
                "breakdown": {
                    "price": r.price_match,
                    "quality": r.quality_match,
                    "certification": r.certification_match,
                    "capacity": r.capacity_match,
                    "logistics": r.logistics_match,
                },
                "explanation": r.explanation,
            }
            for r in results
        ],
    }


@router.post("/quotes/generate")
async def generate_quote_endpoint(request: Request) -> dict[str, Any]:
    body = await request.json()
    quote = generate_quote(
        match_result=None,  # simplified
        quantity=body.get("quantity", 100),
        price_per_unit=body.get("price_per_unit", 0.0),
        currency=body.get("currency", "USD"),
        delivery_days=body.get("delivery_days", 30),
    )
    return {"quote_id": quote.id, "status": quote.status.value, "total": quote.total_amount}


@router.post("/quotes/compare")
async def compare_quotes_endpoint(request: Request) -> dict[str, Any]:
    body = await request.json()
    quotes_data = body.get("quotes", [])
    from backend.models.matching import Quote, QuoteStatus
    quotes = [
        Quote(
            id=f"q_{i}",
            quote_request_id="",
            supplier_id=q.get("supplier_id", ""),
            price_per_unit=q.get("price_per_unit", 0),
            currency=q.get("currency", "USD"),
            total_amount=q.get("total_amount", 0),
            delivery_days=q.get("delivery_days", 30),
            status=QuoteStatus.DRAFT,
        )
        for i, q in enumerate(quotes_data)
    ]
    return compare_quotes(quotes)


@router.post("/contracts/generate")
async def generate_contract_endpoint(request: Request) -> dict[str, Any]:
    body = await request.json()
    from backend.models.matching import Quote, QuoteStatus
    quote = Quote(
        id="temp",
        quote_request_id="",
        supplier_id=body.get("supplier_id", ""),
        price_per_unit=body.get("price_per_unit", 0),
        currency=body.get("currency", "USD"),
        total_amount=body.get("total_amount", 0),
        incoterm=Incoterm(body.get("incoterm", "FOB")),
        payment_term=PaymentTerm(body.get("payment_term", "T/T")),
        delivery_days=body.get("delivery_days", 30),
        status=QuoteStatus.ACCEPTED,
    )
    contract = generate_contract(quote, body.get("buyer_id", ""), body.get("product_description", ""))
    return {
        "contract_id": contract.id,
        "status": contract.status.value,
        "total_value": contract.total_value,
        "risk_flags": contract.risk_flags,
    }
