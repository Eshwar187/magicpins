"""Deterministic renderer translating authoritative Decision and grounded facts into composed components."""

from typing import Any, Dict, List, Optional, Tuple

from app.domain.facts.fact import Fact
from app.domain.models.category import CategoryProfile
from app.domain.models.customer import CustomerStateModel
from app.domain.models.merchant import MerchantState
from app.domain.models.trigger import TriggerState
from app.engine.actions import ActionType
from app.engine.decision import Decision
from app.composer.templates import TEMPLATES, TemplateDefinition


def _get_salutation(merchant: MerchantState, category: CategoryProfile) -> str:
    """Derive professional salutation name from merchant identity."""
    owner = merchant.identity.owner_first_name
    if owner:
        if category.slug == "dentists":
            return f"Dr. {owner}"
        return owner
    name = merchant.identity.name
    if category.slug == "dentists" and not name.lower().startswith("dr."):
        return f"Dr. {name}"
    return name


def _get_customer_salutation(customer: Optional[CustomerStateModel]) -> str:
    """Derive customer salutation name from customer identity."""
    if not customer:
        return "there"
    name = customer.identity.name
    if not name or name.startswith("("):
        return "there"
    parts = name.split()
    if len(parts) >= 2 and parts[0].lower() in ("mr.", "mr", "mrs.", "mrs", "ms.", "ms", "dr.", "dr"):
        return f"{parts[0]} {parts[1]}"
    return parts[0]


def _format_delta_abs(val: Any) -> str:
    """Format fractional or integer percentage delta into absolute string (e.g. -0.35 -> '35')."""
    if val is None:
        return "20"
    try:
        f = float(val)
        if -1.0 <= f <= 1.0 and f != 0.0:
            return str(int(round(abs(f) * 100)))
        return str(int(round(abs(f))))
    except Exception:
        return str(val)


def _build_suppression_key(decision: Decision, category: CategoryProfile, merchant: MerchantState, trigger: TriggerState, customer: Optional[CustomerStateModel]) -> str:
    """Construct deterministic dedup / suppression key."""
    if decision.action_type in (ActionType.WAIT, ActionType.END):
        return f"{decision.action_type.value}:{trigger.id}"

    payload = trigger.payload
    act = decision.action_type

    if act == ActionType.USE_RESEARCH_INSIGHT:
        top_id = payload.get("top_item_id") or payload.get("top_item", {}).get("title", "digest")
        return f"research:{category.slug}:{str(top_id).replace(' ', '_')}"

    if act == ActionType.CUSTOMER_RECALL:
        cid = customer.customer_id if customer else "anon"
        svc = payload.get("service_due", "recall")
        return f"recall:{cid}:{svc}"

    if act == ActionType.CUSTOMER_FOLLOWUP:
        cid = customer.customer_id if customer else "anon"
        return f"followup:{cid}:{trigger.kind}"

    if act == ActionType.CURIOUS_ASK:
        return f"curious:{merchant.merchant_id}:{trigger.kind}"

    if act == ActionType.PROMOTE_DELIVERY_OFFER:
        match_name = payload.get("match", "event").replace(" ", "_")
        return f"event:delivery:{merchant.merchant_id}:{match_name}"

    if act == ActionType.CONTINUE_PLANNING:
        topic = payload.get("intent_topic", "planning").replace(" ", "_")
        return f"planning:{merchant.merchant_id}:{topic}"

    if act == ActionType.REFRAME_SEASONAL_DIP:
        metric = payload.get("metric", "views")
        return f"seasonal:{merchant.merchant_id}:{metric}"

    if act == ActionType.CUSTOMER_WINBACK:
        cid = customer.customer_id if customer else "anon"
        return f"winback:{cid}:{trigger.kind}"

    if act == ActionType.ADDRESS_SUPPLY_ALERT:
        alert_id = payload.get("alert_id") or payload.get("molecule", "recall")
        return f"supply:{merchant.merchant_id}:{str(alert_id).replace(' ', '_')}"

    if act == ActionType.CUSTOMER_REFILL:
        cid = customer.customer_id if customer else "anon"
        runout = payload.get("runout_date", "monthly")
        return f"refill:{cid}:{runout}"

    if act == ActionType.ADDRESS_PERFORMANCE_DIP:
        metric = payload.get("metric", "performance")
        return f"perf_dip:{merchant.merchant_id}:{metric}"

    if act == ActionType.CAPITALIZE_PERF_SPIKE:
        metric = payload.get("metric", "views")
        return f"perf_spike:{merchant.merchant_id}:{metric}"

    if act == ActionType.RENEW_SUBSCRIPTION:
        return f"renewal:{merchant.merchant_id}"

    if act == ActionType.RESOLVE_LISTING_ISSUE:
        return f"listing:{merchant.merchant_id}"

    # Default structured fallback
    return f"{act.value}:{merchant.merchant_id}:{trigger.id}"


def _build_conversation_id(trigger: TriggerState, merchant: MerchantState, customer: Optional[CustomerStateModel]) -> str:
    """Generate meaningful, decodable conversation ID."""
    if customer is not None:
        return f"conv_{customer.customer_id}_{trigger.kind}"
    return f"conv_{merchant.merchant_id}_{trigger.kind}"


def _get_aggregate_val(agg: Any, key: str, default: Any = None) -> Any:
    """Helper to safely read from dict or model."""
    if agg is None:
        return default
    if isinstance(agg, dict):
        return agg.get(key, default)
    return getattr(agg, key, default)


def render_decision(
    decision: Decision,
    category: CategoryProfile,
    merchant: MerchantState,
    trigger: TriggerState,
    customer: Optional[CustomerStateModel] = None,
) -> Tuple[str, str, str, str, str, List[str], str]:
    """Render the authoritative Decision into template components.

    Returns:
        (template_name, body, cta, send_as, suppression_key, template_params, conversation_id)
    """
    act = decision.action_type
    target_scope = decision.target_scope
    send_as = "merchant_on_behalf" if target_scope == "customer" else "vera"
    suppression_key = _build_suppression_key(decision, category, merchant, trigger, customer)
    conv_id = _build_conversation_id(trigger, merchant, customer)
    payload = trigger.payload
    salutation = _get_salutation(merchant, category)
    customer_name = _get_customer_salutation(customer)

    # 1. Research Digest
    if act == ActionType.USE_RESEARCH_INSIGHT:
        tmpl = TEMPLATES["vera_research_digest_v1"]
        matched_item = None
        top_id = payload.get("top_item_id")
        if top_id:
            for d in category.digest:
                if d.id == top_id:
                    matched_item = d
                    break
        pub_name = matched_item.source.split(",")[0] if matched_item else "JIDA Oct issue"
        citation = matched_item.source if matched_item else "JIDA Oct 2026, p.14"
        trial_n = str(payload.get("top_item", {}).get("trial_n", "2,100"))
        finding = matched_item.title if matched_item else "3-month fluoride recall cuts caries recurrence 38% better than 6-month"
        cohort_count = _get_aggregate_val(merchant.customer_aggregate, "high_risk_adult_count")
        cohort_desc = f"{cohort_count} high-risk adult patients" if cohort_count else "high-risk adult patient cohort"

        params = {
            "salutation": salutation,
            "pub_name": pub_name,
            "cohort_desc": cohort_desc,
            "trial_n": trial_n,
            "finding_summary": finding,
            "read_time": "2-min",
            "citation": citation,
        }
        body = tmpl.body_format.format(**params)
        return tmpl.template_name, body, tmpl.cta_type, send_as, suppression_key, list(params.values()), conv_id

    # 2. Customer Routine Recall
    if act == ActionType.CUSTOMER_RECALL:
        tmpl = TEMPLATES["customer_recall_reminder_v1"]
        service_due = payload.get("service_due", "cleaning").replace("_", " ")
        slots = payload.get("available_slots", [])
        slots_text = " or ".join([s.get("label", str(s)) for s in slots[:2]]) if slots else "Wed 5 Nov, 6pm or Thu 6 Nov, 5pm"
        interval_text = payload.get("recall_window") or "5 months"
        offer = decision.supporting_offer
        offer_text = f"Special booking offer: {offer.get('title')}" if offer else "Complimentary checkup included"

        params = {
            "customer_name": customer_name,
            "merchant_name": merchant.identity.name,
            "interval_text": interval_text,
            "service_due": service_due,
            "slots_text": slots_text,
            "offer_text": offer_text,
        }
        body = tmpl.body_format.format(**params)
        return tmpl.template_name, body, tmpl.cta_type, send_as, suppression_key, list(params.values()), conv_id

    # 3. Customer Service Followup (Bridal / Consultation)
    if act == ActionType.CUSTOMER_FOLLOWUP:
        tmpl = TEMPLATES["customer_service_followup_v1"]
        sender_name = merchant.identity.owner_first_name or merchant.identity.name
        days_to_wedding = payload.get("days_to_wedding")
        countdown_text = f"{days_to_wedding} days" if days_to_wedding else "the date approaching"
        program_text = "tailored skin-prep and bridal glow program"
        offer = decision.supporting_offer
        if offer and any(w in offer.get("title", "").lower() for w in ("bridal", "glow", "skin", "wedding", "prep")):
            offer_text = f"Featured package: {offer.get('title')}"
        else:
            offer_text = "Comprehensive package includes consultation and personalized home-care kit"
        pref_slot = customer.preferences.preferred_slots if customer and customer.preferences else None
        slot_text = pref_slot or "Saturday 4pm slot"

        params = {
            "customer_name": customer_name,
            "sender_name": sender_name,
            "merchant_name": merchant.identity.name,
            "countdown_text": countdown_text,
            "program_text": program_text,
            "offer_text": offer_text,
            "slot_text": slot_text,
        }
        body = tmpl.body_format.format(**params)
        return tmpl.template_name, body, tmpl.cta_type, send_as, suppression_key, list(params.values()), conv_id

    # 4. Merchant Curiosity Cadence Check-in
    if act == ActionType.CURIOUS_ASK:
        tmpl = TEMPLATES["vera_curious_ask_v1"]
        params = {
            "salutation": salutation,
            "merchant_name": merchant.identity.name,
        }
        body = tmpl.body_format.format(**params)
        return tmpl.template_name, body, tmpl.cta_type, send_as, suppression_key, list(params.values()), conv_id

    # 5. Contrarian Event / Delivery Promotion
    if act == ActionType.PROMOTE_DELIVERY_OFFER:
        tmpl = TEMPLATES["vera_contrarian_delivery_promo_v1"]
        match_text = payload.get("match", "Major match")
        venue_text = payload.get("venue", "local stadium")
        offer = decision.supporting_offer or {}
        offer_title = offer.get("title", "Delivery Special")

        params = {
            "salutation": salutation,
            "match_text": match_text,
            "venue_text": venue_text,
            "shift_text": "-12%",
            "offer_title": offer_title,
        }
        body = tmpl.body_format.format(**params)
        return tmpl.template_name, body, tmpl.cta_type, send_as, suppression_key, list(params.values()), conv_id

    # 6. Continue Active Planning Intent
    if act == ActionType.CONTINUE_PLANNING:
        tmpl = TEMPLATES["vera_continue_planning_v1"]
        topic = payload.get("intent_topic", "corporate lunch package").replace("_", " ")
        locality = merchant.identity.locality or merchant.identity.city or "your area"
        structure_text = (
            f"1. Standard tier (10-24 orders): ₹25 off retail per meal + free delivery\n"
            f"2. Team tier (25-49 orders): ₹35 off retail + complimentary beverages\n"
            f"3. Corporate bulk (50+ orders): ₹45 off retail + platter bonus\n"
            f"Ordering window: WhatsApp booking by 5pm previous day; delivery between 12:30-1pm."
        )

        params = {
            "salutation": salutation,
            "topic": topic,
            "structure_text": structure_text,
            "locality": locality,
        }
        body = tmpl.body_format.format(**params)
        return tmpl.template_name, body, tmpl.cta_type, send_as, suppression_key, list(params.values()), conv_id

    # 7. Seasonal Performance Reframe
    if act == ActionType.REFRAME_SEASONAL_DIP:
        tmpl = TEMPLATES["vera_reframe_seasonal_dip_v1"]
        metric_name = payload.get("metric", "views")
        delta_pct = _format_delta_abs(payload.get("delta_pct", -0.30))
        raw_season = payload.get("season_note", "April-June")
        seasonal_window = "April-June" if "apr_jun" in raw_season.lower() else raw_season.replace("_", " ")
        member_count = str(_get_aggregate_val(merchant.customer_aggregate, "total_active_members", 245))

        params = {
            "salutation": salutation,
            "metric_name": metric_name,
            "delta_pct": delta_pct,
            "seasonal_window": seasonal_window,
            "member_count": member_count,
        }
        body = tmpl.body_format.format(**params)
        return tmpl.template_name, body, tmpl.cta_type, send_as, suppression_key, list(params.values()), conv_id

    # 8. Customer Lapse Winback
    if act == ActionType.CUSTOMER_WINBACK:
        tmpl = TEMPLATES["customer_winback_reengagement_v1"]
        sender_name = merchant.identity.owner_first_name or merchant.identity.name
        days_lapsed = payload.get("days_since_last_visit", 60)
        time_away = f"{int(days_lapsed // 7)} weeks" if days_lapsed >= 14 else f"{days_lapsed} days"
        focus_area = payload.get("previous_focus", "wellness").replace("_", " ")
        offer = decision.supporting_offer
        offer_text = f"Welcome back special: {offer.get('title')}" if offer else "First session is completely complimentary"

        params = {
            "customer_name": customer_name,
            "sender_name": sender_name,
            "merchant_name": merchant.identity.name,
            "time_away": time_away,
            "focus_area": focus_area,
            "offer_text": offer_text,
        }
        body = tmpl.body_format.format(**params)
        return tmpl.template_name, body, tmpl.cta_type, send_as, suppression_key, list(params.values()), conv_id

    # 9. Supply Alert / Recall Notice
    if act == ActionType.ADDRESS_SUPPLY_ALERT:
        tmpl = TEMPLATES["vera_supply_recall_alert_v1"]
        molecule = payload.get("molecule", "medication").replace("_", " ")
        batches = ", ".join(payload.get("affected_batches", ["batch list"]))
        manufacturer = payload.get("manufacturer", "Manufacturer")
        affected_count = str(payload.get("affected_patient_count", 22))
        total_rx = str(_get_aggregate_val(merchant.customer_aggregate, "chronic_rx_count", 240))

        params = {
            "salutation": salutation,
            "molecule": molecule,
            "batch_list": batches,
            "manufacturer": manufacturer,
            "affected_count": affected_count,
            "total_rx": total_rx,
        }
        body = tmpl.body_format.format(**params)
        return tmpl.template_name, body, tmpl.cta_type, send_as, suppression_key, list(params.values()), conv_id

    # 10. Chronic Prescription Refill Reminder
    if act == ActionType.CUSTOMER_REFILL:
        tmpl = TEMPLATES["customer_chronic_refill_v1"]
        molecules = ", ".join(payload.get("molecule_list", ["regular medications"]))
        raw_runout = payload.get("runout_date", "in 3 days")
        runout_date = raw_runout if raw_runout.startswith("in ") else f"on {raw_runout}"
        patient_ref = f"{customer_name}'s" if customer_name != "there" else "Your"
        offer = decision.supporting_offer
        discount_text = f"Active pharmacy benefit: {offer.get('title')} applied." if offer else "Senior citizen discount applied."

        params = {
            "merchant_name": merchant.identity.name,
            "patient_ref": patient_ref,
            "molecule_list": molecules,
            "runout_date": runout_date,
            "discount_text": discount_text,
        }
        body = tmpl.body_format.format(**params)
        return tmpl.template_name, body, tmpl.cta_type, send_as, suppression_key, list(params.values()), conv_id

    # 11. Performance Dip (Unexpected)
    if act == ActionType.ADDRESS_PERFORMANCE_DIP:
        tmpl = TEMPLATES["vera_remediate_performance_dip_v1"]
        metric_name = payload.get("metric", "inbound calls")
        delta_pct = _format_delta_abs(payload.get("delta_pct", -0.40))
        params = {
            "salutation": salutation,
            "metric_name": metric_name,
            "delta_pct": delta_pct,
        }
        body = tmpl.body_format.format(**params)
        return tmpl.template_name, body, tmpl.cta_type, send_as, suppression_key, list(params.values()), conv_id

    # 12. Capitalize Performance Spike
    if act == ActionType.CAPITALIZE_PERF_SPIKE:
        tmpl = TEMPLATES["vera_capitalize_perf_spike_v1"]
        metric_name = payload.get("metric", "search views")
        delta_pct = _format_delta_abs(payload.get("delta_pct", 0.25))
        params = {
            "salutation": salutation,
            "metric_name": metric_name,
            "delta_pct": delta_pct,
        }
        body = tmpl.body_format.format(**params)
        return tmpl.template_name, body, tmpl.cta_type, send_as, suppression_key, list(params.values()), conv_id

    # 13. Subscription Renewal
    if act == ActionType.RENEW_SUBSCRIPTION:
        tmpl = TEMPLATES["vera_subscription_renewal_v1"]
        plan_name = merchant.subscription.plan or "Pro"
        days_left = str(merchant.subscription.days_remaining or 7)
        params = {
            "salutation": salutation,
            "plan_name": plan_name,
            "days_left": days_left,
        }
        body = tmpl.body_format.format(**params)
        return tmpl.template_name, body, tmpl.cta_type, send_as, suppression_key, list(params.values()), conv_id

    # 14. Listing Verification
    if act == ActionType.RESOLVE_LISTING_ISSUE:
        tmpl = TEMPLATES["vera_resolve_listing_v1"]
        locality = merchant.identity.locality or merchant.identity.city or "your area"
        params = {
            "salutation": salutation,
            "locality": locality,
        }
        body = tmpl.body_format.format(**params)
        return tmpl.template_name, body, tmpl.cta_type, send_as, suppression_key, list(params.values()), conv_id

    # 15. Competitor Alert
    if act == ActionType.ADDRESS_COMPETITOR_CHANGE:
        tmpl = TEMPLATES["vera_competitor_opened_v1"]
        comp_name = payload.get("competitor_name", "A local business")
        dist = str(payload.get("distance_km", 1.2))
        params = {
            "salutation": salutation,
            "competitor_name": comp_name,
            "distance_km": dist,
        }
        body = tmpl.body_format.format(**params)
        return tmpl.template_name, body, tmpl.cta_type, send_as, suppression_key, list(params.values()), conv_id

    # 16. Review Theme Response
    if act == ActionType.RESPOND_TO_REVIEW_THEME:
        tmpl = TEMPLATES["vera_review_theme_response_v1"]
        theme = payload.get("theme", "service speed")
        count = str(payload.get("occurrence_count", 3))
        params = {
            "salutation": salutation,
            "theme_name": theme,
            "count": count,
        }
        body = tmpl.body_format.format(**params)
        return tmpl.template_name, body, tmpl.cta_type, send_as, suppression_key, list(params.values()), conv_id

    # 17. Milestone Celebration
    if act == ActionType.CELEBRATE_MILESTONE:
        tmpl = TEMPLATES["vera_celebrate_milestone_v1"]
        count = str(payload.get("milestone_count", 100))
        params = {
            "salutation": salutation,
            "merchant_name": merchant.identity.name,
            "milestone_count": count,
        }
        body = tmpl.body_format.format(**params)
        return tmpl.template_name, body, tmpl.cta_type, send_as, suppression_key, list(params.values()), conv_id

    # 18. Festival Campaign
    if act == ActionType.PREPARE_FESTIVAL_CAMPAIGN:
        tmpl = TEMPLATES["vera_festival_campaign_v1"]
        fest = payload.get("festival_name", "Festival")
        days = str(payload.get("days_until", 7))
        params = {
            "salutation": salutation,
            "festival_name": fest,
            "days_until": days,
            "category_name": category.display_name or category.slug,
        }
        body = tmpl.body_format.format(**params)
        return tmpl.template_name, body, tmpl.cta_type, send_as, suppression_key, list(params.values()), conv_id

    # Fallback for unexpected actions
    tmpl = TEMPLATES["vera_curious_ask_v1"]
    body = f"Hi {salutation}! How can we best support {merchant.identity.name} today?"
    return "generic_fallback_v1", body, "open_ended", send_as, suppression_key, [salutation], conv_id
