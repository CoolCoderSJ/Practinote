# Practinote
 Use AI to generate practice quizzes directly from your notes.

## Tech Stack/Information
The languages used in this project are Python, HTML, CSS, and JavaScript. The libraries used in this project are Flask, PyPDF2, and NLTK. The web app is hosted on Oracle Cloud Infrastructure.

## Set Up Locally
1. Clone the repository
```bash
git clone https://github.com/CoolCoderSJ/Practinote.git
```
2. Install the required libraries
```bash
pip install -r requirements.txt
```
3. Setup a Google Service Account
    - Go to the [Google Cloud Console](https://console.cloud.google.com/)
    - Create a new project
    - Go to the [Google Cloud Console API Library](https://console.cloud.google.com/apis/library)
    - Enable the Google Drive API and Google Sheets API
    - Go to the [Google Cloud Console Credentials Page](https://console.cloud.google.com/apis/credentials)
    - Create a new service account
    - Download the JSON file and rename it to `service-secrets.json`

4. Setup the environment variables
- Create a file and name it `.env`
- Visit [Cohere](https://cohere.ai/) and create an account
- Navigate to https://dashboard.cohere.com/api-keys
- Copy the Trial API key
- Paste the API key into the `.env` file
Here's an example of what the `.env` file should look like-
```bash
COHERE=your_api_key_goes_here
```

5. Run the app
```bash
python main.py
```