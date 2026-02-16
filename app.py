from fastapi import FastAPI
from pydantic import BaseModel, Field
import random

app = FastAPI()


class ListingRequest(BaseModel):
    main_keyword: str
    tracking_code: str
    price: str
    product_info_lines: list[str] = Field(..., min_items=5, max_items=5)


# Phrase pools
title_variations = [
    "Brand New", "New Modern", "Just Released", "Latest Model",
    "New Contemporary", "New Space-Saving", "New Compact",
    "New Bedroom Essential", "New Minimalist", "New Functional",
    "New Stylish", "New Home Upgrade", "New Storage Solution",
    "New Apartment Ready", "New Sleek Design"
]

benefit_lines = [
    "Smart storage solution for small spaces.",
    "Perfect bedside storage with a compact footprint.",
    "Designed to maximize storage without taking up room.",
    "Lightweight yet sturdy for everyday use.",
    "Ideal for bedrooms, dorms, or living rooms.",
    "Adds modern style and practical storage.",
    "Keeps essentials organized and within reach.",
    "Great for tight spaces needing extra storage.",
    "Functional design with versatile placement.",
    "Blends style and storage in one compact piece."
]

condition_lines = [
    "Brand new in sealed box.",
    "Comes new and securely packaged.",
    "Factory sealed and unused.",
    "New condition, never assembled.",
    "Unopened and ready for assembly.",
    "Fresh from the box, unused.",
    "New and carefully packed.",
    "Never used, still in original packaging.",
    "Sealed packaging, brand new.",
    "New item, complete with all parts."
]

assembly_lines = [
    "Assembly takes about 30 minutes with included instructions and hardware.",
    "Easy setup with step-by-step instructions included.",
    "Simple assembly process with all tools provided.",
    "Clear instructions make setup quick and easy.",
    "Everything needed for assembly is included in the box."
]

DASH_LINE = "----------------------------------------"


def shuffled_cycle(items: list[str]):
    """
    Infinite generator:
    - shuffles the list
    - yields each item once
    - reshuffles and repeats
    This spreads variation evenly while staying random.
    """
    pool = items[:]
    while True:
        random.shuffle(pool)
        for item in pool:
            yield item


@app.post("/generate")
def generate_listings(data: ListingRequest):
    listings: list[str] = []

    # Create “balanced random” generators (random order, low clumping)
    title_gen = shuffled_cycle(title_variations)
    benefit_gen = shuffled_cycle(benefit_lines)
    condition_gen = shuffled_cycle(condition_lines)
    assembly_gen = shuffled_cycle(assembly_lines)

    for _ in range(95):
        info = data.product_info_lines[:]   # copy
        random.shuffle(info)                # randomize bullet order each listing

        title_prefix = next(title_gen)
        benefit = next(benefit_gen)
        condition = next(condition_gen)
        assembly = next(assembly_gen)

        title = f"{title_prefix} {data.main_keyword} With Fabric Drawers Shelf Hooks {data.tracking_code}"

        listing = f"""{title}
{data.price}

{benefit}
Delivery or pickup available

{condition}

Product Information:

● {info[0]}
● {info[1]}
● {info[2]}
● {info[3]}
● {info[4]}

{assembly}

{DASH_LINE}
"""
        listings.append(listing)

    return {
        "filename": f"{data.main_keyword}-{data.tracking_code}-95.txt",
        "content": "\n".join(listings)
    }
