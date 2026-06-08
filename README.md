# HRMS Backend API - AB Enterprises

Human Resource Management System (HRMS) Backend developed using **Python Django** and **Django REST Framework** for **AB Enterprises**.

This system provides a centralized platform for managing employees, payroll processing, salary slip generation, employee records, attendance-related operations, document management, and administrative workflows through secure REST APIs.

---

## 📌 Project Overview

The HRMS Backend serves as the core service layer for the AB Enterprises Human Resource Management ecosystem.

### Key Features

* Employee Management
* Department Management
* Designation Management
* Payroll Management
* Salary Structure Configuration
* Salary Slip Generation
* Employee Document Management
* Authentication & Authorization
* Role-Based Access Control
* File Upload Management
* PDF Generation
* Excel Report Generation
* Background Task Processing
* API Documentation
* Redis Caching Support
* JWT Authentication
* Audit-Friendly Data Management

---

## 🏗 Technology Stack

### Backend Framework

* Python 3.10+
* Django 4.2
* Django REST Framework

### Database

* MySQL

### Authentication

* JWT Authentication
* Simple JWT

### Caching

* Redis
* Django Redis

### Documentation

* Swagger UI
* ReDoc
* OpenAPI Specification

### Reporting

* WeasyPrint
* ReportLab
* OpenPyXL
* XlsxWriter
* Python DOCX

### Deployment

* Gunicorn
* Nginx
* Linux Server

---

## 📂 Project Structure

```bash
hrms_backend/
│
├── config/
│   ├── settings/
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
│
├── apps/
│   ├── authentication/
│   ├── employee/
│   ├── payroll/
│   ├── department/
│   ├── designation/
│   ├── reports/
│   ├── salary_slips/
│   └── common/
│
├── media/
├── static/
├── requirements.txt
├── manage.py
└── README.md
```

---

## 🔐 Authentication

The system uses JWT-based authentication.

### Login Flow

1. User submits credentials.
2. System validates user.
3. Access Token generated.
4. Refresh Token generated.
5. Subsequent API calls use Bearer Token.

### Authorization Header

```http
Authorization: Bearer <access_token>
```

---

## 👥 Employee Management

The platform supports:

* Employee onboarding
* Employee profile management
* Employee document uploads
* Employee status tracking
* Employee search and filtering
* Employee reporting hierarchy
* Employment history management

### Employee Information

* Employee ID
* Full Name
* Email
* Mobile Number
* Department
* Designation
* Joining Date
* Employment Type
* Bank Details
* Address Information
* Profile Image
* Supporting Documents

---

## 🏢 Department Management

Manage organizational departments:

* Create Department
* Update Department
* Delete Department
* Department Listing
* Department Employee Mapping

Examples:

* Human Resources
* Information Technology
* Finance
* Operations
* Administration

---

## 💼 Designation Management

Manage company roles and designations:

Examples:

* Software Engineer
* Senior Engineer
* Team Lead
* HR Executive
* Finance Manager
* Operations Manager

Features:

* Create Designation
* Update Designation
* Delete Designation
* Employee Mapping

---

## 💰 Payroll Management

Comprehensive payroll engine for employee salary processing.

### Payroll Components

#### Earnings

* Basic Salary
* House Rent Allowance (HRA)
* Special Allowance
* Conveyance Allowance
* Medical Allowance
* Bonus
* Incentives

#### Deductions

* Provident Fund (PF)
* Professional Tax
* Income Tax
* ESI
* Loan Deductions
* Other Deductions

### Payroll Features

* Monthly Salary Processing
* Salary Revision Management
* Payroll Calculation
* Payroll Approval Workflow
* Payroll Reports
* Payroll History

---

## 📄 Salary Slip Generation

Automated salary slip generation with PDF export support.

### Salary Slip Includes

* Employee Details
* Payroll Period
* Earnings Breakdown
* Deductions Breakdown
* Net Pay
* Company Details
* Authorized Signatory Information

### Export Formats

* PDF
* Excel

---

## 📊 Reports & Exports

### Supported Reports

* Employee Master Report
* Payroll Summary Report
* Salary Register
* Department-wise Report
* Designation-wise Report
* Employee Salary History
* Monthly Payroll Report

### Export Options

* Excel (.xlsx)
* PDF (.pdf)
* DOCX (.docx)

---

## 📚 API Documentation

Interactive API documentation is available through:

### Swagger

```bash
/api/docs/
```

### ReDoc

```bash
/api/redoc/
```

### OpenAPI Schema

```bash
/api/schema/
```

---

## ⚙️ Installation

### Clone Repository

```bash
git clone https://github.com/your-org/hrms-ab-enterprises-backend.git

cd hrms-ab-enterprises-backend
```

### Create Virtual Environment

```bash
python -m venv venv
```

### Activate Virtual Environment

Linux/Mac

```bash
source venv/bin/activate
```

Windows

```bash
venv\Scripts\activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 🗄 Database Configuration

Create a MySQL database:

```sql
CREATE DATABASE hrms_db;
```

Configure environment variables.

---

## 🔧 Environment Variables

Create a `.env` file:

```env
DEBUG=True

SECRET_KEY=your-secret-key

ALLOWED_HOSTS=*

DB_NAME=hrms_db
DB_USER=root
DB_PASSWORD=password
DB_HOST=localhost
DB_PORT=3306

REDIS_HOST=localhost
REDIS_PORT=6379

ACCESS_TOKEN_LIFETIME=60
REFRESH_TOKEN_LIFETIME=7
```

---

## 🚀 Running the Application

### Apply Migrations

```bash
python manage.py makemigrations

python manage.py migrate
```

### Create Superuser

```bash
python manage.py createsuperuser
```

### Run Development Server

```bash
python manage.py runserver
```

Application:

```bash
http://127.0.0.1:8000
```

---

## 🔄 Background Tasks

Background jobs are managed using:

```text
django-background-tasks
```

Examples:

* Salary Slip Generation
* Report Exports
* Scheduled Payroll Jobs
* Notification Processing

Run background worker:

```bash
python manage.py process_tasks
```

---

## ⚡ Redis Integration

Redis is used for:

* API Caching
* Session Storage
* Performance Optimization
* Temporary Data Storage

Start Redis:

```bash
redis-server
```

---

## 📦 Major Dependencies

### Core Framework

* Django
* Django REST Framework
* django-filter

### Authentication

* djangorestframework-simplejwt
* PyJWT

### Documentation

* drf-spectacular
* drf-spectacular-sidecar
* drf-yasg

### Database

* mysqlclient
* PyMySQL

### Caching

* redis
* django-redis

### Reporting

* WeasyPrint
* ReportLab
* OpenPyXL
* XlsxWriter
* Python DOCX
* PyPDF2

### Utilities

* python-decouple
* python-dotenv
* django-cleanup
* django-cors-headers

---

## 🔒 Security Features

* JWT Authentication
* Password Hashing
* CSRF Protection
* CORS Configuration
* Secure File Handling
* Environment-Based Configuration
* Role-Based Access Controls

---

## 🧪 Testing

Run tests:

```bash
python manage.py test
```

Run specific app tests:

```bash
python manage.py test app_name
```

---

## 🚀 Production Deployment

Recommended Production Stack:

```text
Linux (Ubuntu)
Nginx
Gunicorn
MySQL
Redis
Django
```

Start Gunicorn:

```bash
gunicorn config.wsgi:application
```

---

## 📝 Versioning

Current Version:

```text
v1.0.0
```

API Base URL:

```text
/api/v1/
```

---

## 👨‍💻 Developed For

**AB Enterprises**

Enterprise Human Resource Management System (HRMS)

Modules:

* Employee Management
* Payroll Management
* Salary Processing
* Salary Slip Generation
* Reporting & Analytics
* Administrative Controls

---

## 📄 License

This repository contains proprietary software developed exclusively for AB Enterprises.

Unauthorized copying, modification, distribution, or commercial usage without written permission is prohibited.

© AB Enterprises. All Rights Reserved.
