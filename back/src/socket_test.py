# -*- coding: utf-8 -*-
import socket
import sys
import os

# --- 設定 ---
HOST = '10.96.8.115'  # ★PCのIPアドレス
PORT = 8000

def raw_http_test():
    sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)
    
    print "--- RAW SOCKET TEST (v3: User-Agent Added) ---"
    print "Target: " + HOST + ":" + str(PORT)
    
    try:
        # 1. Socket Create
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(10)
        
        # 2. Connect
        print "Connecting..."
        s.connect((HOST, PORT))
        print "Connected!"
        
        # 3. Request Body
        body = '{"message": "SocketTest", "target_value": 1}'
        content_len = len(body)
        
        # ★ここが重要！ curlのフリをするヘッダーを追加
        request = "POST /api/nao/trigger HTTP/1.1\r\n" + \
                  "Host: " + HOST + "\r\n" + \
                  "User-Agent: curl/7.68.0\r\n" + \
                  "Accept: */*\r\n" + \
                  "Content-Type: application/json\r\n" + \
                  "Content-Length: " + str(content_len) + "\r\n" + \
                  "Connection: close\r\n" + \
                  "\r\n" + \
                  body
        
        print "Sending HTTP Request..."
        s.sendall(request)
        
        # 4. Receive Response
        print "Waiting for response..."
        response = ""
        while True:
            data = s.recv(1024)
            if not data: break
            response += data
            
        print "--- SERVER RESPONSE ---"
        if len(response) == 0:
            print "[EMPTY] Still empty. Check Server Logs!"
        else:
            print response
        print "-----------------------"
        
        s.close()
        
    except Exception as e:
        print "!!! FAILURE !!!"
        print str(e)

if __name__ == "__main__":
    raw_http_test()