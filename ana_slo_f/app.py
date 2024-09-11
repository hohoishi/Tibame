from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from bs4 import BeautifulSoup
import json
import requests
import configparser
import pandas as pd 
import re
import threading
from ana_slo import ana_slo 

app = Flask(__name__)

# Line Bot 相關資訊

config = configparser.ConfigParser()
config.read('config.ini')

line_bot_api = LineBotApi(config.get('line-bot', 'channel_access_token'))
handler = WebhookHandler(config.get('line-bot', 'channel_secret'))

@app.route("/callback", methods=['POST', 'GET'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'
    
#一個message event給使用者輸入 country ,brand, storename 去呼叫slot_data_top10 且回傳slot_data_top10結果
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text
    #如果符合xxxx,xxxx才執行
    pattern = r'^[^,]+,[^,]+$'
    if  re.match(pattern, user_message):
        country,store = user_message.split(',')

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=slot_data_top10(country,  store))
        )
    else: 
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='No data available! the format is <country,store>. Example:東京都,アミューズ浅草店 . or visit https://ana-slo.com/')
        )

def slot_data_top10(country, store):
    try:
    
        a = ana_slo(country, store)

        if a :
            data_list = a.get_slot_data_14()
            df_all = pd.pd.DataFrame(data_list, columns=a.columns_slot)


    #------------------------------------------------
            #用差枚總數排行
            df_all['差枚'] = df_all['差枚'].str.replace(',', '').str.replace('+', '').astype(int)
            top10_coins = df_all.groupby('台番号')['差枚'].sum().sort_values(ascending=False).head(10)
            df_all['win'] = df_all['差枚'].apply(lambda x: 1 if x > 0 else 0)
            #top10.index 篩選df_all['台號'] == top10.index
            df_top10_coins = df_all[df_all['台番号'].isin(top10_coins.index)]
            #計算top10的WIN RATE
            top10_coins_win_rate = df_top10_coins.groupby('台番号')['win'].mean().sort_values(ascending=False).head(10)
            df_final_coins = pd.merge(top10_coins, top10_coins_win_rate, on='台番号', how='left')
        
            return df_final_coins.to_string()
        else:

            return 'No data available, please visit https://ana-slo.com/ for correct format.'
    
    except Exception as e:
        print(e)
        return 'No data available, please visit https://ana-slo.com/ for correct format.'
        
if __name__ == '__main__':
    app.debug = True
    app.run()
