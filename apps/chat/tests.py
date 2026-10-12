import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from .models import Conversation, Message, MessageModerationAction

User = get_user_model()


class ConversationAndMessageModelTests(TestCase):
    def test_legacy_conversations_and_messages_remain_supported(self):
        conversation = Conversation.objects.create(
            session_key="legacy-session",
            customer_name="Kwame",
            customer_email="kwame@example.com",
        )
        message = Message.objects.create(
            conversation=conversation,
            content="Legacy message",
        )
        self.assertFalse(conversation.is_archived)
        self.assertEqual(conversation.unread_count, 1)
        self.assertIn("Kwame", str(conversation))
        self.assertIn("Kwame", str(message))

    def test_deleted_message_string_does_not_reveal_content(self):
        conversation = Conversation.objects.create(
            session_key="deleted-session",
            customer_name="Ama",
        )
        message = Message.objects.create(
            conversation=conversation,
            content="private content",
            deleted_at=timezone.now(),
        )
        self.assertEqual(str(message), "Deleted message")


class PersistentChatTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="chat-user", password="Securepass!125")
        self.client.force_login(self.user)

    def start_conversation(self):
        response = self.client.post(
            "/chat/",
            {"initial_message": "Hello, I would like to ask a question."},
        )
        self.assertEqual(response.status_code, 302)
        return Conversation.objects.get(user=self.user)

    def test_guest_cannot_start_or_send_messages(self):
        guest = Client()
        response = guest.get("/chat/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])
        self.assertEqual(Conversation.objects.count(), 0)

    def test_start_conversation_uses_authenticated_account(self):
        conversation = self.start_conversation()
        message = conversation.chat_messages.get()
        self.assertEqual(conversation.user, self.user)
        self.assertEqual(message.sender, self.user)
        self.assertEqual(message.content, "Hello, I would like to ask a question.")

    def test_message_send_and_poll_use_id_cursor(self):
        conversation = self.start_conversation()
        response = self.client.post(
            f"/chat/{conversation.pk}/send/",
            {"content": "A follow-up"},
        )
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(payload["content"], "A follow-up")

        staff_reply = Message.objects.create(
            conversation=conversation,
            content="We received your message.",
            is_from_dj=True,
        )
        response = self.client.get(
            f"/chat/{conversation.pk}/poll/?after={payload['id']}"
        )
        result = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in result["messages"]], [staff_reply.pk])
        self.assertFalse(result["agent_online"])

    def test_poll_reports_customer_and_staff_presence(self):
        conversation = self.start_conversation()
        self.client.get(f"/chat/{conversation.pk}/")
        staff = User.objects.create_user(
            username="presence-staff",
            password="Securepass!125",
            is_staff=True,
        )
        staff_client = Client()
        staff_client.force_login(staff)
        staff_client.get(f"/portal/chat/{conversation.pk}/")
        customer_result = self.client.get(
            f"/chat/{conversation.pk}/poll/?after=0"
        )
        self.assertTrue(json.loads(customer_result.content)["agent_online"])
        staff_result = staff_client.get(
            f"/chat/{conversation.pk}/poll/?after=0"
        )
        self.assertTrue(json.loads(staff_result.content)["customer_online"])

    def test_other_account_cannot_view_send_or_poll(self):
        conversation = self.start_conversation()
        other_user = User.objects.create_user(
            username="other-chat-user",
            password="Securepass!125",
        )
        self.client.force_login(other_user)
        self.assertEqual(self.client.get(f"/chat/{conversation.pk}/").status_code, 404)
        self.assertEqual(
            self.client.post(f"/chat/{conversation.pk}/send/", {"content": "No"}).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(f"/chat/{conversation.pk}/poll/").status_code,
            404,
        )

    def test_chat_history_survives_logout_and_login(self):
        conversation = self.start_conversation()
        self.client.logout()
        self.client.force_login(self.user)
        response = self.client.get("/accounts/chats/")
        self.assertContains(response, f"Conversation {conversation.pk}")
        self.assertContains(response, "Hello, I would like to ask a question.")

    def test_older_message_history_is_loaded_in_bounded_pages(self):
        conversation = self.start_conversation()
        Message.objects.bulk_create(
            [
                Message(
                    conversation=conversation,
                    content=f"History item {index}",
                    sender=self.user,
                )
                for index in range(55)
            ]
        )
        window = self.client.get(f"/chat/{conversation.pk}/")
        self.assertContains(window, 'id="loadOlderMessages"')
        oldest_visible_id = window.context["messages"][0].pk
        response = self.client.get(
            f"/chat/{conversation.pk}/history/?before={oldest_visible_id}"
        )
        result = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(result["messages"]), 50)
        self.assertFalse(result["has_more"])

    def test_owner_can_soft_delete_only_their_message(self):
        conversation = self.start_conversation()
        message = conversation.chat_messages.get()
        response = self.client.post(
            f"/chat/{conversation.pk}/messages/{message.pk}/delete/",
            {"confirm_delete": "1"},
        )
        self.assertEqual(response.status_code, 302)
        message.refresh_from_db()
        self.assertIsNotNone(message.deleted_at)
        self.assertEqual(message.deletion_kind, "owner")
        page = self.client.get(f"/chat/{conversation.pk}/")
        self.assertContains(page, "This message was removed.")
        self.assertNotContains(page, "Hello, I would like to ask a question.")

    def test_owner_cannot_delete_another_sender_message(self):
        conversation = self.start_conversation()
        staff_user = User.objects.create_user(
            username="reply-author",
            password="Securepass!125",
        )
        message = Message.objects.create(
            conversation=conversation,
            content="Staff response",
            is_from_dj=True,
            sender=staff_user,
        )
        response = self.client.post(
            f"/chat/{conversation.pk}/messages/{message.pk}/delete/",
            {"confirm_delete": "1"},
        )
        self.assertEqual(response.status_code, 404)
        message.refresh_from_db()
        self.assertIsNone(message.deleted_at)

    def test_staff_can_reply_and_superadmin_moderation_is_audited(self):
        conversation = self.start_conversation()
        staff = User.objects.create_user(
            username="staff-reply",
            password="Securepass!125",
            is_staff=True,
        )
        self.client.force_login(staff)
        response = self.client.post(
            f"/portal/chat/{conversation.pk}/",
            {"content": "Staff answer"},
        )
        self.assertEqual(response.status_code, 302)
        staff_message = conversation.chat_messages.get(content="Staff answer")
        self.assertEqual(staff_message.sender, staff)

        superuser = User.objects.create_superuser(
            username="chat-admin",
            password="Securepass!125",
            email="chat-admin@example.com",
        )
        self.client.force_login(superuser)
        response = self.client.post(
            f"/portal/chat/{conversation.pk}/messages/{staff_message.pk}/moderate/",
            {"confirm": "1", "reason": "Personal information was shared."},
        )
        self.assertEqual(response.status_code, 302)
        staff_message.refresh_from_db()
        self.assertIsNotNone(staff_message.deleted_at)
        self.assertEqual(MessageModerationAction.objects.get().moderator, superuser)
