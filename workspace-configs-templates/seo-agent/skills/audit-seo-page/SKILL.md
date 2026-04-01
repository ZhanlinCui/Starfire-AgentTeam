---
name: audit-seo-page
description: Audits existing web pages for SEO issues and provides actionable improvement recommendations.
version: 1.0.0
tags:
  - seo
  - audit
  - analysis
examples:
  - "Audit this page content for SEO issues"
  - "What SEO improvements can I make to this landing page?"
  - "Review my blog post for search optimization"
---

# Audit SEO Page

When asked to audit content for SEO, analyze these factors and provide a structured report:

## Checklist

### Title & Meta
- [ ] Title tag present and 50-60 characters
- [ ] Primary keyword in title (preferably near the front)
- [ ] Meta description present and 150-160 characters
- [ ] Meta description includes a call-to-action

### Content Structure
- [ ] Exactly one H1 tag
- [ ] H1 contains primary keyword
- [ ] 3-5 H2 sections with relevant secondary keywords
- [ ] Proper heading hierarchy (no skipping levels)
- [ ] Word count in 800-1500 range for landing pages

### Keyword Usage
- [ ] Primary keyword density between 1-2%
- [ ] Keyword appears in first 100 words
- [ ] Secondary keywords distributed naturally across H2 sections
- [ ] No keyword stuffing

### Technical SEO
- [ ] Internal links present (2-3 minimum)
- [ ] Image alt text suggestions included
- [ ] Schema markup recommendations
- [ ] Mobile-friendly structure (short paragraphs, scannable)

### User Experience
- [ ] Clear call-to-action
- [ ] Content provides genuine value (not just keyword filler)
- [ ] Logical flow from problem to solution
- [ ] FAQ section for featured snippet potential

## Output Format
Provide the audit as a structured report with:
1. **Score**: Overall SEO score out of 100
2. **Strengths**: What the page does well
3. **Issues**: Problems found, ordered by impact (high/medium/low)
4. **Recommendations**: Specific, actionable fixes for each issue
5. **Revised snippets**: Show before/after for the top 3 improvements

Use the `score_seo` tool if available to get a quantitative baseline before providing qualitative analysis.
