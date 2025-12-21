# -*- coding: utf-8 -*-
import sys
import os
import time
import subprocess # ★コマンド実行用ライブラリ
from naoqi import ALProxy

# --- 設定 ---
# ★ここに、curlで成功したときのIPアドレスを正確に入れてください
PC_IP = "192.168.10.3"  
PC_PORT = "8000"
# URL
ENDPOINT = "http://" + PC_IP + ":" + PC_PORT + "/api/nao/trigger"

def main(ip, port):
    sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)
    print "info: Script started (Curl Mode)."

    try:
        mem = ALProxy("ALMemory", ip, port)
        face = ALProxy("ALFaceDetection", ip, port)
        tts = ALProxy("ALTextToSpeech", ip, port)
        leds = ALProxy("ALLeds", ip, port)
    except Exception as e:
        print "FATAL ERROR: Proxy connection failed. " + str(e)
        return

    try:
        face.subscribe("AmadeusFace")
        print "info: Face detection started."
    except Exception:
        pass

    cooldown = False
    
    try:
        while True:
            val = mem.getData("FaceDetected")
            
            if val and isinstance(val, list) and len(val) >= 2 and not cooldown:
                print "Event: Face Detected!"
                
                leds.fadeRGB("FaceLeds", "red", 0.1)
                tts.say("Target confirmed.")
                
                # --- PCへの送信（ここをcurlコマンドに変更）---
                print "info: Executing curl command..."
                try:
                    # コマンドを組み立てる
                    # curl -X POST -H "Content-Type: application/json" -d '...' URL
                    cmd = [
                        "/usr/bin/curl",
                        "-v",
                        "-X", "POST",
                        "-H", "Content-Type: application/json",
                        "-d", '{"message": "Face detected", "target_value": null}',
                        "--connect-timeout", "5",
                        ENDPOINT
                    ]
                    
                    # 実行！
                    ret = subprocess.call(cmd)
                    
                    if ret == 0:
                        print "Sent to PC: Success (Exit Code 0)"
                    else:
                        print "Curl Failed with Exit Code: " + str(ret)
                        
                except Exception as e:
                    print "Command Execution Error: " + str(e)
                # -------------------------------------------
                
                cooldown = True
                time.sleep(5)
                
                leds.fadeRGB("FaceLeds", "white", 0.5)
                cooldown = False
                print "info: Ready for next."

            time.sleep(0.5)

    except KeyboardInterrupt:
        print "Interrupted."
    except Exception as e:
        print "CRASH: " + str(e)
    finally:
        try:
            face.unsubscribe("AmadeusFace")
        except:
            pass
        leds.reset("FaceLeds")

if __name__ == "__main__":
    main("127.0.0.1", 9559)