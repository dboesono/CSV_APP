# CSV Processor App

A Streamlit application for cleaning and previewing **Device** and **Alarm** CSV/XLSX datasets, with easy download of processed outputs.

---

## Prerequisites

- **Python 3.8+** installed and on your PATH  
- **pip** (comes with Python)  
- A terminal / PowerShell / Command Prompt (Windows) or shell (macOS/Linux)  

---

## Installation & Setup

1. **Download & extract the ZIP**  
   1. Go to the GitHub repository:  
      https://github.com/dboesono/CSV_APP  
   2. Click **Code ▶ Download ZIP**  
   ![Screenshot of Downloading Steps](asset/github_download_1.png)
   ![Screenshot of Downloading Steps](asset/github_download_2.png)

   3. Save and extract to the Desktop, e.g. `CSV_APP-main.zip`
   4. Inside the zip file, move the `CSV_APP-main` folder outside to the desktop and delete the `CSV_APP-main.zip` file

2. **Open a terminal** from the command prompt and change into the project directory:  
   ```bash
   cd Desktop/CSV_APP-main
   ```

3. **Install Python External Packages:** Write this command line in the command prompt
   ```bash
   pip install -r requirements.txt
   ```

4. **Creating a Launcher:** Go to notepad and copy paste the below code to the empty notepad:
   ```bat
   @echo off
   REM ── Set this to wherever you extracted the CSV_APP folder ──
   set "APP_DIR=%USERPROFILE%\Desktop\CSV_APP-main"

   REM ── Switch to that directory ──
   cd /d "%APP_DIR%"

   REM ── Launch the Streamlit app ──
   streamlit run app.py

   pause
   ```

   Save it as `run_app.bat` file and save it to the desktop. The placement of the files should look like the following:

   ```text
   Desktop/
   ├── CSV_APP-main/
   │   ├── .streamlit/
   │   │   └── config.toml
   │   ├── assets/
   │   ├── app.py
   │   ├── requirements.txt
   │   └── README.md
   └── run_app.bat

4. Once completed. Double-click the `run_app.bat` file to run the app.
