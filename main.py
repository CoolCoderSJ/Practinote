from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from flask_session import Session
import os, json
from notion2md.exporter.block import MarkdownExporter, StringExporter
import docxpy
from PyPDF2 import PdfReader

from dotenv import load_dotenv
load_dotenv()

from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.query import Query
from appwrite.services.users import Users

from argon2 import PasswordHasher
ph = PasswordHasher()

from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

import cohere

client = (Client()
    .set_endpoint(f'{os.environ["APPWRITE_HOST"]}/v1') 
    .set_project(os.environ['APPWRITE_ID'])               
    .set_key(os.environ['APPWRITE_KEY']))   
db = Databases(client)
users = Users(client)

settings = {
    "client_config_backend": "service",
    "service_config": {
        "client_json_file_path": "service-secrets.json",
    }
}

gauth = GoogleAuth(settings=settings)
gauth.ServiceAuth()
drive = GoogleDrive(gauth)

app = Flask(__name__)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
Session(app)

co = cohere.Client(os.environ['COHERE'])

def generate_questions(input, history=[], promptaddition=""):
    message = f'You are given the following notes taken during a class: {input}. \n\nFrom these notes, generate 10 test questions and their answers. Respond in the format \nQuestions\n1. \n2. \n3. \n4. \n5. \n6. \n7. \n8. \n9. \n10. \n\nAnswers\n1.\n2. \n3. \n4. \n5. \n6. \n7. \n8. \n9. \n10. List all of the questions first, then list all of the answers.'+promptaddition
    print (message)
    response = co.chat( 
    model='command',
    message=message,
    temperature=0.3,
    chat_history=history,
    prompt_truncation='AUTO',
    stream=False,
    citation_quality='accurate',
    connectors=[]
    ) 
    text = response.text
    print(text)
    questions = text.split("Questions")[1].split("Answers")[0].split("\n")
    answers = text.split("Answers")[1].split("\n")
    questions = [question for question in questions if question != ""]
    answers = [answer for answer in answers if answer != ""]
    return questions, answers, message, text

def get_all_docs(data, collection, queries=[]):
    docs = []
    haslimit = False
    for query in queries:
        print(query)
        if query.startswith("limit"): 
            print(int(query.split("limit(")[1].split(")")[0]))
            if int(query.split("limit(")[1].split(")")[0]) <= 100: print("true"); haslimit = True
    
    if not haslimit:
        queries.append(Query.limit(100))
        querylength = len(queries)
        while True:
            if docs:
                queries.append(Query.cursorAfter(docs[-1]['$id']))
            try:
                results = db.list_documents(data, collection, queries=queries)
            except: return docs
            if len(results['documents']) == 0:
                break
            results = results['documents']
            docs += results
            print(data, collection, len(docs))
            if len(queries) != querylength:
                queries.pop()
    else:
        return db.list_documents(data, collection, queries=queries)['documents']
    return docs

@app.route('/')
def index():
    if not "user" in session:
        return redirect(url_for('login'))
    notes = get_all_docs("data", "notes", queries=[Query.equal("userId", session['user'])])
    res = {}
    titleToId = {}
    for note in notes:
        res[note['title']] = get_all_docs("data", "tests", queries=[Query.equal("noteRef", note['$id'])])
        titleToId[note['title']] = note['$id']

    return render_template('home.html', res=res, titleToId=titleToId)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if not request.form or not 'username' in request.form or not 'password' in request.form:
            flash("Either a username, password, or both were not provided", "error")
        username = request.form['username']
        password = request.form['password']

        allusers = users.list(queries=[Query.equal('name', username)])['users']
        if len(allusers) == 0:
            sessid = users.create('unique()', name=username, password=password)['$id']
            session['user'] = sessid
            return redirect(url_for('index'))
        
        user = allusers[0]
        try:
            ph.verify(user['password'], password)
        except: 
            flash("Incorrect password", "error")
            return render_template('login.html')
    
        sessid = user['$id']
        session['user'] = sessid
        return redirect(url_for('index'))

    return render_template('login.html')

@app.route("/notion-intermediary", methods=['GET', 'POST'])
def notion_inter():
    if request.method == "GET":
        tokens = db.list_documents("tokens", "notion", queries=[Query.equal("userId", session['user'])])['documents']
        if len(tokens) == 0:
            token = ""
        else:
            token = tokens[0]['notion_token']
        return render_template('notion-intermediary.html', token=token)
    
    token = request.form['token']
    tokens = db.list_documents("tokens", "notion", queries=[Query.equal("userId", session['user'])])['documents']
    if len(tokens) == 0:
        db.create_document("tokens", "notion", "unique()", {"userId": session['user'], "notion_token": token})
    else:
        db.update_document("tokens", "notion", tokens[0]['$id'], {"notion_token": token})
    os.environ['NOTION_TOKEN'] = token
    page = request.form['page']
    md = StringExporter(block_id=page.split("-")[-1].split("?")[0]).export()
    print(len(str(md)))
    note = db.create_document("data", "notes", "unique()", {
        "userId": session['user'],
        "notestext": str(md),
        "title": " ".join(page.split("?")[0].split("/")[-1].split("-")[:-1])
    })
    questions, answers, message, text = generate_questions(md[0:8000])
    print(questions, answers)
    test = db.create_document("data", "tests", "unique()", {
        "noteRef": note["$id"],
        "questions": questions,
        "answers": answers,
    })

    ctx = [
        {
            "user_name": "User",
            "message": message
        }, {
            "user_name": "Chatbot",
            "message": text
        }
    ]
    db.create_document("data", "chatctx", "unique()", {
        "noteRef": note["$id"],
        "ctx": json.dumps(ctx)
    })

    return redirect('/test/' + test['$id'])


@app.route("/docs-intermediary", methods=['GET', 'POST'])
def docs_inter():
    if request.method == "GET": return render_template('docs-intermediary.html')
    doc = request.form['page']
    file = drive.CreateFile({'id': doc})
    title = file['title']
    content = str(file.GetContentString("text/plain"))

    note = db.create_document("data", "notes", "unique()", {
        "userId": session['user'],
        "notestext": content,
        "title": title
    })
    questions, answers, message, text = generate_questions(content[0:8000])
    print(questions, answers)
    test = db.create_document("data", "tests", "unique()", {
        "noteRef": note["$id"],
        "questions": questions,
        "answers": answers,
    })

    ctx = [
        {
            "user_name": "User",
            "message": message
        }, {
            "user_name": "Chatbot",
            "message": text
        }
    ]
    db.create_document("data", "chatctx", "unique()", {
        "noteRef": note["$id"],
        "ctx": json.dumps(ctx)
    })

    return redirect('/test/' + test['$id'])

@app.route("/file-intermediary", methods=['GET', 'POST'])
def file_inter():
    if request.method == "GET": return render_template('file-intermediary.html')
    file = request.files['file']
    filename = file.filename
    if filename.endswith(".md") or filename.endswith(".txt"):
        content = str(file.read())
    elif filename.endswith(".docx"):
        f = open(filename, "wb")
        f.write(file.read())
        f.close()
        content = docxpy.process(filename)
        os.remove(filename)
    elif filename.endswith(".pdf"):
        f = open(filename, "wb")
        f.write(file.read())
        f.close()
        reader = PdfReader(filename)
        pages = reader.pages
        content = ""
        for page in pages:
            content += page.extract_text()
        os.remove(filename)
    print(content)
    note = db.create_document("data", "notes", "unique()", {
        "userId": session['user'],
        "notestext": content,
        "title": request.form['name']
    })
    questions, answers, message, text = generate_questions(content[0:8000])
    print(questions, answers)
    test = db.create_document("data", "tests", "unique()", {
        "noteRef": note["$id"],
        "questions": questions,
        "answers": answers,
    })

    ctx = [
        {
            "user_name": "User",
            "message": message
        }, {
            "user_name": "Chatbot",
            "message": text
        }
    ]
    db.create_document("data", "chatctx", "unique()", {
        "noteRef": note["$id"],
        "ctx": json.dumps(ctx)
    })

    return redirect('/test/' + test['$id'])

@app.route('/test/<testid>', methods=['GET', 'POST'])
def test(testid):
    if request.method == "GET":
        test = db.get_document("data", "tests", testid)
        if test['user_ans']:
            return redirect("/answers/"+testid)
        return render_template('test.html', test=test, testid=testid)
    test = db.get_document("data", "tests", testid)
    answers = test['answers']
    user_ans = []
    accuracy = []
    for i in range(len(answers)):
        user_ans.append(request.form[str(i+1)])

    for i in range(len(user_ans)):
        prompt = f"""the following question was given to a student: 
        {test['questions'][i]}
        the correct answer to this question is:
        {answers[i]}
        the student answered:
        {user_ans[i]}
        should this answer be accepted? Answer only with true or false."""
        response = co.chat( 
        model='command',
        message=prompt,
        temperature=0.3,
        chat_history=[],
        prompt_truncation='AUTO',
        stream=False,
        citation_quality='accurate',
        connectors=[]
        )
        text = response.text
        if text.lower() == "true": accuracy.append(True)
        else: accuracy.append(False)
        print(text)
    print(accuracy)

    db.update_document("data", "tests", testid, {"user_ans": user_ans, "close": accuracy})
    return redirect("/answers/"+testid)

@app.route('/answers/<testid>', methods=['GET'])
def answers(testid):
    test = db.get_document("data", "tests", testid)
    score = test['close'].count(True)
    return render_template('answers.html', test=test, testid=testid, score=score)

@app.route("/new/<testid>", methods=['POST'])
def newtest(testid):
    noteRef = db.get_document("data", "tests", testid)['noteRef']
    note = db.get_document("data", "notes", noteRef)
    ctxdoc = db.list_documents("data", "chatctx", queries=[Query.equal("noteRef", noteRef)])['documents'][0]
    ctx = ctxdoc['ctx']
    print(ctx)
    qstr = ""
    tests = get_all_docs("data", "tests", queries=[Query.equal("noteRef", noteRef)])
    for test in tests:
        qstr += "\n\n" + "\n".join(test['questions'])
    questions, answers, message, text = generate_questions(note['notestext'][0:8000], history=json.loads(ctx), promptaddition=f"\n\nThis is a new test. Do not re-use any questions you have already used. This is important- make sure every question is a different one than ones you have used in the past. Make sure you included the answers in the correct format. Write 'Questions' and make a numbered list with only the questions. Then write 'Answers' and make a numbered list with the answers. Your questions should NOT be equal to or similar to one of the following:\n{qstr}")
    print(questions, answers)
    test = db.create_document("data", "tests", "unique()", {
        "noteRef": note["$id"],
        "questions": questions,
        "answers": answers,
    })

    newctx = [
        {
            "user_name": "User",
            "message": message
        }, {
            "user_name": "Chatbot",
            "message": text
        }
    ]
    ctx = json.loads(ctx)
    ctx += newctx
    db.update_document("data", "chatctx", ctxdoc['$id'], {
        "noteRef": note["$id"],
        "ctx": json.dumps(ctx)
    })

    return redirect('/test/' + test['$id'])    

@app.route("/delete/note/<noteid>", methods=['POST'])
def deletenote(noteid):
    note = db.get_document("data", "notes", noteid)
    tests = get_all_docs("data", "tests", queries=[Query.equal("noteRef", noteid)])
    for test in tests:
        db.delete_document("data", "tests", test['$id'])
    db.delete_document("data", "notes", noteid)
    return redirect("/")

@app.route("/delete/test/<testid>", methods=['POST'])
def deletetest(testid):
    test = db.get_document("data", "tests", testid)
    db.delete_document("data", "tests", testid)
    return redirect("/")


app.run(debug=True)