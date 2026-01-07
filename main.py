from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uuid

app = FastAPI(title="Products Service")

# In-memory storage (testing only)
PRODUCTS = {}

class ProductCreate(BaseModel):
    name: str
    type: str = "physical"
    metadata: dict = {}

class Product(ProductCreate):
    id: str


@app.post("/products", response_model=Product)
def create_product(product: ProductCreate):
    product_id = f"prod_{uuid.uuid4().hex[:8]}"
    PRODUCTS[product_id] = product.dict()
    return {"id": product_id, **PRODUCTS[product_id]}


@app.get("/products", response_model=list[Product])
def list_products():
    return [
        {"id": pid, **data}
        for pid, data in PRODUCTS.items()
    ]


@app.get("/products/{product_id}", response_model=Product)
def get_product(product_id: str):
    if product_id not in PRODUCTS:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"id": product_id, **PRODUCTS[product_id]}
