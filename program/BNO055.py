"""
BNO055 9軸センサーモジュール テストプログラム (MicroPython)

接続:
  VDD -> 3.3V
  GND -> GND
  SDA -> GPIO2 (Pin 3) または GPIO0
  SCL -> GPIO3 (Pin 5) または GPIO1
  PS0 -> GND (I2Cモード)
  PS1 -> GND (I2Cアドレス: 0x28)

使用方法:
  Raspberry Pi Picoの場合、Thonnyなどで実行
"""

from machine import I2C, Pin
import time
import struct

# ========================================
# 設定
# ========================================
# I2C設定 (Raspberry Pi Picoの場合)
# I2C0: SDA=GP0,GP4,GP8,GP12,GP16,GP20  SCL=GP1,GP5,GP9,GP13,GP17,GP21
# I2C1: SDA=GP2,GP6,GP10,GP14,GP18,GP26 SCL=GP3,GP7,GP11,GP15,GP19,GP27
I2C_ID = 1              # I2Cバス番号 (0 or 1)
I2C_SDA_PIN = 2         # SDAピン番号
I2C_SCL_PIN = 3         # SCLピン番号
I2C_FREQ = 1000         # I2C周波数 (400kHz)

BNO055_ADDRESS = 0x28   # I2Cアドレス
UPDATE_INTERVAL = 0.1   # データ更新間隔(秒)

# ========================================
# レジスタアドレス
# ========================================
BNO055_CHIP_ID = 0x00
BNO055_OPR_MODE = 0x3D
BNO055_PWR_MODE = 0x3E
BNO055_SYS_TRIGGER = 0x3F
BNO055_CALIB_STAT = 0x35
BNO055_SYS_STATUS = 0x39
BNO055_SYS_ERROR = 0x3A

# データレジスタ
BNO055_EULER_H_LSB = 0x1A
BNO055_QUATERNION_W_LSB = 0x20
BNO055_ACCEL_DATA_X_LSB = 0x08
BNO055_GYRO_DATA_X_LSB = 0x14
BNO055_MAG_DATA_X_LSB = 0x0E
BNO055_LINEAR_ACCEL_X_LSB = 0x28
BNO055_GRAVITY_X_LSB = 0x2E

# 動作モード
OPERATION_MODE_CONFIG = 0x00
OPERATION_MODE_NDOF = 0x0C        # 9軸フュージョン
OPERATION_MODE_IMU = 0x08         # 6軸フュージョン(加速度+ジャイロ)
OPERATION_MODE_COMPASS = 0x09     # 地磁気コンパス


class BNO055:
    def __init__(self, i2c, address=BNO055_ADDRESS):
        self.i2c = i2c
        self.address = address
        
    def write_byte(self, reg, value):
        """1バイト書き込み"""
        self.i2c.writeto_mem(self.address, reg, bytes([value]))
        
    def read_byte(self, reg):
        """1バイト読み込み"""
        return self.i2c.readfrom_mem(self.address, reg, 1)[0]
    
    def read_bytes(self, reg, length):
        """複数バイト読み込み"""
        return self.i2c.readfrom_mem(self.address, reg, length)
    
    def init(self):
        """センサー初期化"""
        print("BNO055を初期化中...")
        
        # チップID確認
        chip_id = self.read_byte(BNO055_CHIP_ID)
        if chip_id != 0xA0:
            raise RuntimeError(f"BNO055が見つかりません (ID: 0x{chip_id:02X})")
        print(f"BNO055検出 (ID: 0x{chip_id:02X})")
        
        # コンフィグモードに設定
        self.write_byte(BNO055_OPR_MODE, OPERATION_MODE_CONFIG)
        time.sleep(0.03)
        
        # 電源モードをNormalに設定
        self.write_byte(BNO055_PWR_MODE, 0x00)
        time.sleep(0.01)
        
        # システムリセット
        self.write_byte(BNO055_SYS_TRIGGER, 0x20)
        time.sleep(0.7)
        
        # リセット後のチップID再確認
        while self.read_byte(BNO055_CHIP_ID) != 0xA0:
            time.sleep(0.01)
        time.sleep(0.05)
        
        # 電源モードをNormalに設定
        self.write_byte(BNO055_PWR_MODE, 0x00)
        time.sleep(0.01)
        
        # NDOFモード(9軸センサーフュージョン)に設定
        self.write_byte(BNO055_OPR_MODE, OPERATION_MODE_NDOF)
        time.sleep(0.02)
        
        print("初期化完了")
        
    def get_calibration_status(self):
        """キャリブレーション状態取得"""
        calib = self.read_byte(BNO055_CALIB_STAT)
        sys = (calib >> 6) & 0x03
        gyro = (calib >> 4) & 0x03
        accel = (calib >> 2) & 0x03
        mag = calib & 0x03
        return sys, gyro, accel, mag
    
    def get_system_status(self):
        """システム状態取得"""
        status = self.read_byte(BNO055_SYS_STATUS)
        error = self.read_byte(BNO055_SYS_ERROR)
        return status, error
    
    def get_euler(self):
        """オイラー角取得 (Heading, Roll, Pitch) [度]"""
        data = self.read_bytes(BNO055_EULER_H_LSB, 6)
        heading = struct.unpack('<h', data[0:2])[0] / 16.0
        roll = struct.unpack('<h', data[2:4])[0] / 16.0
        pitch = struct.unpack('<h', data[4:6])[0] / 16.0
        return heading, roll, pitch
    
    def get_quaternion(self):
        """クォータニオン取得"""
        data = self.read_bytes(BNO055_QUATERNION_W_LSB, 8)
        w = struct.unpack('<h', data[0:2])[0] / 16384.0
        x = struct.unpack('<h', data[2:4])[0] / 16384.0
        y = struct.unpack('<h', data[4:6])[0] / 16384.0
        z = struct.unpack('<h', data[6:8])[0] / 16384.0
        return w, x, y, z
    
    def get_acceleration(self):
        """加速度取得 [m/s²]"""
        data = self.read_bytes(BNO055_ACCEL_DATA_X_LSB, 6)
        x = struct.unpack('<h', data[0:2])[0] / 100.0
        y = struct.unpack('<h', data[2:4])[0] / 100.0
        z = struct.unpack('<h', data[4:6])[0] / 100.0
        return x, y, z
    
    def get_gyroscope(self):
        """角速度取得 [deg/s]"""
        data = self.read_bytes(BNO055_GYRO_DATA_X_LSB, 6)
        x = struct.unpack('<h', data[0:2])[0] / 16.0
        y = struct.unpack('<h', data[2:4])[0] / 16.0
        z = struct.unpack('<h', data[4:6])[0] / 16.0
        return x, y, z
    
    def get_magnetometer(self):
        """地磁気取得 [μT]"""
        data = self.read_bytes(BNO055_MAG_DATA_X_LSB, 6)
        x = struct.unpack('<h', data[0:2])[0] / 16.0
        y = struct.unpack('<h', data[2:4])[0] / 16.0
        z = struct.unpack('<h', data[4:6])[0] / 16.0
        return x, y, z
    
    def get_linear_acceleration(self):
        """線形加速度取得(重力除去) [m/s²]"""
        data = self.read_bytes(BNO055_LINEAR_ACCEL_X_LSB, 6)
        x = struct.unpack('<h', data[0:2])[0] / 100.0
        y = struct.unpack('<h', data[2:4])[0] / 100.0
        z = struct.unpack('<h', data[4:6])[0] / 100.0
        return x, y, z
    
    def get_gravity(self):
        """重力ベクトル取得 [m/s²]"""
        data = self.read_bytes(BNO055_GRAVITY_X_LSB, 6)
        x = struct.unpack('<h', data[0:2])[0] / 100.0
        y = struct.unpack('<h', data[2:4])[0] / 100.0
        z = struct.unpack('<h', data[4:6])[0] / 100.0
        return x, y, z


def main():
    print("=" * 60)
    print("BNO055 9軸センサー テストプログラム (MicroPython)")
    print("=" * 60)
    print()
    
    try:
        # I2C初期化
        print(f"I2C初期化中... (SDA=GPIO{I2C_SDA_PIN}, SCL=GPIO{I2C_SCL_PIN})")
        i2c = I2C(I2C_ID, sda=Pin(I2C_SDA_PIN), scl=Pin(I2C_SCL_PIN), freq=I2C_FREQ)
        
        # I2Cデバイススキャン
        devices = i2c.scan()
        print(f"I2Cデバイス検出: {[hex(d) for d in devices]}")
        
        if BNO055_ADDRESS not in devices:
            print(f"エラー: BNO055 (0x{BNO055_ADDRESS:02X}) が見つかりません")
            print("接続を確認してください")
            return
        
        # センサー初期化
        sensor = BNO055(i2c)
        sensor.init()
        
        print("\nキャリブレーション中...")
        print("センサーをゆっくり様々な方向に回転させてください")
        print("キャリブレーション状態: Sys Gyro Acc Mag (各0-3)")
        print("-" * 60)
        
        # メインループ
        while True:
            # キャリブレーション状態
            sys_cal, gyro_cal, accel_cal, mag_cal = sensor.get_calibration_status()
            
            # オイラー角
            heading, roll, pitch = sensor.get_euler()
            
            # 加速度
            ax, ay, az = sensor.get_acceleration()
            
            # ジャイロ
            gx, gy, gz = sensor.get_gyroscope()
            
            # 地磁気
            mx, my, mz = sensor.get_magnetometer()
            
            # 表示
            print(f"Cal:[{sys_cal} {gyro_cal} {accel_cal} {mag_cal}] "
                  f"Euler H:{heading:6.1f}° R:{roll:6.1f}° P:{pitch:6.1f}° | "
                  f"Acc X:{ax:6.2f} Y:{ay:6.2f} Z:{az:6.2f} m/s²")
            
            time.sleep(UPDATE_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\n終了します")
    except Exception as e:
        print(f"\nエラー: {e}")
        import sys
        sys.print_exception(e)


if __name__ == "__main__":
    main()
