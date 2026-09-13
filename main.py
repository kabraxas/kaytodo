from datetime import datetime, timedelta
import os
from flask import Flask, request
import pytz
import requests

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TODOIST_TOKEN = os.environ.get("TODOIST_TOKEN")


def send_telegram(chat_id, message):
  try:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    requests.post(url, json=payload, timeout=5)
  except Exception as e:
    print(f"Telegram send error: {e}")


def fetch_todoist_tasks_by_filter(filter_query):
  url = "https://api.todoist.com/api/v1/tasks"
  headers = {"Authorization": f"Bearer {TODOIST_TOKEN}"}
  params = {"filter": filter_query} if filter_query else {}
  try:
    response = requests.get(url, headers=headers, params=params, timeout=10)
    return response.status_code, response.text
  except Exception as e:
    return 500, str(e)


def get_tasks_summary(mode):
  try:
    import json

    kst = pytz.timezone("Asia/Seoul")
    now_kst = datetime.now(kst)
    today_date = now_kst.date()
    today_str = today_date.strftime("%Y-%m-%d")

    if mode == "day":
      title_label = "오늘의 할 일"
      status_code, text_resp = fetch_todoist_tasks_by_filter("today")

      if status_코드가_아님 := (status_code != 200):
        return (
            f"<b>[Todoist 연동 오류]</b>\n상태 코드:"
            f" {status_code}\n내용:\n{text_resp}"
        )

      tasks = json.loads(text_resp)
      # tasks가 리스트가 아닐 경우(에러 딕셔너리 등) 방어 처리
      if not isinstance(tasks, list):
        return (
            f"<b>[Todoist 응답 오류]</b>\n예상치 못한 데이터 형태입니다:\n"
            f"{text_resp}"
        )

      filtered_tasks = [task["content"] for task in tasks if "content" in task]

    else:
      title_label = "이번 주 할 일 (일요일 시작)"
      weekday_num = now_kst.weekday()  # 월:0 ~ 일:6
      days_since_sunday = (weekday_num + 1) % 7
      start_of_week = today_date - timedelta(days=days_since_sunday)
      end_of_week = start_of_week + timedelta(days=6)

      start_str = start_of_week.strftime("%Y-%m-%d")
      end_str = end_of_week.strftime("%Y-%m-%d")

      filter_query = f"{start_str} | {end_str}"
      status_code, text_resp = fetch_todoist_tasks_by_filter(filter_query)

      if status_code != 200:
        return (
            f"<b>[Todoist 연동 오류]</b>\n상태 코드:"
            f" {status_code}\n내용:\n{text_resp}"
        )

      tasks = json.loads(text_resp)
      if not isinstance(tasks, list):
        return (
            f"<b>[Todoist 응답 오류]</b>\n예상치 못한 데이터 형태입니다:\n"
            f"{text_resp}"
        )

      filtered_tasks = []
      for task in tasks:
        due = task.get("due")
        if due and "date" in due:
          try:
            task_date = datetime.strptime(due["date"][:10], "%Y-%m-%d").date()
            if start_of_week <= task_date <= end_of_week:
              filtered_tasks.append(
                  f"[{due['date'][:10]}] {task.get('content', '')}"
              )
          except Exception:
            pass

    if not filtered_tasks:
      return (
          f"<b>[Todoist {title_label} ({today_str})]</b>\n\n조회된 할 일이"
          f" 없습니다."
      )
    else:
      message = f"<b>[Todoist {title_label} ({today_str})]</b>\n\n"
      for idx, content in enumerate(filtered_tasks, 1):
        message += f"{idx}. {content}\n"
      return message
  except Exception as e:
    return f"<b>[코드 내부 에러]</b>\n{str(e)}"


@app.route("/", methods=["POST"])
def telegram_webhook():
  try:
    data = request.get_json(silent=True)
    if not data:
      return "OK", 200

    message_obj = data.get("message") or data.get("edited_message")
    if message_obj:
      chat_id = message_obj.get("chat", {}).get("id")
      text = message_obj.get("text", "").strip()

      if chat_id and text:
        if text == "/day":
          msg = get_tasks_summary("day")
          send_telegram(chat_id, msg)
        elif text == "/week":
          msg = get_tasks_summary("week")
          send_telegram(chat_id, msg)
        elif text == "/debug":
          status_code, result = fetch_todoist_tasks_by_filter("today")
          msg = (
              f"<b>[디버그 결과]</b>\n상태 코드: {status_code}\n내용:\n{result}"
          )
          send_telegram(chat_id, msg)
        elif text == "/start":
          send_telegram(chat_id, "Todoist 봇이 준비되었습니다.")
  except Exception as e:
    print(f"Webhook processing error: {e}")

  return "OK", 200


@app.route("/", methods=["GET"])
def health_check():
  return "Bot is running!", 200


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 5000))
  app.run(host="0.0.0.0", port=port)
