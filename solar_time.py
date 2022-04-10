from datetime import datetime

import astral
import astral.geocoder as geocoder
from astral.sun import sun

city: astral.LocationInfo = geocoder.lookup("Atlanta", geocoder.database())

print(city)
print(sun(city.observer, datetime.now()))
