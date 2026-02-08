"""
Seed script for Categories, Subcategories, and Tags based on prompt marketplace structure.

Structure:
- Main Categories (8): Models, Art, Logos, Graphics, Productivity, Marketing, Photography, Games
- Each Main Category has Subcategories
- Each Subcategory has Tags
- All levels include "Other" option

Run: python seed_categories_tags.py
Options:
  --clear : Clear existing categories and tags before seeding
  --tags-only : Only seed/update tags (categories must exist)
"""

import asyncio
import os
import sys
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB connection
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "promptforum")


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug"""
    import re
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    text = re.sub(r'^-+|-+$', '', text)
    return text


# =============================================================================
# COMPLETE DATA FROM PMT FILE
# =============================================================================

# Image generation tags (shared by multiple AI image models)
IMAGE_GENERATION_TAGS = [
    "3D", "Abstract", "Accessory", "Animal", "Anime", "Art", "Avatar",
    "Architecture", "Cartoon", "Celebrity", "Clothing", "Clip Art", "Cute",
    "Cyberpunk", "Drawing", "Drink", "Fantasy", "Fashion", "Food", "Future",
    "Gaming", "Glass", "Graphic Design", "Holiday", "Icon", "Ink", "Interior",
    "Illustration", "Jewelry", "Landscape", "Logo", "Mockup", "Monogram",
    "Monster", "Nature", "Pattern", "Painting", "People", "Photographic",
    "Pixel Art", "Poster", "Product", "Psychedelic", "Retro", "Scary", "Space",
    "Steampunk", "Statue", "Sticker", "Unique Style", "Synthwave", "Texture",
    "Vehicle", "Wallpaper", "Other"
]

# Text/Chat model tags (shared by multiple text AI models)
TEXT_MODEL_TAGS = [
    "Ads", "Business", "Chatbot", "Coach", "Conversion", "Code", "Copy",
    "Email", "Fashion", "Fix", "Finance", "Fun", "Funny", "Food", "Generation",
    "Games", "Health", "Ideas", "Language", "Marketing", "Music", "Plan",
    "Prompts", "SEO", "Social", "Sport", "Summarise", "Study", "Translate",
    "Travel", "Writing", "Other"
]

# Main Categories Data Structure
CATEGORIES_DATA = {
    "Models": {
        "description": "AI Model specific prompts",
        "icon": "robot",
        "order": 1,
        "subcategories": {
            "ChatGPT Image prompts": {"tags": IMAGE_GENERATION_TAGS, "type": "image"},
            "Claude prompts": {"tags": TEXT_MODEL_TAGS, "type": "text"},
            "DALL-E prompts": {"tags": IMAGE_GENERATION_TAGS, "type": "image"},
            "DeepSeek prompts": {"tags": TEXT_MODEL_TAGS, "type": "text"},
            "FLUX prompts": {"tags": IMAGE_GENERATION_TAGS, "type": "image"},
            "Gemini prompts": {"tags": TEXT_MODEL_TAGS, "type": "text"},
            "Gemini Image prompts": {"tags": IMAGE_GENERATION_TAGS, "type": "image"},
            "ChatGPT prompts": {"tags": TEXT_MODEL_TAGS, "type": "text"},
            "Grok prompts": {"tags": TEXT_MODEL_TAGS, "type": "text"},
            "Grok Image prompts": {"tags": IMAGE_GENERATION_TAGS, "type": "image"},
            "Hailuo AI prompts": {"tags": IMAGE_GENERATION_TAGS, "type": "image"},
            "Hunyuan prompts": {"tags": IMAGE_GENERATION_TAGS, "type": "image"},
            "Ideogram prompts": {"tags": IMAGE_GENERATION_TAGS, "type": "image"},
            "Imagen prompts": {"tags": IMAGE_GENERATION_TAGS, "type": "image"},
            "KLING AI prompts": {"tags": IMAGE_GENERATION_TAGS, "type": "image"},
            "Leonardo Ai prompts": {"tags": IMAGE_GENERATION_TAGS, "type": "image"},
            "Llama prompts": {"tags": TEXT_MODEL_TAGS, "type": "text"},
            "Midjourney prompts": {"tags": IMAGE_GENERATION_TAGS, "type": "image"},
            "Midjourney Video prompts": {"tags": IMAGE_GENERATION_TAGS, "type": "video"},
            "Qwen Image prompts": {"tags": IMAGE_GENERATION_TAGS, "type": "image"},
            "Recraft prompts": {"tags": IMAGE_GENERATION_TAGS, "type": "image"},
            "Seedance prompts": {"tags": IMAGE_GENERATION_TAGS, "type": "image"},
            "Seedream prompts": {"tags": IMAGE_GENERATION_TAGS, "type": "image"},
            "Sora prompts": {"tags": IMAGE_GENERATION_TAGS, "type": "video"},
            "Stable Diffusion prompts": {"tags": IMAGE_GENERATION_TAGS, "type": "image"},
            "Veo prompts": {"tags": IMAGE_GENERATION_TAGS, "type": "video"},
            "Wan prompts": {"tags": IMAGE_GENERATION_TAGS, "type": "image"},
            "Other": {"tags": ["Other"], "type": "other"}
        }
    },
    "Art": {
        "description": "Art and illustration prompts",
        "icon": "palette",
        "order": 2,
        "subcategories": {
            "Anime prompts": {
                "tags": ["People", "Fantasy", "Landscapes", "Other"]
            },
            "Cartoon prompts": {
                "tags": ["Animals", "Food", "People", "Vehicles", "Other"]
            },
            "Painting prompts": {
                "tags": ["Animals", "Nature", "People", "Landscape", "Other"]
            },
            "Illustration prompts": {
                "tags": ["Animals", "Food & Drink", "Nature", "Other"]
            },
            "Unique Styles prompts": {
                "tags": ["Futuristic", "Psychedelic", "Pixel Art", "Scary", "Synthwave", "Other"]
            },
            "Other": {"tags": ["Other"]}
        }
    },
    "Logos": {
        "description": "Logo and icon design prompts",
        "icon": "badge",
        "order": 3,
        "subcategories": {
            "Logo prompts": {
                "tags": ["3D", "Animal", "Business & Startup", "Cartoon", "Cute", "Food",
                        "Lettered", "Hand-drawn", "Minimalist", "Modern", "Painted", "Styled", "Other"]
            },
            "Icon prompts": {
                "tags": ["3D", "Animal", "Clipart", "Cute", "Flat Graphic", "Pixel Art",
                        "Styled", "UI", "Video Games", "Other"]
            },
            "Other": {"tags": ["Other"]}
        }
    },
    "Graphics": {
        "description": "Graphics and design prompts",
        "icon": "image",
        "order": 4,
        "subcategories": {
            "Pattern prompts": {
                "tags": ["Animals", "Food", "Nature", "Painted", "Unique Styled", "Other"]
            },
            "Product Design prompts": {
                "tags": ["Book Covers", "Cards", "Coloring Books", "Laser Engraving",
                        "Posters", "Stickers", "T-Shirt Prints", "Tattoos", "UX/UI", "Other"]
            },
            "Profile Picture prompts": {
                "tags": ["3D", "Animals", "Anime", "Fantasy", "Futuristic", "People", "Other"]
            },
            "Other": {"tags": ["Other"]}
        }
    },
    "Productivity": {
        "description": "Productivity and writing prompts",
        "icon": "briefcase",
        "order": 5,
        "subcategories": {
            "Productivity prompts": {
                "tags": ["Coaching", "Food & Diet", "Health & Fitness", "Personal Finance",
                        "Idea Generation", "Meditation", "Planning", "Studying", "Travel", "Other"]
            },
            "Writing prompts": {
                "tags": ["Email", "Translation & Language", "Music & Lyrics", "Summarisation", "Other"]
            },
            "Coding prompts": {
                "tags": ["Python", "JavaScript", "TypeScript", "React", "Node.js", "Other"]
            },
            "Other": {"tags": ["Other"]}
        }
    },
    "Marketing": {
        "description": "Marketing and business prompts",
        "icon": "megaphone",
        "order": 6,
        "subcategories": {
            "Marketing prompts": {
                "tags": ["Ad Writing", "Copy Writing", "SEO", "Other"]
            },
            "Business prompts": {
                "tags": ["Finance", "Real Estate", "Other"]
            },
            "Social Media prompts": {
                "tags": ["Etsy", "Instagram", "Twitter", "YouTube", "Other"]
            },
            "Other": {"tags": ["Other"]}
        }
    },
    "Photography": {
        "description": "Photography style prompts",
        "icon": "camera",
        "order": 7,
        "subcategories": {
            "Photography prompts": {
                "tags": ["Accessories", "Animals", "Buildings", "Clothing", "Food",
                        "Jewelry", "Landscape", "Nature", "People", "Product", "Space", "Vehicles", "Other"]
            },
            "Photography Style prompts": {
                "tags": ["Cinematic", "Retro", "Other"]
            },
            "Other": {"tags": ["Other"]}
        }
    },
    "Games": {
        "description": "Gaming and 3D prompts",
        "icon": "gamepad",
        "order": 8,
        "subcategories": {
            "3D prompts": {
                "tags": ["Animals", "Buildings", "Icons", "Landscapes", "People", "Vehicles", "Other"]
            },
            "Fun & Games prompts": {
                "tags": ["Joke & Comedy", "Text Based Games", "Other"]
            },
            "Video Game Art prompts": {
                "tags": ["Fantasy Game Art", "Game Maps", "Other"]
            },
            "Other": {"tags": ["Other"]}
        }
    }
}


async def clear_collections(db):
    """Clear existing categories and tags"""
    print("\n[*] Clearing existing data...")
    
    # Clear categories
    result = await db.categories.delete_many({})
    print(f"  [OK] Deleted {result.deleted_count} categories")
    
    # Clear tags
    result = await db.tags.delete_many({})
    print(f"  [OK] Deleted {result.deleted_count} tags")


async def seed_categories_and_tags(db, clear_existing: bool = False, tags_only: bool = False):
    """Seed categories, subcategories, and tags"""
    
    if clear_existing and not tags_only:
        await clear_collections(db)
    
    categories_collection = db.categories
    tags_collection = db.tags
    
    now = datetime.utcnow()
    
    # Track statistics
    stats = {
        "categories_created": 0,
        "categories_skipped": 0,
        "subcategories_created": 0,
        "subcategories_skipped": 0,
        "tags_created": 0,
        "tags_skipped": 0,
        "tags_updated": 0
    }
    
    # Store subcategory IDs for tag linking
    subcategory_ids = {}
    
    print("\n" + "=" * 60)
    print("SEEDING CATEGORIES, SUBCATEGORIES, AND TAGS")
    print("=" * 60)
    
    # =========================================================================
    # STEP 1: Create/Get Main Categories
    # =========================================================================
    if not tags_only:
        print("\n[STEP 1] Creating Main Categories...")
        
        for cat_name, cat_data in CATEGORIES_DATA.items():
            cat_slug = slugify(cat_name)
            
            # Check if exists
            existing = await categories_collection.find_one({"slug": cat_slug, "parent_id": None})
            
            if existing:
                print(f"  [SKIP] Main category '{cat_name}' exists")
                stats["categories_skipped"] += 1
                parent_id = str(existing["_id"])
            else:
                category_doc = {
                    "name": cat_name,
                    "slug": cat_slug,
                    "description": cat_data.get("description"),
                    "parent_id": None,
                    "icon": cat_data.get("icon"),
                    "order": cat_data.get("order", 0),
                    "post_count": 0,
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now
                }
                result = await categories_collection.insert_one(category_doc)
                parent_id = str(result.inserted_id)
                stats["categories_created"] += 1
                print(f"  [OK] Created: {cat_name}")
            
            # =========================================================================
            # STEP 2: Create Subcategories for each Main Category
            # =========================================================================
            print(f"\n  [STEP 2] Creating subcategories for '{cat_name}'...")
            
            for subcat_name, subcat_data in cat_data.get("subcategories", {}).items():
                subcat_slug = slugify(subcat_name)
                
                # Check if exists
                existing_sub = await categories_collection.find_one({
                    "slug": subcat_slug,
                    "parent_id": parent_id
                })
                
                if existing_sub:
                    print(f"    [SKIP] Subcategory '{subcat_name}' exists")
                    stats["subcategories_skipped"] += 1
                    subcat_id = str(existing_sub["_id"])
                else:
                    subcat_doc = {
                        "name": subcat_name,
                        "slug": subcat_slug,
                        "description": f"{subcat_name} for {cat_name}",
                        "parent_id": parent_id,
                        "icon": None,
                        "order": 0,
                        "post_count": 0,
                        "is_active": True,
                        "created_at": now,
                        "updated_at": now
                    }
                    result = await categories_collection.insert_one(subcat_doc)
                    subcat_id = str(result.inserted_id)
                    stats["subcategories_created"] += 1
                    print(f"    [OK] Created: {subcat_name}")
                
                # Store subcategory ID for tag linking
                subcategory_ids[f"{cat_name}|{subcat_name}"] = subcat_id
    else:
        # Tags only mode - fetch existing subcategory IDs
        print("\n[INFO] Tags-only mode - fetching existing subcategories...")
        
        for cat_name, cat_data in CATEGORIES_DATA.items():
            cat_slug = slugify(cat_name)
            parent_cat = await categories_collection.find_one({"slug": cat_slug, "parent_id": None})
            
            if not parent_cat:
                print(f"  [ERROR] Main category '{cat_name}' not found!")
                continue
            
            parent_id = str(parent_cat["_id"])
            
            for subcat_name in cat_data.get("subcategories", {}).keys():
                subcat_slug = slugify(subcat_name)
                existing_sub = await categories_collection.find_one({
                    "slug": subcat_slug,
                    "parent_id": parent_id
                })
                
                if existing_sub:
                    subcategory_ids[f"{cat_name}|{subcat_name}"] = str(existing_sub["_id"])
                else:
                    print(f"  [WARN] Subcategory '{subcat_name}' not found in '{cat_name}'")
    
    # =========================================================================
    # STEP 3: Create Tags for each Subcategory
    # =========================================================================
    print("\n[STEP 3] Creating Tags for Subcategories...")
    
    for cat_name, cat_data in CATEGORIES_DATA.items():
        print(f"\n  Processing tags for '{cat_name}'...")
        
        for subcat_name, subcat_data in cat_data.get("subcategories", {}).items():
            subcat_key = f"{cat_name}|{subcat_name}"
            subcat_id = subcategory_ids.get(subcat_key)
            
            if not subcat_id:
                print(f"    [SKIP] No subcategory ID for '{subcat_name}'")
                continue
            
            tags_list = subcat_data.get("tags", [])
            
            for tag_name in tags_list:
                # Create unique slug: subcategory-slug + tag-slug
                tag_slug = f"{slugify(subcat_name)}-{slugify(tag_name)}"
                
                # Check if tag exists for this subcategory
                existing_tag = await tags_collection.find_one({
                    "slug": tag_slug,
                    "subcategory_id": subcat_id
                })
                
                if existing_tag:
                    stats["tags_skipped"] += 1
                    continue
                
                # Check if tag exists without subcategory_id (old data)
                old_tag = await tags_collection.find_one({
                    "slug": tag_slug,
                    "subcategory_id": {"$exists": False}
                })
                
                if old_tag:
                    # Update old tag with subcategory_id
                    await tags_collection.update_one(
                        {"_id": old_tag["_id"]},
                        {"$set": {"subcategory_id": subcat_id, "updated_at": now}}
                    )
                    stats["tags_updated"] += 1
                    continue
                
                # Create new tag
                tag_doc = {
                    "name": tag_name,
                    "slug": tag_slug,
                    "description": None,
                    "subcategory_id": subcat_id,
                    "group": cat_name,  # Use main category as group
                    "color": None,
                    "usage_count": 0,
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now
                }
                
                await tags_collection.insert_one(tag_doc)
                stats["tags_created"] += 1
            
            print(f"    [OK] Processed {len(tags_list)} tags for '{subcat_name}'")
    
    # =========================================================================
    # Print Summary
    # =========================================================================
    print("\n" + "=" * 60)
    print("SEEDING COMPLETED!")
    print("=" * 60)
    print(f"\nCategories:")
    print(f"  - Created: {stats['categories_created']}")
    print(f"  - Skipped (existing): {stats['categories_skipped']}")
    print(f"\nSubcategories:")
    print(f"  - Created: {stats['subcategories_created']}")
    print(f"  - Skipped (existing): {stats['subcategories_skipped']}")
    print(f"\nTags:")
    print(f"  - Created: {stats['tags_created']}")
    print(f"  - Updated: {stats['tags_updated']}")
    print(f"  - Skipped (existing): {stats['tags_skipped']}")
    
    # Count totals
    total_categories = await categories_collection.count_documents({"parent_id": None})
    total_subcategories = await categories_collection.count_documents({"parent_id": {"$ne": None}})
    total_tags = await tags_collection.count_documents({})
    
    print(f"\nDatabase Totals:")
    print(f"  - Main Categories: {total_categories}")
    print(f"  - Subcategories: {total_subcategories}")
    print(f"  - Tags: {total_tags}")
    
    return stats


async def verify_data(db):
    """Verify the seeded data structure"""
    print("\n" + "=" * 60)
    print("VERIFYING DATA STRUCTURE")
    print("=" * 60)
    
    categories_collection = db.categories
    tags_collection = db.tags
    
    # Get all main categories
    main_cats = await categories_collection.find({"parent_id": None}).to_list(length=None)
    
    for cat in main_cats:
        cat_id = str(cat["_id"])
        cat_name = cat["name"]
        
        # Get subcategories
        subcats = await categories_collection.find({"parent_id": cat_id}).to_list(length=None)
        
        print(f"\n{cat_name} ({len(subcats)} subcategories)")
        
        for subcat in subcats[:3]:  # Show first 3 subcategories
            subcat_id = str(subcat["_id"])
            subcat_name = subcat["name"]
            
            # Get tags count
            tags_count = await tags_collection.count_documents({"subcategory_id": subcat_id})
            
            print(f"  - {subcat_name}: {tags_count} tags")
        
        if len(subcats) > 3:
            print(f"  ... and {len(subcats) - 3} more subcategories")


async def main():
    """Main function"""
    # Parse arguments
    clear_existing = "--clear" in sys.argv
    tags_only = "--tags-only" in sys.argv
    verify_only = "--verify" in sys.argv
    
    print("=" * 60)
    print("CATEGORY & TAG SEEDER")
    print("=" * 60)
    print(f"\nOptions:")
    print(f"  --clear: {clear_existing}")
    print(f"  --tags-only: {tags_only}")
    print(f"  --verify: {verify_only}")
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DATABASE_NAME]
    
    try:
        if verify_only:
            await verify_data(db)
        else:
            await seed_categories_and_tags(
                db,
                clear_existing=clear_existing,
                tags_only=tags_only
            )
            await verify_data(db)
        
        print("\n" + "=" * 60)
        print("DONE!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
