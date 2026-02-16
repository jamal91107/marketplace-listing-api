from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import random
import re

app = FastAPI()


class ListingRequest(BaseModel):
    main_keyword: str
    tracking_code: str
    price: str
    product_info_lines: list[str] = Field(..., min_items=5, max_items=5)


class RawListingRequest(BaseModel):
    listing_text: str


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
    """Shuffle the list and yield each item once, then reshuffle and repeat forever."""
    pool = items[:]
    while True:
        random.shuffle(pool)
        for item in pool:
            yield item


def generate_95(data: ListingRequest) -> dict:
    listings: list[str] = []

    title_gen = shuffled_cycle(title_variations)
    benefit_gen = shuffled_cycle(benefit_lines)
    condition_gen = shuffled_cycle(condition_lines)
    assembly_gen = shuffled_cycle(assembly_lines)

    for _ in range(95):
        info = data.product_info_lines[:]   # copy
        random.shuffle(info)                # shuffle bullet order each listing

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
        "filename": f"{data.main_keyword.replace(' ', '-')}-{data.tracking_code}-95.txt",
        "content": "\n".join(listings)
    }


def parse_listing_text(listing_text: str) -> ListingRequest:
    # Normalize line endings and strip extra whitespace
    text = listing_text.replace("\r\n", "\n").strip()

    lines = [ln.strip() for ln in text.split("\n") if ln.strip() != ""]
    if len(lines) < 2:
        raise HTTPException(status_code=400, detail="Listing text is too short.")

    # Title is first non-empty line
    title_line = lines[0]

    # Price: first line that looks like $105, $105.00, etc.
    price = None
    for ln in lines:
        if re.match(r"^\$\d+(\.\d{2})?$", ln):
            price = ln
            break
    if not price:
        raise HTTPException(status_code=400, detail="Could not find a price line like $105.")

    # Tracking code: last token in title line
    title_tokens = title_line.split()
    if len(title_tokens) < 2:
        raise HTTPException(status_code=400, detail="Title line not valid.")
    tracking_code = title_tokens[-1]

    # Remove tracking code from title line
    title_without_code = " ".join(title_tokens[:-1]).strip()

    # Remove common "new" prefixes if present (so generator can add its own random prefix)
    # e.g. "Brand New", "New", "Just Released", etc.
    removable_prefixes = [
        "Brand New", "New", "Just Released", "Latest Model", "New Modern", "New Contemporary",
        "New Space-Saving", "New Compact", "New Bedroom Essential", "New Minimalist",
        "New Functional", "New Stylish", "New Home Upgrade", "New Storage Solution",
        "New Apartment Ready", "New Sleek Design"
    ]
    main_keyword = title_without_code
    for pref in sorted(removable_prefixes, key=len, reverse=True):
        if main_keyword.lower().startswith(pref.lower() + " "):
            main_keyword = main_keyword[len(pref):].strip()
            break

    # Product info bullets: grab lines starting with ●
    bullets = [ln.lstrip("●").strip() for ln in lines if ln.startswith("●")]
    if len(bullets) < 5:
        raise HTTPException(
            status_code=400,
            detail=f"Found {len(bullets)} bullet lines starting with ●. Need 5."
        )

    product_info_lines = bullets[:5]

    return ListingRequest(
        main_keyword=main_keyword,
        tracking_code=tracking_code,
        price=price,
        product_info_lines=product_info_lines
    )


@app.post("/generate")
def generate_listings(data: ListingRequest):
    return generate_95(data)


@app.post("/generate_from_listing")
def generate_from_listing(data: RawListingRequest):
    parsed = parse_listing_text(data.listing_text)
    return generate_95(parsed)
