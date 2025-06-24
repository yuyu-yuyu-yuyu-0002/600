from flask import Flask, request, abort 
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import openai
import os
import json
import random 
from datetime import datetime


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



knowledge_chunks = [
    "戀愛式導購 AI ― LINE 對話引導看房機器⼈
1. 團隊介紹
我們的團隊由具有豐富房地產經驗的專業房仲和頂尖的AI技術專家組成。團隊中包含多名擁有⼈⼯智慧
與⾃然語⾔處理（NLP）背景的技術⼈員，致⼒於將先進的AI技術應⽤於房地產⾏業，提供創新⽽有效
的解決⽅案。
2. ⽬標客群與痛點
⽬標客群
潛在買家和租客
房地產中介公司
痛點
防詐騙需求：線上看房詐騙事件頻發，消費者信任度低。
導購轉換低：傳統房地產導購⽅式難以吸引和轉化顧客。
3. AI 技術運⽤
情緒偵測 NLP
利⽤⾃然語⾔處理技術，分析⽤⼾情緒，提供個性化的看房建議。
對話引導模型
智能對話系統能夠模擬真⼈互動，引導⽤⼾進⾏下⼀步操作，增加參與度。
4. 獨特競爭優勢
戀愛話術：將戀愛話術融⼊對話，引發⽤⼾情感共鳴。
房地產導購融合：結合專業房地產知識，提供精準的看房建議。
5. 預期效益
提⾼預約看房率：通過智能引導提⾼看房預約的轉化率。
降低詐騙⾵險：加強⽤⼾識別與信任，減少詐騙事件。
6. 使⽤情境展⽰
模擬LINE對話界⾯，展⽰AI如何與⽤⼾進⾏互動，引導其看房決策。
7. 商業模式與擴展性
SaaS模式：提供軟體即服務，讓更多房地產公司輕鬆接⼊。
房仲系統API整合：與現有房仲系統無縫整合，提⾼操作效率。
8. 社會影響與落地價值
提升信任與安全：建⽴更安全的線上看房環境，增強⽤⼾信任。
促進房地產市場健康發展：通過技術創新，推動整個⾏業的進步。
9. 結語與呼籲⽀持
戀愛式導購 AI 將成為房地產⾏業的變⾰⼒量。我們誠邀各界⽀持與合作，共同推動這⼀創新技術的落
地與普及。讓我們攜⼿創造更智能、更安全的看房體驗。"
    ,
    "第三段資料：戀愛式導購 AI ― LINE 對話引導看房機器⼈
1. 團隊介紹
我們的團隊由具有豐富房地產經驗的專業房仲和頂尖的AI技術專家組成。團隊中包含多名擁有⼈⼯智慧
與⾃然語⾔處理（NLP）背景的技術⼈員，致⼒於將先進的AI技術應⽤於房地產⾏業，提供創新⽽有效
的解決⽅案。
2. ⽬標客群與痛點
⽬標客群
潛在買家和租客
房地產中介公司
痛點
防詐騙需求：線上看房詐騙事件頻發，消費者信任度低。
導購轉換低：傳統房地產導購⽅式難以吸引和轉化顧客。
3. AI 技術運⽤
情緒偵測 NLP
利⽤⾃然語⾔處理技術，分析⽤⼾情緒，提供個性化的看房建議。
對話引導模型
智能對話系統能夠模擬真⼈互動，引導⽤⼾進⾏下⼀步操作，增加參與度。
4. 獨特競爭優勢
戀愛話術：將戀愛話術融⼊對話，引發⽤⼾情感共鳴。
房地產導購融合：結合專業房地產知識，提供精準的看房建議。
5. 預期效益
提⾼預約看房率：通過智能引導提⾼看房預約的轉化率。
降低詐騙⾵險：加強⽤⼾識別與信任，減少詐騙事件。
6. 使⽤情境展⽰
模擬LINE對話界⾯，展⽰AI如何與⽤⼾進⾏互動，引導其看房決策。
7. 商業模式與擴展性
SaaS模式：提供軟體即服務，讓更多房地產公司輕鬆接⼊。
房仲系統API整合：與現有房仲系統無縫整合，提⾼操作效率。
8. 社會影響與落地價值
提升信任與安全：建⽴更安全的線上看房環境，增強⽤⼾信任。
促進房地產市場健康發展：通過技術創新，推動整個⾏業的進步。
9. 結語與呼籲⽀持
戀愛式導購 AI 將成為房地產⾏業的變⾰⼒量。我們誠邀各界⽀持與合作，共同推動這⼀創新技術的落
地與普及。讓我們攜⼿創造更智能、更安全的看房體驗。",
    "第三段資料：戀愛式導購 AI ― LINE 對話引導看房機器⼈
1. 團隊介紹
我們的團隊由具有豐富房地產經驗的專業房仲和頂尖的AI技術專家組成。團隊中包含多名擁有⼈⼯智慧
與⾃然語⾔處理（NLP）背景的技術⼈員，致⼒於將先進的AI技術應⽤於房地產⾏業，提供創新⽽有效
的解決⽅案。
2. ⽬標客群與痛點
⽬標客群
潛在買家和租客
房地產中介公司
痛點
防詐騙需求：線上看房詐騙事件頻發，消費者信任度低。
導購轉換低：傳統房地產導購⽅式難以吸引和轉化顧客。
3. AI 技術運⽤
情緒偵測 NLP
利⽤⾃然語⾔處理技術，分析⽤⼾情緒，提供個性化的看房建議。
對話引導模型
智能對話系統能夠模擬真⼈互動，引導⽤⼾進⾏下⼀步操作，增加參與度。
4. 獨特競爭優勢
戀愛話術：將戀愛話術融⼊對話，引發⽤⼾情感共鳴。
房地產導購融合：結合專業房地產知識，提供精準的看房建議。
5. 預期效益
提⾼預約看房率：通過智能引導提⾼看房預約的轉化率。
降低詐騙⾵險：加強⽤⼾識別與信任，減少詐騙事件。
6. 使⽤情境展⽰
模擬LINE對話界⾯，展⽰AI如何與⽤⼾進⾏互動，引導其看房決策。
7. 商業模式與擴展性
SaaS模式：提供軟體即服務，讓更多房地產公司輕鬆接⼊。
房仲系統API整合：與現有房仲系統無縫整合，提⾼操作效率。
8. 社會影響與落地價值
提升信任與安全：建⽴更安全的線上看房環境，增強⽤⼾信任。
促進房地產市場健康發展：通過技術創新，推動整個⾏業的進步。
9. 結語與呼籲⽀持
戀愛式導購 AI 將成為房地產⾏業的變⾰⼒量。我們誠邀各界⽀持與合作，共同推動這⼀創新技術的落
地與普及。讓我們攜⼿創造更智能、更安全的看房體驗。",
    # 更多段落可繼續加
]



# === STEP 5: 問答階段：查詢 FAISS 並餵給 GPT ===
def ask_question_over_chunks(query):
    system_prompt = "你是一位資料助理，請根據『內容』回答問題。若找不到資料，請只回答：不知道。"

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
                return f"[第{i+1}段] {answer}"
        except Exception as e:
            print(f"❌ 第 {i+1} 段查詢失敗：{e}")

    return "不知道"






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






@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):

    user_input = event.message.text
    user_id = event.source.user_id


    
    try:          
        # 所有訊息都用向量資料庫查找內容 + GPT 回答
        reply = ask_question_over_chunks(user_input)

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






