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
from mega import Mega
import requests





os.environ["TOKENIZERS_PARALLELISM"] = "false"


# GPT API Key 設定（openai 0.28.1 寫法）
openai.api_key = 'sk-kVraVp5JrS0q3DLd1202F329D8C943938cAfDa071f966b29'
openai.api_base = 'https://free.v36.cm/v1'  # 自訂 API server URL


# LINE 設定
CHANNEL_SECRET = '74630b154d9d0cf1823c5c32db2bcf4f'
CHANNEL_ACCESS_TOKEN = 'iqYgdqANm0V1UVbC+0jYZqXQNATimJvJRU+esv0RR5TlngqFDmytCT3aVyiyW3mj2BZBoRK6UYoAY8Y2D1L2iVizgzRwU3Q2QblOcdFlf58fK70AZIJ+TtCyb+zvjlwHcEn0TubFwY851pNcJVOEiwdB04t89/1O/w1cDnyilFU='


line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

vectorstore = None


def download_txt_from_url(url: str, filename: str = "text.txt"):
    print("🌐 從 URL 下載 text.txt...")
    response = requests.get(url)
    
    if response.status_code != 200:
        raise Exception(f"❌ 無法下載檔案，HTTP 狀態碼：{response.status_code}")
    
    content = response.text.strip()
    if not content:
        raise ValueError(f"❌ 下載內容為空")

    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"✅ 成功下載：{filename}")
    print(f"📄 檔案大小：{len(content)} 字元")
    print(f"📄 前100字內容：\n{content[:100]}")

    
def load_embedding_model():
    return HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-MiniLM-L3-v2")

# === STEP 2: 讀取 TXT 檔 並切割 ===
def load_txt_documents(filepath: str):
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_text(text)
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


MEGA_EMAIL = os.environ.get("MEGA_EMAIL")
MEGA_PASSWORD = os.environ.get("MEGA_PASSWORD")




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
        
        print("🔐 登入 MEGA 並下載 .txt 檔案...")
        download_txt_from_url("https://mega.nz/file/DUdCiA7R#wEzOXnZHiA0mio6owJ4fVqJWFxQHv0waCaPs2roE7ps")
        print("✅ 下載完成：text.txt")

        with open("text.txt", "r", encoding="utf-8") as f:
            content = f.read()
            print(f"📄 檔案大小：{len(content)} 字元")
            print(f"📄 前100字內容：\n{content[:100]}")

        
        # ✅ 這裡加入檢查
        if not os.path.exists("text.txt"):
             raise FileNotFoundError("text.txt 不存在")
        if os.stat("text.txt").st_size == 0:
            raise ValueError("text.txt 是空的")

        print("📄 讀取並處理 text.txt")
      
        print("🔍 載入資料與建立向量庫...")
        embeddings = load_embedding_model()
        print("🔍 讀取 TXT 檔 並切割...")
        docs = load_txt_documents("text.txt")
        print("🔍 建立向量資料庫...") 
        vectorstore = FAISS.from_documents(docs, embeddings)
        print("✅ 向量資料庫建立完成")


@app.route("/", methods=["GET"])
def index():
    global vectorstore
    if vectorstore is None:
        # 再次嘗試初始化（避免 before_first_request 失敗）
        try:
            build_vectorstore()
        except FileNotFoundError as e:
            return str(e), 404
        except ValueError as e:
            return str(e), 400
        except Exception as e:
            return f"❌ 初始化向量庫失敗：{e}", 500

    return "✅ 向量資料庫已建立完成並可使用", 200



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






