# 🧩 E-Commerce MVP – Products API (Microservice)

A **headless Products microservice** built with **Flask**, designed as part of a **SaaS / headless ecommerce architecture**.

This service is **API-only**.  
It stores products temporarily in-memory and asynchronously persists them to a **database service**.  
Users consume this API from their own frontends or web apps.

---

## 🚀 Live Demo (Render / PythonAnywhere)

Base URL (Products Service):

https://saas-ecommvp-v1-api-products-service.onrender.com/

Database Service URL:

https://vitrixlabph.pythonanywhere.com/api/products

---

## 📦 Features

- Fast **in-memory cache** for instant API responses  
- Async **database persistence** using background threads  
- Retry logic for reliability  
- Cache inspection and manual sync endpoints (`/cache/stats`, `/cache/sync`)  
- Health check endpoint (`/health`)  
- Filtered list and limit query parameters  
- Logging for operations, background tasks, and errors  
- CORS enabled for cross-origin requests  

---

## 📁 Project Structure
```
├── main.py / flask_app.py # Main Flask app with Products Service logic
├── requirements.txt # Dependencies
└── README.md
```

---

## 🛠 Tech Stack

- **Python 3.10+**  
- **Flask**  
- **Requests** (for DB API calls)  
- **SQLite** (optional, in DB service)  
- **Threading** for async persistence  

---

## 🔌 API Endpoints

### ➕ Create Product

`POST /products`

**Request Body**

```json
{
  "name": "T-Shirt",
  "type": "physical",
  "metadata": {"brand": "Test Brand"}
}
```
Response

```json
{
  "id": "prod_abcdef1234",
  "name": "T-Shirt",
  "type": "physical",
  "metadata": {"brand": "Test Brand"},
  "created_at": "2026-01-07T14:00:00"
}
```
Stores product in cache immediately

Persists asynchronously to DB service

📄 List Products
GET /products

Optional query parameters:

type → filter by product type

limit → maximum number of products returned (default 100)

Response

```json
[
  {
    "id": "prod_abcdef1234",
    "name": "T-Shirt",
    "type": "physical",
    "metadata": {"brand": "Test Brand"},
    "created_at": "2026-01-07T14:00:00"
  }
]
```

🔍 Get Product by ID
```GET /products/{product_id}```

Looks in cache first, optionally fetches from DB service if missing

❌ Delete Product
```DELETE /products/{product_id}```

Deletes from cache immediately

Async deletes from DB service

🧪 Cache & Health Endpoints
```GET /health → checks service health + DB connectivity```

```GET /cache/stats → cache statistics and memory usage```

```POST /cache/sync → manually sync cache with DB service```

🧪 CURL Testing (Windows CMD)
Create Product

```cmd 
curl -X POST https://saas-ecommvp-v1-api-products-service.onrender.com/products -H "Content-Type: application/json" -d "{\"name\":\"T-Shirt\",\"metadata\":{\"brand\":\"Test Brand\"}}"
```
List Products 

```cmd 
curl https://saas-ecommvp-v1-api-products-service.onrender.com/products
```
Get Product

```cmd
curl https://saas-ecommvp-v1-api-products-service.onrender.com/products/prod_abcdef1234
```
Delete Product

```cmd 
curl -X DELETE https://saas-ecommvp-v1-api-products-service.onrender.com/products/prod_abcdef1234
```

⚠️ Data Persistence Notice
Products Service uses in-memory cache → data resets on restart (Render free-tier)

Database Service handles permanent storage (PythonAnywhere SQLite or PostgreSQL)

Background threads handle async persistence with retries

Manual cache sync endpoint /cache/sync ensures consistency

🧱 Architecture Context
```csharp 
[UI / Frontend] 
       |
       | POST /products
       v
[Products Service]  ← cache, fast API, async DB persistence
       |
       | POST/DELETE → DB Service
       v
[Database Service]  ← SQLite / PostgreSQL, persistent storage
```
Microservice pattern: each service owns its data, scales independently, communicates via APIs

🔜 Roadmap
Full PostgreSQL persistence

Multi-tenant support (API keys)

Update / Patch endpoints

Swagger / OpenAPI documentation

Service-to-service integration monitoring

📄 License
MIT License

👨‍💻 Author
Built as a learning + MVP foundation for an API-first ecommerce SaaS platform.
