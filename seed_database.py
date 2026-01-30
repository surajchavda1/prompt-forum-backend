import asyncio
import os
import re
import random
import string
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB connection
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "promptforum")


# Categories data
CATEGORIES_DATA = [
    # Parent: Prompts
    {
        "name": "Prompts",
        "slug": "prompts",
        "description": "All about prompt engineering and prompt templates",
        "parent_id": None,
        "icon": "💬",
        "order": 1,
        "subcategories": [
            {"name": "Prompt Engineering", "slug": "prompt-engineering", "description": "Techniques and strategies for crafting effective prompts"},
            {"name": "System Prompts", "slug": "system-prompts", "description": "System-level prompts and configurations"},
            {"name": "Roleplay Prompts", "slug": "roleplay-prompts", "description": "Prompts for character and roleplay scenarios"},
            {"name": "Business Prompts", "slug": "business-prompts", "description": "Business and professional use cases"},
            {"name": "Marketing Prompts", "slug": "marketing-prompts", "description": "Marketing, copywriting, and advertising prompts"},
            {"name": "Coding Prompts", "slug": "coding-prompts", "description": "Programming and development prompts"},
            {"name": "Image Prompts", "slug": "image-prompts", "description": "Image generation prompts"},
            {"name": "Video Prompts", "slug": "video-prompts", "description": "Video generation and editing prompts"},
            {"name": "Voice / Audio Prompts", "slug": "voice-audio-prompts", "description": "Voice and audio generation prompts"},
            {"name": "Agents / Automation Prompts", "slug": "agents-automation-prompts", "description": "AI agents and automation workflows"}
        ]
    },
    # Parent: AI Models & Tools
    {
        "name": "AI Models & Tools",
        "slug": "ai-models-tools",
        "description": "Discussion about AI models and tools",
        "parent_id": None,
        "icon": "🤖",
        "order": 2,
        "subcategories": [
            {"name": "ChatGPT / OpenAI", "slug": "chatgpt-openai", "description": "ChatGPT and OpenAI models"},
            {"name": "Claude", "slug": "claude", "description": "Anthropic's Claude AI"},
            {"name": "Gemini", "slug": "gemini", "description": "Google's Gemini AI"},
            {"name": "Llama / Open Source Models", "slug": "llama-open-source", "description": "Llama and other open source models"},
            {"name": "Midjourney", "slug": "midjourney", "description": "Midjourney image generation"},
            {"name": "Stable Diffusion", "slug": "stable-diffusion", "description": "Stable Diffusion and similar tools"},
            {"name": "Runway / Video AI", "slug": "runway-video-ai", "description": "Runway and video AI tools"},
            {"name": "ElevenLabs / Voice AI", "slug": "elevenlabs-voice-ai", "description": "Voice AI and text-to-speech"},
            {"name": "LangChain", "slug": "langchain", "description": "LangChain framework and chains"},
            {"name": "n8n / Zapier Automations", "slug": "n8n-zapier", "description": "Workflow automation tools"}
        ]
    },
    # Parent: Prompt Marketplace
    {
        "name": "Prompt Marketplace",
        "slug": "prompt-marketplace",
        "description": "Buy, sell, and review prompts",
        "parent_id": None,
        "icon": "🛍️",
        "order": 3,
        "subcategories": [
            {"name": "Prompt Requests", "slug": "prompt-requests", "description": "Request custom prompts"},
            {"name": "Prompt Reviews", "slug": "prompt-reviews", "description": "Review and rate prompts"},
            {"name": "Prompt Packs", "slug": "prompt-packs", "description": "Bundled prompt collections"},
            {"name": "Paid Prompts", "slug": "paid-prompts", "description": "Premium prompts for sale"},
            {"name": "Free Prompts", "slug": "free-prompts", "description": "Free prompts and templates"},
            {"name": "Prompt Services", "slug": "prompt-services", "description": "Custom prompt building services"}
        ]
    },
    # Parent: Developer Zone
    {
        "name": "Developer Zone",
        "slug": "developer-zone",
        "description": "For developers building with AI",
        "parent_id": None,
        "icon": "👨‍💻",
        "order": 4,
        "subcategories": [
            {"name": "API Integration", "slug": "api-integration", "description": "Integrating AI APIs"},
            {"name": "AI SaaS Development", "slug": "ai-saas-development", "description": "Building AI-powered SaaS"},
            {"name": "AI Chatbots", "slug": "ai-chatbots", "description": "Building chatbots and conversational AI"},
            {"name": "RAG (Docs + Knowledgebase)", "slug": "rag-knowledgebase", "description": "Retrieval Augmented Generation"},
            {"name": "Fine-tuning", "slug": "fine-tuning", "description": "Model fine-tuning and training"},
            {"name": "Vector Databases", "slug": "vector-databases", "description": "Vector DB implementation"},
            {"name": "Webhooks", "slug": "webhooks", "description": "Webhook integration and automation"},
            {"name": "Deployment / Hosting", "slug": "deployment-hosting", "description": "Deploying AI applications"}
        ]
    },
    # Parent: No-Code / Low-Code
    {
        "name": "No-Code / Low-Code",
        "slug": "no-code-low-code",
        "description": "Build AI apps without coding",
        "parent_id": None,
        "icon": "🎨",
        "order": 5,
        "subcategories": [
            {"name": "Workflow Builders", "slug": "workflow-builders", "description": "Visual workflow builders"},
            {"name": "Drag & Drop AI Apps", "slug": "drag-drop-ai-apps", "description": "No-code AI app builders"},
            {"name": "Form Builders", "slug": "form-builders", "description": "AI-powered form builders"},
            {"name": "CRM / Business Automations", "slug": "crm-business-automations", "description": "CRM and business automation"},
            {"name": "AI + Google Sheets", "slug": "ai-google-sheets", "description": "AI integration with Google Sheets"},
            {"name": "AI + Notion", "slug": "ai-notion", "description": "AI integration with Notion"}
        ]
    },
    # Parent: Community & Support
    {
        "name": "Community & Support",
        "slug": "community-support",
        "description": "Get help and connect with the community",
        "parent_id": None,
        "icon": "🤝",
        "order": 6,
        "subcategories": [
            {"name": "Help / Q&A", "slug": "help-qa", "description": "Ask questions and get help"},
            {"name": "Feature Requests", "slug": "feature-requests", "description": "Suggest new features"},
            {"name": "Bug Reports", "slug": "bug-reports", "description": "Report bugs and issues"},
            {"name": "Announcements", "slug": "announcements", "description": "Official announcements"},
            {"name": "Tutorials / Guides", "slug": "tutorials-guides", "description": "Learn from tutorials and guides"},
            {"name": "Showcase / Demos", "slug": "showcase-demos", "description": "Share your projects"}
        ]
    },
    # Parent: Safety & Policy
    {
        "name": "Safety & Policy",
        "slug": "safety-policy",
        "description": "AI safety, ethics, and policies",
        "parent_id": None,
        "icon": "🛡️",
        "order": 7,
        "subcategories": [
            {"name": "Prompt Safety", "slug": "prompt-safety", "description": "Safe and responsible prompting"},
            {"name": "AI Ethics", "slug": "ai-ethics", "description": "Ethical considerations in AI"},
            {"name": "Policy Questions", "slug": "policy-questions", "description": "Platform policies and guidelines"},
            {"name": "Jailbreak Discussion", "slug": "jailbreak-discussion", "description": "Moderated discussion about jailbreaks"},
            {"name": "Content Filters", "slug": "content-filters", "description": "Content moderation and filtering"}
        ]
    },
    # Parent: Monetization & Growth
    {
        "name": "Monetization & Growth",
        "slug": "monetization-growth",
        "description": "Grow and monetize your AI projects",
        "parent_id": None,
        "icon": "💰",
        "order": 8,
        "subcategories": [
            {"name": "Pricing & Plans", "slug": "pricing-plans", "description": "Pricing strategies and plans"},
            {"name": "Affiliate / Referral", "slug": "affiliate-referral", "description": "Affiliate and referral programs"},
            {"name": "Selling Prompts", "slug": "selling-prompts", "description": "How to sell prompts effectively"},
            {"name": "Prompt Branding", "slug": "prompt-branding", "description": "Branding your prompt business"},
            {"name": "SEO for AI Products", "slug": "seo-ai-products", "description": "SEO strategies for AI products"},
            {"name": "Ads & Marketing", "slug": "ads-marketing", "description": "Advertising and marketing strategies"}
        ]
    },
    # Parent: Industry Use Cases
    {
        "name": "Industry Use Cases",
        "slug": "industry-use-cases",
        "description": "AI applications across industries",
        "parent_id": None,
        "icon": "🏢",
        "order": 9,
        "subcategories": [
            {"name": "Healthcare", "slug": "healthcare", "description": "AI in healthcare and medical"},
            {"name": "Finance / Trading", "slug": "finance-trading", "description": "AI for finance and trading"},
            {"name": "Casino / Betting", "slug": "casino-betting", "description": "AI for casino and betting"},
            {"name": "Education", "slug": "education", "description": "AI in education and e-learning"},
            {"name": "Legal", "slug": "legal", "description": "AI for legal and compliance"},
            {"name": "Real Estate", "slug": "real-estate", "description": "AI in real estate"},
            {"name": "E-commerce", "slug": "e-commerce", "description": "AI for online retail"},
            {"name": "HR / Hiring", "slug": "hr-hiring", "description": "AI for recruitment and HR"}
        ]
    }
]


# Tags data
TAGS_DATA = [
    # Prompt Types
    {"name": "prompt-template", "group": "Prompt Types", "color": "#3B82F6"},
    {"name": "prompt-framework", "group": "Prompt Types", "color": "#3B82F6"},
    {"name": "prompt-system", "group": "Prompt Types", "color": "#3B82F6"},
    {"name": "prompt-role", "group": "Prompt Types", "color": "#3B82F6"},
    {"name": "prompt-chain", "group": "Prompt Types", "color": "#3B82F6"},
    {"name": "prompt-debugging", "group": "Prompt Types", "color": "#3B82F6"},
    {"name": "prompt-optimization", "group": "Prompt Types", "color": "#3B82F6"},
    {"name": "prompt-iteration", "group": "Prompt Types", "color": "#3B82F6"},
    {"name": "prompt-evaluation", "group": "Prompt Types", "color": "#3B82F6"},
    {"name": "prompt-testing", "group": "Prompt Types", "color": "#3B82F6"},
    
    # Prompt Techniques
    {"name": "few-shot", "group": "Prompt Techniques", "color": "#8B5CF6"},
    {"name": "zero-shot", "group": "Prompt Techniques", "color": "#8B5CF6"},
    {"name": "chain-of-thought", "group": "Prompt Techniques", "color": "#8B5CF6"},
    {"name": "self-consistency", "group": "Prompt Techniques", "color": "#8B5CF6"},
    {"name": "reflection", "group": "Prompt Techniques", "color": "#8B5CF6"},
    {"name": "critique-and-rewrite", "group": "Prompt Techniques", "color": "#8B5CF6"},
    {"name": "step-by-step", "group": "Prompt Techniques", "color": "#8B5CF6"},
    {"name": "tree-of-thought", "group": "Prompt Techniques", "color": "#8B5CF6"},
    {"name": "tool-calling", "group": "Prompt Techniques", "color": "#8B5CF6"},
    {"name": "function-calling", "group": "Prompt Techniques", "color": "#8B5CF6"},
    {"name": "structured-output", "group": "Prompt Techniques", "color": "#8B5CF6"},
    {"name": "json-output", "group": "Prompt Techniques", "color": "#8B5CF6"},
    {"name": "schema-validation", "group": "Prompt Techniques", "color": "#8B5CF6"},
    
    # Use Cases
    {"name": "copywriting", "group": "Use Cases", "color": "#10B981"},
    {"name": "seo", "group": "Use Cases", "color": "#10B981"},
    {"name": "social-media", "group": "Use Cases", "color": "#10B981"},
    {"name": "email-writing", "group": "Use Cases", "color": "#10B981"},
    {"name": "landing-page", "group": "Use Cases", "color": "#10B981"},
    {"name": "product-description", "group": "Use Cases", "color": "#10B981"},
    {"name": "customer-support", "group": "Use Cases", "color": "#10B981"},
    {"name": "resume-cv", "group": "Use Cases", "color": "#10B981"},
    {"name": "interview-prep", "group": "Use Cases", "color": "#10B981"},
    {"name": "study-notes", "group": "Use Cases", "color": "#10B981"},
    {"name": "summarization", "group": "Use Cases", "color": "#10B981"},
    {"name": "translation", "group": "Use Cases", "color": "#10B981"},
    {"name": "brainstorming", "group": "Use Cases", "color": "#10B981"},
    {"name": "idea-generation", "group": "Use Cases", "color": "#10B981"},
    
    # Development / Engineering
    {"name": "api", "group": "Development", "color": "#F59E0B"},
    {"name": "sdk", "group": "Development", "color": "#F59E0B"},
    {"name": "rest-api", "group": "Development", "color": "#F59E0B"},
    {"name": "graphql", "group": "Development", "color": "#F59E0B"},
    {"name": "websocket", "group": "Development", "color": "#F59E0B"},
    {"name": "oauth", "group": "Development", "color": "#F59E0B"},
    {"name": "jwt", "group": "Development", "color": "#F59E0B"},
    {"name": "authentication", "group": "Development", "color": "#F59E0B"},
    {"name": "authorization", "group": "Development", "color": "#F59E0B"},
    {"name": "rate-limit", "group": "Development", "color": "#F59E0B"},
    {"name": "caching", "group": "Development", "color": "#F59E0B"},
    {"name": "redis", "group": "Development", "color": "#F59E0B"},
    {"name": "queue", "group": "Development", "color": "#F59E0B"},
    {"name": "cron-jobs", "group": "Development", "color": "#F59E0B"},
    {"name": "background-workers", "group": "Development", "color": "#F59E0B"},
    {"name": "logging", "group": "Development", "color": "#F59E0B"},
    {"name": "monitoring", "group": "Development", "color": "#F59E0B"},
    {"name": "error-handling", "group": "Development", "color": "#F59E0B"},
    
    # AI Architecture
    {"name": "rag", "group": "AI Architecture", "color": "#EC4899"},
    {"name": "embeddings", "group": "AI Architecture", "color": "#EC4899"},
    {"name": "vector-db", "group": "AI Architecture", "color": "#EC4899"},
    {"name": "pinecone", "group": "AI Architecture", "color": "#EC4899"},
    {"name": "weaviate", "group": "AI Architecture", "color": "#EC4899"},
    {"name": "qdrant", "group": "AI Architecture", "color": "#EC4899"},
    {"name": "chromadb", "group": "AI Architecture", "color": "#EC4899"},
    {"name": "pgvector", "group": "AI Architecture", "color": "#EC4899"},
    {"name": "retrieval", "group": "AI Architecture", "color": "#EC4899"},
    {"name": "chunking", "group": "AI Architecture", "color": "#EC4899"},
    {"name": "reranking", "group": "AI Architecture", "color": "#EC4899"},
    {"name": "memory", "group": "AI Architecture", "color": "#EC4899"},
    {"name": "context-window", "group": "AI Architecture", "color": "#EC4899"},
    
    # Agents & Automation
    {"name": "ai-agent", "group": "Agents & Automation", "color": "#6366F1"},
    {"name": "multi-agent", "group": "Agents & Automation", "color": "#6366F1"},
    {"name": "workflow", "group": "Agents & Automation", "color": "#6366F1"},
    {"name": "orchestration", "group": "Agents & Automation", "color": "#6366F1"},
    {"name": "n8n", "group": "Agents & Automation", "color": "#6366F1"},
    {"name": "zapier", "group": "Agents & Automation", "color": "#6366F1"},
    {"name": "make-com", "group": "Agents & Automation", "color": "#6366F1"},
    {"name": "triggers", "group": "Agents & Automation", "color": "#6366F1"},
    {"name": "webhooks", "group": "Agents & Automation", "color": "#6366F1"},
    {"name": "node-execution", "group": "Agents & Automation", "color": "#6366F1"},
    {"name": "debugging", "group": "Agents & Automation", "color": "#6366F1"},
    {"name": "audit-logs", "group": "Agents & Automation", "color": "#6366F1"},
    
    # Image / Video / Voice
    {"name": "image-generation", "group": "Media", "color": "#EF4444"},
    {"name": "image-editing", "group": "Media", "color": "#EF4444"},
    {"name": "midjourney", "group": "Media", "color": "#EF4444"},
    {"name": "stable-diffusion", "group": "Media", "color": "#EF4444"},
    {"name": "dalle", "group": "Media", "color": "#EF4444"},
    {"name": "video-generation", "group": "Media", "color": "#EF4444"},
    {"name": "runway", "group": "Media", "color": "#EF4444"},
    {"name": "voice-ai", "group": "Media", "color": "#EF4444"},
    {"name": "text-to-speech", "group": "Media", "color": "#EF4444"},
    {"name": "speech-to-text", "group": "Media", "color": "#EF4444"},
    {"name": "elevenlabs", "group": "Media", "color": "#EF4444"},
    
    # Frontend / Backend Stack
    {"name": "nextjs", "group": "Tech Stack", "color": "#14B8A6"},
    {"name": "reactjs", "group": "Tech Stack", "color": "#14B8A6"},
    {"name": "nodejs", "group": "Tech Stack", "color": "#14B8A6"},
    {"name": "fastapi", "group": "Tech Stack", "color": "#14B8A6"},
    {"name": "laravel", "group": "Tech Stack", "color": "#14B8A6"},
    {"name": "django", "group": "Tech Stack", "color": "#14B8A6"},
    {"name": "flutter", "group": "Tech Stack", "color": "#14B8A6"},
    {"name": "unity3d", "group": "Tech Stack", "color": "#14B8A6"},
    {"name": "mongodb", "group": "Tech Stack", "color": "#14B8A6"},
    {"name": "postgresql", "group": "Tech Stack", "color": "#14B8A6"},
    {"name": "mysql", "group": "Tech Stack", "color": "#14B8A6"},
    {"name": "prisma", "group": "Tech Stack", "color": "#14B8A6"},
    {"name": "supabase", "group": "Tech Stack", "color": "#14B8A6"},
    {"name": "firebase", "group": "Tech Stack", "color": "#14B8A6"},
    
    # Output Formats
    {"name": "markdown", "group": "Output Formats", "color": "#84CC16"},
    {"name": "json", "group": "Output Formats", "color": "#84CC16"},
    {"name": "yaml", "group": "Output Formats", "color": "#84CC16"},
    {"name": "csv", "group": "Output Formats", "color": "#84CC16"},
    {"name": "xml", "group": "Output Formats", "color": "#84CC16"},
    {"name": "sql", "group": "Output Formats", "color": "#84CC16"},
    {"name": "code-snippet", "group": "Output Formats", "color": "#84CC16"},
    {"name": "tables", "group": "Output Formats", "color": "#84CC16"},
    {"name": "bullet-list", "group": "Output Formats", "color": "#84CC16"},
    
    # Monetization
    {"name": "pricing", "group": "Monetization", "color": "#F97316"},
    {"name": "subscriptions", "group": "Monetization", "color": "#F97316"},
    {"name": "prompt-selling", "group": "Monetization", "color": "#F97316"},
    {"name": "marketplace", "group": "Monetization", "color": "#F97316"},
    {"name": "licensing", "group": "Monetization", "color": "#F97316"},
    {"name": "revenue", "group": "Monetization", "color": "#F97316"},
    {"name": "affiliate", "group": "Monetization", "color": "#F97316"},
    {"name": "payments", "group": "Monetization", "color": "#F97316"},
    {"name": "stripe", "group": "Monetization", "color": "#F97316"},
    {"name": "razorpay", "group": "Monetization", "color": "#F97316"},
    
    # Security / Policy
    {"name": "security", "group": "Security", "color": "#DC2626"},
    {"name": "privacy", "group": "Security", "color": "#DC2626"},
    {"name": "pii", "group": "Security", "color": "#DC2626"},
    {"name": "prompt-injection", "group": "Security", "color": "#DC2626"},
    {"name": "jailbreak", "group": "Security", "color": "#DC2626"},
    {"name": "safe-prompts", "group": "Security", "color": "#DC2626"},
    {"name": "moderation", "group": "Security", "color": "#DC2626"},
    {"name": "compliance", "group": "Security", "color": "#DC2626"},
    {"name": "gdpr", "group": "Security", "color": "#DC2626"},
    {"name": "encryption", "group": "Security", "color": "#DC2626"},
    
    # Stake / Betting Related
    {"name": "stake", "group": "Betting", "color": "#7C3AED"},
    {"name": "casino", "group": "Betting", "color": "#7C3AED"},
    {"name": "sports-betting", "group": "Betting", "color": "#7C3AED"},
    {"name": "odds", "group": "Betting", "color": "#7C3AED"},
    {"name": "risk-management", "group": "Betting", "color": "#7C3AED"},
    {"name": "bankroll", "group": "Betting", "color": "#7C3AED"},
    {"name": "fairness", "group": "Betting", "color": "#7C3AED"},
    {"name": "provably-fair", "group": "Betting", "color": "#7C3AED"},
    {"name": "dice", "group": "Betting", "color": "#7C3AED"},
    {"name": "plinko", "group": "Betting", "color": "#7C3AED"},
    {"name": "keno", "group": "Betting", "color": "#7C3AED"},
    {"name": "crash-game", "group": "Betting", "color": "#7C3AED"},
    
    # Community Tags
    {"name": "question", "group": "Community", "color": "#06B6D4"},
    {"name": "answer", "group": "Community", "color": "#06B6D4"},
    {"name": "tutorial", "group": "Community", "color": "#06B6D4"},
    {"name": "guide", "group": "Community", "color": "#06B6D4"},
    {"name": "showcase", "group": "Community", "color": "#06B6D4"},
    {"name": "feedback", "group": "Community", "color": "#06B6D4"},
    {"name": "bug", "group": "Community", "color": "#06B6D4"},
    {"name": "feature-request", "group": "Community", "color": "#06B6D4"},
    {"name": "solved", "group": "Community", "color": "#06B6D4"},
    {"name": "not-solved", "group": "Community", "color": "#06B6D4"}
]


async def seed_categories(db):
    """Seed categories into database"""
    categories_collection = db.categories
    
    # Clear existing categories (optional - comment out if you want to keep existing)
    # await categories_collection.delete_many({})
    
    print("[*] Seeding categories...")
    
    for parent_data in CATEGORIES_DATA:
        # Create parent category
        parent = {
            "name": parent_data["name"],
            "slug": parent_data["slug"],
            "description": parent_data.get("description"),
            "parent_id": None,
            "icon": parent_data.get("icon"),
            "order": parent_data["order"],
            "post_count": 0,
            "is_active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Check if parent already exists
        existing = await categories_collection.find_one({"slug": parent["slug"]})
        if existing:
            print(f"  [SKIP] Parent category '{parent['name']}' already exists")
            parent_id = str(existing["_id"])
        else:
            result = await categories_collection.insert_one(parent)
            parent_id = str(result.inserted_id)
            print(f"  [OK] Created parent category: {parent['name']}")
        
        # Create subcategories
        for sub_data in parent_data.get("subcategories", []):
            subcategory = {
                "name": sub_data["name"],
                "slug": sub_data["slug"],
                "description": sub_data.get("description"),
                "parent_id": parent_id,
                "icon": None,
                "order": 0,
                "post_count": 0,
                "is_active": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            # Check if subcategory already exists
            existing_sub = await categories_collection.find_one({"slug": subcategory["slug"]})
            if existing_sub:
                print(f"     [SKIP] Subcategory '{subcategory['name']}' already exists")
            else:
                await categories_collection.insert_one(subcategory)
                print(f"     [OK] Created subcategory: {subcategory['name']}")
    
    # Count total
    total = await categories_collection.count_documents({})
    print(f"\n[SUCCESS] Categories seeded! Total: {total}")


async def seed_tags(db):
    """Seed tags into database"""
    tags_collection = db.tags
    
    # Clear existing tags (optional - comment out if you want to keep existing)
    # await tags_collection.delete_many({})
    
    print("\n[*] Seeding tags...")
    
    for tag_data in TAGS_DATA:
        tag = {
            "name": tag_data["name"],
            "slug": tag_data["name"],  # Use name as slug
            "description": None,
            "group": tag_data.get("group"),
            "color": tag_data.get("color"),
            "usage_count": 0,
            "is_active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Check if tag already exists
        existing = await tags_collection.find_one({"slug": tag["slug"]})
        if not existing:
            await tags_collection.insert_one(tag)
            print(f"  [OK] Created tag: {tag['name']} ({tag['group']})")
        else:
            print(f"  [SKIP] Tag '{tag['name']}' already exists")
    
    # Count total
    total = await tags_collection.count_documents({})
    print(f"\n[SUCCESS] Tags seeded! Total: {total}")


def sanitize_username(base: str) -> str:
    """
    Sanitize a string to create a valid username base.
    - Lowercase
    - Only alphanumeric characters (no underscores/hyphens in base)
    """
    # Convert to lowercase
    sanitized = base.lower().strip()
    # Keep only alphanumeric characters
    sanitized = re.sub(r'[^a-z0-9]', '', sanitized)
    # Limit length to leave room for suffix (base-xxxxx-xxxxx = 12 chars for suffix)
    sanitized = sanitized[:20]
    return sanitized


def generate_random_suffix() -> str:
    """Generate a random suffix in format xxxxx-xxxxx (alphanumeric)"""
    part1 = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
    part2 = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
    return f"{part1}-{part2}"


async def is_username_taken(db, username: str) -> bool:
    """Check if username already exists (case-insensitive)"""
    existing = await db.users.find_one({
        "username": {"$regex": f"^{re.escape(username)}$", "$options": "i"}
    })
    return existing is not None


async def generate_unique_username(db, email: str, full_name: str = None) -> str:
    """
    Generate a unique username for a user.
    Format: {base}-{random5}-{random5}
    Example: surajchavda-a3b2c-x9y8z
    """
    # Determine base username
    if full_name:
        base_username = sanitize_username(full_name)
    else:
        # Use email prefix
        email_prefix = email.split('@')[0]
        base_username = sanitize_username(email_prefix)
    
    # Ensure base username is not empty
    if not base_username:
        base_username = "user"
    
    # Generate username with random suffix
    # Format: base-xxxxx-xxxxx
    suffix = generate_random_suffix()
    username = f"{base_username}-{suffix}"
    
    # Verify uniqueness (very rare collision, but check anyway)
    max_attempts = 5
    for _ in range(max_attempts):
        if not await is_username_taken(db, username):
            return username
        # Regenerate suffix on collision
        suffix = generate_random_suffix()
        username = f"{base_username}-{suffix}"
    
    return username


async def migrate_usernames(db, force_regenerate: bool = False):
    """
    Generate usernames for all users who don't have one.
    If force_regenerate is True, regenerate usernames for ALL users.
    """
    users_collection = db.users
    
    print("\n[*] Migrating usernames for existing users...")
    
    if force_regenerate:
        # Get all users
        users_to_update = await users_collection.find({}).to_list(length=None)
        print(f"  [INFO] Force regenerating usernames for {len(users_to_update)} users")
    else:
        # Find all users without username
        users_to_update = await users_collection.find({
            "$or": [
                {"username": {"$exists": False}},
                {"username": None},
                {"username": ""}
            ]
        }).to_list(length=None)
        
        if not users_to_update:
            print("  [OK] All users already have usernames!")
            return
        
        print(f"  [INFO] Found {len(users_to_update)} users without username")
    
    updated_count = 0
    for user in users_to_update:
        email = user.get("email", "")
        full_name = user.get("full_name")
        old_username = user.get("username", "N/A")
        
        # Generate unique username
        username = await generate_unique_username(db, email, full_name)
        
        # Update user
        result = await users_collection.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "username": username,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count > 0:
            updated_count += 1
            if force_regenerate:
                print(f"  [OK] {email}: {old_username} -> @{username}")
            else:
                print(f"  [OK] {email} -> @{username}")
        else:
            print(f"  [FAIL] Could not update {email}")
    
    print(f"\n[SUCCESS] Updated {updated_count}/{len(users_to_update)} users with usernames")


async def main(force_regenerate_usernames: bool = False):
    """Main seed function"""
    print("=" * 60)
    print("Starting database seed...")
    print("=" * 60)
    print()
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DATABASE_NAME]
    
    try:
        # Seed categories
        await seed_categories(db)
        
        # Seed tags
        await seed_tags(db)
        
        # Migrate usernames for existing users
        await migrate_usernames(db, force_regenerate=force_regenerate_usernames)
        
        print()
        print("=" * 60)
        print("Database seeding completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print()
        print("=" * 60)
        print(f"ERROR during seeding: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
    finally:
        client.close()


if __name__ == "__main__":
    import sys
    
    # Check for --regenerate-usernames flag
    force_regenerate = "--regenerate-usernames" in sys.argv
    
    if force_regenerate:
        print("[INFO] Force regenerating ALL usernames with new format")
    
    asyncio.run(main(force_regenerate_usernames=force_regenerate))
