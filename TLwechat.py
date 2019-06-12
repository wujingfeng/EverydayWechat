# coding=utf8
"""
①每天定时给多个女友发给微信暖心话
②借助图灵实现自动回复. 避免长时间不回复女友,家庭暴力很危险呀
"""
import os
import random
import time
from datetime import datetime
import itchat
import requests
import yaml
from bs4 import BeautifulSoup
from simplejson import JSONDecodeError

import CityDict as city_dict
from apscheduler.schedulers.background import BackgroundScheduler

# fire the job again if it was missed within GRACE_PERIOD
GRACE_PERIOD = 15 * 60


class info:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/67.0.3396.87 Safari/537.36',
    }
    dictum_channel_name = {1: 'ONE●一个', 2: '词霸(每日英语)', 3: '土味情话'}

    def __init__(self):
        self.girlfriend_list, self.alarm_hour, self.alarm_minute, self.dictum_channel, self.tuling_key, self.auto_reply_list, self.open_reply_limit = self.get_init_data()

    def get_init_data(self):
        """
        初始化基础数据。
        :return: (dict,int,int,int)
            1.dict 需要发送的用户的信息；
            2.int 时；
            3.int 分；
            4.int 格言渠道。（1: 'ONE●一个', 2: '词霸(每日英语)', 3: '土味情话'）
        """
        itchat.auto_login(hotReload=True)
        with open('_config.yaml', 'r', encoding='utf-8') as file:
            config = yaml.load(file, Loader=yaml.Loader)

        alarm_timed = config.get('alarm_timed').strip()
        init_msg = '每天定时发送时间：{}\n'.format(alarm_timed)

        dictum_channel = config.get('dictum_channel', -1)
        init_msg += '格言获取渠道：{}\n'.format(self.dictum_channel_name.get(dictum_channel, '无'))

        tuling_key = config.get('tuling_key')

        auto_reply_list = config.get('auto_reply_list')

        open_reply_limit = config.get('open_reply_limit')

        girlfriend_list = []
        girlfriend_infos = config.get('girlfriend_infos')
        for girlfriend in girlfriend_infos:
            girlfriend.get('wechat_name').strip()
            # 根据城市名称获取城市编号，用于查询天气。查看支持的城市为：http://cdn.sojson.com/_city.json
            city_name = girlfriend.get('city_name').strip()
            city_code = city_dict.CityDict.city_dict.get(city_name)
            if not city_code:
                print('您输入的城市无法收取到天气信息。')
                break
            girlfriend['city_code'] = city_code
            girlfriend_list.append(girlfriend)
            print_msg = (
                '女朋友的微信昵称：{wechat_name}\n\t女友所在城市名称：{city_name}\n\t'
                '在一起的第一天日期：{start_date}\n\t最后一句为：{sweet_words}\n'.format(**girlfriend))
            init_msg += print_msg

        print('*' * 50)
        # print(init_msg)

        hour, minute = [int(x) for x in alarm_timed.split(':')]
        return girlfriend_list, hour, minute, dictum_channel, tuling_key, auto_reply_list, open_reply_limit

    def get_ciba_info(self):
        """
        从词霸中获取每日一句，带英文。
        :return:str ,返回每日一句（双语）
        """
        print('获取格言信息（双语）...')
        resp = requests.get('http://open.iciba.com/dsapi')
        if resp.status_code == 200 and self.is_json(resp):
            content_dict = resp.json()
            content = content_dict.get('content')
            note = content_dict.get('note')
            return '{}\n{}\n'.format(content, note)

        print('没有获取到数据。')
        return None

    @staticmethod
    def is_json(data):
        """
        判断数据是否能被 Json 化。 True 能，False 否。
        :param resp: request.
        :return: bool, True 数据可 Json 化；False 不能 JOSN 化。
        """
        try:
            data.json()
            return True
        except JSONDecodeError:
            return False

    def get_dictum_info(self):
        """
        获取格言信息（从『一个。one』获取信息 http://wufazhuce.com/）
        :return: str， 一句格言或者短语。
        """
        print('获取格言信息...')
        user_url = 'http://wufazhuce.com/'
        resp = requests.get(user_url, headers=self.headers)
        if resp.status_code == 200:
            soup_texts = BeautifulSoup(resp.text, 'lxml')
            # 『one -个』 中的每日一句
            every_msg = soup_texts.find_all('div', class_='fp-one-cita')[0].find('a').text
            return every_msg + '\n'
        print('每日一句获取失败。')
        return None

    def get_lovelive_info(self):
        """
        从土味情话中获取每日一句。
        :return: str,土味情话。
        """
        print('获取土味情话...')
        resp = requests.get('https://api.lovelive.tools/api/SweetNothings')
        if resp.status_code == 200:
            return resp.text + '\n'

        print('土味情话获取失败。')
        return None

    def get_weather_info(self, dictum_msg, city_code, start_date, sweet_words):
        """
        获取天气信息。网址：https://www.sojson.com/blog/305.html .
        :param dictum_msg: str,发送给朋友的信息。
        :param city_code: str,城市对应编码。如：101030100
        :param start_date: str,恋爱第一天日期。如：2018-01-01
        :param sweet_words: str,来自谁的留言。如：来自你的朋友
        :return: str,需要发送的话。
        """
        print('获取天气信息...')
        weather_url = 'http://t.weather.sojson.com/api/weather/city/{}'.format(city_code)
        resp = requests.get(url=weather_url)
        if resp.status_code == 200 and self.is_json(resp) and resp.json().get('status') == 200:
            weather_dict = resp.json()
            # 今日天气
            today_weather = weather_dict.get('data').get('forecast')[1]
            # 今日日期
            today_time = (datetime.now().strftime('%Y{y}%m{m}%d{d} %H:%M:%S')
                          .format(y='年', m='月', d='日'))
            # 今日天气注意事项
            notice = today_weather.get('notice')
            # 温度
            high = today_weather.get('high')
            high_c = high[high.find(' ') + 1:]
            low = today_weather.get('low')
            low_c = low[low.find(' ') + 1:]
            temperature = '温度 : {}/{}'.format(low_c, high_c)

            # 风
            wind_direction = today_weather.get('fx')
            wind_level = today_weather.get('fl')
            wind = '{} : {}'.format(wind_direction, wind_level)

            # 空气指数
            aqi = today_weather.get('aqi')
            aqi = '空气 : {}'.format(aqi)

            # 在一起，一共多少天了，如果没有设置初始日期，则不用处理
            if start_date:
                try:
                    start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
                    day_delta = (datetime.now() - start_datetime).days
                    delta_msg = '宝贝这是我们在一起的第 {} 天。\n'.format(day_delta)
                except ValueError:
                    delta_msg = ''
            else:
                delta_msg = ''

            today_msg = (
                '{today_time}\n{delta_msg}{notice}。\n{temperature}\n'
                '{wind}\n{aqi}\n{dictum_msg}{sweet_words}\n'.format(
                    today_time=today_time, delta_msg=delta_msg, notice=notice,
                    temperature=temperature, wind=wind, aqi=aqi,
                    dictum_msg=dictum_msg, sweet_words=sweet_words if sweet_words else ""))
            return today_msg

    def _online(self):
        """
        通过获取好友信息，判断用户是否还在线。
        :return: bool,当返回为 True 时，在线；False 已断开连接。
        """
        try:
            if itchat.search_friends():
                return True
        except IndexError:
            return False
        return True

    def is_online(self, auto_login=False):
        """
        判断是否还在线。
        :param auto_login: bool,如果掉线了则自动登录(默认为 False)。
        :return: bool,当返回为 True 时，在线；False 已断开连接。
        """

        if self._online():
            return True
        # 仅仅判断是否在线。
        if not auto_login:
            return self._online()

        # 登陆，尝试 5 次。
        for _ in range(5):
            # 命令行显示登录二维码。
            if os.environ.get('MODE') == 'server':
                itchat.auto_login(enableCmdQR=2, hotReload=True)
            else:
                itchat.auto_login(hotReload=True)
            if self._online():
                print('登录成功')
                return True

        print('登录成功')
        return False

    def start_today_info(self, is_test=False):
        """
        每日定时开始处理。
        :param is_test:bool, 测试标志，当为True时，不发送微信信息，仅仅获取数据。
        :return: None.
        """
        print('*' * 50)
        print('获取相关信息...')

        if self.dictum_channel == 1:
            dictum_msg = self.get_dictum_info()
        elif self.dictum_channel == 2:
            dictum_msg = self.get_ciba_info()
        elif self.dictum_channel == 3:
            dictum_msg = self.get_lovelive_info()
        else:
            dictum_msg = ''

        for girlfriend in self.girlfriend_list:
            city_code = girlfriend.get('city_code')
            start_date = girlfriend.get('start_date').strip()
            sweet_words = girlfriend.get('sweet_words')
            today_msg = self.get_weather_info(
                dictum_msg, city_code=city_code, start_date=start_date, sweet_words=sweet_words)
            wechat_name = girlfriend.get('wechat_name')
            UserName = itchat.search_friends(wechat_name)
            if UserName:
                UserName = UserName[0]['UserName']
            else:
                UserName = 'filehelper'
            print('给『{}』发送的内容是:\n{}'.format(wechat_name, today_msg))

            if not is_test:
                if self.is_online(auto_login=True):
                    itchat.send(today_msg, toUserName=UserName)
                # 防止信息发送过快。
            time.sleep(5)

        print('发送成功...\n')

    def addTimer(self):

        # 定时任务
        scheduler = BackgroundScheduler()
        # 每天9：30左右给女朋友发送每日一句
        scheduler.add_job(self.start_today_info, 'cron', hour=self.alarm_hour,
                          minute=self.alarm_minute, misfire_grace_time=GRACE_PERIOD)
        # 每隔 2 分钟发送一条数据用于测试。
        # scheduler.add_job(self.start_today_info, 'interval', seconds=120)
        scheduler.start()


def get_response(msg):
    # 这里我们就像在“3. 实现最简单的与图灵机器人的交互”中做的一样
    # 构造了要发送给服务器的数据
    apiUrl = 'http://www.tuling123.com/openapi/api'

    key_length = len(info().tuling_key)-1
    try:
        num = 0
        while (num < 5):
            num += 1
            data = {
                'key': info().tuling_key[random.randint(0, key_length)],
                'info': msg,
                'userid': '460281',
            }
            r = requests.post(apiUrl, data=data).json()
            # 如果没有请求次数了,则重新请求
            if r['code'] == 40004:
                continue
            else:
                return r.get('text')


    # 为了防止服务器没有正常响应导致程序异常退出，这里用try-except捕获了异常
    # 如果服务器没能正常交互（返回非json或无法连接），那么就会进入下面的return
    except:
        # 将会返回一个None
        return


# 这里是我们在“1. 实现微信消息的获取”中已经用到过的同样的注册方法
@itchat.msg_register(itchat.content.TEXT)
def tuling_reply(msg):
    # 为了保证在图灵Key出现问题的时候仍旧可以回复，这里设置一个默认回复
    defaultReply = 'I received: ' + msg['Text']
    # 如果图灵Key出现问题，那么reply将会是None
    reply = get_response(msg['Text'])
    # a or b的意思是，如果a有内容，那么返回a，否则返回b
    # 有内容一般就是指非空或者非None，你可以用`if a: print('True')`来测试
    if info().open_reply_limit == 1:
        if msg['User']['NickName'] in info().auto_reply_list:
            return reply or defaultReply
        else:
            return
    else:
        return reply or defaultReply


# 为了让实验过程更加方便（修改程序不用多次扫码），我们使用热启动
# if __name__ == '__main__':

itchat.auto_login(hotReload=True)
info().addTimer()
itchat.run()
