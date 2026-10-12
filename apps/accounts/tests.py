from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from apps.chat.models import Conversation, Message

from .models import AdminUserAudit, UserProfile

User = get_user_model()


class RegistrationAndAuthenticationTests(TestCase):
    def setUp(self):
        self.client = Client()

    def registration_data(self, **overrides):
        data = {
            "first_name": "Ama",
            "last_name": "Mensah",
            "phone_number": "+233201234567",
            "location": "Accra",
            "username": "ama-mensah",
            "password1": "UniqueSecure!2030",
            "password2": "UniqueSecure!2030",
        }
        data.update(overrides)
        return data

    def test_registration_creates_hashed_user_and_private_profile(self):
        response = self.client.post(
            "/accounts/register/",
            self.registration_data(),
        )
        self.assertRedirects(response, "/accounts/chats/")
        user = User.objects.get(username="ama-mensah")
        self.assertTrue(user.check_password("UniqueSecure!2030"))
        self.assertNotEqual(user.password, "UniqueSecure!2030")
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.phone_number, "+233201234567")
        self.assertEqual(profile.location, "Accra")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_duplicate_username_and_password_confirmation_are_rejected(self):
        User.objects.create_user(username="ama-mensah", password="UniqueSecure!2030")
        response = self.client.post(
            "/accounts/register/",
            self.registration_data(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already in use")

        response = self.client.post(
            "/accounts/register/",
            self.registration_data(username="another-user", password2="different"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "passwords do not match")
        self.assertFalse(User.objects.filter(username="another-user").exists())

    def test_login_and_post_logout(self):
        user = User.objects.create_user(
            username="login-user",
            password="UniqueSecure!2030",
        )
        response = self.client.post(
            "/accounts/login/",
            {"username": "login-user", "password": "UniqueSecure!2030"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        response = self.client.post("/accounts/logout/")
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(self.client.get("/accounts/logout/").status_code, 405)

    def test_django_admin_cannot_bypass_account_retention_policy(self):
        admin = User.objects.create_superuser(
            username="retention-admin",
            password="UniqueSecure!2030",
            email="retention@example.com",
        )
        user = User.objects.create_user(
            username="retained-user",
            password="UniqueSecure!2030",
        )
        self.client.force_login(admin)
        response = self.client.get(f"/admin/auth/user/{user.pk}/delete/")
        self.assertEqual(response.status_code, 403)
        self.assertTrue(User.objects.filter(pk=user.pk).exists())

    def test_guest_can_browse_public_pages_but_not_chat(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        response = self.client.get("/chat/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])


class RegisteredUserManagementTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser(
            username="user-admin",
            password="UniqueSecure!2030",
            email="admin@example.com",
        )
        self.user = User.objects.create_user(
            username="private-customer",
            password="UniqueSecure!2030",
            first_name="Kofi",
            last_name="Boateng",
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            phone_number="+233555000111",
            location="Kumasi",
        )

    def test_only_superuser_can_manage_registered_users(self):
        self.assertEqual(self.client.get("/portal/registered-users/").status_code, 302)
        staff = User.objects.create_user(
            username="ordinary-staff",
            password="UniqueSecure!2030",
            is_staff=True,
        )
        self.client.force_login(staff)
        self.assertEqual(self.client.get("/portal/registered-users/").status_code, 302)

    def test_search_and_pagination(self):
        self.client.force_login(self.admin)
        response = self.client.get("/portal/registered-users/?q=Kumasi")
        self.assertContains(response, "private-customer")
        self.assertContains(response, "1")
        for index in range(55):
            user = User.objects.create_user(
                username=f"paged-customer-{index}",
                password="UniqueSecure!2030",
            )
            UserProfile.objects.create(user=user)
        response = self.client.get("/portal/registered-users/")
        self.assertEqual(response.context["page_obj"].paginator.per_page, 50)
        self.assertTrue(response.context["page_obj"].has_next())

    def test_private_detail_and_conversations_are_audited(self):
        conversation = Conversation.objects.create(
            session_key="admin-visible-conversation",
            user=self.user,
            customer_name="Private name",
        )
        Message.objects.create(conversation=conversation, content="Private discussion")
        self.client.force_login(self.admin)
        response = self.client.get(f"/portal/registered-users/{self.user.pk}/")
        self.assertContains(response, "+233555000111")
        self.assertTrue(
            AdminUserAudit.objects.filter(
                actor=self.admin,
                target=self.user,
                action=AdminUserAudit.USER_VIEW,
            ).exists()
        )
        response = self.client.get(
            f"/portal/registered-users/{self.user.pk}/conversations/"
        )
        self.assertContains(response, str(conversation.pk))
        self.assertTrue(
            AdminUserAudit.objects.filter(
                actor=self.admin,
                target=self.user,
                action=AdminUserAudit.CONVERSATION_VIEW,
            ).exists()
        )

    def test_status_changes_are_post_confirmed_audited_and_retain_chat(self):
        conversation = Conversation.objects.create(
            session_key="status-retained-conversation",
            user=self.user,
            customer_name="Kofi",
        )
        self.client.force_login(self.admin)
        response = self.client.get(
            f"/portal/registered-users/{self.user.pk}/status/"
        )
        self.assertEqual(response.status_code, 405)
        response = self.client.post(
            f"/portal/registered-users/{self.user.pk}/status/",
            {"active": "false", "confirm": "1"},
        )
        self.assertRedirects(response, f"/portal/registered-users/{self.user.pk}/")
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertTrue(Conversation.objects.filter(pk=conversation.pk).exists())
        self.assertTrue(
            AdminUserAudit.objects.filter(
                action=AdminUserAudit.STATUS_CHANGE,
                target=self.user,
                detail="inactive",
            ).exists()
        )

    def test_cannot_suspend_self_or_privileged_accounts(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            f"/portal/registered-users/{self.admin.pk}/status/",
            {"active": "false", "confirm": "1"},
        )
        self.assertEqual(response.status_code, 302)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
