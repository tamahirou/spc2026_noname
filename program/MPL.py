import time
from machine import I2C, Pin

# ==== I2C 設定 ====
# RaPi Pico の例: I2C(0) / scl=GP1 / sda=GP0
i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400_000)
ADDR = 0x60  # MPL3115A2 の I2C アドレス

# ==== レジスタ定義（MPL3115A2）====
REG_STATUS      = 0x00
REG_OUT_P_MSB   = 0x01
REG_OUT_T_MSB   = 0x04
REG_WHOAMI      = 0x0C
REG_PT_DATA_CFG = 0x13
REG_CTRL_REG1   = 0x26

WHOAMI_EXPECTED = 0xC4  # WHO_AM_I[web:7]


def write_reg(reg, val):
    i2c.writeto_mem(ADDR, reg, bytes([val]))


def read_reg(reg):
    return i2c.readfrom_mem(ADDR, reg, 1)[0]


def init_sensor():
    # スタンバイにする
    ctrl1 = read_reg(REG_CTRL_REG1)
    write_reg(REG_CTRL_REG1, ctrl1 & ~0x01)  # STANDBY

    # 気圧モード（ALT=0）、オーバーサンプリング 128（OS=0b111）[web:7]
    ctrl1 = (ctrl1 & ~0xB8) | (0x00 << 7) | (0x07 << 3)
    write_reg(REG_CTRL_REG1, ctrl1)

    # イベントフラグ有効化（気圧・温度）[web:7]
    write_reg(REG_PT_DATA_CFG, 0x07)

    # アクティブにする
    ctrl1 = read_reg(REG_CTRL_REG1)
    write_reg(REG_CTRL_REG1, ctrl1 | 0x01)  # ACTIVE


def read_pressure_temperature():
    # ワンショットトリガ（OSTビット）[web:7]
    ctrl1 = read_reg(REG_CTRL_REG1)
    write_reg(REG_CTRL_REG1, ctrl1 | 0x02)

    # データ準備完了待ち
    for _ in range(50):
        status = read_reg(REG_STATUS)
        if status & 0x08:  # PDR ビット
            break
        time.sleep(0.05)
    else:
        raise RuntimeError("センサからデータが来ません")

    # 6バイト読出し（P_MSB〜T_LSB）[web:7]
    data = i2c.readfrom_mem(ADDR, REG_OUT_P_MSB, 6)

    # 気圧 20bit（Pa）[web:7]
    p_msb, p_csb, p_lsb = data[0], data[1], data[2]
    p_raw = ((p_msb << 16) | (p_csb << 8) | p_lsb) >> 4
    pressure_pa = p_raw / 4.0  # 1カウント=0.25Pa

    # 温度 12bit[web:7]
    t_msb, t_lsb = data[3], data[4]
    t_raw = ((t_msb << 8) | t_lsb) >> 4
    if t_raw & 0x800:     # 負数処理
        t_raw -= 1 << 12
    temperature_c = t_raw / 16.0  # 1カウント=0.0625℃

    return pressure_pa, temperature_c


def main():
    # アドレス確認用（デバッグ）
    print("scan:", [hex(a) for a in i2c.scan()])

    whoami = read_reg(REG_WHOAMI)
    print("WHOAMI:", hex(whoami))
    if whoami != WHOAMI_EXPECTED:
        print("WHOAMI 不一致")
        return

    print("MPL3115A2 検出 OK")
    init_sensor()
    time.sleep(1)

    while True:
        pressure, temp = read_pressure_temperature()
        print("気圧: {:.2f} hPa, 気温: {:.2f} ℃".format(pressure / 100, temp))
        time.sleep(1)


main()
