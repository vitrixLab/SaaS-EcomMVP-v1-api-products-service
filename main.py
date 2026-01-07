from flask import Flask, request, jsonify
import uuid
import requests
import threading
import time
import logging
from datetime import datetime
from typing import Optional, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# In-memory storage (acts as cache)
PRODUCTS_CACHE = {}

# Database service URL - Your PythonAnywhere service
DB_SERVICE_URL = "https://vitrixlabph.pythonanywhere.com/api/products"

# Optional: Use environment variable for DB URL (more secure)
# DB_SERVICE_URL = os.getenv("DB_SERVICE_URL", "https://vitrixlabph.pythonanywhere.com/api/products")

@app.route("/")
def root():
    return jsonify({
        "service": "Products Service (Flask)",
        "deployment": "Render.com",
        "cache_size": len(PRODUCTS_CACHE),
        "db_service": DB_SERVICE_URL,
        "health_check": "/health",
        "endpoints": {
            "GET /products": "List all products (from cache)",
            "POST /products": "Create product (cache + async to DB)",
            "GET /products/<id>": "Get product by ID",
            "DELETE /products/<id>": "Delete product",
            "GET /health": "Health check",
            "GET /cache/stats": "Cache statistics",
            "POST /cache/sync": "Sync cache with database"
        }
    })

@app.route("/health", methods=["GET"])
def health_check():
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
    
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "Products Service (Flask)",
        "cache_entries": len(PRODUCTS_CACHE),
        "database_service": {
            "url": DB_SERVICE_URL,
            "status": db_status
        },
        "deployment": "Render.com"
    })

@app.route("/products", methods=["POST"])
def create_product():
    """
    Create a new product:
    1. Store in local cache immediately (fast response)
    2. Start background thread to persist to database service
    """
    try:
        data = request.get_json()
        
        # Validate input
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        name = data.get("name")
        if not name:
            return jsonify({"error": "Product name is required"}), 400
        
        # Generate unique ID
        product_id = f"prod_{uuid.uuid4().hex[:10]}"
        created_at = datetime.now().isoformat()
        
        # Create product object
        product_data = {
            "id": product_id,
            "name": name,
            "type": data.get("type", "physical"),
            "metadata": data.get("metadata", {}),
            "created_at": created_at
        }
        
        # Store in memory cache (immediate response)
        PRODUCTS_CACHE[product_id] = product_data
        
        # Start background thread to persist to database
        thread = threading.Thread(
            target=persist_to_database,
            args=(product_id, product_data),
            daemon=True
        )
        thread.start()
        
        logger.info(f"Product created in cache: {product_id} - {name}")
        
        return jsonify(product_data), 201
        
    except Exception as e:
        logger.error(f"Error creating product: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/products", methods=["GET"])
def list_products():
    """List products from cache with optional filtering"""
    try:
        # Get query parameters
        product_type = request.args.get("type")
        limit = int(request.args.get("limit", 100))
        
        products = list(PRODUCTS_CACHE.values())
        
        # Apply filters
        if product_type:
            products = [p for p in products if p.get("type") == product_type]
        
        # Apply limit
        products = products[:limit]
        
        return jsonify(products)
        
    except Exception as e:
        logger.error(f"Error listing products: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/products/<product_id>", methods=["GET"])
def get_product(product_id):
    """Get product by ID from cache"""
    try:
        # Check cache first
        if product_id in PRODUCTS_CACHE:
            return jsonify(PRODUCTS_CACHE[product_id])
        
        # Optional: Try to fetch from DB service if not in cache
        try:
            response = requests.get(f"{DB_SERVICE_URL}/{product_id}", timeout=2)
            if response.status_code == 200:
                product_data = response.json()
                PRODUCTS_CACHE[product_id] = product_data
                return jsonify(product_data)
        except Exception as e:
            logger.warning(f"Could not fetch from DB: {e}")
        
        return jsonify({"error": "Product not found in cache"}), 404
        
    except Exception as e:
        logger.error(f"Error getting product: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/products/<product_id>", methods=["DELETE"])
def delete_product(product_id):
    """Delete product from cache and notify DB service"""
    try:
        if product_id not in PRODUCTS_CACHE:
            return jsonify({"error": "Product not found"}), 404
        
        # Remove from cache
        deleted_product = PRODUCTS_CACHE.pop(product_id)
        
        # Start background thread to delete from DB
        thread = threading.Thread(
            target=delete_from_database,
            args=(product_id,),
            daemon=True
        )
        thread.start()
        
        logger.info(f"Product deleted from cache: {product_id}")
        
        return jsonify({
            "status": "deleted", 
            "product_id": product_id,
            "name": deleted_product.get("name"),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error deleting product: {e}")
        return jsonify({"error": str(e)}), 500

def persist_to_database(product_id: str, product_data: dict):
    """
    Persist product to database service in background
    With retry logic for reliability
    """
    max_retries = 3
    
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
            wait_time = 2 * (attempt + 1)
            logger.info(f"Waiting {wait_time}s before retry...")
            time.sleep(wait_time)
    
    logger.error(f"✗ Failed to persist {product_id} after {max_retries} attempts")
    return False

def delete_from_database(product_id: str):
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

@app.route("/cache/sync", methods=["POST"])
def sync_cache():
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
            
            return jsonify({
                "synced": len(products), 
                "cache_size": len(PRODUCTS_CACHE),
                "timestamp": datetime.now().isoformat()
            })
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        return jsonify({"error": f"Sync failed: {str(e)}"}), 500
    
    return jsonify({"synced": 0, "cache_size": len(PRODUCTS_CACHE)})

@app.route("/cache/stats", methods=["GET"])
def cache_stats():
    """Get cache statistics"""
    product_types = {}
    for product in PRODUCTS_CACHE.values():
        ptype = product.get("type", "unknown")
        product_types[ptype] = product_types.get(ptype, 0) + 1
    
    # Calculate approximate memory usage
    total_chars = sum(len(str(v)) for v in PRODUCTS_CACHE.values())
    
    return jsonify({
        "total_products": len(PRODUCTS_CACHE),
        "memory_usage_kb": round(total_chars / 1024, 2),
        "memory_usage_mb": round(total_chars / (1024 * 1024), 4),
        "product_types": product_types,
        "last_sync_suggestion": "Use POST /cache/sync after service restart",
        "timestamp": datetime.now().isoformat()
    })

# CORS headers (if needed)
@app.after_request
def add_cors_headers(response):
    """Add CORS headers to allow cross-origin requests"""
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Resource not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({"error": "Internal server error"}), 500

# Startup message
logger.info("════════════════════════════════════════════")
logger.info("🚀 Flask Products Service starting up...")
logger.info(f"📊 Database Service URL: {DB_SERVICE_URL}")
logger.info("════════════════════════════════════════════")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
