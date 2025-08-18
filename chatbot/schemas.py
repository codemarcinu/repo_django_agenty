from typing import List

from pydantic import BaseModel, Field


class ProductSchema(BaseModel):
    """
    Pydantic schema for a single product extracted from a receipt.
    Validates the structure and data types of a product item.
    """

    product_name: str = Field(
        ...,
        description="The name of the product.",
        examples=["Mleko Wiejskie 2%"],
    )
    quantity: float = Field(
        ..., description="The quantity of the product.", examples=[1.0, 0.5]
    )
    unit: str = Field(
        ...,
        description="The unit of measurement for the quantity (e.g., 'szt.', 'kg').",
        examples=["szt.", "kg"],
    )


# The root model for the entire JSON structure expected from the LLM.
# The LLM is prompted to return a list of products, so we validate against a list of the schema.
ReceiptDataSchema = List[ProductSchema]
