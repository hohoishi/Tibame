import requests
import json
from bs4 import BeautifulSoup
from threading import Thread

class ana_slo:

    def __init__(self, country, store):
        response = requests.get(f'https://ana-slo.com/ホールデータ/{country}/{store}-データ一覧/')
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('div' , id= 'table')

        #找到所有有 a 的日期
        a = table.find_all('a')
        a_list = []
        for date in a:
            a_list.append(date.text.strip()[:10].replace('/', '-'))
        self.a_list = a_list

        self.store = store 

        response = requests.get(f'https://ana-slo.com/{self.a_list[0]}-{store}-data/')
        soup = BeautifulSoup(response.text, 'html.parser')
        div = soup.find_all('div', id='all_data_block')
        if div:
            tr = div[0].find_all('tr')
            columns_slot = tr[0].text.strip().split('\n')
            columns_slot.append('DATE')
            self.columns_slot = columns_slot
        else: 
            print('Fail to get slot data')
        #['機種名', '台番号', 'G数', '差枚', 'BB', 'RB', '合成確率', 'BB確率', 'RB確率','DATE']

    def get_slot_data_14(self):  

        def _get_slot_data(date , store):
            nonlocal data_list

            response = requests.get(f'https://ana-slo.com/{date}-{store}-data/')
            soup = BeautifulSoup(response.text, 'html.parser')

            div = soup.find_all('div', id='all_data_block')
            tr = div[0].find_all('tr')
            columns_slot = tr[0].text.strip().split('\n')

            for td in tr[1:len(tr)]:
                data = td.text.strip().split('\n')
                if len(data)==len(columns_slot):
                    data.append(date)
                    data_list.append(data)

        data_list = []
        ths = [None] * len(self.a_list[:14])
        for i in range(len(self.a_list[:14])):
            ths[i] = Thread(target=_get_slot_data, args=(self.a_list[i],self.store ), daemon=True)
            ths[i].start()

        for i in range(len(self.a_list[:14])):
            ths[i].join()   
            
        return data_list