from flask import Flask, render_template, request, make_response, redirect, url_for, session
import sys
import io
import json
import os
import random
from fuzzywuzzy import fuzz
from datetime import datetime

# ضبط الترميز لدعم العربية
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

app = Flask(__name__)
app.secret_key = "super_secret_key"

# تحميل الأسئلة من guide.json
def load_responses():
    if os.path.exists("guide.json"):
        with open("guide.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "كيف أتصل بشبكة الواي فاي في الكلية؟": "افتح إعدادات الواي فاي، ابحث عن College-WiFi، أدخل رقمك الجامعي وكلمة المرور.",
        "كيف أستخدم Microsoft Teams؟": "حمل تطبيق Teams، سجل الدخول ببريدك الجامعي، انضم إلى الاجتماع عبر رابط أو رمز."
    }

# ملف التذاكر
TICKETS_FILE = "tickets.json"

def load_tickets():
    if os.path.exists(TICKETS_FILE):
        with open(TICKETS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_tickets(tickets):
    with open(TICKETS_FILE, "w", encoding="utf-8") as f:
        json.dump(tickets, f, ensure_ascii=False, indent=4)

# الصفحة الرئيسية
@app.route("/", methods=["GET", "POST"])
def home():
    answer = ""
    responses = load_responses()
    if request.method == "POST":
        question = request.form.get("question").strip()
        best_match = None
        highest_score = 0
        for q, a in responses.items():
            score = fuzz.partial_ratio(question.lower(), q.lower())
            if score > highest_score and score >= 50:
                highest_score = score
                best_match = a
        answer = best_match if best_match else "عذرًا، لا أفهم سؤالك. جرب صياغة أخرى أو تحقق من الدليل."
    response = make_response(render_template("index.html", answer=answer))
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response

# صفحة الإبلاغ
@app.route("/report", methods=["GET", "POST"])
def report():
    message = ""
    ticket = None
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        student_id = request.form.get("student_id")
        subject = request.form.get("subject")
        problem = request.form.get("problem")
        ticket_id = random.randint(1000, 9999)
        tickets = load_tickets()
        new_ticket = {
            "id": ticket_id,
            "name": name,
            "email": email,
            "student_id": student_id,
            "subject": subject,
            "problem": problem,
            "status": "جديدة",
            "support_response": "",
            "user_response": ""
        }
        tickets.append(new_ticket)
        save_tickets(tickets)
        message = f"تم إنشاء تذكرتك بنجاح! رقم التذكرة: {ticket_id}."
        ticket = new_ticket  # تمرير التذكرة لعرضها
    response = make_response(render_template("report.html", message=message, ticket=ticket))
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response

# الرد على تذكرة
@app.route("/respond_ticket", methods=["POST"])
def respond_ticket():
    ticket_id = request.form.get("ticket_id")
    user_response = request.form.get("user_response")
    tickets = load_tickets()
    ticket = None
    for t in tickets:
        if str(t["id"]) == ticket_id:
            t["user_response"] = user_response
            t["status"] = "في انتظار رد الدعم"
            ticket = t
            break
    save_tickets(tickets)
    message = "تم إرسال ردك بنجاح!"
    response = make_response(render_template("report.html", message=message, ticket=ticket))
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response

# حذف تذكرة (للمستخدم والدعم الفني)
@app.route("/delete_ticket", methods=["POST"])
def delete_ticket():
    ticket_id = request.form.get("ticket_id")
    tickets = load_tickets()
    tickets = [t for t in tickets if str(t["id"]) != ticket_id]
    save_tickets(tickets)
    message = "تم حذف التذكرة بنجاح!"
    response = make_response(render_template("report.html", message=message))
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response

# الدليل التفاعلي
@app.route("/guide")
def guide():
    responses = load_responses()
    response = make_response(render_template("guide.html", responses=responses))
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response

# صفحة عن الكلية
@app.route("/about")
def about():
    response = make_response(render_template("about.html"))
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response

# تسجيل الدخول
@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        code = request.form.get("code")
        if code == "Tvtc.101":
            session["admin"] = True
            return redirect(url_for("admin"))
        else:
            error = "رمز الدخول غير صحيح."
    response = make_response(render_template("login.html", error=error))
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response

# لوحة تحكم الدعم الفني
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if not session.get("admin"):
        return redirect(url_for("login"))
    
    tickets = load_tickets()
    message = ""
    responses = load_responses()
    
    if request.method == "POST":
        if "ticket_id" in request.form and "support_response" in request.form:
            ticket_id = request.form.get("ticket_id")
            support_response = request.form.get("support_response")
            for t in tickets:
                if str(t["id"]) == ticket_id:
                    t["support_response"] = support_response
                    t["status"] = "تم الرد"
                    break
            save_tickets(tickets)
            message = "تم إرسال الرد بنجاح!"
        
        elif "delete_ticket_id" in request.form:
            ticket_id = request.form.get("delete_ticket_id")
            tickets = [t for t in tickets if str(t["id"]) != ticket_id]
            save_tickets(tickets)
            message = "تم حذف التذكرة بنجاح!"
        
        elif "question" in request.form and "answer" in request.form:
            question = request.form.get("question")
            answer = request.form.get("answer")
            responses[question] = answer
            with open("guide.json", "w", encoding="utf-8") as f:
                json.dump(responses, f, ensure_ascii=False, indent=4)
            message = "تم إضافة السؤال بنجاح!"
        
        elif "edit_question" in request.form:
            old_question = request.form.get("old_question")
            new_question = request.form.get("new_question")
            new_answer = request.form.get("new_answer")
            if old_question in responses:
                del responses[old_question]
                responses[new_question] = new_answer
                with open("guide.json", "w", encoding="utf-8") as f:
                    json.dump(responses, f, ensure_ascii=False, indent=4)
                message = "تم تعديل السؤال بنجاح!"
        
        elif "delete_question" in request.form:
            question = request.form.get("delete_question")
            if question in responses:
                del responses[question]
                with open("guide.json", "w", encoding="utf-8") as f:
                    json.dump(responses, f, ensure_ascii=False, indent=4)
                message = "تم حذف السؤال بنجاح!"
    
    response = make_response(render_template("admin.html", tickets=tickets, message=message, responses=responses))
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response

# تسجيل الخروج
@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))