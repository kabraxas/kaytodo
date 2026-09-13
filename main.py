import os
from datetime import datetime, timedelta
import pytz
import requests
from flask import Flask, request

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TODOIST_TOKEN = os.environ.get("TODOIST_TOKEN")


def send_telegram(chat_id, message):
  url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
  payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
  requests.post(url, json=payload)


def fetch_todoist_tasks():
  url = "https://api.todoist.com/rest/v2/tasks"
  headers = {"Authorization": f"Bearer {TODOIST_TOKEN}"}
  response = requests.get(url, headers=headers)
  if response.status_code != 200:
    return []
  return response.json()


def get_tasks_summary(mode):
  kst = pytz.timezone("Asia/Seoul")
  now_kst = datetime.now(kst)
  today_date = now_kst.date()
  today_str = today_date.strftime("%Y-%m-%d")

  tasks = fetch_todoist_tasks()
  filtered_tasks = []

  if mode == "day":
    title_label = "오늘의 할 일"
    for task in tasks:
      due = task.get("due")
      if due:
        due_date_str = due.get("date", "")[:10]
        string_due = due.get("string", "").lower()
        if (
            due_date_str == today_str
            or "매일" in string_due
            or "every" in string_due
        ):
          filtered_tasks.append(task["content"])
  else:
    title_label = "이번 주 할 일 (일요일 시작)"
    weekday_num = now_kst.weekday()
    days_since_sunday = (weekday_num + 1) % 7
    start_of_week = today_date - timedelta(days=days_since_sunday)
    end_of_week = start_of_week + timedelta(days=6)

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
        f" 없습니다.\n(총 태스크 수: {len(tasks)})"
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
      tasks = fetch_todoist_tasks()
      msg = f"총 태스크 수: {len(tasks)}"
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
