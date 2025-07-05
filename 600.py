from flask import Flask, request, abort 
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from linebot.models import FlexSendMessage
import openai
import os
import json
import random 
from datetime import datetime
import os
import psutil
import threading
import time
import PyPDF2

os.environ["TOKENIZERS_PARALLELISM"] = "false"


# GPT API Key 設定（openai 0.28.1 寫法）
openai.api_key = 'sk-Y6eY0OQ0ffzNHRow3639F5C9E29e4c4a9fEb9d6545DaC944'
openai.api_base = 'https://free.v36.cm/v1'  # 自訂 API server URL


# LINE 設定
CHANNEL_SECRET = 'd61f3ddbed2bca885f904047a010dafe'
CHANNEL_ACCESS_TOKEN = 'BmwXbOvc7uqDhjRxRC5MmaF9XH0QuMk+sXKL5Dp8yTqqFLCoq7nRNjj4TVt0mZSs2BZBoRK6UYoAY8Y2D1L2iVizgzRwU3Q2QblOcdFlf5/d61RLlvcB66gGoyqRQxvLw1KCwLF+/WNVioFp5IQ9SgdB04t89/1O/w1cDnyilFU='


line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

vectorstore = None





def log_memory_usage():
    process = psutil.Process(os.getpid())
    while True:
        mem = process.memory_info().rss / 1024 / 1024  # 轉為 MB
        print(f"[Memory Monitor] RAM 使用中: {mem:.2f} MB")
        time.sleep(10)  # 每 10 秒印一次


def load_pdf_to_chunks(pdf_path, chunk_size=2000):
    text = ""

    # 讀取 PDF 所有頁面
    with open(pdf_path, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        for page in reader.pages:
            text += page.extract_text()

    # 清理文字
    text = text.replace("\n", " ").strip()

    # 分段
    chunks = []
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i+chunk_size]
        chunks.append(f"第{i//chunk_size + 1}段：\n{chunk}")

    print(f"[PDF 載入] 成功切成 {len(chunks)} 段")
    return chunks



# === STEP 5: 問答階段：查詢 FAISS 並餵給 GPT ===
def handle_unknown_question(user_input):
    # Step 1: 判斷是否為房地產領域
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "你是一個專業的分類模型。請判斷以下問題是否與『不動產／仲介／買賣／租賃／房屋』相關，只需回答『是』或『否』。"},
            {"role": "user", "content": f"問題：{user_input}"}
        ],
        temperature=0
    )

    classification = response["choices"][0]["message"]["content"].strip().lower()

    if "是" in classification:
        return (
            "您好，感謝您的提問！為了幫助您更進一步，您可以嘗試：\n"
            "1. 提供更多背景或細節，讓我們更精準理解您的需求。\n"
            "2. 掃描下方 LINE QR Code 尋求我們專業領域的房仲來協助您更完整的諮詢解答。"
        )
    else:
        # Step 2: 試著讓 GPT 自己回答（不是房地產類但可能能回答）
        fallback = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "你是一位知識豐富且樂於助人的助理，請用親切的語氣回答以下問題，如果仍然不知道也請誠實說明。"},
                {"role": "user", "content": user_input}
            ],
            temperature=0.7,
            max_tokens=300
        )
        return fallback["choices"][0]["message"]["content"].strip()

def setup_rich_menu_for_user(user_id):
    """設定 Rich Menu 給特定用戶"""
    try:
        # Rich Menu 設定
        rich_menu_to_create = {
            "size": {
                "width": 2500,
                "height": 1686
            },
            "selected": True,
            "name": "Knowledge Base Menu",
            "chatBarText": "知識庫選單",
            "areas": [
                {
                    "bounds": {
                        "x": 0,
                        "y": 0,
                        "width": 2500,
                        "height": 1686
                    },
                    "action": {
                        "type": "uri",
                        "uri": f"https://line-knowledge.vercel.app/?user_id={user_id}"
                    }
                }
            ]
        }
        
        # 創建 Rich Menu
        rich_menu_id = line_bot_api.create_rich_menu(rich_menu_to_create)
        
        # 設定 Rich Menu 圖片 (需要準備一張 2500x1686 的圖片)
        # with open('rich_menu_image.png', 'rb') as f:
        #     line_bot_api.set_rich_menu_image(rich_menu_id, 'image/png', f)
        
        # 將 Rich Menu 綁定到用戶
        line_bot_api.link_rich_menu_to_user(user_id, rich_menu_id)
        
        print(f"Rich Menu 設定成功，用戶 ID: {user_id}")
        
    except Exception as e:
        print(f"設定 Rich Menu 失敗: {e}")


def ask_question_over_chunks(query: str, knowledge_chunks: list) -> str:
    """
    從資料庫段落中逐段查詢答案，
    找到非「不知道」的答案就回傳，
    否則回傳「不知道」。
    """
    system_prompt = "你是一位資料助理，請根據『內容』回答問題。若資料中找不到答案，請只回答：不知道。"
    
    for i, chunk in enumerate(knowledge_chunks):
        user_prompt = f"內容：{chunk}\n\n問題：{query}"
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0,
                max_tokens=300,
            )
            answer = response["choices"][0]["message"]["content"].strip()
            if "不知道" not in answer:
                return f"[來自第{i+1}段]：{answer}"
        except Exception as e:
            print(f"第 {i+1} 段查詢失敗：{e}")

    return "不知道"










app = Flask(__name__)


threading.Thread(target=log_memory_usage, daemon=True).start()

knowledge_chunks = load_pdf_to_chunks("00.pdf")

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    print(f"[Webhook 接收到訊息] Body:\n{body}")  # 印出訊息內容以確認

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("[簽章錯誤] Signature 無效")
        abort(400)

    return 'OK'






@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):

    user_input = event.message.text
    user_id = event.source.user_id

    if user_input.lower() == "設定選單" or user_input.lower() == "menu":
        setup_rich_menu_for_user(user_id)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="Rich Menu 已設定完成！請查看下方選單。")
        )
        return




    try:          
        # 所有訊息都用向量資料庫查找內容 + GPT 回答

        line_bot_api.get_rich_menu_id_of_user(user_id)
        
        if user_input.strip() == "看網頁":
            bubble = {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": "點我打開網頁",
                            "weight": "bold",
                            "size": "lg",
                            "margin": "md"
                        },
                        {
                            "type": "button",
                            "style": "primary",
                            "action": {
                                "type": "uri",
                                "label": "前往網頁",
                                "uri": "https://你的domain/web"  # 例：https://abc.onrender.com/web
                            },
                            "margin": "md"
                        }
                    ]
                }
            }

            line_bot_api.reply_message(
                event.reply_token,
                FlexSendMessage(alt_text="點我看網頁", contents=bubble)
            )
            return  # 不繼續往下執行
    
        reply = ask_question_over_chunks(user_input, knowledge_chunks)
        
        if reply.strip() == "不知道":
            reply = handle_unknown_question(user_input)

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply)
        )

        print(f"[使用者 ID] {user_id}")
        print(f"[使用者提問] {user_input}")
        print(f"[AI 回答] {reply}")

    except Exception as e:
        setup_rich_menu_for_user(user_id)
        print("⚠️ 錯誤發生：", e)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="抱歉～剛剛有點小狀況，哥哥可以再說一次嗎？")
        )



if __name__ == "__main__":
    print("[啟動] Flask App 執行中")
    app.run(host="0.0.0.0", port=5000)






