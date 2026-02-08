# Frontend Guide: Category, Subcategory, and Tag System

## Overview

The system implements a 3-level hierarchy for categorizing prompts (Posts AND Contests):

```
Category -> Subcategory -> Tags
```

**Key Points:**
- Users CANNOT create custom tags - they must select from predefined options
- All levels include an "Other" option as fallback
- Tags are linked to specific subcategories
- This structure applies to BOTH posts (questions) AND contests

---

## Data Structure

### Main Categories (8)
1. **Models** - AI Model specific prompts (ChatGPT, Midjourney, Stable Diffusion, etc.)
2. **Art** - Art and illustration prompts (Anime, Cartoon, Painting, etc.)
3. **Logos** - Logo and icon design prompts
4. **Graphics** - Graphics and design prompts (Patterns, Product Design, etc.)
5. **Productivity** - Productivity and writing prompts
6. **Marketing** - Marketing and business prompts
7. **Photography** - Photography style prompts
8. **Games** - Gaming and 3D prompts

### Subcategories
Each main category has multiple subcategories. For example:
- **Models**: ChatGPT Image prompts, Claude prompts, Midjourney prompts, DALL-E prompts, etc.
- **Art**: Anime prompts, Cartoon prompts, Painting prompts, etc.

### Tags
Each subcategory has specific tags. For example:
- **ChatGPT Image prompts**: 3D, Abstract, Animal, Anime, Art, Avatar, etc.
- **Anime prompts**: People, Fantasy, Landscapes, Other

---

## API Endpoints

### 1. Get All Categories (Tree Structure)

**Endpoint:** `GET /api/categories/tree`

**Use Case:** Initial load to show main categories with their subcategories

**Response:**
```json
{
  "success": true,
  "message": "Category tree retrieved successfully",
  "data": {
    "categories": [
      {
        "id": "category_id",
        "name": "Models",
        "slug": "models",
        "description": "AI Model specific prompts",
        "icon": "robot",
        "order": 1,
        "post_count": 0,
        "is_active": true,
        "subcategories": [
          {
            "id": "subcategory_id",
            "name": "ChatGPT Image prompts",
            "slug": "chatgpt-image-prompts",
            "parent_id": "category_id",
            "tag_count": 55,
            "is_active": true
          }
        ]
      }
    ]
  }
}
```

### 2. Get Parent Categories Only

**Endpoint:** `GET /api/categories/parent`

**Use Case:** Show only main categories in dropdown/selector

**Response:**
```json
{
  "success": true,
  "data": {
    "categories": [
      {
        "id": "category_id",
        "name": "Models",
        "slug": "models",
        "description": "AI Model specific prompts",
        "order": 1
      }
    ]
  }
}
```

### 3. Get Subcategories for a Category

**Endpoint:** `GET /api/categories/{category_id_or_slug}`

**Use Case:** When user selects a main category, get its subcategories

**Example:** `GET /api/categories/models` or `GET /api/categories/67a1234567890abcdef12345`

**Response:**
```json
{
  "success": true,
  "data": {
    "category": {
      "id": "category_id",
      "name": "Models",
      "slug": "models",
      "subcategories": [
        {
          "id": "subcategory_id",
          "name": "ChatGPT Image prompts",
          "slug": "chatgpt-image-prompts"
        },
        {
          "id": "subcategory_id_2",
          "name": "Midjourney prompts",
          "slug": "midjourney-prompts"
        }
      ]
    }
  }
}
```

### 4. Get Tags for a Subcategory (IMPORTANT - Main Flow)

**Endpoint:** `GET /api/categories/{subcategory_id_or_slug}/tags`

**Use Case:** When user selects a subcategory, get available tags

**Example:** `GET /api/categories/chatgpt-image-prompts/tags`

**Response:**
```json
{
  "success": true,
  "data": {
    "tags": [
      {
        "id": "tag_id_1",
        "name": "3D",
        "slug": "chatgpt-image-prompts-3d",
        "subcategory_id": "subcategory_id",
        "usage_count": 0
      },
      {
        "id": "tag_id_2",
        "name": "Abstract",
        "slug": "chatgpt-image-prompts-abstract",
        "subcategory_id": "subcategory_id",
        "usage_count": 0
      },
      {
        "id": "tag_id_3",
        "name": "Other",
        "slug": "chatgpt-image-prompts-other",
        "subcategory_id": "subcategory_id",
        "usage_count": 0
      }
    ],
    "subcategory_id": "subcategory_id",
    "subcategory_name": "ChatGPT Image prompts",
    "subcategory_slug": "chatgpt-image-prompts"
  }
}
```

### 5. Alternative: Get Tags by Subcategory ID

**Endpoint:** `GET /api/tags/subcategory/{subcategory_id}`

**Use Case:** Alternative endpoint using tag routes

**Example:** `GET /api/tags/subcategory/67a1234567890abcdef12345`

**Response:**
```json
{
  "success": true,
  "data": {
    "tags": [...],
    "subcategory_id": "67a1234567890abcdef12345"
  }
}
```

### 6. Search Tags within Subcategory

**Endpoint:** `GET /api/tags/search?q={query}&subcategory_id={subcategory_id}`

**Use Case:** Allow users to search/filter tags within selected subcategory

**Example:** `GET /api/tags/search?q=anime&subcategory_id=67a1234567890abcdef12345`

---

## Frontend Implementation Flow

### Step 1: Load Categories Tree on Page Load

```javascript
// Initial load - get all categories with subcategories
const response = await fetch('/api/categories/tree');
const { data } = await response.json();
const categories = data.categories;

// Store in state
setCategories(categories);
```

### Step 2: Category Selection

```javascript
// When user selects a main category
const handleCategorySelect = (categoryId) => {
  setSelectedCategory(categoryId);
  
  // Find subcategories from already loaded tree
  const category = categories.find(c => c.id === categoryId);
  setSubcategories(category.subcategories);
  
  // Reset subcategory and tags selection
  setSelectedSubcategory(null);
  setTags([]);
  setSelectedTags([]);
};
```

### Step 3: Subcategory Selection - Load Tags

```javascript
// When user selects a subcategory, fetch its tags
const handleSubcategorySelect = async (subcategoryId) => {
  setSelectedSubcategory(subcategoryId);
  
  // Fetch tags for this subcategory
  const response = await fetch(`/api/categories/${subcategoryId}/tags`);
  const { data } = await response.json();
  
  setTags(data.tags);
  setSelectedTags([]); // Reset selected tags
};
```

### Step 4: Tag Selection

```javascript
// User selects tags (multiple selection allowed)
const handleTagSelect = (tagId) => {
  setSelectedTags(prev => {
    if (prev.includes(tagId)) {
      return prev.filter(id => id !== tagId);
    }
    return [...prev, tagId];
  });
};
```

### Step 5: Submit Form with Selected Data

#### For Posts/Questions

```javascript
// When creating a post/question
const handlePostSubmit = async () => {
  const formData = new FormData();
  formData.append('title', title);
  formData.append('body', body);
  formData.append('category_id', selectedCategory);
  formData.append('subcategory_id', selectedSubcategory);
  // Tags: comma-separated slugs
  formData.append('tags', selectedTags.map(tagId => {
    const tag = tags.find(t => t.id === tagId);
    return tag.slug;
  }).join(','));
  
  await fetch('/api/posts/create', {
    method: 'POST',
    body: formData
  });
};
```

#### For Contests

```javascript
// When creating a contest
const handleContestSubmit = async () => {
  const formData = new FormData();
  formData.append('title', title);
  formData.append('description', description);
  formData.append('category_id', selectedCategory);
  formData.append('subcategory_id', selectedSubcategory);
  // Tags: comma-separated slugs
  formData.append('tags', selectedTags.map(tagId => {
    const tag = tags.find(t => t.id === tagId);
    return tag.slug;
  }).join(','));
  formData.append('difficulty', difficulty);
  formData.append('total_prize', totalPrize);
  formData.append('max_participants', maxParticipants);
  formData.append('start_date', startDate.toISOString());
  formData.append('end_date', endDate.toISOString());
  if (coverImage) {
    formData.append('cover_image', coverImage);
  }
  
  await fetch('/api/contests/create', {
    method: 'POST',
    body: formData
  });
};
```

---

## UI Component Structure (React Example)

```jsx
function CategoryTagSelector() {
  const [categories, setCategories] = useState([]);
  const [subcategories, setSubcategories] = useState([]);
  const [tags, setTags] = useState([]);
  
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [selectedSubcategory, setSelectedSubcategory] = useState(null);
  const [selectedTags, setSelectedTags] = useState([]);

  // Load categories on mount
  useEffect(() => {
    fetchCategories();
  }, []);

  return (
    <div>
      {/* Step 1: Category Dropdown */}
      <div>
        <label>Category *</label>
        <select 
          value={selectedCategory || ''} 
          onChange={(e) => handleCategorySelect(e.target.value)}
        >
          <option value="">Select Category</option>
          {categories.map(cat => (
            <option key={cat.id} value={cat.id}>{cat.name}</option>
          ))}
        </select>
      </div>

      {/* Step 2: Subcategory Dropdown (shown after category selected) */}
      {selectedCategory && (
        <div>
          <label>Subcategory *</label>
          <select 
            value={selectedSubcategory || ''} 
            onChange={(e) => handleSubcategorySelect(e.target.value)}
          >
            <option value="">Select Subcategory</option>
            {subcategories.map(sub => (
              <option key={sub.id} value={sub.id}>
                {sub.name} ({sub.tag_count} tags)
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Step 3: Tags Multi-select (shown after subcategory selected) */}
      {selectedSubcategory && tags.length > 0 && (
        <div>
          <label>Tags (select multiple)</label>
          <div className="tags-grid">
            {tags.map(tag => (
              <button
                key={tag.id}
                className={selectedTags.includes(tag.id) ? 'selected' : ''}
                onClick={() => handleTagSelect(tag.id)}
              >
                {tag.name}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

---

## Important Notes

### 1. Tag Uniqueness
- Tags are unique per subcategory
- Tag slug format: `{subcategory-slug}-{tag-slug}` (e.g., `chatgpt-image-prompts-anime`)
- Same tag name can exist in multiple subcategories (e.g., "Animals" in both "Cartoon prompts" and "Painting prompts")

### 2. "Other" Option
- Every category, subcategory, and tag list includes "Other" as fallback
- If user can't find appropriate option, they select "Other"

### 3. No Custom Tags
- Users CANNOT create custom tags
- They must select from the predefined list
- Remove any "create new tag" functionality from frontend

### 4. Validation
- Category is REQUIRED
- Subcategory is REQUIRED
- Tags are OPTIONAL but recommended
- When submitting, send tag slugs (not names or IDs)

### 5. Caching Recommendations
- Cache categories tree on initial load (changes infrequently)
- Cache tags by subcategory to reduce API calls
- Invalidate cache on admin category/tag updates

---

## Data Summary

| Level | Count | Example |
|-------|-------|---------|
| Main Categories | 8 | Models, Art, Logos, Graphics, Productivity, Marketing, Photography, Games |
| Subcategories | 56 | ChatGPT Image prompts, Midjourney prompts, Anime prompts, Logo prompts |
| Tags | 1,487 | 3D, Abstract, Animal, Anime, Business, Code, Email, etc. |

---

## Quick Reference - API Endpoints

### Category/Tag Endpoints

| Action | Method | Endpoint |
|--------|--------|----------|
| Get all categories (tree) | GET | `/api/categories/tree` |
| Get parent categories only | GET | `/api/categories/parent` |
| Get category by ID/slug | GET | `/api/categories/{identifier}` |
| Get subcategory tags | GET | `/api/categories/{subcategory_id}/tags` |
| Get tags by subcategory ID | GET | `/api/tags/subcategory/{subcategory_id}` |
| Search tags in subcategory | GET | `/api/tags/search?q={query}&subcategory_id={id}` |
| Get all tags | GET | `/api/tags/all` |
| Get popular tags | GET | `/api/tags/popular` |

### Post Endpoints (Updated)

| Action | Method | Endpoint | Body Params |
|--------|--------|----------|-------------|
| Create post | POST | `/api/posts/create` | `title`, `body`, `category_id`, `subcategory_id`, `tags` (comma-separated slugs) |
| Update post | POST | `/api/posts/{post_id}/update` | `category_id`, `subcategory_id`, `tags` (optional) |
| Get posts | GET | `/api/posts/all` | Query: `category_id`, `subcategory_id`, `tag` |

### Contest Endpoints (Updated)

| Action | Method | Endpoint | Body Params |
|--------|--------|----------|-------------|
| Create contest | POST | `/api/contests/create` | `title`, `description`, `category_id`, `subcategory_id`, `tags` (comma-separated slugs), `difficulty`, `total_prize`, `max_participants`, `start_date`, `end_date` |
| Update contest | PUT | `/api/contests/{contest_id}` | `category_id`, `subcategory_id`, `tags` (optional) |
| Get contests | GET | `/api/contests` | Query: `category_id`, `subcategory_id`, `tag`, `status`, `difficulty` |

---

## Contest-Specific Changes

### Create Contest Request

```
POST /api/contests/create
Content-Type: multipart/form-data

title: "AI Art Contest"
description: "Create amazing AI-generated art..."
category_id: "67a1234567890abcdef12345"           // Required: Main category ID
subcategory_id: "67a1234567890abcdef12346"        // Optional: Subcategory ID
tags: "anime,3d,abstract"                          // Optional: Comma-separated tag slugs
difficulty: "intermediate"                         // Required: beginner/intermediate/advanced
total_prize: 100                                   // Required: Prize pool
max_participants: 50                               // Required
start_date: "2024-01-15T00:00:00Z"                // Required: ISO format
end_date: "2024-01-30T00:00:00Z"                  // Required: ISO format
cover_image: [file]                                // Optional
```

### Update Contest Request

```
PUT /api/contests/{contest_id}
Content-Type: multipart/form-data

category_id: "67a1234567890abcdef12345"           // Optional
subcategory_id: "67a1234567890abcdef12346"        // Optional
tags: "anime,3d"                                   // Optional: Comma-separated tag slugs
// ... other fields
```

### Filter Contests by Category/Tag

```
GET /api/contests?category_id=67a1234...&subcategory_id=67a1234...&tag=anime&status=active
```

### Contest Response Structure

```json
{
  "id": "contest_id",
  "title": "AI Art Contest",
  "description": "...",
  "category_id": "67a1234567890abcdef12345",
  "subcategory_id": "67a1234567890abcdef12346",
  "tags": ["anime", "3d", "abstract"],
  "category": "Models",                            // Legacy field (category name)
  "difficulty": "intermediate",
  "status": "active",
  "total_prize": 100,
  // ... other fields
}
```

---

## Post-Specific Changes

### Create Post Request

```
POST /api/posts/create
Content-Type: multipart/form-data

title: "How to write Midjourney prompts?"
body: "I'm trying to learn..."
category_id: "67a1234567890abcdef12345"           // Required: Main category ID
subcategory_id: "67a1234567890abcdef12346"        // Required when using tags
tags: "anime,landscapes"                           // Optional: Comma-separated tag slugs
files: [file1, file2]                              // Optional: Attachments
```

### Tag Validation Rules

1. **Tags require subcategory**: If you send tags without selecting a subcategory, you'll get an error:
   ```json
   {
     "success": false,
     "errors": {
       "subcategory_id": "Please select a subcategory to use tags"
     }
   }
   ```

2. **Invalid tags rejected**: If you send tags not linked to the subcategory:
   ```json
   {
     "success": false,
     "message": "Invalid tags provided",
     "errors": {
       "tags": ["'invalid-tag' is not a valid tag for this subcategory"]
     }
   }
   ```

---

## Migration Notes

If you have existing posts/contests with old category/tag data:

1. Old categories in the database will remain (the seed script doesn't delete existing data unless `--clear` flag is used)
2. New structure is additive
3. Consider creating a migration script to update old posts to new category/tag structure
4. Frontend should handle cases where posts have old/missing category data
5. **Contests**: Old contests may have `category` (string name) but not `category_id`. Handle gracefully.
6. **Posts**: Old posts may have user-created tags. These will remain but won't be in the predefined list.

---

## Backward Compatibility

The API maintains backward compatibility:

- **Legacy `category` field**: Still available in responses (stores category name)
- **Old contests**: Will still work but should be updated to use `category_id`
- **Old posts with custom tags**: Will still display but users cannot create new custom tags
