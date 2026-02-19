# core/utils.py
import random
import math
from datetime import datetime, timezone, timedelta
from rest_framework_simplejwt.tokens import AccessToken
from .models import User

def generate_otp(length=6):
    return str(random.randint(10**(length-1), 10**length - 1))

# In-memory OTP store (use Redis in production)
otp_storage = {}

def send_otp_mock(phone: str, otp: str):
    otp_storage[phone] = {
        'otp': otp,
        'expires': datetime.now(timezone.utc) + timedelta(minutes=10)
    }
    print(f"[MOCK OTP] Sent {otp} to {phone}")  # replace with real SMS later
    return True

def verify_otp_mock(phone: str, otp: str) -> bool:
    if phone in otp_storage:
        stored = otp_storage[phone]
        if stored['otp'] == otp and stored['expires'] > datetime.now(timezone.utc):
            del otp_storage[phone]
            return True
    return False

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c

def calculate_eta(distance_km: float, speed_kmh: float) -> float:
    if speed_kmh <= 0:
        return 0
    return (distance_km / speed_kmh) * 60

# Custom JWT creation (if you want to match exactly the old format)
def create_access_token(user: User):
    token = AccessToken.for_user(user)
    token['user_id'] = str(user.id)
    token['role'] = user.role
    return str(token)