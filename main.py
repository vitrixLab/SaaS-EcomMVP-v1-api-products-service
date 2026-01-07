from fastapi import FastAPI, BackgroundTasks, HTTPException, status, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime
import uuid
import requests
import asyncio
from typing import Optional, List
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Products Service",
    description="Primary API service with in-memory cache and async persistence",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# In-memory storage (acts as cache)
PRODUCTS_CACHE = {}

# Database service URL - Your PythonAnywhere service
DB_SERVICE_URL = "https://vitrixlabph.pythonanywhere.com/api/products"

# Optional: Use environment variable for DB URL (more secure)
# DB_SERVICE_URL = os.getenv("DB_SERVICE_URL", "https://vitrixlabph.pythonanywhere.com/api/products")

class ProductCreate(BaseModel):
    name: str
    type: str = "physical"
    metadata: dict = {}

class Product(ProductCreate):
    id: str
    created_at: Optional[str] = None

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    metadata: Optional[dict] = None

@app.get("/")
async def root():
    return {
        "service": "Products Service",
        "deployment": "Render.com",
        "cache_size": len(PRODUCTS_CACHE),
        "db_service": DB_SERVICE_URL,
        "health_check": "/health",
        "endpoints": {
            "GET /products": "List all products (from cache)",
            "POST /products": "Create product (cache + async to DB)",
            "GET /products/{id}": "Get product by ID",
            "DELETE /products/{id}": "Delete product",
            "GET /health": "Health check",
            "GET /cache/stats": "Cache statistics",
            "POST /cache/sync": "Sync cache with database"
        }
    }

@app.get("/health")
async def health_check():
    """Check service health and DB connection"""
    try:
        # Test connection to Database Service
        db_response = requests.get(
            DB_SERVICE_URL.replace('/api/products', '/health'), 
            timeout=3
        )
        db_status = "connected" if db_response.status_code == 200 else "unreachable"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "Products Service",
        "cache_entries": len(PRODUCTS_CACHE),
        "database_service": {
            "url": DB_SERVICE_URL,
            "status": db_status
        },
        "deployment": "Render.com"
    }

@app.post("/products", response_model=Product, status_code=status.HTTP_201_CREATED)
async def create_product(
    product: ProductCreate, 
    background_tasks: BackgroundTasks
):
    """
    Create a new product:
    1. Store in local cache immediately (fast response)
    2. Queue background task to persist to database service (async)
    """
    # Generate unique ID
    product_id = f"prod_{uuid.uuid4().hex[:10]}"
    created_at = datetime.now().isoformat()
    
    # Create product object
    product_data = {
        "id": product_id,
        "name": product.name,
        "type": product.type,
        "metadata": product.metadata,
        "created_at": created_at
    }
    
    # Store in memory cache (immediate response)
    PRODUCTS_CACHE[product_id] = product_data
    
    # Add background task to persist to database
    background_tasks.add_task(
        persist_to_database, 
        product_id=product_id,
        product_data=product_data
    )
    
    logger.info(f"Product created in cache: {product_id} - {product.name}")
    return product_data

@app.get("/products", response_model=List[Product])
async def list_products(
    type: Optional[str] = None,
    limit: int = 100
):
    """List products from cache with optional filtering"""
    products = list(PRODUCTS_CACHE.values())
    
    # Apply filters
    if type:
        products = [p for p in products if p.get("type") == type]
    
    # Apply limit
    products = products[:limit]
    
    return products

@app.get("/products/{product_id}", response_model=Product)
async def get_product(product_id: str):
    """Get product by ID from cache"""
    if product_id in PRODUCTS_CACHE:
        return PRODUCTS_CACHE[product_id]
    
    # Optional: Try to fetch from DB service if not in cache
    try:
        response = requests.get(f"{DB_SERVICE_URL}/{product_id}", timeout=2)
        if response.status_code == 200:
            product_data = response.json()
            PRODUCTS_CACHE[product_id] = product_data
            return product_data
    except Exception as e:
        logger.warning(f"Could not fetch from DB: {e}")
    
    raise HTTPException(
        status_code=404,
        detail="Product not found in cache"
    )

@app.delete("/products/{product_id}")
async def delete_product(product_id: str, background_tasks: BackgroundTasks):
    """Delete product from cache and notify DB service"""
    if product_id not in PRODUCTS_CACHE:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Remove from cache
    deleted_product = PRODUCTS_CACHE.pop(product_id)
    
    # Background task to delete from DB
    background_tasks.add_task(delete_from_database, product_id)
    
    logger.info(f"Product deleted from cache: {product_id}")
    return {
        "status": "deleted", 
        "product_id": product_id,
        "name": deleted_product.get("name"),
        "timestamp": datetime.now().isoformat()
    }

# --- Background Tasks ---
async def persist_to_database(product_id: str, product_data: dict):
    """
    Asynchronously persist product to database service
    With retry logic for reliability
    """
    max_retries = 3
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Persisting {product_id} to DB (attempt {attempt + 1}/{max_retries})")
            
            # Send to database service
            response = requests.post(
                DB_SERVICE_URL,
                json=product_data,
                timeout=5,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"✓ Successfully persisted {product_id} to database")
                return True
            else:
                logger.warning(f"DB service returned {response.status_code}: {response.text}")
                
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout persisting {product_id} (attempt {attempt + 1})")
        except requests.exceptions.ConnectionError:
            logger.warning(f"Connection error persisting {product_id} (attempt {attempt + 1})")
        except Exception as e:
            logger.error(f"Error persisting {product_id}: {e}")
        
        # Wait before retry (exponential backoff)
        if attempt < max_retries - 1:
            wait_time = retry_delay * (attempt + 1)
            logger.info(f"Waiting {wait_time}s before retry...")
            await asyncio.sleep(wait_time)
    
    logger.error(f"✗ Failed to persist {product_id} after {max_retries} attempts")
    
    # Optional: You could implement a dead letter queue or alert here
    return False

async def delete_from_database(product_id: str):
    """Notify database service to delete product"""
    try:
        response = requests.delete(
            f"{DB_SERVICE_URL}/{product_id}",
            timeout=3
        )
        if response.status_code in [200, 204]:
            logger.info(f"Deleted {product_id} from database service")
        else:
            logger.warning(f"Failed to delete {product_id} from DB: {response.status_code}")
    except Exception as e:
        logger.error(f"Error deleting {product_id} from DB: {e}")

# --- Cache Management Endpoints ---
@app.post("/cache/sync")
async def sync_cache():
    """
    Manually sync cache with database service
    Useful after service restart on Render (free tier sleeps)
    """
    try:
        response = requests.get(f"{DB_SERVICE_URL}?limit=1000", timeout=10)
        if response.status_code == 200:
            data = response.json()
            products = data.get("products", [])
            
            # Update cache
            for product in products:
                PRODUCTS_CACHE[product["id"]] = product
            
            logger.info(f"Synced {len(products)} products from database to cache")
            return {
                "synced": len(products), 
                "cache_size": len(PRODUCTS_CACHE),
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
    
    return {"synced": 0, "cache_size": len(PRODUCTS_CACHE)}

@app.get("/cache/stats")
async def cache_stats():
    """Get cache statistics"""
    product_types = {}
    for product in PRODUCTS_CACHE.values():
        ptype = product.get("type", "unknown")
        product_types[ptype] = product_types.get(ptype, 0) + 1
    
    # Calculate approximate memory usage
    total_chars = sum(len(str(v)) for v in PRODUCTS_CACHE.values())
    
    return {
        "total_products": len(PRODUCTS_CACHE),
        "memory_usage_kb": round(total_chars / 1024, 2),
        "memory_usage_mb": round(total_chars / (1024 * 1024), 4),
        "product_types": product_types,
        "last_sync_suggestion": "Use POST /cache/sync after service restart",
        "timestamp": datetime.now().isoformat()
    }

# Startup event
@app.on_event("startup")
async def startup_event():
    """Optional: Sync cache with database on startup"""
    logger.info("════════════════════════════════════════════")
    logger.info("🚀 Products Service starting up...")
    logger.info(f"📊 Database Service URL: {DB_SERVICE_URL}")
    logger.info("════════════════════════════════════════════")

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "timestamp": datetime.now().isoformat()}
    )

# CORS middleware (if you'll have a frontend)
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
