"""
Dedicated service interface for LLM operations via the Cohere API.
Handles client configuration, structured JSON generation, retries, timeouts,
and provides a deterministic offline fallback for Jordanian Arabic dialect testing.
"""

from abc import ABC, abstractmethod
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

import cohere
from cohere.core.request_options import RequestOptions

from app.config import settings

logger = logging.getLogger(__name__)


class BaseLLMClient(ABC):
    """Abstract interface isolating model provider access from business services."""

    @abstractmethod
    def generate_chat_completion(
        self,
        messages: List[Dict[str, str]],
        json_mode: bool = True
    ) -> str:
        """Executes a chat completion call and returns the text response."""
        pass


class CohereLLMClient(BaseLLMClient):
    """
    Production client accessing pretrained Cohere models via the official Cohere ClientV2 API.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        timeout_seconds: Optional[int] = None,
        max_retries: Optional[int] = None
    ):
        self.api_key = api_key or settings.COHERE_API_KEY
        self.model = model or settings.COHERE_MODEL
        self.temperature = temperature if temperature is not None else settings.COHERE_TEMPERATURE
        self.timeout_seconds = timeout_seconds or settings.COHERE_TIMEOUT_SECONDS
        self.max_retries = max_retries if max_retries is not None else settings.COHERE_MAX_RETRIES

        if not self.api_key:
            raise ValueError("COHERE_API_KEY must be provided for CohereLLMClient.")

        self.client = cohere.ClientV2(
            api_key=self.api_key,
            timeout=float(self.timeout_seconds),
            max_retries=self.max_retries
        )

    def generate_chat_completion(
        self,
        messages: List[Dict[str, str]],
        json_mode: bool = True
    ) -> str:
        chat_messages = []
        for msg in messages:
            chat_messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })

        response_format = {"type": "json_object"} if json_mode else None

        last_exception = None
        for attempt in range(1, self.max_retries + 2):
            try:
                response = self.client.chat(
                    model=self.model,
                    messages=chat_messages,
                    temperature=self.temperature,
                    response_format=response_format,
                    request_options=RequestOptions(
                        timeout_in_seconds=self.timeout_seconds,
                        max_retries=self.max_retries
                    )
                )

                if response.message and response.message.content:
                    first_block = response.message.content[0]
                    if hasattr(first_block, "text"):
                        return first_block.text
                return "{}"
            except Exception as exc:
                last_exception = exc
                logger.warning("Cohere API call attempt %d failed: %s", attempt, str(exc))
                if attempt <= self.max_retries:
                    time.sleep(2 ** attempt * 0.5)

        raise RuntimeError(f"Cohere API call failed after {self.max_retries + 1} attempts: {last_exception}")


class MockJordanianCohereClient(BaseLLMClient):
    """
    Hermetic, deterministic client for local development, offline runs, and automated testing.
    Understands Jordanian Arabic colloquial idioms and code-switching.
    """

    def generate_chat_completion(
        self,
        messages: List[Dict[str, str]],
        json_mode: bool = True
    ) -> str:
        system_content = messages[0].get("content", "") if messages else ""
        user_content = messages[-1].get("content", "") if messages else ""

        # Route by system prompt specialization
        if "evaluating sales leakage" in system_content.lower():
            return self._mock_leakages(user_content)
        elif "executive coach" in system_content.lower() or "coaching recommendations" in system_content.lower():
            return self._mock_coaching(user_content)
        else:
            return self._mock_objections(user_content)

    def _extract_transcript(self, user_content: str) -> str:
        match = re.search(r"---\s*\n(.*?)\n---", user_content, re.DOTALL)
        if match:
            return match.group(1)
        return user_content

    def _mock_objections(self, user_content: str) -> str:
        transcript = self._extract_transcript(user_content)
        objections = []
        counter = 1

        # 1. Price objections in Jordanian Arabic
        price_match = re.search(
            r"((?:والله\s+)?(?:يا\s+غالي\s+)?(?:كتير\s+)?غالي(?:\s+علي\s+هالأيام)?(?:[^\n\.\?]*))",
            transcript,
            re.IGNORECASE
        )
        if not price_match:
            price_match = re.search(r"(الـ\s*budget\s+تبعنا\s+tight[^\n\.\?]*)", transcript, re.IGNORECASE)
        if not price_match:
            price_match = re.search(r"(الفائدة\s+عندكم\s+مرتفعة[^\n\.\?]*)", transcript, re.IGNORECASE)

        if price_match:
            raw_excerpt = price_match.group(1).strip()
            clean_excerpt = re.sub(r"^Turn\s+\d+:\s*(?:\[\d{2}:\d{2}\]\s*)?(?:CUSTOMER|العميل):\s*", "", raw_excerpt).strip()
            
            addressed = "partially"
            agent_resp = "بنقدر نعملك خصم 10% أول 3 شهور"
            if "300 ميجا بتعطيك فايبر مباشر" in transcript or "نص السعر" in transcript:
                addressed = "yes"
                agent_resp = "باقة الـ 300 ميجا بتعطيك فايبر مباشر بدون تقطيع وبتوفر عليك"
            elif "فكر بالموضوع" in transcript or "هذا هو السعر" in transcript:
                addressed = "partially"

            objections.append({
                "finding_id": f"OBJ-{counter:03d}",
                "category": "price",
                "customer_excerpt": clean_excerpt,
                "turn_reference": "Customer Turn",
                "agent_response_excerpt": agent_resp,
                "addressed_status": addressed,
                "speaker_attribution": "labeled",
                "explanation": "أبدى العميل اعتراضاً صريحاً على التكلفة بالعامية الأردنية.",
                "confidence": 0.95,
                "company_guidance_ref": "RULE-PRICE-01",
                "review_status": "pending"
            })
            counter += 1

        # 2. Timing objections: "مش فاضي هسة", "رن علي بعدين", "ملخوم"
        timing_match = re.search(
            r"((?:مش\s+فاضي|ملخوم|عندي\s+شغل)[^\n\.\?]*)",
            transcript,
            re.IGNORECASE
        )
        if timing_match:
            raw_excerpt = timing_match.group(1).strip()
            clean_excerpt = re.sub(r"^Turn\s+\d+:\s*(?:\[\d{2}:\d{2}\]\s*)?(?:CUSTOMER|العميل):\s*", "", raw_excerpt).strip()
            addressed = "no"
            agent_resp = "اسمعني بس دقيقة مش رح أطول عليك"
            if "بناسبك أرجع اتصل" in transcript:
                addressed = "yes"
                agent_resp = "أكيد ولا يهمك، بناسبك أرجع اتصل العصر؟"

            objections.append({
                "finding_id": f"OBJ-{counter:03d}",
                "category": "timing",
                "customer_excerpt": clean_excerpt,
                "turn_reference": "Customer Turn",
                "agent_response_excerpt": agent_resp,
                "addressed_status": addressed,
                "speaker_attribution": "labeled",
                "explanation": "أوضح العميل عدم ملاءمة وقت المكالمة وطلب المعاودة لاحقاً.",
                "confidence": 0.96,
                "company_guidance_ref": "RULE-TIMING-01",
                "review_status": "pending"
            })
            counter += 1

        # 3. Competitor objections: "شركة ثانية", "أمنية", "أورانج"
        comp_match = re.search(
            r"((?:شركة\s+(?:أمنية|زين|أورانج|ثانية)|معطيتني\s+عرض)[^\n\.\?]*)",
            transcript,
            re.IGNORECASE
        )
        if comp_match:
            raw_excerpt = comp_match.group(1).strip()
            clean_excerpt = re.sub(r"^Turn\s+\d+:\s*(?:\[\d{2}:\d{2}\]\s*)?(?:CUSTOMER|العميل):\s*", "", raw_excerpt).strip()
            addressed = "yes" if ("الفرق الأساسي" in transcript or "الفايبر كابل ضوئي" in transcript) else "no"
            objections.append({
                "finding_id": f"OBJ-{counter:03d}",
                "category": "competitor",
                "customer_excerpt": clean_excerpt,
                "turn_reference": "Customer Turn",
                "agent_response_excerpt": "الفايبر كابل ضوئي مباشر لبيتك بسرعة رفع 100 ميجا وثبات كامل",
                "addressed_status": addressed,
                "speaker_attribution": "labeled",
                "explanation": "قارن العميل العرض الحالي بعرض منافس في السوق الأردني.",
                "confidence": 0.92,
                "company_guidance_ref": "RULE-COMP-01",
                "review_status": "pending"
            })
            counter += 1

        # 4. Authority objection: "بدي استشير", "بدي أسأل مرتي/الوالد/شريكي"
        auth_match = re.search(
            r"((?:بدي\s+(?:استشير|أسأل|أحكي\s+مع)\s+(?:مرتي|زوجتي|الوالد|شريكي))[^\n\.\?]*)",
            transcript,
            re.IGNORECASE
        )
        if auth_match:
            raw_excerpt = auth_match.group(1).strip()
            clean_excerpt = re.sub(r"^Turn\s+\d+:\s*(?:\[\d{2}:\d{2}\]\s*)?(?:CUSTOMER|العميل):\s*", "", raw_excerpt).strip()
            objections.append({
                "finding_id": f"OBJ-{counter:03d}",
                "category": "authority",
                "customer_excerpt": clean_excerpt,
                "turn_reference": "Customer Turn",
                "agent_response_excerpt": "حقك مية بالمية يا غالي. رح أبعثلك تفاصيل العرض والخصم بمسج",
                "addressed_status": "yes",
                "speaker_attribution": "labeled",
                "explanation": "العميل يحتاج استشارة صاحب قرار آخر لإتمام الاشتراك.",
                "confidence": 0.94,
                "company_guidance_ref": "RULE-AUTH-01",
                "review_status": "pending"
            })
            counter += 1

        return json.dumps({"objections": objections}, ensure_ascii=False)

    def _mock_leakages(self, user_content: str) -> str:
        transcript = self._extract_transcript(user_content)
        leakages = []
        counter = 1

        # Check for unaddressed timing objection
        if "مش فاضي" in transcript and ("اسمعني بس دقيقة" in transcript or "العرض بس اليوم" in transcript):
            raw_match = re.search(r"(اسمعني بس دقيقة[^\n\.\?]*)", transcript)
            exc = raw_match.group(1).strip() if raw_match else "اسمعني بس دقيقة مش رح أطول عليك"
            leakages.append({
                "finding_id": f"LEAK-{counter:03d}",
                "category": "unaddressed_objection",
                "severity": "critical",
                "evidence_class": "observed_failure",
                "transcript_excerpt": exc,
                "turn_reference": "Agent Turn",
                "expected_behavior": "احترام وقت العميل فوراً والاتفاق على موعد معاودة محدد بدلاً من محاولة إجباره على الاستماع.",
                "missing_behavior": "تجاهل ضيق وقت العميل وأصر على المتابعة، مما أدى لإنهاء المكالمة بانزعاج.",
                "confidence": 0.95,
                "rubric_ref": "RULE-TIMING-01",
                "related_objection_id": "OBJ-002",
                "recommended_human_review": True,
                "review_status": "pending"
            })
            counter += 1

        # Check for missed discovery (agent pitched package without asking questions)
        if "باقة" in transcript and not any(q in transcript for q in ["كم شخص", "كم جهاز", "شو سرعة", "شو طبيعة"]):
            raw_match = re.search(r"((?:العرض عنا اليوم\s+)?باقة[^\n\.\?]*)", transcript)
            exc = raw_match.group(1).strip() if raw_match else "باقة 300 ميجا بـ 25 دينار"
            clean_exc = re.sub(r"^Turn\s+\d+:\s*(?:\[\d{2}:\d{2}\]\s*)?(?:AGENT|الموظف):\s*", "", exc).strip()
            leakages.append({
                "finding_id": f"LEAK-{counter:03d}",
                "category": "missed_discovery",
                "severity": "high",
                "evidence_class": "observed_failure",
                "transcript_excerpt": clean_exc,
                "turn_reference": "Agent Turn",
                "expected_behavior": "طرح أسئلة استكشافية لفهم عدد الأجهزة واحتياج المنزل قبل طرح السعر والباقة.",
                "missing_behavior": "بدأ بعرض الباقة والسعر دون معرفة سرعة المشترك الحالية أو عدد أفراد العائلة.",
                "confidence": 0.91,
                "rubric_ref": "RUBRIC-DISC-01",
                "related_objection_id": None,
                "recommended_human_review": False,
                "review_status": "pending"
            })
            counter += 1

        # Check for missed next step (ending call passively without follow-up commitment)
        if "فكر بالموضوع" in transcript and "موعد" not in transcript and "بكرة" not in transcript:
            raw_match = re.search(r"(فكر بالموضوع[^\n\.\?]*)", transcript)
            exc = raw_match.group(1).strip() if raw_match else "فكر بالموضوع ورنلنا"
            clean_exc = re.sub(r"^Turn\s+\d+:\s*(?:\[\d{2}:\d{2}\]\s*)?(?:AGENT|الموظف):\s*", "", exc).strip()
            leakages.append({
                "finding_id": f"LEAK-{counter:03d}",
                "category": "missed_next_step",
                "severity": "medium",
                "evidence_class": "observed_failure",
                "transcript_excerpt": clean_exc,
                "turn_reference": "Agent Turn",
                "expected_behavior": "تحديد إجراء لاحق واضح بجدول زمني محدد مع العميل.",
                "missing_behavior": "أنهى المكالمة بترك المبادرة للعميل دون تحديد موعد اتصال قادم أو إرسال تفاصيل العرض.",
                "confidence": 0.89,
                "rubric_ref": "RUBRIC-CLOSE-01",
                "related_objection_id": None,
                "recommended_human_review": False,
                "review_status": "pending"
            })
            counter += 1

        return json.dumps({"leakages": leakages}, ensure_ascii=False)

    def _mock_coaching(self, user_content: str) -> str:
        coaching = []
        counter = 1

        # Extract verified findings from user prompt
        finding_matches = re.findall(r"ID:\s*([A-Z0-9\-]+)\s*\|\s*Category:\s*([a-z_]+)", user_content)

        for fid, fcat in finding_matches:
            if "discovery" in fcat:
                coaching.append({
                    "action_id": f"COACH-{counter:03d}",
                    "related_finding_id": fid,
                    "skill_domain": "Needs Discovery",
                    "priority": "high",
                    "evidence_excerpt": "باقة 300 ميجا بـ 25 دينار",
                    "recommended_behavior": "اسأل العميل أولاً عن طبيعة استخدامه الحالي للإنترنت قبل تقديم أي باقة أو ذكر السعر.",
                    "example_phrase": "قبل ما نحدد الباقة، كم شخص بالعيلة بستخدم النت بنفس الوقت وهل بتحتاجوه للدراسة والجيمنج؟",
                    "coaching_guideline_ref": "RUBRIC-DISC-01",
                    "language": settings.COACHING_LANGUAGE,
                    "review_status": "pending"
                })
                counter += 1
            elif "timing" in fcat or "unaddressed" in fcat:
                coaching.append({
                    "action_id": f"COACH-{counter:03d}",
                    "related_finding_id": fid,
                    "skill_domain": "Objection Handling & Time Management",
                    "priority": "high",
                    "evidence_excerpt": "اسمعني بس دقيقة مش رح أطول عليك",
                    "recommended_behavior": "عندما يذكر العميل أنه غير متاح، احترم وقته مباشرة واعرض خيارين محددين لإعادة الاتصال.",
                    "example_phrase": "ولا يهمك مقدر وقتك، بناسبك أرجع اتصل بحضرتك اليوم العصر ولا بكرة الصبح أفضل؟",
                    "coaching_guideline_ref": "RULE-TIMING-01",
                    "language": settings.COACHING_LANGUAGE,
                    "review_status": "pending"
                })
                counter += 1
            elif "next_step" in fcat:
                coaching.append({
                    "action_id": f"COACH-{counter:03d}",
                    "related_finding_id": fid,
                    "skill_domain": "Closing & Follow-Up Discipline",
                    "priority": "medium",
                    "evidence_excerpt": "فكر بالموضوع ورنلنا",
                    "recommended_behavior": "لا تترك الخطوة القادمة معلقة بيد العميل؛ حدد موعداً للتواصل القادم أو أرسل ملخص العرض فوراً عبر واتساب.",
                    "example_phrase": "رح أبعثلك تفاصيل الباقة والخصم بمسج، ورح أرجع أرن عليك بكرة الساعة 12 لنثبت طلب التركيب، تمام؟",
                    "coaching_guideline_ref": "RUBRIC-CLOSE-01",
                    "language": settings.COACHING_LANGUAGE,
                    "review_status": "pending"
                })
                counter += 1
            elif "price" in fcat:
                coaching.append({
                    "action_id": f"COACH-{counter:03d}",
                    "related_finding_id": fid,
                    "skill_domain": "Value Framing",
                    "priority": "medium",
                    "evidence_excerpt": "كتير غالي علي هالأيام",
                    "recommended_behavior": "اربط السعر بثبات السرعة وتوفير باقات الموبايل الإضافية قبل عرض أي خصومات.",
                    "example_phrase": "مقدر تماماً، بس الفايبر بوفر عليك شحن باقات إضافية لكل أجهزة البيت بدون أي تقطيع.",
                    "coaching_guideline_ref": "RULE-PRICE-01",
                    "language": settings.COACHING_LANGUAGE,
                    "review_status": "pending"
                })
                counter += 1

        return json.dumps({"coaching": coaching}, ensure_ascii=False)


def get_llm_client() -> BaseLLMClient:
    """Factory returning Cohere client or mock client based on configuration."""
    if settings.is_mock_llm:
        logger.info("Initializing MockJordanianCohereClient (offline / mock mode active)")
        return MockJordanianCohereClient()
    logger.info("Initializing production CohereLLMClient for model: %s", settings.COHERE_MODEL)
    return CohereLLMClient()
