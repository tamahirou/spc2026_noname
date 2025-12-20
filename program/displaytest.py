from machine import Pin, I2C
import framebuf
import time

# ========================================
# ピン設定 - 使用するマイコンに合わせて変更
# ========================================
# Raspberry Pi Pico / Pico W の場合
# I2C0: SDA=GP0,GP4,GP8,GP12,GP16,GP20  SCL=GP1,GP5,GP9,GP13,GP17,GP21
# I2C1: SDA=GP2,GP6,GP10,GP14,GP18,GP26 SCL=GP3,GP7,GP11,GP15,GP19,GP27

# 推奨設定 (I2C0)
SDA_PIN = 10  # GP10
SCL_PIN = 11  # GP11
I2C_BUS = 1  # I2C0

# GPIO10, GPIO11を使う場合 (I2C1)
# SDA_PIN = 10  # GP10
# SCL_PIN = 11  # GP11
# I2C_BUS = 1   # I2C1

# その他の組み合わせ例
# SDA_PIN = 4   # GP4
# SCL_PIN = 5   # GP5
# I2C_BUS = 0   # I2C0

# SDA_PIN = 6   # GP6
# SCL_PIN = 7   # GP7
# I2C_BUS = 1   # I2C1

# ESP32 の場合 (コメントを外して使用)
# SDA_PIN = 21  # GPIO21
# SCL_PIN = 22  # GPIO22
# I2C_BUS = 0

# ESP8266 の場合 (コメントを外して使用)
# SDA_PIN = 4   # GPIO4 (D2)
# SCL_PIN = 5   # GPIO5 (D1)
# I2C_BUS = 0

# I2C設定
I2C_FREQ = 400000  # 400kHz
I2C_ADDR = 0x3C    # OLEDのI2Cアドレス

# ========================================
# SSD1306 OLEDディスプレイドライバ
# ========================================

# レジスタ定義
SET_CONTRAST = 0x81
SET_ENTIRE_ON = 0xA4
SET_NORM_INV = 0xA6
SET_DISP = 0xAE
SET_MEM_ADDR = 0x20
SET_COL_ADDR = 0x21
SET_PAGE_ADDR = 0x22
SET_DISP_START_LINE = 0x40
SET_SEG_REMAP = 0xA0
SET_MUX_RATIO = 0xA8
SET_COM_OUT_DIR = 0xC0
SET_DISP_OFFSET = 0xD3
SET_COM_PIN_CFG = 0xDA
SET_DISP_CLK_DIV = 0xD5
SET_PRECHARGE = 0xD9
SET_VCOM_DESEL = 0xDB
SET_CHARGE_PUMP = 0x8D


class SSD1306:
    """SSD1306 OLEDディスプレイ基本クラス"""
    
    def __init__(self, width, height, external_vcc):
        self.width = width
        self.height = height
        self.external_vcc = external_vcc
        self.pages = self.height // 8
        self.buffer = bytearray(self.pages * self.width)
        fb = framebuf.FrameBuffer(self.buffer, self.width, self.height, framebuf.MONO_VLSB)
        self.framebuf = fb
        self.fill = fb.fill
        self.pixel = fb.pixel
        self.hline = fb.hline
        self.vline = fb.vline
        self.line = fb.line
        self.rect = fb.rect
        self.fill_rect = fb.fill_rect
        self.text = fb.text
        self.scroll = fb.scroll
        self.blit = fb.blit
        self.ellipse = fb.ellipse
        self.init_display()

    def init_display(self):
        """ディスプレイ初期化"""
        for cmd in (
            SET_DISP | 0x00,  # display off
            SET_MEM_ADDR, 0x00,  # horizontal addressing mode
            SET_DISP_START_LINE | 0x00,
            SET_SEG_REMAP | 0x01,  # column addr 127 mapped to SEG0
            SET_MUX_RATIO, self.height - 1,
            SET_COM_OUT_DIR | 0x08,  # scan from COM[N] to COM0
            SET_DISP_OFFSET, 0x00,
            SET_COM_PIN_CFG, 0x02 if self.height == 32 else 0x12,
            SET_DISP_CLK_DIV, 0x80,
            SET_PRECHARGE, 0x22 if self.external_vcc else 0xF1,
            SET_VCOM_DESEL, 0x30,
            SET_CONTRAST, 0xFF,
            SET_ENTIRE_ON,
            SET_NORM_INV,
            SET_CHARGE_PUMP, 0x10 if self.external_vcc else 0x14,
            SET_DISP | 0x01,  # display on
        ):
            self.write_cmd(cmd)
        self.fill(0)
        self.show()

    def poweroff(self):
        """ディスプレイをオフ"""
        self.write_cmd(SET_DISP | 0x00)

    def poweron(self):
        """ディスプレイをオン"""
        self.write_cmd(SET_DISP | 0x01)

    def contrast(self, contrast):
        """コントラスト設定 (0-255)"""
        self.write_cmd(SET_CONTRAST)
        self.write_cmd(contrast)

    def invert(self, invert):
        """表示反転"""
        self.write_cmd(SET_NORM_INV | (invert & 1))

    def show(self):
        """バッファ内容を画面に表示"""
        x0 = 0
        x1 = self.width - 1
        if self.width == 64:
            x0 += 32
            x1 += 32
        self.write_cmd(SET_COL_ADDR)
        self.write_cmd(x0)
        self.write_cmd(x1)
        self.write_cmd(SET_PAGE_ADDR)
        self.write_cmd(0)
        self.write_cmd(self.pages - 1)
        self.write_data(self.buffer)


class SSD1306_I2C(SSD1306):
    """SSD1306 I2C接続クラス"""
    
    def __init__(self, width, height, i2c, addr=0x3C, external_vcc=False):
        self.i2c = i2c
        self.addr = addr
        self.temp = bytearray(2)
        super().__init__(width, height, external_vcc)

    def write_cmd(self, cmd):
        """コマンド送信"""
        self.temp[0] = 0x80  # Co=1, D/C#=0
        self.temp[1] = cmd
        self.i2c.writeto(self.addr, self.temp)

    def write_data(self, buf):
        """データ送信"""
        self.i2c.writeto(self.addr, b'\x40' + buf)


# ========================================
# テストプログラム
# ========================================

def test_display():
    """動作確認テスト"""
    print("OLED SSD1306 動作確認プログラム (MicroPython)")
    print("=" * 50)
    print(f"使用ピン: SDA=GPIO{SDA_PIN}, SCL=GPIO{SCL_PIN}")
    print(f"I2Cアドレス: {hex(I2C_ADDR)}")
    print("=" * 50)
    
    try:
        # I2C初期化 (内部プルアップ有効)
        print("\nI2C初期化中...")
        sda_pin = Pin(SDA_PIN, Pin.IN, Pin.PULL_UP)  # SDAピン + プルアップ
        scl_pin = Pin(SCL_PIN, Pin.IN, Pin.PULL_UP)  # SCLピン + プルアップ
        i2c = I2C(I2C_BUS, sda=sda_pin, scl=scl_pin, freq=I2C_FREQ)
        
        # I2Cデバイススキャン
        devices = i2c.scan()
        if devices:
            print(f"✓ I2Cデバイス検出: {[hex(d) for d in devices]}")
        else:
            print("✗ I2Cデバイスが見つかりません")
            print("配線を確認してください")
            return
        
        # OLEDディスプレイ初期化 (128x64)
        print("ディスプレイ初期化中...")
        oled = SSD1306_I2C(128, 64, i2c, addr=I2C_ADDR)
        print("✓ ディスプレイ初期化成功\n")
        
        # テスト1: テキスト表示
        print("テスト1: テキスト表示")
        oled.fill(0)
        oled.text("Hello OLED!", 0, 0)
        oled.text("SSD1306 Test", 0, 16)
        oled.text("MicroPython", 0, 32)
        oled.show()
        time.sleep(2)
        
        # テスト2: 図形描画
        print("テスト2: 図形描画")
        oled.fill(0)
        oled.rect(0, 0, 128, 64, 1)  # 外枠
        oled.fill_rect(10, 10, 40, 20, 1)  # 塗りつぶし矩形
        oled.ellipse(90, 32, 20, 15, 1)  # 楕円
        oled.line(0, 0, 127, 63, 1)  # 対角線
        oled.show()
        time.sleep(2)
        
        # テスト3: アニメーション
        print("テスト3: アニメーション")
        for i in range(0, 65, 2):
            oled.fill(0)
            oled.text("Moving...", i, 28)
            oled.show()
            time.sleep(0.05)
        
        # テスト4: カウンター
        print("テスト4: カウンター表示")
        for i in range(10):
            oled.fill(0)
            oled.text("Counter:", 20, 20)
            oled.text(str(i), 50, 35)
            oled.show()
            time.sleep(0.5)
        
        # テスト5: チェッカーパターン
        print("テスト5: チェッカーパターン")
        oled.fill(0)
        for x in range(0, 128, 8):
            for y in range(0, 64, 8):
                if (x // 8 + y // 8) % 2 == 0:
                    oled.fill_rect(x, y, 8, 8, 1)
        oled.show()
        time.sleep(2)
        
        # テスト6: プログレスバー
        print("テスト6: プログレスバー")
        for i in range(101):
            oled.fill(0)
            oled.text("Progress:", 20, 20)
            oled.rect(10, 35, 108, 12, 1)
            oled.fill_rect(12, 37, i, 8, 1)
            oled.text(f"{i}%", 50, 50)
            oled.show()
            time.sleep(0.03)
        
        # テスト7: スクロール
        print("テスト7: スクロール")
        oled.fill(0)
        oled.text("Scrolling", 20, 28)
        oled.show()
        time.sleep(1)
        for _ in range(10):
            oled.scroll(5, 0)
            oled.show()
            time.sleep(0.1)
        
        # 完了メッセージ
        oled.fill(0)
        oled.text("Test", 40, 20)
        oled.text("Complete!", 25, 35)
        oled.show()
        
        print("\n" + "=" * 50)
        print("✓ すべてのテスト完了")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n✗ エラー: {e}")
        print("\n確認事項:")
        print("1. 配線が正しいか (SDA, SCL, VCC, GND)")
        print("2. I2Cアドレスが0x3Cか")
        print("3. ピン番号が正しいか")
        print("4. プルアップ抵抗が適切か")


# メイン実行
if __name__ == "__main__":
    test_display()