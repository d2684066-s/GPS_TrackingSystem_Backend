from django.urls import path
from .views import (
    # Auth
    SignupView,
    LoginView,
    MeView,
    ForgotPasswordView,
    ResetPasswordView,

    # Public / Student
    BookAmbulanceView,
    ActiveBusesView,
    BusETAView,
    AvailableAmbulancesView,
    MyBookingsView,
    CheckUserView,

    # Driver
    AvailableVehiclesView,
    AssignVehicleView,
    ReleaseVehicleView,
    StartTripView,
    EndTripView,
    MarkOutOfStationView,
    PendingBookingsView,
    AcceptBookingView,
    AbortBookingView,
    VerifyOTPView,
    CompleteBookingView,
    MyTripsView,
    ActiveTripView,

    # Admin
    AdminStatsView,
    AddVehicleView,
    VehicleListView,
    DeleteVehicleView,
    StudentListView,
    DeleteStudentView,
    DriverListView,
    DeleteDriverView,
    OffenceListView,
    DeleteOffenceView,
    MarkOffencePaidView,
    AddRFIDDeviceView,
    RFIDDeviceListView,
    DeleteRFIDDeviceView,
    TripListView,
    BookingListView,

    # GPS & RFID
    ReceiveGPSView,
    ReceiveRFIDScanView,
)

urlpatterns = [
    # Auth
    path('auth/signup/', SignupView.as_view(), name='signup'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/me/', MeView.as_view(), name='me'),
    path('auth/forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('auth/reset-password/', ResetPasswordView.as_view(), name='reset-password'),

    # Public / Student
    path('public/ambulance/book/', BookAmbulanceView.as_view(), name='book-ambulance'),

    # Driver routes
    path('driver/available-vehicles/<str:vehicle_type>/', AvailableVehiclesView.as_view(), name='available-vehicles'),
    path('driver/assign-vehicle/<uuid:vehicle_id>/', AssignVehicleView.as_view(), name='assign-vehicle'),
    path('driver/release-vehicle/<uuid:vehicle_id>/', ReleaseVehicleView.as_view(), name='release-vehicle'),
    path('driver/start-trip/', StartTripView.as_view(), name='start-trip'),
    path('driver/end-trip/<uuid:trip_id>/', EndTripView.as_view(), name='end-trip'),
    path('driver/mark-out-of-station/<uuid:vehicle_id>/', MarkOutOfStationView.as_view(), name='mark-out-of-station'),
    path('driver/pending-bookings/', PendingBookingsView.as_view(), name='pending-bookings'),
    path('driver/accept-booking/<uuid:booking_id>/', AcceptBookingView.as_view(), name='accept-booking'),
    path('driver/abort-booking/<uuid:booking_id>/', AbortBookingView.as_view(), name='abort-booking'),
    path('driver/verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('driver/complete-booking/<uuid:booking_id>/', CompleteBookingView.as_view(), name='complete-booking'),
    path('driver/my-trips/', MyTripsView.as_view(), name='my-trips'),
    path('driver/active-trip/', ActiveTripView.as_view(), name='active-trip'),

    # Admin routes
    path('admin/stats/', AdminStatsView.as_view(), name='admin-stats'),
    path('admin/vehicles/', AddVehicleView.as_view(), name='add-vehicle'),
    path('admin/vehicles/list/', VehicleListView.as_view(), name='vehicle-list'),
    path('admin/vehicles/<uuid:vehicle_id>/', DeleteVehicleView.as_view(), name='delete-vehicle'),
    
    path('admin/students/', StudentListView.as_view(), name='student-list'),
    path('admin/students/<uuid:student_id>/', DeleteStudentView.as_view(), name='delete-student'),
    
    path('admin/drivers/', DriverListView.as_view(), name='driver-list'),
    path('admin/drivers/<uuid:driver_id>/', DeleteDriverView.as_view(), name='delete-driver'),
    
    path('admin/offences/', OffenceListView.as_view(), name='offence-list'),
    path('admin/offences/<uuid:offence_id>/', DeleteOffenceView.as_view(), name='delete-offence'),
    path('admin/offences/<uuid:offence_id>/mark-paid/', MarkOffencePaidView.as_view(), name='mark-offence-paid'),
    
    path('admin/rfid-devices/', AddRFIDDeviceView.as_view(), name='add-rfid-device'),
    path('admin/rfid-devices/list/', RFIDDeviceListView.as_view(), name='rfid-list'),
    path('admin/rfid-devices/<uuid:device_id>/', DeleteRFIDDeviceView.as_view(), name='delete-rfid-device'),
    
    path('admin/trips/', TripListView.as_view(), name='trip-list'),
    path('admin/bookings/', BookingListView.as_view(), name='booking-list'),

    # Public
    path('public/buses/', ActiveBusesView.as_view(), name='active-buses'),
    path('public/bus/<uuid:bus_id>/eta/', BusETAView.as_view(), name='bus-eta'),
    path('public/ambulances/', AvailableAmbulancesView.as_view(), name='available-ambulances'),
    path('public/my-bookings/', MyBookingsView.as_view(), name='my-bookings'),
    path('public/check-user/', CheckUserView.as_view(), name='check-user'),

    # GPS & RFID (from devices)
    path('gps/receive/', ReceiveGPSView.as_view(), name='receive-gps'),
    path('rfid/scan/', ReceiveRFIDScanView.as_view(), name='receive-rfid'),
]