#!/usr/bin/env python3
"""
Script to extract YouTube video transcripts using yt-dlp.
"""
import sys
import json
import subprocess
import os
import tempfile
import re

def clean_transcript(text):
    """Clean and deduplicate transcript text."""
    # Remove timestamp tags like <00:00:21.119>
    text = re.sub(r'<[\d:\.]+>', '', text)
    # Remove other HTML/VTT tags
    text = re.sub(r'<[^>]+>', '', text)
    # Remove "Kind: captions Language: en" headers
    text = re.sub(r'Kind:\s*captions\s*Language:\s*\w+', '', text)
    text = re.sub(r'\[music\]', '', text)

    # Split into words and deduplicate consecutive repeated phrases
    words = text.split()
    cleaned_words = []
    i = 0

    while i < len(words):
        # Try to find repeating patterns
        found_repeat = False
        for pattern_length in range(min(20, len(words) - i), 0, -1):
            if i + pattern_length * 2 <= len(words):
                pattern = words[i:i+pattern_length]
                next_pattern = words[i+pattern_length:i+pattern_length*2]
                if pattern == next_pattern:
                    # Found a repeat, add pattern once and skip ahead
                    cleaned_words.extend(pattern)
                    i += pattern_length * 2
                    # Skip additional repeats
                    while i + pattern_length <= len(words):
                        if words[i:i+pattern_length] == pattern:
                            i += pattern_length
                        else:
                            break
                    found_repeat = True
                    break

        if not found_repeat:
            cleaned_words.append(words[i])
            i += 1

    # Join and clean up spacing
    text = ' '.join(cleaned_words)
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()

    return text

def get_video_info(url):
    """Extract video title and transcript."""
    try:
        # Get video metadata including title
        cmd_info = [
            'yt-dlp',
            '--skip-download',
            '--print', '%(title)s',
            url
        ]
        title = subprocess.check_output(cmd_info, text=True, stderr=subprocess.DEVNULL).strip()

        # Create a temporary directory
        with tempfile.TemporaryDirectory() as tmpdir:
            # Get transcript using simpler method
            cmd_transcript = [
                'yt-dlp',
                '--skip-download',
                '--write-auto-subs',
                '--sub-lang', 'en',
                '--output', f'{tmpdir}/video',
                url
            ]
            subprocess.run(cmd_transcript, check=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)

            # Find the subtitle file
            subtitle_files = [f for f in os.listdir(tmpdir) if f.endswith(('.vtt', '.en.vtt'))]

            if not subtitle_files:
                # Try manual subtitles
                cmd_manual = [
                    'yt-dlp',
                    '--skip-download',
                    '--write-subs',
                    '--sub-lang', 'en',
                    '--output', f'{tmpdir}/video',
                    url
                ]
                subprocess.run(cmd_manual, check=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                subtitle_files = [f for f in os.listdir(tmpdir) if f.endswith(('.vtt', '.en.vtt'))]

            if not subtitle_files:
                return {
                    'title': title,
                    'transcript': None,
                    'url': url,
                    'error': 'No subtitles available for this video'
                }

            # Read the VTT file
            subtitle_file = os.path.join(tmpdir, subtitle_files[0])
            with open(subtitle_file, 'r', encoding='utf-8') as f:
                vtt_content = f.read()

            # Parse VTT to extract text only
            lines = vtt_content.split('\n')
            transcript_lines = []
            for line in lines:
                line = line.strip()
                # Skip WEBVTT header, timestamps, and empty lines
                if line and not line.startswith('WEBVTT') and '-->' not in line:
                    # Skip sequence numbers
                    if not line.isdigit():
                        transcript_lines.append(line)

            # Join all lines
            raw_transcript = ' '.join(transcript_lines)

            # Clean and deduplicate
            transcript = clean_transcript(raw_transcript)

            return {
                'title': title,
                'transcript': transcript,
                'url': url
            }

    except subprocess.CalledProcessError as e:
        print(f"Error fetching video: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: get_youtube_transcript.py <youtube_url>", file=sys.stderr)
        sys.exit(1)

    url = sys.argv[1]
    result = get_video_info(url)
    print(json.dumps(result, indent=2))
