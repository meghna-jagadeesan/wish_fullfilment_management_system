# WishBridge — Multi-Stakeholder Wish Fulfilment Management System

A Software Engineering project prototype connecting people with verified essential needs to donors. It supports medical treatment, education, food, shelter, accessibility and emergency essentials.

## Stakeholders
- **Beneficiary / Guardian:** submits a request and optional supporting document.
- **Administrator / Verifier:** reviews and verifies/rejects requests before they are publicly listed.
- **Donor:** browses verified requests and records a contribution.
- **System:** tracks goals, contributions, progress and fulfilment status.

## Technology
Python, Flask, SQLite, HTML, CSS, Jinja templates.

## Run on Windows using VS Code
1. Extract this ZIP.
2. Open the `wish_fulfillment_charity` folder in VS Code.
3. Select **Terminal → New Terminal**.
4. Run:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

5. Open `http://127.0.0.1:5000` in your browser.
6. Keep the terminal running while using the website. Press `Ctrl+C` to stop the server.

If `py` is unavailable, replace it with `python`. The commands above avoid needing to activate the virtual environment.

## Demo administrator account
- Email: `admin@wish.local`
- Password: `Admin123!`

Use the administrator to review requests. Create normal accounts through **Join us** and select either beneficiary or donor.

## Suggested demo flow
1. Register a **beneficiary** account.
2. Submit a wish (for example, medical treatment) with a goal amount and optional PDF/JPG/PNG supporting file.
3. Log out and log in as administrator; verify or reject the request.
4. Log out and register/log in as a **donor**.
5. Browse verified wishes, open one and record a contribution.
6. View the updated funding progress and donor dashboard.

## Important limitations
- This is an educational prototype. Contributions are only recorded in the local database; **no real payment or money transfer occurs**.
- Do not use real patient information in a public demo. Uploads are limited to PDF/JPG/PNG and 5 MB; only the admin can download submitted evidence through the app.
- Before real-world use, add secure payment-provider integration, stronger privacy/security controls, audit logs, CSRF protection, proper production configuration, and independent verification procedures. Change the development secret key before deployment.
- Database file `wishbridge.db` is created automatically in the project folder on first run. Delete it only if you want to reset all local demo data.
