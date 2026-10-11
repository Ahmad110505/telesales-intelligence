"""
Sales Knowledge Base and Playbook Retrieval Service.
Provides company-specific telesales policies, objection rebuttals, and rubrics
grounded in Jordanian market dynamics (telecom, insurance, banking).
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class SalesPlaybookRule(BaseModel):
    rule_id: str
    category: str
    title_ar: str
    title_en: str
    recommended_technique_ar: str
    recommended_technique_en: str
    example_script_ar: str
    example_script_en: str
    rubric_guidance: str


DEFAULT_SALES_RULES: List[SalesPlaybookRule] = [
    # 1. Price Objection Handling
    SalesPlaybookRule(
        rule_id="RULE-PRICE-01",
        category="price",
        title_ar="معالجة اعتراض السعر عبر إبراز القيمة والفرق التقني",
        title_en="Price Objection: Value Framing & Technical Differentiation",
        recommended_technique_ar="توضيح العائد على الاستثمار وثبات الخط (فايبر مقابل 4G) أو سرعة التحميل والرفع، مع عدم تخفيض السعر فوراً قبل فهم حجم الاستخدام.",
        recommended_technique_en="Reframe cost around speed stability, upload bandwidth, and bundled savings before offering standard discounts.",
        example_script_ar="أكيد بعرف إنه السعر نقطة مهمة لحضرتك، بس شو سرعة النت الحالية عندك؟ لأن باقة الـ 300 ميجا بتعطيك فايبر مباشر بدون تقطيع لك وللعيلة كاملة وبتوفر عليك اشتراكات ثانية.",
        example_script_en="I completely understand price is key. What speed are you currently running? Our 300 Mbps fiber guarantees zero lag across all household devices.",
        rubric_guidance="Agent must not simply repeat the price or drop the call without exploring customer's usage or breaking down daily value."
    ),
    # 2. Timing Objection Handling
    SalesPlaybookRule(
        rule_id="RULE-TIMING-01",
        category="timing",
        title_ar="معالجة اعتراض التوقيت وتأجيل المكالمة",
        title_en="Timing Objection: Securing Scheduled Callback",
        recommended_technique_ar="احترام وقت العميل فوراً والاتفاق على موعد دقيق ومحدد لإعادة الاتصال بدلاً من إنهاء المكالمة دون أفق.",
        recommended_technique_en="Acknowledge time constraint respectfully and lock in a specific callback time rather than a vague dismissal.",
        example_script_ar="ولا يهمك يا هلا، مقدر وقتك تماماً. بناسبك أرجع اتصل بحضرتك اليوم العصر على الساعة 4 ولا بكرة الصبح أفضل؟",
        example_script_en="Understood completely, I appreciate you are busy. Would 4 PM this afternoon or tomorrow morning be better for a quick 2-minute follow-up?",
        rubric_guidance="Agent must acknowledge the customer's urgency and propose two specific callback slots."
    ),
    # 3. Competitor Comparison
    SalesPlaybookRule(
        rule_id="RULE-COMP-01",
        category="competitor",
        title_ar="المقارنة مع الشركات المنافسة",
        title_en="Competitor Comparison: Superior Service & Local Coverage",
        recommended_technique_ar="تجنب ذم المنافس، والتركيز على نقاط القوة الحصرية (جهاز الراوتر المتطور، راوتر WiFi 6 مجاني، دعم فني 24/7، خدمة التركيب خلال 24 ساعة).",
        recommended_technique_en="Validate competitor brand respectfully while highlighting unique value drivers (WiFi 6 router, SLA, 24h installation).",
        example_script_ar="الشركات الثانية ممتازة، بس الميزة عندنا إنه التركيب مجاني خلال 24 ساعة وبنركبلك أحدث راوتر فايبر 6 بيغطي البيت كامل مع صيانة مجانية.",
        example_script_en="They offer good services, but our offer includes free next-day installation with WiFi 6 coverage guaranteed across your whole home.",
        rubric_guidance="Agent must highlight unique differentiators without disparaging competitors."
    ),
    # 4. Authority Objection
    SalesPlaybookRule(
        rule_id="RULE-AUTH-01",
        category="authority",
        title_ar="اعتراض سلطة القرار واستشارة الأهل/الشريك",
        title_en="Authority Objection: Consultation with Partner/Family",
        recommended_technique_ar="تأييد رغبة العميل في الاستشارة وتزويده بالنقاط الجوهرية والخصم المؤقت لمساعدته في اتخاذ القرار.",
        recommended_technique_en="Support consultation, summarize key perks via WhatsApp/SMS, and schedule follow-up with all decision makers.",
        example_script_ar="حقك طبعاً تستشير الأهل. رح أبعثلك تفاصيل العرض والخصم الخاص بمسج عشان تكون واضحة إلك وإلهم، وبنتواصل بكرة لنثبت العرض.",
        example_script_en="Of course, that makes total sense. Let me send a quick summary of the promo via SMS so you have the numbers in hand for your discussion.",
        rubric_guidance="Agent should validate consultation and equip caller with concise value bullet points."
    ),
    # 5. Missed Discovery Rubric
    SalesPlaybookRule(
        rule_id="RUBRIC-DISC-01",
        category="missed_discovery",
        title_ar="معيار استكشاف احتياج العميل",
        title_en="Customer Needs Discovery Standard",
        recommended_technique_ar="طرح سؤالين مفتوحين على الأقل حول الاستخدام الحالي أو الصعوبات التي يواجهها قبل عرض الباقات.",
        recommended_technique_en="Ask at least two open-ended questions about current setup, pain points, or usage before pitching specific bundles.",
        example_script_ar="حالياً كم جهاز بكون شابك على النت بنفس الوقت؟ وهل بتواجهوا بطء بالتحميل أو ألعاب الأونلاين؟",
        example_script_en="How many devices usually stream simultaneously at home, and do you experience slowdowns during peak hours?",
        rubric_guidance="Calling out package pricing without knowing family/business usage profile constitutes a discovery leakage."
    ),
    # 6. Missed Next Step Rubric
    SalesPlaybookRule(
        rule_id="RUBRIC-CLOSE-01",
        category="missed_next_step",
        title_ar="معيار تحديد الخطوة القادمة والإغلاق",
        title_en="Call Closing and Next Step Standard",
        recommended_technique_ar="الاتفاق على إجراء واضح ومحدد زمنيًا في نهاية المكالمة (تحديد موعد التركيب، إرسال رابط الدفع، أو موعد محدد للمعاودة).",
        recommended_technique_en="Always conclude with a concrete, scheduled commitment (installation booking, payment link, or exact callback time).",
        example_script_ar="تمام يا هلا، رح أثبتلك طلب التركيب ليوم الأربعاء الصباحي، وبمر الفني بين 10 و 12، اتفقنا؟",
        example_script_en="Great, I will secure your installation slot for Wednesday between 10 AM and 12 PM. Does that work for you?",
        rubric_guidance="Ending call with 'فكر بالموضوع ورنلنا' without follow-up commitment is an observed closing leakage."
    )
]


class SalesKnowledgeBase:
    """
    In-memory / repository-backed knowledge store for sales rubrics and coaching playbooks.
    """
    def __init__(self, rules: Optional[List[SalesPlaybookRule]] = None):
        self.rules = rules or DEFAULT_SALES_RULES

    def get_guidance_for_objection(self, category: str) -> Optional[SalesPlaybookRule]:
        cat_lower = category.lower().strip()
        for rule in self.rules:
            if rule.category == cat_lower:
                return rule
        return None

    def get_rubric_for_leakage(self, category: str) -> Optional[SalesPlaybookRule]:
        cat_lower = category.lower().strip()
        for rule in self.rules:
            if rule.category == cat_lower:
                return rule
        return None

    def get_all_rules(self) -> List[SalesPlaybookRule]:
        return self.rules
