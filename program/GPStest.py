from machine import UART, Pin
import time
import os
import sys # sysモジュールをインポート (print()でも内部的に使用)
import ujson # MicroPythonのJSONライブラリ

# --- 設定 ---
# ファイル関連の設定
CSV_FILENAME = "gps_log.csv"

# シリアル出力とCSV記録の制御フラグ
SERIAL_OUTPUT_TO_REPL = True   # REPL (USBシリアル/Dashアプリ) にデータをJSONで表示するかどうか
RECORD_TO_CSV = True           # CSVファイルにデータを記録するかどうか

# UART (GPSモジュールとの通信用) の初期化
# PicoのGP12 (TX) とGP13 (RX) を使用してGPSモジュールと接続
# GPSモジュールのボーレートに合わせて設定してください (通常 9600 または 115200)
GPS_UART_ID = 0 # UART0を使用 (PicoのUSBシリアルとは異なる物理ピン)
GPS_UART_BAUDRATE = 115200 # GPSモジュールのボーレート
GPS_UART_TX_PIN = 1
GPS_UART_RX_PIN = 2

print("[INFO] UART初期化開始")
print(f"[INFO] GPS UARTボーレート: {GPS_UART_BAUDRATE}bps (TX:GP{GPS_UART_TX_PIN}, RX:GP{GPS_UART_RX_PIN})")
uart = UART(GPS_UART_ID,
            baudrate=GPS_UART_BAUDRATE,
            tx=Pin(GPS_UART_TX_PIN),
            rx=Pin(GPS_UART_RX_PIN),
            rxbuf=1024, # 受信バッファサイズを大きくすると、データ欠損が減る可能性があります
            timeout=100) # タイムアウトを長くすると、行の終わりを待つ時間が長くなります

def ensure_file_exists():
    """CSVファイルの存在確認と作成"""
    try:
        try:
            os.stat(CSV_FILENAME)
            print(f"[INFO] 既存のログファイルを使用: {CSV_FILENAME}")
        except OSError:
            print(f"[INFO] 新規ログファイル作成: {CSV_FILENAME}")
            with open(CSV_FILENAME, "w") as f:
                # ヘッダーにTimestamp, Altitude, Satellites, GPS_Quality, HDOP を追加
                f.write("Timestamp,Latitude,Longitude,Altitude,Satellites,GPS_Quality,HDOP\n")
        return True
    except Exception as e:
        print(f"[ERROR] ファイル作成エラー: {e}")
        return False

def convert_nmea_coord(raw_coord, direction):
    """NMEA座標を度数に変換"""
    try:
        if not raw_coord or not direction:
            return None
        
        parts = raw_coord.split('.')
        if len(parts) != 2:
            return None
            
        if len(parts[0]) > 2:  # 緯度 (DDMM.MMMMM) の場合
            degrees = float(parts[0][:-2])
            minutes = float(parts[0][-2:] + '.' + parts[1])
        else:  # 経度 (DDDMM.MMMMM) の場合
            degrees = float(parts[0])
            minutes = float('0.' + parts[1])
            
        value = degrees + (minutes / 60.0)
        
        if direction in ['S', 'W']:
            value = -value
            
        return value
    except (ValueError, IndexError, TypeError):
        return None

# CSVファイルの準備
if RECORD_TO_CSV:
    if not ensure_file_exists():
        raise RuntimeError("Failed to prepare log file for CSV recording.")

print("[INFO] GPSデータ処理開始")
print("-" * 50)

while True:
    if uart.any(): # UARTバッファにデータがあるか確認
        try:
            line = uart.readline() # 1行読み込み
            if line: # データが読み込めた場合
                # print("RAW:", line) # DEBUG: 生データ出力
                decoded_line = line.decode('utf-8').strip()
                
                if decoded_line.startswith('$GNGGA') or decoded_line.startswith('$GPGGA'):
                    parts = decoded_line.split(',')
                    if len(parts) >= 15:
                        try:
                            # NMEA GNGGA/GPGGA フォーマットの解析
                            # $GNGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47
                            utc_time_str = parts[1]
                            latitude_raw = parts[2]
                            lat_dir = parts[3]
                            longitude_raw = parts[4]
                            lon_dir = parts[5]
                            gps_quality = int(parts[6]) if parts[6] else 0
                            num_satellites = int(parts[7]) if parts[7] else 0
                            hdop = float(parts[8]) if parts[8] else 0.0
                            altitude = float(parts[9]) if parts[9] else 0.0
                            alt_unit = parts[10] # M (meters)

                            # 位置情報の処理
                            lat = convert_nmea_coord(latitude_raw, lat_dir)
                            lon = convert_nmea_coord(longitude_raw, lon_dir)

                            if lat is not None and lon is not None:
                                # 現在のUnixタイムスタンプを取得 (Dashアプリとの互換性のため)
                                current_timestamp = time.time()
                                
                                # 時刻表示用フォーマット
                                time_str = f"{utc_time_str[:2]}:{utc_time_str[2:4]}:{utc_time_str[4:6]}" if len(utc_time_str) >= 6 else utc_time_str
                                
                                # 詳細情報のREPL表示
                                print("-" * 50)
                                print(f"時刻(UTC): {time_str}")
                                print(f"緯度: {lat:.6f} {lat_dir}")
                                print(f"経度: {lon:.6f} {lon_dir}")
                                print(f"高度: {altitude:.1f} {alt_unit}")
                                print(f"衛星数: {num_satellites}")
                                print(f"HDOP: {hdop:.1f}")
                                print(f"GPS品質: {gps_quality} (0:無効, 1:GPS固定, 2:DGPS固定)")
                                
                                # JSON形式でシリアルポートに出力 (Dashアプリが読み取る)
                                if SERIAL_OUTPUT_TO_REPL:
                                    gps_data = {
                                        "type": "gps", # データの種類を明示
                                        "latitude": round(lat, 6),
                                        "longitude": round(lon, 6),
                                        "timestamp": current_timestamp,
                                        "altitude": round(altitude, 1),
                                        "num_satellites": num_satellites,
                                        "gps_quality": gps_quality,
                                        "hdop": round(hdop, 1)
                                    }
                                    sys.stdout.write(ujson.dumps(gps_data) + '\n')
                                
                                # CSVファイルに記録
                                if RECORD_TO_CSV:
                                    try:
                                        csv_line = (
                                            f"{current_timestamp},"
                                            f"{lat:.6f},{lon:.6f},"
                                            f"{altitude:.1f},{num_satellites},{gps_quality},{hdop:.1f}\n"
                                        )
                                        with open(CSV_FILENAME, "a") as f:
                                            f.write(csv_line)
                                    except OSError as e:
                                        print(f"[ERROR] CSV書き込みエラー: {e}")
                                        # CSV書き込みエラーの場合、ファイルが存在しない可能性があるので再作成を試みる
                                        if not ensure_file_exists():
                                            print("[ERROR] CSVファイル再作成にも失敗しました。")
                            else:
                                print("-" * 50)
                                print(f"衛星捕捉待ち (緯度/経度データが無効)")
                                print(f"衛星数: {num_satellites}")
                                print(f"GPS品質: {gps_quality} (0:無効, 1:GPS固定, 2:DGPS固定)")
                        except (ValueError, IndexError, TypeError) as e:
                            print(f"[ERROR] NMEAデータ解析エラー: {e} (ライン: {decoded_line})")
                    else:
                        print(f"[WARNING] 不完全なGNGGA/GPGGAライン: {decoded_line}")

        except UnicodeError:
            # デコードできないバイトシーケンスはスキップ
            pass
        except Exception as e:
            print(f"[ERROR] 予期せぬUARTデータ処理エラー: {str(e)}")
            
    # 短いディレイを挟むことでCPU負荷を軽減しつつ、新しいNMEAデータを待機
    time.sleep(0.1) # GPSモジュールの更新頻度に合わせて調整 (通常1Hzなので0.1-0.5秒程度で十分)


