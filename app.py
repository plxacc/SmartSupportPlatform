from flask import Flask, render_template, request, make_response, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
import sys
import io
import os
import random
from datetime import datetime
import requests

# ضبط الترميز لدعم العربية
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "super_secret_key")

# إعداد DeepSeek API
DEEPSEEK_API_KEY = "sk-cc2115d5a18144c191aeb48416dd9824"  # استبدل هذا بمفتاح API الخاص بك

# إعداد قاعدة البيانات
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "sqlite:///site.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# نموذج التذكرة
class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    student_id = db.Column(db.String(50), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    problem = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), nullable=False, default="جديدة")
    support_response = db.Column(db.Text, nullable=True)
    user_response = db.Column(db.Text, nullable=True)
    read_by_support = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# نموذج الأسئلة (الدليل التفاعلي)
class Guide(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(500), nullable=False, unique=True)
    answer = db.Column(db.Text, nullable=False)

# إنشاء قاعدة البيانات
with app.app_context():
    db.create_all()
    # إضافة بيانات افتراضية للدليل إذا لم تكن موجودة
    if not Guide.query.first():
        default_guides = [
            Guide(question="كيف أتصل بشبكة الواي فاي في الكلية؟", answer="افتح إعدادات الواي فاي، ابحث عن College-WiFi، أدخل رقمك الجامعي وكلمة المرور."),
            Guide(question="كيف أستخدم Microsoft Teams؟", answer="حمل تطبيق Teams، سجل الدخول ببريدك الجامعي، انضم إلى الاجتماع عبر رابط أو رمز.")
        ]
        db.session.bulk_save_objects(default_guides)
        db.session.commit()

# تحميل الأسئلة من قاعدة البيانات
def load_responses():
    guides = Guide.query.all()
    return {guide.question: guide.answer for guide in guides}

# دالة للتواصل مع DeepSeek API
def get_ai_response(question):
    api_url = "https://api.deepseek.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}
    payload = {
        "model": "deepseek-chat",  # يمكنك استخدام "deepseek-reasoner" للمهام التقنية
        "messages": [
            {"role": "system", "content": "أجب بالعربية بطريقة طبيعية وودودة."},
            {"role": "user", "content": question}
        ],
        "max_tokens": 200,
        "temperature": 0.7
    }
    try:
        response = requests.post(api_url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        print(f"API response: {result}")
        if "choices" in result and result["choices"]:
            answer = result["choices"][0]["message"]["content"].strip()
            if not answer:
                return "آسف، لم أفهم سؤالك جيدًا. هل يمكنك إعادة صياغته بطريقة أخرى؟"
            return answer
        else:
            print("Unexpected API response format")
            return "آسف، الرد من API غير متوقع. دعني أحاول مرة أخرى!"
    except Exception as e:
        print(f"DeepSeek API error: {str(e)}")
        return f"عذرًا، حدث خطأ في API: {str(e)}"

# الصفحة الرئيسية
@app.route("/", methods=["GET"])
def home():
    response = make_response(render_template("index.html"))
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response

# واجهة الدردشة
@app.route("/chat", methods=["POST"])
def chat():
    question = request.form.get("question").strip()
    print(f"Received question: {question}")
    responses = load_responses()
    print(f"Loaded responses: {responses}")
    answer = ""

    # تحسين التحية
    greetings = ["مرحبًا", "السلام عليكم", "الو", "سلام"]
    if any(greeting in question.lower() for greeting in greetings):
        possible_greetings = [
            "أهلاً! كيف يمكنني مساعدتك؟",
            "مرحبًا بك! ما الذي تحتاجه؟",
            "سلام! يسعدني مساعدتك، ما سؤالك؟"
        ]
        answer = random.choice(possible_greetings)
        print(f"Answer (greeting): {answer}")
    else:
        # البحث في قاعدة البيانات أولاً
        for q, a in responses.items():
            if question.lower().strip() in q.lower() or q.lower() in question.lower().strip():
                answer = a
                print(f"Answer found in database: {answer}")
                break
        else:
            # استخدام DeepSeek API
            answer = get_ai_response(question)
            print(f"Answer from DeepSeek API: {answer}")

    return jsonify({"answer": answer})

# صفحة فتح تذكرة
@app.route("/report", methods=["GET", "POST"])
def report():
    message = ""
    ticket = session.pop("new_ticket", None)
    search_tickets = []
    search_message = ""

    if request.method == "POST":
        if "search_query" in request.form:
            search_query = request.form.get("search_query")
            search_tickets = Ticket.query.filter(
                (Ticket.id == search_query) | (Ticket.student_id == search_query)
            ).all()
            if not search_tickets:
                search_message = "لم يتم العثور على تذكرة مطابقة."
        elif "name" in request.form:
            name = request.form.get("name")
            email = request.form.get("email")
            student_id = request.form.get("student_id")
            subject = request.form.get("subject")
            problem = request.form.get("problem")
            ticket_id = random.randint(1000, 9999)
            new_ticket = Ticket(
                id=ticket_id,
                name=name,
                email=email,
                student_id=student_id,
                subject=subject,
                problem=problem,
                status="جديدة",
                support_response="",
                user_response="",
                read_by_support=False
            )
            db.session.add(new_ticket)
            db.session.commit()
            session["new_ticket"] = {
                "id": new_ticket.id,
                "name": new_ticket.name,
                "email": new_ticket.email,
                "student_id": new_ticket.student_id,
                "subject": new_ticket.subject,
                "problem": new_ticket.problem,
                "status": new_ticket.status,
                "support_response": new_ticket.support_response,
                "user_response": new_ticket.user_response,
                "read_by_support": new_ticket.read_by_support
            }
            message = f"تم إنشاء تذكرتك بنجاح! رقم التذكرة: {ticket_id}."
            return redirect(url_for("report"))

    response = make_response(render_template("report.html", message=message, ticket=ticket, search_tickets=search_tickets, search_message=search_message))
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response

# الرد على تذكرة
@app.route("/respond_ticket", methods=["POST"])
def respond_ticket():
    ticket_id = request.form.get("ticket_id")
    user_response = request.form.get("user_response")
    ticket = Ticket.query.get(ticket_id)
    if ticket:
        ticket.user_response = user_response
        ticket.status = "في انتظار رد الدعم"
        db.session.commit()
        session["new_ticket"] = {
            "id": ticket.id,
            "name": ticket.name,
            "email": ticket.email,
            "student_id": ticket.student_id,
            "subject": ticket.subject,
            "problem": ticket.problem,
            "status": ticket.status,
            "support_response": ticket.support_response,
            "user_response": ticket.user_response,
            "read_by_support": ticket.read_by_support
        }
    return redirect(url_for("report"))

# حذف تذكرة
@app.route("/delete_ticket", methods=["POST"])
def delete_ticket():
    ticket_id = request.form.get("ticket_id")
    ticket = Ticket.query.get(ticket_id)
    if ticket:
        db.session.delete(ticket)
        db.session.commit()
    session.pop("new_ticket", None)
    return redirect(url_for("report"))

# الدليل التفاعلي
@app.route("/guide", methods=["GET", "POST"])
def guide():
    responses = load_responses()
    search_query = request.form.get("search_query", "").strip()
    search_message = ""

    if request.method == "POST" and search_query:
        filtered_responses = {q: a for q, a in responses.items() if search_query.lower() in q.lower() or search_query.lower() in a.lower()}
        if not filtered_responses:
            search_message = "لم يتم العثور على نتائج مطابقة."
        responses = filtered_responses

    response = make_response(render_template("guide.html", responses=responses, search_query=search_query, search_message=search_message))
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response

# صفحة عن الكلية
@app.route("/about")
def about():
    response = make_response(render_template("about.html"))
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response

# صفحة المصممين
@app.route("/designers")
def designers():
    response = make_response(render_template("designers.html"))
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response

# تسجيل الدخول
@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        code = request.form.get("code")
        admin_code = os.environ.get("ADMIN_CODE", "Tvtc.101")
        if code == admin_code:
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

    tickets = Ticket.query.all()
    message = ""
    responses = load_responses()
    search_query = request.form.get("search_query", "") if request.method == "POST" else ""

    # تصفية التذاكر بناءً على البحث
    if search_query:
        tickets = Ticket.query.filter(
            (Ticket.id == search_query) | (Ticket.student_id == search_query)
        ).all()

    # تحديث حالة القراءة
    for ticket in tickets:
        ticket.read_by_support = True
    db.session.commit()

    if request.method == "POST":
        if "ticket_id" in request.form and "support_response" in request.form:
            ticket_id = request.form.get("ticket_id")
            support_response = request.form.get("support_response")
            ticket = Ticket.query.get(ticket_id)
            if ticket:
                ticket.support_response = support_response
                ticket.status = "تم الرد"
                db.session.commit()
                message = "تم إرسال الرد بنجاح!"
        
        elif "delete_ticket_id" in request.form:
            ticket_id = request.form.get("delete_ticket_id")
            ticket = Ticket.query.get(ticket_id)
            if ticket:
                db.session.delete(ticket)
                db.session.commit()
                message = "تم حذف التذكرة بنجاح!"
        
        elif "question" in request.form and "answer" in request.form:
            question = request.form.get("question")
            answer = request.form.get("answer")
            new_guide = Guide(question=question, answer=answer)
            db.session.add(new_guide)
            try:
                db.session.commit()
                message = "تم إضافة السؤال بنجاح!"
            except:
                db.session.rollback()
                message = "خطأ: السؤال موجود بالفعل."
        
        elif "edit_question" in request.form:
            old_question = request.form.get("old_question")
            new_question = request.form.get("new_question")
            new_answer = request.form.get("new_answer")
            guide = Guide.query.filter_by(question=old_question).first()
            if guide:
                guide.question = new_question
                guide.answer = new_answer
                try:
                    db.session.commit()
                    message = "تم تعديل السؤال بنجاح!"
                except:
                    db.session.rollback()
                    message = "خطأ: السؤال الجديد موجود بالفعل."
        
        elif "delete_question" in request.form:
            question = request.form.get("delete_question")
            guide = Guide.query.filter_by(question=question).first()
            if guide:
                db.session.delete(guide)
                db.session.commit()
                message = "تم حذف السؤال بنجاح!"

    response = make_response(render_template("admin.html", tickets=tickets, message=message, responses=responses, search_query=search_query))
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response

# تسجيل الخروج
@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("home"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)