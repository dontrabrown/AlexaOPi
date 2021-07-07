#!/usr/bin/env python

import logging
import os
import time
#import RPi.GPIO as GPIO
from pyA20.gpio import gpio as GPIO
from pyA20.gpio import port
import pyaudio
import wave
from creds import *
import requests
import json
import re
from memcache import Client
import vlc
import threading
import email
import optparse
import sys
import snowboydecoder
import snowboydetect
import signal

import tunein

# record format
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 800
RECORD_SECONDS = 6
WAVE_OUTPUT_FILENAME = "recording.wav"
audio = pyaudio.PyAudio()

# Settings
plb_light = port.PA9		# GPIO Pin for the playback/activity light
rec_light = port.PA8		# GPIO Pin for the recording light
lights = [plb_light, rec_light]  # GPIO Pins with LED's connected
device = "plughw:0"  # Name of your microphone/sound card in arecord -L

# Get arguments
parser = optparse.OptionParser()
parser.add_option('-s', '--silent',
                  dest="silent",
                  action="store_true",
                  default=False,
                  help="start without saying hello"
                  )
parser.add_option('-d', '--debug',
                  dest="debug",
                  action="store_true",
                  default=False,
                  help="display debug messages"
                  )

cmdopts, cmdargs = parser.parse_args()
silent = cmdopts.silent
debug = cmdopts.debug
#debug = True

# Setup
recorded = False
servers = ["127.0.0.1:11211"]
mc = Client(servers, debug=1)
path = os.path.realpath(__file__).rstrip(os.path.basename(__file__))
interrupted = False

# Variables
p = ""
nav_token = ""
streamurl = ""
streamid = ""
position = 0
audioplaying = False
start = time.time()
tunein_parser = tunein.TuneIn(5000)
currVolume = 100

# constants
MAX_RECORDING_LENGTH = 6
MAX_VOLUME = 100
MIN_VOLUME = 30

#Snowboy setup
logging.basicConfig()
logger = logging.getLogger("snowboy")
logger.setLevel(logging.INFO)
TOP_DIR = os.path.dirname(os.path.abspath(__file__))
model = sys.argv[1]
RESOURCE_FILE = os.path.join(TOP_DIR, "resources/common.res")
DETECT_DING = os.path.join(TOP_DIR, "resources/r2beep.mp3")
DETECT_DONG = os.path.join(TOP_DIR, "resources/dong.wav")


# Function for snowboy

def interrupt_callback():
    global interrupted

    return interrupted



if len(sys.argv) == 1:
    print("Error: need to specify model name")
    print("Usage: python demo.py your.model")
    sys.exit(-1)


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def internet_on():
    print("Checking Internet Connection...")
    try:
        r = requests.get('https://api.amazon.com/auth/o2/token')
        print("Connection {}OK{}".format(bcolors.OKGREEN, bcolors.ENDC))
        return True
    except:
        print("Connection {}Failed{}".format(bcolors.WARNING, bcolors.ENDC))
        return False


def gettoken():
    token = mc.get("access_token")
    refresh = refresh_token
    if token:
        return token
    elif refresh:
        payload = {"client_id": Client_ID, "client_secret": Client_Secret, "refresh_token": refresh,
                   "grant_type": "refresh_token",}
        url = "https://api.amazon.com/auth/o2/token"
        r = requests.post(url, data=payload)
        resp = json.loads(r.text)
        mc.set("access_token", resp['access_token'], 3570)
        return resp['access_token']
    else:
        return False


def alexa_speech_recognizer():
    # https://developer.amazon.com/public/solutions/alexa/alexa-voice-service/rest/speechrecognizer-requests
    if debug: print("{}Sending Speech Request...{}".format(bcolors.OKBLUE, bcolors.ENDC))
    # GPIO.output(plb_light, GPIO.HIGH)
    url = 'https://access-alexa-na.amazon.com/v1/avs/speechrecognizer/recognize'
    headers = {'Authorization': 'Bearer %s' % gettoken()}
    d = {
        "messageHeader": {
            "deviceContext": [
                {
                    "name": "playbackState",
                    "namespace": "AudioPlayer",
                    "payload": {
                        "streamId": "",
                        "offsetInMilliseconds": "0",
                        "playerActivity": "IDLE"
                    }
                }
            ]
        },
        "messageBody": {
            "profile": "alexa-close-talk",
            "locale": "en-us",
            "format": "audio/L16; rate=16000; channels=1"
        }
    }
    with open(path + 'recording.wav') as inf:
        files = [
            ('file', ('request', json.dumps(d), 'application/json; charset=UTF-8')),
            ('file', ('audio', inf, 'audio/L16; rate=16000; channels=1'))
        ]
        r = requests.post(url, headers=headers, files=files)
    process_response(r)


def alexa_getnextitem(nav_token):
    # https://developer.amazon.com/public/solutions/alexa/alexa-voice-service/rest/audioplayer-getnextitem-request
    time.sleep(0.8)
    if audioplaying == False:
        if debug: print("{}Sending GetNextItem Request...{}".format(bcolors.OKBLUE, bcolors.ENDC))
        # GPIO.output(plb_light, GPIO.HIGH)
        url = 'https://access-alexa-na.amazon.com/v1/avs/audioplayer/getNextItem'
        headers = {'Authorization': 'Bearer %s' % gettoken(), 'content-type': 'application/json; charset=UTF-8'}
        d = {
            "messageHeader": {},
            "messageBody": {
                "navigationToken": nav_token
            }
        }
        r = requests.post(url, headers=headers, data=json.dumps(d))
        process_response(r)


def alexa_playback_progress_report_request(requestType, playerActivity, streamid):
    # https://developer.amazon.com/public/solutions/alexa/alexa-voice-service/rest/audioplayer-events-requests
    # streamId                  Specifies the identifier for the current stream.
    # offsetInMilliseconds      Specifies the current position in the track, in milliseconds.
    # playerActivity            IDLE, PAUSED, or PLAYING
    if debug: print("{}Sending Playback Progress Report Request...{}".format(bcolors.OKBLUE, bcolors.ENDC))
    headers = {'Authorization': 'Bearer %s' % gettoken()}
    d = {
        "messageHeader": {},
        "messageBody": {
            "playbackState": {
                "streamId": streamid,
                "offsetInMilliseconds": 0,
                "playerActivity": playerActivity.upper()
            }
        }
    }

    if requestType.upper() == "ERROR":
        # The Playback Error method sends a notification to AVS that the audio player has experienced an issue during playback.
        url = "https://access-alexa-na.amazon.com/v1/avs/audioplayer/playbackError"
    elif requestType.upper() == "FINISHED":
        # The Playback Finished method sends a notification to AVS that the audio player has completed playback.
        url = "https://access-alexa-na.amazon.com/v1/avs/audioplayer/playbackFinished"
    elif requestType.upper() == "IDLE":
        # The Playback Idle method sends a notification to AVS that the audio player has reached the end of the playlist.
        url = "https://access-alexa-na.amazon.com/v1/avs/audioplayer/playbackIdle"
    elif requestType.upper() == "INTERRUPTED":
        # The Playback Interrupted method sends a notification to AVS that the audio player has been interrupted.
        # Note: The audio player may have been interrupted by a previous stop Directive.
        url = "https://access-alexa-na.amazon.com/v1/avs/audioplayer/playbackInterrupted"
    elif requestType.upper() == "PROGRESS_REPORT":
        # The Playback Progress Report method sends a notification to AVS with the current state of the audio player.
        url = "https://access-alexa-na.amazon.com/v1/avs/audioplayer/playbackProgressReport"
    elif requestType.upper() == "STARTED":
        # The Playback Started method sends a notification to AVS that the audio player has started playing.
        url = "https://access-alexa-na.amazon.com/v1/avs/audioplayer/playbackStarted"

    r = requests.post(url, headers=headers, data=json.dumps(d))
    if r.status_code != 204:
        print("{}(alexa_playback_progress_report_request Response){} {}".format(bcolors.WARNING, bcolors.ENDC, r))
    else:
        if debug: print(
            "{}Playback Progress Report was {}Successful!{}".format(bcolors.OKBLUE, bcolors.OKGREEN, bcolors.ENDC))


def process_response(r):
    global nav_token, streamurl, streamid, currVolume, isMute
    if debug: print("{}Processing Request Response...{}".format(bcolors.OKBLUE, bcolors.ENDC))
    nav_token = ""
    streamurl = ""
    streamid = ""
    if r.status_code == 200:
        data = "Content-Type: " + r.headers['content-type'] + '\r\n\r\n' + r.content
        msg = email.message_from_string(data)
        for payload in msg.get_payload():
            if payload.get_content_type() == "application/json":
                j = json.loads(payload.get_payload())
                if debug: print("{}JSON String Returned:{} {}".format(bcolors.OKBLUE, bcolors.ENDC, json.dumps(j)))
            elif payload.get_content_type() == "audio/mpeg":
                filename = path + "tmpcontent/" + payload.get('Content-ID').strip("<>").replace(":","") + ".mp3"
                with open(filename, 'wb') as f:
                    f.write(payload.get_payload())
            else:
                if debug: print(
                    "{}NEW CONTENT TYPE RETURNED: {} {}".format(bcolors.WARNING, bcolors.ENDC,
                                                                payload.get_content_type()))
        # Now process the response
        if 'directives' in j['messageBody']:
            if len(j['messageBody']['directives']) == 0:
                if debug: print("0 Directives received")
                GPIO.output(rec_light, GPIO.LOW)
                GPIO.output(plb_light, GPIO.LOW)
            for directive in j['messageBody']['directives']:
                if directive['namespace'] == 'SpeechSynthesizer':
                    if directive['name'] == 'speak':
                        GPIO.output(rec_light, GPIO.LOW)
                        play_audio(path + "tmpcontent/" + directive['payload']['audioContent'].lstrip("cid:").replace(":","") + ".mp3")
                    for directive in j['messageBody']['directives']:  # if Alexa expects a response
                        if directive[
                            'namespace'] == 'SpeechRecognizer':  # this is included in the same string as above if a response was expected
                            if directive['name'] == 'listen':
                                if debug: print(
                                    "{}Further Input Expected, timeout in: {} {}ms".format(bcolors.OKBLUE, bcolors.ENDC,
                                                                                           directive['payload'][
                                                                                               'timeoutIntervalInMillis']))
                                play_audio(path + 'beep.wav', 0, 100)
                                timeout = directive['payload']['timeoutIntervalInMillis'] / 116
                                # listen until the timeout from Alexa
                                silence_listener(timeout)
                                # now process the response
                                alexa_speech_recognizer()
                elif directive['namespace'] == 'AudioPlayer':
                    # do audio stuff - still need to honor the playBehavior
                    if directive['name'] == 'play':
                        nav_token = directive['payload']['navigationToken']
                        for stream in directive['payload']['audioItem']['streams']:
                            if stream['progressReportRequired']:
                                streamid = stream['streamId']
                                playBehavior = directive['payload']['playBehavior']
                            if stream['streamUrl'].startswith("cid:"):
                                content = path + "tmpcontent/" + stream['streamUrl'].lstrip("cid:").replace(":","") + ".mp3"
                            else:
                                content = stream['streamUrl']
                            pThread = threading.Thread(target=play_audio,
                                                       args=(content, stream['offsetInMilliseconds']))
                            pThread.start()
                elif directive['namespace'] == "Speaker":
                    # speaker control such as volume
                    if directive['name'] == 'SetVolume':
                        vol_token = directive['payload']['volume']
                        type_token = directive['payload']['adjustmentType']
                        if (type_token == 'relative'):
                            currVolume = currVolume + int(vol_token)
                        else:
                            currVolume = int(vol_token)

                        if (currVolume > MAX_VOLUME):
                            currVolume = MAX_VOLUME
                        elif (currVolume < MIN_VOLUME):
                            currVolume = MIN_VOLUME

                        if debug: print("new volume = {}".format(currVolume))

        elif 'audioItem' in j['messageBody']:  # Additional Audio Iten
            nav_token = j['messageBody']['navigationToken']
            for stream in j['messageBody']['audioItem']['streams']:
                if stream['progressReportRequired']:
                    streamid = stream['streamId']
                if stream['streamUrl'].startswith("cid:"):
                    content = path + "tmpcontent/" + stream['streamUrl'].lstrip("cid:").replace(":","") + ".mp3"
                else:
                    content = stream['streamUrl']
                pThread = threading.Thread(target=play_audio, args=(content, stream['offsetInMilliseconds']))
                pThread.start()

        return
    elif r.status_code == 204:
        GPIO.output(rec_light, GPIO.LOW)
        for x in range(0, 3):
            time.sleep(.2)
            GPIO.output(plb_light, GPIO.HIGH)
            time.sleep(.2)
            GPIO.output(plb_light, GPIO.LOW)
        if debug: print(
            "{}Request Response is null {}(This is OKAY!){}".format(bcolors.OKBLUE, bcolors.OKGREEN, bcolors.ENDC))
    else:
        print("{}(process_response Error){} Status Code: {}".format(bcolors.WARNING, bcolors.ENDC, r.status_code))
        r.connection.close()
        GPIO.output(rec_light, GPIO.LOW)
        for x in range(0, 3):
            time.sleep(.2)
            GPIO.output(rec_light, GPIO.HIGH)
            time.sleep(.2)
            GPIO.output(lights, GPIO.LOW)


def play_audio(file=DETECT_DING, offset=0, overRideVolume=0):
    global currVolume
    if (file.find('radiotime.com') != -1):
        file = tuneinplaylist(file)
    global nav_token, p, audioplaying
    if debug: print("{}Play_Audio Request for:{} {}".format(bcolors.OKBLUE, bcolors.ENDC, file))
    GPIO.output(plb_light, GPIO.HIGH)
    #i = vlc.Instance('--aout=alsa')  # , '--alsa-audio-device=mono', '--file-logging', '--logfile=vlc-log.txt')
    i = vlc.Instance('--aout=alsa', '--alsa-audio-device=hw:0,0')
    m = i.media_new(file)
    p = i.media_player_new()
    p.set_media(m)
    mm = m.event_manager()
    mm.event_attach(vlc.EventType.MediaStateChanged, state_callback, p)
    audioplaying = True

    if (overRideVolume == 0):
        p.audio_set_volume(currVolume)
    else:
        p.audio_set_volume(overRideVolume)

    p.play()
    while audioplaying:
        continue
    GPIO.output(plb_light, GPIO.LOW)


def tuneinplaylist(url):
    global tunein_parser
    if (debug): print("TUNE IN URL = {}".format(url))
    req = requests.get(url)
    lines = req.content.split('\n')

    nurl = tunein_parser.parse_stream_url(lines[0])
    if (len(nurl) != 0):
        return nurl[0]

    return ""


def state_callback(event, player):
    global nav_token, audioplaying, streamurl, streamid
    state = player.get_state()
    # 0: 'NothingSpecial'
    # 1: 'Opening'
    # 2: 'Buffering'
    # 3: 'Playing'
    # 4: 'Paused'
    # 5: 'Stopped'
    # 6: 'Ended'
    # 7: 'Error'
    if debug: print("{}Player State:{} {}".format(bcolors.OKGREEN, bcolors.ENDC, state))
    if state == 3:  # Playing
        if streamid != "":
            rThread = threading.Thread(target=alexa_playback_progress_report_request,
                                       args=("STARTED", "PLAYING", streamid))
            rThread.start()
    elif state == 5:  # Stopped
        audioplaying = False
        if streamid != "":
            rThread = threading.Thread(target=alexa_playback_progress_report_request,
                                       args=("INTERRUPTED", "IDLE", streamid))
            rThread.start()
        streamurl = ""
        streamid = ""
        nav_token = ""
    elif state == 6:  # Ended
        audioplaying = False
        if streamid != "":
            rThread = threading.Thread(target=alexa_playback_progress_report_request,
                                       args=("FINISHED", "IDLE", streamid))
            rThread.start()
            streamid = ""
        if streamurl != "":
            pThread = threading.Thread(target=play_audio, args=(streamurl,))
            streamurl = ""
            pThread.start()
        elif nav_token != "":
            gThread = threading.Thread(target=alexa_getnextitem, args=(nav_token,))
            gThread.start()
    elif state == 7:
        audioplaying = False
        if streamid != "":
            rThread = threading.Thread(target=alexa_playback_progress_report_request, args=("ERROR", "IDLE", streamid))
            rThread.start()
        streamurl = ""
        streamid = ""
        nav_token = ""

def silence_listener(triggeredbyvoice):
    # Reenable reading microphone raw data
    stream = audio.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK,input_device_index=0)
    framerec = []

    # Buffer as long as we haven't heard enough silence or the total size is within max size
    # thresholdSilenceMet = False
    # frames = 0
    # numSilenceRuns = 0
    # silenceRun = 0
    start = time.time()
    play_audio(DETECT_DING)
    print ("Start recording")
    # #do not count first 10 frames when doing VAD
    # while (frames < throwaway_frames):  # VAD_THROWAWAY_FRAMES):
    #     data = stream.read(CHUNK, exception_on_overflow=False)
    #     frames = frames + 1
    #     framerec.append(data)
    # now do VAD
    if triggeredbyvoice:
        for i in range(0, int(RATE/CHUNK * MAX_RECORDING_LENGTH)):
            data = stream.read(CHUNK, exception_on_overflow=False)
            framerec.append(data)
    else:
        while ((time.time() - start) < MAX_RECORDING_LENGTH):
            data = stream.read(CHUNK, exception_on_overflow=False)
            framerec.append(data)
            GPIO.output(rec_light, GPIO.HIGH)

    print ("End recording")
    play_audio(path+'resources/r2-ok.mp3')

    if debug: play_audio(path+'beep.wav', 0, 100)
    stream.close()

    GPIO.output(rec_light, GPIO.LOW)
    waveFile = wave.open(path+WAVE_OUTPUT_FILENAME, 'wb')
    waveFile.setnchannels(CHANNELS)
    waveFile.setsampwidth(audio.get_sample_size(FORMAT))
    waveFile.setframerate(RATE)
    waveFile.writeframes(b''.join(framerec))
    waveFile.close()



def start(triggerword=False):
    global audioplaying, p

    while True:
        record_audio = False

        # Enable reading microphone raw data
        stream = audio.open(format=FORMAT,
                            channels=CHANNELS,
                            rate=RATE,
                            input=True,
                            frames_per_buffer=CHUNK,input_device_index=0)
        framerec = []
        start = time.time()

        while record_audio == False:
            time.sleep(.1)


            if triggerword:
                if audioplaying: p.stop()
                start = time.time()
                record_audio = True

            if debug: print ("detected the edge, setting up audio")
            #
            # To avoid overflows close the microphone connection
            stream.close()

            # # clean up the temp directory
            if debug == False: os.system("rm tmpcontent/*")
            #
            if debug: print "Starting to listen..."
            if triggerword: silence_listener(True)
            else: silence_listener(False)
            if debug: print "Debug: Sending audio to be processed"
            alexa_speech_recognizer()
            # Now that request is handled restart audio decoding

            redetect = snowboydecoder.HotwordDetector(model, sensitivity=0.5)
            print('Ready to hear your voice')

            redetect.start(interrupt_check=interrupt_callback,
                           sleep_time=0.03)
            ##############################################################################


def setup():
    GPIO.init()
    GPIO.setcfg(lights[0], GPIO.OUTPUT)
    GPIO.setcfg(lights[1], GPIO.OUTPUT)

    while internet_on() == False:
        print(".")
    token = gettoken()
    if token == False:
        while True:
            for x in range(0, 5):
                time.sleep(.1)
                GPIO.output(rec_light, GPIO.HIGH)
                time.sleep(.1)
                GPIO.output(rec_light, GPIO.LOW)
    for x in range(0, 5):
        time.sleep(.1)
        GPIO.output(plb_light, GPIO.HIGH)
        time.sleep(.1)
        GPIO.output(plb_light, GPIO.LOW)
    if (silent == False): play_audio(path + "hello.mp3")


def signal_handler(signal, frame):
    global interrupted
    interrupted = True

# capture SIGINT signal, e.g., Ctrl+C
signal.signal(signal.SIGINT, signal_handler)

if __name__ == "__main__":
    setup()
    start()
