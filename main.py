from datetime import datetime, timedelta, timezone
import json
import os
from flask import Flask, request
import requests

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TODOIST_TOKEN = os.environ.get("TODOIST_TOKEN")

KST = timezone(timedelta(hours=9))


def send_telegram(chat_id, message):
  try:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    if len(message) > 4000:
      message = message[:3997] + "..."

    payload = {"chat_id": chat_id, "text": message}
    response = requests.post(url, json=payload, timeout=5)
    print(f"Telegram response: {response.text}")
  except Exception as e:
    print(f"Telegram send error: {e}")


def fetch_todoist_tasks():
  # v1 엔드포인트는 filter 파라미터를 무시하므로 전체 목록을 가져와서 서버에서 직접 필터링합니다.
  url = "https://api.todoist.com/api/v1/tasks"
  headers = {"Authorization": f"Bearer {TODOIST_TOKEN}"}
  try:
    response = requests.get(url, headers=headers, timeout=10)
    return response.status_code, response.text
  except Exception as e:
    return 500, str(e)


def get_tasks_summary(mode):
  try:
    now_kst = datetime.now(KST)
    today_date = now_kst.date()
    today_str = today_date.strftime("%Y-%m-%d")

    status_code, text_resp = fetch_todoist_tasks()
    if status_code != 200:
      return (
          f"[Todoist 연동 오류]\n상태 코드: {status_code}\n내용:\n{text_resp[:500]}"
      )

    try:
      data = json.loads(text_resp)
    except Exception:
      return f"[Todoist 응답 오류]\nJSON 파싱 실패:\n{text_resp[:400]}"

    if isinstance(data, dict):
      tasks = data.get("results", [])
    elif isinstance(data, list):
      tasks = data
    else:
      return f"[Todoist 응답 오류]\n원본 데이터:\n{text_resp[:400]}"

    filtered_tasks = []

    if mode == "day":
      title_label = "오늘의 할 일 (기한 지난 항목 포함)"
      for task in tasks:
        # 완료된 태스크 제외
        if task.get("checked", False) or task.get("is_completed", False):
          continue

        due = task.get("due")
        if due and "date" in due:
          try:
            task_date = datetime.strptime(due["date"][:10], "%Y-%m-%d").date()
            # 오늘이거나 기한이 지난(Overdue) 할 일 포함
            if task_date <= today_date:
              prefix = (
                  f"[{due['date'][:10]}] " if task_date < today_date else ""
              )
              filtered_tasks.append(f"{prefix}{task.get('content', '')}")
          except Exception:
            pass

    else:
      title_label = "이번 주 할 일 (일요일 시작)"
      weekday_num = now_kst.weekday()
      days_since_sunday = (weekday_num + 1) % 7
      start_of_week = today_date - timedelta(days=days_since_sunday)
      end_of_week = start_of_week + timedelta(days=6)

      for task in tasks:
        if task.get("checked", False) or task.get("is_completed", False):
          continue

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
      return f"[Todoist {title_label} ({today_str})]\n\n조회된 할 일이 없습니다."
    else:
      message = f"[Todoist {title_label} ({today_str})]\n\n"
      for idx, content in enumerate(filtered_tasks, 1):
        message += f"{idx}. {content}\n"
      return message
  except Exception as e:
    return f"[코드 내부 에러]\n{str(e)}"


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
        command = text.split("@")[0]

        if command == "/day":
          msg = get_tasks_summary("day")
          send_telegram(chat_id, msg)
        elif command == "/week":
          msg = get_tasks_summary("week")
          send_telegram(chat_id, msg)
        elif command == "/debug":
          status_code, result = fetch_todoist_tasks()
          msg = (
              f"[디버그 결과]\n상태 코드: {status_code}\n내용:\n{result[:500]}"
          )
          send_telegram(chat_id, msg)
        elif command == "/start":
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
