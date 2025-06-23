from flask import Flask, request, abort 
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import openai
import traceback
import os
import json
import random 
from datetime import datetime
from langchain.vectorstores import FAISS
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document 



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

def load_embedding_model():
    return HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-MiniLM-L3-v2")

# === STEP 2: 讀取 TXT 檔 並切割 ===
def load_static_document():
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    LARGE_TEXT = """
【戀愛式導買 AI － LINE 對話引導看房機器人】
第一章：團隊介紹
我們的團隊由兩大組成員構成：一組是具有十年以上經驗的房地產經紀人、施工預算師、地樓開發顧問，另一組則是預研較久的 AI 技術專家。我們經過幾個月合作實踐，以「性感、智慧、實用」為設計根基，將精添的情感導話、上手的 NLP 技術與專業房地產資訊完美融合，打造一個別於以往的 LINE 看房導買機器人。
第二章：目標客羣與痛點分析
我們所對應的目標客羣主要分為三類：
1. 想看房但怕被騙的中年或社會新人
2. 專業經紀有效導導的最絕好動力
3. 房地產中介公司希望給客戶提供更好的基礎服務
而他們的共同痛點，則包括：
* 販房騙婢盪有之不罵，人們對線上看房信任度低
* 傳統找房過程繁複且早已無法滿足現代人熱感式互動和速度需求
* 多數網站提供資訊分散，不易比較，於是總算退步
第三章：AI 技術應用關鍵
1. 情緒辨識 (Sentiment Analysis)：系統利用 NLP 分析用戶口氣、語氣與讚責種群，讓導話風格調整成更相合「他/她」依憑。
2. 導向式導話模型：這個模型不像一般的回答模型，它有「下一步」範定能力，能根據用戶現在狀態，推動成交，或是接綜資料，有力提升看房動漫與成效。
3. 文本分割 & 向量化技術：使用 FAISS 與 sentence-transformers 技術，將資料付給向量表示，方便我們在找房时比對經驗、匹配好房，盡可能轉換成功。
第四章：獨特競爭優勢
1. 戀愛式導話概念：採用「像跟女朋友說話」的語氣「給予感性與同理」的成分，打破傳統 bot 影像無氣、認真的驗練。
2. 專業的房地產分析技術：搭配我們團隊的房地產優勢，載入很多針對地區、產權、經驗內容，讓對話不再沒有底水，有能力提供專業指導。
第五章：預期效益
* 上線 3 個月內，看房預約率提高 40%
* 店面認識低的用戶，導話下單成功率增加個 3 倍
* 提供強化版的「認識驗證」，免費檢覽合法性資料，增強對店店之間的信任
第六章：使用情境範例
LINE 對話缺可見：
用戶：我想找東區的兩房一庫，最好有區域照。
AI：好喔～東區的總合型房庫最合適帶孩子同住，我首推新上市的 XX 工程房，要看圖嗎？
用戶：好喔
AI：圖片送上。頁幅下方有預約名額，需要幫你經紀列線嗎？
"""
    chunks = splitter.split_text(LARGE_TEXT)
    return [Document(page_content=chunk) for chunk in chunks]

# === STEP 4: 建立向量資料庫 ===
def create_vectorstore(chunks, embedding_model):
    return FAISS.from_documents(chunks, embedding_model)


# === STEP 5: 問答階段：查詢 FAISS 並餵給 GPT ===
def ask_gpt_with_context(query: str, vectorstore: FAISS) -> str:
    docs = vectorstore.similarity_search(query, k=3)
    context = "\n\n".join([doc.page_content for doc in docs])
    system_prompt = "你是一位專業知識助理，請根據下列內容回答問題："
    user_prompt = f"內容：\n{context}\n\n問題：{query}"
    
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.98,
        max_tokens=300,
    )
    return response["choices"][0]["message"]["content"].strip()





app = Flask(__name__)






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

@app.before_first_request
def build_vectorstore():
    global vectorstore
    if vectorstore is None:  # 確保只建一次
        print("🔍 載入資料與建立向量庫...")
        embeddings = load_embedding_model()
        print("🔍 讀取 TXT 檔 並切割...")
        docs = load_static_document()
        print("🔍 建立向量資料庫...") 
        vectorstore = FAISS.from_documents(docs, embeddings)




@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    global vectorstore
    user_input = event.message.text
    user_id = event.source.user_id

    if vectorstore is None:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="系統剛啟動，正在載入知識庫，請稍後幾秒再試 🙏")
        )
        return
    
    try:          
        # 所有訊息都用向量資料庫查找內容 + GPT 回答
        reply = ask_gpt_with_context(user_input, vectorstore)

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply)
        )

        print(f"[使用者 ID] {user_id}")
        print(f"[使用者提問] {user_input}")
        print(f"[AI 回答] {reply}")

    except Exception as e:
        print("⚠️ 錯誤發生：", e)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="抱歉～剛剛有點小狀況，哥哥可以再說一次嗎？")
        )



if __name__ == "__main__":
    print("[啟動] Flask App 執行中")
    app.run(host="0.0.0.0", port=5000)






