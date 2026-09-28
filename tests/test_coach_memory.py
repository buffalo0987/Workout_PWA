#!/usr/bin/env python3
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.init_db import init_database
import backend.app.controllers as controllers

TEST_DB = "test_coach_memory.db"

class TestCoachMemory(unittest.TestCase):
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

    def setUp(self):
        controllers.clear_coach_chat_history("test_user")

    def test_save_and_get_chat_history(self):
        # Initial history should be empty
        history = controllers.get_coach_chat_history("test_user")
        self.assertEqual(len(history), 0)

        # Save user message
        id1 = controllers.save_coach_message("test_user", "user", "I have a shoulder injury.")
        self.assertTrue(id1)

        # Save coach response with thought
        id2 = controllers.save_coach_message(
            "test_user",
            "assistant",
            "Understood, avoiding overhead pressing.",
            "1. Shoulder impingement risk. 2. Remove overhead work."
        )
        self.assertTrue(id2)

        # Verify retrieval
        history = controllers.get_coach_chat_history("test_user")
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[0]["content"], "I have a shoulder injury.")
        self.assertEqual(history[1]["role"], "assistant")
        self.assertEqual(history[1]["content"], "Understood, avoiding overhead pressing.")
        self.assertEqual(history[1]["thought"], "1. Shoulder impingement risk. 2. Remove overhead work.")

    def test_clear_chat_history(self):
        controllers.save_coach_message("test_user", "user", "Message 1")
        controllers.save_coach_message("test_user", "assistant", "Reply 1")
        self.assertEqual(len(controllers.get_coach_chat_history("test_user")), 2)

        # Clear history
        res = controllers.clear_coach_chat_history("test_user")
        self.assertTrue(res)
        self.assertEqual(len(controllers.get_coach_chat_history("test_user")), 0)

    def test_build_coach_prompt_multi_turn_structure(self):
        # Simulate 25 back-and-forth messages
        messages = []
        for i in range(25):
            messages.append({"role": "user" if i % 2 == 0 else "assistant", "content": f"Turn {i}"})

        chat_messages, model, url = controllers.build_coach_prompt("test_user", messages)

        # First message must be the system prompt
        self.assertEqual(chat_messages[0]["role"], "system")
        self.assertIn("Dr. Marcus Vance", chat_messages[0]["content"])

        # Remaining messages should be capped at 20 past messages
        self.assertEqual(len(chat_messages), 21) # 1 system + 20 history
        self.assertEqual(chat_messages[-1]["content"], "Turn 24")
        self.assertEqual(chat_messages[1]["content"], "Turn 5")

    def test_delete_all_user_data_wipes_chat(self):
        controllers.save_coach_message("test_user", "user", "Permanent note")
        self.assertEqual(len(controllers.get_coach_chat_history("test_user")), 1)

        controllers.delete_all_user_data("test_user")
        self.assertEqual(len(controllers.get_coach_chat_history("test_user")), 0)

if __name__ == "__main__":
    unittest.main()
