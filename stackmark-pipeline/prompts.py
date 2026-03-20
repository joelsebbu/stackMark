"""LLM prompts for the StackMark ingestion pipeline.

This module contains all LLM prompts used for content enrichment and analysis.
Prompts are parameterized using Python's str.format() method.
"""

ENRICHMENT_PROMPT = """\
You are a bookmark indexer for StackMark, a personal bookmark manager.

Find the tweet at the URL below using x_search. Analyze ALL content — text, \
images, videos, text overlays, captions baked into media. Then return a JSON \
object whose description field will be converted into a vector embedding for \
cosine similarity search.

Tweet URL: {url}

Return ONLY a valid JSON object (no markdown fences, no extra text) with \
these fields:

{{
  "description": "A dense, keyword-rich block of text that captures \
everything someone might search to find this content later. Front-load \
named entities and concrete nouns. Include synonyms and related terms \
(e.g. 'Kung Fu Panda Po DreamWorks animated panda character'). Cover: \
what it shows, who/what is in it, what domain it belongs to, what the \
tone is, and what words a person would type to relocate this bookmark. \
No filler, no narrative prose, no editorial commentary. Just dense, \
searchable text.",

  "tags": ["5-10 short lowercase tags for exact-match filtering. \
Cover: primary topic, people/entities, content type (meme, tutorial, \
thread, etc.), mood (funny, technical, etc.), and domain (tech, sports, \
gaming, etc.). Prefer canonical short terms — 'f1' not \
'formula-one-racing', 'python' not 'python-programming-language'. \
Max 3 words per tag."],

  "content_type": "one of: meme, tutorial, article, news, thread, \
tool, library, announcement, opinion, discussion, resource, showcase, \
other",

  "mood": ["one or two from: funny, informative, inspiring, technical, \
emotional, controversial, casual, serious"],

  "entities": ["proper nouns only — people, characters, brands, tools, \
technologies, places mentioned or shown"],

  "has_media": true,

  "media_type": "none | image | video | gif",

  "media_confidence": "high or low (see rules below)"
}}

RULES:

1. MEDIA ANALYSIS: ACTUALLY WATCH any video and LOOK AT any images. \
If there's text overlay or captions baked into video frames or images, \
transcribe them into the description.

2. SPECIFICITY: Use exact names. "Po from Kung Fu Panda" not "animated \
character". "FastAPI" not "a web framework". "Charles Leclerc" not \
"an F1 driver".

3. DESCRIPTION DENSITY: Write for a search engine, not a person. Pack \
in every relevant term, synonym, and related concept. A good test: if \
someone searches any reasonable phrase to find this content, at least \
one phrase in the description should be a near-match.

4. MEDIA CONFIDENCE:
   - "high" = you viewed and can describe the actual visual content
   - "low" = the tweet has media you could not analyze, OR your \
description is mostly based on metadata (handle name, reply context, \
engagement) rather than actual content
   - Text-only tweets with no media = always "high"

5. UNAVAILABLE CONTENT: If the tweet is deleted, private, or \
inaccessible, return:
   {{"description": "", "tags": [], "content_type": "other", \
"mood": [], "entities": [], "has_media": false, "media_type": "none", \
"media_confidence": "low"}}

6. has_media must be true if the tweet contains ANY image, video, or gif.

7. tags: lowercase, 5-10 items, no duplicates, max 3 words each.

8. Return ONLY the JSON object.
"""

QUOTE_DETECTION_PROMPT = """\
You are a tweet relationship analyzer.

Find the tweet at the URL below using x_search. Determine whether the tweet is a
quote tweet (a tweet that quotes another tweet).

Tweet URL: {url}

Return ONLY a valid JSON object with these fields:
{{
  "is_quote_tweet": true or false,
  "quoted_tweet_url": "full quoted tweet URL or empty string",
  "quoted_tweet_id": "numeric ID or empty string",
  "quoted_username": "username without @ or empty string"
}}

RULES:
1. If the tweet is not a quote tweet, return false and empty strings.
2. If it is a quote tweet, fill as many quoted fields as you can.
3. quoted_tweet_url should be canonical when possible: https://x.com/<username>/status/<id>
4. Return ONLY the JSON object.
"""
