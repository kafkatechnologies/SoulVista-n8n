from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import swisseph as swe
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from datetime import datetime
import pytz
import time

app = FastAPI()

# Vedic Constants
SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
NAKSHATRAS = ["Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra", "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"]
PLANET_MAP = {"Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS, "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER, "Venus": swe.VENUS, "Saturn": swe.SATURN, "Rahu": swe.MEAN_NODE}

class BirthData(BaseModel):
    dateOfBirth: str
    timeOfBirth: str
    placeOfBirth: str
    stateOfBirth: str

def get_navamsha_data(longitude):
    idx = int(longitude / (10/3)) % 12
    return SIGNS[idx]

@app.post("/calculate")
def calculate(data: BirthData):
    try:
        # 1. Get Coordinates
        geolocator = Nominatim(user_agent="soulvista_engine")
        location = geolocator.geocode(f"{data.placeOfBirth}, {data.stateOfBirth}, India")
        if not location:
            raise HTTPException(status_code=400, detail="Location not found")
        
        # 2. Get Timezone
        tf = TimezoneFinder()
        tz_name = tf.timezone_at(lng=location.longitude, lat=location.latitude)
        
        # 3. Process Time 
        # Extract HH:MM if time format is HH:MM:SS
        clean_time = ":".join(data.timeOfBirth.split(":")[:2])
        
        local_tz = pytz.timezone(tz_name)
        # Format strictly changed to dd/mm/yyyy
        local_dt = datetime.strptime(f"{data.dateOfBirth} {clean_time}", "%d/%m/%Y %H:%M")
        utc_dt = local_tz.localize(local_dt).astimezone(pytz.utc)
        jd_ut = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour + utc_dt.minute/60.0)

        # 4. Calculations
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
        ayan = swe.get_ayanamsa_ut(jd_ut)
        
        _, ascmc = swe.houses_ex(jd_ut, location.latitude, location.longitude, b'W')
        d1_lag_lon = (ascmc[0] - ayan) % 360
        
        planets = []
        for name, code in PLANET_MAP.items():
            res, _ = swe.calc_ut(jd_ut, code, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)
            p_lon = res[0]
            planets.append({
                "planet": name,
                "d1_sign": SIGNS[int(p_lon / 30)],
                "degree": round(p_lon % 30, 2),
                "d9_sign": get_navamsha_data(p_lon),
                "nakshatra": NAKSHATRAS[int(p_lon / (40/3)) % 27]
            })

        return {
            "ascendant": SIGNS[int(d1_lag_lon / 30)],
            "planetary_placements": planets,
            "metadata": {"timezone": tz_name, "lat": location.latitude, "lon": location.longitude}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
