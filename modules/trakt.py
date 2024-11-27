import os
import requests
import traceback
from dotenv import load_dotenv
from collections import defaultdict
from datetime import datetime, timedelta
from flask import render_template, jsonify

class TraktAPI:
    def __init__(self):
        load_dotenv()
        self.client_id = os.getenv('TRAKT_CLIENT_ID')
        self.client_secret = os.getenv('TRAKT_CLIENT_SECRET')
        self.tmdb_api_key = os.getenv('TMDB_API_KEY')
        self.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'
        self.base_url = 'https://api.trakt.tv'
        self.tmdb_base_url = 'https://api.themoviedb.org/3'
        self.headers = {
            'Content-Type': 'application/json',
            'trakt-api-version': '2',
            'trakt-api-key': self.client_id,
            'Accept': 'application/json'
        }
        self.access_token = os.getenv('TRAKT_ACCESS_TOKEN')
        if self.access_token:
            self.headers['Authorization'] = f'Bearer {self.access_token}'

    def authenticate(self):
        response = requests.post(
            f'{self.base_url}/oauth/device/code',
            headers={
                'Content-Type': 'application/json'
            },
            json={
                'client_id': self.client_id
            }
        )
        if response.status_code != 200:
            raise Exception('Failed to get device code')
        
        device_code_data = response.json()
        print(f"Please go to {device_code_data['verification_url']} and enter code: {device_code_data['user_code']}")
        
        # Poll for the token
        token_response = requests.post(
            f'{self.base_url}/oauth/device/token',
            headers={
                'Content-Type': 'application/json'
            },
            json={
                'code': device_code_data['device_code'],
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
        )
        
        if token_response.status_code == 200:
            token_data = token_response.json()
            self.access_token = token_data['access_token']
            self.headers['Authorization'] = f'Bearer {self.access_token}'
            print("Successfully authenticated!")
            return token_data
        else:
            raise Exception('Failed to get access token')

    def get_watched_shows(self):
        response = requests.get(
            f'{self.base_url}/sync/watched/shows',
            headers=self.headers,
            params={'extended': 'full'}
        )
        
        if response.status_code != 200:
            print("API Response:", response.text)
            raise Exception('Failed to get watched shows')
        
        shows_data = response.json()
        shows_with_images = []
        
        for show in shows_data:
            if 'show' in show and 'ids' in show['show']:
                tmdb_id = show['show']['ids'].get('tmdb')
                if tmdb_id:
                    images = self.get_tmdb_images(tmdb_id)
                    if images:
                        show['show']['images'] = images
                shows_with_images.append(show)
                
                # Debug print
                #print(f"\nDEBUG - Show: {show['show'].get('title')}")
                #print(f"TMDb ID: {tmdb_id}")
                #print(f"Images: {show['show'].get('images', {})}")
        
        return shows_with_images

    def get_watched_movies(self):
        response = requests.get(
            f'{self.base_url}/sync/watched/movies',
            headers=self.headers,
            params={'extended': 'full,metadata'}
        )
        
        if response.status_code != 200:
            raise Exception('Failed to get watched movies')
        return response.json()

    def get_watched_episodes(self):
        response = requests.get(
            f'{self.base_url}/sync/watched/episodes',
            headers=self.headers,
            params={'extended': 'full,metadata'}
        )
        
        if response.status_code != 200:
            raise Exception('Failed to get watched episodes')
        return response.json()

    def get_watch_history(self, media_type=None, limit=20):
        params = {'limit': limit, 'extended': 'full,metadata'}
        if media_type:
            params['type'] = media_type

        response = requests.get(
            f'{self.base_url}/sync/history',
            headers=self.headers,
            params=params
        )
        
        if response.status_code != 200:
            raise Exception('Failed to get watch history')
        return response.json()

    def get_tmdb_images(self, tmdb_id, media_type='tv'):
        if not self.tmdb_api_key or not tmdb_id:
            return None

        url = f'{self.tmdb_base_url}/{media_type}/{tmdb_id}'
        response = requests.get(url, params={'api_key': self.tmdb_api_key})
        
        if response.status_code == 200:
            data = response.json()
            return {
                'poster_url': f'https://image.tmdb.org/t/p/w500{data.get("poster_path")}' if data.get("poster_path") else None,
                'backdrop_url': f'https://image.tmdb.org/t/p/w1280{data.get("backdrop_path")}' if data.get("backdrop_path") else None
            }
        print(f"TMDb API error: {response.status_code} - {response.text}")
        return None
    
def init_trakt_routes(app):
    trakt_api = TraktAPI()

    @app.route('/trakt')
    def dashboard():
        try:
            return render_template('trakt.html')
        except Exception as e:
            print(f"Error rendering dashboard: {str(e)}")
            return "Error loading dashboard", 500

    @app.route('/api/trakt/stats')
    def get_trakt_stats():
        try:
            shows = trakt_api.get_watched_shows() or []
            movies = trakt_api.get_watched_movies() or []
            episodes = trakt_api.get_watched_episodes() or []

            print(f"Debug - Raw counts: Shows={len(shows)}, Movies={len(movies)}, Episodes={len(episodes)}")

            # Initialize counters
            total_watch_time = 0
            movies_count = 0
            
            # Process episodes
            for episode in episodes:
                try:
                    if isinstance(episode, dict) and 'episode' in episode:
                        runtime = episode['episode'].get('runtime', 0)
                        if runtime:
                            total_watch_time += runtime
                except Exception as e:
                    print(f"Error processing episode: {str(e)}")
                    continue
            
            # Process movies
            for movie in movies:
                try:
                    if isinstance(movie, dict) and 'movie' in movie:
                        runtime = movie['movie'].get('runtime', 0)
                        plays = movie.get('plays', 1)
                        if runtime:
                            total_watch_time += runtime * plays
                        movies_count += 1
                except Exception as e:
                    print(f"Error processing movie: {str(e)}")
                    continue

            # Calculate total hours
            total_hours = round(total_watch_time / 60, 1) if total_watch_time > 0 else 0
            
            stats = {
                'total_shows': len(shows),
                'total_movies': movies_count,
                'total_episodes': len(episodes),
                'total_watch_time': total_hours
            }
            
            print(f"Debug - Calculated stats: {stats}")
            return jsonify(stats)
            
        except Exception as e:
            print(f"Error in get_stats: {str(e)}")
            print(traceback.format_exc())
            return jsonify({'error': str(e)}), 500

    @app.route('/api/shows')
    def get_shows():
        try:
            shows = trakt_api.get_watched_shows() or []
            print(f"Debug - Raw shows count: {len(shows)}")
            
            formatted_shows = []
            for show in shows:
                try:
                    if not isinstance(show, dict) or 'show' not in show:
                        print("Debug - Invalid show format")
                        continue
                        
                    show_data = show['show']
                    if not isinstance(show_data, dict):
                        print("Debug - Invalid show_data format")
                        continue
                    
                    # Get TMDb ID
                    tmdb_id = show_data.get('ids', {}).get('tmdb')
                    if tmdb_id:
                        images = trakt_api.get_tmdb_images(str(tmdb_id))
                    else:
                        images = None
                    
                    formatted_show = {
                        'title': show_data.get('title', ''),
                        'year': show_data.get('year'),
                        'overview': show_data.get('overview', ''),
                        'runtime': show_data.get('runtime', 0),
                        'plays': show.get('plays', 0),
                        'episodes_watched': show.get('plays', 0),
                        'total_episodes': show_data.get('aired_episodes', 0),
                        'last_watched_at': show.get('last_watched_at', ''),
                        'genres': show_data.get('genres', []),
                        'rating': show_data.get('rating', 0),
                        'status': show_data.get('status', ''),
                        'network': show_data.get('network', ''),
                        'poster_url': images.get('poster_url') if images else None,
                        'backdrop_url': images.get('backdrop_url') if images else None
                    }
                    
                    # Only add shows with valid data
                    if formatted_show['title'] and formatted_show['poster_url']:
                        formatted_shows.append(formatted_show)
                        print(f"Debug - Successfully processed show: {formatted_show['title']}")
                        print(f"Debug - Poster URL: {formatted_show['poster_url']}")
                    
                except Exception as e:
                    print(f"Error processing show: {str(e)}")
                    continue
            
            # Sort shows by last watched date
            sorted_shows = sorted(
                formatted_shows,
                key=lambda x: x['last_watched_at'] or '',
                reverse=True
            )
            
            return jsonify(sorted_shows)
                                
        except Exception as e:
            print(f"Error in get_shows: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/movies')
    def get_movies():
        try:
            movies = trakt_api.get_watched_movies() or []
            print(f"Debug - Raw movies count: {len(movies)}")
            
            formatted_movies = []
            for movie in movies:
                try:
                    if not isinstance(movie, dict) or 'movie' not in movie:
                        continue
                    
                    movie_data = movie['movie']
                    if not isinstance(movie_data, dict):
                        continue

                    # Get TMDB images
                    tmdb_id = movie_data.get('ids', {}).get('tmdb')
                    images = None
                    if tmdb_id:
                        images = trakt_api.get_tmdb_images(str(tmdb_id), media_type='movie')
                    
                    formatted_movie = {
                        'title': movie_data.get('title', 'Unknown Title'),
                        'year': movie_data.get('year'),
                        'overview': movie_data.get('overview', ''),
                        'runtime': movie_data.get('runtime', 0),
                        'plays': movie.get('plays', 1),
                        'last_watched_at': movie.get('last_watched_at', ''),
                        'genres': movie_data.get('genres', []),
                        'rating': movie_data.get('rating', 0),
                        'poster_url': images.get('poster_url') if images else None,
                        'backdrop_url': images.get('backdrop_url') if images else None
                    }
                    
                    if formatted_movie['title']:
                        formatted_movies.append(formatted_movie)
                        print(f"Debug - Successfully processed movie: {formatted_movie['title']}")
                        
                except Exception as e:
                    print(f"Error processing movie: {str(e)}")
                    continue
            
            return jsonify(formatted_movies)
            
        except Exception as e:
            print(f"Error in get_movies: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/watch-time')
    def get_watch_time():
        try:
            history = trakt_api.get_watch_history(limit=1000) or []
            
            monthly_stats = defaultdict(lambda: {
                'total_minutes': 0,
                'shows': set(),
                'movies': 0,
                'episodes': 0
            })
            
            for item in history:
                try:
                    watched_at = datetime.strptime(
                        item.get('watched_at', ''),
                        '%Y-%m-%dT%H:%M:%S.%fZ'
                    )
                    month_key = watched_at.strftime('%Y-%m')
                    
                    if item.get('type') == 'episode' and 'episode' in item and 'show' in item:
                        runtime = item['episode'].get('runtime', 0)
                        monthly_stats[month_key]['episodes'] += 1
                        monthly_stats[month_key]['shows'].add(item['show'].get('title', ''))
                    elif 'movie' in item:
                        runtime = item['movie'].get('runtime', 0)
                        monthly_stats[month_key]['movies'] += 1
                    else:
                        runtime = 0
                    
                    monthly_stats[month_key]['total_minutes'] += runtime
                except (ValueError, KeyError) as e:
                    print(f"Error processing history item: {str(e)}")
                    continue
            
            # Format monthly data
            months = []
            for i in range(6):
                date = datetime.now() - timedelta(days=30*i)
                month_key = date.strftime('%Y-%m')
                
                if month_key in monthly_stats:
                    stats = monthly_stats[month_key]
                    shows_count = len(stats['shows'])
                else:
                    stats = {'total_minutes': 0, 'shows': set(), 'movies': 0, 'episodes': 0}
                    shows_count = 0
                
                months.append({
                    'month': date.strftime('%b %Y'),
                    'hours': round(stats['total_minutes'] / 60, 1),
                    'shows': shows_count,
                    'movies': stats['movies'],
                    'episodes': stats['episodes']
                })
            
            return jsonify({
                'months': list(reversed(months)),
                'total_hours': round(sum(m['hours'] for m in months), 1)
            })
            
        except Exception as e:
            print(f"Error in get_watch_time: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/history')
    def get_history():
        try:
            history = trakt_api.get_watch_history(limit=20) or []
            
            formatted_history = []
            for item in history:
                try:
                    if not isinstance(item, dict):
                        continue
                    
                    history_item = {
                        'type': item.get('type', ''),
                        'watched_at': item.get('watched_at', '')
                    }
                    
                    if item.get('type') == 'episode' and 'episode' in item and 'show' in item:
                        episode = item['episode']
                        show = item['show']
                        history_item.update({
                            'show_title': show.get('title', ''),
                            'episode_title': episode.get('title', ''),
                            'season': episode.get('season'),
                            'episode': episode.get('number'),
                            'full_episode_title': (
                                f"S{episode.get('season', 0):02d}E"
                                f"{episode.get('number', episode.get('episode', 0)):02d} - "
                                f"{episode.get('title', '')}"
                            )
                        })
                    elif 'movie' in item:
                        movie = item['movie']
                        history_item.update({
                            'movie_title': movie.get('title', ''),
                            'year': movie.get('year')
                        })
                    
                    formatted_history.append(history_item)
                    
                except Exception as e:
                    print(f"Error processing history item: {str(e)}")
                    continue
            
            return jsonify(formatted_history)
            
        except Exception as e:
            print(f"Error in get_history: {str(e)}")
            return jsonify({'error': str(e)}), 500

    return app