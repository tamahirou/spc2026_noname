from machine import Pin, PWM
from time import sleep

# GPIO16 を PWM 50Hz で初期化
servo = PWM(Pin(20))
servo.freq(50)

# 0〜180度に対応するデューティ比の範囲を設定
# （おおよそ 0.5ms〜2.4ms パルスに相当）
MIN_US = 500      # 0度付近
MAX_US = 2400     # 180度付近
PERIOD_US = 20000 # 50Hz -> 20ms

def angle_to_duty(angle):
    # 角度(0〜180)をパルス幅(μs)に変換
    us = MIN_US + (MAX_US - MIN_US) * angle / 180
    # サーボ用に 16bit デューティ（0〜65535）へ変換
    duty = int(us / PERIOD_US * 65535)
    return duty

def set_angle(angle):
    angle = max(0, min(180, angle))  # 範囲クリップ
    servo.duty_u16(angle_to_duty(angle))

# 動作確認：0→90→180→90→0度と動かす
while True:
    for a in (0, 90, 180, 90):
        set_angle(a)
        sleep(1)
