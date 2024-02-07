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
import math
import sdnotify


# Some notes to myself about the features of this shoddily written program...

# Started as a way to put some neat WS2811 LEDs on the house....
#   ultimately, kept getting hacked and changed way too quickly to get to other more urgent projects

# Soooo, bits and pieces of this code essentially do several main things:
#   1) Accesses the internet for IP based geolocation, date, sunrise/sunset, and weather data.
#       *) Sunrise/Sunset makes sense for saving power on lights.
#       *) Weather data was supposed to be neat effects like blowing wind, twinkling orange for fall, spurious flashes for thunderstorms
#           Lots of pieces are there, just haven't fully hashed out because S.O. and myself decided upon patterns we liked most
#       *) Date data was originally supposed to inform patterns such as the following:
#           October: purples and oranges, cycling about
#           Halloween day: Same as october but with random startling flashes for passerby's
#           November: Oranges and yellows and like falling leaves, gently fades/brightens LEDs 
#           December: Yellow, blue, red, greens
#           Feburary: Pinks and Reds
#           New Year: Randomized spurts outwards of specific colors (like fireworks)
#           4th of July: Red Whites and Blues
#           Diwali: All yellows (like candles) with flickering
#           Pride Month: Make house look like an RGB gaming computer, rainbow cycling.
#           
#   2) Longer term goal would be to build a cohesive pattern and cycling system that operates ontop of the patterns:
#       Weather: See above discussion
#       Rolling: LED pattern simply moves according to speed chosen
#       Twinkling: Randomized dimming/brightening of LEDs
#       Fading: LEDs dim and brighten all at once
#       Sinusoid: Rolling mask to the pattern (i.e. 
#
#   3) Final pipe dream was to build a function for mapping pixels on house to a cartesian pixel grid for
#       for moving things spatially consistently, framed the logic for this, just haven't pursued further.


# Ultimately a lot of this is still hardcoded but I am working on getting to this as time permits outside of 
#   job, home renos, and slowwwlllyyy building up a pet company (SimplyFloof) and an environmental instrumentation company (Environmentation)
# Planning to play around with this late winter/spring when thematic styles can be more fluid.

# Please reach out to me if you have questions or requests, always happy to hop back in when time permits


# Watchdog timer
notify = sdnotify.SystemdNotifier()

sunsetCheck = True

# In minutes
#   Can be used to account for mountains and whatnot
# i.e. if -50, means start up lights 50 minutes before sunset
sunsetShift = -51#-300

# UNAPPLIED
minsPastMidnight = 0
# UNAPPLIED
runUntilSunrise = False
    
timeCheckInterval = 3
watchDogInterval = 5
updateDelay = 1#1#0.2

# LED WS2811 configurations for Raspberry Pi
PIN = board.D18
NUM_PIXELS=500 #This number can be much greater than the number of pixels if you don't want to count
ORDER = neopixel.RGB
   
# Set upper limit to brightness
max_bright = 255
   
off = (0, 0, 0)
on = (max_bright, max_bright, max_bright)
red = (max_bright, 0, 0)
green = (0, max_bright, 0)
blue = (0, 0, max_bright)
#pink = (max_bright,int(20*max_bright/255),int(147*max_bright/255))
pink = (max_bright,int(20*max_bright/255),int(60*max_bright/255))
orange = (max_bright, 20, 0)
yellow = (max_bright, int(90*max_bright/255), 0)
purple = (max_bright, 0, int(100*max_bright/255))
white = (max_bright, max_bright, max_bright)
cw = (max_bright, max_bright, max_bright)
#ww = (255,255,80)
ww = (max_bright, int(90*max_bright/255), 0)

# Assorted Variables
#iterator = 0
num_rainbows = 16# 4#3
skip = 0#100
pattern = None
patternType = "rolling"



# Personal API key python file config.py
#   of form api_key = "bleh"
import config
def get_ip():
    response = requests.get('https://api64.ipify.org?format=json').json()
    return response['ip']

def get_location():
    ip_address = get_ip()
    # response = requests.get(f'https://ipapi.co/{ip_address}/json/').json()
    response = requests.get(f'https://api.ipapi.is/?q={ip_address}').json()
    return response.get('location')

def get_sunset(loc):
    city = astral.LocationInfo(loc.get("city"),loc.get("region"),loc.get("timezone"),loc.get("latitude"), loc.get("longitude"))
    sunset = sun(city.observer, date=datetime.date.today(), tzinfo=loc.get("timezone"))["sunset"]
    
    sunset = sunset + datetime.timedelta(minutes = sunsetShift )

    return sunset

def get_timenow(loc):
    return datetime.datetime.now(pytz.timezone(loc.get('timezone')))
    # return datetime.datetime.now(pytz.timezone(loc.get('location').get('timezone')))

def get_weather(loc):
    lat = loc.get("latitude")
    lon = loc.get("longitude")
    # lat = loc.get("location").get("latitude")
    # lon = loc.get("location").get("longitude")
    url = "https://api.openweathermap.org/data/2.5/weather?lat=%s&lon=%s&appid=%s&units=metric" % (lat, lon, config.api_key)
   
    try:
        response = requests.get(url)
        data = json.loads(response.text)
    except:
        return None, None

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

    return wx, desc

def get_event(date = None):
    date = str(date).split('-')
    year = int(date[0])
    month = int(date[1])
    day = int(date[2])
    
    if month == 10:
        if day == 31:
            event = 'halloween'
        else:
            event = 'october'
    elif month == 11:
        if day == 11:
            event = 'veterans' #colors two blues and red in between
        else:
            event = 'november'
    elif month == 12:
        if day == 24:
            event = 'december' #'christmaseve'
        elif day == 25:
            event = 'december' #'christmas'
        else:
            event = 'december'
    elif month == 1:
        if day == 1:
            event = 'newyear'
    elif month == 2:
        event = 'february'
        # if day == 14:
        #    event = 'valentines'
        #else:
        #    event = 'february'
    elif month == 3:
        if day == 17:
            event = 'stpatricksday'
    elif month == 5:
        if day == 5:
            event = 'cincodemayo'
    elif month == 6:
        if day == 19:
            event = 'juneteenth'
        else:
            event = 'pridemonth'
    elif month == 7:
        if day == 4:
            event = 'independenceday'


    # Need to figure out how to program
    #   diwali (darkest day of November?
    #   memorial day last monday of may (do all red)
    #   labor day (floating monday sep 1-7, red/white/blue)
    
    return event

def set_pattern( pixels, event ):
    # setting pattern based on event
    numFade == 0
    
    if event == 'december':
        uniqueColors = [blue, red, green, ww]#, white]#white]#, green]#,blue]

    if event == "february":
        uniqueColors = [pink]

    for i in range(math.floor(skip/numUniqueColors), math.ceil(NUM_PIXELS/numUniqueColors)):
        for j, color in enumerate(uniqueColors):
            if (i*numUniqueColors + j) < NUM_PIXELS:
                pixels[i*numUniqueColors+j] = color
        updateDelay = 2#1#1.5
        #if numFade != 0:
        #    updateDelay = updateDelay / (2*numFade)
    if event == "pride":
        for i in range(skip,NUM_PIXELS):
            val = i/(NUM_PIXELS/num_rainbows)
            while(val > 1.0):
                val -= 1.0
            (r, g, b) = colorsys.hsv_to_rgb( val , 1.0, 1.0)
            if r>=1.0: r = 1
            if g>=1.0: g = 1
            if b>=1.0: b = 1
            pixels[i] = int(255*r), int(255*g), int(255*b)
        updateDelay = 0.01#5


    print("Pattern is set")

    return pixels, updateDelay 


# Currently unimplemented
def cartesianBuild( ):
    # need to come up with scheme for house orientation.
    #   For example, my house has LEDs of the form:
    #
    #                                   ->
    #                                 ->  ->
    #                               ->      ->
    #                             ->          ->
    #                           ->      <-      ->
    #                ->->-> V ->      <-  <-    # ->
    #             ->          |     <-      <- ##  |
    #           ->            |     |        |     |    
    #         ->              |     |        |     |
    #       ->             ____________________________     
    #     ->               | ======================== |
    #   ->                 | ======================== |
    # -> ######### <-<-<-<-^ ======================== |
    # |            | _____ ^ ======================== |
    # |            | |   | <-<-<-<-<-<-<-<-<-<-<-<-<-<-
    # |            | |   | |                          |                         
    # |            | |   | |                          |
    # |            | _____ |                          |
    # |            |_______|                          |
    # |                    |                          | 
    # |                    |                          |
    #
    #
    #   Note the direction of arrows, left right is obvious,
    #   down arrow is towards the front, carrot is into house
    #   hash tags are led strips connected by general wiring
    #   equal signs are roofing shingles over garage leading 
    #   up to next level

    #   Premise of LEDs, each LED needs to know it's directionality
    #   and position so that everything can be cycled correctly.

    #   So let's break LED's into segments as a list in cartesian space
    #   starting at the first LED in the strip (seeing as data is daisy chained)

    #   In my case, the lowest right pixel is the starting pixel.
    #       So 30 ft, 90 pixels, moving to the left
    #       Then 5 ft, 15 pixels towards the house
    #       Then 8 ft, 24 pixels over top of front door, moving left
    #           dark wire running to the furthest left pixel
    #       Then 21 ft, 63 pixels moving from left to right
    #       Then 10 ft, 30 pixels moving away from house
    #       Then 30 ft, 60 pixels moving up and over topmost peak towards right
    #           dark wire running from topmost peak on right to recessed peak
    #       Then 16 ft, 48 pixels moving from righ to left
    #           End of sequence

    #       45 degree steep peaks move sqrt(2) slower than horizontal LEDs
    #       Program in speed adustment

    #       Need to map everything to "pixel" cartesian space

    #       In other words, leds across front of garage are 30 ft,
    #           but this is -90 pixels towards the left, and the topmost 
    #           peak of house does not fully extend to the 90th pixel 
    #           nor the 0th pixel of the garage line

    #       Therefore, we could say, the topmost peak runs from pixel
    #           -70 to -45, at +45 degrees, and -45 to -20 at -45 deg
    
    #       Similarly, we could say into or out of the house are at
    #           -90 or +90 degrees.

    #       So to build this, we could do two arrays at total length of pixels,
    #           one to denote angle
    

    # So first strip is 90 pixels, 180 deg, starts at pos 0
    #   second strip is 15 pixels, 90 deg, starts at pos -90
    #   third strip is  30 pixels, 180 deg, starts at pos -90
    #   fourth strip is 90 pixels, 45 deg, ends at pos -90
    #   fifth strip is 30 pixels, -90 deg, ends at pos -90
    #   sixth strip is 50 pixels, 45 deg, starts at pos -70
    #   seventh strip is 50 pixels, -45 deg, starts at pos -45
    #   eigth strip is 25 pixels, 135 deg, starts at pos -30
    #   ningth strip is 25 pixels, -135 deg, starts at pos -45

    # break this into strips.....
    #   Each row is a new strip, with columns
    #       [#LEDs, angle, strt_x, end_x, start_y, end_y ]
    ##   Noting that start and end are in LED counts
    # ANGLE is ALWAYS referenced to start pixel in strip

    strips = [ 
            [ 90,  180,    0,  -90, None, None ],
            [ 15,   90,  -90, None, None, None ],
            [ 30,  180,  -90, None, None, None ],
            [ 90,   45, None,  -90, None, None ],
            ]

    # Once I have all my strips loaded, need to fill in None values
    #   by calculating the end start or end positions based on angles

    for i, strip in enumerate(strips):
        if strip[2] == None:
            # This means start position needs to be calculated
            strips[i][2] = strip[3] - np.cos(strip[1]) * strip[0]
        if strip[3] == None:
            strips[i][3] = strip[2] + np.cos(strip[1]) * strip[0]

        if strip[4] == None and strip[5] == None:
            # This means we don't care about vertical positions
            strips[i][4] = 0
            strips[i][5] = 0
        if strip[4] == None:
            strips[i][4] = strip[5] - np.sin(strip[1]) * strip[0]
        if strip[5] == None:
            strips[i][5] = strip[4] + np.sin(strip[1]) * strip[0]

    #   Next, figure out arrange according to patterns
    #
    #   For example, rainbow I will want an option to have everything going
    #       smoothly from left to right.
    #
    #   To do this, I will need to put everything into a pixel matrix

    pixelGrid = []
    for strip in strips:
        #For each strip, we start at start pos, (which in my case is 0,0)
        #   and interpolate across, start_x/y, to end_x/y

        # There ***should*** not be segments that are not straight lines
        #   if there are, this is edge case, not programming it for now =(
        for i in range(strip[0]):
            pixelGrid.append( [ strip[2] + i*strip[3]/strip[0],
                strip[4] + i*strip[5]/strip[0] ] )
        # I should now have full cartesian grid of pixels

    # Now let's sort them based on x position:
    pixelGrid = np.array(pixelGrid)

    # First create a evenly distributed grid from max to min
    
    # Some pattern examples,
    #   Maybe I want lights to radiate away/towards peaks
    #       I would need to define radiation point (pick the highest peak?)
    #       if no Y data, should calculate center x value

    #if( max(pixelGrid(1,:]) != min(pixelGrid(1,:])) ):
    #if( max(pixelGrid[1,:]) == min(pixelGrid(1,:])) ):
        # This means no y data present

    # Check max of y data, if equal to min of y data, use min_x + (max_x - min_x)/2
    #   if does have y data from last check, find x value at highest point

    # Another pattern example:
    #   Everything moves in the same direction


if __name__ == "__main__":
    # This line is for kicking off the system daemon
    notify.notify("READY=1")


    # Only do this once at beginning of code
    loc = get_location()
   
    # Grab sunset information
    # If current time is before sunset, lights are off, otherwise on 
    now = get_timenow(loc)
    sunset = get_sunset(loc)
    
    # Initialize pixel system
    pixels = neopixel.NeoPixel( PIN, NUM_PIXELS, auto_write = False, pixel_order = ORDER)
   
    # Initialize Pixels to OFF
    for i in range(skip):
        pixels[i] = off
    
    oldTimeCheck = time.time()#datetime.datetime.now()
    
    oldWxCheck = time.time()
    wx, wxdesc = get_weather(loc)
    
    print("Weather is ", wxdesc)
    wxCheckInterval = 86400/1000 # Get 1000 requests per day for free
    
    nextFlash = time.time()
    
    #patternType = "static"#"rolling"
    uniqueColors = [blue, red, green, ww]#, white]#white]#, green]#,blue]
    numUniqueColors = len(uniqueColors)

    notify.notify("WATCHDOG=1")
    notify.notify("STATUS=Watchdog kicked at {}".format(get_timenow(loc)))
    oldWatchDogCheck = time.time()

    # Main loop
    while True:
        if time.time() > oldWxCheck + wxCheckInterval:
            print("Updating weather data")
            tmp_wx, tmp_wxdesc = get_weather(loc)
            oldWxCheck = time.time()
            if wxdesc != None:
                wx = tmp_wx
                wxdesc = tmp_wxdesc
            print("Weather is ", wxdesc)
   
        if time.time() > oldWatchDogCheck + watchDogInterval:
            notify.notify("WATCHDOG=1")
            notify.notify("STATUS=Watchdog kicked at {}".format(get_timenow(loc)))
            oldWatchDogCheck = time.time()
       
        if( sunset.date() < get_timenow(loc).date() or pattern is None):
            print("Moved onto new day, recalculating sunset time")
            sunset = get_sunset(loc)
            
            # Set pattern
            pattern = [(0,0,0)]*NUM_PIXELS

           # If numFade = 0, hard changes, otherwise add blending
            numFade = 0#5

            newColorsWithFade = []
            if numFade != 0:
                for i in range(numUniqueColors):#-1):
                    if uniqueColors[i] == uniqueColors[i-1]:
                        newColorsWithFade.append(uniqueColors[i-1])
                    else:
                        colorStep = tuple(int(color/numFade) for color in uniqueColors[i-1])
                        for j in range(numFade):
                            newColorsWithFade.append(
                                tuple(max(0,int(color - j*step)) for color,step in zip(uniqueColors[i-1],colorStep)))
                        newColorsWithFade.append((0,0,0))
                        colorStep = tuple(int(color/numFade) for color in uniqueColors[i])
                        for j in range(numFade,0,-1):
                            newColorsWithFade.append(
                                tuple(max(0,int(color - j*step)) for color,step in zip(uniqueColors[i],colorStep)))
                uniqueColors = newColorsWithFade
                numUniqueColors = len(uniqueColors)

            #### GET PATTERN HERE #####
    
            event = get_event(datetime.date.today())
            pixels, updateDelay = set_pattern( pixels, event )

            print("Pattern set to ",event)
   
        # Can use the following to manually force weather effect
        #wx['t'][0] =  0#1
        #wx['t'][1] =  0#1
   
        # Check duration of wait time to figure out how many twinkles
        twinkling = False
        if twinkling:
            twinkleInterval = 0.05
            twinkleIntensity = 1.3

            for j in range(int(int(updateDelay/twinkleInterval)/2)):
                currentPixels = pixels[:]
                for i in range(0,NUM_PIXELS):
                    #pixels[i] = int(pixels[i]/1.1)
                    r,g,b = pixels[i]
                    pixels[i] = (int(r/twinkleIntensity),int(g/twinkleIntensity),int(b/twinkleIntensity))
                pixels.show()
            
                time.sleep(twinkleInterval)

                for i in range(0,NUM_PIXELS):
                    pixels[i] = currentPixels[i]
                pixels.show()
                time.sleep(twinkleInterval)

        slowTwinkle = False
        if slowTwinkle:
            twinkleFadeSteps = 30
            twinkleDivision = 1.08
            twinklesPerInterval = 1
            twinkleInterval = updateDelay/(twinkleFadeSteps*2)

            # Find out what the new values need to be to make them integer arithmetic compatible
            for j in range(twinklesPerInterval):
                currentPixels = pixels[:]

                for k in range(1,twinkleFadeSteps+1):
                    for i in range(0,NUM_PIXELS):
                        #pixels[i] = int(pixels[i]/1.1)
                        r,g,b = currentPixels[i]
                        pixels[i] = (int(r/(twinkleDivision**k)),int(g/(twinkleDivision**k)),int(b/(twinkleDivision**k)))
                    pixels.show()
            
                    time.sleep(twinkleInterval)

                for k in range(twinkleFadeSteps,0,-1):
                    for i in range(0,NUM_PIXELS):
                        #pixels[i] = int(pixels[i]/1.1)
                        r,g,b = currentPixels[i]
                        pixels[i] = (int(r/(twinkleDivision**k)),int(g/(twinkleDivision**k)),int(b/(twinkleDivision**k)))
                    pixels.show()

                    time.sleep(twinkleInterval)

                for i in range(0,NUM_PIXELS):
                    pixels[i] = currentPixels[i]
                pixels.show()
                time.sleep(twinkleInterval)

        # Sinusoidal fade mask:
        sinusoidSweep = True
        if sinusoidSweep:
            period = 40 # number of pixels for sinunsoid to repeat
            speed = 2 # Time between peak to fade and unfade back to peak intensity
            fadeMin = 0.1 # value between 0 and 1 that dicates dimmest that it will go (1 is no dimming)

            # Goofy way of doing this but attempt roll of fade first, otherwise we know it hasn't been established
            try:
                fadeMask = np.roll(fadeMask,1)
            except:
                # Define fade mask, i.e., the percentage to scale original values by
                # Start with 0 to 1
                fadeMask = np.zeros(NUM_PIXELS)
                for i,fade in enumerate(fadeMask):
                    fadeMask[i] = 0.5 + 0.5*np.sin(2*np.pi*i/period)

                # Now scale according to fademin 
                fadeMask = fadeMask * (1 - fadeMin) + fadeMin
                currentPixels = pixels[:]

            # Roll on the fademask is going to be dependent on delay and speed
            for i,fade in enumerate(fadeMask):
                #print(i,fade)
                r,g,b = currentPixels[i]
                pixels[i] = (int(r*fade),int(g*fade),int(b*fade))
           
            # Sleep will dictate how fast this feature moves
            # If period is, say, 10 pixels, and speed is 5 seconds, we need to roll fades at speed/period
            updateDelay = speed/period


        # Checking over weather conditions to define style
        #if wx['t'][0] > 0 and time.time() > nextFlash:
        
        # FLASHING should be handled during the delays, need to move down to the bottom at some point
        if 1==0 and time.time() > nextFlash:
            # This means thunderstorm is occurring
            #   Check intensity and flash accordingly
            intensity = wx['t'][1]
            # now define wait until next update of flashing
            flashDelay = int(random.random()*1.2 + 0.1)
            # size of flash, scale is max length, offset is minimum
            sizeOfFlash = int(random.random()*70 + 30)
            # starting index
            flashStart = int(random.random()*(NUM_PIXELS-skip)) + skip
    
            if flashStart + sizeOfFlash > NUM_PIXELS:
                sizeOfFlash = NUM_PIXELS - flashStart
    
            # Perform the flash quickly, save existing pixel vals
            currentPixels = pixels[:]
            
            for i in range(flashStart, flashStart+sizeOfFlash):
                pixels[i] = on#(255,255,255)
            pixels.show()
            time.sleep(0.05)
    
            for i in range(NUM_PIXELS):
                pixels[i] = currentPixels[i]
            
            nextFlash = time.time() + flashDelay
    
   
        static=True
        if not static:
            # This will simply roll by one value everytime
            currentPixels = pixels[:]
            currentPixels = currentPixels[skip:]
            currentPixels = np.roll(currentPixels,3)
            for i in range(skip,NUM_PIXELS):
                pixels[i] = currentPixels[i-skip]
        
        # Final check to see if before sunset
        #   if before sunset, calculate wait until sunset and wait
        #   if after sunset, wait until date rolls over.
        if( sunsetCheck and sunset > get_timenow(loc) ) :
            secondsUntilSunset = (sunset - get_timenow(loc)).seconds
            print("Beginning wait. Number of seconds until sunset: ", (sunset - get_timenow(loc)).seconds)
            # Turning off pixels
            for i in range(NUM_PIXELS):
                pixels[i] = (0,0,0)
            updateDelay = 5
            
            if ( secondsUntilSunset < 30 ):#sunset < get_timenow(loc) ):
                # Set pattern to None to encourage recheck of pattern
                pattern = None

        pixels.show()
        sys.stdout.flush()
        
        # If twinkling, remove updateDelay
        if not twinkling and not slowTwinkle:
            time.sleep(updateDelay)#0.05)
