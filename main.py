from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from flask_session import Session
import os, json
from notion2md.exporter.block import MarkdownExporter, StringExporter
import docxpy
from PyPDF2 import PdfReader

from dotenv import load_dotenv
load_dotenv()

from flata import Flata, where, Query
from flata.storages import JSONStorage
db = Flata('db.json', storage=JSONStorage)
users_db = db.table("users")
notion_tokens_db = db.table("notion_tokens")
tests_db = db.table("tests")
notes_db = db.table("notes")

from argon2 import PasswordHasher
ph = PasswordHasher()

from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

import cohere

import markdown


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

def generate_questions(input, history=[], promptaddition="", questions=10):
    questions = int(questions)
    qstr = "\n".join([f"{i+1}." for i in range(questions)])
    message = f'You are given the following notes taken during a class: {input}. \n\nFrom these notes, generate {questions} test questions and their answers. Respond in the format \nQuestions\n{qstr}\nAnswers\n{qstr} List all of the questions first, then list all of the answers.'+promptaddition
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

@app.route('/')
def index():
    if not "user" in session:
        return redirect(url_for('login'))
    notes = notes_db.search(where('userId') == session['user'])
    res = {}
    titleToId = {}
    for note in notes:
        res[note['title']] = tests_db.search(where('noteRef') == note['id'])
        titleToId[note['title']] = note['id']

    return render_template('home.html', res=res, titleToId=titleToId)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if not request.form or not 'username' in request.form or not 'password' in request.form:
            flash("Either a username, password, or both were not provided", "error")
        username = request.form['username']
        password = request.form['password']

        allusers = users_db.search(where('name') == username)
        if len(allusers) == 0:
            sessid = users_db.insert({
                "name": username,
                "password": ph.hash(password)
            })['id']
            session['user'] = sessid
            sampleNotes = notes_db.insert({
                "userId": session['user'],
                "notestext":"""# Class Notes

**Subject:** Introduction to Biology

**Date:** [Date]

**Topic:** Cell Structure and Function

## I. Introduction to Cells
- Cells are the basic units of life.
- **Cell theory:** All living organisms are composed of cells, and cells arise from pre-existing cells.
- **Two main types of cells:** prokaryotic and eukaryotic.

## II. Prokaryotic Cells
- Simple structure, lacking membrane-bound organelles.
- **Examples:** Bacteria and Archaea.
- **Key features:**
  - Cell membrane
  - Cytoplasm
  - DNA (nucleoid)
  - Ribosomes
- No nucleus; DNA is found in the nucleoid region.

## III. Eukaryotic Cells
- More complex, with membrane-bound organelles.
- **Examples:** Animals, plants, fungi, and protists.
- **Key features:**
  - Cell membrane
  - Cytoplasm
  - Nucleus (membrane-bound)
  - Membrane-bound organelles:
    - Endoplasmic reticulum
    - Golgi apparatus
    - Mitochondria
    - Chloroplasts (plants)
    - Lysosomes
    - Vacuoles

## IV. Plasma (Cell) Membrane
- **Functions:**
  - Boundary, selective barrier
  - Regulates passage of substances in and out of the cell
- Composed of a lipid bilayer with embedded proteins.
- **Selective permeability:** Allows some molecules to pass while blocking others.

## V. Nucleus
- Control center of the cell.
- Contains genetic material (DNA) organized into chromosomes.
- Surrounded by the nuclear envelope with nuclear pores for communication.

## VI. Endoplasmic Reticulum (ER)
- **Rough ER:** Studded with ribosomes; involved in protein synthesis.
- **Smooth ER:** Synthesizes lipids and detoxifies substances.

## VII. Golgi Apparatus
- Modifies, sorts, and packages proteins and lipids for transport.

## VIII. Mitochondria
- Powerhouses of the cell, generating ATP (energy) through cellular respiration.
- Have their own DNA (circular) and divide independently.

## IX. Chloroplasts (Plants)
- Site of photosynthesis, converting sunlight into chemical energy.
- Contain chlorophyll for capturing light energy.

## X. Lysosomes
- Vesicles containing enzymes for intracellular digestion and waste removal.

## XI. Vacuoles
- Storage sacs for various substances, including water, nutrients, and waste.

## XII. Conclusion
- Cells are the building blocks of life, and their structure determines their function.
- Prokaryotic and eukaryotic cells differ in complexity and organelles.
- Understanding cell structure is essential for comprehending life processes.
""",
                "title": "Sample Biology Notes"
            })
            questions, answers, message, text = generate_questions(sampleNotes['notestext'][0:8000])
            print(questions, answers)
            test = tests_db.insert({
                "noteRef": sampleNotes['id'],
                "questions": questions,
                "answers": answers,
            })
            return redirect(url_for('index'))
        
        user = allusers[0]
        try:
            ph.verify(user['password'], password)
        except: 
            flash("Incorrect password", "error")
            return render_template('login.html')
    
        sessid = user['id']
        session['user'] = sessid
        return redirect(url_for('index'))

    return render_template('login.html')

@app.route("/notion-intermediary", methods=['GET', 'POST'])
def notion_inter():
    if request.method == "GET":
        tokens = notion_tokens_db.search(where('userId') == session['user'])
        if len(tokens) == 0:
            token = ""
        else:
            token = tokens[0]['notion_token']
        return render_template('notion-intermediary.html', token=token)
    
    token = request.form['token']
    tokens = notion_tokens_db.search(where('userId') == session['user'])
    if len(tokens) == 0:
        notion_tokens_db.insert({"userId": session['user'], "notion_token": token})
    else:
        notion_tokens_db.update({"userId": session['user'], "notion_token": token}, where('userId') == session['user'])
    os.environ['NOTION_TOKEN'] = token
    page = request.form['page']
    md = StringExporter(block_id=page.split("-")[-1].split("?")[0]).export()
    print(len(str(md)))
    note = notes_db.insert({
        "userId": session['user'],
        "notestext": str(md),
        "title": " ".join(page.split("?")[0].split("/")[-1].split("-")[:-1])
    })
    questions, answers, message, text = generate_questions(md[0:8000], questions=request.form['questions'])
    print(questions, answers)
    test = tests_db.insert({
        "noteRef": note["id"],
        "questions": questions,
        "answers": answers,
    })

    return redirect('/test/' + str(test['id']))


@app.route("/docs-intermediary", methods=['GET', 'POST'])
def docs_inter():
    if request.method == "GET": return render_template('docs-intermediary.html')
    doc = request.form['page']
    file = drive.CreateFile({'id': doc})
    title = file['title']
    content = str(file.GetContentString("text/plain"))

    note = notes_db.insert({
        "userId": session['user'],
        "notestext": content,
        "title": title
    })

    questions, answers, message, text = generate_questions(content[0:8000], questions=request.form['questions'])
    print(questions, answers)
    test = tests_db.insert({
        "noteRef": note["id"],
        "questions": questions,
        "answers": answers,
    })

    return redirect('/test/' + str(test['id']))

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
    note = notes_db.insert({
        "userId": session['user'],
        "notestext": content,
        "title": request.form['name']
    })
    questions, answers, message, text = generate_questions(content[0:8000], questions=request.form['questions'])
    print(questions, answers)
    test = tests_db.insert({
        "noteRef": note["id"],
        "questions": questions,
        "answers": answers,
    })

    return redirect('/test/' + str(test['id']))

@app.route('/test/<int:testid>', methods=['GET', 'POST'])
def test(testid):
    if request.method == "GET":
        test = tests_db.get(where('id') == testid)
        print(test)
        if "user_ans" in test:
            return redirect("/answers/"+str(testid))
        return render_template('test.html', test=test, testid=testid)
    test = tests_db.get(where('id') == testid)
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

    tests_db.update({"user_ans": user_ans, "close": accuracy}, where('id') == testid)
    return redirect("/answers/"+str(testid))


@app.route("/notes/<int:noteid>", methods=['GET'])
def notes(noteid):
    note = notes_db.get(where('id') == noteid)['notestext']
    return render_template('notes.html', content=markdown.markdown(note), title=notes_db.get(where('id') == noteid)['title'])


@app.route('/answers/<int:testid>', methods=['GET'])
def answers(testid):
    test = tests_db.get(where('id') == testid)
    score = test['close'].count(True)
    return render_template('answers.html', test=test, testid=testid, score=score)

@app.route("/new/<int:testid>", methods=['POST'])
def newtest(testid):
    noteRef = tests_db.get(where('id') == testid)['noteRef']
    note = notes_db.get(where('id') == noteRef)
    # print(ctx)
    qstr = ""
    tests = tests_db.search(where('noteRef') == noteRef)
    amtoftests = len(tests)
    for test in tests:
        qstr += "\n\n" + "\n".join(test['questions'])
    testnum = amtoftests 
    notelength = len(note['notestext'])
    index = testnum*7900
    toIndex = index + 7900
    if index > notelength: index = notelength-7900
    if toIndex > notelength: toIndex = notelength
    print(index, toIndex)
    questions, answers, message, text = generate_questions(note['notestext'][index:toIndex], questions=request.form['questions'], promptaddition=f"\n\nThis is a new test. Do not re-use any questions you have already used. This is important- make sure every question is a different one than ones you have used in the past. Make sure you included the answers in the correct format. Write 'Questions' and make a numbered list with only the questions. Then write 'Answers' and make a numbered list with the answers.")
    print(questions, answers)
    test = tests_db.insert({
        "noteRef": noteRef,
        "questions": questions,
        "answers": answers,
    })

    return redirect('/test/' + str(test['id'])) 

@app.route("/delete/note/<int:noteid>", methods=['POST'])
def deletenote(noteid):
    note = notes_db.get(where('id') == noteid)
    tests = tests_db.search(where('noteRef') == noteid)
    for test in tests:
        tests_db.remove(where('id') == test['id'])
    notes_db.remove(where('id') == noteid)
    return redirect("/")

@app.route("/delete/test/<int:testid>", methods=['POST'])
def deletetest(testid):
    tests_db.remove(where('id') == testid)
    return redirect("/")


app.run(debug=True)