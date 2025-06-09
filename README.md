# 🍽️ FeastFleetDeliveryApp

**FeastFleetDeliveryApp** is a fully serverless food delivery web application hosted on AWS. Customers can browse restaurants, place orders, manage reservations, interact with a chatbot assistant, and upload images—all without any backend server to maintain.

---

## ⚙️ Features

- **Restaurant discovery**: list, view, full-text search (powered by OpenSearch)  
- **Menu browsing** with image upload support  
- **User authentication**: login & registration pages  
- **Order management**: add to cart, place, view, and track orders  
- **Reservation system**: create and view bookings  
- **Chatbot assistant** using AWS Lex  
- Fully **serverless stack**: AWS Lambda, API Gateway, DynamoDB, OpenSearch  
- **Static frontend**: HTML/CSS/JavaScript hosted via S3 + CloudFront

---

## 🗂️ Project Structure

```plaintext
FeastFleetDeliveryApp/
├── database/
│   ├── create_es_indexes.py        # Defines OpenSearch index schema
│   ├── upload_data.py             # Seeds DynamoDB and OpenSearch
│   └── restaurant_data_update.py  # Updates restaurant data records
|
├── frontend/
│   ├── css/ images/ js/            # Static assets
│   ├── index.html                  # Landing / Home
│   ├── login.html                  # User login page
│   ├── register.html               # User registration page
│   ├── menu.html                   # Restaurant menu view
│   ├── restaurant-info.html        # Detailed restaurant info
│   ├── view-cart.html              # Shopping cart view
│   ├── order-list.html             # User’s order history
│   ├── order-detail.html           # Order details page
│   ├── reservation-creation.html   # Reservation form
│   ├── view-reservations.html      # User’s reservations list
│   ├── chatbot.html                # Chatbot interface
│   └── error.html                  # Error/fallback page
|
├── lambdas/
│   ├── LF1-Restaurant-search.py    # Restaurant search logic
│   ├── LF4-Cart-add.py            # Add items to cart
│   ├── LF6-Cart-view.py           # View cart contents
│   ├── LF7-Place-order.py         # Place a new order
│   ├── LF9-View-order.py          # Retrieve an order
│   ├── LF10-Simulate-delivery.py  # Mock delivery updates
│   ├── LF11–LF13 (reservation handling)
│   ├── LF14–LF15 (image upload & processing via SageMaker)
│   └── LEX-General-Handler.py     # Chatbot intent handler
|
├── serverless.yml or SAM template  # AWS infra specifications
├── .gitignore
└── README.md                        # Project documentation
