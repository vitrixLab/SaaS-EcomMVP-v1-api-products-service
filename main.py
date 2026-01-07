from fastapi import FastAPI
from pydantic import BaseModel
import uuid

app = FastAPI()

PRODUCTS = {}

class Product(BaseModel):
    name: str
    type: str = "physical"
    metadata: dict = {}

@app.post("/products")
def create_product(product: Product):
    product_id = f"prod_{uuid.uuid4().hex[:8]}"
    PRODUCTS[product_id] = product.dict()
    return {"id": product_id, **PRODUCTS[product_id]}
