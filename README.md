# PromptForum Backend API

A complete forum backend system built with FastAPI, featuring authentication, categories, tags, posts with file uploads, and more.

## Features

### 🔐 Authentication System
- ✅ Email/Password Authentication
- ✅ Google OAuth Integration
- ✅ OTP Email Verification
- ✅ Password Reset with OTP
- ✅ JWT Access & Refresh Tokens
- ✅ Secure Password Hashing (bcrypt)

### 📁 Forum System
- ✅ Categories (Hierarchical - Parent/Child)
- ✅ Tags (Grouped & Colored)
- ✅ 9 Parent Categories with 68 Subcategories
- ✅ 178 Tags across 12 Groups
- ✅ **Forum Posts/Questions** 🆕
- ✅ **Secure File Uploads** 🆕
- ✅ **Auto-create Tags** 🆕
- ✅ **Vote System** 🆕
- ✅ **Search & Filters** 🆕
- ✅ Database Seed Script

### 🛠️ Technical Features
- ✅ MongoDB Database
- ✅ Clean Architecture (Models, Services, Routes)
- ✅ Professional Email Templates
- ✅ Standardized API Responses
- ✅ File Upload Security (type & size validation)
- ✅ CORS Enabled
- ✅ API Documentation (Swagger/ReDoc)
- ✅ GET & POST Only Convention

## Project Structure

```
backend/
├── app/
│   ├── models/               # Pydantic schemas (NO __init__.py)
│   │   ├── auth/            # Authentication models
│   │   │   ├── user.py     # User schemas
│   │   │   ├── otp.py      # OTP schemas
│   │   │   └── token.py    # Token & auth request schemas
│   │   └── forum/           # Forum models
│   │       ├── category.py # Category schemas
│   │       └── tag.py      # Tag schemas
│   ├── services/            # Business logic (NO __init__.py)
│   │   ├── auth/           # Authentication services
│   │   │   ├── security.py      # JWT & password hashing
│   │   │   ├── otp.py           # OTP generation & verification
│   │   │   ├── email.py         # Email sending service
│   │   │   ├── google_auth.py   # Google OAuth
│   │   │   └── auth_service.py  # Main auth service
│   │   └── forum/          # Forum services
│   │       ├── category.py # Category database operations
│   │       └── tag.py      # Tag database operations
│   ├── routes/             # API endpoints (NO __init__.py)
│   │   ├── auth/          # Authentication routes
│   │   │   ├── auth_routes.py   # Auth endpoints
│   │   │   └── dependencies.py  # Auth dependencies
│   │   └── forum/         # Forum routes
│   │       ├── category_routes.py  # Category endpoints
│   │       └── tag_routes.py       # Tag endpoints
│   ├── utils/              # Utilities (NO __init__.py)
│   │   └── response.py    # Standardized responses
│   ├── database.py         # MongoDB connection
│   └── main.py             # FastAPI application
├── seed_database.py        # Database seed script
├── .env                    # Environment variables
├── requirements.txt        # Python dependencies
├── QUICK_START_FORUM.md    # Quick start guide
├── API_ENDPOINTS.md        # API documentation
├── SEED_DATABASE.md        # Seed data guide
└── README.md               # This file
```

**Note:** Zero `__init__.py` files! All imports use direct paths for maximum simplicity.

## Installation

### Prerequisites

- Python 3.8+
- MongoDB (local or cloud)
- SMTP server (Gmail recommended for development)

### Step 1: Clone and Setup

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Environment Configuration

**A `.env` file has been created with default values. Update it with your actual credentials:**

Edit the `.env` file with your configurations:

#### Required Settings:

1. **SECRET_KEY**: Generate a secure key
   ```bash
   # Generate using Python
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

2. **MongoDB**: 
   - Local: `mongodb://localhost:27017`
   - Cloud (MongoDB Atlas): Get connection string from your cluster

3. **Email (Gmail)**:
   - Enable 2-Factor Authentication on your Gmail account
   - Generate an App Password: https://myaccount.google.com/apppasswords
   - Use the app password in `SMTP_PASSWORD`

4. **Google OAuth** (optional):
   - Go to: https://console.cloud.google.com/
   - Create a new project
   - Enable Google+ API
   - Create OAuth 2.0 credentials
   - Add authorized redirect URIs
   - Copy Client ID and Client Secret to `.env`

### Step 3: Start MongoDB

```bash
# If using local MongoDB, make sure it's running
# Windows: MongoDB should be running as a service
# macOS: brew services start mongodb-community
# Linux: sudo systemctl start mongod
```

### Step 4: Seed the Database

```bash
# Run the seed script to populate categories and tags
python seed_database.py
```

This will create:
- 77 categories (9 parent + 68 subcategories)
- 178 tags across 12 groups

### Step 5: Run the Application

```bash
# Start the FastAPI server
uvicorn app.main:app --reload

# Or with custom host and port
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at:
- API: http://localhost:8000
- Swagger Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

For complete API documentation, see [API_ENDPOINTS.md](API_ENDPOINTS.md)

### Authentication (All endpoints prefixed with `/api/auth`)

#### 1. Sign Up with Email
```http
POST /api/auth/signup
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securePassword123",
  "full_name": "John Doe"
}
```

#### 2. Verify Email (with OTP)
```http
POST /api/auth/verify-email
Content-Type: application/json

{
  "email": "user@example.com",
  "otp_code": "123456"
}
```

#### 3. Login with Email
```http
POST /api/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securePassword123"
}
```

#### 4. Login with Google
```http
POST /api/auth/google
Content-Type: application/json

{
  "token": "google-oauth-token"
}
```

#### 5. Refresh Token
```http
POST /api/auth/refresh
Content-Type: application/json

{
  "refresh_token": "your-refresh-token"
}
```

#### 6. Forgot Password
```http
POST /api/auth/forgot-password
Content-Type: application/json

{
  "email": "user@example.com"
}
```

#### 7. Reset Password
```http
POST /api/auth/reset-password
Content-Type: application/json

{
  "email": "user@example.com",
  "otp_code": "123456",
  "new_password": "newSecurePassword123"
}
```

#### 8. Resend OTP
```http
POST /api/auth/resend-otp
Content-Type: application/json

{
  "email": "user@example.com"
}
```

#### 9. Get Current User
```http
GET /api/auth/me
Authorization: Bearer <access_token>
```

#### 10. Logout
```http
POST /api/auth/logout
Authorization: Bearer <access_token>
```

### Categories (All endpoints prefixed with `/api/categories`)

```http
GET  /api/categories/all              # Get all categories
GET  /api/categories/tree             # Get category tree (parent + subcategories)
GET  /api/categories/parent           # Get only parent categories
GET  /api/categories/{slug}           # Get single category
POST /api/categories/create           # Create category (auth required)
POST /api/categories/{id}/update      # Update category (auth required)
POST /api/categories/{id}/delete      # Delete category (auth required)
```

### Tags (All endpoints prefixed with `/api/tags`)

```http
GET  /api/tags/all                    # Get all tags
GET  /api/tags/popular?limit=50       # Get popular tags
GET  /api/tags/group/{group_name}     # Get tags by group
GET  /api/tags/search?q=query         # Search tags
GET  /api/tags/{slug}                 # Get single tag
POST /api/tags/create                 # Create tag (auth required)
POST /api/tags/{id}/update            # Update tag (auth required)
POST /api/tags/{id}/delete            # Delete tag (auth required)
```

## Authentication Flow

### Email/Password Flow:
1. User signs up → OTP sent to email
2. User verifies email with OTP → Account activated
3. User logs in → Receives access & refresh tokens
4. User accesses protected routes with access token

### Google OAuth Flow:
1. User clicks "Sign in with Google" on frontend
2. Frontend gets Google token
3. Frontend sends token to `/auth/google`
4. Backend verifies token and creates/logs in user
5. User receives access & refresh tokens

### Password Reset Flow:
1. User requests password reset → OTP sent to email
2. User submits OTP + new password
3. Password updated successfully

## Security Features

- **Password Hashing**: bcrypt with salt
- **JWT Tokens**: Separate access (30min) and refresh (7 days) tokens
- **OTP Expiration**: 10 minutes
- **OTP Attempts**: Limited to 5 attempts
- **Email Verification**: Required for email/password accounts
- **Token Validation**: Validates token type and expiration

## Database Collections

### Users Collection (Authentication)
```json
{
  "_id": "ObjectId",
  "email": "user@example.com",
  "full_name": "John Doe",
  "hashed_password": "bcrypt_hash",
  "auth_provider": "email",  // "email" or "google"
  "google_id": "google_user_id",
  "is_verified": true,
  "is_active": true,
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00"
}
```

### OTPs Collection (Authentication)
```json
{
  "_id": "ObjectId",
  "email": "user@example.com",
  "otp_code": "123456",
  "created_at": "2024-01-01T00:00:00",
  "expires_at": "2024-01-01T00:10:00",
  "is_used": false,
  "attempts": 0
}
```

### Categories Collection (Forum)
```json
{
  "_id": "ObjectId",
  "name": "Prompts",
  "slug": "prompts",
  "description": "All about prompt engineering...",
  "parent_id": null,  // null for parent, ObjectId for subcategory
  "icon": "💬",
  "order": 1,
  "post_count": 0,
  "is_active": true,
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00"
}
```

### Tags Collection (Forum)
```json
{
  "_id": "ObjectId",
  "name": "prompt-template",
  "slug": "prompt-template",
  "description": null,
  "group": "Prompt Types",
  "color": "#3B82F6",
  "usage_count": 0,
  "is_active": true,
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00"
}
```

## Standardized API Responses

All endpoints return consistent response format:

### Success Response
```json
{
  "success": true,
  "message": "Operation successful",
  "data": { ... }
}
```

### Error Response
```json
{
  "success": false,
  "message": "Error message",
  "errors": { ... }
}
```

### HTTP Status Codes
- `200 OK`: Success
- `400 Bad Request`: Invalid input
- `401 Unauthorized`: Authentication required
- `404 Not Found`: Resource not found
- `422 Unprocessable Entity`: Validation error
- `500 Internal Server Error`: Server error

## Quick Testing Guide

### Using Swagger UI
1. Open http://localhost:8000/docs
2. Test authentication flow:
   - Try `/api/auth/signup`
   - Check your email for OTP
   - Verify with `/api/auth/verify-email`
   - Login with `/api/auth/login`
3. Test forum endpoints:
   - Get categories: `/api/categories/tree`
   - Get tags: `/api/tags/all`
   - Search tags: `/api/tags/search`

### Using cURL
```bash
# Get category tree
curl http://localhost:8000/api/categories/tree

# Get popular tags
curl http://localhost:8000/api/tags/popular?limit=20

# Search tags
curl http://localhost:8000/api/tags/search?q=prompt
```

## Frontend Integration

### Using with React/Vue/Angular:

```javascript
// Sign up
const signup = async (email, password, fullName) => {
  const response = await fetch('http://localhost:8000/api/auth/signup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, full_name: fullName })
  });
  return response.json();
};

// Login
const login = async (email, password) => {
  const response = await fetch('http://localhost:8000/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  });
  const data = await response.json();
  // Store tokens
  localStorage.setItem('access_token', data.access_token);
  localStorage.setItem('refresh_token', data.refresh_token);
  return data;
};

// Access protected route
const getCurrentUser = async () => {
  const token = localStorage.getItem('access_token');
  const response = await fetch('http://localhost:8000/api/auth/me', {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  return response.json();
};

// Get category tree
const getCategories = async () => {
  const response = await fetch('http://localhost:8000/api/categories/tree');
  const data = await response.json();
  return data.data.categories;
};

// Get tags by group
const getTagsByGroup = async (groupName) => {
  const response = await fetch(
    `http://localhost:8000/api/tags/group/${encodeURIComponent(groupName)}`
  );
  const data = await response.json();
  return data.data.tags;
};
```

## Troubleshooting

### Email not sending?
- Check SMTP credentials in `.env`
- For Gmail, ensure you're using an App Password, not your regular password
- Check if 2FA is enabled on your Gmail account

### MongoDB connection error?
- Ensure MongoDB is running
- Check connection string in `.env`
- For MongoDB Atlas, ensure IP whitelist is configured

### Google OAuth not working?
- Verify Google Client ID and Secret
- Check authorized redirect URIs in Google Console
- Ensure Google+ API is enabled

## Production Deployment

### Important Security Steps:
1. Change `SECRET_KEY` to a strong random value
2. Set `DEBUG=False`
3. Use environment-specific `.env` files
4. Enable HTTPS
5. Set proper CORS origins
6. Use a production SMTP service (SendGrid, AWS SES)
7. Implement rate limiting
8. Add request logging
9. Use MongoDB with authentication enabled
10. Implement token blacklisting for logout

### Recommended Services:
- **Hosting**: AWS, Google Cloud, DigitalOcean, Heroku
- **Database**: MongoDB Atlas
- **Email**: SendGrid, AWS SES, Mailgun
- **Monitoring**: Sentry, DataDog

## Contributing

Feel free to submit issues and enhancement requests!

## License

MIT License
