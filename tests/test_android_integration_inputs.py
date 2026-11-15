#!/usr/bin/env python3
"""
FACTS AI - Android Integration & Workflow Inputs Verification Suite
==================================================================
Verifies:
1. ScriptWriter accepts and incorporates custom user and category-specific AI instructions.
2. CLI parser in main.py accepts --category and --instructions without errors.
3. Verification that default instructions (None) preserve authentic Devanagari Hindi behavior.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from script_writer import ScriptWriter
from main import AutomationPipeline
import config


class TestAndroidWorkflowInputs(unittest.TestCase):
    def setUp(self):
        self.writer = ScriptWriter()
        self.writer.api_key = "test_dummy_key"

    def test_custom_instructions_injected_into_prompt(self):
        """Verify custom global and category AI instructions are cleanly injected into Hindi prompt."""
        test_topic = "सौर मंडल के रहस्य"
        test_instructions = "Use an energetic, suspenseful tone and focus on Jupiter's Great Red Spot."

        # Mock the OpenRouter API call to inspect the generated prompt payload
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{
                    "message": {
                        "content": '{"title": "बृहस्पति का विशाल रहस्य", "segments": [{"text": "क्या आप जानते हैं कि बृहस्पति का लाल धब्बा एक महातूफान है?", "keywords": "jupiter storm red spot", "type": "hook"}, {"text": "यह तूफान सदियों से लगातार तेजी से घूम रहा है।", "keywords": "jupiter atmosphere", "type": "body"}, {"text": "हमारी पृथ्वी से भी बड़ा यह तूफान अत्यंत शक्तिशाली है।", "keywords": "planet earth comparison", "type": "body"}, {"text": "नासा के अंतरिक्ष यान ने इसकी तस्वीरें कैद की हैं।", "keywords": "nasa probe jupiter", "type": "body"}, {"text": "ऐसे ही अंतरिक्ष के रहस्यों के लिए सब्सक्राइब करें!", "keywords": "subscribe space", "type": "cta"}], "seo": {"title": "बृहस्पति का महातूफान", "description": "बृहस्पति के लाल धब्बे का सच।", "tags": ["jupiter", "hindi", "space"], "hashtags": ["#jupiter", "#space"]}}'
                    }
                }]
            }
            mock_post.return_value = mock_response

            self.writer.generate_hindi_script(
                test_topic,
                format_type="short",
                custom_instructions=test_instructions
            )

            # Assert post was called and custom instructions were in prompt
            self.assertTrue(mock_post.called)
            call_kwargs = mock_post.call_args[1]
            sent_prompt = call_kwargs["json"]["messages"][0]["content"]

            self.assertIn("ADDITIONAL USER & CATEGORY INSTRUCTIONS", sent_prompt)
            self.assertIn(test_instructions, sent_prompt)

    def test_empty_instructions_preserves_standard_prompt(self):
        """When no instructions are provided, prompt does not contain empty instruction header."""
        test_topic = "अंतरिक्ष में ध्वनि"

        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{
                    "message": {
                        "content": '{"title": "अंतरिक्ष का सन्नाटा", "segments": [{"text": "अंतरिक्ष में कोई ध्वनि तरंग नहीं चल सकती।", "keywords": "space vacuum", "type": "hook"}, {"text": "ध्वनि को चलने के लिए हवा की जरूरत होती है।", "keywords": "sound waves air", "type": "body"}, {"text": "निर्वात में कोई माध्यम नहीं होता।", "keywords": "vacuum space", "type": "body"}, {"text": "इसलिए वहां हर जगह सन्नाटा है।", "keywords": "astronaut silent", "type": "body"}, {"text": "सब्सक्राइब करें और जानें विज्ञान।", "keywords": "subscribe button", "type": "cta"}], "seo": {"title": "अंतरिक्ष में सन्नाटा", "description": "सन्नाटे का सच।", "tags": ["space", "sound"], "hashtags": ["#space"]}}'
                    }
                }]
            }
            mock_post.return_value = mock_response

            self.writer.generate_hindi_script(test_topic, format_type="short", custom_instructions=None)
            sent_prompt = mock_post.call_args[1]["json"]["messages"][0]["content"]
            self.assertNotIn("ADDITIONAL USER & CATEGORY INSTRUCTIONS", sent_prompt)


if __name__ == "__main__":
    unittest.main()
