# Authentication Implementation Guide

## Overview

Secure authentication has been implemented for the Innovo Agent application with:
- User registration with password hashing (bcrypt)
- User login with password verification
- Email domain validation (@innovo-consulting.de or @gmail.com)
- Proper error handling and user feedback

## Installation

### Backend Dependencies

Navigate to the `backend` directory and install Python dependencies:

```bash
cd backend
pip install -r requirements.txt
```

**Required packages:**
- `fastapi==0.115.0` - Web framework
- `uvicorn[standard]==0.32.0` - ASGI server
- `sqlalchemy==2.0.36` - ORM
- `passlib[bcrypt]==1.7.4` - Password hashing
- `python-multipart==0.0.12` - Form data handling

### Frontend

The frontend already has all necessary dependencies. No additional packages are required.

## Running the Application

### 1. Start the Backend Server

```bash
cd backend
uvicorn main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`

### 2. Start the Frontend

In a separate terminal:

```bash
cd frontend
npm run dev
```

The frontend will be available at `http://localhost:5173` (or the port Vite assigns)

### 3. Configure API URL (Optional)

If your backend runs on a different URL, create a `.env` file in the `frontend` directory:

```
VITE_API_URL=http://localhost:8000
```

## Database

The application uses SQLite by default. The database file `innovo.db` will be created automatically in the `backend` directory on first run.

To use PostgreSQL instead, set the `DATABASE_URL` environment variable:
```bash
export DATABASE_URL="postgresql://user:password@localhost/innovo"
```

## API Endpoints

### POST /auth/register

Create a new user account.

**Request:**
```json
{
  "email": "user@innovo-consulting.de",
  "password": "password123"
}
```

**Success Response (201):**
```json
{
  "success": true,
  "message": "Account created successfully"
}
```

**Error Responses:**
- `409 Conflict`: Account already exists
- `400 Bad Request`: Validation error (invalid email domain or password too short)

### POST /auth/login

Authenticate and log in.

**Request:**
```json
{
  "email": "user@innovo-consulting.de",
  "password": "password123"
}
```

**Success Response (200):**
```json
{
  "success": true,
  "message": "Login successful"
}
```

**Error Responses:**
- `404 Not Found`: User not found
- `401 Unauthorized`: Incorrect password

## Manual Testing Steps

### Test Case 1: Register a New User

1. Open the application in your browser
2. Click "Create Account" tab
3. Enter:
   - Email: `test@innovo-consulting.de`
   - Password: `test123`
4. Click "Create Account"
5. **Expected**: Button shows "Processing...", then navigates to `/projects` page

### Test Case 2: Login Success

1. Make sure you've registered a user (Test Case 1)
2. Click "Login" tab
3. Enter:
   - Email: `test@innovo-consulting.de`
   - Password: `test123`
4. Click "Login"
5. **Expected**: Button shows "Processing...", then navigates to `/projects` page

### Test Case 3: Login - User Not Found

1. Click "Login" tab
2. Enter:
   - Email: `nonexistent@innovo-consulting.de`
   - Password: `anypassword`
3. Click "Login"
4. **Expected**: Error message displays: "User not found. Please create an account."

### Additional Test Cases

**Test Case 4: Register - Duplicate Email**
1. Try to register with an email that already exists
2. **Expected**: Error message: "Account already exists. Please log in."

**Test Case 5: Login - Wrong Password**
1. Login with correct email but wrong password
2. **Expected**: Error message: "Incorrect password."

**Test Case 6: Invalid Email Domain**
1. Try to register with email like `test@example.com`
2. **Expected**: Client-side validation error: "Email must end with @innovo-consulting.de or @gmail.com"

**Test Case 7: Password Too Short**
1. Try to register with password less than 6 characters
2. **Expected**: Client-side validation error: "Password must be at least 6 characters."

## Security Features

✅ **Password Hashing**: Passwords are hashed using bcrypt before storage  
✅ **Case-Insensitive Email**: Email addresses are normalized to lowercase  
✅ **Email Domain Validation**: Only @innovo-consulting.de or @gmail.com allowed  
✅ **No Password Leakage**: Passwords are never logged or returned in responses  
✅ **Proper HTTP Status Codes**: 201 for creation, 409 for conflicts, 404 for not found, 401 for unauthorized  
✅ **Error Messages**: Clear, user-friendly error messages without exposing sensitive information

## Files Changed

### Backend Files Created:
- `backend/main.py` - FastAPI application entry point
- `backend/app/__init__.py` - Package init
- `backend/app/database.py` - Database configuration
- `backend/app/models.py` - SQLAlchemy User model
- `backend/app/schemas.py` - Pydantic schemas for validation
- `backend/app/utils.py` - Password hashing utilities
- `backend/app/routers/__init__.py` - Routers package init
- `backend/app/routers/auth.py` - Authentication endpoints
- `backend/requirements.txt` - Python dependencies
- `backend/README.md` - Backend documentation

### Frontend Files Modified:
- `frontend/src/pages/LoginPage/LoginPage.tsx` - Updated to call backend API with error handling and loading states

## Database Schema

```sql
CREATE TABLE users (
    email VARCHAR PRIMARY KEY,
    password_hash VARCHAR NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## Troubleshooting

**Issue**: "Network error. Please check if the backend server is running."
- **Solution**: Make sure the backend server is running on port 8000

**Issue**: CORS errors in browser console
- **Solution**: Verify the frontend URL is in the CORS allowed origins in `backend/main.py`

**Issue**: Database errors
- **Solution**: Ensure you have write permissions in the `backend` directory for SQLite, or configure PostgreSQL properly

**Issue**: Import errors in Python
- **Solution**: Make sure you're in a virtual environment and all dependencies are installed: `pip install -r requirements.txt`

