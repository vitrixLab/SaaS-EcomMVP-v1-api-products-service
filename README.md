# 🧩 E-Commerce MVP – Products API (Microservice)

A **simple, API-first ecommerce Products microservice** built with **FastAPI**, designed as part of a **headless / SaaS commerce architecture**.

This service exposes product-related APIs only.  
There is **no frontend**, **no storefront**, and **no hosting of user applications**.

Users consume this API from their own applications and hosting environments.

---

## 🚀 Live Demo (Render)

**Base URL:**  
https://saas-ecommvp-v1-api-products-service.onrender.com

---

## 📦 Features

- API-only (headless)
- Microservice architecture
- FastAPI + Pydantic validation
- In-memory storage (for MVP testing)
- Ready for PostgreSQL upgrade
- Easy to test with `curl`

---

## 📁 Project Structure

```text
.
├── main.py
├── requirements.txt
└── README.md
```

---

## 🛠 Tech Stack

- **Python 3.10+**
- **FastAPI**
- **Uvicorn**
- **Pydantic**

---

## 🔌 API Endpoints

### ➕ Create Product

`POST /products`

**Request Body**
```json
{
  "name": "T-Shirt",
  "type": "physical",
  "metadata": {
    "brand": "Test Brand",
    "color": "black"
  }
}
```

**Response**
```json
{
  "id": "prod_871e2cfe",
  "name": "T-Shirt",
  "type": "physical",
  "metadata": {
    "brand": "Test Brand",
    "color": "black"
  }
}
```

---

### 📄 List All Products

`GET /products`

**Response**
```json
[
  {
    "id": "prod_871e2cfe",
    "name": "T-Shirt",
    "type": "physical",
    "metadata": {
      "brand": "Test Brand"
    }
  }
]
```

---

### 🔍 Get Product by ID

`GET /products/{product_id}`

**Example**
```text
GET /products/prod_871e2cfe
```

---

## 🧪 CURL Testing (Windows CMD)

### Create Product
```cmd
curl -X POST https://saas-ecommvp-v1-api-products-service.onrender.com/products -H "Content-Type: application/json" -d "{\"name\":\"T-Shirt\",\"metadata\":{\"brand\":\"Test Brand\"}}"
```

### List Products
```cmd
curl https://saas-ecommvp-v1-api-products-service.onrender.com/products
```

### Get Single Product
```cmd
curl https://saas-ecommvp-v1-api-products-service.onrender.com/products/prod_871e2cfe
```

---

## ⚠️ Data Persistence Notice

This MVP uses **in-memory storage**:

- Data is **not persisted**
- Data resets on service restart or redeploy
- Intended for **API shape validation only**

**Planned upgrades:**
- PostgreSQL (Render)
- Multi-tenant support
- API-key authentication

---

## 🧱 Architecture Context

This service is part of a larger **ecommerce SaaS** composed of independent microservices:

- Products Service ✅
- Variants Service
- Inventory Service
- Orders Service
- Payments Service
- Webhooks Service

Each service:
- Owns its data
- Scales independently
- Communicates via APIs

---

## 🔜 Roadmap

- API-key authentication
- Persistent database (PostgreSQL)
- Update & delete endpoints
- OpenAPI / Swagger export
- Service-to-service integration

---

## 📄 License

MIT License

---

## 👨‍💻 Author

Built as a **learning + MVP foundation** for an **API-first ecommerce SaaS platform**.
