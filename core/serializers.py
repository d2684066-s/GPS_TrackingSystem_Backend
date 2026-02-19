# core/serializers.py
from rest_framework import serializers
from .models import (
    User, Vehicle, Trip, Booking, Offence, RFIDDevice
)
from django.contrib.auth.hashers import make_password, check_password

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'name', 'phone', 'email', 'registration_id',
            'role', 'driver_type', 'created_at', 'dob'
        ]
        read_only_fields = ['id', 'created_at']

class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            'name', 'phone', 'password', 'registration_id',
            'email', 'dob', 'role', 'driver_type'
        ]

    def create(self, validated_data):
        validated_data['password'] = make_password(validated_data['password'])
        return super().create(validated_data)

class UserLoginSerializer(serializers.Serializer):
    phone = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        if not data.get('phone') and not data.get('email'):
            raise serializers.ValidationError("Phone or email is required")
        return data

class TokenResponseSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    token_type = serializers.CharField(default='bearer')
    user = UserSerializer()

class VehicleSerializer(serializers.ModelSerializer):
    assigned_to = serializers.UUIDField(source='assigned_to.id', read_only=True, allow_null=True)
    assigned_driver_name = serializers.CharField(read_only=True)

    class Meta:
        model = Vehicle
        fields = '__all__'

class VehicleCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = ['vehicle_number', 'gps_imei', 'barcode', 'vehicle_type']

class TripSerializer(serializers.ModelSerializer):
    vehicle = serializers.UUIDField(source='vehicle.id')
    driver = serializers.UUIDField(source='driver.id')

    class Meta:
        model = Trip
        fields = '__all__'

class BookingSerializer(serializers.ModelSerializer):
    driver = serializers.UUIDField(source='driver.id', read_only=True, allow_null=True)
    vehicle = serializers.UUIDField(source='vehicle.id', read_only=True, allow_null=True)

    class Meta:
        model = Booking
        fields = '__all__'

class BookingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = ['student_registration_id', 'student_name', 'phone', 'place', 'place_details', 'user_location']

class OffenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Offence
        fields = '__all__'

class RFIDDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = RFIDDevice
        fields = '__all__'