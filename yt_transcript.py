import argparse
import os
import re
import time
from typing import Dict, List, Optional, Union

import googleapiclient.discovery
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound


class YouTubeTranscriptExtractor:
    """A class to extract transcripts from YouTube videos."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the YouTube Transcript Extractor.
        
        Args:
            api_key: YouTube Data API key (optional, needed for channel/playlist operations)
        """
        self.api_key = api_key
        if api_key:
            self.youtube = googleapiclient.discovery.build(
                "youtube", "v3", developerKey=api_key
            )
        
    def get_video_transcript(self, video_id: str, language: Optional[str] = None) -> Dict:
        """
        Extract transcript for a single video.
        
        Args:
            video_id: YouTube video ID
            language: Language code for transcript (e.g., 'en', 'es')
            
        Returns:
            Dictionary containing video ID and transcript text
            
        Raises:
            TranscriptsDisabled: If transcripts are disabled for the video
            NoTranscriptFound: If no transcript could be found
        """
        try:
            if language:
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                transcript = transcript_list.find_transcript([language])
                transcript_data = transcript.fetch()
            else:
                transcript_data = YouTubeTranscriptApi.get_transcript(video_id)
            
            # Combine all text segments into a single transcript
            full_transcript = " ".join([item['text'] for item in transcript_data])
            
            # Clean up the transcript (remove unnecessary spaces, line breaks)
            full_transcript = re.sub(r'\s+', ' ', full_transcript).strip()
            
            return {
                "video_id": video_id,
                "transcript": full_transcript
            }
            
        except (TranscriptsDisabled, NoTranscriptFound) as e:
            print(f"Error extracting transcript for video {video_id}: {str(e)}")
            return {
                "video_id": video_id,
                "transcript": None,
                "error": str(e)
            }
    
    def extract_video_id_from_url(self, url: str) -> Optional[str]:
        """
        Extract YouTube video ID from a URL.
        
        Args:
            url: YouTube video URL
            
        Returns:
            Video ID or None if not found
        """
        # Handle youtu.be short URLs
        if 'youtu.be' in url:
            return url.split('/')[-1].split('?')[0]
        
        # Handle standard youtube.com URLs
        video_id_match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', url)
        if video_id_match:
            return video_id_match.group(1)
        
        # If the input is already just a video ID
        if re.match(r'^[0-9A-Za-z_-]{11}$', url):
            return url
            
        return None
    
    def get_playlist_video_ids(self, playlist_id: str, max_results: int = 50) -> List[str]:
        """
        Get all video IDs from a YouTube playlist.
        
        Args:
            playlist_id: YouTube playlist ID
            max_results: Maximum number of videos to retrieve
            
        Returns:
            List of video IDs
        """
        if not self.api_key:
            raise ValueError("YouTube API key is required for playlist operations")
            
        video_ids = []
        next_page_token = None
        
        while True:
            request = self.youtube.playlistItems().list(
                part="contentDetails",
                playlistId=playlist_id,
                maxResults=min(max_results - len(video_ids), 50),
                pageToken=next_page_token
            )
            
            try:
                response = request.execute()
                
                for item in response['items']:
                    video_ids.append(item['contentDetails']['videoId'])
                    
                next_page_token = response.get('nextPageToken')
                
                if not next_page_token or len(video_ids) >= max_results:
                    break
                    
            except HttpError as e:
                print(f"Error retrieving playlist videos: {e}")
                break
                
        return video_ids
    
    def get_channel_video_ids(self, channel_id: str, max_results: int = 50) -> List[str]:
        """
        Get video IDs from a YouTube channel's uploads.
        
        Args:
            channel_id: YouTube channel ID
            max_results: Maximum number of videos to retrieve
            
        Returns:
            List of video IDs
        """
        if not self.api_key:
            raise ValueError("YouTube API key is required for channel operations")
            
        # First, get the uploads playlist ID for this channel
        channel_response = self.youtube.channels().list(
            part="contentDetails",
            id=channel_id
        ).execute()
        
        if not channel_response['items']:
            print(f"Channel {channel_id} not found")
            return []
            
        uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        
        # Then get videos from this playlist
        return self.get_playlist_video_ids(uploads_playlist_id, max_results)
    
    def extract_transcripts_batch(self, video_ids: List[str], language: Optional[str] = None, 
                                  output_dir: Optional[str] = None, delay: float = 0.5) -> List[Dict]:
        """
        Extract transcripts for multiple videos.
        
        Args:
            video_ids: List of YouTube video IDs
            language: Language code for transcript
            output_dir: Directory to save individual transcript files
            delay: Delay between API requests in seconds
            
        Returns:
            List of dictionaries containing video IDs and transcripts
        """
        results = []
        
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        for i, video_id in enumerate(video_ids):
            print(f"Processing video {i+1}/{len(video_ids)}: {video_id}")
            
            transcript_data = self.get_video_transcript(video_id, language)
            results.append(transcript_data)
            
            # Save to file if output directory specified
            if output_dir and transcript_data.get('transcript'):
                output_file = os.path.join(output_dir, f"{video_id}.txt")
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(transcript_data['transcript'])
                print(f"Saved transcript to {output_file}")
                
            # Add delay to avoid hitting API rate limits
            if i < len(video_ids) - 1:
                time.sleep(delay)
                
        return results
        
    def extract_from_url(self, url: str, language: Optional[str] = None) -> Dict:
        """
        Extract transcript from a YouTube URL.
        
        Args:
            url: YouTube video, playlist, or channel URL
            language: Language code for transcript
            
        Returns:
            Dictionary with transcript data
        """
        # Extract video ID from URL
        if 'youtube.com/watch' in url or 'youtu.be/' in url:
            video_id = self.extract_video_id_from_url(url)
            if not video_id:
                return {"error": "Invalid YouTube video URL"}
            return self.get_video_transcript(video_id, language)
            
        # Handle playlist URLs
        elif 'youtube.com/playlist' in url:
            playlist_id_match = re.search(r'list=([^&]+)', url)
            if not playlist_id_match:
                return {"error": "Invalid YouTube playlist URL"}
                
            playlist_id = playlist_id_match.group(1)
            video_ids = self.get_playlist_video_ids(playlist_id)
            return {
                "playlist_id": playlist_id,
                "transcripts": self.extract_transcripts_batch(video_ids, language)
            }
            
        # Handle channel URLs
        elif any(x in url for x in ['youtube.com/channel/', 'youtube.com/c/', 'youtube.com/user/']):
            if not self.api_key:
                return {"error": "YouTube API key required for channel operations"}
                
            # Handle different channel URL formats
            if 'youtube.com/channel/' in url:
                channel_id = url.split('youtube.com/channel/')[1].split('/')[0]
            else:
                # For custom URLs like /c/ or /user/, we need to look up the channel ID
                username = url.split('/')[-1]
                try:
                    if 'youtube.com/c/' in url:
                        response = self.youtube.search().list(
                            part="snippet",
                            q=username,
                            type="channel",
                            maxResults=1
                        ).execute()
                    else:  # /user/
                        response = self.youtube.channels().list(
                            part="id",
                            forUsername=username
                        ).execute()
                        
                    if not response.get('items'):
                        return {"error": f"Channel not found: {username}"}
                        
                    channel_id = response['items'][0]['id']
                except HttpError as e:
                    return {"error": f"YouTube API error: {str(e)}"}
            
            video_ids = self.get_channel_video_ids(channel_id)
            return {
                "channel_id": channel_id,
                "transcripts": self.extract_transcripts_batch(video_ids, language)
            }
            
        return {"error": "URL not recognized as YouTube video, playlist, or channel"}


def main():
    """Command-line interface for the transcript extractor."""
    parser = argparse.ArgumentParser(description="Extract transcripts from YouTube videos")
    
    parser.add_argument("input", help="YouTube video URL, ID, playlist URL, or channel URL")
    parser.add_argument("--api-key", help="YouTube Data API key (required for playlists/channels)")
    parser.add_argument("--language", help="Language code (e.g., 'en', 'es')")
    parser.add_argument("--output-dir", help="Directory to save transcript files")
    parser.add_argument("--video-list", help="File containing list of video IDs or URLs")
    
    args = parser.parse_args()
    
    extractor = YouTubeTranscriptExtractor(api_key=args.api_key)
    
    # Handle batch processing from file
    if args.video_list:
        with open(args.video_list, 'r') as f:
            video_urls = [line.strip() for line in f if line.strip()]
            
        video_ids = []
        for url in video_urls:
            video_id = extractor.extract_video_id_from_url(url)
            if video_id:
                video_ids.append(video_id)
            else:
                print(f"Could not extract video ID from: {url}")
                
        results = extractor.extract_transcripts_batch(
            video_ids, 
            language=args.language,
            output_dir=args.output_dir
        )
        
        # Print summary
        successful = sum(1 for r in results if r.get('transcript'))
        print(f"\nProcessed {len(results)} videos, {successful} transcripts extracted")
        
    # Handle single video, playlist, or channel
    else:
        result = extractor.extract_from_url(args.input, args.language)
        
        if 'error' in result:
            print(f"Error: {result['error']}")
        elif 'transcript' in result:
            # Single video result
            if result['transcript']:
                print(f"\nTranscript for video {result['video_id']}:")
                print(result['transcript'][:1000] + "..." if len(result['transcript']) > 1000 else result['transcript'])
                
                if args.output_dir:
                    os.makedirs(args.output_dir, exist_ok=True)
                    output_file = os.path.join(args.output_dir, f"{result['video_id']}.txt")
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(result['transcript'])
                    print(f"\nSaved complete transcript to {output_file}")
            else:
                print(f"\nNo transcript available for video {result['video_id']}")
        else:
            # Playlist or channel result
            source_type = "playlist" if "playlist_id" in result else "channel"
            source_id = result.get("playlist_id") or result.get("channel_id")
            
            transcripts = result.get("transcripts", [])
            successful = sum(1 for t in transcripts if t.get('transcript'))
            
            print(f"\nProcessed {len(transcripts)} videos from {source_type} {source_id}")
            print(f"Successfully extracted {successful} transcripts")
            
            if args.output_dir:
                print(f"Transcripts saved to {args.output_dir}")


if __name__ == "__main__":
    main()