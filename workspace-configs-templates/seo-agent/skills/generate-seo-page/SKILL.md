---
name: generate-seo-page
description: Generates SEO-optimized landing pages with proper structure, meta tags, and keyword placement.
version: 1.0.0
tags:
  - seo
  - content
  - landing-page
examples:
  - "Generate an SEO landing page for a Vancouver renovation company"
  - "Create an optimized blog post about kitchen remodeling trends"
  - "Write a service page targeting 'commercial roofing repair'"
---

# Generate SEO Landing Page

When asked to generate an SEO page, follow this process:

## Step 1: Keyword Analysis
- Identify the primary keyword from the user's request
- Infer 3-5 secondary/long-tail keywords related to the topic
- If web_search is available, research competitor pages for the primary keyword

## Step 2: Page Structure
Generate the page with this structure:
- **Title tag** (50-60 chars): Include primary keyword near the front
- **Meta description** (150-160 chars): Compelling summary with primary keyword
- **H1**: One per page, contains primary keyword naturally
- **H2s**: 3-5 sections, each targeting a secondary keyword
- **H3s**: Sub-sections where depth is needed
- **Body**: 800-1500 words, keyword density 1-2% for primary keyword

## Step 3: On-Page SEO Elements
Include in every generated page:
- Internal linking suggestions (2-3 related pages)
- Image alt text recommendations
- Schema markup suggestions (LocalBusiness, FAQ, or Article as appropriate)
- Call-to-action placement

## Step 4: Output Format
Return the page as structured markdown with:
- SEO metadata block at the top (title, description, keywords)
- Full page content with proper header hierarchy
- A brief SEO score summary at the bottom

## Quality Rules
- Never keyword-stuff — content must read naturally
- Every H2 should provide genuine value, not just keyword variations
- Include at least one FAQ section when relevant (good for featured snippets)
- Prefer specific, actionable language over generic filler
