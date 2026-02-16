from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import random
import re
import os
import uuid
import time

app = FastAPI()

# ---- Request Models ----

class ListingRequest(BaseModel):
    main_keyword: str
    tracking_code: str
    price: str
    product_info_lines: list[str] = Field(..., min_items=5, max_items=5)

class RawListingRequest(BaseModel):
    listing_text: str

# ---- Phrase pools ----

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

# ---- Temp-file storage ----
# Render’s filesystem is ephemeral; this is perfect for temporary downloads.
TMP_DIR = "/tmp/marketplace_files"
os.makedirs(TMP_DIR, exist_ok=True)

# token -> {"path": "...", "filename": "...", "created": unix_time}
FILE_INDEX: dict[str, dict] = {}

# how long links should work (seconds)
LINK_TTL_SECONDS = 60 * 20  # 20 minutes


def _cleanup_expired_files():
    """Remove expired temp files."""
    now = time.time()
    expired_tokens = []
    for token, meta in FILE_INDEX.items():
        if now - meta["created"] > LINK_TTL_SECONDS:
            expired_tokens.append(token)

    for token in expired_tokens:
        meta = FILE_INDEX.pop(token, None)
        if meta:
            try:
                os.remove(meta["path"])
            except FileNotFoundError:
                pass


def shuffled_cycle(items: list[str]):
    """Shuffle the list and yield each item once, then reshuffle and repeat forever."""
    pool = items[:]
    while True:
        random.shuffle(pool)
        for item in pool:
            yield item


def generate_95_text(data: ListingRequest) -> tuple[str, str]:
    """Return (filename, full_text_content)."""
    listings: list[str] = []

    title_gen = shuffled_cycle(title_variations)
    benefit_gen = shuffled_cycle(benefit_lines)
    condition_gen = shuffled_cycle(condition_lines)
    assembly_gen = shuffled_cycle(assembly_lines)

    for _ in range(95):
        info = data.product_info_lines[:]   # copy
        random.shuffle(info)

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

    filename = f"{data.main_keyword.replace(' ', '-')}-{data.tracking_code}-95-Listings.txt"
    content = "\n".join(listings)
    return filename, content


def parse_listing_text(listing_text: str) -> ListingRequest:
    text = listing_text.replace("\r\n", "\n").strip()
    lines = [ln.strip() for ln in text.split("\n") if ln.strip() != ""]
    if len(lines) < 2:
        raise HTTPException(status_code=400, detail="Listing text is too short.")

    title_line = lines[0]

    # Price: first line that matches $105 or $105.00
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
    title_without_code = " ".join(title_tokens[:-1]).strip()

    # Remove common “new” prefixes so generator can add its own prefix
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

    bullets = [ln.lstrip("●").strip() for ln in lines if ln.startswith("●")]
    if len(bullets) < 5:
        raise HTTPException(status_code=400, detail=f"Found {len(bullets)} bullet lines starting with ●. Need 5.")

    product_info_lines = bullets[:5]

    return ListingRequest(
        main_keyword=main_keyword,
        tracking_code=tracking_code,
        price=price,
        product_info_lines=product_info_lines
    )


def _write_temp_file(filename: str, content: str) -> tuple[str, str]:
    """Create a temp file and return (token, file_path)."""
    _cleanup_expired_files()

    token = uuid.uuid4().hex  # unguessable
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", filename).strip("-")
    path = os.path.join(TMP_DIR, f"{token}-{safe_name}")

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    FILE_INDEX[token] = {"path": path, "filename": safe_name, "created": time.time()}
    return token, path


# ---- Endpoints ----

@app.post("/generate")
def generate_listings(data: ListingRequest):
    filename, content = generate_95_text(data)
    token, _path = _write_temp_file(filename, content)

    return {
        "filename": filename,
        "download_url": f"/download/{token}",
        "content": content  # keep this for now; you can remove later if you want only downloads
    }


@app.post("/generate_from_listing")
def generate_from_listing(data: RawListingRequest):
    parsed = parse_listing_text(data.listing_text)
    filename, content = generate_95_text(parsed)
    token, _path = _write_temp_file(filename, content)

    return {
        "filename": filename,
        "download_url": f"/download/{token}",
        "content": content
    }


@app.get("/download/{token}")
def download(token: str, background_tasks: BackgroundTasks):
    _cleanup_expired_files()

    meta = FILE_INDEX.get(token)
    if not meta:
        raise HTTPException(status_code=404, detail="File not found or link expired.")

    file_path = meta["path"]
    download_name = meta["filename"]

    # Delete after it’s served (best-effort)
    def _delete_after():
        FILE_INDEX.pop(token, None)
        try:
            os.remove(file_path)
        except FileNotFoundError:
            pass

    background_tasks.add_task(_delete_after)

    return FileResponse(
        path=file_path,
        media_type="text/plain",
        filename=download_name
    )
