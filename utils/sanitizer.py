"""
Sanitizer Module for White-Labeling and Brand Protection.
Ensures zero brand leakage (Jules, Google Jules, Gemini, Google) in all outgoing
Telegram messages, activity descriptions, code summaries, and system replies.
"""

import re
from typing import Optional


def sanitize_brand_leaks(text: Optional[str]) -> str:
    """
    Sanitizes any accidental brand or engine disclosures from text before sending to Telegram.
    Transforms self-identifying statements into neutral, friendly assistant responses.
    """
    if not text or not isinstance(text, str):
        return text or ""

    sanitized = text

    # 1. Full composite identity declarations (e.g. Gemini + Google + Jules)
    pattern_composite_gemini_jules = re.compile(
        r"(?:أنا|انا)\s+(?:جيميناي|Gemini)\s*(?:\([^)]*\))?[^،,.\n]*"
        r"تم\s+تطوير(?:ه|ي)\s+بواسطة\s+Google[^،,.\n]*"
        r"(?:(?:و\s*)?أعمل\s+هنا\s+كمهندس\s+برمجيات\s+ذكاء\s+اصطناعي\s+يُدعى\s*[\"']?جولز[\"']?\s*(?:\(Jules\))?)?[.،]?",
        re.IGNORECASE
    )
    sanitized = pattern_composite_gemini_jules.sub("أنا مساعدك الذكي، جاهز لمساعدتك في أي استفسار أو مهمة.", sanitized)

    # 2. Specific "I am Jules..." introductions in Arabic
    pattern_ana_jules_ar = re.compile(
        r"(?:أنا|انا)\s+(?:جولز|Jules)\s*(?:\((?:Jules|جولز)\))?[،,]?\s*(?:مهندس\s+برمجيات\s+ذكاء\s+اصطناعي\s*(?:تم\s+تطويري\s+بواسطة\s+Google)?)?",
        re.IGNORECASE
    )
    sanitized = pattern_ana_jules_ar.sub("أنا مساعدك الذكي", sanitized)

    # 3. Specific "I am Gemini..." introductions in Arabic
    pattern_ana_gemini_ar = re.compile(
        r"(?:أنا|انا)\s+(?:جيميناي|Gemini)\s*(?:\((?:Gemini|جيميناي)\))?[،,]?\s*(?:نموذج\s+لغوي\s+كبير\s*(?:تم\s+تطويره\s+بواسطة\s+Google)?)?",
        re.IGNORECASE
    )
    sanitized = pattern_ana_gemini_ar.sub("أنا مساعدك الذكي", sanitized)

    # 4. English identity introductions: "I am Jules / Gemini developed by Google..."
    pattern_intro_en = re.compile(
        r"(?:I\s+am|I'm)\s+(?:Jules|Gemini)\s*(?:\([^)]*\))?[^,.\n]*"
        r"(?:developed|created|trained)?\s*(?:by\s+Google)?[^,.\n]*[.!]?",
        re.IGNORECASE
    )
    sanitized = pattern_intro_en.sub("I am your AI assistant, ready to help you.", sanitized)

    # 5. Developer attributions (developed by Google / trained by Google)
    sanitized = re.sub(
        r"تم\s+(?:تطوير|تدريب)(?:ي|ه)\s+(?:بواسطة|من\s+قبل)\s+(?:شركة\s+)?(?:Google|جوجل)",
        "تم إعدادي لمساعدتك",
        sanitized,
        flags=re.IGNORECASE
    )
    sanitized = re.sub(
        r"(?:طورتني|طورني|أنشأتني|أنشأني|صنعتني|صنعني|برمجتني|برمجني)\s+(?:شركة\s+)?(?:Google|جوجل)",
        "تم إعدادي",
        sanitized,
        flags=re.IGNORECASE
    )
    sanitized = re.sub(
        r"(?:أنا\s+)?(?:نموذج|مساعد|روبوت)\s+(?:ذكاء\s+اصطناعي\s+)?(?:من|عبر|بواسطة)\s+(?:شركة\s+)?(?:Google|جوجل)",
        "أنا مساعدك الذكي",
        sanitized,
        flags=re.IGNORECASE
    )
    sanitized = re.sub(
        r"(?:مدعوم|مبني)\s+بواسطة\s+(?:Google|جوجل)",
        "مدعوم بأحدث التقنيات",
        sanitized,
        flags=re.IGNORECASE
    )
    sanitized = re.sub(
        r"نموذج\s+لغوي\s+كبير\s+تم\s+تطويره\s+بواسطة\s+(?:Google|جوجل)",
        "نموذج ذكاء اصطناعي متقدم",
        sanitized,
        flags=re.IGNORECASE
    )
    sanitized = re.sub(
        r"مهندس\s+برمجيات\s+ذكاء\s+اصطناعي\s+يُدعى\s*[\"']?جولز[\"']?(?:\s*\(Jules\))?",
        "مساعد ذكي لتطوير البرمجيات",
        sanitized,
        flags=re.IGNORECASE
    )
    sanitized = re.sub(
        r"(?:developed|created|trained|powered)\s+by\s+Google",
        "ready to assist you",
        sanitized,
        flags=re.IGNORECASE
    )

    # 6. Compound brand names
    sanitized = re.sub(r"Google\s+Jules", "المساعد الذكي", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"جوجل\s+جولز", "المساعد الذكي", sanitized)
    sanitized = re.sub(r"Jules\s+Agent", "المساعد الذكي", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"وكيل\s+جولز", "المساعد الذكي", sanitized)
    sanitized = re.sub(r"جولز\s*\(Jules\)", "المساعد الذكي", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"Jules\s*\(جولز\)", "المساعد الذكي", sanitized, flags=re.IGNORECASE)

    # 7. Arabic prefixes before "جولز" with strict word boundary protection
    def _ar_jules_replacer(match: re.Match) -> str:
        prefix = match.group(1) or ""
        prefix_map = {
            "ب": "بالمساعد الذكي",
            "ل": "للمساعد الذكي",
            "ك": "كالمساعد الذكي",
            "و": "والمساعد الذكي",
            "ف": "فالمساعد الذكي",
        }
        return prefix_map.get(prefix, "المساعد الذكي")

    sanitized = re.sub(
        r"(?<!\w)([بلكوف])?جولز(?!\w)",
        _ar_jules_replacer,
        sanitized
    )

    # 8. Standalone English word "Jules"
    has_arabic = bool(re.search(r"[\u0600-\u06FF]", sanitized))
    en_replacement = "المساعد الذكي" if has_arabic else "AI assistant"
    sanitized = re.sub(r"\bJules\b", en_replacement, sanitized, flags=re.IGNORECASE)

    # 9. Standalone "جيميناي"
    def _ar_gemini_replacer(match: re.Match) -> str:
        prefix = match.group(1) or ""
        prefix_map = {
            "ب": "بالذكاء الاصطناعي",
            "ل": "للذكاء الاصطناعي",
            "ك": "كالذكاء الاصطناعي",
            "و": "والذكاء الاصطناعي",
            "ف": "فالذكاء الاصطناعي",
        }
        return prefix_map.get(prefix, "الذكاء الاصطناعي")

    sanitized = re.sub(
        r"(?<!\w)([بلكوف])?جيميناي(?!\w)",
        _ar_gemini_replacer,
        sanitized
    )

    # 10. Standalone English "Gemini" when NOT part of a specific technical model ID (e.g. gemini-3.1-pro)
    gemini_en_rep = "الذكاء الاصطناعي" if has_arabic else "AI"
    sanitized = re.sub(r"\bGemini\b(?![-_\d])", gemini_en_rep, sanitized, flags=re.IGNORECASE)

    # Clean double spaces that might result from removals
    sanitized = re.sub(r" {2,}", " ", sanitized)

    return sanitized
