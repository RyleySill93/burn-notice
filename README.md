# Burn Notice - Modern Full-Stack Application Blueprint

A production-ready full-stack application built with React, TypeScript, FastAPI, and PostgreSQL. This project serves as a blueprint for building modern web applications with enterprise-grade features.

## 🚀 Features

### Authentication & Security
- **Multiple Authentication Methods**: Password, Magic Link, Azure SSO, OIDC SSO
- **Multi-Factor Authentication**: TOTP, SMS, Email verification
- **Comprehensive Security Headers**: CSP, HSTS, X-Frame-Options, and more
- **CORS Protection**: Configurable and restrictive CORS policies
- **Password Reset Flow**: Secure token-based password recovery with auto-login
- **Session Management**: JWT tokens with refresh token rotation
- **IP Whitelisting**: Optional IP-based access control

### Backend Architecture
- **FastAPI**: High-performance async Python web framework
- **SQLAlchemy ORM**: Type-safe database operations
- **Alembic Migrations**: Version-controlled database schema
- **Domain-Driven Design**: Organized by business domains
- **Pydantic Validation**: Robust input validation and serialization
- **Dramatiq**: Asynchronous task processing
- **WebSocket Support**: Real-time communication capabilities

### Frontend Architecture
- **React 18**: Modern React with hooks and concurrent features
- **TypeScript**: Full type safety across the application
- **React Router v7**: Type-safe routing with file-based organization
- **React Query**: Powerful data fetching and caching
- **Orval**: Auto-generated API client from OpenAPI spec
- **Tailwind CSS**: Utility-first styling
- **Shadcn/ui**: Beautiful and accessible UI components

### Developer Experience
- **Environment-Based Configuration**: Easy deployment across environments
- **Comprehensive Logging**: Structured logging with request tracking
- **Error Handling**: User-friendly error messages with proper logging
- **Make Commands**: Simplified development workflow
- **Hot Reload**: Fast development with automatic reloading
- **Type Generation**: Auto-sync between backend and frontend types

## 🔒 Security Features

### Recently Implemented Security Enhancements

#### 1. Restricted CORS Configuration
- Changed from permissive `allow_methods=['*']` and `allow_headers=['*']` to specific allowed values
- Configurable via environment variables:
  - `CORS_ALLOWED_METHODS`: Default: GET, POST, PUT, PATCH, DELETE, OPTIONS
  - `CORS_ALLOWED_HEADERS`: Default: Accept, Content-Type, Authorization, etc.

#### 2. Comprehensive Security Headers
All responses include security headers to protect against common web vulnerabilities:

- **X-Frame-Options**: DENY - Prevents clickjacking
- **X-Content-Type-Options**: nosniff - Prevents MIME type sniffing
- **Strict-Transport-Security**: Forces HTTPS (production only)
- **Content-Security-Policy**: Restricts resource loading to prevent XSS
- **Referrer-Policy**: Controls referrer information leakage
- **X-XSS-Protection**: Legacy XSS protection for older browsers
- **Permissions-Policy**: Restricts browser features

Configuration via environment variables:
- `ENABLE_SECURITY_HEADERS`: Toggle security headers (default: true)
- `ENABLE_HSTS`: Enable HSTS header (default: false for local, true for production)
- `CSP_POLICY`: Customize Content-Security-Policy as needed

#### 3. Enhanced Password Reset Flow
- Secure token-based password reset via email
- Auto-login after successful password reset
- Protection against email enumeration
- One-time use tokens with expiration

## 🛠 Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- Redis (for caching and WebSocket support)

### Quick Start

1. Clone the repository
```bash
git clone <repository-url>
cd burn-notice
```

2. Set up environment variables
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Install dependencies
```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

4. Initialize the database
```bash
cd backend
make setup-db
make migrate
```

5. Start the development servers
```bash
# Terminal 1: Backend
make server

# Terminal 2: Frontend
cd frontend
npm run dev

# Terminal 3: Worker (for async tasks)
cd backend
make worker
```

## 📦 Environment Variables

### Required Variables
```bash
# Database
DB_NAME=burn-notice
DB_USER=burn-notice
DB_PASSWORD=your_password

# Security
SECRET_KEY=your-secret-key
BACKEND_CORS_ORIGINS=http://localhost:5173

# Email
EMAIL_FROM_ADDRESS=noreply@yourapp.com

# AWS (for file storage)
AWS_STORAGE_BUCKET_NAME=your-bucket-name

# Company Info
COMPANY_NAME=YourCompany
VITE_COMPANY_NAME="Your Company, Inc."
VITE_SUPPORT_EMAIL=support@yourcompany.com
VITE_COMPANY_WEBSITE=www.yourcompany.com
VITE_LOGO_URL=https://your-logo-url.com/logo.png
```

### Optional Security Configuration
```bash
# CORS Configuration
CORS_ALLOWED_METHODS=GET,POST,PUT,PATCH,DELETE,OPTIONS
CORS_ALLOWED_HEADERS=Accept,Content-Type,Authorization

# Security Headers
ENABLE_SECURITY_HEADERS=true
ENABLE_HSTS=false  # Set to true in production
CSP_POLICY="default-src 'self'; ..."  # Customize as needed
```

## 🏗 Project Structure

```
burn-notice/
├── backend/
│   ├── src/
│   │   ├── app/           # Application domains (todos, chat, etc.)
│   │   ├── common/        # Shared utilities and middleware
│   │   ├── core/          # Core business logic (auth, users, etc.)
│   │   ├── network/       # Network layer (HTTP, WebSocket, Database)
│   │   └── platform/      # Platform services (email, SMS, files)
│   ├── migrations/        # Database migrations
│   └── tests/            # Test suite
├── frontend/
│   ├── src/
│   │   ├── components/    # Reusable components
│   │   ├── views/        # Page components
│   │   ├── generated/    # Auto-generated API client
│   │   ├── hooks/        # Custom React hooks
│   │   └── services/     # Business logic services
│   └── public/           # Static assets
└── Makefile             # Development commands
```

## 🧪 Testing

```bash
# Backend tests
cd backend
make test

# Frontend tests
cd frontend
npm test
```

## 📝 API Documentation

When running locally, API documentation is available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🚢 Deployment

The application is designed to be easily deployed to various platforms:
- **Backend**: Any platform supporting Python (AWS, GCP, Azure, Heroku)
- **Frontend**: Static hosting (Vercel, Netlify, CloudFront)
- **Database**: PostgreSQL (RDS, Cloud SQL, managed services)
- **Redis**: Managed Redis services (ElastiCache, Redis Cloud)

## 📄 License

[Your License Here]

## 🤝 Contributing

[Your contribution guidelines here]