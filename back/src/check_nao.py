import paramiko

# --- 設定 ---
NAO_IP = "10.96.8.112"  # ★あなたのNAOのIPに書き換えてください
NAO_PORT = 22
NAO_USER = "nao"
NAO_PASS = "nao" 

# NAOの中で実行させるコード
# ※ sys.pathを追加して、確実にnaoqiを見つけられるようにします
remote_code = """
import sys
import os

# 一般的なNAOqiのパスを追加
sys.path.append("/opt/aldebaran/lib/python2.7/site-packages")
sys.path.append("/usr/lib/python2.7/site-packages")

try:
    from naoqi import ALProxy
    
    # 接続テスト
    tts = ALProxy("ALTextToSpeech", "127.0.0.1", 9559)
    tts.setLanguage("Japanese")
    tts.say("Connected")
    print("SUCCESS")
    
except ImportError:
    print("ERROR: Still cannot find naoqi. Python path is: " + str(sys.path))
except Exception as e:
    print("ERROR: " + str(e))
"""

def check_connection():
    print(f"Connecting to NAO ({NAO_IP})...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(NAO_IP, port=NAO_PORT, username=NAO_USER, password=NAO_PASS)
        print("SSH Connection Established!")
        
        # ★ここを変更: python2.7 を明示的に呼び出す
        # -i オプションで環境変数を読み込ませる試み
        cmd = f"/usr/bin/python2.7 -c '{remote_code}'"
        
        print("Executing script on NAO...")
        stdin, stdout, stderr = client.exec_command(cmd)
        
        output = stdout.read().decode('utf-8').strip()
        error = stderr.read().decode('utf-8').strip()
        
        if "SUCCESS" in output:
            print("✅ 成功！NAOが 'Connected' と喋りました。")
        else:
            print(f"⚠️ NAO側でエラー:\n{output}\n{error}")
            
    except Exception as e:
        print(f"❌ PC側でエラー: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_connection()