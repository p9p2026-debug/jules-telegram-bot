"""
Google GenAI / Jules Agent Service Module.
Interfaces with Google's GenAI API for text, code analysis, images, and documents (PDF/MD/Code).
Maintains multi-turn conversation context for each session and dynamically resolves API keys.
"""

import logging
from typing import List, Optional, Tuple
from google import genai
from google.genai import types
import config
from database.repositories import SessionRepository, SettingsRepository, UserRepository

logger = logging.getLogger(__name__)

class JulesService:
    """Service to interact with Google's Gemini / Jules agent models."""

    @staticmethod
    async def get_effective_api_key(user_id: int) -> Optional[str]:
        """
        Determines the appropriate API key for a user:
        1. User's custom API key (if set and allowed)
        2. System API key override in database
        3. Environment variable GEMINI_API_KEY
        """
        user = await UserRepository.get_by_id(user_id)
        if user and user.get("custom_api_key"):
            return user["custom_api_key"].strip()

        db_sys_key = await SettingsRepository.get_setting("system_api_key", "")
        if db_sys_key and db_sys_key.strip():
            return db_sys_key.strip()

        if config.GEMINI_API_KEY and config.GEMINI_API_KEY.strip():
            return config.GEMINI_API_KEY.strip()

        return None

    @staticmethod
    def resolve_model_id(model_choice: str) -> str:
        """Maps user model choice ('flash' or 'pro') to the configured Google model ID."""
        if model_choice.lower() == "pro":
            return config.MODEL_PRO_ID
        return config.MODEL_FLASH_ID

    @classmethod
    async def generate_response(
        cls,
        user_id: int,
        session_id: str,
        user_prompt: str,
        media_bytes: Optional[bytes] = None,
        mime_type: Optional[str] = None,
        file_name: Optional[str] = None
    ) -> str:
        """
        Executes a multimodal or text conversation turn with Jules/Gemini.
        Preserves session context and persists conversation messages.
        """
        api_key = await cls.get_effective_api_key(user_id)
        if not api_key:
            return (
                "⚠️ **مفتاح API غير متوفر!**\n\n"
                "لم يتم العثور على مفتاح Google Gemini API صالح في النظام.\n"
                "• إذا كان مسموحاً لك، يمكنك إدخال مفتاحك الخاص باستخدام الأمر: `/apikey <مفتاحك>`\n"
                "• أو يرجى من مدير البوت تعيين المفتاح الرئيسي عبر المتغيرات البيئية أو لوحة الأدمن."
            )

        # Retrieve user model preference
        user = await UserRepository.get_by_id(user_id)
        model_choice = user.get("selected_model", "flash") if user else "flash"
        model_id = cls.resolve_model_id(model_choice)

        # Build conversation history
        history_rows = await SessionRepository.get_session_messages(session_id, limit=16)
        contents: List[types.Content] = []

        for row in history_rows:
            role = "user" if row["role"] == "user" else "model"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=row["content"])]
                )
            )

        # Build current user turn parts
        current_parts: List[types.Part] = []

        if media_bytes and mime_type:
            # Handle multimodal input (images or PDF)
            if mime_type.startswith("image/") or mime_type == "application/pdf":
                current_parts.append(
                    types.Part.from_bytes(data=media_bytes, mime_type=mime_type)
                )
            elif mime_type.startswith("text/") or mime_type in ["application/json", "application/javascript"]:
                # Text/code documents: decode as text
                try:
                    text_content = media_bytes.decode("utf-8", errors="replace")
                    prompt_header = f"📄 محتوى الملف المرفق ({file_name or 'document'}):\n```\n{text_content}\n```\n\n"
                    user_prompt = prompt_header + (user_prompt or "يرجى فحص وتحليل هذا الملف البرمجي بالتفصيل.")
                except Exception as exc:
                    logger.warning("Failed to decode text file: %s", exc)

        if user_prompt:
            current_parts.append(types.Part.from_text(text=user_prompt))
        elif not current_parts:
            current_parts.append(types.Part.from_text(text="مرحباً! يرجى تقديم تحليل أو مساعدة برمجية."))

        contents.append(types.Content(role="user", parts=current_parts))

        # Save user message to database
        saved_user_text = user_prompt or f"[{file_name or 'مرفق وسائط'}]"
        await SessionRepository.add_message(
            session_id=session_id,
            role="user",
            content=saved_user_text,
            media_type=mime_type
        )

        try:
            client = genai.Client(api_key=api_key)
            generation_config = types.GenerateContentConfig(
                system_instruction=config.JULES_SYSTEM_PROMPT,
                temperature=0.4,  # Accurate, focused coding & architecture outputs
            )

            response = await client.aio.models.generate_content(
                model=model_id,
                contents=contents,
                config=generation_config
            )

            assistant_reply = response.text or "لم يقدم النموذج رداً نصياً على هذا الطلب."

            # Save assistant reply to database
            await SessionRepository.add_message(
                session_id=session_id,
                role="model",
                content=assistant_reply
            )

            return assistant_reply

        except Exception as exc:
            logger.exception("Jules GenAI call error: %s", exc)
            err_msg = str(exc)
            if "API_KEY_INVALID" in err_msg or "400" in err_msg and "key" in err_msg.lower():
                return "❌ **خطأ في مفتاح API:** المفتاح المستخدم غير صالح أو منتهي الصلاحية. يرجى التحقق منه وتحديثه عبر `/apikey`."
            elif "RESOURCE_EXHAUSTED" in err_msg or "429" in err_msg:
                return "⏳ **تم تجاوز حد الطلبات (Rate Limit):** يرجى الانتظار دقيقة أو التبديل إلى النموذج السريع عبر `/model`."
            elif "PERMISSION_DENIED" in err_msg or "403" in err_msg:
                if "has not been used in project" in err_msg or "disabled" in err_msg.lower():
                    return (
                        "❌ **الخدمة غير مفعلة على مشروع مفتاح الـ API (403):**\n\n"
                        "المشروع المرتبط بالمفتاح يحتاج إلى تفعيل خدمة الـ Generative Language.\n"
                        "• **الحل الأسرع:** اضغط على زر (Enable / تفعيل) من الرابط التالي:\n"
                        "https://console.developers.google.com/apis/api/generativelanguage.googleapis.com/overview?project=306419110271\n\n"
                        "• أو استخرج مفتاحاً جاهزاً ومفعلاً مجاناً من [Google AI Studio](https://aistudio.google.com/app/apikey) وحدّثه عبر `/apikey`."
                    )
                return "❌ **خطأ في الصلاحيات (403):** مفتاح الـ API لا يملك صلاحية استخدام هذا النموذج."
            return f"❌ **حدث خطأ فني أثناء معالجة الطلب.** يرجى المحاولة مرة أخرى أو مراجعة المشرف."


def html_escape(text: str) -> str:
    """Helper to escape raw error strings."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
