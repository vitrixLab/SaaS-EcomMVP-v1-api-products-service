from fastapi import FastAPI, BackgroundTasks, HTTPException, status
from pydantic import BaseModel
from datetime import datetime
import uuid
import requests
import asyncio
from typing import Optional, List
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Products Service",
    description="Primary API service with in-memory cache and async persistence",
    version="1.0.0"
)

# In-memory storage (acts as cache)
PRODUCTS_CACHE = {}

# Database service URL (deploy on PythonAnywhere)
DB_SERVICE_URL = "https://yourusername.pythonanywhere.com/api/products"  # ← UPDATE THIS

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
        "endpoints": {
            "GET /products": "List all products (from cache)",
            "POST /products": "Create product (cache + async to DB)",
            "GET /products/{id}": "Get product by ID",
            "GET /health": "Health check"
        }
    }

@app.get("/health")
async def health_check():
    """Check service health and DB connection"""
    db_status = "unknown"
    try:
        # Quick test to DB service
        response = requests.get(DB_SERVICE_URL.replace('/api/products', '/health'), timeout=2)
        db_status = "connected" if response.status_code == 200 else "unreachable"
    except:
        db_status = "unreachable"
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "cache_entries": len(PRODUCTS_CACHE),
        "database_service": db_status
    }

@app.post("/products", response_model=Product, status_code=status.HTTP_201_CREATED)
async def create_product(
    product: ProductCreate, 
    background_tasks: BackgroundTasks
):
    """
    Create a new product:
    1. Store in local cache immediately
    2. Queue background task to persist to database service
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
    
    logger.info(f"Product created in cache: {product_id}")
    return product_data

@app.get("/products", response_model=List[Product])
async def list_products(
    type_filter: Optional[str] = None,
    limit: int = 100
):
    """List products from cache"""
    products = list(PRODUCTS_CACHE.values())
    
    # Apply filters
    if type_filter:
        products = [p for p in products if p.get("type") == type_filter]
    
    # Apply limit
    products = products[:limit]
    
    return products

@app.get("/products/{product_id}", response_model=Product)
async def get_product(product_id: str):
    """Get product by ID from cache"""
    if product_id not in PRODUCTS_CACHE:
        # Optional: Try to fetch from DB service if not in cache
        try:
            response = requests.get(f"{DB_SERVICE_URL}/{product_id}", timeout=2)
            if response.status_code == 200:
                product_data = response.json()
                PRODUCTS_CACHE[product_id] = product_data
                return product_data
        except:
            pass
        
        raise HTTPException(
            status_code=404,
            detail="Product not found in cache"
        )
    
    return PRODUCTS_CACHE[product_id]

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
    return {"status": "deleted", "product_id": product_id}

# --- Background Tasks ---
async def persist_to_database(product_id: str, product_data: dict):
    """
    Asynchronously persist product to database service
    With retry logic for reliability
    """
    max_retries = 3
    retry_delay = 1  # seconds
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting to persist {product_id} to DB (attempt {attempt + 1})")
            
            # Send to database service
            response = requests.post(
                DB_SERVICE_URL,
                json=product_data,
                timeout=5,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"Successfully persisted {product_id} to database service")
                return True
            else:
                logger.warning(f"DB service returned {response.status_code}: {response.text}")
                
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout persisting {product_id} (attempt {attempt + 1})")
        except requests.exceptions.ConnectionError:
            logger.warning(f"Connection error persisting {product_id} (attempt {attempt + 1})")
        except Exception as e:
            logger.error(f"Error persisting {product_id}: {e}")
        
        # Wait before retry
        if attempt < max_retries - 1:
            await asyncio.sleep(retry_delay * (attempt + 1))  # Exponential backoff
    
    logger.error(f"Failed to persist {product_id} after {max_retries} attempts")
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
    Useful after service restart
    """
    try:
        response = requests.get(DB_SERVICE_URL, timeout=5)
        if response.status_code == 200:
            products = response.json().get("products", [])
            
            # Update cache
            for product in products:
                PRODUCTS_CACHE[product["id"]] = product
            
            logger.info(f"Synced {len(products)} products from database")
            return {"synced": len(products), "cache_size": len(PRODUCTS_CACHE)}
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        raise HTTPException(status_code=500, detail="Sync failed")
    
    return {"synced": 0, "cache_size": len(PRODUCTS_CACHE)}

@app.get("/cache/stats")
async def cache_stats():
    """Get cache statistics"""
    return {
        "total_products": len(PRODUCTS_CACHE),
        "memory_usage": f"{sum(len(str(v)) for v in PRODUCTS_CACHE.values()) / 1024:.2f} KB",
        "product_types": {
            "physical": sum(1 for p in PRODUCTS_CACHE.values() if p.get("type") == "physical"),
            "digital": sum(1 for p in PRODUCTS_CACHE.values() if p.get("type") == "digital"),
            "service": sum(1 for p in PRODUCTS_CACHE.values() if p.get("type") == "service")
        }
    }

# Startup event
@app.on_event("startup")
async def startup_event():
    """Optional: Sync cache with database on startup"""
    logger.info("Products Service starting up...")
    # Uncomment to auto-sync on startup:
    # await sync_cache()
