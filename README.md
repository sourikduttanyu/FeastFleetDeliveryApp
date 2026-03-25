# FeastFleet — Serverless Food Delivery Platform

A production-grade, end-to-end food delivery web application built entirely on AWS serverless infrastructure. This project demonstrates full-stack cloud development across 10+ AWS services, covering authentication, real-time order processing, AI/ML integration, full-text search, and event-driven architecture.

> Built as a cloud engineering portfolio project to demonstrate expertise in AWS serverless architecture, distributed systems design, and full-stack development.

---

## Skills Demonstrated

| Area | Technologies |
|------|-------------|
| Cloud Architecture | AWS Lambda, API Gateway, CloudFront, S3 |
| Databases & Search | DynamoDB (NoSQL), OpenSearch (full-text search) |
| Auth & Security | AWS Cognito (JWT, OAuth2 flows), SECRET_HASH signing |
| Event-Driven Design | SQS (async order queue), SNS (pub/sub notifications) |
| AI / ML | SageMaker (ResNet-50 image classification), AWS Lex (NLP chatbot) |
| Geolocation | AWS Location Service (geocoding / reverse geocoding) |
| Email & Messaging | AWS SES (transactional email) |
| Frontend | Vanilla JS, HTML5, CSS3, Axios, AWS API Gateway JS SDK |
| Backend | Python 3, Boto3, requests-aws4auth, opensearch-py |

---

## What It Does

FeastFleet lets users:

- **Search restaurants** by name or cuisine (Italian, Thai, American, Japanese, Mexican, Vegetarian) using full-text search
- **Browse menus**, add items to a persistent cart, and place orders
- **Track delivery** with real-time status updates simulated via Lambda
- **Make restaurant reservations** with live availability checking
- **Chat with an AI assistant** (AWS Lex) for guided ordering
- **Upload food photos** for AI-powered recognition — a SageMaker ResNet-50 model identifies the dish
- **Receive email confirmations** for orders and reservations via AWS SES

---

## System Architecture

```
Browser  ──►  CloudFront (CDN)  ──►  S3 (static frontend)
                                           │
                                    API Gateway (REST)
                                           │
                          ┌────────────────┼───────────────────┐
                          ▼                ▼                   ▼
                    Lambda (auth)    Lambda (business)   Lambda (async)
                          │                │                   ▲
                    Cognito (JWT)    ┌──────┴──────┐          SQS
                                    ▼             ▼      (order queue)
                                DynamoDB    OpenSearch
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
                   SES            SNS         SageMaker
                 (email)      (pub/sub)   (image inference)
                                               │
                                        S3 (image store)
                                               │
                                    Location Service (geocoding)
```

**Key design decisions:**
- All business logic is in Lambda — zero servers to manage or scale
- Orders are processed asynchronously through SQS to decouple placement from fulfillment
- Search uses OpenSearch instead of DynamoDB scans for performance at scale
- Frontend is pure static assets on S3 + CloudFront — no web server needed

---

## Features In Depth

### Authentication (AWS Cognito)
- User registration and login using Cognito User Pools with `USER_PASSWORD_AUTH` flow
- `SECRET_HASH` HMAC-SHA256 signing on all Cognito API calls
- JWT `IdToken` stored in `localStorage`, sent as `Authorization: Bearer` on every request
- Lambda authorizers validate claims via API Gateway — user identity extracted from `requestContext.authorizer.claims.sub`

### Order Processing (SQS + Lambda)
- Placing an order (LF7) validates cart contents and enqueues an SQS message
- A separate consumer Lambda (LF8) processes the queue, updates order status in DynamoDB, and triggers an SES confirmation email
- This decoupling prevents order placement from blocking on downstream failures

### Restaurant Search (OpenSearch)
- Restaurants and menu items are indexed in OpenSearch with `restaurants_index` and `menu_items_index`
- Full-text queries support partial name matches and cuisine-type filtering
- Sync Lambdas (LF17/18/19) keep the OpenSearch index in sync with DynamoDB writes

### Food Image Recognition (SageMaker)
- Users upload a food photo → stored in S3 (LF14)
- SNS triggers LF15, which invokes a SageMaker ResNet-50 endpoint with the image bytes
- Classification result returned to the user with identified food items

### AI Chatbot (AWS Lex)
- `LEX-General-Hander.py` handles all Lex intents for order assistance and restaurant queries
- Stateful conversation context managed within the Lex session

### Reservations (DynamoDB + GSI)
- Reservation availability checked against a `restaurant_id-res_date` composite GSI
- Supports creation, listing, and cancellation with email confirmation

---

## Project Structure

```
FeastFleetDeliveryApp/
├── frontend/
│   ├── index.html                        # Home / restaurant search
│   ├── results.html                      # Search results listing
│   ├── restaurant-info.html              # Restaurant details + map
│   ├── menu.html                         # Menu browsing
│   ├── view-cart.html                    # Cart review
│   ├── order-list.html / order-detail.html   # Order history & tracking
│   ├── reservation-creation.html         # Reservation form
│   ├── view-reservations.html / view-reservation.html
│   ├── chatbot.html                      # Lex chatbot UI
│   ├── upload-image.html                 # Food photo upload
│   ├── login.html / register.html
│   ├── js/                               # Client-side logic (Axios, auth, cart)
│   ├── css/                              # Styling
│   └── apiGateway-js-sdk/                # AWS-generated API client (gitignored)
│
├── lambdas/                              # 24 Python Lambda functions
│   ├── login.py / register.py / logout.py
│   ├── LF1  — restaurant search (OpenSearch)
│   ├── LF2  — get restaurant by ID
│   ├── LF3  — get menu
│   ├── LF4  — add to cart
│   ├── LF6  — view cart
│   ├── LF7  — place order → SQS
│   ├── LF8  — process order from SQS → DynamoDB + SES
│   ├── LF9-1/2 — view order / order list
│   ├── LF10 — simulate delivery status updates
│   ├── LF11–LF13 — reservation availability, creation, view/delete
│   ├── LF14–LF15 — image upload (S3) + SageMaker inference
│   ├── LF17–LF19 — OpenSearch sync on data updates
│   └── LEX-General-Hander.py — chatbot intent routing
│
└── database/
    ├── create_es_indexes.py              # Define OpenSearch index mappings
    ├── upload_data.py                    # Seed DynamoDB + OpenSearch from CSV
    └── restaurant_data_update.py         # Bulk restaurant record updates
```

---

## Data Model (DynamoDB)

| Table | Partition Key | Notable Indexes |
|-------|--------------|-----------------|
| `User` | `user_id` | GSI on `email` |
| `Restaurant` | `restaurant_id` | — |
| `Menu_Items` | `item_id` | FK: `restaurant_id` |
| `Cart` | `user_id` | One active cart per user |
| `Order` | `order_id` | GSI on `user_id` |
| `Reservation` | `reservation_id` | GSI on `restaurant_id-res_date` |
| `Delivery_Tracking` | `order_id` | — |

---

## API Overview

Base URL: `https://930lk1e388.execute-api.us-east-1.amazonaws.com/dev`

| Method | Endpoint | Lambda | Description |
|--------|----------|--------|-------------|
| POST | `/auth/login` | login.py | Cognito login, returns JWT |
| POST | `/auth/register` | register.py | Create account + DynamoDB record |
| GET | `/restaurants/search` | LF1 | OpenSearch query |
| GET | `/restaurants/{id}` | LF2 | Restaurant details |
| GET | `/menu/{restaurantId}` | LF3 | Menu items |
| POST/GET | `/cart` | LF4 / LF6 | Manage cart |
| POST | `/orders` | LF7 | Place order → SQS |
| GET | `/orders` | LF9-2 | Order history |
| GET | `/orders/{id}` | LF9-1 | Order details |
| POST/GET/DELETE | `/reservations` | LF12/13 | Manage reservations |
| POST | `/images/upload` | LF14 | Upload to S3 |
| POST | `/chatbot` | LEX handler | Send chat message |

---

## Setup

### Prerequisites
- AWS account (us-east-1)
- AWS CLI configured
- Python 3.x

### 1. Seed the database

```bash
cd database
python create_es_indexes.py   # Create OpenSearch indexes
python upload_data.py         # Load restaurant and menu data
```

### 2. Deploy Lambda functions

Upload each `lambdas/*.py` file to its corresponding AWS Lambda function via the AWS Console or CLI.

### 3. Deploy the frontend

```bash
aws s3 sync frontend/ s3://your-bucket-name --delete
```

Then configure CloudFront to point to the S3 bucket.

### 4. Add the API Gateway SDK

Generate the JavaScript SDK from API Gateway and place it in `frontend/apiGateway-js-sdk/`.

---

## Infrastructure

- **Region:** AWS us-east-1
- **Compute:** AWS Lambda (Python 3.x) — all 24 functions stateless
- **API:** REST API via API Gateway with Cognito authorizer
- **CDN:** CloudFront distribution over S3 static site
- **No EC2, no containers, no servers**

---

## License

Built for educational and portfolio purposes.
