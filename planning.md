# Provenance Guard Planning Spec

## 1. Detection Signals
*Describe the 2+ signals that will be used to classify content.*

- **Signal 1:** Perplexity Score
  - **What it measures:** How surprised a language model is by the choice of words in the text. AI-generated text tends to follow highly predictable patterns (low perplexity), whereas human writing is more unpredictable and varied (high perplexity). More surprised/unpredictable -> more human.
  - **Output format:** Floating-point number (e.g., raw perplexity or normalized between 0.0 and 1.0).
  - **What it misses (blind spots):** Standard, highly common sentences or boilerplate text used frequently by both AI and humans (e.g., "In conclusion, it is important to note..."). These standard phrases will have low perplexity and may be misclassified as AI.
- **Signal 2:** Burstiness
  - **What it measures:** The variation in sentence length and structure across the text. Human writers naturally vary their sentence lengths (e.g., mixing short, punchy sentences with long, complex ones), while AI text tends to be uniform in length and structure. More variation -> more human.
  - **Output format:** Floating-point number (e.g., standard deviation of sentence lengths).
  - **What it misses (blind spots):** Highly structured human creative writing, such as poetry, sonnets, or rhythmic art pieces that require consistent, uniform sentence lengths and repetitive patterns. These will have low burstiness and may be misclassified as AI.
- **Combination Logic:**
  - Min-max scaling will be applied to normalize both raw scores (Perplexity and Burstiness) into a range of [0.0, 1.0].
  - The final confidence score is calculated using a weighted average: `(Normalized Perplexity * 0.6) + (Normalized Burstiness * 0.4)`.

---

## 2. Uncertainty Representation
*Define the confidence score scale and thresholds.*

- **Calibrated Score Mapping:**
  - Raw perplexity (P) and burstiness (B) are min-max normalized to [0, 1]. They are combined as `1.0 - (0.6 * P + 0.4 * B)` to map human characteristics (high variation/surprise) to 0 and AI characteristics to 1.
- **Verdict Thresholds:**
  - **Most Likely Human:** `0 to 0.4`
  - **Uncertain:** `0.4 to 0.7`
  - **Most Likely AI:** `0.7 to 1`
- **Meaning of 0.6 Confidence:**
  - A score of 0.6 would fall under the "Uncertain" category.
---

## 3. Transparency Label Design
*Write out the exact text for each of the three label variants that will be shown to the user.*

- **Most Likely Human (0 to 0.4):**
  > "Verified Human-Written: The structural variation and word choices in this text strongly align with human writing patterns."
- **Uncertain (0.4 to 0.7):**
  > "Uncertain/Mixed: This text exhibits a combination of predictable patterns and style variations. It may be human work that is highly structured, or AI-generated text that has been edited."
- **Most Likely AI (0.7 to 1):**
  > "Likely AI-Generated: This text contains highly predictable word choices and uniform sentence structures characteristic of AI generation."

---

## 4. Appeals Workflow
*Define the workflow for contesting a classification.*

- **Eligibility:** Those that receive a classification of "Most Likely AI" or "Uncertain" and think that it is a false classification can submit an appeal.
- **Information Captured:** 
  - Content and creator id to locate their piece of text.
  - Any evidence to support the creator's claim (e.g., a text explanation of why the creator thinks the classification is incorrect. Any draft history link or information ( like google docs history))
- **System Action:**
  - Status changes (e.g., to "under review")
  - Audit logging details
- **Reviewer Interface:** They can see that the status is under review, their confidence score, the label and that they can check back later on any updates.

---

## 5. Anticipated Edge Cases
*Identify specific content types the system will handle poorly.*

- **Scenario 1 (Structured Poetry/Art Pieces):** Rhythmic poetry or sonnets that intentionally utilize uniform sentence structures, consistent lengths, and repetitive word selections. Because this style lacks variance, the Burstiness signal will register low variation, and the system may misclassify this human-written work as AI.
- **Scenario 2 (Boilerplate or Formal Writing):** Text containing common templates, academic introductory formats, or legal/boilerplate sentences (e.g., "In conclusion, it is important to note..."). These sentences are highly predictable by default, yielding a low Perplexity score, which can lead the system to flag them as AI-generated.

---

## 6. Architecture
*Include the diagram and a brief narrative describing the submission and appeal flows.*

### Diagram (ASCII Art or Mermaid)

```
       [ Client Request ]
               │
               ▼
┌──────────────────────────────┐
│  POST /submit (Submission)   │
└──────────────┬───────────────┘
               │ (Raw Text)
               ▼
┌──────────────────────────────┐
│  2-Signal Detection Pipeline │
│                              │
│  ├─ Perplexity Score (A)     │──► Word Predictability (LLM)
│  └─ Burstiness Heuristics (B)│──► Sentence length variation
└──────────────┬───────────────┘
               │ (Raw Scores)
               ▼
┌──────────────────────────────┐
│     Min-Max Normalization    │──► Normalizes A and B to [0.0, 1.0]
└──────────────┬───────────────┘
               │ (Normalized A & B)
               ▼
┌──────────────────────────────┐
│      Confidence Scoring      │──► Combined Score = 1.0 - (0.6*A + 0.4*B)
└──────────────┬───────────────┘
               │ (Final Score)
               ▼
┌──────────────────────────────┐      Verdict Thresholds:
│  Transparency Label Routing  ├─────►  0.0 - 0.4: Most Likely Human
└──────────────┬───────────────┘        0.4 - 0.7: Uncertain
               │                        0.7 - 1.0: Most Likely AI
               ▼
┌──────────────────────────────┐
│      Audit Log Database      │──► Stores: Timestamp, Content ID, Creator ID,
└──────────────┬───────────────┘            Verdict Label, Scores, Status
               │
               ▼
┌──────────────────────────────┐
│      Structured Output       │──► Returns JSON: Content ID, Verdict Label,
└──────────────────────────────┘                  Confidence Score
```

### Flow Narrative
- **Submission Flow:** Raw text sent to `POST /submit` runs through LLM-perplexity and burstiness analyzers, scales the outputs, calculates a weighted confidence score, selects the corresponding transparency label, writes a structured entry to the database audit log, and returns the classification metadata to the client.
- **Appeal Flow:** If a user appeals a classification via `POST /appeal`, the system updates the original log status to "under review", records the creator's reasoning/evidence in the audit log, and returns a confirmation response.

---

## 7. AI Tool Plan

### Milestone 3: Submission Endpoint & First Signal
- **Spec Sections to Provide:** 
  - Section 1 (Detection Signals - Signal 1: Perplexity Score)
  - Section 6 (Architecture Diagram - Submission Flow)
- **Generation Requests:**
  - Ask the AI tool to generate a Flask app skeleton with a stubbed `POST /submit` route.
  - Ask it to implement the first signal function to call the Groq Llama model API calculating the word probability perplexity score.
- **Verification Plan:**
  - Test the endpoint manually using curl to ensure it returns a structured JSON output with placeholder values.
  - Call the perplexity function directly using python scripts with sample inputs to verify that it generates valid perplexity scores before integration.

### Milestone 4: Second Signal & Confidence Scoring
- **Spec Sections to Provide:**
  - Section 1 (Detection Signals - Signal 2: Burstiness + Combination Logic)
  - Section 2 (Uncertainty Representation - Calibrated Score Mapping)
  - Section 6 (Architecture Diagram)
- **Generation Requests:**
  - Ask for a standalone Python function calculating Burstiness (sentence structure variation) using text tools (e.g. NLTK or custom splits).
  - Ask for the confidence scoring combination function that applies min-max scaling and calculates the combined score: `1.0 - (0.6 * P + 0.4 * B)`.
- **Verification Plan:**
  - Test with 4 distinct text types (obviously AI-written, casual human text, formal human document, lightly edited AI text).
  - Print out individual and combined scores to verify that the scores vary meaningfully and align with verdict thresholds.

### Milestone 5: Production Layer
- **Spec Sections to Provide:**
  - Section 3 (Transparency Label Design)
  - Section 4 (Appeals Workflow)
  - Section 6 (Architecture Diagram - Appeal Flow)
- **Generation Requests:**
  - Ask for a transparency label mapping function matching the threshold rules.
  - Ask for a `POST /appeal` endpoint updating database/log records to "under review" and saving reasoning.
  - Ask for Flask-Limiter integration on `/submit` to enforce the chosen rate limits.
- **Verification Plan:**
  - Ensure all 3 transparency labels are correctly reached by adjusting test scores.
  - Submit an appeal using `content_id` and confirm it logs correctly.
  - Run a shell loop to fire requests rapidly to verify rate-limiting correctly triggers HTTP 429.


