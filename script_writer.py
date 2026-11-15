import json
import logging
import re
from typing import Dict, List, Optional
import requests

import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ScriptWriter")

class LanguageValidationError(Exception):
    """Raised when script text fails language validation (e.g. English narration when Hindi is required, or foreign scripts)."""
    pass

# Permitted technical and scientific acronyms in uppercase Latin letters
APPROVED_TECHNICAL_ACRONYMS = {
    "NASA", "ISRO", "AI", "UPI", "DNA", "GPS", "IIT", "DRDO",
    "GST", "ATM", "SIM", "OTP", "CERN", "ESA", "IT", "LED",
    "LCD", "CPU", "RAM", "RNA", "COVID", "WHO", "NIST"
}

# Regex pattern for unintended foreign scripts that must be strictly rejected
FORBIDDEN_FOREIGN_SCRIPTS = re.compile(
    r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF'  # Arabic
    r'\u0400-\u04FF\u0500-\u052F'                # Cyrillic
    r'\u0370-\u03FF'                            # Greek
    r'\u4E00-\u9FFF\u3400-\u4DBF'                # Chinese / CJK
    r'\u0590-\u05FF'                            # Hebrew
    r'\u0E00-\u0E7F]'                           # Thai
)

class ScriptWriter:
    """
    YouTube Script & SEO Metadata Generator.
    Enforces strict Devanagari Hindi script generation, rejects foreign scripts and English narration,
    permits approved technical acronyms, and guarantees ~30-second Shorts duration.
    """
    def __init__(self):
        self.api_key = config.OPENROUTER_API_KEY
        self.model = config.LLM_MODEL
        self.base_url = config.OPENROUTER_BASE_URL

    def _extract_json(self, text: str) -> dict:
        """Helper to extract a JSON object from text containing conversational noise."""
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            json_str = text[start:end+1]
            return json.loads(json_str)
        raise ValueError("No valid JSON object found in LLM response.")

    def validate_hindi_text(self, text: str) -> bool:
        """
        Validates that narration text is authentic Hindi in Devanagari script:
        1. Strictly requires Devanagari characters (\\u0900-\\u097F).
        2. Strictly rejects Arabic, Cyrillic, Greek, Chinese, and other unintended foreign scripts.
        3. Strictly rejects English narration sentences.
        4. Permits only approved technical acronyms (e.g. NASA, ISRO, AI, UPI, DNA).
        5. Preserves Devanagari combining marks (matras, halant, anusvara, visarga).
        6. Safely accommodates ZWJ and ZWNJ.
        """
        if not text or not isinstance(text, str):
            return False
        clean = text.strip()

        # Gate 1: Reject forbidden foreign scripts immediately
        if FORBIDDEN_FOREIGN_SCRIPTS.search(clean):
            logger.warning(f"Foreign script character rejected in text: '{clean}'")
            return False

        # Gate 2: Must contain Devanagari characters
        devanagari_chars = len(re.findall(r'[\u0900-\u097F]', clean))
        if devanagari_chars == 0:
            return False

        # Gate 3: Check Latin words (only approved technical acronyms allowed)
        latin_words = re.findall(r'[a-zA-Z]+', clean)
        for lw in latin_words:
            if lw.upper() not in APPROVED_TECHNICAL_ACRONYMS:
                logger.warning(f"Disallowed English narration word '{lw}' found in Hindi text: '{clean}'")
                return False

        return True

    def validate_script_language(self, script_data: dict, target_language: str = "hi", format_type: str = "short") -> bool:
        """
        Validates that every segment adheres to language, script, and duration constraints.
        Enforces segment count (4-6 segments for Shorts ~30s target).
        """
        if not script_data or "segments" not in script_data:
            raise LanguageValidationError("Script data is empty or missing 'segments'.")

        segments = script_data.get("segments", [])
        if not segments:
            raise LanguageValidationError("Script contains zero narration segments.")

        if target_language == "hi":
            total_words = 0
            for idx, seg in enumerate(segments):
                narration = seg.get("text", "").strip()
                if not narration:
                    raise LanguageValidationError(f"Segment {idx} contains empty narration text.")

                # Check forbidden foreign scripts
                if FORBIDDEN_FOREIGN_SCRIPTS.search(narration):
                    raise LanguageValidationError(
                        f"Segment {idx} contains forbidden foreign script characters. Text: '{narration}'"
                    )

                # Check Devanagari Hindi validation
                if not self.validate_hindi_text(narration):
                    raise LanguageValidationError(
                        f"Segment {idx} failed Hindi language validation: English narration is not allowed. "
                        f"Only approved technical acronyms ({', '.join(sorted(APPROVED_TECHNICAL_ACRONYMS))}) "
                        f"are permitted. Given: '{narration}'"
                    )

                words_in_seg = len(narration.split())
                total_words += words_in_seg

            # Total duration check for Shorts (typically 30-70 words spoken in 20-35s)
            if format_type == "short" and (total_words < 25 or total_words > 80):
                logger.warning(f"Shorts total word count ({total_words}) may deviate from ~30s duration target.")

        # Duration & Segment Count Gate
        if format_type == "short":
            if len(segments) < 4 or len(segments) > 6:
                raise LanguageValidationError(
                    f"Shorts script segment count ({len(segments)}) outside allowed bounds. "
                    f"Must contain between 4 and 6 segments to strictly target ~30 seconds duration."
                )

        return True

    def generate_hindi_script(self, topic: str, format_type: str = "short", verified_facts: Optional[Dict] = None, custom_instructions: Optional[str] = None) -> dict:
        """
        Generates an authentic Hindi video script in Devanagari script for an Indian audience.
        Targets ~30 seconds duration for Shorts, preserves scientific accuracy, and strictly forbids English narration.
        Accommodates custom global and category-specific AI instructions without compromising factual accuracy.
        """
        facts_context = ""
        if verified_facts and isinstance(verified_facts, dict):
            claim = verified_facts.get("claim", "")
            explanation = verified_facts.get("explanation", "")
            facts_context = f"\nVERIFIED SCIENTIFIC FACTS TO STRICTLY PRESERVE:\n- Core Claim: {claim}\n- Scientific Basis: {explanation}\n"

        instructions_context = ""
        if custom_instructions and isinstance(custom_instructions, str) and custom_instructions.strip():
            instructions_context = f"\nADDITIONAL USER & CATEGORY INSTRUCTIONS (Follow strictly unless conflicting with scientific facts or Hindi language requirements):\n{custom_instructions.strip()}\n"

        if format_type == "long":
            prompt = f"""Create a highly engaging, relaxing, and scientifically accurate long-form script in natural Hindi (देवनागरी लिपि) for YouTube (16:9 aspect ratio, 2-3 minutes) about: "{topic}".
{facts_context}{instructions_context}
STRICT REQUIREMENTS:
1. It MUST contain exactly 12 to 16 distinct segments.
2. Every segment narration ('text' field) MUST be written in natural, fluent Hindi in DEVANAGARI script.
3. English narration or Latin transliteration is STRICTLY FORBIDDEN. Only approved technical acronyms (e.g. NASA, ISRO, AI) are allowed.
4. Scientific facts must be strictly accurate.
5. Visual keywords MUST be 1-2 simple English nouns for stock video search.

Respond ONLY with a valid JSON object matching this schema:
{{
  "title": "Hindi Video Title in Devanagari",
  "segments": [
    {{
      "text": "Hindi narration in Devanagari (10-14 words max)",
      "keywords": "galaxy cosmos",
      "type": "hook"
    }},
    ...
  ],
  "seo": {{
    "title": "Devanagari SEO Title",
    "description": "Devanagari Description with scientific context",
    "tags": ["hindi science facts", "devanagari", "technology"],
    "hashtags": ["#science", "#hindi", "#facts"]
  }}
}}
"""
        else:
            prompt = f"""Create a captivating, fast-paced, and scientifically accurate YouTube Shorts script in natural Hindi (देवनागरी लिपि) about: "{topic}".
{facts_context}{instructions_context}
STRICT REQUIREMENTS:
1. Target duration: approximately 30 seconds (EXACTLY 4 to 5 punchy segments, 8-12 words per segment).
2. All segment narration ('text' field) MUST be written in natural, fluent Hindi in DEVANAGARI script.
3. English narration or Hinglish in Latin script is STRICTLY FORBIDDEN. Only approved acronyms (NASA, ISRO, AI, UPI, DNA) are allowed.
4. Foreign scripts (Arabic, Cyrillic, Chinese, etc.) are strictly forbidden.
5. Preserve scientific accuracy based on verified facts.
6. Visual keywords MUST be 1-2 simple English nouns for stock footage retrieval.
7. The title and SEO metadata must be tailored for Indian viewers.

Respond ONLY with a valid JSON object matching this schema:
{{
  "title": "अद्भुत वैज्ञानिक रहस्य (Devanagari title under 60 chars)",
  "segments": [
    {{
      "text": "क्या आप जानते हैं कि अंतरिक्ष में पूर्ण सन्नाटा क्यों रहता है?",
      "keywords": "space stars galaxy",
      "type": "hook"
    }},
    {{
      "text": "ध्वनि तरंगों को यात्रा करने के लिए वायुमंडल या माध्यम की जरूरत होती है।",
      "keywords": "sound waves science",
      "type": "body"
    }},
    {{
      "text": "अंतरिक्ष में कोई हवा नहीं है, इसलिए वहां कोई आवाज नहीं गूंजती।",
      "keywords": "astronaut deep space silence",
      "type": "body"
    }},
    {{
      "text": "नासा के अनुसार दो अंतरिक्ष यात्री पास होकर भी एक-दूसरे को नहीं सुन सकते।",
      "keywords": "space helmet communication",
      "type": "body"
    }},
    {{
      "text": "ऐसे ही अद्भुत वैज्ञानिक रहस्यों के लिए अभी सब्सक्राइब करें!",
      "keywords": "futuristic subscribe button",
      "type": "cta"
    }}
  ],
  "seo": {{
    "title": "अंतरिक्ष का अनसुना सच - Science Facts in Hindi",
    "description": "जानिए अंतरिक्ष में सन्नाटा क्यों होता है। दैनिक वैज्ञानिक रहस्यों के लिए सब्सक्राइब करें।",
    "tags": ["science facts in hindi", "अंतरिक्ष", "विज्ञान", "facts", "shorts"],
    "hashtags": ["#science", "#facts", "#hindi", "#shorts"]
  }}
}}
"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/google/antigravity",
            "X-Title": "Antigravity YouTube Automation"
        }

        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "max_tokens": 2500 if format_type == "long" else 1500
        }

        if self.api_key:
            try:
                logger.info(f"Generating Hindi {format_type} script for '{topic}' via model: {self.model}")
                response = requests.post(f"{self.base_url}/chat/completions", headers=headers, json=data, timeout=30)
                if response.status_code == 200:
                    result = response.json()
                    content = result['choices'][0]['message']['content'].strip()
                    script_data = self._extract_json(content)
                    self.validate_script_language(script_data, "hi", format_type=format_type)
                    logger.info("Hindi script generation and language validation succeeded.")
                    return script_data
                else:
                    logger.warning(f"OpenRouter API call failed ({response.status_code}): {response.text}")
            except Exception as e:
                logger.warning(f"Error calling OpenRouter or validating Hindi script: {e}")

        # Fallback to authentic Hindi template
        logger.info("Using authentic Hindi fallback template.")
        fallback_script = self._get_fallback_hindi_script(topic, format_type, verified_facts)
        self.validate_script_language(fallback_script, "hi", format_type=format_type)
        return fallback_script

    def _get_fallback_hindi_script(self, topic: str, format_type: str = "short", verified_facts: Optional[Dict] = None) -> dict:
        """Returns a verified, scientifically accurate Hindi fallback script in Devanagari (4-5 segments for Shorts)."""
        if format_type == "long":
            segments = [
                {"text": "नमस्ते दोस्तों, आज हम एक बेहद हैरान करने वाले वैज्ञानिक रहस्य को जानेंगे।", "keywords": "galaxy cosmos mystery", "type": "hook"},
                {"text": "हमारा ब्रह्मांड ऐसे चमत्कारों से भरा है जिन्हें समझना वैज्ञानिकों के लिए भी चुनौती है।", "keywords": "deep space universe", "type": "body"},
                {"text": "अंतरिक्ष में ध्वनि यात्रा नहीं कर सकती क्योंकि वहां कोई वायुमंडल नहीं है।", "keywords": "silence astronaut vacuum", "type": "body"},
                {"text": "ध्वनि को यात्रा करने के लिए अणुओं और माध्यम की जरूरत होती है।", "keywords": "physics sound waves", "type": "body"},
                {"text": "न्यूट्रॉन तारे ब्रह्मांड के सबसे घने और तेजी से घूमने वाले पिंड हैं।", "keywords": "neutron star pulsar", "type": "body"},
                {"text": "एक चम्मच न्यूट्रॉन तारे का वजन पृथ्वी पर माउंट एवरेस्ट के बराबर हो सकता है।", "keywords": "gravity dense matter", "type": "body"},
                {"text": "प्रकाश की गति तीन लाख किलोमीटर प्रति सेकंड है, जो ब्रह्मांड की अंतिम गति सीमा है।", "keywords": "speed of light lasers", "type": "body"},
                {"text": "सूर्य का प्रकाश पृथ्वी तक पहुंचने में लगभग आठ मिनट और बीस सेकंड का समय लेता है।", "keywords": "sun rays earth orbit", "type": "body"},
                {"text": "ब्लैक होल का गुरुत्वाकर्षण इतना प्रचंड होता है कि प्रकाश भी बाहर नहीं आ सकता।", "keywords": "black hole event horizon", "type": "body"},
                {"text": "आइंस्टीन के सापेक्षता सिद्धांत ने समय और अंतरिक्ष के संबंध को हमेशा के लिए बदल दिया।", "keywords": "albert einstein physics theory", "type": "body"},
                {"text": "हमारे शरीर का हर परमाणु अरबों साल पहले किसी तारे के भीतर बना था।", "keywords": "stardust human cells chemistry", "type": "body"},
                {"text": "ऐसे ही अद्भुत और प्रमाणित वैज्ञानिक रहस्यों के लिए चैनल को तुरंत सब्सक्राइब करें।", "keywords": "neon subscribe button glow", "type": "cta"}
            ]
            return {
                "title": f"विज्ञान का अनसुना सच: {topic}",
                "segments": segments,
                "seo": {
                    "title": f"विज्ञान के अद्भुत रहस्य - {topic} in Hindi",
                    "description": f"जानिए {topic} से जुड़े प्रामाणिक वैज्ञानिक तथ्य। सब्सक्राइब करें दैनिक ज्ञान के लिए।",
                    "tags": ["science facts in hindi", topic.lower(), "अंतरिक्ष", "विज्ञान", "facts"],
                    "hashtags": ["#science", "#hindi", "#facts", "#space"]
                }
            }
        else:
            return {
                "title": "अंतरिक्ष का सबसे बड़ा रहस्य",
                "segments": [
                    {
                        "text": "क्या आप जानते हैं कि अंतरिक्ष पूरी तरह से शांत और नीरव है?",
                        "keywords": "space silence galaxy stars",
                        "type": "hook"
                    },
                    {
                        "text": "ध्वनि तरंगों को यात्रा करने के लिए हवा या किसी भौतिक माध्यम की आवश्यकता होती है।",
                        "keywords": "sound waves science cosmos",
                        "type": "body"
                    },
                    {
                        "text": "अंतरिक्ष में कोई वायुमंडल नहीं है, इसलिए वहां पूर्ण सन्नाटा पसरा रहता है।",
                        "keywords": "astronaut floating deep space",
                        "type": "body"
                    },
                    {
                        "text": "नासा के अनुसार दो अंतरिक्ष यात्री पास चिल्लाकर भी एक-दूसरे को नहीं सुन सकते।",
                        "keywords": "nasa space helmet communication",
                        "type": "body"
                    },
                    {
                        "text": "ऐसे ही अद्भुत और प्रामाणिक विज्ञान तथ्यों के लिए अभी सब्सक्राइब करें!",
                        "keywords": "subscribe button glow futuristic",
                        "type": "cta"
                    }
                ],
                "seo": {
                    "title": "अंतरिक्ष का अद्भुत रहस्य - Science Facts in Hindi",
                    "description": "जानिए अंतरिक्ष में आवाज क्यों नहीं सुनाई देती। सब्सक्राइब करें दैनिक विज्ञान जानकारी के लिए।",
                    "tags": ["science facts", "hindi facts", "space", "अंतरिक्ष", "विज्ञान", "shorts"],
                    "hashtags": ["#science", "#facts", "#hindi", "#shorts", "#space"]
                }
            }

    def generate_script(self, topic: str, format_type: str = "short", language: str = "hi", verified_facts: Optional[Dict] = None, custom_instructions: Optional[str] = None) -> dict:
        """
        Generates a complete YouTube video script and SEO metadata for a given topic.
        Defaults to Hindi Devanagari script generation (language='hi').
        Supports language='en' for backwards compatibility.
        """
        if language == "hi":
            return self.generate_hindi_script(topic, format_type, verified_facts, custom_instructions=custom_instructions)

        # Legacy English script generation for backward test compatibility
        if not self.api_key:
            logger.warning("OpenRouter API key is missing. Returning fallback English script.")
            return self._get_fallback_script(topic, format_type)

        if format_type == "long":
            prompt = f"""Create a highly engaging long-form YouTube script about: "{topic}" for an Indian audience.
Respond ONLY with a valid JSON object matching the standard format with segments (12-18 segments) and seo metadata."""
        else:
            prompt = f"""Create a highly engaging YouTube Shorts script about: "{topic}" for an Indian audience.
Respond ONLY with a valid JSON object matching the standard format with segments (4-5 segments) and seo metadata."""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/google/antigravity",
            "X-Title": "Antigravity YouTube Automation"
        }
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "max_tokens": 2500 if format_type == "long" else 1500
        }

        try:
            response = requests.post(f"{self.base_url}/chat/completions", headers=headers, json=data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content'].strip()
                return self._extract_json(content)
        except Exception as e:
            logger.error(f"Error in legacy English script generation: {e}")

        return self._get_fallback_script(topic, format_type)

    def _get_fallback_script(self, topic: str, format_type: str = "short") -> dict:
        """Returns a static English fallback script if the API is offline."""
        logger.warning(f"Generating an English fallback script for {format_type} format.")
        try:
            from indian_niches_templates import get_niche_template
            return get_niche_template(topic, format_type)
        except Exception as e:
            logger.error(f"Failed to load indian_niches_templates fallback: {e}")

        if format_type == "long":
            segments = []
            for i in range(12):
                segments.append({
                    "text": f"Soothing fact segment number {i+1} about the deep and calming history of {topic}.",
                    "keywords": "satisfying loop, relaxing visual, oddly satisfying",
                    "type": "body"
                })
            segments[0]["type"] = "hook"
            segments[0]["text"] = f"Take a slow breath. Relax. Let us explore the quiet beauty of {topic}."
            segments[-1]["type"] = "cta"
            segments[-1]["text"] = "Thank you for sharing this calm moment. Subscribe for more daily peace."

            return {
                "title": f"The Soothing Truth of {topic}",
                "segments": segments,
                "seo": {
                    "title": f"ASMR Study and Sleep Guide: {topic}",
                    "description": f"A relaxing long-form ASMR facts video about {topic}. Subscribe for daily calm loops.",
                    "tags": [topic.lower(), "educational", "asmr", "satisfying", "relaxing", "sleep"],
                    "hashtags": [f"#{topic.replace(' ', '')}", "#asmr", "#relaxing", "#longform"]
                }
            }
        else:
            return {
                "title": f"The Truth About {topic}",
                "segments": [
                    {
                        "text": f"Have you ever wondered about the mystery of {topic}?",
                        "keywords": "mystery, question, thinking",
                        "type": "hook"
                    },
                    {
                        "text": f"It turns out {topic} has a rich history that impacts our daily lives.",
                        "keywords": "history, civilization, earth",
                        "type": "body"
                    },
                    {
                        "text": "Many experts agree that its significance will only grow in the future.",
                        "keywords": "future, technology, growing",
                        "type": "body"
                    },
                    {
                        "text": "Make sure to hit subscribe and tell us your thoughts below!",
                        "keywords": "subscribe, youtube, comment",
                        "type": "cta"
                    }
                ],
                "seo": {
                    "title": f"The Ultimate Guide to {topic}",
                    "description": f"Exploring the incredible details of {topic}. Subscribe for daily videos!",
                    "tags": [topic.lower(), "educational", "shorts", "interesting facts"],
                    "hashtags": [f"#{topic.replace(' ', '')}", "#shorts", "#facts"]
                }
            }

if __name__ == "__main__":
    writer = ScriptWriter()
    script = writer.generate_script("अंतरिक्ष में ध्वनि", language="hi")
    print(json.dumps(script, indent=2, ensure_ascii=False))
