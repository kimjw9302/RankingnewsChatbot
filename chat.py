# -*- coding: utf-8 -*-
import re
import urllib.request
import datetime
import json
from builtins import print

import requests
import urllib.request

from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from flask import Flask, request
from slack import WebClient
from slackeventsapi import SlackEventAdapter
from slack.web.classes import extract_json
from slack.web.classes.blocks import *
from slack.web.classes.elements import *
from slack.web.classes.interactions import MessageInteractiveEvent

# SLACK_TOKEN = 'xoxb-689115425012-693172739702-pE4sboLggcIl0b2ZBIUoKvVk'
# SLACK_SIGNING_SECRET = '92c406c764a91c9b14fb8d8a4af632b8'
SLACK_TOKEN = 'xoxb-689115425012-689247336836-CkOHnlZceaugc0CpKwOk21xb'
SLACK_SIGNING_SECRET = 'f7bca5b219e2b338afe9680b4f8438e8'

# MATCHING 섹션별 매칭 코드
MATCHING = {"정치": 100, "경제": 101,"사회":102,"문화":103,"세계":104,"IT":105,
            "10대":10 ,"20대":20,"30대":30,"40대":40,"50대":50,"60대":60 ,"오늘" : 0, "어제" :-1}
ERROR_STRING = ["올바른 URL을 입력하세요"]
app = Flask(__name__)

# /listening 으로 슬랙 이벤트를 받습니다.
slack_events_adaptor = SlackEventAdapter(SLACK_SIGNING_SECRET, "/listening", app)
slack_web_client = WebClient(token=SLACK_TOKEN)


# url매칭 확인 함수
def _is_url_matching(url):
    return re.search(r'(https?://\S+)', url.split('|')[0]).group(0)


# 정치 크롤링 함수
def _politics(cate,date):
    # 정보를 담을 딕셔너리 생성
    dics = []
    num = MATCHING[cate]
    url = "https://news.naver.com/main/ranking/popularDay.nhn?rankingType=popular_day&sectionId={}&date={}".format(
        num,date)
    print("요청 URL : " , url)
    block_sections = []
    # ======매칭에러 시 종료=======
    if not _is_url_matching(url):
        return ERROR_STRING[0]

    source_code = urllib.request.urlopen(url)
    soup = BeautifulSoup(source_code, "html.parser")

    # 한번에 받아와서 데이터 가공하기.
    contents = soup.find("div", class_="content")
    for i in range(1, 6):
        nameOfclass = "ranking_item is_num{}".format(i)
        dic = {}
        dic["rank"] = str(i)
        for li in contents.find_all("li", class_=nameOfclass):
            ranking_thumb = li.find("div", class_="ranking_thumb")
            if ranking_thumb == None:
                dic["thumbs"] = "http://assets.lateral.io/newsbot-bot.png"
            else:
                dic["thumbs"] = ranking_thumb.find('img').get('src')

            ranking_header = li.find("div", class_="ranking_headline")
            #헤드라인 같은 경우-> 다시 크롤링
            dic["url"] = "https://news.naver.com" + ranking_header.find("a")['href']

            headsource_code = urllib.request.urlopen(dic["url"])
            head_soup = BeautifulSoup(headsource_code,"html.parser")
            head = head_soup.find("h3",id="articleTitle").get_text()

            dic['head'] = head

            dics.append(dic)

    gisa = []
    images = []
    #========블록 초기화==================
    message_blocks = [{"type":"divider"}]
    for i,dic in enumerate(dics):
        string = "*[" + dic["rank"] + "위]*\n\n<" + dic["url"] +"|"+dic["head"]+ ">"
        images.append(ImageElement(
            image_url=dic["thumbs"],
            alt_text = "image"
        ))
        message_blocks.append(SectionBlock(
            text = string,
            accessory = images[i]
        ))
        gisa.append(string)

    #========버튼액션 초기화 ===============
    new_date = datetime.strptime(date,'%Y%m%d')

    yesterday = new_date -timedelta(days=1)
    # print(yesterday.strftime("%Y%m%d"))
    new_yesterday = yesterday.strftime("%Y%m%d")

    tommorow = new_date+timedelta(days=1)
    now = int(datetime.now().strftime("%Y%m%d"))
    new_tommorow = int(tommorow.strftime("%Y%m%d"))
    # print(str(int(new_date.strftime("%Y%m%d"))) +"// " +str(now))
    if int(new_date.strftime("%Y%m%d")) == now:
        button_actions = ActionsBlock(
            block_id=cate,
            elements=[
                ButtonElement(
                    text="전날 뉴스",
                    action_id="yesterday", value=new_yesterday
                ),
            ]
        )
    else:
        button_actions = ActionsBlock(
            block_id=cate,
            elements=[
                ButtonElement(
                    text="전날 뉴스",
                    action_id="yesterday", value=new_yesterday
                ),
                ButtonElement(
                    text="다음날 뉴스",
                    action_id="tommorow", value=str(new_tommorow)
                ),
            ]
        )
    # print("요청날짜 : " + str(new_tommorow))
    message_blocks.append(button_actions)

    return message_blocks

# 연령대 크롤링 함수
def _ageNews(age):

    search_url = 'https://news.naver.com/main/ranking/popularDay.nhn?rankingType=age&subType={}'.format(age.replace("대", ""))
    print("요청 URL :" + search_url)
    source_code = urllib.request.urlopen(search_url).read()
    soup = BeautifulSoup(source_code, "html.parser")
    informs = []
    informs_div = soup.find("ol", class_="ranking_list")
    rank = 0
    for i in range(1, 6):
        for informs_div2 in informs_div.find_all("li", class_="ranking_item is_num{}".format(str(i))):
            rank += 1
            link = 'https://news.naver.com' + informs_div2.find("a")["href"]
            headsource_code = urllib.request.urlopen(link)
            head_soup = BeautifulSoup(headsource_code, "html.parser")
            head = head_soup.find("h3", id="articleTitle").get_text()
            # dic["thumbs"] = "http://assets.lateral.io/newsbot-bot.png"
            ranking_thumb = informs_div2.find("div", class_="ranking_thumb")
            image = ''
            # ranking_thumb.find('img').get('src')
            if ranking_thumb == None:
                image = "http://assets.lateral.io/newsbot-bot.png"
            else:
                image = ranking_thumb.find("img").get("src")
            informs.append({
                "rank": rank,
                "title": head,
                "link": link,
                "image": image,
            })
    inform_filed = []
    message_blocks = [{"type": "divider"}]
    for i, inform in enumerate(informs):
        string = "*[" + str(inform["rank"]) + "위]*\n<" + inform["link"] + "|" + inform["title"] + ">*"
        inform_filed.append(ImageElement(
            image_url=inform["image"],
            alt_text="image"
        ))
        message_blocks.append(SectionBlock(
            text=string,
            accessory=inform_filed[i]
        ))

    return message_blocks

# 크롤링 함수 구현하기
def _crawl(text):
    text = text.split(' ')
    # 연령대별은 연령대
    # 섹션은 날짜, 카테고리
    if text[1] in MATCHING:
        return _ageNews(text[1])
    num = 0

    if not text[2] in MATCHING:
        return "카테고리를 제대로 입력해주세요."
    # gisa.append(_politics(num))


    return _politics(text[2],text[1])

@app.route("/click", methods=["GET", "POST"])
def on_button_click():
    # 버튼 클릭은 SlackEventsApi에서 처리해주지 않으므로 직접 처리합니다
    payload = request.values["payload"]

    click_event = MessageInteractiveEvent(json.loads(payload))

    cate = click_event.block_id
    new_date = click_event.value

    # 전날로 다시 크롤링합니다.
    message_blocks = _politics(cate, new_date)

    slack_web_client.chat_postMessage(
        channel=click_event.channel.id,
        text= "요청한 " + new_date+ " *" + cate + "* 뉴스입니다.\n"
        )
    # 메시지를 채널에 올립니다
    slack_web_client.chat_postMessage(
        channel=click_event.channel.id,
        blocks=extract_json(message_blocks)
    )

    # Slack에게 클릭 이벤트를 확인했다고 알려줍니다
    return "OK", 200

# 챗봇이 멘션을 받았을 경우
@slack_events_adaptor.on("app_mention")
def app_mentioned(event_data):
    channel = event_data["event"]["channel"]
    text = event_data["event"]["text"]
    user_id = event_data["event"]["user"]
    # 연령대별은 연령대
    # 섹션은 날짜, 카테고리 검색 조건 설정
    text_matach = text.split(" ")
    message_blocks = []
    if text_matach[1] in MATCHING and not text_matach[1] == "오늘" and not text_matach[1] == "어제":
        print("pass")
        slack_web_client.chat_postMessage(
            channel=channel,
            text="요청한  *" + text_matach[1] + "* 뉴스입니다.\n"
        )
    else:
        if len(text_matach) <= 2 :
            slack_web_client.chat_postMessage(
                channel=channel,
                text="`@<봇이름> YYYYmmdd(오늘까지) 카테고리(정치,시사,IT,세계,사회문화)`와 같이 멘션해주세요\n 혹은 `@<봇이름> 연령대(10대,20대,30대,40대,50대,60대)` 와 같이 멘션해주세요"
            )
            return 0
        if not text_matach[2] in MATCHING:
            slack_web_client.chat_postMessage(
                channel=channel,
                text="`@<봇이름> YYYYmmdd(오늘까지) 카테고리(정치,시사,IT,세계,사회문화)`와 같이 멘션해주세요\n 혹은 `@<봇이름> 연령대(10대,20대,30대,40대,50대,60대)` 와 같이 멘션해주세요"
            )
            return 0
        else:
            if text_matach[1] == "오늘":
                text_matach[1] = datetime.now().strftime("%Y%m%d")
                text =text.replace('오늘',text_matach[1])
            elif text_matach[1] == "어제":
                text_matach[1] = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
                text = text.replace('어제', text_matach[1])
            print(text)
            now = int(datetime.now().strftime("%Y%m%d"))
            new_date = datetime.strptime(text_matach[1], '%Y%m%d')

            if int(new_date.strftime("%Y%m%d")) > now:
                    slack_web_client.chat_postMessage(
                        channel=channel,
                        text="`@<봇이름> YYYYmmdd(오늘까지) 카테고리(정치,시사,IT,세계,사회문화)`와 같이 멘션해주세요\n 혹은 `@<봇이름> 연령대(10대,20대,30대,40대,50대,60대)` 와 같이 멘션해주세요"
                    )
                    return 0
            slack_web_client.chat_postMessage(
                channel=channel,
                text="요청한 " + text.split(" ")[1] + " *" + text.split(" ")[2] + "* 뉴스입니다.\n"
            )

    message = _crawl(text)


    slack_web_client.chat_postMessage(
            channel=channel,
            blocks=extract_json(message)
        )

    return 0

# / 로 접속하면 서버가 준비되었다고 알려줍니다.
@app.route("/", methods=["GET"])
def index():
    return "<h1>Server is ready.</h1>"

if __name__ == '__main__':
    # _crawl('politic')
    app.run('0.0.0.0', port=8080)