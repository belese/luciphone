import RPi.GPIO as GPIO
from modules.xbmcjson import XBMC
import subprocess
from modules.py532lib.NFC import NFC as NFC
from datetime import datetime
import time
import os
import os.path
import urllib.request
import threading

# set max volume
# admin tag : enable usb,start samba??
# check internet connection on

# config
VOLUMEMAX = 65
DEFAULTVOLUME = 55

# path and file name
PATH = "/home/xbian/Mediatheque"
MUSIQUE_PATH = "Musique"
VIDEO_PATH = "Video"
UID_FILE = ".UID"

# Preferred Player Name
VIDEOPLAYER = "[TV]Samsung LED32"
AUDIOPLAYER = "PAPlayer"

# Special Tag
ADMIN_TAG = "blabla"

# pushbutton connected to this GPIO pin
NEXTPIN = 27
PREVIOUSPIN = 22
AMPOFFPIN = 11

# Timeout button pressed before 2nd button function in seconds
VOLUMETO = 2

MPATH = os.path.join(PATH, MUSIQUE_PATH)
VPATH = os.path.join(PATH, VIDEO_PATH)


# TEXT
PRET = "/home/xbian/Luciphone/Voice/pret.wav"
NETWORKON = "/home/xbian/Luciphone/Voice/networkon.wav"
WIFIOFF = "/home/xbian/Luciphone/Voice/wifioff"


# helper battery saver
class power_management:
    def __init__(self):        
        self.alwaysUsb = os.path.isfile('/boot/luciphone.debug')
        self.neverUsb = False
        self.usbEnable = True
        self.disableusb()  # disable usb/wifi at start todo do it earlier in boot process
        self.ampEnable = False
        self.t = None
        self.sleeping = False
        self.sleepstate = {'usb': self.usbEnable, 'amp': self.ampEnable}

    def permanentUsb(self, state):
        print('Permanent usb change : ', state)
        if state == None:
            self.alwaysUsb = False
            self.neverUsb = False
        elif state:
            self.alwaysUsb = True
            self.neverUsb = False
            self.enableusb()
        else:
            self.alwaysUsb = False
            self.neverUsb = True
            self.disableusb()

    def sleep(self):
        if self.t or self.sleeping:
            return
        self.t = threading.Timer(10.0, self._sleep)
        self.t.start()
        print ('Sleep mode start in 30.0')

    def _sleep(self):
        self.t = None
        self.sleepstate = {'usb': self.usbEnable, 'amp': self.ampEnable}
        if self.usbEnable:
            self.disableusb()
        if self.ampEnable:
            self.disableAmp()
        print ('Sleeping')
        self.sleeping = True

    def wake(self):
        if self.t:
            print ('cancel sleep mode')
            self.t.cancel()
            self.t = None
        if not self.sleeping:
            return
        print ('Waking Up')
        if self.sleepstate['usb']:
            self.enableusb()
        if self.sleepstate['amp']:
            self.enableAmp()
        self.sleeping = False

    def enableAmp(self):
        if self.ampEnable:
            return
        GPIO.output(AMPOFFPIN, 1)
        self.ampEnable = True

    def disableAmp(self):
        if not self.ampEnable:
            return
        GPIO.output(AMPOFFPIN, 0)
        self.ampEnable = False

    def disableusb(self):
        if not self.usbEnable or self.alwaysUsb:
            return
        with open('/sys/devices/platform/soc/20980000.usb/buspower', 'wb') as a:
            subprocess.check_call(["echo",'0'],stdout=a)
            pass
        print ("Usb disable")
        self.usbEnable = False

    def enableusb(self):
        if self.usbEnable or self.neverUsb:
            return
        with open('/sys/devices/platform/soc/20980000.usb/buspower', 'wb') as a:
            subprocess.check_call(["echo",'1'],stdout=a)
            pass
        self.usbEnable = True

        if self.waitForNetwork():
            # wait for a network connection
            print("we have a internet connection")
            print ("USB enabled")
        else:
            # no internet connection
            print("No internet conncection")
            self.disableusb()
        return self.usbEnable

    def hasHdmiConnected(self):
        a = subprocess.Popen(["./tvstatus.sh"], stdout=subprocess.PIPE)
        status = a.stdout.read()[:-1]
        if status in (b'on', b'standby'):
            # hdmi cable plug
            return True
        else:
            return False

    def waitForNetwork(self, timeout=12):
        starttime = time.time()
        while starttime > time.time() - timeout:
            print ("Waiting for network ...")
            try:
                urllib.request.urlopen("http://192.168.1.1")
                return True
            except urllib.error.URLError as e:
                pass
        return False


class player:
    AUDIO = 1
    VIDEO = 2
    ANALOG = "PI:Analogue"
    HDMI = "PI:HDMI"

    def __init__(self):
        # Login with default xbmc/xbmc credentials
        self.xbmc = XBMC("http://127.0.0.1:8080/jsonrpc")
        # set defaut volume
        self.xbmc.Application.SetVolume({"volume": DEFAULTVOLUME})
        self.currentUid = None
        self.Mindex = self.scanDirs(MPATH)
        self.Vindex = self.scanDirs(VPATH)
        self.playerid = 0
        self.paused = True  # keep paused status, as i can't retrieve for dlna player
        self.pwm = power_management()
        self.talk(PRET)
        self.pwm.sleep()
        self.usboncpt = 0
        self.usboffcpt = 0
        self.lastclick = time.time()

    def talk(self, wavfile):
        self.pwm.enableAmp()
        subprocess.check_call(["/usr/bin/aplay", wavfile])
        self.pwm.disableAmp()

    def setAudioOutput(self, playercoreid):
        if playercoreid > 3 or self.pwm.hasHdmiConnected():
            output = self.HDMI
            self.pwm.disableAmp()
        else:
            output = self.ANALOG
            self.pwm.enableAmp()

        self.xbmc.Settings.SetSettingValue(
            {"setting": "audiooutput.audiodevice", "value": output})

    def getPlayerID(self, mediatype):
        defaultplayer = 1
        if mediatype == self.AUDIO:
            playerwanted = AUDIOPLAYER
        else:
            playerwanted = VIDEOPLAYER
            # if video and hdmi connected, force use of dvdplayer
            if self.pwm.hasHdmiConnected():
                return defaultplayer

        for player in self.xbmc.Player.GetPlayers()['result']:
            if playerwanted == player['name']:
                return player['playercoreid']

        print('Looking for newtork Renderer')
        # we don't find player, enable wifi to try find it
        self.xbmc.Settings.SetSettingValue(
            {"setting": "services.upnpserver", "value": False})
        if self.pwm.enableusb():
            self.xbmc.Settings.SetSettingValue(
                {"setting": "services.upnpserver", "value": True})
            time.sleep(2)
            for player in self.xbmc.Player.GetPlayers()['result']:
                print(player)
                if playerwanted == player['name']:
                    return player['playercoreid']
            if playerwanted == VIDEOPLAYER :
                for player in self.xbmc.Player.GetPlayers()['result']:
                    if player['playercoreid'] > 3 and player['playsvideo'] :
                        return player['playercoreid']
            self.pwm.disableusb()

        # we don't find player, even with wifi, return default player
        return defaultplayer

    def play(self, uid):
        print ("Start Player with uid ", uid)
        mediatype = None
        path = None
        self.usboncpt = 0
        self.usboffcpt = 0

        if str(uid) in self.Mindex:
            mediatype = self.AUDIO
            path = self.Mindex[str(uid)]
        elif str(uid) in self.Vindex:
            mediatype = self.VIDEO
            path = self.Vindex[str(uid)]
        else:
            print ('Unknwow Tag UID')
            return False

        # get player id and select audio output
        self.pwm.wake()
        playercoreid = self.getPlayerID(mediatype)
        self.setAudioOutput(playercoreid)

        if self.currentUid != uid or not self.isPaused() or playercoreid != self.playerid:
            # new disk on player detected
            self.currentUid = uid
            self.playerid = playercoreid
            self.ScreenSaverOff()
            self.xbmc.Input.ExecuteAction({"action": "stop"})
            print(self.xbmc.Player.Open(
                {"item": {"directory": path}, "options": {"playercoreid": self.playerid}}))
            self.paused = False
        else:
            # same disk was put
            self.unpause()
        return True

    def unpause(self):
        if self.isPaused():
            self.ScreenSaverOff()
            self.xbmc.Input.ExecuteAction({"action": "play"})
            self.paused = False

    def pause(self):
        if not self.isPaused():
            self.ScreenSaverOff()
            self.xbmc.Input.ExecuteAction({"action": "pause"})
            self.paused = True
            self.pwm.sleep()

    def next(self):
        self.ScreenSaverOff()
        if not self.isPaused():
            self.xbmc.Input.ExecuteAction({"action": "skipnext"})
        else:
            if time.time() - self.lastclick > 5:
                self.lastclick = time.time()
                if self.usboncpt != 5:
                    self.usboncpt = 0
                if self.usboffcpt != 5:
                    self.usboffcpt = 0

            if self.usboncpt < 2:
                self.usboncpt += 1
            elif self.usboncpt == 2:
                self.usboncpt = 0
            if self.usboffcpt == 2:
                self.pwm.permanentUsb(False)
                self.usboffcpt = 5
                self.usboncpt = 0

    def previous(self):
        self.ScreenSaverOff()
        if not self.isPaused():
            self.xbmc.Input.ExecuteAction({"action": "skipprevious"})
        else:
            if time.time() - self.lastclick > 5:
                self.lastclick = time.time()
                if self.usboncpt != 5:
                    self.usboncpt = 0
                if self.usboffcpt != 5:
                    self.usboffcpt = 0

            if self.usboffcpt < 2:
                self.usboffcpt += 1
            elif self.usboffcpt == 2:
                self.usboffcpt = 0
            if self.usboncpt == 2:
                self.talk(NETWORKON)
                self.pwm.permanentUsb(True)
                self.usboncpt = 5
                self.usboffcpt = 0

    def volUp(self):
        self.ScreenSaverOff()
        if self.xbmc.Application.GetProperties({"properties": ["volume"]})['result']['volume'] < VOLUMEMAX:
            self.xbmc.Input.ExecuteAction({"action": "volumeup"})

    def volDown(self):
        self.ScreenSaverOff()
        self.xbmc.Input.ExecuteAction({"action": "volumedown"})

    def isPaused(self):
        player = self.xbmc.Player.GetActivePlayers()["result"]
        if player:
            try:
                self.paused = self.xbmc.Player.GetProperties(
                    {"playerid": player[-1]['playerid'], "properties": ["speed"]})["result"]["speed"] == 0
            except:
                pass

        return self.paused

    def ScreenSaverOff(self):
        # send noop command, otherwise if screensaver is activate,
        # first command is ignored
        self.xbmc.Input.ExecuteAction({"action": "noop"})

    def scanDirs(self, path):
        idx = {}
        # recursive all dirs from a root

        def listdirs(folder):
            return [d for d in (os.path.join(folder, d1) for d1 in os.listdir(folder)) if os.path.isdir(d)]

        for name in listdirs(path):
            if os.path.isfile(os.path.join(name, UID_FILE)):
                f = open(os.path.join(name, UID_FILE), 'r')
                uid = f.read()
                f.close
                if uid:
                    idx[uid] = name
                print ("find UID %s' in %s" % (uid, name))
        return idx


class luciphone:

    def __init__(self):
        NFC.add_event_detect(NFC.NEWTAG, self.onDiskDetected)
        NFC.add_event_detect(NFC.REMOVETAG, self.onDiskRemoved)

        self.player = player()
        self.stopped = False
        self.busy = False
        self.adminTag = False
        self.UID = None

    # callback function
    def onButtonStateChanged(self, pin):
        if GPIO.input(pin) or self.busy:
            return

        self.busy = True
        secondfn = False
        # button is down
        buttonPressedTime = datetime.now()
        print ('A Button is Down')
        time.sleep(0.1)
        while not GPIO.input(pin):
            if self.adminTag:
                break
            if (datetime.now() - buttonPressedTime).total_seconds() >= VOLUMETO:
                if pin == NEXTPIN:
                    print ("Volume up")
                    self.player.volUp()
                elif pin == PREVIOUSPIN:
                    print ("Volume Down")
                    self.player.volDown()
                else:
                    break
                secondfn = True
                time.sleep(0.1)

        print ('Button is UP')
        if not secondfn:
            if pin == NEXTPIN:
                print ("Next")
                if self.adminTag:
                    pass
                else:
                    self.player.next()
            elif pin == PREVIOUSPIN:
                print ("Previous")
                if self.adminTag:
                    pass
                else:
                    self.player.previous()
        self.busy = False

    def onDiskDetected(self, uid):
        print ("disc detected", uid)
        if uid == ADMIN_TAG:
            pass
        else:
            print ('play')
            if self.player.play(uid):
                self.currentUid = uid
            else:
                self.currentUid = None

    def onDiskRemoved(self, uid):
        print (uid)
        if uid == ADMIN_TAG:
            pass
        elif self.currentUid == uid:
            self.player.pause()
        else:
            print('Unknown remove uid')

    def start(self):
        try :
           NFC.start()
        except :
            NFC.start()         
        GPIO.cleanup()

# start here
# initialise GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(NEXTPIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(PREVIOUSPIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(AMPOFFPIN, GPIO.OUT)
GPIO.output(AMPOFFPIN, 0)
play = luciphone()
# subscribe to button presses and disk actions
GPIO.add_event_detect(NEXTPIN, GPIO.FALLING,
                      callback=play.onButtonStateChanged)
GPIO.add_event_detect(PREVIOUSPIN, GPIO.FALLING,
                      callback=play.onButtonStateChanged)

play.start()
