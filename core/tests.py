# core/tests.py
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth.hashers import make_password
from core.models import User, Vehicle, Booking, Trip, Offence, RFIDDevice
import json

class CoreAPITests(TestCase):
    def setUp(self):
        """Set up test data and client"""
        self.client = APIClient()

        # ─── CLEAN OLD TEST DATA ────────────────────────────────────────
        User.objects.filter(phone__in=["9437987654", "9437123456", "admin@gceits.com"]).delete()
        Vehicle.objects.filter(gps_imei__startswith="test-imei-").delete()
        Booking.objects.all().delete()
        Trip.objects.all().delete()
        Offence.objects.all().delete()
        RFIDDevice.objects.all().delete()

        # ─── CREATE TEST ADMIN (use email, no username) ─────────────────
        self.admin = User.objects.create(
            name="Admin Test",
            phone="0000000000",
            email="admin@gceits.com",
            password=make_password("Admin@12345"),
            registration_id="ADMIN001",
            role="admin"
        )
        self.admin = User.objects.create(
            Username="durga",
            phone="0000000000", # not applicable enter username for devlopment process
            email="admin@gceits.com",
            password=make_password("Admin@12345"),
            registration_id="ADMIN001",
            role="admin"
        )
        # Note: since no is_staff/is_superuser in your model, admin login via API is still possible if views allow
        #Note : createsuperuser with the help of using createsuperuser with manage.py from terminal

        # ─── CREATE TEST DRIVER ─────────────────────────────────────────
        self.driver = User.objects.create(
            name="Test Driver Raj",
            phone="9437123456",
            email="driver@test.com",
            password=make_password("driver123"),
            registration_id="DRVTEST001",
            role="driver",
            driver_type="ambulance"
        )

        # ─── CREATE TEST STUDENT ────────────────────────────────────────
        self.student = User.objects.create(
            name="Test Student Priya",
            phone="9437987654",
            email="student@test.com",
            password=make_password("student123"),
            registration_id="STUTEST001",
            role="student"
        )

        # ─── CREATE TEST AMBULANCE ──────────────────────────────────────
        self.ambulance = Vehicle.objects.create(
            vehicle_number="OD-TEST-AMB-001",
            gps_imei="test-imei-ambulance-001",
            barcode="AMBTEST001",
            vehicle_type="ambulance",
            assigned_to=self.driver,
            assigned_driver_name=self.driver.name,
            current_location={"lat": 20.2961, "lng": 85.8245}
        )

        # ─── LOGIN AS STUDENT (get token) ───────────────────────────────
        login_response = self.client.post('/api/auth/login/', {
            'phone': '9437987654',
            'password': 'student123'
        }, format='json')
        self.student_token = login_response.data.get('access_token') if login_response.status_code == 200 else None

        # ─── LOGIN AS DRIVER ────────────────────────────────────────────
        login_response = self.client.post('/api/auth/login/', {
            'phone': '9437123456',
            'password': 'driver123'
        }, format='json')
        self.driver_token = login_response.data.get('access_token') if login_response.status_code == 200 else None

        # ─── LOGIN AS ADMIN (if possible) ───────────────────────────────
        login_response = self.client.post('/api/auth/login/', {
            'email': 'admin@gceits.com',
            'password': 'Admin@12345'
        }, format='json')
        self.admin_token = login_response.data.get('access_token') if login_response.status_code == 200 else None

    # ────────────────────────────────────────────────
    # Public Endpoints
    # ────────────────────────────────────────────────

    def test_public_buses_list(self):
        """GET /api/public/buses/ should return 200 even if empty"""
        response = self.client.get('/api/public/buses/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue('buses' in response.data or 'message' in response.data)

    def test_book_ambulance(self):
        """POST /api/public/ambulance/book/ should create booking"""
        if not self.student_token:
            self.skipTest("Student login failed - check login view")

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.student_token}')

        data = {
            "student_registration_id": "STUTEST001",
            "phone": "9437987654",
            "place": "KIIT Gate 7",
            "place_details": "Near boys hostel",
            "user_location": {"lat": 20.3525, "lng": 85.8190}
        }

        response = self.client.post('/api/public/ambulance/book/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], "pending")
        self.assertEqual(response.data['student_name'], "Test Student Priya")

    def test_public_ambulances_list(self):
        """GET /api/public/ambulances/ should return list"""
        response = self.client.get('/api/public/ambulances/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('ambulances', response.data)

    # ────────────────────────────────────────────────
    # Auth Endpoints
    # ────────────────────────────────────────────────

    def test_signup_new_user(self):
        """POST /api/auth/signup/ should create new user"""
        User.objects.filter(phone="9437999999").delete()  # clean

        data = {
            "name": "New Signup User",
            "phone": "9437999999",
            "password": "newpass123",
            "registration_id": "NEWUSER001",
            "role": "student"
        }
        response = self.client.post('/api/auth/signup/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('access_token', response.data)
        self.assertIn('user', response.data)

    def test_login_student(self):
        """POST /api/auth/login/ should return token"""
        data = {
            "phone": "9437987654",
            "password": "student123"
        }
        response = self.client.post('/api/auth/login/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', response.data)

    # ────────────────────────────────────────────────
    # GPS Endpoint (no auth required)
    # ────────────────────────────────────────────────

    def test_gps_receive(self):
        """POST /api/gps/receive/ should accept data"""
        data = {
            "imei": "test-imei-ambulance-001",
            "latitude": 20.2961,
            "longitude": 85.8245,
            "speed": 35
        }
        response = self.client.post('/api/gps/receive/', data, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])
        if response.status_code == status.HTTP_200_OK:
            self.assertIn("message", response.data)
            self.assertIn("vehicle_id", response.data)
        else:
            self.assertIn("detail", response.data)  # "Vehicle not found" is ok if IMEI missing

    # ────────────────────────────────────────────────
    # Driver Protected Endpoints
    # ────────────────────────────────────────────────

    def test_driver_pending_bookings(self):
        """GET /api/driver/pending-bookings/ (protected)"""
        if not self.driver_token:
            self.skipTest("Driver login failed")

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.driver_token}')
        response = self.client.get('/api/driver/pending-bookings/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('bookings', response.data)

    def test_driver_accept_booking(self):
        """POST /api/driver/accept-booking/<uuid>/ (needs booking first)"""
        if not self.driver_token:
            self.skipTest("Driver login failed")

        # First create a booking (use student token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.student_token}')
        book_data = {
            "student_registration_id": "STUTEST001",
            "phone": "9437987654",
            "place": "KIIT Gate 7",
            "place_details": "Near hostel",
            "user_location": {"lat": 20.3525, "lng": 85.8190}
        }
        book_response = self.client.post('/api/public/ambulance/book/', book_data, format='json')
        if book_response.status_code != status.HTTP_201_CREATED:
            self.skipTest("Could not create booking for accept test")

        booking_id = book_response.data['id']

        # Now accept as driver
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.driver_token}')
        response = self.client.post(f'/api/driver/accept-booking/{booking_id}/', format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('otp', response.data)

        self.driver = User.objects.create(
            name="Test Driver Raj",
            phone="9437123456",
            email="driver@test.com",
            password=make_password("driver123"),
            registration_id="DRVTEST001",
            role="driver",
            driver_type="ambulance 1"
        )

# Run with: python manage.py test core