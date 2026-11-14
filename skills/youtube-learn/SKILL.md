---
name: youtube-learn
description: Turn a YouTube video into an interactive multi-session learning experience (explain, quiz, track progress, debrief). Use when the user shares a YouTube URL and wants to learn or study its content. Requires yt-dlp.
---

Paths: `scripts/` is relative to this skill's folder. Progress data lives in `~/.agent-toolkit/data/youtube-learn/` (outside the skill, shared by every harness).

# YouTube Learn Skill

## Purpose
Transform YouTube videos into deep, multi-session learning experiences — no prior video watching required. The skill teaches you the content directly using an Explain→Engage→Confirm model, then tests you, tracks progress across sessions, and generates a personalized debrief.

---

## Storage Structure

```
~/.agent-toolkit/data/youtube-learn/
  {video_id}.json               ← progress, section plan, test results
  {video_id}_transcript.txt     ← full transcript, fetched from YouTube exactly once
  {video_id}_backup.json        ← backup created before a full reset
```

---

## State Schema

```json
{
  "video_id": "string",
  "video_title": "string",
  "video_url": "string",
  "sections": [
    {
      "index": 0,
      "title": "string",
      "transcript_slice": "the portion of transcript covering this section",
      "key_topics": ["string"],
      "key_terms": ["string"],
      "key_points": ["string"],
      "teaching_complete": false,
      "test_complete": false,
      "test_results": [
        {
          "question": "string",
          "verdict": "strong | partial | missed",
          "gap": "string or null"
        }
      ],
      "weak_concepts": ["string"],
      "last_touched": "ISO8601 date string"
    }
  ],
  "current_section_index": 0,
  "debrief_generated": false,
  "sessions": [
    {
      "date": "ISO8601 date string",
      "sections_covered": [0, 1],
      "notes": "string"
    }
  ],
  "created_at": "ISO8601 date string",
  "last_session": "ISO8601 date string"
}
```

---

## Workflow

### Phase 1: Extract & Check State

Extract `video_id` from the URL (the value of `?v=`).

**Check for cached transcript first:**
- If `~/.agent-toolkit/data/youtube-learn/{video_id}_transcript.txt` exists → read it locally. Do NOT call YouTube.
- If it does NOT exist → run: `python3 scripts/get_youtube_transcript.py "<youtube_url>"` → save the transcript text to `{video_id}_transcript.txt` → this is the only time YouTube is contacted.

**Check for progress file:**
- If `{video_id}.json` exists → go to Phase 1b (Returning Learner)
- If it does NOT exist → go to Phase 2 (New Video)

---

### Phase 1b: Returning Learner Flow

Read the progress file. Determine state:

**Case A: All sections complete (all `teaching_complete` AND `test_complete` true)**
```
Welcome back! You've already completed "[video title]".

What would you like to do?
1. Review a specific section (re-teach + re-test)
2. See your weak spots from last time
3. Generate (or regenerate) the debrief document
4. Start completely fresh (wipes progress)
```

**Case B: Partially complete (some sections done, some not)**
```
Welcome back! You're partway through "[video title]".

Last session: {last_session date}
Progress: {N} of {total} sections complete

Sections completed: {list of titles}
Next up: Section {N+1} — "{title}"

Options:
1. Resume from where you left off
2. Restart a specific section
3. Jump to a specific section
4. Start completely fresh
```

**Case C: Progress file corrupted or missing required fields**
Notify user. Offer fresh start. Save corrupted file as `{video_id}_backup.json` before overwriting.

After user selects, proceed to Phase 3 for the appropriate section.

---

### Phase 2: Analyze Content (New Video)

Using the cached transcript:

1. Read the full transcript
2. Segment into **3–7 logical sections** based on natural topic shifts
   - Each section should be a coherent conceptual unit
   - Extract the relevant transcript slice for each section and store it in `transcript_slice`
3. For each section identify:
   - **Title**: Short, descriptive (e.g., "The Expertise Gap Problem")
   - **Key Topics**: 2–4 subject areas
   - **Key Terms**: Important vocabulary introduced
   - **Key Points**: 3–5 core ideas the learner must understand
4. Create the progress file with all sections defined, all flags false, `created_at` = now

Present the plan:
```
I've broken "[video title]" into {N} learning sections:

1. {Title} — {one-line description}
2. {Title} — {one-line description}
...

I'll teach you each section directly, then explore it with you, then test you before moving on.
No need to watch the video first — I've got the content.

Ready to begin with Section 1?
```

Wait for confirmation.

---

### Phase 3: Section Learning Loop

At the start of each session, note the current time as `session_start_time`. Check elapsed time at every response — if ≥ 20 minutes have passed, surface the pacing reminder before the next teaching move.

For each section, load its `transcript_slice` into context. This is the only transcript content needed for that section.

---

#### Step 3A: Section Orientation

Always show this at the start of every section (including on resume and review):

```
─────────────────────────────────────
Section {N}: {Title}
─────────────────────────────────────

Key Topics:  {topic1} · {topic2} · {topic3}

Key Terms:   {term1}, {term2}, {term3}

Key Points:
  • {point 1}
  • {point 2}
  • {point 3}

Let's work through this together.
─────────────────────────────────────
```

---

#### Step 3B: Teaching Phase — Explain → Engage → Confirm

This is the core loop. Repeat it for each Key Point in the section.

**The three moves:**

**EXPLAIN** — Teach the concept directly and concisely. Write as a knowledgeable colleague would brief someone: tight, clear, with the key analogy or example from the actual transcript. No jargon without definition. Aim for 3–6 sentences per concept. Never dump everything at once — one concept per cycle.

**ENGAGE** — Immediately follow the explanation with a single Socratic question about what was just explained. The question should require the learner to process, connect, or apply the concept — not just recall it. Examples:
- "Given that, why do you think they chose folders over a new format?"
- "What problem does this solve that traditional tools couldn't?"
- "How does this change what you'd do differently when building an agent?"

Wait for the learner's response before proceeding.

**CONFIRM** — Respond specifically to what the learner said:
- **On point**: "Exactly — {specific reinforcement of what they got right}." Then move to the next concept.
- **Partially right**: "You've got {correct part} — the piece you're missing is {specific gap}. {one sentence clarification}." Then move on.
- **Off track**: "Interesting angle — let me reframe: {clearer version of the question}." Give one more attempt, then explain and move on.

Never just give the answer without the learner attempting first.
Never stack two concepts in one Explain block.
Never ask two questions at once.

Work through all Key Points this way. Aim for 3–6 full EEC cycles per section depending on depth.

When all Key Points have been covered, mark `teaching_complete: true` in the progress file and save it.

---

#### Step 3C: Section Test

Transition:
```
Good work on Section {N}. Let's see what stuck — closed book from here.
I'll ask you {N} questions. Answer as fully as you can.
```

Scale question count:
- 2 key points → 2 questions
- 3–4 key points → 3–4 questions
- 5+ key points → 5 questions

Rules:
- One question at a time. Wait for response before proceeding.
- After each response, give a verdict:
  - **Strong**: "Exactly right." + one-line reinforcement. Move on.
  - **Partial**: "You got {X} — you missed {specific named concept}. Flagging for review." Move on.
  - **Missed**: "The answer: {concise answer}. Flagging for review." Move on.
- Record each result in `test_results` for this section.
- Add missed/partial concept names to `weak_concepts`.

After all questions:
```
Section {N} test complete.
Strong: {count} | Partial: {count} | Missed: {count}

{if weak_concepts}: Flagged for review: {list}

Ready for Section {N+1}?
```

Mark `test_complete: true`, set `last_touched` to now. Save progress file.

---

#### Step 3D: Pacing Reminder

At every response, check elapsed time since `session_start_time`.

If ≥ 20 minutes:
```
⏱ We've been at this for about 20 minutes. Want to keep going or wrap up here?
```
- Continuing: reset clock, proceed.
- Stopping: go to Phase 4b (Mid-Video Stop).

---

### Phase 4: Session End Handling

#### Phase 4a: All Sections Complete

```
You've made it through all {N} sections of "[video title]".

Overall performance:
  Strong:  {total}
  Partial: {total}
  Missed:  {total}

{if weak_concepts exist}:
Concepts to revisit: {list}

Would you like me to generate your personalized debrief now?
```

If yes → Phase 5.

#### Phase 4b: Mid-Video Stop

```
Session saved.

Completed: {list of section titles}
Next up:   Section {N} — "{title}"

{if weak concepts from today}: Today's flagged concepts: {list}

Resume next time with:
/youtube-learn {url}
```

Set `last_session` = now. Append to `sessions` array. Save progress file.

---

### Phase 5: Debrief Generation

Generate only when:
- All sections complete and user confirms, OR
- User explicitly requests it

The debrief is **personalized to actual performance**:
- Weak concepts (missed/partial) get ⚠️ marker and expanded explanation with extra examples
- Strong concepts get concise entries
- Self-Assessment questions prioritize concepts the learner struggled with
- Next Steps calls out specific gaps

Save to: `/Users/ismar.dupanovic/Desktop/{topic_name}_reference.md`
Use snake_case from video title.

#### Debrief Structure:

```markdown
# 🎯 {Video Title}
> {One-line tagline}

---

## 🔄 Core Paradigm Shift
OLD WAY → NEW WAY
The Big Idea and why it matters.

---

## 🧠 Section Summaries

### Section 1: {Title}
Key points, key terms, core insight.

### Section 2: {Title}
...

---

## 📚 Key Concepts
Logically organized.
Weak concepts marked ⚠️ with expanded explanation.

---

## 🔤 Terminology
Alphabetically sorted. Concise definitions with context.

---

## ⚖️ Decision Rules & Heuristics
When to X vs Y. Clear criteria. Practical guidance.

---

## 🛠️ Practical Patterns
Step-by-step workflows. Best practices from the video.

---

## 🎨 Analogies & Mental Models
Memorable metaphors from the transcript.

---

## 💡 Key Insights & Takeaways
Numbered. Actionable. "Stop doing X, start doing Y" framing.

---

## 🎓 Your Performance Summary
Strong:  {list}
Partial: {list — expanded notes above}
Missed:  {list — marked ⚠️ above with full explanation}

---

## 📋 Self-Assessment Questions
8–12 questions. Hardest concepts first.
"If you can answer these clearly, you've internalized the material."

---

## 🔗 Next Steps
- Concepts to revisit: {weak list with specific advice}
- How to go deeper
- Actionable first step

> "{Memorable quote from the transcript}"

---

## 📎 Metadata
- Source: {video_url}
- Video: {video_title}
- Sessions: {count}
- Debrief generated: {date}
- Sections covered: {list}
```

**Style rules:**
- Emojis on headers as shown
- Horizontal rules between major sections
- Tables for comparisons
- Code blocks for examples
- ✓ / ❌ for pros/cons
- **Bold** key terms on first use
- ASCII diagrams for complex relationships
- ⚠️ on weak concepts with fuller treatment

After saving:
```
Debrief saved to ~/Desktop/{filename}.md
Personalized to your session — harder concepts have expanded coverage.
```

Mark `debrief_generated: true`. Save progress file.

---

### Returning Learner: Review Mode

**Specific section review:**
1. Show orientation brief (Step 3A)
2. Run abbreviated EEC pass — if `teaching_complete` was already true, keep it shorter but still use Explain→Engage→Confirm
3. Run fresh test (new questions where possible; reuse flagged ones otherwise)
4. Append new results to `test_results` — do not overwrite prior results

**Weak spots review:**
1. List all `weak_concepts` across sections with section context
2. Ask: "Want to work through all of them, or pick specific ones?"
3. For each: brief Explain → Engage question → 1–2 test questions
4. Update results

---

## Agent Behavior Rules (Non-Negotiable)

1. **Never re-fetch the transcript if `{video_id}_transcript.txt` exists.** Read locally.
2. **Load only the current section's `transcript_slice` per section.** Not the full transcript.
3. **One concept per EEC cycle.** Never batch multiple concepts into one Explain block.
4. **One question at a time.** Never stack questions.
5. **Always wait for learner response before proceeding.**
6. **Always show Section Orientation (3A)** — never skip it, even on resume or review.
7. **Save progress file after every section test completes.** Never lose results.
8. **Check elapsed time at every response.** Surface 20-min reminder as soon as threshold is crossed.
9. **Name gaps specifically.** Not "you missed something" — "you didn't mention progressive disclosure."
10. **Never generate the debrief without user confirmation** (except auto-offer at completion).
11. **State file is source of truth.** On conflict between memory and file, trust the file.

---

## File Reference

| File | Created | Purpose |
|------|---------|---------|
| `{video_id}_transcript.txt` | First load only | Full transcript, never re-fetched |
| `{video_id}.json` | First load | Progress, section plan, test results |
| `{video_id}_backup.json` | On fresh reset only | Safety copy before wipe |
| `~/Desktop/{topic}_reference.md` | On debrief request | Personalized reference document |
