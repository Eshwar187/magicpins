"""Deterministic template definitions for Vera message composition.

Each template defines structured text with exact placeholders that are substituted
exclusively from grounded decision facts and context models.
"""

from typing import Dict, List, NamedTuple


class TemplateDefinition(NamedTuple):
    template_name: str
    target_scope: str
    cta_type: str
    body_format: str
    required_params: List[str]


TEMPLATES: Dict[str, TemplateDefinition] = {
    # 1. Research Digest
    "vera_research_digest_v1": TemplateDefinition(
        template_name="vera_research_digest_v1",
        target_scope="merchant",
        cta_type="binary_yes_no",
        body_format=(
            "{salutation}, {pub_name}'s recent publication landed. One item directly relevant to your "
            "{cohort_desc} — a {trial_n}-patient study demonstrated that {finding_summary}. "
            "Worth reviewing ({read_time} summary). Would you like me to pull the abstract and draft "
            "a patient-education WhatsApp note you can share? — {citation}"
        ),
        required_params=["salutation", "pub_name", "cohort_desc", "trial_n", "finding_summary", "read_time", "citation"],
    ),

    # 2. Customer Routine Recall
    "customer_recall_reminder_v1": TemplateDefinition(
        template_name="customer_recall_reminder_v1",
        target_scope="customer",
        cta_type="multi_choice_slot",
        body_format=(
            "Hi {customer_name}, {merchant_name} here 🦷 It has been {interval_text} since your last visit "
            "— your routine {service_due} is due. We have slots ready for you: {slots_text}. "
            "{offer_text}. Reply 1 for the first slot, 2 for the second, or let us know a convenient time for you."
        ),
        required_params=["customer_name", "merchant_name", "interval_text", "service_due", "slots_text", "offer_text"],
    ),

    # 3. Customer Service Followup (Bridal / Trial)
    "customer_service_followup_v1": TemplateDefinition(
        template_name="customer_service_followup_v1",
        target_scope="customer",
        cta_type="binary_yes_no",
        body_format=(
            "Hi {customer_name} 💍 {sender_name} from {merchant_name} here. With {countdown_text} until your wedding, "
            "now is the ideal window to start your {program_text}. {offer_text}. "
            "Would you like me to reserve your preferred {slot_text} for your first session next week?"
        ),
        required_params=["customer_name", "sender_name", "merchant_name", "countdown_text", "program_text", "offer_text", "slot_text"],
    ),

    # 4. Merchant Curiosity Cadence Check-in
    "vera_curious_ask_v1": TemplateDefinition(
        template_name="vera_curious_ask_v1",
        target_scope="merchant",
        cta_type="open_ended",
        body_format=(
            "Hi {salutation}! Quick check — what service or item has been most asked-for this week at {merchant_name}? "
            "I will turn your answer into an updated Google Business post plus a quick 3-line customer reply template you can use. "
            "Takes just 5 minutes."
        ),
        required_params=["salutation", "merchant_name"],
    ),

    # 5. Contrarian Event / Delivery Promotion
    "vera_contrarian_delivery_promo_v1": TemplateDefinition(
        template_name="vera_contrarian_delivery_promo_v1",
        target_scope="merchant",
        cta_type="binary_yes_no",
        body_format=(
            "Quick update {salutation} — {match_text} tonight ({venue_text}). Important heads-up: weekend match "
            "evenings typically shift dine-in restaurant covers by {shift_text} as customers watch from home. "
            "Skip the dine-in push tonight; instead feature your active offer \"{offer_title}\" as a delivery special. "
            "Would you like me to draft the delivery promo banner and social story announcement? Ready in 10 minutes."
        ),
        required_params=["salutation", "match_text", "venue_text", "shift_text", "offer_title"],
    ),

    # 6. Active Planning Intent Continuation
    "vera_continue_planning_v1": TemplateDefinition(
        template_name="vera_continue_planning_v1",
        target_scope="merchant",
        cta_type="binary_yes_no",
        body_format=(
            "{salutation}, here is a concrete starter structure for your {topic} package — you can review and adjust:\n\n"
            "{structure_text}\n\n"
            "Local workplace offices in {locality} are within your service radius. Would you like me to draft a concise "
            "outreach note to share with their facilities coordinators?"
        ),
        required_params=["salutation", "topic", "structure_text", "locality"],
    ),

    # 7. Seasonal Performance Reframe
    "vera_reframe_seasonal_dip_v1": TemplateDefinition(
        template_name="vera_reframe_seasonal_dip_v1",
        target_scope="merchant",
        cta_type="binary_yes_no",
        body_format=(
            "{salutation}, your {metric_name} is down {delta_pct}% this week — but please note this matches the typical "
            "{seasonal_window} category acquisition lull. Recommended strategy: pause unnecessary ad spend right now and protect "
            "your budget for the peak season. In the meantime, concentrate retention on your {member_count} active members. "
            "Would you like me to prepare a seasonal attendance challenge draft to keep them engaged through this window?"
        ),
        required_params=["salutation", "metric_name", "delta_pct", "seasonal_window", "member_count"],
    ),

    # 8. Customer Lapse Winback
    "customer_winback_reengagement_v1": TemplateDefinition(
        template_name="customer_winback_reengagement_v1",
        target_scope="customer",
        cta_type="binary_yes_no",
        body_format=(
            "Hi {customer_name} 👋 {sender_name} from {merchant_name} here. It has been about {time_away} since your last visit "
            "— this happens to most members and there is zero judgment. We have introduced a schedule that aligns well with your "
            "{focus_area} goals. {offer_text}. Reply YES if you would like me to hold a free trial spot for you — no commitment and no auto-charge."
        ),
        required_params=["customer_name", "sender_name", "merchant_name", "time_away", "focus_area", "offer_text"],
    ),

    # 9. Supply Alert / Recall Notice
    "vera_supply_recall_alert_v1": TemplateDefinition(
        template_name="vera_supply_recall_alert_v1",
        target_scope="merchant",
        cta_type="binary_yes_no",
        body_format=(
            "{salutation}, urgent update: voluntary manufacturer recall announced for {molecule} batches ({batch_list}) by {manufacturer} "
            "due to sub-potency (no safety risk reported, but replacement is required). Based on your repeat records, {affected_count} of your "
            "{total_rx} chronic-Rx patients were dispensed these batches recently. Would you like me to draft their patient notification note "
            "and replacement-pickup steps?"
        ),
        required_params=["salutation", "molecule", "batch_list", "manufacturer", "affected_count", "total_rx"],
    ),

    # 10. Chronic Prescription Refill Reminder
    "customer_chronic_refill_v1": TemplateDefinition(
        template_name="customer_chronic_refill_v1",
        target_scope="customer",
        cta_type="binary_confirm",
        body_format=(
            "Namaste — {merchant_name} here. {patient_ref} monthly medicines ({molecule_list}) are scheduled to run out on {runout_date}. "
            "Your regular brands and dosages are packed and ready. {discount_text} Free home delivery to your saved address. "
            "Reply CONFIRM to arrange dispatch, or call us if there is any update to your prescription."
        ),
        required_params=["merchant_name", "patient_ref", "molecule_list", "runout_date", "discount_text"],
    ),

    # 11. Performance Dip (Unexpected)
    "vera_remediate_performance_dip_v1": TemplateDefinition(
        template_name="vera_remediate_performance_dip_v1",
        target_scope="merchant",
        cta_type="binary_yes_no",
        body_format=(
            "{salutation}, quick alert on your 7-day metrics: inbound {metric_name} dropped {delta_pct}% week-over-week. "
            "To restore search visibility, I recommend updating your Google listing with fresh weekly photos and launching a targeted local promotion. "
            "Would you like me to prepare a ready-to-publish update for your profile?"
        ),
        required_params=["salutation", "metric_name", "delta_pct"],
    ),

    # 12. Capitalize Performance Spike
    "vera_capitalize_perf_spike_v1": TemplateDefinition(
        template_name="vera_capitalize_perf_spike_v1",
        target_scope="merchant",
        cta_type="binary_yes_no",
        body_format=(
            "Great news {salutation}! Your {metric_name} surged +{delta_pct}% this week. To convert this extra traffic into long-term regulars, "
            "I recommend promoting your signature service with a time-limited welcome offer. Would you like me to draft the promotional post?"
        ),
        required_params=["salutation", "metric_name", "delta_pct"],
    ),

    # 13. Subscription Renewal
    "vera_subscription_renewal_v1": TemplateDefinition(
        template_name="vera_subscription_renewal_v1",
        target_scope="merchant",
        cta_type="binary_yes_no",
        body_format=(
            "{salutation}, your magicpin {plan_name} subscription has {days_left} days remaining. Renewing your plan now ensures "
            "uninterrupted listing optimization, Google Business Profile management, and customer messaging support. "
            "Would you like to review the renewal details?"
        ),
        required_params=["salutation", "plan_name", "days_left"],
    ),

    # 14. Listing Verification
    "vera_resolve_listing_v1": TemplateDefinition(
        template_name="vera_resolve_listing_v1",
        target_scope="merchant",
        cta_type="binary_yes_no",
        body_format=(
            "{salutation}, your Google Business Profile is currently unverified. Verified local listings in {locality} receive significantly "
            "higher customer calls and directions. Would you like me to guide you through the quick verification steps today?"
        ),
        required_params=["salutation", "locality"],
    ),

    # 15. Competitor Alert
    "vera_competitor_opened_v1": TemplateDefinition(
        template_name="vera_competitor_opened_v1",
        target_scope="merchant",
        cta_type="binary_yes_no",
        body_format=(
            "{salutation}, heads-up: a new competitor ({competitor_name}) recently listed approximately {distance_km} km from your location. "
            "To protect your local market share, I recommend highlighting your signature offerings and verified customer reviews. "
            "Would you like me to draft a showcase post?"
        ),
        required_params=["salutation", "competitor_name", "distance_km"],
    ),

    # 16. Review Theme Response
    "vera_review_theme_response_v1": TemplateDefinition(
        template_name="vera_review_theme_response_v1",
        target_scope="merchant",
        cta_type="binary_yes_no",
        body_format=(
            "{salutation}, recent customer reviews highlight feedback around \"{theme_name}\" ({count} recent mentions). "
            "Proactively acknowledging this feedback reassures prospective clients. Would you like me to prepare a constructive response template "
            "for your review replies?"
        ),
        required_params=["salutation", "theme_name", "count"],
    ),

    # 17. Milestone Celebration
    "vera_celebrate_milestone_v1": TemplateDefinition(
        template_name="vera_celebrate_milestone_v1",
        target_scope="merchant",
        cta_type="binary_yes_no",
        body_format=(
            "Congratulations {salutation}! {merchant_name} just crossed {milestone_count} customer reviews on Google. "
            "Milestone achievements provide fantastic local credibility. Would you like me to prepare a celebratory thank-you post for your customers?"
        ),
        required_params=["salutation", "merchant_name", "milestone_count"],
    ),

    # 18. Festival Campaign
    "vera_festival_campaign_v1": TemplateDefinition(
        template_name="vera_festival_campaign_v1",
        target_scope="merchant",
        cta_type="binary_yes_no",
        body_format=(
            "{salutation}, {festival_name} is coming up in {days_until} days. Festive demand for {category_name} increases significantly "
            "during this period. Would you like me to draft a dedicated festive campaign and promotional package for your customers?"
        ),
        required_params=["salutation", "festival_name", "days_until", "category_name"],
    ),
}
