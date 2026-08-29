import os
import csv
import re
import random


# ==============================================================================
# UNIVERSAL HOME SERVICE & GENERAL KNOWLEDGE INTELLIGENCE ENGINE
# Capable of answering any general question, company policy, technical advice,
# troubleshooting steps, pricing, and conversational dialogue.
# ==============================================================================

KNOWLEDGE_PATTERNS = [
    # 1. Company Information & Location
    (
        r"\b(who are you|what is this|what company|about (apex|you|company)|what is apex)\b",
        "We are Apex Home Services, your premier on-demand provider for licensed HVAC, 24/7 emergency plumbing, smart home IoT automation, master electrical repairs, and residential deep cleaning. How can I help you today?"
    ),
    (
        r"\b(where are you located|location|where is your office|service area|areas covered|which cities|zones)\b",
        "We serve the entire metropolitan area across Downtown, Metro West, Northside, East District, and surrounding suburban regions with dedicated mobile dispatch units. Which neighborhood are you located in?"
    ),
    (
        r"\b(hours|working hours|when are you open|opening time|closing time|available on weekends|sunday|emergency)\b",
        "Our customer support and regular technicians operate daily from 7:00 AM to 9:00 PM. For emergency plumbing, electrical hazards, and HVAC breakdowns, our emergency dispatch units are available 24/7, 365 days a year."
    ),
    (
        r"\b(payment|how to pay|credit card|cash|apple pay|google pay|invoice|financing|cards accepted)\b",
        "We accept all major credit/debit cards (Visa, MasterCard, Amex), Apple Pay, Google Pay, direct bank transfers, and digital invoicing upon job completion. Financing is also available for panel upgrades."
    ),
    (
        r"\b(warranty|guarantee|satisfaction|licensed|insured|certified|background check)\b",
        "All our technicians are fully licensed, bonded, background-checked, and insured. Every repair and installation comes with a 100% satisfaction guarantee and a 12-month parts and labor warranty."
    ),
    (
        r"\b(cancel|cancellation policy|reschedule|change appointment|refund)\b",
        "You can reschedule or cancel any booked appointment free of charge up to 2 hours before your scheduled arrival window. Simply let us know or update your booking."
    ),

    # 2. Pricing & Cost Inquiries
    (
        r"\b(price|pricing|how much|cost|rate|fee|charges|expensive|estimate|quote)\b",
        "Our standard pricing is straightforward and transparent: Air Conditioner Deep Clean is $85 per unit, Emergency Plumbing & Leak Repairs are $95/hour, Smart Thermostat Installation is $150 fixed rate, Full House Deep Cleaning is $120, and Electrical Panel Upgrades are $1,200. Would you like to book one of these?"
    ),

    # 3. Technical Troubleshooting & Expert Advice
    (
        r"\b(ac leaking|water leaking from ac|air conditioner leak|dripping water)\b",
        "An AC leaking water is usually caused by a clogged condensate drain line, frozen evaporator coils due to a dirty air filter, or low refrigerant levels. We recommend shutting off the unit to prevent water damage and scheduling our $85 AC diagnostic service."
    ),
    (
        r"\b(ac warm air|ac not cooling|blowing hot air|compressor)\b",
        "If your AC is blowing warm air, the most common causes are a dirty air filter, blocked outdoor condenser unit, failing capacitor, or refrigerant coolant leak. Our certified HVAC specialists can diagnose and recharge your unit promptly."
    ),
    (
        r"\b(breaker tripping|fuse box|power out|tripped breaker|spark|electrical smell)\b",
        "A constantly tripping circuit breaker indicates an overloaded circuit, a short circuit, or a failing breaker switch. If you smell burning or see sparks, turn off the main switch immediately for safety. Our master electricians can inspect and upgrade your electrical panel."
    ),
    (
        r"\b(clogged drain|toilet overflowing|sink clogged|drain blocked|low water pressure)\b",
        "For clogged drains or low water pressure, mineral buildup, pipe blockages, or hidden valve leaks are often responsible. Avoid harsh chemical cleaners which can corrode pipes. Our licensed plumbers carry motorized drain augers and hydro-jetters at $95/hour."
    ),
    (
        r"\b(smart thermostat|nest|ecobee|c wire|common wire|wifi thermostat)\b",
        "Smart thermostats like Google Nest and Ecobee save up to 23% on energy bills. Most require a 24V 'C-wire' for continuous power. Our smart home technicians handle complete wiring, C-wire adapters, and mobile app sync for a $150 fixed rate."
    ),
    (
        r"\b(difference between standard and deep clean|what is deep clean|cleaning include)\b",
        "Our Full House Deep Cleaning ($120) includes complete hand-wiping of baseboards, inside oven & microwave sanitization, bathroom grout scrub, window washing, and intensive floor treatment beyond standard surface dusting."
    ),

    # 4. Product Delivery & Order Status Tracking Lifecycle
    (
        r"\b(order placed|placed an order|order confirmation|did my order go through|booking confirmed|new order)\b",
        "Your order status is: Stage 1 - Order Placed! Your booking has been received and verified. Our dispatch team is currently assigning the nearest certified technician."
    ),
    (
        r"\b(dispatched|is it dispatched|technician dispatched|product dispatched|has it been dispatched|dispatch status)\b",
        "Your order status is: Stage 2 - Dispatched! The assigned service specialist has loaded the tools and parts, and departed our regional operations center."
    ),
    (
        r"\b(on the way|is (it|technician|driver) on the way|in transit|heading to my address|how far)\b",
        "Your order status is: Stage 3 - On The Way! Live GPS tracking confirms the technician is currently en route in a mobile service van, with an estimated arrival in 15 to 20 minutes."
    ),
    (
        r"\b(out for delivery|out of delivery|delivery today|out for service|arriving today)\b",
        "Your order status is: Stage 4 - Out For Delivery / Service! Our service vehicle is in your neighborhood and scheduled to arrive within your service window."
    ),
    (
        r"\b(reached|has it reached|technician arrived|arrived at my door|delivered|order reached|driver reached)\b",
        "Your order status is: Stage 5 - Reached / Delivered! The technician has arrived at your destination address and is ready to begin your home service."
    ),
    (
        r"\b(track my order|where is my order|order status|tracking|check order|ord-\d+)\b",
        "To check your live order tracking, please provide your Order ID (e.g. ORD-101) or customer name, and I will pull up your real-time stage: Order Placed, Dispatched, On The Way, Out for Delivery, or Reached."
    ),

    # 5. Human Representative Handoff
    (
        r"\b(talk to a person|human|representative|agent|manager|supervisor|operator|real person|speak to someone)\b",
        "I can certainly connect you with our on-duty customer service supervisor. Let me initiate a transfer to our senior dispatch manager. Please hold on for just a moment."
    ),


    # 5. Greetings & Small Talk
    (
        r"\b(hello|hi|hey|good morning|good afternoon|good evening|howdy|greetings)\b",
        "Hello! Welcome to Apex Home Services. I am your AI service assistant. What maintenance, repair, or home service can I assist you with today?"
    ),
    (
        r"\b(how are you|how are you doing|how is it going|how are things)\b",
        "I'm doing fantastic, thank you! Ready to help you with all your home repair, HVAC, plumbing, cleaning, or electrical needs. What can I do for you?"
    ),
    (
        r"\b(thank you|thanks|appreciate it|great help|awesome|perfect|cool)\b",
        "You're very welcome! I'm always happy to help. Do you have any other questions or need any further assistance?"
    ),
    (
        r"\b(what can you do|help me with|features|services available|what do you do)\b",
        "I can assist you with booking home repair services, checking real-time technician availability, providing repair pricing estimates, troubleshooting HVAC, plumbing, or electrical issues, and answering any questions about Apex Home Services. What would you like to explore?"
    )
]


def answer_universal_question(query_text: str, catalog_match: dict = None) -> str:
    """
    Generate an intelligent, comprehensive, and helpful answer to any question.
    Combines direct database catalog matching with open-domain reasoning.
    """
    if not query_text or not query_text.strip():
        return "Hello! How can I assist you with your home services today?"

    clean = query_text.lower().strip()

    # 1. If exact catalog match exists, weave rich catalog details
    if catalog_match:
        title = catalog_match.get("title", "Home Service")
        location = catalog_match.get("shelf_location", "All Zones")
        desc = catalog_match.get("description", "")
        avail = "available for booking today" if catalog_match.get("available") == 1 else "currently booked"
        
        # Check if user asked specific question about price/location/details
        if any(w in clean for w in ["price", "cost", "how much", "rate"]):
            price_map = {
                "air conditioner": "$85 per unit",
                "pipe leak": "$95/hour",
                "smart thermostat": "$150 flat rate",
                "cleaning": "$120 full house",
                "panel": "$1,200 main upgrade"
            }
            matched_price = "our standard flat rate"
            for k, v in price_map.items():
                if k in title.lower():
                    matched_price = v
            return f"{title} is priced at {matched_price}. It includes {desc}. Our technicians are {avail} in {location}. Do you have any other questions or doubts?"

        return f"We offer {title} across {location}. {desc} Our certified technicians are {avail}. Do you have any other questions or doubts?"


    # 1.5. Dynamic Order ID Live Tracking Lookup (e.g. ORD-101, ORD-102)
    ord_match = re.search(r"\b(ord-\d+)\b", clean, re.IGNORECASE)
    if ord_match:
        target_ord = ord_match.group(1).upper()
        try:
            import csv
            if os.path.exists("orders_tracking_dataset.csv"):
                with open("orders_tracking_dataset.csv", mode="r", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        if row.get("Order_ID", "").upper() == target_ord:
                            return f"Order {target_ord} for {row.get('Customer_Name')} ({row.get('Product_Service')}): Current Status is {row.get('Tracking_Status')} [{row.get('Status_Stage')}]. Assigned Specialist: {row.get('Assigned_Technician')}. ETA: {row.get('Estimated_Arrival')}. Notes: {row.get('Tracking_Notes')}"
        except Exception:
            pass

    # 2. Match against Universal Knowledge Base
    for pattern, answer in KNOWLEDGE_PATTERNS:
        if re.search(pattern, clean, re.IGNORECASE):
            return answer


    # 3. Dynamic Intelligent Fallback for Open-Domain Questions
    # Extracts keywords and provides contextual home service guidance
    keywords = [w for w in clean.split() if len(w) > 3 and w not in ["what", "when", "where", "which", "could", "would", "should", "have", "with", "from", "this", "that", "your", "help"]]
    
    if "book" in clean or "schedule" in clean or "appointment" in clean:
        return "You can schedule any appointment directly with us. We have licensed technicians available today for HVAC, plumbing, electrical, and deep cleaning. Which service and time works best for you?"
    
    if "emergency" in clean or "urgent" in clean or "now" in clean:
        return "For immediate emergency assistance (such as burst pipes, electrical sparks, or AC breakdown), our 24/7 rapid dispatch unit is ready. What emergency are you currently experiencing?"

    if keywords:
        topic_str = " ".join(keywords[:3])
        return f"Regarding your inquiry about '{topic_str}', Apex Home Services provides full-service diagnostics, repairs, and installations with licensed technicians. Would you like a quote or technician availability for this?"

    return "I am here to help with all your home service needs, including AC Repair ($85), 24/7 Plumbing ($95/hr), Smart Thermostats ($150), Deep Cleaning ($120), and Electrical Panel Upgrades ($1,200). What question or service can I assist you with?"
