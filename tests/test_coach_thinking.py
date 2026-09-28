#!/usr/bin/env python3
import os
import sys
import json
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.init_db import init_database
import backend.app.controllers as controllers

TEST_DB = "test_coach_thinking.db"

class TestCoachThinking(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)
        init_database(TEST_DB)
        controllers.DB_PATH = TEST_DB

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

    @patch("backend.app.controllers.build_coach_prompt")
    @patch("backend.app.services.ollama_client.stream_completion")
    def test_handle_coach_chat_stream_with_thinking(self, mock_stream, mock_prompt):
        mock_prompt.return_value = ("Test Prompt", "qwen2.5:7b", "http://localhost:11434")

        # Simulate stream chunks with split tags
        simulated_tokens = [
            {"token": "<th", "done": False},
            {"token": "ink>\n1. Diagnostic: Checking fatigue.", "done": False},
            {"token": "\n2. Volume target: 15 sets.</", "done": False},
            {"token": "think>\nGreat work on that session!", "done": False},
            {"token": " Keep pushing hard.", "done": False},
            {"token": "```json\n{\"routines_to_create\": []}\n```", "done": True},
        ]
        mock_stream.return_value = iter(simulated_tokens)

        events = []
        generator = controllers.handle_coach_chat_stream({"user_id": "test_athlete", "messages": []})
        for line in generator:
            line_str = line.strip()
            if line_str.startswith("data: "):
                events.append(json.loads(line_str[6:]))

        event_types = [e["type"] for e in events]
        self.assertIn("thought", event_types)
        self.assertIn("text", event_types)
        self.assertIn("done", event_types)

        # Check collected thoughts
        thought_chunks = [e["delta"] for e in events if e["type"] == "thought"]
        full_thought = "".join(thought_chunks)
        self.assertIn("1. Diagnostic: Checking fatigue.", full_thought)
        self.assertIn("2. Volume target: 15 sets.", full_thought)
        self.assertNotIn("<think>", full_thought)
        self.assertNotIn("</think>", full_thought)

        # Check collected text
        text_chunks = [e["delta"] for e in events if e["type"] == "text"]
        full_text = "".join(text_chunks)
        self.assertIn("Great work on that session!", full_text)
        self.assertNotIn("<think>", full_text)
        self.assertNotIn("```json", full_text)

    @patch("backend.app.controllers.build_coach_prompt")
    @patch("backend.app.controllers.generate_completion")
    def test_handle_coach_chat_static_fallback(self, mock_gen, mock_prompt):
        mock_prompt.return_value = ("Test Prompt", "qwen2.5:7b", "http://localhost:11434")
        raw_response = (
            "<think>\n1. Athlete wants more bicep volume.\n2. Add Incline DB Curls.\n</think>\n"
            "I have updated your routine to incorporate Incline Dumbbell Curls."
        )
        mock_gen.return_value = {
            "content": raw_response,
            "model": "qwen2.5:7b"
        }

        result = controllers.handle_coach_chat({"user_id": "test_athlete", "messages": []})
        self.assertEqual(result["thought"], "1. Athlete wants more bicep volume.\n2. Add Incline DB Curls.")
        self.assertEqual(result["reply"], "I have updated your routine to incorporate Incline Dumbbell Curls.")
        self.assertNotIn("<think>", result["reply"])

if __name__ == "__main__":
    unittest.main()
