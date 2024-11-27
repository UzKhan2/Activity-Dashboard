import os
import traceback
from urllib.parse import urlparse
from dataclasses import dataclass
import xml.etree.ElementTree as ET
from flask import render_template, jsonify
from typing import List, Dict, Any, Optional, Tuple


@dataclass
class MovieInfo:
    title: str
    rating: Optional[int] = None
    watched_date: Optional[str] = None
    rewatch: str = 'No'
    year: Optional[str] = None
    link: Optional[str] = None
    tmdb_id: Optional[str] = None
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None

class LetterboxdAPI:
    def __init__(self, trakt_api):
        self.trakt_api = trakt_api

    def parse_letterboxd_rss(self, xml_content: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Parse Letterboxd RSS feed and return formatted data with images and statistics"""
        if not xml_content or not xml_content.strip():
            print("Warning: Empty XML content received")
            return [], self._calculate_stats([], [])
            
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            print(f"XML parsing error: {str(e)}")
            print(f"First 200 characters of XML content: {xml_content[:200]}")
            return [], self._calculate_stats([], [])
        
        movies = []
        ratings = []
        
        # Print feed information for debugging
        channel = root.find('.//channel')
        if channel is not None:
            print(f"Feed title: {channel.findtext('title', 'No title found')}")
            print(f"Feed description: {channel.findtext('description', 'No description found')}")
        
        for item in root.findall('.//item'):
            try:
                title = item.findtext('title', '').strip()
                if not title:
                    continue
                
                movie_name = title
                rating = None
                
                # Extract rating if present
                if ' - ★' in title:
                    parts = title.split(' - ★')
                    if len(parts) == 2:
                        movie_name = parts[0].strip()
                        rating = len(parts[1].strip())
                        if rating > 0:
                            ratings.append(rating)
                
                movie = self._parse_movie_item(item, movie_name, rating)
                if movie:
                    # Debug logging
                    print(f"\nProcessed movie:")
                    print(f"Title: {movie['title']}")
                    print(f"TMDb ID: {movie['tmdb_id']}")
                    print(f"Poster URL: {movie['poster_url']}")
                    movies.append(movie)
                    
            except Exception as e:
                print(f"Error parsing movie item: {str(e)}")
                continue
        
        stats = self._calculate_stats(movies, ratings)
        return movies, stats

    def _parse_movie_item(self, item: ET.Element, movie_name: str, rating: Optional[int]) -> Optional[Dict[str, Any]]:
        """Parse individual movie item from RSS feed"""
        try:
            # Extract basic information
            watched_date = item.find('.//{https://letterboxd.com}watchedDate')
            rewatch = item.find('.//{https://letterboxd.com}rewatch')
            film_year = item.find('.//{https://letterboxd.com}filmYear')
            link = item.findtext('link', '')
            
            # First try to get TMDb ID from the RSS feed
            tmdb_id = None
            for namespace in [
                './/{https://themoviedb.org}movieId',
                './/movieId',
                './/{http://themoviedb.org}movieId'
            ]:
                tmdb_id_elem = item.find(namespace)
                if tmdb_id_elem is not None:
                    tmdb_id = tmdb_id_elem.text
                    print(f"Found TMDb ID {tmdb_id} using namespace: {namespace}")
                    break
            
            # Get images if TMDb ID is available
            poster_url = None
            backdrop_url = None
            if tmdb_id:
                print(f"Fetching TMDb images for movie {movie_name} with ID {tmdb_id}")
                images = self.trakt_api.get_tmdb_images(tmdb_id, media_type='movie')
                if images:
                    poster_url = images.get('poster_url')
                    backdrop_url = images.get('backdrop_url')
                    print(f"Retrieved poster URL: {poster_url}")
            
            # If no TMDb poster, try to extract from description
            if not poster_url:
                description = item.findtext('description', '')
                if description:
                    try:
                        import re
                        # Look for image URL in description
                        img_match = re.search(r'src="([^"]+)"', description)
                        if img_match:
                            poster_url = img_match.group(1)
                            print(f"Extracted poster URL from description: {poster_url}")
                    except Exception as e:
                        print(f"Error extracting image from description: {str(e)}")
            
            # Create movie object
            movie = MovieInfo(
                title=movie_name,
                rating=rating,
                watched_date=watched_date.text if watched_date is not None else None,
                rewatch=rewatch.text if rewatch is not None else 'No',
                year=film_year.text if film_year is not None else None,
                link=link,
                tmdb_id=tmdb_id,
                poster_url=poster_url,
                backdrop_url=backdrop_url
            )
            
            return vars(movie)
            
        except Exception as e:
            print(f"Error parsing movie item details: {str(e)}")
            traceback.print_exc()
            return None

    def _calculate_stats(self, movies: List[Dict[str, Any]], ratings: List[int]) -> Dict[str, Any]:
        """Calculate statistics from movies list"""
        return {
            'total': len(movies),
            'rated': len(ratings),
            'rewatches': len([m for m in movies if m['rewatch'] == 'Yes']),
            'avg_rating': sum(ratings) / len(ratings) if ratings else None
        }

def init_letterboxd_routes(app, trakt_api, fetch_rss_feed):
    """Initialize Letterboxd routes for the Flask application"""
    
    @app.route('/letterboxd')
    def letterboxd():
        """Render the main Letterboxd template"""
        return render_template('letterboxd.html')

    @app.route('/api/letterboxd/movies')
    def letterboxd_movies():
        """API endpoint for movie data"""
        try:
            if not trakt_api:
                from .trakt import TraktAPI
                local_trakt_api = TraktAPI()
            else:
                local_trakt_api = trakt_api

            letterboxd_api = LetterboxdAPI(local_trakt_api)
            
            rss_url = os.getenv('LETTERBOXD_RSS_URL')
            if not rss_url:
                raise ValueError("Letterboxd RSS URL not configured")
                
            parsed_url = urlparse(rss_url)
            if not all([parsed_url.scheme, parsed_url.netloc]):
                raise ValueError("Invalid RSS URL format")
                
            xml_content = fetch_rss_feed(rss_url, feed_type='letterboxd')
            movies, _ = letterboxd_api.parse_letterboxd_rss(xml_content)
            
            # Sort movies by watch date
            movies.sort(key=lambda x: x.get('watched_date', ''), reverse=True)
            
            return jsonify(movies)
            
        except Exception as e:
            print(f"Error fetching movie data: {str(e)}")
            print(traceback.format_exc())
            return jsonify({'error': str(e)}), 500

    @app.route('/api/letterboxd/stats')
    def letterboxd_stats():
        """API endpoint for statistics"""
        try:
            if not trakt_api:
                from .trakt import TraktAPI
                local_trakt_api = TraktAPI()
            else:
                local_trakt_api = trakt_api

            letterboxd_api = LetterboxdAPI(local_trakt_api)
            
            rss_url = os.getenv('LETTERBOXD_RSS_URL')
            if not rss_url:
                raise ValueError("Letterboxd RSS URL not configured")
                
            parsed_url = urlparse(rss_url)
            if not all([parsed_url.scheme, parsed_url.netloc]):
                raise ValueError("Invalid RSS URL format")
                
            xml_content = fetch_rss_feed(rss_url, feed_type='letterboxd')
            _, stats = letterboxd_api.parse_letterboxd_rss(xml_content)
            
            return jsonify(stats)
            
        except Exception as e:
            print(f"Error fetching stats: {str(e)}")
            print(traceback.format_exc())
            return jsonify({'error': str(e)}), 500

def _create_trakt_api():
    """Create a new TraktAPI instance with proper error handling"""
    try:
        from .trakt import TraktAPI
        api = TraktAPI()
        if not api.tmdb_api_key:
            print("Warning: TMDB API key is not set")
        return api
    except Exception as e:
        print(f"Error creating TraktAPI: {str(e)}")
        return None