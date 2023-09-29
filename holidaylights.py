import board
import neopixel
import time
import colorsys
import requests
import astral
from astral.sun import sun
import datetime
import pytz
import json
import random
import numpy as np
import sys

# Personal API key python file config.py
#   of form api_key = "bleh"
import config

def get_ip():
    response = requests.get('https://api64.ipify.org?format=json').json()
    return response['ip']

def get_location():
    ip_address = get_ip()
    response = requests.get(f'https://ipapi.co/{ip_address}/json/').json()
    return response

def get_sunset(loc):
    city = astral.LocationInfo(loc.get("city"),loc.get("region"),loc.get("timezone"),loc.get("latitude"), loc.get("longitude"))
    sunset = sun(city.observer, date=datetime.date.today(), tzinfo=loc.get("timezone"))["sunset"]
    return sunset

def get_timenow(loc):
    return datetime.datetime.now(pytz.timezone(loc.get('timezone')))

def get_weather(loc):
    lat = loc.get("latitude")
    lon = loc.get("longitude")
    url = "https://api.openweathermap.org/data/2.5/weather?lat=%s&lon=%s&appid=%s&units=metric" % (lat, lon, config.api_key)
    
    response = requests.get(url)
    data = json.loads(response.text)
    
    weather = data["weather"]
    wind = data['wind']
    clouds = data['clouds']
    
    # Now under weather, I need to check if multiple codes exist....
    numConditions = len(weather)

    # I should now have the number of conditions....
    # Conditions I care about is wind, rain, drizzle, thunderstorm
    
    # For wind, possibility that either wind is missing altogether, or just gust missing
    try:
        windData = [wind['speed'], wind['deg']]
    except: windData = [0,0]
    try:
        windData.append(100.0*min(1.0, wind['gust']/100.0))
    except:
        windData.append(0)

    # Now for cloud cover percentage (not that this will be used, idk yet?)
    cloudCover = clouds['all']

    # t for thunderstorm, r for rain, s for snow, c for cloud cover, w for wind
    wx = {
            "t" :[0,0],
            "r" :[0,0],
            "s" :[0,0],
            "c" :[0,0],
            "w" :windData
            }
   
    # We know the number of weather conditions by "numConditions"
    # Iterate through conditions, populating weather array
    for condition in range(numConditions):
        desc = str(weather[condition]["description"])

        if 'thunderstorm' in desc:
            wx['t'][0] = 100
            if 'light' in desc: wx['t'][1] = max( wx['r'][1], 20 )
            elif 'heavy' in desc: wx['t'][1] = max( wx['r'][1], 60 )
            else: wx['r'][1] = max( wx['t'][1], 40 )
        if 'shower' in desc:
            wx['r'][0] = 75
            if 'light' in desc: wx['r'][1] = max( wx['r'][1], 20 )
            elif 'heavy' in desc: wx['r'][1] = max( wx['r'][1], 60 )
            else: wx['r'][1] = max( wx['r'][1], 40 )
        if 'rain' in desc:
            wx['r'][0] = 50
            if 'light' in desc: wx['r'][1] = max( wx['r'][1], 20 )
            elif 'very heavy' in desc: wx['r'][1] = max( wx['r'][1], 80 )
            elif 'heavy' in desc: wx['r'][1] = max( wx['r'][1], 60 )
            elif 'extreme' in desc: wx['r'][1] = max( wx['r'][1], 100 )
            else: wx['r'][1] = max( wx['r'][1], 40 )
        if 'drizzle' in desc:
            wx['r'][0] = 25
            if 'light' in desc: wx['r'][1] = max( wx['r'][1], 20 )
            elif 'heavy' in desc: wx['r'][1] = max( wx['r'][1], 60 )
            else: wx['r'][1] = max( wx['r'][1], 40 )
        if 'snow' in desc:
            wx['s'][0] = 100
            if 'light' in desc: wx['r'][1] = max( wx['r'][1], 20 )
            elif 'heavy' in desc: wx['r'][1] = max( wx['r'][1], 60 )
            else: wx['r'][1] = max( wx['r'][1], 40 )
        
        # Don't want all the pixels turning turning off
        #   set to fractional limit, i.e. 100% cloud cover / 10 = up to 10% of pixels off
        #   not even sure I want this feature
        wx['c'] = cloudCover/10 

    return wx

def get_event(date = None):
    # Events and effects:
    #   Christmas/December colors r,g,b,w
    #   October colors orange, purple, mayyybbbeee green
    #   November colors, orange, white, yellow

    #   Pride month: rainbow cycling
    #   Fourth of July: Red, White, and Blue, static
    #   Election day: election results api, hue from red to blue dependent
    #       Periodically cycles to random chaotic flashing.
    #       Likely needs to persist for a week or two because fucking Nevada
    #
    print("Get event")

def set_pattern( event ):
    # setting pattern based on event
    print("Set pattern")


# Begin crude code
if __name__ == "__main__":


    # Only do this once at beginning of code
    loc = get_location()
    
    # Grab sunset information
    # If current time is before sunset, lights are off, otherwise on
    
    now = get_timenow(loc)
    sunset = get_sunset(loc)
    
    PIN = board.D18
    NUM_PIXELS=200
    ORDER = neopixel.RGB
    
    max_bright = 255
    
    color1 = (0, 0, 0)
    color2 = (max_bright, max_bright, max_bright)
    red = (max_bright, 0, 0)
    green = (0, max_bright, 0)
    blue = (0, 0, max_bright)
    
    orange = (255, 20, 0)
    yellow = (255, 90, 0)
    purple = (255, 0, 100)
    
    pixels = neopixel.NeoPixel( PIN, NUM_PIXELS, auto_write = False, pixel_order = ORDER)
    
    iterator = 0
    num_rainbows = 4#3
    skip = 100
    pattern = None
    
    for i in range(skip):
        pixels[i] = (0,0,0)
    
    oldTimeCheck = time.time()#datetime.datetime.now()
    timeCheckInterval = 3
    
    oldWxCheck = time.time()
    wx = get_weather(loc)
    wxCheckInterval = 86400/1000 # Get 1000 requests per day for free
    
    nextFlash = time.time()
    
    #patternType = "static"#"rolling"
    patternType = "rolling"
    uniqueColors = [orange,orange,purple]#,blue]
    numUniqueColors = len(uniqueColors)
    updateDelay = 1#0.2
    
    while True:
        # Only ocassionally update current time and sunset time...
        #if time.time() > oldTimeCheck + timeCheckInterval:
        #    print("Time is being updated")
        #    oldTimeCheck = time.time()
        #    now = get_timenow(loc)
        #    if datetime.datetime.now().date() > sunset.date():
        #        sunset = get_sunset(loc)
    
        if time.time() > oldWxCheck + wxCheckInterval:
            print("Updating weather data")
            wx = get_weather(loc)
            oldWxCheck = time.time()
    
       
        if( sunset.date() < get_timenow(loc).date() or pattern is None):
            print("Moved onto new day, recalculating sunset time")
            sunset = get_sunset(loc)
            #print("Also recalculating what event it is")
            #event = get_event()
            
            print("Also recalculating pattern")
    
            # Set pattern
            pattern = [(0,0,0)]*NUM_PIXELS
    
            event = 'october'
            #event = 'pride'#'october'
            if event == 'october':
                for i in range(int(skip/numUniqueColors), int(NUM_PIXELS/numUniqueColors)):
                    for j, color in enumerate(uniqueColors):
                        pixels[i*numUniqueColors+j] = color
                    updateDelay = 1
            if event == "pride":
                for i in range(skip,NUM_PIXELS):
                    val = (i+iterator)/(NUM_PIXELS/num_rainbows)# + iterator/(NUM_PIXELS)
                    while(val > 1.0):
                        val -= 1.0
                    (r, g, b) = colorsys.hsv_to_rgb( val , 1.0, 1.0)
                    if r>=1.0: r = 1
                    if g>=1.0: g = 1
                    if b>=1.0: b = 1
                    pixels[i] = int(255*r), int(255*g), int(255*b)
                updateDelay = 0.05
        #if event == 'october':
        #if event == 'halloween':
        #if event == 'november':
        #if event == 'december':
        #if event == 'christmas':
        #if event == 
        
        #whiteMask = [(0,0,0)]*NUM_PIXELS
    
        wx['t'][0] = 0# 1
        wx['t'][1] = 0# 1
    
        # Checking over weather conditions to define style
        if wx['t'][0] > 0 and time.time() > nextFlash:
            # This means thunderstorm is occurring
            #   Check intensity and flash accordingly
            intensity = wx['t'][1]
            # now define wait until next update of flashing
            flashDelay = int(random.random()*2 + 0.2)
            # size of flash, scale is max length, offset is minimum
            sizeOfFlash = int(random.random()*40 + 5)
            # starting index
            flashStart = int(random.random()*(NUM_PIXELS-skip)) + skip
    
            if flashStart + sizeOfFlash > NUM_PIXELS:
                sizeOfFlash = NUM_PIXELS - flashStart
    
            # Perform the flash quickly, save existing pixel vals
            currentPixels = pixels[:]
            
            for i in range(flashStart, flashStart+sizeOfFlash):
                pixels[i] = (255,255,255)
            pixels.show()
            time.sleep(0.05)
    
            for i in range(NUM_PIXELS):
                pixels[i] = currentPixels[i]
            
            nextFlash = time.time() + flashDelay
    
        # Static colors:
        if(patternType == 'flip'):
            for j in range(100):
                if i%2 == 0:
                    #pixels[2*j] = (255, 0, 0)
                    pixels[2*j] = (0, 0, 0)
                    pixels[2*j+1] = (max_bright,max_bright,max_bright)
                else:
                    pixels[2*j+1] = (0, 0, 0)
                    #pixels[2*j+1] = (255, 0, 0)
                    pixels[2*j] = (max_bright, max_bright, max_bright)
        elif(patternType == 'rolling'):
            # This will simply roll by one value everytime
            currentPixels = pixels[:]
            currentPixels = currentPixels[skip:]
    
            currentPixels = np.roll(currentPixels,3)
            for i in range(skip,NUM_PIXELS):
                pixels[i] = currentPixels[i-skip]
        
        # Final check to see if before sunset
        #   if before sunset, calculate wait until sunset and wait
        #   if after sunset, wait until date rolls over.
        if( sunset > get_timenow(loc) ) :
            print("Beginning the long wait. Number of seconds until sunset: ", (sunset - get_timenow(loc)).seconds)
            # Turning off pixels
            for i in range(NUM_PIXELS):
                pixels[i] = (0,0,0)
            pixels.show()
            # Now beginning the long wait
            updateDelay = (sunset - get_timenow(loc)).seconds
    
        pixels.show()
        sys.stdout.flush()
        time.sleep(updateDelay)#0.05)
        iterator+=1
        if iterator > NUM_PIXELS: iterator = 0

