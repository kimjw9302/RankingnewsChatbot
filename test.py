# -*- coding: utf-8 -*-
import json
import re
import requests
import urllib.request
import urllib.parse

from bs4 import BeautifulSoup
from flask import Flask, request
from slack import WebClient
from slack.web.classes import extract_json
from slack.web.classes.blocks import *
from slack.web.classes.elements import *
from slack.web.classes.interactions import MessageInteractiveEvent
from slackeventsapi import SlackEventAdapter


SLACK_TOKEN = ''
SLACK_SIGNING_SECRET = ''


app = Flask(__name__)
# /listening 으로 슬랙 이벤트를 받습니다.
slack_events_adaptor = SlackEventAdapter(SLACK_SIGNING_SECRET, "/listening", app)
slack_web_client = WebClient(token=SLACK_TOKEN)


# 키워드로 중고거래 사이트를 크롤링하여 가격대가 비슷한 상품을 찾은 다음,
# 메시지 블록을 만들어주는 함수입니다
def make_sale_message_blocks(keyword, price):
    # 주어진 키워드로 중고거래 사이트를 크롤링합니다
    query_text = urllib.parse.quote_plus(keyword, encoding="unicode-escape")
    query_text = query_text.replace("%5C", "%")
    search_url = "http://corners.auction.co.kr/corner/UsedMarketList.aspx?keyword=" + query_text
    print('Searching : ' + search_url)
    source_code = urllib.request.urlopen(search_url).read()
    soup = BeautifulSoup(source_code, "html.parser")

    # 페이지에서 각 매물의 정보를 추출합니다.
    items = []
    for item_div in soup.find_all("div", class_="list_view"):
        title = item_div.find("div", class_="item_title type1").get_text().strip()
        link = item_div.find("a")["href"]
        image = item_div.find("div", class_="image_info").find("a").find("img")["src"]
        item_price = item_div.find("div", class_="market_info").find("div", class_="present").find("span", class_="now").find("strong").get_text().strip()
        items.append({
            "title": title,
            "link": link,
            "image": image,
            "price": item_price,
        })

    for i, seller_div in enumerate(soup.find_all("div", class_="item_seller_info")):
        seller = seller_div.find("a").get_text().strip()
        items[i]["seller"] = seller

    # 각 매물을 원하는 가격에 가까운 순서대로 정렬합니다.
    items.sort(key=lambda item: abs(price - int(item["price"].replace(",", ""))))

    # 메시지를 꾸밉니다
    # 처음 섹션에는 제목과 첫 번째 상품의 사진을 넣습니다
    first_item_image = ImageElement(
        image_url=items[0]["image"],
        alt_text=keyword
    )
    head_section = SectionBlock(
        text="*\"" + keyword + "\", " + str(price) + "원으로 검색한 결과입니다.*",
        accessory=first_item_image
    )

    # 두 번째 섹션에는 처음 10개의 상품을 제목 링크/내용으로 넣습니다
    item_fields = []
    for item in items[:10]:
        # 첫 줄은 제목 링크, 두 번째 줄은 게시일과 가격을 표시합니다.
        text = "*<" + item["link"] + "|" + item["title"] + ">*"
        text += "\n" + str(item["price"]) + "원 / " + item["seller"]
        item_fields.append(text)
    link_section = SectionBlock(fields=item_fields)

    # 마지막 섹션에는 가격대를 바꾸는 버튼을 추가합니다
    # 여러 개의 버튼을 넣을 땐 ActionsBlock을 사용합니다 (버튼 5개까지 가능)
    button_actions = ActionsBlock(
        block_id=keyword,
        elements=[
            ButtonElement(
                text="1만원 올리기",
                action_id="price_up_1", value=str(price + 10000)
            ),
            ButtonElement(
                text="5만원 올리기", style="danger",
                action_id="price_up_5", value=str(price + 50000)
            ),
            ButtonElement(
                text="1만원 낮추기",
                action_id="price_down_1", value=str(price - 10000)
            ),
            ButtonElement(
                text="5만원 낮추기", style="primary",
                action_id="price_down_5", value=str(price - 50000)
            ),
        ]
    )

    # 각 섹션을 list로 묶어 전달합니다
    return [ button_actions]


# 챗봇이 멘션을 받으면 중고거래 사이트를 검색합니다
@slack_events_adaptor.on("app_mention")
def app_mentioned(event_data):
    channel = event_data["event"]["channel"]
    text = event_data["event"]["text"]

    # 입력한 텍스트에서 검색 키워드와 가격대를 뽑아냅니다.
    matches = re.search(r"<@U\w+>\s+(.+)\s+(\d+)원", text)
    if not matches:
        # 유저에게 사용법을 알려줍니다
        print(text)
        slack_web_client.chat_postMessage(
            channel=channel,
            text="사용하려면 `@중고거래봇 <키워드> 10000원`과 같이 멘션하세요"
        )
        return

    keyword = matches.group(1)
    price = int(matches.group(2))

    # 중고거래 사이트를 크롤링하여 가격대가 비슷한 상품을 찾아옵니다.
    message_blocks = make_sale_message_blocks(keyword, price)
    # print(message_blocks)
        # 메시지를 채널에 올립니다
    slack_web_client.chat_postMessage(
        channel=channel,
        blocks=extract_json(message_blocks)
    )


# 사용자가 버튼을 클릭한 결과는 /click 으로 받습니다
# 이 기능을 사용하려면 앱 설정 페이지의 "Interactive Components"에서
# /click 이 포함된 링크를 입력해야 합니다.
@app.route("/click", methods=["GET", "POST"])
def on_button_click():
    # 버튼 클릭은 SlackEventsApi에서 처리해주지 않으므로 직접 처리합니다
    payload = request.values["payload"]
    click_event = MessageInteractiveEvent(json.loads(payload))
    print(payload)
    keyword = click_event.block_id
    new_price = int(click_event.value)

    # 다른 가격대로 다시 크롤링합니다.
    message_blocks = make_sale_message_blocks(keyword, new_price)

    # 메시지를 채널에 올립니다
    slack_web_client.chat_postMessage(
        channel=click_event.channel.id,
        blocks=extract_json(message_blocks)
    )

    # Slack에게 클릭 이벤트를 확인했다고 알려줍니다
    return "OK", 200


# / 로 접속하면 서버가 준비되었다고 알려줍니다.
@app.route("/", methods=["GET"])
def index():
    return "<h1>Server is ready.</h1>"


if __name__ == '__main__':
    app.run('0.0.0.0', port=8080)
