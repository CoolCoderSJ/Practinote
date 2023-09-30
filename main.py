from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)

@app.route('/<path>')
def index(path):
    return render_template(f'{path}.html')

app.run(debug=True)