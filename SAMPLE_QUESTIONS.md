# 📝 Sample Questions for PromptForum

**Real-world examples of how to write great questions with prompts and images**

---

## Example 1: Midjourney Character Consistency

### Title
```
How to maintain consistent character appearance across multiple Midjourney generations?
```

### Category
`AI Models & Tools` → `Midjourney`

### Tags
```
midjourney, character-design, consistency, ai-art
```

### Body (Full Markdown)

````markdown
# Problem: Character Changes Every Generation

I'm creating a graphic novel and need the same character in 20+ different scenes. Every time I generate a new image, the character looks completely different.

## What I've Tried So Far

### Attempt 1: Using Seed Parameter
```bash
/imagine prompt: young woman with long red hair, green eyes, wearing blue medieval dress, 
fantasy art style --seed 12345 --v 6.0
```

**Result:** ❌ Face shape and hair color still varies

![Seed Attempt 1](http://localhost:8000/uploads/user_123/seed_attempt_1.png)
![Seed Attempt 2](http://localhost:8000/uploads/user_123/seed_attempt_2.png)

*Notice how the face structure is completely different!*

---

### Attempt 2: Extremely Detailed Description
```bash
/imagine prompt: portrait of a 25-year-old woman, oval face shape, sharp jawline, 
high cheekbones, almond-shaped green eyes, long straight red hair reaching mid-back, 
pale skin with light freckles, wearing sapphire blue medieval dress with gold trim, 
standing pose, fantasy art style, professional digital art --seed 12345 --v 6.0
```

**Result:** ❌ Better but still inconsistent

![Detailed Attempt 1](http://localhost:8000/uploads/user_123/detailed_1.png)
![Detailed Attempt 2](http://localhost:8000/uploads/user_123/detailed_2.png)

*The dress and general look improved, but facial features still change*

---

### Attempt 3: Style Reference (--sref)
```bash
/imagine prompt: young woman in blue dress --sref https://reference.url/art-style.png 
--seed 12345 --v 6.0
```

**Result:** ❌ Helps with art style, NOT character consistency

---

## My Specific Questions

1. **Is there a parameter specifically for character locking?** I've heard rumors about `--cref` but can't find documentation.

2. **Should I generate a "base" character first** and then reference it?

3. **What's the optimal `--cw` (character weight) value** for maximum consistency?

4. **Does aspect ratio affect consistency?** All my attempts used `--ar 2:3`

---

## What I Need

- ✅ Same facial features (eyes, nose, mouth, jawline)
- ✅ Same hair color and style
- ⚠️ Different poses are fine
- ⚠️ Different clothing is fine
- ⚠️ Different backgrounds/settings are fine

---

## Comparison Table

| Attempt | Method | Consistency Score | Time Spent |
|---------|--------|-------------------|------------|
| 1 | Seed only | 20% | 2 hours |
| 2 | Detailed prompt | 45% | 4 hours |
| 3 | Style reference | 30% | 3 hours |

---

## Additional Context

**My Setup:**
- Midjourney v6.0
- Discord bot interface
- ~$20 budget for testing
- Need 20 consistent images total

**Example of what I'm trying to achieve:**

![Perfect Example](http://localhost:8000/uploads/user_123/perfect_example.png)

*This artist achieved perfect consistency - how?!*

---

## Attached Files

📎 **reference_sheet.pdf** (2.3 MB) - Character design reference  
📎 **all_attempts.zip** (5.1 MB) - All 30 failed generation attempts

---

**Any help would be greatly appreciated!** I've been stuck on this for a week 😓
````

---

## Example 2: ChatGPT Prompt Engineering

### Title
```
How to get ChatGPT to follow exact JSON output format consistently?
```

### Category
`AI Models & Tools` → `ChatGPT / OpenAI`

### Tags
```
chatgpt, gpt-4, json-output, prompt-engineering, structured-data
```

### Body (Full Markdown)

````markdown
# Issue: ChatGPT Ignores JSON Schema 50% of the Time

I'm building a product description generator that needs **exact JSON format** for my e-commerce platform. ChatGPT keeps adding extra fields or changing the structure.

---

## Required Output Format

```json
{
  "title": "string (max 60 chars)",
  "description": "string (max 500 chars)",
  "features": ["string", "string", "string"],
  "specifications": {
    "weight": "string",
    "dimensions": "string",
    "material": "string"
  },
  "seo_keywords": ["string", "string", "string"]
}
```

---

## My Current Prompt

```
Generate a product description for a laptop.

Output format:
{
  "title": "...",
  "description": "...",
  "features": [...],
  "specifications": {...},
  "seo_keywords": [...]
}
```

---

## What Actually Happens

### Good Response (50% of the time) ✅

```json
{
  "title": "High-Performance Gaming Laptop",
  "description": "Powerful laptop designed for...",
  "features": ["Intel i7 processor", "16GB RAM", "RTX 3060"],
  "specifications": {
    "weight": "2.3kg",
    "dimensions": "35x25x2cm",
    "material": "Aluminum"
  },
  "seo_keywords": ["gaming", "laptop", "performance"]
}
```

![Working Output](http://localhost:8000/uploads/user_456/good_response.png)

---

### Bad Response (50% of the time) ❌

```json
{
  "title": "High-Performance Gaming Laptop",
  "description": "Powerful laptop designed for...",
  "features": ["Intel i7 processor", "16GB RAM", "RTX 3060"],
  "specifications": {
    "weight": "2.3kg",
    "dimensions": "35x25x2cm",
    "material": "Aluminum"
  },
  "seo_keywords": ["gaming", "laptop", "performance"],
  "price_range": "$1200-$1500",           ← EXTRA FIELD
  "target_audience": "Gamers and creators" ← EXTRA FIELD
}
```

![Bad Output](http://localhost:8000/uploads/user_456/bad_response.png)

*My JSON parser crashes because of unexpected fields!*

---

## What I've Tried

### ❌ Attempt 1: System message enforcement
```python
system_message = """You are a JSON generator. 
Output ONLY valid JSON. Do not add extra fields."""

response = openai.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": system_message},
        {"role": "user", "content": prompt}
    ]
)
```

**Result:** Still adds extra fields randomly

---

### ❌ Attempt 2: JSON Schema in prompt
```python
prompt = f"""Generate product description.

STRICT JSON SCHEMA:
{{
  "title": string,
  "description": string,
  "features": array of strings,
  "specifications": object,
  "seo_keywords": array of strings
}}

DO NOT add any fields not in this schema.

Product: {product_name}
"""
```

**Result:** Slightly better (70% success) but not consistent

---

### ❌ Attempt 3: Function calling
```python
functions = [{
    "name": "generate_description",
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "description": {"type": "string"},
            # ... all fields
        },
        "required": ["title", "description", ...]
    }
}]
```

**Result:** ❌ **ERROR: Functions not supported in gpt-4 yet?**

---

## Specific Questions

1. **Is there a GPT-4 parameter** that enforces strict JSON schema?

2. **Should I use response_format={"type": "json_object"}?** Does this help?

3. **Is prompt engineering enough** or do I need post-processing validation?

4. **What's the best practice** for production JSON generation?

---

## Code Context

My current implementation:

```python
import openai
import json

def generate_product_description(product_name):
    prompt = f"""
    Generate a product description for: {product_name}
    
    Output ONLY this exact JSON structure:
    {{
      "title": "string",
      "description": "string", 
      "features": ["string"],
      "specifications": {{}},
      "seo_keywords": ["string"]
    }}
    """
    
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    
    # Parse JSON
    try:
        data = json.loads(response.choices[0].message.content)
        return data
    except json.JSONDecodeError as e:
        print(f"JSON parsing failed: {e}")
        return None

# Test
result = generate_product_description("Gaming Laptop")
print(result)
```

---

## Error Logs

```bash
File "generator.py", line 24, in generate_product_description
    data = json.loads(response.choices[0].message.content)
json.decoder.JSONDecodeError: Expecting property name enclosed in double quotes: 
line 8 column 3 (char 245)
```

![Error Screenshot](http://localhost:8000/uploads/user_456/error_screenshot.png)

---

## My Environment

- **Model:** GPT-4 (not GPT-4-Turbo)
- **SDK:** `openai==1.3.0`
- **Python:** 3.11
- **Use Case:** E-commerce automation
- **Volume:** ~500 products/day

---

## What Success Looks Like

I need **100% consistent JSON** that:
- ✅ Always follows exact schema
- ✅ Never adds extra fields
- ✅ Never skips required fields
- ✅ Parses without errors

---

**Is this even possible with ChatGPT, or should I look at other models?**

Any production-tested solutions would be life-saving! 🙏
````

---

## Example 3: Stable Diffusion Prompt Issue

### Title
```
Why does Stable Diffusion ignore negative prompts for "hands"?
```

### Category
`AI Models & Tools` → `Stable Diffusion`

### Tags
```
stable-diffusion, negative-prompt, hands, anatomy, prompt-debugging
```

### Body (Full Markdown)

````markdown
# Frustrating Issue: Broken Hands Despite Negative Prompts

No matter what I put in negative prompts, Stable Diffusion keeps generating **horrific mutant hands** with 6+ fingers.

---

## My Setup

```yaml
Model: Stable Diffusion XL 1.0
Sampler: DPM++ 2M Karras
Steps: 30
CFG Scale: 7
Resolution: 1024x1024
```

---

## Current Prompt

### Positive Prompt
```
professional portrait photo of a young woman holding a coffee cup, 
natural lighting, realistic hands, proper anatomy, 5 fingers, 
detailed fingers, photorealistic, high quality, 8k
```

### Negative Prompt
```
deformed hands, mutated hands, extra fingers, missing fingers, 
fused fingers, too many fingers, bad anatomy, ugly hands, 
6 fingers, 7 fingers, malformed hands, poorly drawn hands
```

---

## What I Get (Results)

![Result 1 - 7 Fingers](http://localhost:8000/uploads/user_789/result_1.png)
![Result 2 - Fused Fingers](http://localhost:8000/uploads/user_789/result_2.png)
![Result 3 - Alien Hand](http://localhost:8000/uploads/user_789/result_3.png)

**Every. Single. Time.** 😭

---

## Comparison: Prompts vs Results

| Attempt | CFG Scale | Steps | Result |
|---------|-----------|-------|--------|
| 1 | 7 | 20 | 7 fingers |
| 2 | 9 | 30 | Fused fingers |
| 3 | 5 | 40 | 6 fingers |
| 4 | 7 | 50 | Distorted hand |

---

## Things I've Tried

### ❌ Method 1: More negative prompts
```
Negative: deformed hands, mutated hands, extra fingers, missing fingers, 
fused fingers, too many fingers, 6 fingers, 7 fingers, 8 fingers, 
bad anatomy, ugly hands, malformed hands, poorly drawn hands, 
bad hands, worst quality hands, mutated fingers, extra digit, 
fewer digits, cropped hands, jpeg artifacts on hands
```

**Result:** No improvement

---

### ❌ Method 2: Emphasizing in positive
```
Positive: (perfect hands:1.5), (5 fingers:1.5), (detailed fingers:1.4), 
(realistic anatomy:1.5), proper hand structure
```

**Result:** Still broken

---

### ❌ Method 3: ControlNet Depth
```python
# Using ControlNet with depth map
controlnet_args = {
    "model": "control_v11f1p_sd15_depth",
    "image": reference_hand_image,
    "weight": 1.0
}
```

**Result:** Better but still not perfect

![ControlNet Result](http://localhost:8000/uploads/user_789/controlnet_attempt.png)

---

### ❌ Method 4: Inpainting hands separately
```
1. Generate image with hands hidden
2. Inpaint hands using reference
```

**Result:** Time-consuming and inconsistent

---

## Code I'm Using

```python
from diffusers import StableDiffusionXLPipeline
import torch

pipe = StableDiffusionXLPipeline.from_pretrained(
    "stabilityai/stable-diffusion-xl-base-1.0",
    torch_dtype=torch.float16
).to("cuda")

prompt = "professional portrait of woman holding coffee cup"
negative = "deformed hands, mutated hands, extra fingers, 6 fingers"

image = pipe(
    prompt=prompt,
    negative_prompt=negative,
    num_inference_steps=30,
    guidance_scale=7.0
).images[0]

image.save("output.png")
```

---

## Questions

1. **Is this a known limitation** of SDXL 1.0?

2. **Does the base model need fine-tuning** on hand datasets?

3. **Are there specific LoRAs** that fix hand anatomy?

4. **Should I switch to a different model?** (Midjourney doesn't have this issue!)

5. **What's the professional workflow** for commercial work with perfect hands?

---

## Hand Reference Images

This is what I want:

![Perfect Hand Reference 1](http://localhost:8000/uploads/user_789/perfect_hand_1.png)
![Perfect Hand Reference 2](http://localhost:8000/uploads/user_789/perfect_hand_2.png)

Simple, realistic, 5-finger hands!

---

## Why This Matters

I'm creating product photography for an online store. **Customers notice bad hands immediately** and it looks unprofessional.

Examples of comments I've received:
> "Why does the model have 7 fingers? This looks AI-generated and cheap."
> "I can't buy from a store that uses such obviously fake images."

---

## Additional Files

📎 **generation_logs.txt** (45 KB) - Full generation parameters for all 50 attempts  
📎 **hand_references.zip** (3.2 MB) - Reference photos of correct hand anatomy

---

**I've spent 20+ hours on this. Is there a solution or should I just hire a photographer?** 😤

Any Stable Diffusion experts who've solved this, please share your secrets!
````

---

## Example 4: Claude Prompt Structure

### Title
```
How to structure Claude prompts for consistent creative writing output?
```

### Category
`Prompts` → `System Prompts`

### Tags
```
claude, creative-writing, prompt-structure, consistency, storytelling
```

### Body (Full Markdown)

````markdown
# Challenge: Claude's Writing Style Changes Mid-Story

I'm using Claude 3 Opus to write a fantasy novel. The **tone and style shift dramatically** between chapters, even with the same prompt.

---

## My Current Prompt Template

```xml
<task>
Write the next chapter of a dark fantasy novel.
</task>

<style>
- Tone: Dark, gritty, atmospheric
- POV: Third-person limited
- Tense: Past tense
- Style: Similar to George R.R. Martin
</style>

<context>
Previous chapter: [summary here]
Current scene: [description here]
</context>

<requirements>
- Length: 2000-2500 words
- Include dialogue
- End with cliffhanger
</requirements>

<characters>
- Kira: Assassin, cynical, skilled fighter
- Marcus: Knight, honorable, naive
</characters>
```

---

## What Happens

### Chapter 1 Output (Perfect) ✅

```
The blade whispered through darkness, finding flesh with practiced precision. 
Kira didn't wait to watch the body fall—she never did. Three seconds to 
confirm the kill, five to disappear into shadow. Any longer was amateur hour.

Marcus would be furious when he learned of tonight's work, but Marcus was 
always furious these days. Honor had that effect on people; it made them 
slow, predictable, dead.
```

![Chapter 1 Screenshot](http://localhost:8000/uploads/user_234/chapter1_style.png)

**Perfect!** Dark, gritty, concise sentences. ⭐⭐⭐⭐⭐

---

### Chapter 3 Output (Completely Different) ❌

```
Kira felt a profound sense of melancholy wash over her as she contemplated 
the philosophical implications of her chosen profession. Was she truly free, 
or merely a puppet dancing on strings of fate? The existential weight of 
her existence pressed down upon her shoulders like the burdensome mantle 
of destiny itself.

Marcus, her stalwart companion and beacon of righteousness in this morally 
ambiguous world, approached with measured steps...
```

![Chapter 3 Screenshot](http://localhost:8000/uploads/user_234/chapter3_style.png)

**What?!** Now it's flowery, philosophical, and wordy. This is NOT the style I wanted! 😤

---

## Side-by-Side Comparison

| Aspect | Chapter 1 (Good) | Chapter 3 (Bad) |
|--------|------------------|-----------------|
| **Sentence Length** | Short, punchy | Long, rambling |
| **Vocabulary** | Simple, direct | Pretentious, verbose |
| **Tone** | Dark, cynical | Philosophical, flowery |
| **Pacing** | Fast | Slow |

![Style Comparison](http://localhost:8000/uploads/user_234/style_comparison.png)

---

## What I've Tried

### ❌ Attempt 1: System Message
```xml
<system>
You are a dark fantasy writer. Write in short, punchy sentences. 
Avoid flowery language. Keep it gritty and fast-paced.
</system>
```

**Result:** Helps for 1-2 chapters, then reverts

---

### ❌ Attempt 2: Style Examples
```xml
<style_examples>
GOOD: "The knife found its mark. Quick. Silent. Professional."
BAD: "The blade, gleaming with malevolent purpose, descended gracefully..."

GOOD: "Marcus talked about honor. Kira talked about survival."
BAD: "Marcus waxed poetic about the philosophical nature of honor..."
</style_examples>
```

**Result:** Better but still inconsistent

---

### ❌ Attempt 3: Temperature = 0.3
```python
response = anthropic.messages.create(
    model="claude-3-opus-20240229",
    temperature=0.3,  # Lower = more consistent
    messages=[{"role": "user", "content": prompt}]
)
```

**Result:** More consistent but writing feels robotic

---

### ❌ Attempt 4: Few-Shot Examples
```xml
<examples>
<example>
Input: Write opening paragraph for Chapter 2
Output: Blood dried fastest in winter. Kira had learned that early. 
Tonight's work was clean—one cut, one body, one less problem.
</example>

<example>
Input: Write opening paragraph for Chapter 4
Output: The tavern stank of ale and desperation. Kira's kind of place. 
Marcus stood out like a virgin at a brothel.
</example>
</examples>

<task>
Now write opening for Chapter 5...
</task>
```

**Result:** BEST so far but still drifts after ~1000 words

---

## My Code

```python
import anthropic

client = anthropic.Anthropic(api_key="...")

def generate_chapter(chapter_num, previous_summary, scene_description):
    prompt = f"""
    <task>Write Chapter {chapter_num} of dark fantasy novel</task>
    
    <style_rules>
    1. Short sentences (max 15 words)
    2. Active voice only
    3. No flowery adjectives
    4. Cynical tone
    5. Fast pacing
    </style_rules>
    
    <context>
    Previous: {previous_summary}
    Scene: {scene_description}
    </context>
    
    <length>2000-2500 words</length>
    
    Write the chapter now. Maintain dark, punchy style throughout.
    """
    
    response = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=4000,
        temperature=0.4,
        messages=[{"role": "user", "content": prompt}]
    )
    
    return response.content[0].text

# Generate
chapter_5 = generate_chapter(5, summary_ch4, "Kira infiltrates castle")
print(chapter_5)
```

---

## Specific Questions

1. **Is there a way to "lock" writing style** in Claude?

2. **Should I use XML tags differently?** I've seen `<style>`, `<tone>`, `<voice>` used

3. **Does conversation history help?** If I include previous chapters as context?

4. **What's the optimal temperature** for consistent creative writing?

5. **Are there specific phrases** that anchor style better?

---

## What Works in Midjourney (Comparison)

With Midjourney, I can use `--sref` to lock style perfectly:

```bash
/imagine prompt: dark fantasy scene --sref https://my-style-ref.png
```

![Midjourney Style Consistency](http://localhost:8000/uploads/user_234/midjourney_comparison.png)

**100% style consistency across 50+ images!**

**Why can't Claude do this for writing?** 😭

---

## Ideal Outcome

I need Claude to:
- ✅ Maintain consistent tone throughout entire novel (20+ chapters)
- ✅ Keep sentence structure similar (short, punchy)
- ✅ Avoid style drift after 1000+ words
- ✅ Remember character voices

---

## Additional Context

**Novel Stats:**
- Genre: Dark fantasy
- Target length: 100,000 words
- Chapters: 25
- Currently on: Chapter 8

**What I've written so far:**
📎 **chapters_1-7.pdf** (89 KB) - First 7 chapters for reference  
📎 **character_bibles.docx** (45 KB) - Detailed character profiles  
📎 **world_notes.txt** (23 KB) - World-building notes

---

**I'm considering switching to GPT-4, but I prefer Claude's writing quality when it works.**

Has anyone solved this for long-form creative writing? Any prompt engineers here? 🙏
````

---

## Key Elements in Each Sample

### ✅ All samples include:

1. **Clear problem statement**
   - What's wrong
   - Why it matters

2. **What I've tried** (multiple attempts)
   - Code examples
   - Different approaches
   - Results for each

3. **Visual evidence**
   - Screenshots
   - Comparison images
   - Before/after examples

4. **Specific questions**
   - Numbered list
   - Clear and focused

5. **Code snippets**
   - With syntax highlighting
   - Actual runnable code

6. **Context & specifications**
   - Version numbers
   - Environment details
   - Use case explanation

7. **File attachments**
   - Reference materials
   - Logs
   - Additional data

8. **Markdown formatting**
   - Headers for structure
   - Tables for comparisons
   - Lists for clarity
   - Blockquotes for emphasis

---

## 🎯 Why These Are Good Questions

### They follow Stack Overflow best practices:

✅ **Specific and focused**  
✅ **Show research effort**  
✅ **Include reproducible examples**  
✅ **Provide visual evidence**  
✅ **Have clear success criteria**  
✅ **Include relevant context**  
✅ **Ask specific answerable questions**

### They demonstrate:

- 🔍 Problem-solving attempts
- 📊 Data and metrics
- 💻 Code examples
- 🖼️ Visual proof
- 📝 Clear documentation
- 🎯 Specific goals

---

**These question formats will attract high-quality answers from experts!** 🚀
