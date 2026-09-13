from datetime import datetime, timedelta
import os
from flask import Flask, request
import pytz
import requests

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TODOIST_TOKEN = os.environ.get("TODOIST_TOKEN")


def send_telegram(chat_id, message):
  url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
  payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
  requests.post(url, json=payload)


def fetch_todoist_tasks_by_filter(filter_query):
  url = "https://api.todoist.com/rest/v2/tasks"
  headers = {"Authorization": f"Bearer {TODOIST_TOKEN}"}
  params = {"filter": filter_query} if filter_query else {}
  response = requests.get(url, headers=headers, params=params)
  if response.status_code == 200:
    return response.status_code, response.json()
  else:
    return response.status_code, response.text


def get_tasks_summary(mode):
  kst = pytz.timezone("Asia/Seoul")
  now_kst = datetime.now(kst)
  today_date = now_kst.date()
  today_str = today_date.strftime("%Y-%m-%d")

  if mode == "day":
    title_label = "오늘의 할 일"
    status_code, tasks = fetch_todoist_tasks_by_filter("today")

    if status_code != 200:
      return f"<b>[Todoist 연동 오류]</b>\nAPI 호출 실패 (상태 코드: {status_code})\n내용: {tasks}"

    filtered_tasks = [task["content"] for task in tasks]

  else:
    title_label = "이번 주 할 일 (일요일 시작)"
    weekday_num = now_kst.weekday()  # 월:0 ~ 일:6
    days_since_sunday = (weekday_num + 1) % 7
    start_of_week = today_date - timedelta(days=days_since_sunday)
    end_of_week = start_of_week + timedelta(days=6)

    start_str = start_of_week.strftime("%Y-%m-%d")
    end_str = end_of_week.strftime("%Y-%m-%d")

    filter_query = f"{start_str} | {end_str}"
    status_code, tasks = fetch_todoist_tasks_by_filter(filter_query)

    if status_code != 200:
      return f"<b>[Todoist 연동 오류]</b>\nAPI 호출 실패 (상태 코드: {status_code})\n내용: {tasks}"

    filtered_tasks = []
    for task in tasks:
      due = task.get("due")
      if due and "date" in due:
        try:
          task_date = datetime.strptime(due["date"][:10], "%Y-%m-%d").date()
          if start_of_week <= task_date <= end_of_week:
            filtered_tasks.append(f"[{due['date'][:10]}] {task['content']}")
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


@app.route("/", methods=["POST"])
def telegram_webhook():
  data = request.get_json()
  if data and "message" in data:
    chat_id = data["message"]["chat"]["id"]
    text = data["message"].get("text", "").strip()

    if text == "/day":
      msg = get_tasks_summary("day")
      send_telegram(chat_id, msg)
    elif text == "/week":
      msg = get_tasks_summary("week")
      send_telegram(chat_id, msg)
    elif text == "/debug":
      status_code, result = fetch_todoist_tasks_by_filter("today")
      if status_code == 200:
        msg = (
            f"<b>[디버그 성공]</b>\nHTTP 상태 코드: {status_code}\n오늘 필터 태스크"
            f" 수: {len(result)}"
        )
      else:
        msg = (
            f"<b>[디버그 실패]</b>\nHTTP 상태 코드: {status_code}\n에러 내용:"
            f" {result}"
        )
      send_telegram(chat_id, msg)
    elif text == "/start":
      send_telegram(chat_id, "Todoist 봇이 준비되었습니다.")

  return "OK", 200


@app.route("/", methods=["GET"])
def health_check():
  return "Bot is running!", 200


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 5000))
  app.run(host="0.0.0.0", port=port)
