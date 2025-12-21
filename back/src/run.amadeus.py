import paramiko
import time
import sys

# --- 設定 ---
NAO_IP = "10.96.8.112"   # ★あなたのNAOのIP
NAO_USER = "nao"
NAO_PASS = "nao"
LOCAL_FILE = "nao_eye.py"
REMOTE_FILE = "/home/nao/nao_eye.py"

def create_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    # タイムアウト対策設定
    client.connect(
        NAO_IP, 
        username=NAO_USER, 
        password=NAO_PASS, 
        timeout=30,
        banner_timeout=60,
        look_for_keys=False,
        allow_agent=False
    )
    return client

def upload_file():
    print(f"1. Uploading {LOCAL_FILE} to NAO...")
    client = None
    try:
        client = create_client()
        sftp = client.open_sftp()
        sftp.put(LOCAL_FILE, REMOTE_FILE)
        sftp.close()
        print("   Upload successful.")
    except Exception as e:
        print(f"   Upload Failed: {e}")
        sys.exit(1)
    finally:
        if client: client.close()

def run_remote_script():
    print("2. Starting Amadeus Eye on NAO (New Connection)...")
    print("   Press Ctrl+C to stop.")
    client = None
    try:
        client = create_client()
        
        # コマンドを変更: 環境変数を読み込ませてから実行
        # python -u を使うことでバッファリングを無効化
        cmd = "source /etc/profile; python -u " + REMOTE_FILE
        
        stdin, stdout, stderr = client.exec_command(cmd)
        
        # 出力監視ループ
        while True:
            if stdout.channel.recv_ready():
                line = stdout.channel.recv(1024).decode('utf-8', errors='ignore')
                print(f"[NAO]: {line}", end="")
            
            if stderr.channel.recv_ready():
                line = stderr.channel.recv(1024).decode('utf-8', errors='ignore')
                print(f"[NAO ERR]: {line}", end="")

            if stdout.channel.exit_status_ready():
                # プロセス終了
                break
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nStopping by user...")
        # 終了時にCtrl+CをNAOにも送れればベストだが、今回は接続を切る
    except Exception as e:
        print(f"\nExecution Error: {e}")
    finally:
        if client: client.close()
        print("Connection closed.")
        
if __name__ == "__main__":
    upload_file()
    time.sleep(1)
    run_remote_script()