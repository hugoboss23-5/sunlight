"""
OCDS Field Extractor for SUNLIGHT CRI Indicators

Extracts structured indicator inputs from raw OCDS release data.
Handles field presence/absence gracefully — missing fields produce
GRAY (indeterminate) rather than GREEN (clean), following the principle
that absence of evidence is not evidence of absence.

References:
- OCDS schema: https://standard.open-contracting.org/latest/en/schema/
- OCP Red Flags Guide (2024): 73 indicators mapped to OCDS fields
- Cardinal library field mapping: https://github.com/open-contracting/cardinal-rs
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExtractedRelease:
    """Structured data extracted from a single OCDS release for indicator computation."""

    # Identity
    ocid: str
    release_id: str
    release_date: Optional[datetime] = None

    # Buyer info
    buyer_id: Optional[str] = None
    buyer_name: Optional[str] = None

    # Tender fields
    procurement_method: Optional[str] = None          # open, limited, direct, selective
    procurement_method_details: Optional[str] = None   # free text description
    number_of_tenderers: Optional[int] = None
    tender_period_start: Optional[datetime] = None
    tender_period_end: Optional[datetime] = None
    tender_period_days: Optional[float] = None
    enquiry_period_end: Optional[datetime] = None
    tender_status: Optional[str] = None

    # Award fields
    award_date: Optional[datetime] = None
    award_value: Optional[float] = None
    award_currency: Optional[str] = None
    award_supplier_id: Optional[str] = None
    award_supplier_name: Optional[str] = None
    number_of_awards: int = 0

    # Contract fields
    contract_value: Optional[float] = None
    contract_currency: Optional[str] = None
    contract_period_start: Optional[datetime] = None
    contract_period_end: Optional[datetime] = None

    # Amendment fields
    amendments: list[dict] = field(default_factory=list)
    amendment_count: int = 0
    original_value: Optional[float] = None
    final_value: Optional[float] = None

    # Bid details (if available — many publishers omit this)
    bids: list[dict] = field(default_factory=list)
    bid_count: Optional[int] = None

    # Item classification
    item_classifications: list[str] = field(default_factory=list)
    main_classification: Optional[str] = None

    # Decision period (award date - tender end date)
    decision_period_days: Optional[float] = None

    # Data quality flags
    fields_present: set = field(default_factory=set)
    fields_missing: set = field(default_factory=set)


def parse_datetime(value) -> Optional[datetime]:
    """Parse ISO datetime string, handling various OCDS formats."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    # Try common formats
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    logger.warning(f"Could not parse datetime: {value}")
    return None


def safe_get(data: dict, *keys, default=None):
    """Safely traverse nested dict keys."""
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, default)
        elif isinstance(current, list) and isinstance(key, int) and key < len(current):
            current = current[key]
        else:
            return default
    return current


def extract_release(release: dict) -> ExtractedRelease:
    """
    Extract structured indicator inputs from a raw OCDS release.

    Handles both compiled releases (full picture of a contracting process)
    and individual releases. Gracefully handles missing fields.

    Args:
        release: A single OCDS release dict

    Returns:
        ExtractedRelease with all available fields populated
    """
    result = ExtractedRelease(
        ocid=release.get("ocid", ""),
        release_id=release.get("id", ""),
        release_date=parse_datetime(release.get("date")),
    )

    present = set()
    missing = set()

    # --- BUYER ---
    buyer = release.get("buyer", {})
    if buyer:
        result.buyer_id = buyer.get("id") or buyer.get("identifier", {}).get("id")
        result.buyer_name = buyer.get("name")
        if result.buyer_id:
            present.add("buyer_id")
        else:
            missing.add("buyer_id")
    else:
        # Try parties array with "buyer" role
        for party in release.get("parties", []):
            if "buyer" in party.get("roles", []):
                result.buyer_id = party.get("id") or party.get("identifier", {}).get("id")
                result.buyer_name = party.get("name")
                break
        if result.buyer_id:
            present.add("buyer_id")
        else:
            missing.add("buyer_id")

    # --- TENDER ---
    tender = release.get("tender", {})
    if tender:
        # Procurement method
        result.procurement_method = tender.get("procurementMethod")
        result.procurement_method_details = tender.get("procurementMethodDetails")
        if result.procurement_method:
            present.add("procurement_method")
        else:
            missing.add("procurement_method")

        # Number of tenderers — multiple possible locations
        n_tenderers = tender.get("numberOfTenderers")
        if n_tenderers is not None:
            try:
                result.number_of_tenderers = int(n_tenderers)
                present.add("number_of_tenderers")
            except (ValueError, TypeError):
                missing.add("number_of_tenderers")
        else:
            missing.add("number_of_tenderers")

        # Tender period
        tender_period = tender.get("tenderPeriod", {})
        if tender_period:
            result.tender_period_start = parse_datetime(tender_period.get("startDate"))
            result.tender_period_end = parse_datetime(tender_period.get("endDate"))
            if result.tender_period_start and result.tender_period_end:
                delta = result.tender_period_end - result.tender_period_start
                result.tender_period_days = delta.total_seconds() / 86400
                present.add("tender_period_days")
            else:
                missing.add("tender_period_days")
        else:
            missing.add("tender_period_days")

        # Enquiry period
        enquiry_period = tender.get("enquiryPeriod", {})
        if enquiry_period:
            result.enquiry_period_end = parse_datetime(enquiry_period.get("endDate"))

        result.tender_status = tender.get("status")

    # --- BIDS ---
    bids_section = release.get("bids", {})
    bid_details = bids_section.get("details", []) if isinstance(bids_section, dict) else []
    if bid_details:
        result.bids = bid_details
        result.bid_count = len(bid_details)
        present.add("bid_count")
        # If we have bid details but no numberOfTenderers, derive it
        if result.number_of_tenderers is None:
            # Count unique tenderers
            tenderer_ids = set()
            for bid in bid_details:
                for tenderer in bid.get("tenderers", []):
                    tid = tenderer.get("id") or tenderer.get("name", "")
                    if tid:
                        tenderer_ids.add(tid)
            if tenderer_ids:
                result.number_of_tenderers = len(tenderer_ids)
                present.add("number_of_tenderers")
    else:
        missing.add("bid_details")

    # --- AWARDS ---
    awards = release.get("awards", [])
    if awards:
        result.number_of_awards = len(awards)
        # Use first active/valid award
        active_award = None
        for award in awards:
            if award.get("status") in ("active", "Active", None):
                active_award = award
                break
        if active_award is None and awards:
            active_award = awards[0]

        if active_award:
            result.award_date = parse_datetime(active_award.get("date"))
            value = active_award.get("value", {})
            if value:
                try:
                    result.award_value = float(value.get("amount", 0))
                    result.award_currency = value.get("currency")
                    present.add("award_value")
                except (ValueError, TypeError):
                    missing.add("award_value")

            # Supplier from award
            suppliers = active_award.get("suppliers", [])
            if suppliers:
                result.award_supplier_id = suppliers[0].get("id") or suppliers[0].get("name")
                result.award_supplier_name = suppliers[0].get("name")
                present.add("award_supplier_id")
            else:
                missing.add("award_supplier_id")

            # Decision period: award date minus tender period end
            if result.award_date and result.tender_period_end:
                delta = result.award_date - result.tender_period_end
                result.decision_period_days = delta.total_seconds() / 86400
                present.add("decision_period_days")
    else:
        missing.add("awards")

    # --- CONTRACTS ---
    contracts = release.get("contracts", [])
    if contracts:
        contract = contracts[0]  # Primary contract
        value = contract.get("value", {})
        if value:
            try:
                result.contract_value = float(value.get("amount", 0))
                result.contract_currency = value.get("currency")
                present.add("contract_value")
            except (ValueError, TypeError):
                missing.add("contract_value")

        period = contract.get("period", {})
        if period:
            result.contract_period_start = parse_datetime(period.get("startDate"))
            result.contract_period_end = parse_datetime(period.get("endDate"))

        # Amendments
        amendments = contract.get("amendments", [])
        if amendments:
            result.amendments = amendments
            result.amendment_count = len(amendments)
            present.add("amendments")
            # Try to compute value change from amendments
            if result.award_value and result.contract_value:
                result.original_value = result.award_value
                result.final_value = result.contract_value
    else:
        missing.add("contracts")

    # --- ITEM CLASSIFICATION ---
    items = safe_get(release, "tender", "items") or []
    classifications = []
    for item in items:
        classification = item.get("classification", {})
        scheme = classification.get("scheme", "")
        item_id = classification.get("id", "")
        if item_id:
            classifications.append(f"{scheme}:{item_id}" if scheme else item_id)
    result.item_classifications = classifications
    if classifications:
        result.main_classification = classifications[0]
        present.add("item_classification")
    else:
        missing.add("item_classification")

    result.fields_present = present
    result.fields_missing = missing
    return result


def extract_releases(releases: list[dict]) -> list[ExtractedRelease]:
    """Extract structured data from a list of OCDS releases."""
    results = []
    for release in releases:
        try:
            results.append(extract_release(release))
        except Exception as e:
            logger.error(f"Failed to extract release {release.get('ocid', '?')}: {e}")
    return results
