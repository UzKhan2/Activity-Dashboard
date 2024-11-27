import os
import time
import requests
import traceback
from enum import Enum
from datetime import datetime
from urllib.parse import urlparse
from dataclasses import dataclass
import xml.etree.ElementTree as ET
from flask import render_template, jsonify
from typing import List, Dict, Any, Optional, Tuple

class MediaStatus(Enum):
    WATCHING = "watching"
    READING = "reading"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"
    DROPPED = "dropped"
    PLAN_TO_WATCH = "plan to watch"
    PLAN_TO_READ = "plan to read"

@dataclass
class MediaInfo:
    title: str
    status: Optional[str] = None
    date_updated: Optional[str] = None
    link: Optional[str] = None
    media_type: str = "Unknown"
    image_url: str = '/api/placeholder/225/319'
    mal_id: Optional[str] = None
    synopsis: Optional[str] = None
    score: Optional[float] = None
    genres: List[str] = None
    studios: List[str] = None
    season: Optional[str] = None
    year: Optional[int] = None
    rating: Optional[str] = None
    duration: Optional[str] = None
    # Anime specific fields
    episodes_watched: int = 0
    total_episodes: int = 0
    # Manga specific fields
    chapters_read: int = 0
    total_chapters: int = 0
    volumes_read: int = 0
    total_volumes: int = 0

    def __post_init__(self):
        if self.genres is None:
            self.genres = []
        if self.studios is None:
            self.studios = []

class JikanAPI:
    def __init__(self):
        self.base_url = "https://api.jikan.moe/v4"
        self.last_request = 0
        self.rate_limit = 4
        self.cache = {}
        
    def _rate_limit(self) -> None:
        now = time.time()
        time_since_last = now - self.last_request
        if time_since_last < self.rate_limit:
            sleep_time = self.rate_limit - time_since_last
            print(f"Rate limiting: sleeping for {sleep_time} seconds")
            time.sleep(sleep_time)
        self.last_request = time.time()

    def get_media_info(self, mal_id: str, media_type: str = 'anime') -> Optional[Dict[str, Any]]:
        cache_key = f"{media_type}_{mal_id}"
        if cache_key in self.cache:
            print(f"Using cached data for {media_type} ID: {mal_id}")
            return self.cache[cache_key]

        try:
            self._rate_limit()
            url = f"{self.base_url}/{media_type}/{mal_id}"
            print(f"Fetching {media_type} info from: {url}")
            
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json().get('data', {})
            print(f"Successfully fetched info for {media_type} ID: {mal_id}")
            
            self.cache[cache_key] = data
            return data
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {media_type} info for ID {mal_id}: {str(e)}")
            return None
        except Exception as e:
            print(f"Unexpected error fetching {media_type} info: {str(e)}")
            return None

class MyAnimeListAPI:
    def __init__(self, jikan_client: JikanAPI):
        self.jikan_client = jikan_client

    def parse_mal_rss(self, xml_content: str, media_type: str = 'anime') -> Tuple[List[MediaInfo], Dict[str, Any]]:
        if not xml_content or not xml_content.strip():
            print(f"Warning: Empty XML content received for {media_type}")
            return [], self._create_empty_stats()
            
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            print(f"XML parsing error: {str(e)}")
            print(f"First 200 characters of XML content: {xml_content[:200]}")
            return [], self._create_empty_stats()
        
        media_list = []
        scores = []
        
        channel = root.find('.//channel')
        if channel is not None:
            print(f"Feed title: {channel.findtext('title', 'No title found')}")
            print(f"Feed description: {channel.findtext('description', 'No description found')}")
        
        for item in root.findall('.//item'):
            try:
                media_info = self._parse_media_item(item, media_type)
                if media_info:
                    media_list.append(media_info)
                    if media_info.score:
                        scores.append(media_info.score)
                
            except Exception as e:
                print(f"Error processing {media_type} item: {str(e)}")
                continue
        
        print(f"Successfully parsed {len(media_list)} {media_type} entries")
        stats = self._calculate_stats(media_list, scores, media_type)
        
        return media_list, stats

    def _parse_media_item(self, item: ET.Element, media_type: str) -> Optional[MediaInfo]:
        try:
            title_elem = item.find('title')
            if title_elem is None or not title_elem.text:
                return None
                
            full_title = title_elem.text.strip()
            title = full_title.rsplit(' - ', 1)[0] if ' - ' in full_title else full_title
            item_type = full_title.rsplit(' - ', 1)[1] if ' - ' in full_title else 'Unknown'
            
            media_info = MediaInfo(
                title=title,
                media_type=item_type
            )
            
            link = item.find('link')
            if link is not None and link.text:
                media_info.link = link.text.strip()
                try:
                    parts = link.text.strip().split('/')
                    for i, part in enumerate(parts):
                        if part == media_type and i + 1 < len(parts):
                            media_info.mal_id = parts[i + 1]
                            break
                except Exception as e:
                    print(f"Could not extract MAL ID from link: {link.text}")
            
            description = item.find('description')
            if description is not None and description.text:
                desc_text = description.text.strip()
                desc_text = desc_text.replace('<![CDATA[', '').replace(']]>', '').strip()
                
                self._parse_description(desc_text, media_info, media_type)
            
            pub_date = item.find('pubDate')
            if pub_date is not None and pub_date.text:
                media_info.date_updated = pub_date.text.strip()
            
            if media_info.mal_id and media_info.mal_id.isdigit():
                self._enrich_with_jikan_data(media_info, media_type)
            
            return media_info
            
        except Exception as e:
            print(f"Error parsing {media_type} item: {str(e)}")
            return None

    def _parse_description(self, desc_text: str, media_info: MediaInfo, media_type: str) -> None:
        parts = desc_text.split(' - ')
        if len(parts) == 2:
            status = parts[0].strip().lower()
            media_info.status = status
            
            progress_part = parts[1].split(' of ')
            if len(progress_part) == 2:
                try:
                    progress = int(progress_part[0])
                    total = int(progress_part[1].split(' ')[0])
                    
                    if media_type == 'anime':
                        media_info.episodes_watched = progress
                        media_info.total_episodes = total
                    else:
                        if 'vol' in progress_part[1].lower():
                            media_info.volumes_read = progress
                            media_info.total_volumes = total
                        else:
                            media_info.chapters_read = progress
                            media_info.total_chapters = total
                            
                except ValueError:
                    print(f"Error parsing progress numbers from: {progress_part}")

    def _enrich_with_jikan_data(self, media_info: MediaInfo, media_type: str) -> None:
        jikan_data = self.jikan_client.get_media_info(media_info.mal_id, media_type)
        if jikan_data:
            images = jikan_data.get('images', {})
            jpg_images = images.get('jpg', {})
            media_info.image_url = (
                jpg_images.get('large_image_url') or 
                jpg_images.get('image_url') or 
                jpg_images.get('small_image_url') or 
                media_info.image_url
            )
            
            media_info.synopsis = jikan_data.get('synopsis')
            media_info.score = jikan_data.get('score')
            media_info.genres = [genre['name'] for genre in jikan_data.get('genres', [])]
            media_info.studios = [studio['name'] for studio in jikan_data.get('studios', [])] if media_type == 'anime' else []
            media_info.season = jikan_data.get('season')
            media_info.year = jikan_data.get('year')
            media_info.rating = jikan_data.get('rating')
            media_info.duration = jikan_data.get('duration') if media_type == 'anime' else None
            
            if not media_info.status:
                media_info.status = jikan_data.get('status', '').lower()

    def _calculate_stats(self, media_list: List[MediaInfo], scores: List[float], media_type: str) -> Dict[str, Any]:
        if media_type == 'anime':
            watching_status = MediaStatus.WATCHING.value
            plan_status = MediaStatus.PLAN_TO_WATCH.value
        else:
            watching_status = MediaStatus.READING.value
            plan_status = MediaStatus.PLAN_TO_READ.value

        stats = {
            'total': len(media_list),
            'current': len([m for m in media_list if m.status == watching_status]),
            'completed': len([m for m in media_list if m.status == MediaStatus.COMPLETED.value]),
            'planned': len([m for m in media_list if m.status == plan_status]),
            'avg_score': sum(scores) / len(scores) if scores else None
        }
        return stats

    def _create_empty_stats(self) -> Dict[str, Any]:
        return {
            'total': 0,
            'current': 0,
            'completed': 0,
            'planned': 0,
            'avg_score': None
        }

def init_myanimelist_routes(app, fetch_rss_feed):
    jikan_client = JikanAPI()
    mal_api = MyAnimeListAPI(jikan_client)
    
    def get_media_list(media_type: str):
        try:
            rss_url = os.getenv(f'MAL_{media_type.upper()}_RSS_URL')
            if not rss_url:
                raise ValueError(f"MyAnimeList {media_type} RSS URL not configured")
                
            parsed_url = urlparse(rss_url)
            if not all([parsed_url.scheme, parsed_url.netloc]):
                raise ValueError("Invalid RSS URL format")
            
            xml_content = fetch_rss_feed(rss_url, feed_type='myanimelist')
            media_list, _ = mal_api.parse_mal_rss(xml_content, media_type)
            
            media_list.sort(key=lambda x: x.date_updated or '', reverse=True)
            
            return [vars(media) for media in media_list]
            
        except Exception as e:
            print(f"Error fetching {media_type} list: {str(e)}")
            print(traceback.format_exc())
            return []

    @app.route('/api/myanimelist/anime')
    def get_anime_list():
        try:
            anime_list = get_media_list('anime')
            return jsonify(anime_list)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/myanimelist/manga')
    def get_manga_list():
        try:
            manga_list = get_media_list('manga')
            return jsonify(manga_list)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/myanimelist/stats')
    def get_myanimelist_stats():
        try:
            anime_stats = {}
            manga_stats = {}
            
            anime_rss_url = os.getenv('MAL_ANIME_RSS_URL')
            if anime_rss_url:
                xml_content = fetch_rss_feed(anime_rss_url, feed_type='myanimelist')
                _, anime_stats = mal_api.parse_mal_rss(xml_content, 'anime')
            
            manga_rss_url = os.getenv('MAL_MANGA_RSS_URL')
            if manga_rss_url:
                xml_content = fetch_rss_feed(manga_rss_url, feed_type='myanimelist')
                _, manga_stats = mal_api.parse_mal_rss(xml_content, 'manga')
            
            combined_stats = {
                'total_anime': anime_stats.get('total', 0),
                'total_manga': manga_stats.get('total', 0),
                'watching': anime_stats.get('current', 0),
                'reading': manga_stats.get('current', 0),
                'completed_anime': anime_stats.get('completed', 0),
                'completed_manga': manga_stats.get('completed', 0),
                'planned_anime': anime_stats.get('planned', 0),
                'planned_manga': manga_stats.get('planned', 0),
                'avg_anime_score': anime_stats.get('avg_score'),
                'avg_manga_score': manga_stats.get('avg_score')
            }
            
            return jsonify(combined_stats)
            
        except Exception as e:
            print(f"Error fetching stats: {str(e)}")
            print(traceback.format_exc())
            return jsonify({'error': str(e)}), 500
    
    @app.route('/myanimelist')
    def myanimelist():
        try:
            return render_template('myanimelist.html')
        except Exception as e:
            print(f"Error rendering MyAnimeList page: {str(e)}")
            print(traceback.format_exc())
            return f"Error loading MyAnimeList page: {str(e)}", 500

def format_date(date_str: str) -> str:
    try:
        if date_str:
            date_obj = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %z')
            return date_obj.strftime('%Y-%m-%d %H:%M')
    except Exception:
        pass
    return date_str