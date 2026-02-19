from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth.hashers import check_password, make_password
from django.db.models import Q 
from django.utils import timezone
import logging

from .models import User, Vehicle, Booking, Offence, RFIDDevice, Trip
from .serializers import (
    UserCreateSerializer, UserLoginSerializer, UserSerializer,
    TokenResponseSerializer, BookingCreateSerializer, BookingSerializer,
    VehicleSerializer, VehicleCreateSerializer,
    TripSerializer,
    OffenceSerializer,
    RFIDDeviceSerializer,
)
from .utils import (
    create_access_token, send_otp_mock, verify_otp_mock, generate_otp,
    calculate_distance, calculate_eta
)
from .permissions import IsAdmin, IsDriver
from rest_framework_simplejwt.tokens import RefreshToken

logger = logging.getLogger(__name__)


class SignupView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserCreateSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            token = create_access_token(user)
            user_data = UserSerializer(user).data
            return Response({
                "access_token": token,
                "token_type": "bearer",
                "user": user_data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        phone = serializer.validated_data.get('phone')
        email = serializer.validated_data.get('email')
        password = serializer.validated_data['password']

        try:
            if phone:
                user = User.objects.get(phone=phone)
            elif email:
                user = User.objects.get(email=email)
            else:
                return Response({"detail": "Phone or email required"}, status=400)
        except User.DoesNotExist:
            return Response({"detail": "Invalid credentials"}, status=401)

        if not check_password(password, user.password):
            return Response({"detail": "Invalid credentials"}, status=401)

        token = create_access_token(user)
        user_data = UserSerializer(user).data

        return Response({
            "access_token": token,
            "token_type": "bearer",
            "user": user_data
        })


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        phone = request.data.get('phone')
        if not phone:
            return Response({"detail": "Phone required"}, status=400)

        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=404)

        otp = generate_otp()
        send_otp_mock(phone, otp)
        # In real app → send via SMS gateway

        return Response({
            "message": "OTP sent successfully",
            # "otp": otp   # ← remove this in production!
        })


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        phone = request.data.get('phone')
        otp = request.data.get('otp')
        new_password = request.data.get('new_password')

        if not all([phone, otp, new_password]):
            return Response({"detail": "All fields required"}, status=400)

        if not verify_otp_mock(phone, otp):
            return Response({"detail": "Invalid or expired OTP"}, status=400)

        try:
            user = User.objects.get(phone=phone)
            user.password = make_password(new_password)
            user.save()
            return Response({"message": "Password reset successfully"})
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=404)


# ────────────────────────────────────────────────
# Example: Public - Book Ambulance (student side)
# ────────────────────────────────────────────────
# core/views.py
class BookAmbulanceView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = BookingCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        # Extract validated data
        validated_data = serializer.validated_data

        # Auto-fill student_name if not provided
        student_name = validated_data.get('student_name')
        student_reg_id = validated_data['student_registration_id']

        if not student_name:
            try:
                student = User.objects.get(registration_id=student_reg_id)
                student_name = student.name
            except User.DoesNotExist:
                student_name = "Unknown Student"  # fallback

        # Create the booking with the name filled
        booking = Booking.objects.create(
            **validated_data,
            student_name=student_name,
            # You can also auto-fill other fields if needed, e.g.:
            # phone = request.user.phone if not validated_data.get('phone') else validated_data['phone']
        )

        # Return the full serialized booking
        return Response(BookingSerializer(booking).data, status=201)


# Add more views later (get active buses, pending bookings, etc.)

# ────────────────────────────────────────────────
# Driver Endpoints
# ────────────────────────────────────────────────

class AvailableVehiclesView(APIView):
    permission_classes = [IsDriver]

    def get(self, request, vehicle_type):
        vehicles = Vehicle.objects.filter(
            vehicle_type=vehicle_type,
            assigned_to__isnull=True
        )
        serializer = VehicleSerializer(vehicles, many=True)
        return Response({"vehicles": serializer.data})


class AssignVehicleView(APIView):
    permission_classes = [IsDriver]

    def post(self, request, vehicle_id):
        try:
            vehicle = Vehicle.objects.get(id=vehicle_id)
        except Vehicle.DoesNotExist:
            return Response({"detail": "Vehicle not found"}, status=404)

        if vehicle.assigned_to is not None:
            return Response({"detail": "Vehicle already assigned"}, status=400)

        vehicle.assigned_to = request.user
        vehicle.assigned_driver_name = request.user.name
        vehicle.save()

        return Response({"message": "Vehicle assigned successfully"})


class ReleaseVehicleView(APIView):
    permission_classes = [IsDriver]

    def post(self, request, vehicle_id):
        try:
            vehicle = Vehicle.objects.get(id=vehicle_id)
        except Vehicle.DoesNotExist:
            return Response({"detail": "Vehicle not found"}, status=404)

        if vehicle.assigned_to != request.user:
            return Response({"detail": "Vehicle not assigned to you"}, status=403)

        vehicle.assigned_to = None
        vehicle.assigned_driver_name = None
        vehicle.save()

        return Response({"message": "Vehicle released successfully"})


class StartTripView(APIView):
    permission_classes = [IsDriver]

    def post(self, request):
        vehicle_id = request.data.get('vehicle_id')
        if not vehicle_id:
            return Response({"detail": "vehicle_id required"}, status=400)

        try:
            vehicle = Vehicle.objects.get(id=vehicle_id, assigned_to=request.user)
        except Vehicle.DoesNotExist:
            return Response({"detail": "Vehicle not found or not assigned to you"}, status=404)

        # Check for existing active trip
        if Trip.objects.filter(driver=request.user, is_active=True).exists():
            return Response({"detail": "You already have an active trip"}, status=400)

        trip = Trip.objects.create(
            vehicle=vehicle,
            driver=request.user,
            vehicle_number=vehicle.vehicle_number,
            driver_name=request.user.name,
            vehicle_type=vehicle.vehicle_type,
            is_active=True
        )

        return Response(TripSerializer(trip).data, status=201)


class EndTripView(APIView):
    permission_classes = [IsDriver]

    def post(self, request, trip_id):
        try:
            trip = Trip.objects.get(id=trip_id, driver=request.user, is_active=True)
        except Trip.DoesNotExist:
            return Response({"detail": "Active trip not found"}, status=404)

        trip.is_active = False
        trip.end_time = timezone.now()
        trip.save()

        # Optional: clear current location
        trip.vehicle.current_location = {}
        trip.vehicle.save()

        return Response({"message": "Trip ended successfully"})


class MarkOutOfStationView(APIView):
    permission_classes = [IsDriver]

    def post(self, request, vehicle_id):
        is_out = request.data.get('is_out_of_station')
        if is_out is None:
            return Response({"detail": "is_out_of_station (bool) required"}, status=400)

        try:
            vehicle = Vehicle.objects.get(id=vehicle_id, assigned_to=request.user)
        except Vehicle.DoesNotExist:
            return Response({"detail": "Vehicle not found or not yours"}, status=404)

        vehicle.is_out_of_station = bool(is_out)
        vehicle.save()

        status_str = "out of" if is_out else "in"
        return Response({"message": f"Vehicle marked as {status_str} station"})


class PendingBookingsView(APIView):
    permission_classes = [IsDriver]

    def get(self, request):
        bookings = Booking.objects.filter(status='pending').order_by('-created_at')
        serializer = BookingSerializer(bookings, many=True)
        return Response({"bookings": serializer.data})


class AcceptBookingView(APIView):
    permission_classes = [IsDriver]

    def post(self, request, booking_id):
        try:
            booking = Booking.objects.get(id=booking_id, status='pending')
        except Booking.DoesNotExist:
            return Response({"detail": "Booking not found or not pending"}, status=404)

        # Get driver's ambulance
        ambulance = Vehicle.objects.filter(
            assigned_to=request.user,
            vehicle_type='ambulance'
        ).first()

        if not ambulance:
            return Response({"detail": "No ambulance assigned to you"}, status=400)

        otp = generate_otp()
        send_otp_mock(booking.phone, otp)

        eta = None
        if ambulance.current_location and booking.user_location:
            loc_v = ambulance.current_location
            loc_u = booking.user_location
            dist = calculate_distance(
                loc_v.get('lat', 0), loc_v.get('lng', 0),
                loc_u.get('lat', 0), loc_u.get('lng', 0)
            )
            eta = calculate_eta(dist, 60)  # ambulance speed

        booking.status = 'accepted'
        booking.driver = request.user
        booking.driver_name = request.user.name
        booking.vehicle = ambulance
        booking.vehicle_number = ambulance.vehicle_number
        booking.otp = otp
        booking.eta_minutes = round(eta, 1) if eta else None
        booking.save()

        return Response({
            "message": "Booking accepted",
            "otp": otp,               # remove in prod
            "booking": BookingSerializer(booking).data
        })


class AbortBookingView(APIView):
    permission_classes = [IsDriver]

    def post(self, request, booking_id):
        Booking.objects.filter(
            id=booking_id,
            driver=request.user
        ).update(status='cancelled')
        return Response({"message": "Booking cancelled"})


class VerifyOTPView(APIView):
    permission_classes = [IsDriver]

    def post(self, request):
        booking_id = request.data.get('booking_id')
        otp = request.data.get('otp')

        if not all([booking_id, otp]):
            return Response({"detail": "booking_id and otp required"}, status=400)

        try:
            booking = Booking.objects.get(
                id=booking_id,
                driver=request.user,
                otp=otp
            )
        except Booking.DoesNotExist:
            return Response({"detail": "Invalid OTP or booking not assigned to you"}, status=400)

        booking.status = 'in_progress'
        booking.save()

        return Response({"message": "OTP verified, ride started"})


class CompleteBookingView(APIView):
    permission_classes = [IsDriver]

    def post(self, request, booking_id):
        Booking.objects.filter(
            id=booking_id,
            driver=request.user
        ).update(status='completed')
        return Response({"message": "Booking completed"})


class MyTripsView(APIView):
    permission_classes = [IsDriver]

    def get(self, request):
        trips = Trip.objects.filter(driver=request.user).order_by('-start_time')
        serializer = TripSerializer(trips, many=True)
        return Response({"trips": serializer.data})


class ActiveTripView(APIView):
    permission_classes = [IsDriver]

    def get(self, request):
        trip = Trip.objects.filter(driver=request.user, is_active=True).first()
        if trip:
            return Response({"trip": TripSerializer(trip).data})
        return Response({"trip": None})
    
# ────────────────────────────────────────────────
# Admin Endpoints
# ────────────────────────────────────────────────

class AdminStatsView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        total_students = User.objects.filter(role='student').count()
        total_drivers = User.objects.filter(role='driver').count()
        total_buses = Vehicle.objects.filter(vehicle_type='bus').count()
        total_ambulances = Vehicle.objects.filter(vehicle_type='ambulance').count()
        active_trips = Trip.objects.filter(is_active=True).count()
        pending_bookings = Booking.objects.filter(status='pending').count()
        total_offences = Offence.objects.count()
        unpaid_offences = Offence.objects.filter(is_paid=False).count()

        return Response({
            "total_students": total_students,
            "total_drivers": total_drivers,
            "total_buses": total_buses,
            "total_ambulances": total_ambulances,
            "active_trips": active_trips,
            "pending_bookings": pending_bookings,
            "total_offences": total_offences,
            "unpaid_offences": unpaid_offences,
        })


class AddVehicleView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request):
        serializer = VehicleCreateSerializer(data=request.data)
        if serializer.is_valid():
            vehicle = serializer.save()
            return Response(VehicleSerializer(vehicle).data, status=201)
        return Response(serializer.errors, status=400)


class VehicleListView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        vehicle_type = request.query_params.get('vehicle_type')
        search = request.query_params.get('search')

        queryset = Vehicle.objects.all()
        if vehicle_type:
            queryset = queryset.filter(vehicle_type=vehicle_type)
        if search:
            queryset = queryset.filter(
                Q(vehicle_number__icontains=search) |
                Q(gps_imei__icontains=search)
            )

        serializer = VehicleSerializer(queryset, many=True)
        return Response({"vehicles": serializer.data})


class DeleteVehicleView(APIView):
    permission_classes = [IsAdmin]

    def delete(self, request, vehicle_id):
        try:
            vehicle = Vehicle.objects.get(id=vehicle_id)
            vehicle.delete()
            return Response({"message": "Vehicle deleted"})
        except Vehicle.DoesNotExist:
            return Response({"detail": "Vehicle not found"}, status=404)


class StudentListView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        search = request.query_params.get('search')
        queryset = User.objects.filter(role='student')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(registration_id__icontains=search) |
                Q(phone__icontains=search)
            )
        serializer = UserSerializer(queryset, many=True)
        return Response({"students": serializer.data})


class DeleteStudentView(APIView):
    permission_classes = [IsAdmin]

    def delete(self, request, student_id):
        deleted = User.objects.filter(id=student_id, role='student').delete()
        if deleted[0] == 0:
            return Response({"detail": "Student not found"}, status=404)
        return Response({"message": "Student deleted"})


class DriverListView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        driver_type = request.query_params.get('driver_type')
        search = request.query_params.get('search')

        queryset = User.objects.filter(role='driver')
        if driver_type:
            queryset = queryset.filter(driver_type=driver_type)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(registration_id__icontains=search) |
                Q(phone__icontains=search)
            )

        serializer = UserSerializer(queryset, many=True)
        return Response({"drivers": serializer.data})


class DeleteDriverView(APIView):
    permission_classes = [IsAdmin]

    def delete(self, request, driver_id):
        # Release vehicles first
        Vehicle.objects.filter(assigned_to__id=driver_id).update(
            assigned_to=None, assigned_driver_name=None
        )

        deleted = User.objects.filter(id=driver_id, role='driver').delete()
        if deleted[0] == 0:
            return Response({"detail": "Driver not found"}, status=404)
        return Response({"message": "Driver deleted"})


class OffenceListView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        offence_type = request.query_params.get('offence_type')
        is_paid = request.query_params.get('is_paid')
        search = request.query_params.get('search')

        queryset = Offence.objects.all().order_by('-created_at')
        if offence_type:
            queryset = queryset.filter(offence_type=offence_type)
        if is_paid is not None:
            is_paid_bool = is_paid.lower() == 'true'
            queryset = queryset.filter(is_paid=is_paid_bool)
        if search:
            queryset = queryset.filter(
                Q(driver_name__icontains=search) |
                Q(student_name__icontains=search) |
                Q(vehicle_number__icontains=search)
            )

        serializer = OffenceSerializer(queryset, many=True)
        return Response({"offences": serializer.data})


class DeleteOffenceView(APIView):
    permission_classes = [IsAdmin]

    def delete(self, request, offence_id):
        deleted = Offence.objects.filter(id=offence_id).delete()
        if deleted[0] == 0:
            return Response({"detail": "Offence not found"}, status=404)
        return Response({"message": "Offence deleted"})


class MarkOffencePaidView(APIView):
    permission_classes = [IsAdmin]

    def patch(self, request, offence_id):
        updated = Offence.objects.filter(id=offence_id).update(is_paid=True)
        if updated == 0:
            return Response({"detail": "Offence not found"}, status=404)
        return Response({"message": "Offence marked as paid"})


class AddRFIDDeviceView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request):
        serializer = RFIDDeviceSerializer(data=request.data)
        if serializer.is_valid():
            device = serializer.save()
            return Response(RFIDDeviceSerializer(device).data, status=201)
        return Response(serializer.errors, status=400)


class RFIDDeviceListView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        devices = RFIDDevice.objects.all()
        serializer = RFIDDeviceSerializer(devices, many=True)
        return Response({"devices": serializer.data})


class DeleteRFIDDeviceView(APIView):
    permission_classes = [IsAdmin]

    def delete(self, request, device_id):
        deleted = RFIDDevice.objects.filter(id=device_id).delete()
        if deleted[0] == 0:
            return Response({"detail": "Device not found"}, status=404)
        return Response({"message": "Device deleted"})


class TripListView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        is_active = request.query_params.get('is_active')
        vehicle_type = request.query_params.get('vehicle_type')

        queryset = Trip.objects.all().order_by('-start_time')
        if is_active is not None:
            queryset = queryset.filter(is_active=(is_active.lower() == 'true'))
        if vehicle_type:
            queryset = queryset.filter(vehicle_type=vehicle_type)

        serializer = TripSerializer(queryset, many=True)
        return Response({"trips": serializer.data})


class BookingListView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        status_filter = request.query_params.get('status')
        queryset = Booking.objects.all().order_by('-created_at')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        serializer = BookingSerializer(queryset, many=True)
        return Response({"bookings": serializer.data})
    

# ────────────────────────────────────────────────
# Public / Misc Endpoints
# ────────────────────────────────────────────────

class ActiveBusesView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        # Use vehicle_type from Trip (denormalized field) to avoid JOIN
        active_trips = Trip.objects.filter(is_active=True, vehicle_type="bus")

        if active_trips.exists():
            buses = []
            for trip in active_trips:
                vehicle = trip.vehicle
                # Reset out-of-station flag if active trip exists
                if vehicle.is_out_of_station:
                    vehicle.is_out_of_station = False
                    vehicle.save()
                buses.append({
                    "trip_id": str(trip.id),
                    "vehicle_id": str(vehicle.id),
                    "vehicle_number": vehicle.vehicle_number,
                    "driver_name": trip.driver_name,
                    "location": vehicle.current_location,
                    "is_out_of_station": False
                })
            return Response({"buses": buses, "all_out_of_station": False})

        # No active trips → check all buses
        all_buses = Vehicle.objects.filter(vehicle_type="bus")
        if not all_buses.exists():
            return Response({"message": "No buses registered", "buses": [], "all_out_of_station": False})

        all_out = all(v.is_out_of_station for v in all_buses)
        if all_out:
            return Response({"message": "All buses are out of station", "buses": [], "all_out_of_station": True})

        return Response({"message": "No active bus trips at the moment", "buses": [], "all_out_of_station": False})

class BusETAView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, bus_id):
        user_lat = request.query_params.get('user_lat')
        user_lng = request.query_params.get('user_lng')
        
        if not all([user_lat, user_lng]):
            return Response({"detail": "user_lat and user_lng required"}, status=400)
        
        try:
            vehicle = Vehicle.objects.get(id=bus_id, vehicle_type='bus')
        except Vehicle.DoesNotExist:
            return Response({"detail": "Bus not found"}, status=404)
        
        if not vehicle.current_location:
            return Response({"eta_minutes": None, "message": "Bus location not available"})
        
        loc = vehicle.current_location
        distance = calculate_distance(
            float(loc.get('lat', 0)), float(loc.get('lng', 0)),
            float(user_lat), float(user_lng)
        )
        eta = calculate_eta(distance, 40)  # BUS_SPEED_LIMIT
        
        return Response({
            "bus_location": loc,
            "user_location": {"lat": float(user_lat), "lng": float(user_lng)},
            "distance_km": round(distance, 2),
            "eta_minutes": round(eta, 1),
            "speed_assumed_kmh": 40
        })


class AvailableAmbulancesView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        ambulances = Vehicle.objects.filter(vehicle_type='ambulance', assigned_to__isnull=True)
        serializer = VehicleSerializer(ambulances, many=True)
        return Response({"ambulances": serializer.data})


class MyBookingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        bookings = Booking.objects.filter(phone=request.user.phone).order_by('-created_at')
        serializer = BookingSerializer(bookings, many=True)
        return Response({"bookings": serializer.data})


class CheckUserView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        phone = request.data.get('phone')
        registration_id = request.data.get('registration_id')
        
        if not phone and not registration_id:
            return Response({"detail": "Phone or registration_id required"}, status=400)
        
        query = Q()
        if phone:
            query |= Q(phone=phone)
        if registration_id:
            query |= Q(registration_id=registration_id)
        
        exists = User.objects.filter(query).exists()
        user = None
        if exists:
            user_obj = User.objects.filter(query).first()
            user = UserSerializer(user_obj).data
        
        return Response({"exists": exists, "user": user})


# ────────────────────────────────────────────────
# GPS & RFID Receiver (device → server)
# ────────────────────────────────────────────────

class ReceiveGPSView(APIView):
    permission_classes = [AllowAny]  # in production → API key or auth

    def post(self, request):
        imei = request.data.get('imei')
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        speed = request.data.get('speed')
        timestamp = request.data.get('timestamp')

        if not all([imei, latitude, longitude, speed]):
            return Response({"detail": "Missing required fields"}, status=400)

        try:
            vehicle = Vehicle.objects.get(gps_imei=imei)
        except Vehicle.DoesNotExist:
            return Response({"detail": "Vehicle not found for this IMEI"}, status=404)

        location = {
            "lat": float(latitude),
            "lng": float(longitude),
            "speed": float(speed),
            "timestamp": timestamp or timezone.now().isoformat()
        }

        vehicle.current_location = location
        vehicle.save()

        # Overspeed check (bus only)
        if vehicle.vehicle_type == 'bus' and float(speed) > 40:  # CAMPUS_SPEED_LIMIT
            driver_name = vehicle.assigned_driver_name
            offence = Offence.objects.create(
                offence_type='bus_overspeed',
                driver=vehicle.assigned_to,
                driver_name=driver_name,
                vehicle=vehicle,
                vehicle_number=vehicle.vehicle_number,
                speed=float(speed),
                speed_limit=40,
                location=location,
                is_paid=False
            )
            logger.warning(f"Overspeed: {vehicle.vehicle_number} @ {speed} km/h")

        # If ambulance → update active booking ETA
        if vehicle.vehicle_type == 'ambulance':
            active_booking = Booking.objects.filter(
                vehicle=vehicle,
                status__in=['accepted', 'in_progress']
            ).first()
            if active_booking and active_booking.user_location:
                u_loc = active_booking.user_location
                dist = calculate_distance(
                    location['lat'], location['lng'],
                    u_loc.get('lat', 0), u_loc.get('lng', 0)
                )
                eta = calculate_eta(dist, 60)
                active_booking.eta_minutes = round(eta, 1)
                active_booking.save()
                # In real app → socket emit 'eta_update'

        return Response({"message": "GPS data received", "vehicle_id": str(vehicle.id)})


class ReceiveRFIDScanView(APIView):
    permission_classes = [AllowAny]  # → secure in production

    def post(self, request):
        rfid_device_id = request.data.get('rfid_device_id')
        student_registration_id = request.data.get('student_registration_id')
        student_name = request.data.get('student_name')
        phone = request.data.get('phone')
        speed = request.data.get('speed')
        timestamp = request.data.get('timestamp')

        if not all([rfid_device_id, student_registration_id, speed]):
            return Response({"detail": "Missing required fields"}, status=400)

        try:
            device = RFIDDevice.objects.get(rfid_id=rfid_device_id)
        except RFIDDevice.DoesNotExist:
            return Response({"detail": "RFID device not registered"}, status=404)

        if float(speed) > 40:  # CAMPUS_SPEED_LIMIT
            try:
                student = User.objects.get(registration_id=student_registration_id)
            except User.DoesNotExist:
                student = None

            Offence.objects.create(
                offence_type='student_speed',
                student=student,
                student_name=student_name,
                student_registration_id=student_registration_id,
                phone=phone,
                speed=float(speed),
                speed_limit=40,
                location={"name": device.location_name},
                rfid_number=rfid_device_id,
                is_paid=False
            )
            logger.warning(f"Student speed violation: {student_name} @ {speed} km/h")
            return Response({"message": "Speed violation recorded"})

        return Response({"message": "Scan recorded, no violation"})