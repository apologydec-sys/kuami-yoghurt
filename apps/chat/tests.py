import json
from datetime import timedelta

from django.test import Client, TestCase
from django.utils import timezone

from .models import Conversation, Message


class ConversationTest(TestCase):
    def test_create_conversation(self):
        conv = Conversation.objects.create(
            session_key="abc123xyz",
            customer_name="Kwame",
            customer_email="kwame@example.com",
        )
        self.assertFalse(conv.is_archived)
        self.assertIn("Kwame", str(conv))

    def test_unread_count(self):
        conv = Conversation.objects.create(
            session_key="session-001", customer_name="Ama"
        )
        Message.objects.create(conversation=conv, content="Hello!", is_from_dj=False)
        Message.objects.create(conversation=conv, content="Hi back", is_from_dj=True)
        self.assertEqual(conv.unread_count, 1)


class MessageTest(TestCase):
    def test_create_message(self):
        conv = Conversation.objects.create(
            session_key="session-002", customer_name="Kofi"
        )
        msg = Message.objects.create(conversation=conv, content="Is the DJ available?")
        self.assertFalse(msg.is_from_dj)
        self.assertFalse(msg.is_read)
        self.assertIn("Kofi", str(msg))


class ChatStartViewTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_get_start_page(self):
        response = self.client.get("/chat/")
        self.assertEqual(response.status_code, 200)

    def test_post_creates_conversation(self):
        response = self.client.post("/chat/", {
            "customer_name": "Akosua",
            "customer_email": "akosua@example.com",
            "initial_message": "Hello, I'd like to book you.",
        })
        # Should redirect to chat window.
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Conversation.objects.filter(customer_name="Akosua").exists())
        conv = Conversation.objects.get(customer_name="Akosua")
        self.assertIn("/chat/{}/".format(conv.pk), response["Location"])


class SendMessageViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        # Create a conversation with the session key the test client will have.
        session = self.client.session
        session.save()
        self.session_key = self.client.session.session_key

    def _get_conversation(self):
        """Create a conversation then return it."""
        self.client.post("/chat/", {
            "customer_name": "Kojo",
            "customer_email": "kojo@example.com",
            "initial_message": "Hi there!",
        })
        return Conversation.objects.filter(customer_name="Kojo").first()

    def test_send_message_returns_json(self):
        conv = self._get_conversation()
        self.assertIsNotNone(conv)
        response = self.client.post(
            "/chat/{}/send/".format(conv.pk),
            {"content": "A follow-up message."},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("content", data)
        self.assertIn("id", data)
        self.assertIn("timestamp", data)
        self.assertFalse(data["is_from_dj"])

    def test_wrong_session_gets_403(self):
        """A second client with a different session should get 403."""
        conv = self._get_conversation()
        self.assertIsNotNone(conv)

        other_client = Client()
        response = other_client.post(
            "/chat/{}/send/".format(conv.pk),
            {"content": "Sneaky message."},
        )
        self.assertEqual(response.status_code, 403)


class PollMessagesViewTest(TestCase):
    def setUp(self):
        self.client = Client()

    def _get_conversation(self):
        self.client.post("/chat/", {
            "customer_name": "Abena",
            "customer_email": "abena@example.com",
            "initial_message": "Hello!",
        })
        return Conversation.objects.filter(customer_name="Abena").first()

    def test_poll_returns_messages_after_timestamp(self):
        conv = self._get_conversation()
        self.assertIsNotNone(conv)

        # Add a message directly.
        msg = Message.objects.create(conversation=conv, content="A new reply.", is_from_dj=True)
        old_ts = (msg.created_at - timedelta(seconds=1)).isoformat()

        response = self.client.get(
            "/chat/{}/poll/?since={}".format(conv.pk, old_ts)
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("messages", data)
        ids = [m["id"] for m in data["messages"]]
        self.assertIn(msg.pk, ids)

    def test_poll_excludes_old_messages(self):
        conv = self._get_conversation()
        self.assertIsNotNone(conv)

        # Add a message.
        msg = Message.objects.create(conversation=conv, content="Old message.", is_from_dj=True)
        future_ts = (msg.created_at + timedelta(seconds=5)).isoformat()

        response = self.client.get(
            "/chat/{}/poll/?since={}".format(conv.pk, future_ts)
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        ids = [m["id"] for m in data["messages"]]
        self.assertNotIn(msg.pk, ids)
