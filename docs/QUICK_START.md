# Quick Start Guide - Running the Innovo Agent Application

## Prerequisites

- **Python 3.8+** installed
- **Node.js 16+** and npm installed
- **pip** (Python package manager)

## Step-by-Step Setup

### Step 1: Verify Prerequisites

Check if you have Python and Node.js installed:

```bash
python --version  # Should show Python 3.8 or higher
node --version    # Should show Node.js 16 or higher
npm --version     # Should show npm version
```

### Step 2: Set Up Backend

1. **Navigate to backend directory:**
   ```bash
   cd backend
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv venv
   ```

3. **Activate virtual environment:**
   - **On macOS/Linux:**
     ```bash
     source venv/bin/activate
     ```
   - **On Windows:**
     ```bash
     venv\Scripts\activate
     ```

4. **Install backend dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Start the backend server:**
   ```bash
   uvicorn main:app --reload --port 8000
   ```

   You should see output like:
   ```
   INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
   INFO:     Application startup complete.
   ```

   **Keep this terminal window open!** The backend server needs to keep running.

### Step 3: Set Up Frontend (New Terminal)

Open a **new terminal window** (keep the backend running in the first terminal).

1. **Navigate to frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install frontend dependencies (if not already installed):**
   ```bash
   npm install
   ```

3. **Start the frontend development server:**
   ```bash
   npm run dev
   ```

   You should see output like:
   ```
   VITE v7.x.x  ready in xxx ms

   ➜  Local:   http://localhost:5173/
   ➜  Network: use --host to expose
   ```

### Step 4: Access the Application

1. Open your web browser
2. Navigate to: **http://localhost:5173** (or the URL shown in your terminal)
3. You should see the **Innovo Agent Login** page

### Step 5: Test the Application

1. **Create a new account:**
   - Click "Create Account" tab
   - Enter email: `test@innovo-consulting.de`
   - Enter password: `test123` (minimum 6 characters)
   - Click "Create Account"
   - Should navigate to the Projects page

2. **Log out and log back in:**
   - Navigate back to `/login` (or refresh and it should redirect)
   - Click "Login" tab
   - Enter the same credentials
   - Should successfully log in

## Troubleshooting

### Backend Issues

**Problem: `ModuleNotFoundError` or import errors**
- Solution: Make sure you activated the virtual environment and installed dependencies:
  ```bash
  source venv/bin/activate  # or venv\Scripts\activate on Windows
  pip install -r requirements.txt
  ```

**Problem: Port 8000 already in use**
- Solution: Either stop the other process using port 8000, or run on a different port:
  ```bash
  uvicorn main:app --reload --port 8001
  ```
  Then update frontend `.env` file with `VITE_API_URL=http://localhost:8001`

**Problem: Database errors**
- Solution: Make sure you have write permissions in the `backend` directory. The SQLite database will be created automatically.

### Frontend Issues

**Problem: `npm: command not found`**
- Solution: Install Node.js from https://nodejs.org/

**Problem: Port 5173 already in use**
- Solution: Vite will automatically use the next available port. Check the terminal output for the actual URL.

**Problem: "Network error" when trying to login/register**
- Solution: 
  1. Make sure the backend server is running (check the first terminal)
  2. Verify backend is accessible at http://localhost:8000
  3. Check browser console for CORS errors

**Problem: Frontend can't connect to backend**
- Solution: Create a `.env` file in the `frontend` directory:
  ```
  VITE_API_URL=http://localhost:8000
  ```
  Then restart the frontend server.

## Stopping the Servers

- **Backend**: Press `CTRL+C` in the backend terminal
- **Frontend**: Press `CTRL+C` in the frontend terminal

## Verifying Everything Works

1. **Backend Health Check:**
   - Open: http://localhost:8000/health
   - Should see: `{"status":"ok"}`

2. **Backend API Docs:**
   - Open: http://localhost:8000/docs
   - Should see FastAPI interactive documentation

3. **Frontend:**
   - Open: http://localhost:5173
   - Should see the login page

## Project Structure

```
Demo_innovo/
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── requirements.txt     # Python dependencies
│   ├── innovo.db            # SQLite database (created automatically)
│   └── app/
│       ├── database.py      # Database configuration
│       ├── models.py        # User model
│       ├── schemas.py       # Pydantic schemas
│       ├── utils.py         # Password hashing
│       └── routers/
│           └── auth.py       # Auth endpoints
│
└── frontend/
    ├── package.json         # Node dependencies
    └── src/
        └── pages/
            └── LoginPage/
                └── LoginPage.tsx  # Updated login page
```

## Next Steps

Once everything is running:
- Test user registration
- Test user login
- Explore the Projects page
- Check the database file (`backend/innovo.db`) to see stored users

For detailed authentication documentation, see `AUTHENTICATION_SETUP.md`

