# Create your tests here.
from django.test import TestCase
from rest_framework.test import APIClient
from django.urls import reverse
from unittest.mock import patch
from member_management.models import User, Organization
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

class APITestCase(TestCase):
    def setUp(self):
        # テストデータの初期設定
        self.organization_client = APIClient()
        self.user_client = APIClient()

    @patch('member_management.services.user_service.UserService.send_verification_email')
    def test_admin_flow(self, mock_send_email):
        # 1.登録
        mock_send_email.return_value = None
        response = self.organization_client.post('/member_management/api/register/', {
            'name': 'Test Org',
            'phone_number': '08012345678',
            'sei': 'org_last_name',
            'mei': 'org_first_name',
            'email': 'test_org@gmail.com',
            'password': 'test_org'
        }, format='json')
        self.assertEqual(response.status_code, 201)
        mock_send_email.assert_called_once()
        print('test_register ok')

        # 2.メール認証
        user = User.objects.get(email='test_org@gmail.com')
        response = self.organization_client.get(reverse('verify_email', kwargs={'uidb64': urlsafe_base64_encode(force_bytes(user.pk))}))
        self.assertIn(response.status_code, [200, 302])
        print('test_verify_email ok')

        # 3.ログイン
        response = self.organization_client.post('/api/token/', {
            'username': 'test_org@gmail.com',
            'password': 'test_org'
        })
        token = response.json()['access']
        self.organization_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        print('test_login ok')

        # 4.ユーザー作成
        response = self.organization_client.post('/api/users/', {
            'username': 'test_user@gmail.com',
            'email': 'test_user@gmail.com',
            'password': 'test_user',
            'last_name': 'user_last_name',
            'first_name': 'user_first_name',
            'phone_number': '08012345678'
        }, format='json')
        self.assertEqual(response.status_code, 201)
        print('test_create_user ok')

        # 5.adminマイページ情報取得
        response = self.user_client.get('/api/users/me/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['email'], 'test_user@gmail.com')
        self.assertEqual(response.json()['last_name'], 'user_last_name')
        self.assertEqual(response.json()['first_name'], 'user_first_name')
        self.assertEqual(response.json()['phone_number'], '08012345678')
        print('test_get_me ok')

        # 6.userログイン
        login_response = self.organization_client.post('/api/token/', {
            'username': 'test_user@gmail.com',
            'password': 'test_user'
        })
        token = login_response.json()['access']
        self.user_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        print('test_login_user ok')

        # 7.userマイページ情報取得
        response = self.user_client.get('/api/users/me/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['email'], 'test_user@gmail.com')
        self.assertEqual(response.json()['last_name'], 'user_last_name')
        self.assertEqual(response.json()['first_name'], 'user_first_name')
        self.assertEqual(response.json()['phone_number'], '08012345678')
        print('test_get_me_user ok')

# class IntegrationTests(TestCase):
#     def setUp(self):
#         self.client = APIClient()

#     @patch('member_management.services.user_service.UserService.send_verification_email')
#     def test_full_flow(self, mock_send_email):
#         # 1. 登録
#         print('test_register ok')
#         response = self.organization_client.post('/member_management/api/register/', {
#             'username': 'test_org@gmail.com',
#             'name': 'Test Org',
#             'phone_number': '08012345678',
#             'last_name': 'org_last_name',
#             'first_name': 'org_first_name',
#             'email': 'test_org@gmail.com',
#             'password': 'test_org'
#         }, format='json')
#         self.assertEqual(response.status_code, 201)
#         mock_send_email.assert_called_once()
#         print('test_register ok')

#         # 2. メール認証
#         user = User.objects.get(email='test_org@gmail.com')
#         verify_response = self.client.get(
#             reverse('verify_email', kwargs={'uidb64': urlsafe_base64_encode(force_bytes(user.pk))})
#         )
#         self.assertIn(verify_response.status_code, [200, 302])
#         print('test_verify_email ok')
#         # 3. ログイン
#         login_response = self.client.post('/api/token/', {
#             'username': 'test_org@gmail.com',
#             'password': 'test_org'
#         })
#         self.assertEqual(login_response.status_code, 200)
#         print('test_login ok')
